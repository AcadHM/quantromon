"""Phase 2: Palace electrostatics on the three pad+IDC+Al+JJ islands.

No on-chip ground plane. Palace 'Ground' is the air-box far field.
Metals are 2.5D sheets (standard LOM). Ta 160 nm is not extruded.
L2D2100 Al (meander cut at y = 0) and L2D2400 JJ fingers are included.
L3 stays out so the 0.2 um junction gaps stay open.

SQDMetal is imported only inside functions so Windows Q3D can import
``quantromon`` without Palace.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from quantromon.paths import (
    ensure_sqdmetal_on_path,
    outdir,
    palace_binary,
    simdir,
)

# IDC bbox from the DXF, metres, with a small pad.
IDC_RECT_M = (80e-6, -200e-6, 370e-6, 200e-6)
# Al meander bbox (for local refine_rectangle in the notebook if needed).
AL_RECT_M = (-80e-6, -80e-6, 40e-6, 80e-6)
# L2D2400 fingers live in about x=+/-0.22 um, y=+/-5.6 um. Keep this box
# tiny: a 2 um field on the whole meander wrote a 3 GB mesh.
JJ_RECT_M = (-3e-6, -8e-6, 3e-6, 8e-6)


def _user_options(palace_dir: str, num_cpus: int) -> dict:
    return {
        "mesh_refinement": 0,
        "dielectric_material": "sapphire",
        "topping_material": "vacuum",
        "solver_order": 1,
        "solver_tol": 1.0e-8,
        "solver_maxits": 500,
        "mesh_min": 10e-6,
        "mesh_max": 80e-6,
        "fillet_resolution": 12,
        "num_cpus": num_cpus,
        "palace_dir": palace_dir,
        "gmsh_verbosity": 2,
        "gmsh_dist_func_discretisation": 80,
    }


def build_cap_sim(
    design,
    name: str = "quantrota_pads_cap",
    palace_dir: str | None = None,
    num_cpus: int | None = None,
    coarse: bool = True,
    sim_dir: Path | str | None = None,
):
    """Create a PALACE_Capacitance_Simulation. Does not mesh yet.

    Do **not** call add_ground_plane. Default _ground_plane is omit=True.
    """
    ensure_sqdmetal_on_path()
    from SQDMetal.PALACE.Capacitance_Simulation import (
        PALACE_Capacitance_Simulation,
    )

    if num_cpus is None:
        num_cpus = max(1, min(8, (os.cpu_count() or 4)))
    binary = palace_binary(palace_dir)

    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["PMIX_MCA_gds"] = "hash"

    parent = simdir(sim_dir)
    cap_sim = PALACE_Capacitance_Simulation(
        name=name,
        metal_design=design,
        sim_parent_directory=str(parent) + "/",
        mode="simPC",
        meshing="GMSH",
        user_options=_user_options(binary, num_cpus),
        view_design_gmsh_gui=False,
        create_files=True,
    )
    cap_sim.add_metallic(1, threshold=1e-10, fuse_threshold=1e-10)
    cap_sim.set_xBoundary_as_proportion(0.15)
    cap_sim.set_yBoundary_as_proportion(0.15)
    cap_sim.set_zBoundary_as_proportion(1.0, 1.0)

    if coarse:
        idc_min, idc_max = 5e-6, 25e-6
        pad_min, pad_max = 20e-6, 80e-6
    else:
        idc_min, idc_max = 2e-6, 10e-6
        pad_min, pad_max = 8e-6, 40e-6

    cap_sim.fine_mesh_components(
        ["P1", "P2", "P3"],
        min_size=pad_min,
        max_size=pad_max,
        taper_dist_min=30e-6,
        taper_dist_max=200e-6,
    )
    x1, y1, x2, y2 = IDC_RECT_M
    cap_sim.fine_mesh_in_rectangle(
        x1,
        y1,
        x2,
        y2,
        min_size=idc_min,
        max_size=idc_max,
        taper_dist_min=10e-6,
        taper_dist_max=80e-6,
    )
    # The 0.5 um meander is in the metal. A 2 um size field on the whole
    # Al bbox wrote a 3 GB mesh (OOM). A 0.15 um field on a 6 x 16 um JJ
    # box also ran the mesher to ~12 GB RSS and died. Keep the 0.2 um
    # fingers in the CAD; do not put a volume size field on them here.
    return cap_sim


def label_terminals(cap_sim) -> dict[int, str]:
    """Map Palace Cond index (1-based) to P1/P2/P3 by nearest pad centroid."""
    from quantromon.geometry.dxf import load_pad_islands

    islands_mm = load_pad_islands(units="mm")
    pad_xy = {name: (g.centroid.x, g.centroid.y) for name, g in islands_mm.items()}
    mapping = {}
    for i, geom in enumerate(cap_sim._cur_cap_terminals):
        cx, cy = geom.centroid.x, geom.centroid.y
        name = min(
            pad_xy,
            key=lambda n: (pad_xy[n][0] - cx) ** 2 + (pad_xy[n][1] - cy) ** 2,
        )
        mapping[i + 1] = name
    return mapping


def prepare(cap_sim, out_png: Path | None = None):
    """Mesh + write Palace JSON. Returns the conductor-index figure."""
    cap_sim.prepare_simulation()
    n = len(cap_sim._cur_cap_terminals)
    if n != 3:
        raise RuntimeError(
            f"expected 3 floating conductors (P1,P2,P3), got {n}. "
            "A ground sheet was probably added, or pads fused."
        )
    mapping = label_terminals(cap_sim)
    cap_sim.terminal_names = mapping
    print("terminal map:", mapping)
    fig = cap_sim.display_conductor_indices()
    if out_png is not None:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_png, dpi=140, bbox_inches="tight")
    return fig


def mesh_file(cap_sim) -> Path:
    return Path(cap_sim.sim_parent_directory) / cap_sim.name / f"{cap_sim.name}.msh"


def open_gmsh_gui(cap_sim, hide_box: bool = True, hide_substrate: bool = False):
    """Open the native Gmsh window on the current .msh. Blocks until you close it."""
    ensure_sqdmetal_on_path()
    from SQDMetal.PALACE.Utilities.GMSH_Navigator import GMSH_Navigator

    path = mesh_file(cap_sim)
    if not path.is_file():
        raise FileNotFoundError(path)
    nav = GMSH_Navigator(str(path))
    nav.open_GUI(
        show_metals=True,
        hide_box=hide_box,
        hide_substrate=hide_substrate,
        hide_substrate_gaps=True,
    )
    return nav


def plot_mesh(cap_sim, **kwargs):
    """Matplotlib view of the surface mesh (works in a notebook, no Gmsh window)."""
    ensure_sqdmetal_on_path()
    from SQDMetal.PALACE.Utilities.GMSH_Navigator import GMSH_Navigator

    path = mesh_file(cap_sim)
    if not path.is_file():
        raise FileNotFoundError(path)
    nav = GMSH_Navigator(str(path))
    return nav.plot_mesh(**kwargs)


def refine_rectangle(cap_sim, x1_um, y1_um, x2_um, y2_um, min_um=2.0, max_um=8.0):
    """Add a local fine-mesh box. Units are microns. Call prepare() again after this."""
    cap_sim.fine_mesh_in_rectangle(
        x1_um * 1e-6,
        y1_um * 1e-6,
        x2_um * 1e-6,
        y2_um * 1e-6,
        min_size=min_um * 1e-6,
        max_size=max_um * 1e-6,
        taper_dist_min=10e-6,
        taper_dist_max=80e-6,
    )


def interpret_maxwell_fF(C_fF: np.ndarray, terminal_map: dict | None = None) -> dict:
    """Maxwell matrix in fF. Off-diagonals are -C_mutual.

    ``terminal_map`` is 1-based Cond index -> 'P1'/'P2'/'P3'.
    """
    C = np.asarray(C_fF, dtype=float)
    out = {"C_maxwell_fF": C, "terminal_map": terminal_map}
    if C.shape != (3, 3):
        return out
    names = ["Cond1", "Cond2", "Cond3"]
    if terminal_map:
        names = [terminal_map[i] for i in (1, 2, 3)]
    if set(names) == {"P1", "P2", "P3"}:
        idx = {n: i for i, n in enumerate(names)}
        out["CJ_P1P2_fF"] = -C[idx["P1"], idx["P2"]]
        out["CJ_P3P2_fF"] = -C[idx["P3"], idx["P2"]]
        out["CR_P1P3_fF"] = -C[idx["P1"], idx["P3"]]
    return out


def main(
    run_palace: bool = False,
    coarse: bool = True,
    out: Path | str | None = None,
    sim_dir: Path | str | None = None,
    palace_dir: str | None = None,
):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from quantromon.geometry.pads import make_design

    dest = outdir(out)
    design = make_design()
    print("chip size_z", design.chips.main.size.size_z)
    print("components", list(design.components))
    cap_sim = build_cap_sim(
        design, coarse=coarse, sim_dir=sim_dir, palace_dir=palace_dir
    )
    print("ground omitted:", cap_sim._ground_plane.get("omit"))
    fig = prepare(cap_sim, dest / "phase2_conductors.png")
    plt.close(fig)
    print("terminals", len(cap_sim._cur_cap_terminals))
    print("config", cap_sim._sim_config)
    print("wrote", dest / "phase2_conductors.png")

    if run_palace:
        C = cap_sim.run()
        C_fF = np.asarray(C, dtype=float) * 1e15
        print("C (fF)")
        print(C_fF)
        np.savetxt(dest / "phase2_C_fF.csv", C_fF, delimiter=",")
        print(interpret_maxwell_fF(C_fF, getattr(cap_sim, "terminal_names", None)))
    return cap_sim


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true", help="run Palace after meshing")
    p.add_argument("--fine", action="store_true", help="tighter IDC mesh")
    p.add_argument("--palace", default=None, help="Palace binary (else QUANTROMON_PALACE)")
    p.add_argument("--outdir", default=None)
    p.add_argument("--simdir", default=None)
    args = p.parse_args()
    main(
        run_palace=args.run,
        coarse=not args.fine,
        out=args.outdir,
        sim_dir=args.simdir,
        palace_dir=args.palace,
    )
