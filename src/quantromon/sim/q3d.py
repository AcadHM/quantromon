"""Phase 3: Ansys Q3D validator for the Palace C-matrix.

This is the Qiskit Metal electrostatic path (tutorial 4.01, renderer
name ``q3d``). It is Q3D Extractor inside Ansys Electronics Desktop, not
HFSS eigenmode. Same P1/P2/P3 Metal design as Palace. No lumped JJ C.

This Ubuntu box cannot launch AEDT (Windows COM). Default is --dry-run:
print the Palace table and write an empty comparison CSV. On a Windows
machine with AEDT, use --run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from quantromon.paths import outdir, reference_outdir

# Palace numbers from the runs that actually finished. See
# out/phase3_palace_reference.csv and devnotes/phase3.md.
PALACE_CASES = {
    "pads": {
        "include_al_leads": False,
        "include_jj_fingers": False,
        "palace_file": "phase2_C_fF_coarse.csv",
        "palace_term_map": {1: "P3", 2: "P1", 3: "P2"},
        "palace_CJ_P1P2_fF": 27.85,
        "palace_CJ_P3P2_fF": 27.64,
        "palace_CR_P1P3_fF": 572.63,
        "note": "Palace file is pads+1um stubs, not Ta-only. Closest frozen C.",
    },
    "al_meander": {
        "include_al_leads": True,
        "include_jj_fingers": False,
        "palace_file": "phase2_C_fF_al_meander.csv",
        "palace_term_map": {1: "P3", 2: "P1", 3: "P2"},
        "palace_CJ_P1P2_fF": 32.74,
        "palace_CJ_P3P2_fF": 32.54,
        "palace_CR_P1P3_fF": 600.27,
        "note": "Main comparison. L2D2100 cut at y=0. No L2D2400.",
    },
}


def ansys_status() -> tuple[bool, str]:
    """True if this process can talk to Ansys Q3D via Metal's COM renderer."""
    if sys.platform != "win32":
        return False, f"platform is {sys.platform}; AEDT Q3D via pyEPR is Windows COM"
    try:
        import pythoncom  # noqa: F401
        import pyEPR  # noqa: F401
    except ImportError as exc:
        return False, f"missing Ansys Python stack ({exc})"
    return True, "Windows + pyEPR import ok (AEDT still has to be installed)"


def load_palace_matrix(path: Path) -> np.ndarray:
    C = np.loadtxt(path, delimiter=",")
    if C.shape != (3, 3):
        raise RuntimeError(f"{path} is not a 3x3 C matrix, got {C.shape}")
    return C


def names_from_q3d_index(index) -> list[str]:
    """Map Q3D net names onto P1/P2/P3. Abort if a name is missing or extra."""
    mapped = []
    for raw in index:
        s = str(raw).upper()
        hit = [n for n in ("P1", "P2", "P3") if n in s]
        if len(hit) != 1:
            raise RuntimeError(f"cannot map Q3D net {raw!r} to a single P1/P2/P3")
        mapped.append(hit[0])
    if sorted(mapped) != ["P1", "P2", "P3"]:
        raise RuntimeError(f"Q3D nets mapped to {mapped}, expected P1 P2 P3 only")
    return mapped


