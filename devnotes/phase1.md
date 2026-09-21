# Phase 1: three Ta pads + IDC + L2D2100 Al in Qiskit Metal

Exact commands. Environment: conda env **`chip`**.

Phase 1 is pads, the 22-finger IDC (`L6D1800` + `L7D1800`), **L2D2100 Al** (meander cut at `y = 0`), and **L2D2400 JJ fingers** (0.2 um gaps). `L3` stays out. No Palace.

If a command prints something other than the block under it, stop and fix that step.

## 0. One-time check

Open a terminal and type:

```bash
conda activate chip
cd /home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon
pip install -e ".[dev]"
python -c "import quantromon, qiskit_metal, ezdxf, shapely; print('ok', quantromon.__version__, qiskit_metal.__version__)"
```

Expected:

```text
ok 0.1.0 0.8.1
```

The DXF is packaged; no `sys.path` and no `cd` after install. Confirm:

```bash
python -c "from quantromon.geometry.dxf import DEFAULT_DXF; print(DEFAULT_DXF.is_file(), DEFAULT_DXF)"
```

## 1. Extract and label the three islands

From the clone (so `./out` is the repo `out/`):

```bash
python -m quantromon.geometry.dxf
```

Expected stdout (this is the first-chunk result already on disk):

```text
dxf     : .../model_/QuantroTa_01_726_22_finger_130nm_SJ_01_04_25.dxf
islands : 3
name     area_um2      cx_um      cy_um       xmin       ymin       xmax       ymax  holes
P1      244824.03      19.40     522.58    -125.00    -145.00     343.64    1021.00      0
P2      106840.22    -330.33      -0.00    -550.00    -125.00       0.50     125.00      0
P3      244974.02      20.26    -522.36    -125.00   -1021.00     353.64     145.00      0
wrote   : .../out/phase1_islands.txt
wrote   : .../out/phase1_islands.png
```

Gate:

- `islands : 3` or the script raises `expected 3 pad islands`
- P2 has the smallest `cx_um` (left antenna)
- P1 has larger `cy_um` than P3 (top vs bottom)
- Open `out/phase1_islands.png`: red P1, green P2, blue P3, 22 IDC fingers on the right, and an inset of the Al meander. `out/phase1_al_zoom.png` is the centre; `out/phase1_jj_zoom.png` is the 0.2 um JJ gaps.
- P2 `xmax` is about `0.50` um (P2 Al bar reaches the origin), not `-63.5` um
- P1-P2 and P3-P2 Al gaps are about `0.20` um. P1 and P3 meanders do not touch (1.2 um cut at y = 0). No `L3`, no alignment crosses.

If Metal later looks 1000x too small, the um-to-mm conversion failed. Do not continue.

## 2. Build the Metal design

```bash
python -m quantromon.geometry.pads
```

Expected:

```text
DXF islands (um)
...
components : ['P1', 'P2', 'P3']
  P1: bounds mm (-0.1250,-0.1450)-(0.3436,1.0210)
  P2: bounds mm (-0.5500,-0.1250)-(0.0005,0.1250)
  P3: bounds mm (-0.1250,-1.0210)-(0.3536,0.1450)
wrote out/phase1_metal.png
wrote out/phase1_pads.gds
```

A warning about `Fake_Junctions.GDS` is normal. Phase 1 has no junctions.

Bounds are millimetres. A pad about 1 mm tall is correct (the DXF cell is about 2 mm high).

## 3. Optional: same thing in a notebook

`pip install -e .` once. Then `import quantromon` works even if Jupyter starts in `notebooks/`. The first code cell sets `OUT` to the clone's `out/` via `quantromon.paths.repo_root()`.

```bash
conda activate chip
```

Then in `notebooks/phase1_pads.ipynb`:

```python
from quantromon.geometry.dxf import load_pad_islands, island_table, plot_islands, DEFAULT_DXF

islands = load_pad_islands(units="um")
print(island_table(islands))
plot_islands(islands, OUT / "phase1_islands.png", dxf_path=DEFAULT_DXF)
```

```python
from quantromon.geometry.pads import make_design, plot_metal, export_gds

design = make_design()
print(list(design.components))
plot_metal(design, OUT / "phase1_metal.png")
export_gds(design, str(OUT / "phase1_pads.gds"))
```

Do not open `MetalGUI`. In the notebook, the Metal layout is the matplotlib figure from `qm.view(design)` at the bottom of the last cell. The same picture is also saved as `out/phase1_metal.png`. The DXF overlay is `out/phase1_islands.png` and is displayed in the cell above.

## 4. What this phase does not do

Do not load `L3` Dolan (that shorts the JJ fingers). Do not join the meander across y = 0 (that DC-shorts P1 to P3). Do not run Palace. Do not copy `HairpinMeander` from `quantromon.paper.metal`.

## 5. Files

| Path | Role |
|---|---|
| `src/quantromon/geometry/dxf.py` | DXF -> shapely, label P1/P2/P3 |
| `src/quantromon/geometry/pads.py` | QComponent + `make_design()` |
| `out/phase1_islands.png` | DXF overlay, colored islands, Al inset |
| `out/phase1_al_zoom.png` | Close-up of L2D2100 meander + JJ-approach lines |
| `out/phase1_islands.txt` | area / centroid table |
| `out/phase1_metal.png` | Metal view |
| `out/phase1_pads.gds` | GDS of the three pads |

Background: `devnotes/QuantroTa_01_layout_notes.md`.

## 6. Done when

- Three components named `P1`, `P2`, `P3`
- Overlay matches `L6`+`L7` plus split `L2D2100` Al
- GDS exists
- Meander is on P1/P3 as metal, with a gap at y = 0

Next is Phase 2: Palace electrostatics on these three islands (sapphire 0.43 mm, Ta 160 nm, no on-chip ground).
