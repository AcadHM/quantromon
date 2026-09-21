# QuantroTa_01: where we are and what is next

19 Sep 2026; package layout 21 Sep 2026. Env: conda **`chip`**. Canonical workdir: `/home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon/`. `/home/hm/QpiAi/Github/device_design` is a symlink to the same tree so old shells still work.

Install once in `chip`: `pip install -e ".[dev]"` (laptop) or `pip install -e ".[ansys]"` (Windows Q3D). Then `import quantromon` with no `sys.path`.

Palace binary and the `chip` conda env stay where they were.

This is the short status. Geometry details: `QuantroTa_01_layout_notes.md`. Typed commands: `phase1.md`, `phase2.md`, `phase3.md`.

## Goal

Rebuild the fabricated QuantroTa_01 cell from the labmate DXF in Qiskit Metal, extract a lumped Maxwell C of P1 / P2 / P3, then put the Josephson overlap in as a lumped \(C_J\). No on-chip ground. Palace (and later Q3D) Ground is the air box, not a metal sheet.

This DXF is this mask. The paper/SEM reconstruction in `quantromon.paper.metal` is a cousin, not a copy.

## Done

**Phase 1.** Three Metal islands from the DXF:

- Ta pads + 22-finger IDC (`L6` + `L7`)
- All `L2D2100` Al (leads, meander, JJ-approach lines), meander cut 1.2 um at \(y = 0\) so P1 and P3 are not DC-shorted
- `L2D2400` JJ fingers on the CAD (0.20 um P1-P2 and P3-P2 gaps). `L3` is out (Dolan mask would short them)
- Plots: `out/phase1_islands.png`, `out/phase1_al_zoom.png`, `out/phase1_jj_zoom.png`, `out/phase1_metal.png`

**Phase 2.** Palace electrostatics, 3 terminals, sapphire 430 um, sheet metals. Terminal map `{1: P3, 2: P1, 3: P2}`.

| Run | \(C_J\) P1-P2 | \(C_J\) P3-P2 | \(C_R\) P1-P3 | File |
|---|---|---|---|---|
| pads + 1 um Al stubs | 27.85 fF | 27.64 fF | 572.63 fF | `out/phase2_C_fF_coarse.csv` |
| pads + L2D2100 meander (no JJ fingers) | 32.74 fF | 32.54 fF | 600.27 fF | `out/phase2_C_fF_al_meander.csv` |

Paper (cousin device): \(C_J\) fit 56.88 fF / HFSS 50.23 fF; \(C_R\) fit 781.8 fF / HFSS 713.9 fF.

**Not done in Palace (on purpose or OOM):**

- IDC min 2 um: 1.7 GB mesh, Palace killed (~15 GB RAM)
- 2 um size field on the whole Al meander box: 3 GB mesh
- 0.15 um size field on the 0.20 um JJ gap: mesher ~13 GB, killed, no C

**Phase 3.** Ansys Q3D on the lab HP Z2 (AEDT 2025.2, conda `chip`). First `--run --case al_meander` solved but left Metal `ground_main_plane` Unassigned, so \(C_R\) was 324 fF vs Palace 600 fF. Ground COM delete is on `main` (`17b97bd`). Lab handoff: `lab_windows.md`.

## What the numbers mean

Palace \(C_J \approx 33\) fF is **coplanar** pad + wiring C (Al gap still ~4 um in the solved mesh).

Kishor ~56 fF is mostly the **AlOx overlap** of the Dolan junction (two Al films, ~1 nm oxide). 2.5D sheets do not contain that sandwich. More RAM, HFSS, or Q3D will not invent it. Circuit split:

\[
C_{J,\mathrm{qubit}} = C_{J,\mathrm{Palace/Q3D}} + C_{J,\mathrm{overlap}}
\]

\(C_R\) from Palace is the IDC. It is ~16% below paper HFSS 714 fF (coarse 5 um fingers, isotropic sapphire, different box). Chase that only after Q3D, with a milder IDC mesh, not `--fine` 2 um on this machine.

## Further steps (in order)

### 1. Q3D on the Windows Ansys box (in progress)

Clone is `D:\Hari\quantromon`. Commands and git/SSL notes: `lab_windows.md`.

```text
git pull
python -m quantromon.sim.q3d --run --case al_meander
```

Gate: log shows `deleted ['ground_main_plane']`, 3x3 matrix, nets P1 P2 P3, no `ground_*` in Ansys. Compare to Palace 32.74 / 32.54 / 600.27 fF. First run with the leftover ground sheet is not that comparison.

Details: `phase3.md`. Notebook: `notebooks/phase3_q3d.ipynb`.

### 2. Lumped overlap \(C_J\)

After Q3D (or if Q3D is delayed), do **not** remesh the 0.20 um gap on this 15 GB box.

Add \(C_{J,\mathrm{overlap}}\) as a lumped element, one per junction (P1-P2 and P3-P2):

- start from paper HFSS 50.23 fF or fit 56.88 fF, **or**
- \(c_s \times A\) from Dolan overlap (\(W\), \(B\), evaporation angles in the thesis)

Keep Palace/Q3D for pads + IDC + Al wiring. Do not add overlap C on top of a Palace number that already tried to be 56 fF (it never was).

### 3. Optional \(C_R\) check

Only if Q3D \(C_R\) also sits well below ~714 fF: densify the IDC to about 4 um, not 2 um. Do not put a fine box on the meander.

### 4. Later: 3D waveguide

Eigenmode of the 1.75 cm x 3.5 cm x 8.2 cm box for \(\kappa\) and antenna coupling. That is HFSS eigenmode (or Palace eigenmode), not Q3D. Not required to close planar LOM.

## Do not do

- Another 0.15 um JJ mesh on this laptop
- `python -m quantromon.sim.palace --fine` on this laptop
- Union `L3` into the conductors
- Close the meander across \(y = 0\)
- Treat HFSS eigenmode as a drop-in for the C-matrix (use Q3D)

## Commands on this Ubuntu box

```bash
conda activate chip
cd /home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon
pip install -e ".[dev]"
python -m quantromon.geometry.dxf     # geometry + plots
python -m quantromon.geometry.pads    # Metal + GDS
python -m quantromon.sim.palace       # remesh only
python -m quantromon.sim.palace --run # remesh + Palace (coarse)
python -m quantromon.sim.q3d          # dry-run Q3D table
```

## File map

| Path | Role |
|---|---|
| `src/quantromon/geometry/dxf.py` | DXF to P1/P2/P3 |
| `src/quantromon/geometry/pads.py` | Metal design |
| `src/quantromon/sim/palace.py` | Palace C |
| `src/quantromon/sim/q3d.py` | Q3D validator |
| `notebooks/phase1_pads.ipynb` | look at layout |
| `notebooks/phase2_cap.ipynb` | look at mesh |
| `notebooks/phase3_q3d.ipynb` | look at Palace vs Q3D table |
| `out/phase2_C_fF_al_meander.csv` | current Palace C |
| `out/phase3_palace_reference.csv` | run history |
| `out/phase3_q3d_vs_palace.csv` | comparison (first Q3D run still had ground sheet) |
| `devnotes/lab_windows.md` | Ansys PC chat handoff |