def dataframe_to_maxwell_p123(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Reorder a 3x3 Maxwell matrix so rows/cols are P1, P2, P3."""
    if df.shape != (3, 3):
        raise RuntimeError(
            f"Q3D matrix is {df.shape}, not 3x3. "
            "A ground net probably leaked in. Delete ground_main_plane."
        )
    names = names_from_q3d_index(df.index)
    order = ["P1", "P2", "P3"]
    loc = [names.index(n) for n in order]
    C = np.asarray(df.values, dtype=float)[np.ix_(loc, loc)]
    # Palace and Ansys Maxwell: mutuals are negative. If the solver returned
    # a SPICE matrix (positive mutuals), flip off-diagonals.
    off = C[np.triu_indices(3, 1)]
    if np.all(off > 0):
        C = -C
        np.fill_diagonal(C, -np.diag(C))
    return C, order


def interpret_named(C_fF: np.ndarray) -> dict:
    from quantromon.sim.palace import interpret_maxwell_fF

    return interpret_maxwell_fF(C_fF, {1: "P1", 2: "P2", 3: "P3"})


def _allow_pandas_delim_whitespace() -> None:
    """pyEPR still passes delim_whitespace; pandas 2.2+ removed that kwarg."""
    if getattr(pd.read_csv, "_quantromon_delim_patch", False):
        return
    orig = pd.read_csv

    def read_csv(*args, **kwargs):
        if kwargs.pop("delim_whitespace", False):
            kwargs["sep"] = r"\s+"
            kwargs.setdefault("engine", "python")
        return orig(*args, **kwargs)

    read_csv._quantromon_delim_patch = True
    pd.read_csv = read_csv


def _ansys_object_names(q3d) -> list[str]:
    if q3d.pinfo is None:
        return []
    return list(q3d.pinfo.get_all_object_names())


def _delete_ground_if_present(q3d) -> None:
    """Remove Metal's chip ground sheet. Palace has no on-chip ground.

    HfssModeler has no ``.delete``. Swallowing that AttributeError left
    ``ground_main_plane`` in Q3D Unassigned, which Ansys treats as grounded
    and screens ``C_R``.
    """
    before = _ansys_object_names(q3d)
    print("ansys objects before ground delete:", before)
    targets = [name for name in before if name.lower().startswith("ground_")]
    if not targets:
        print("no ground_* object in Ansys")
    else:
        q3d.modeler._modeler.Delete(
            ["NAME:Selections", "Selections:=", ",".join(targets)]
        )
        print("deleted", targets)
    after = _ansys_object_names(q3d)
    leftover = [name for name in after if name.lower().startswith("ground_")]
    if leftover:
        raise RuntimeError(
            "ground sheet still in Ansys after delete: "
            f"{leftover}. Unassigned conductors are treated as grounded."
        )
    print("ansys objects after ground delete:", after)
    try:
        q3d.assign_nets()
    except Exception as exc:
        print("assign_nets after ground delete:", exc)


def run_q3d_case(case_name: str, max_passes: int = 10, percent_error: float = 0.5):
    """Render the Metal design into Q3D and return a P1/P2/P3 Maxwell matrix in fF."""
    from qiskit_metal.analyses.quantization import LOManalysis

    from quantromon.geometry.pads import make_design

    spec = PALACE_CASES[case_name]
    design = make_design(
        include_al_leads=spec["include_al_leads"],
        include_jj_fingers=spec["include_jj_fingers"],
        material="sapphire",
    )
    print("components", list(design.components))
    print("chip material", design.chips.main.material)
    print("size_z", design.chips.main.size.size_z)

    lom = LOManalysis(design, "q3d")
    q3d = lom.sim.renderer
    q3d.q3d_options["material_thickness"] = "160nm"
    q3d.start()
    q3d.new_ansys_design(f"quantrota_{case_name}", "capacitive")
    q3d.render_design(["P1", "P2", "P3"], [], box_plus_buffer=False)
    _delete_ground_if_present(q3d)

    lom.sim.setup.max_passes = max_passes
    lom.sim.setup.min_passes = 2
    lom.sim.setup.percent_error = percent_error
    lom.sim.setup.freq_ghz = 5.0
    setup_name = q3d.initialize_cap_extract(**lom.sim.setup)
    q3d.analyze_setup(setup_name)
    _allow_pandas_delim_whitespace()
    df, units = q3d.get_capacitance_matrix()
    print("Q3D raw matrix\n", df)
    print("units", units)
    C = np.asarray(df.values, dtype=float)
    if units and str(units).lower() in ("f", "farad", "farads"):
        C = C * 1e15
        df = pd.DataFrame(C, index=df.index, columns=df.columns)
    C_fF, order = dataframe_to_maxwell_p123(df)
    print("ordered", order)
    print(C_fF)
    print(interpret_named(C_fF))
    return C_fF, df


def _palace_csv(dest: Path, filename: str) -> Path:
    """Prefer ``dest``, then the clone's ``out/`` (reference CSVs live there)."""
    here = dest / filename
    if here.is_file():
        return here
    return reference_outdir() / filename


def palace_row(case_name: str, dest: Path) -> dict:
    spec = PALACE_CASES[case_name]
    row = {
        "case": case_name,
        "palace_CJ_P1P2_fF": spec["palace_CJ_P1P2_fF"],
        "palace_CJ_P3P2_fF": spec["palace_CJ_P3P2_fF"],
        "palace_CR_P1P3_fF": spec["palace_CR_P1P3_fF"],
        "q3d_CJ_P1P2_fF": np.nan,
        "q3d_CJ_P3P2_fF": np.nan,
        "q3d_CR_P1P3_fF": np.nan,
        "note": spec["note"],
    }
    path = _palace_csv(dest, spec["palace_file"])
    if path.is_file():
        from quantromon.sim.palace import interpret_maxwell_fF

        C = load_palace_matrix(path)
        parsed = interpret_maxwell_fF(C, spec["palace_term_map"])
        row["palace_CJ_P1P2_fF"] = parsed.get("CJ_P1P2_fF", row["palace_CJ_P1P2_fF"])
        row["palace_CJ_P3P2_fF"] = parsed.get("CJ_P3P2_fF", row["palace_CJ_P3P2_fF"])
        row["palace_CR_P1P3_fF"] = parsed.get("CR_P1P3_fF", row["palace_CR_P1P3_fF"])
    return row


def write_comparison(rows: list[dict], out_csv: Path) -> Path:
    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(df.to_string(index=False))
    print("wrote", out_csv)
    return out_csv


def main(
    run_q3d: bool = False,
    case: str = "al_meander",
    out: Path | str | None = None,
):
    dest = outdir(out)
    ok, reason = ansys_status()
    print("ansys:", "yes" if ok else "no")
    print("reason:", reason)
    ref = _palace_csv(dest, "phase3_palace_reference.csv")
    print("palace reference:", ref)

    rows = [palace_row(name, dest) for name in PALACE_CASES]
    if not run_q3d:
        print("dry-run: not launching Q3D")
        write_comparison(rows, dest / "phase3_q3d_vs_palace.csv")
        return rows

    if not ok:
        raise SystemExit("cannot --run: " + reason)

    if case not in PALACE_CASES:
        raise SystemExit(f"unknown case {case!r}, choose {list(PALACE_CASES)}")

    C_fF, _ = run_q3d_case(case)
    parsed = interpret_named(C_fF)
    for row in rows:
        if row["case"] != case:
            continue
        row["q3d_CJ_P1P2_fF"] = parsed["CJ_P1P2_fF"]
        row["q3d_CJ_P3P2_fF"] = parsed["CJ_P3P2_fF"]
        row["q3d_CR_P1P3_fF"] = parsed["CR_P1P3_fF"]
    np.savetxt(dest / f"phase3_q3d_{case}_C_fF.csv", C_fF, delimiter=",")
    write_comparison(rows, dest / "phase3_q3d_vs_palace.csv")
    return rows


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "--run",
        action="store_true",
        help="launch Ansys Q3D (Windows + AEDT). Default is dry-run.",
    )
    p.add_argument(
        "--case",
        default="al_meander",
        choices=list(PALACE_CASES),
        help="geometry case to solve in Q3D",
    )
    p.add_argument("--outdir", default=None)
    args = p.parse_args()
    main(run_q3d=args.run, case=args.case, out=args.outdir)
