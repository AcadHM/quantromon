# quantromon

Installable Python package for the QuantroTa_01 cell: DXF islands, Qiskit Metal, Palace C, Ansys Q3D.

This is a library. You write scripts (or notebooks) on the laptop, `git pull` on the lab PC, and run the same scripts in the `chip` conda env. There is no project CLI.

## Install

Both machines: clone this repo, activate `chip`, then editable-install so `import quantromon` works without `sys.path` hacks.

Laptop (Ubuntu, Palace):

```bash
conda activate chip
cd /path/to/quantromon
pip install -e ".[dev]"
pip install -e /path/to/SQDMetal
```

Lab Windows PC (Ansys Q3D). Palace and SQDMetal are not required:

```bash
conda activate chip
cd \path\to\quantromon
git pull
pip install -e ".[ansys]"
```

Python 3.11, same as `chip` and SQDMetal.

## Import from a script

```python
from quantromon.geometry.dxf import load_pad_islands, DEFAULT_DXF
from quantromon.geometry.pads import make_design, QuantroTaPad
from quantromon.sim.palace import build_cap_sim, prepare
from quantromon.sim.q3d import run_q3d_case, ansys_status, main as q3d_main

q3d_main(run_q3d=True, case="al_meander")
```

Optional module drivers (same as the old root scripts):

```bash
python -m quantromon.geometry.dxf
python -m quantromon.geometry.pads
python -m quantromon.sim.palace --run
python -m quantromon.sim.q3d --run --case al_meander
```

Run them from the clone so `./out` and `./sims` land next to the repo, not inside site-packages.

## Environment

| Variable | Meaning |
|---|---|
| `QUANTROMON_PALACE` | Palace binary. Else this laptop's spack path if that file exists, else `palace` on PATH. |
| `QUANTROMON_SQDMETAL` | SQDMetal clone if it is not already `pip install -e`. Last resort: sibling `Hari_Quantromon/SQDMetal`. |

`--outdir` / `--simdir` on the Palace and Q3D modules default to `./out` and `./sims` under the current working directory.

## Layout

```text
src/quantromon/geometry/   DXF parse + Metal pads
src/quantromon/sim/        Palace (lazy SQDMetal) and Q3D (lazy Ansys)
src/quantromon/paper/      SEM cousin, not this mask
src/quantromon/feedline/   placeholder for later 2D CPW / TL
src/quantromon/data/       packaged QuantroTa_01 DXF
notebooks/                 look / iterate (import the package)
devnotes/                  typed commands and physics notes
out/                       small reference CSVs (png/gds are gitignored)
```

The 3D waveguide eigenmode is not in this package. A planar feedline would go in `feedline/` later.

## Git

This folder is its own repo. SQDMetal and QDW2025 stay out. Do not commit `sims/` meshes.
