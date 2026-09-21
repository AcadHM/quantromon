# Phase 3: Ansys Q3D validator (same C as Palace)

Env: conda **`chip`**. Phase 1/2 Metal design is the geometry. This phase does **not** add a lumped JJ.

Qiskit Metal's matching analysis is **Ansys Q3D Extractor**, not HFSS eigenmode. Official docs:

- [3.3 Render your design to Ansys](https://qiskit-community.github.io/qiskit-metal/tut/3-Renderers/3.3-Render-your-design-to-Ansys.html)
- [4.01 Capacitance matrix and LOM analysis](https://qiskit-community.github.io/qiskit-metal/tut/4-Analysis/4.01-Capacitance-and-LOM.html)

Those notebooks use `LOManalysis(design, "q3d")`. That is the same electrostatic Maxwell C we got from Palace. HFSS in Metal is eigenmode / driven-modal (waveguide later). Kishor's paper saying "HFSS" for \(C_J\) is the Ansys suite name; the extractor for a C-matrix is Q3D.

This laptop is Ubuntu. AEDT + pyEPR COM is Windows. `python -m quantromon.sim.q3d` here is a dry-run. `--run` is for a Windows box with Electronics Desktop.

## 1. Palace runs so far

| Run | Geometry | Mesh | \(C_J\) P1-P2 | \(C_J\) P3-P2 | \(C_R\) P1-P3 | File |
|---|---|---|---|---|---|---|
| pads + 1 um Al stubs | L6+L7 plus three 1 um leads. No meander. No JJ fingers. | IDC 5 um, pads 20 um | 27.85 fF | 27.64 fF | 572.63 fF | `out/phase2_C_fF_coarse.csv` |
| Al meander | pads+IDC plus all L2D2100, cut 1.2 um at y=0. No L2D2400. No L3. | IDC 5 um, pads 20 um, no Al-box field | 32.74 fF | 32.54 fF | 600.27 fF | `out/phase2_C_fF_al_meander.csv` (also `out/phase2_C_fF.csv`) |
| IDC 2 um | same idea, finer IDC | IDC min 2 um | OOM | OOM | OOM | ~1.7 GB msh, Palace killed |
| 2 um Al box | meander + size field on whole Al bbox | 2 um on ~120 x 160 um | OOM | | | 3 GB msh, not solved |
| 0.15 um JJ box | CAD had 0.20 um L2D2400 gaps | 0.15 um on 6 x 16 um | killed | | | mesher ~13 GB, no C |

All successful runs: 3 floating conductors, no on-chip ground, Palace Ground = air-box wall, sapphire 430 um, metals as sheets. Terminal map `{1: P3, 2: P1, 3: P2}`.

Paper (cousin device, not this DXF): \(C_J\) fit 56.88 fF, HFSS 50.23 fF; \(C_R\) fit 781.8 fF, HFSS 713.9 fF. That \(C_J\) is the AlOx overlap, not the next Palace/Q3D target.

CSV copy of the table: `out/phase3_palace_reference.csv`.

**Phase 3 compares the Al-meander row** (32.74 / 32.54 / 600.27 fF). Optional second case is pads-only (Ta, no Al) as a stand-in for the stubs run; the stubs-only attach path is gone.

## 2. What is identical, what is not

Same:

- Metal components P1, P2, P3 from `make_design()`
- No `L3`, meander cut at y=0, no lumped JJ
- Three nets, no on-chip ground (script deletes Metal's `ground_main_plane`)
- Sapphire chip, 430 um
- Maxwell C in fF, then the same \(C_J\) / \(C_R\) read-out as Palace

Not the same (cannot be):

- Mesh: Palace is Gmsh size fields; Q3D is adaptive passes (`max_passes`, `percent_error`)
- Sheet thickness: Palace 2.5D; Q3D thin conductor default 200 nm, we set 160 nm
- Air box: Palace used SQDMetal proportions; Q3D uses Metal chip + buffers
- Solver: Palace vs Q3D iterative

If Q3D \(C_R\) is within ~10-20% of 600 fF and the two \(C_J\) still match each other, that is a pass for "same problem, different engine". Do not expect bit equality.

## 3. Dry-run on this laptop

```bash
conda activate chip
cd /home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon
python -m quantromon.sim.q3d
```

Expected: `ansys: no`, Palace numbers printed, `out/phase3_q3d_vs_palace.csv` with empty Q3D columns.

Notebook: `notebooks/phase3_q3d.ipynb` (bootstrap, then the same call).

## 4. Real Q3D (Windows + AEDT)

Install Ansys Electronics Desktop. In the `chip` env (or a Windows clone of it):

```bash
pip install -e ".[ansys]"
python -m quantromon.sim.q3d --run --case al_meander
```

`--case pads` is Ta only (no Al). `--case al_meander` is the main check.

Gate after `--run`:

- Q3D matrix is **3x3**. If it is 4x4, ground leaked in. Stop.
- Nets map to P1, P2, P3.
- Script writes `out/phase3_q3d_al_meander_C_fF.csv` and fills `out/phase3_q3d_vs_palace.csv`.

A `Fake_Junctions.GDS` warning is still normal.

## 5. What this phase does not do

- No HFSS eigenmode / waveguide \(\kappa\)
- No lumped AlOx \(C_J\)
- No 0.15 um JJ mesh
- No `--fine` IDC

## 6. Files

| Path | Role |
|---|---|
| `src/quantromon/sim/q3d.py` | dry-run table + optional Q3D solve |
| `out/phase3_palace_reference.csv` | Palace history |
| `out/phase3_q3d_vs_palace.csv` | comparison (Q3D empty until `--run`) |
| `notebooks/phase3_q3d.ipynb` | look at the table |
| `devnotes/phase3.md` | this file |
