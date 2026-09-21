# Phase 2: Palace capacitance matrix (P1, P2, P3)

Exact commands. Env: conda **`chip`**. Phase 1 must already work.

This extracts the lumped Maxwell C-matrix of the three islands on sapphire: Ta pads+IDC, **L2D2100 Al** (meander cut at y = 0), and **L2D2400 JJ fingers** (0.2 um gaps). No `L3`. No on-chip ground. Palace `Ground` is the **air-box wall**, not a metal sheet under the pads.

## 0. Check Palace and SQDMetal

```bash
conda activate chip
cd /home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon
pip install -e ".[dev]"
python -c "from SQDMetal.PALACE.Capacitance_Simulation import PALACE_Capacitance_Simulation; print('SQDMetal ok')"
ls /home/hm/repo/spack/opt/spack/linux-alderlake/palace-0.16.0-k47wlt5uelpxxmtpoj46frfzw7mkmc34/bin/palace
```

Expected: `SQDMetal ok` and the palace binary listed. If SQDMetal is not installed: `pip install -e ../SQDMetal` or set `QUANTROMON_SQDMETAL`. Palace binary: `QUANTROMON_PALACE` or the laptop spack path if that file exists.

## 1. Mesh and label conductors (do this first)

```bash
python -m quantromon.sim.palace
```

This:

- rebuilds the Phase 1 Metal design
- sets sapphire thickness `size_z = 430um`
- adds **only** metallic layer 1 (`add_metallic`)
- does **not** call `add_ground_plane`
- puts vacuum above and below the chip
- writes a coarse first-pass mesh (IDC `min_size = 5 um`). The 0.2 um JJ fingers are in the metal. Do not put a 0.15 um size field on them (mesher ~12 GB RSS) and do not put a 2 um field on the whole meander (3 GB `.msh`).
- asserts there are **exactly 3** terminals

Expected stdout includes:

```text
chip size_z 430um
components ['P1', 'P2', 'P3']
ground omitted: True
terminals 3
config .../sims/quantrota_pads_cap/quantrota_pads_cap.json
wrote out/phase2_conductors.png
```

Gate: open `out/phase2_conductors.png`. You must see three coloured islands, **no chip-filling ground sheet**.

On the first successful mesh (17 Sep 2026) the map was:

- Cond1 = P3 (bottom pad + lower IDC fingers)
- Cond2 = P1 (top pad + upper IDC fingers)
- Cond3 = P2 (left pad)

`python -m quantromon.sim.palace` now prints `terminal map: {1: 'P3', 2: 'P1', 3: 'P2'}` (or whatever the mesh order is). Use that, not assumed P1/P2/P3 order.

If `terminals` is 4, a ground plane leaked in. Stop.

A `Fake_Junctions.GDS` warning is normal.

## 2. Run Palace (after the gate)

```bash
python -m quantromon.sim.palace --run
```

This remeshes then calls Palace. Minutes to tens of minutes on the coarse mesh.

Expected: a 3x3 matrix printed in fF, and `out/phase2_C_fF.csv`.

With L2D2100 Al included (meander cut at y = 0), `terminal map: {1: 'P3', 2: 'P1', 3: 'P2'}`:

```text
C (fF)
[[ 709.75  -600.27   -32.54]
 [-600.27   708.25   -32.74]
 [ -32.54   -32.74    96.72]]

CJ_P1P2 = 32.74 fF
CJ_P3P2 = 32.54 fF
CR_P1P3 = 600.27 fF
```

Pads-only coarse run (same mesh settings, no meander) was \(C_J \approx 27.8\) fF and \(C_R = 572.63\) fF (`out/phase2_C_fF_coarse.csv`). Adding the split Al raised \(C_J\) by about 5 fF (P1/P2 Al gap is 4.15 um, not the 0.2 um JJ gap) and \(C_R\) by about 28 fF.

P1/P3 self-C ~709 fF; P2 ~97 fF. The two \(C_J\) values matching is a good symmetry check. \(C_R\) is large because that is the 22-finger IDC. This is a **coarse** mesh (5 um on the IDC); `--fine` will move \(C_R\) some.

Maxwell C: diagonals are self-capacitance to the box; off-diagonals are **negative** mutuals.

## 3. Tighter IDC mesh (terminal)

```bash
python -m quantromon.sim.palace --fine --run
```

IDC `min_size = 2 um`. Better \(C_R\), slower mesh.

## 4. Notebook vs script

The `.py` files are the **engine**: same commands, same files, no GUI required. The notebooks are for **looking and iterating**.

| Look at | Notebook |
|---|---|
| DXF overlay, Metal layout | `notebooks/phase1_pads.ipynb` |
| Conductors, Gmsh mesh, local refine, Palace | `notebooks/phase2_cap.ipynb` |

In Phase 2, after `prepare` (same order as Murat: mesh, look, then Palace):

1. `plot_mesh(cap_sim)` draws the surface mesh inline.
2. `open_gmsh_gui(cap_sim)` is the native Gmsh window (blocks until you close it). Needs a desktop display.
3. Open the **coarse** mesh only (around 100 MB). Do not put a 2 um size field on the Al meander box: that wrote a 3 GB `.msh` here. The leftover 2 um IDC mesh is ~1.7 GB; do not open that either.
4. To densify a region, microns, same axes as `phase1_islands.png`:

```python
from quantromon.sim.palace import refine_rectangle, prepare
refine_rectangle(cap_sim, 80, -200, 370, 200, min_um=4.0, max_um=12.0)
fig = prepare(cap_sim, OUT / "phase2_conductors.png")
```

Then plot the mesh again. The mesh lives at `sims/quantrota_pads_cap/quantrota_pads_cap.msh`. Check the file size first: a few hundred MB is the coarse mesh you can open. A 2 um size field on the Al box wrote 3 GB here (do not open). The leftover 2 um IDC mesh is ~1.7 GB (do not open).

## 5. What this phase does not do

- No uncut meander (that would DC-short P1 to P3)
- No `L3` Dolan mask (that would short the 0.2 um JJ gaps)
- No 3D waveguide eigenmode
- Metals are **sheets**, not 160 nm extruded solids (standard electrostatic LOM)

## 6. Files

| Path | Role |
|---|---|
| `src/quantromon/sim/palace.py` | setup, mesh, optional Palace run |
| `out/phase2_conductors.png` | terminal index map |
| `sims/quantrota_pads_cap/` | mesh + Palace JSON |
| `out/phase2_C_fF.csv` | C-matrix after `--run` |
