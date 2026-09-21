# Lab Windows handoff (continue here)

21 Sep 2026. This file is the chat migration for the HP Z2 Ansys PC. Open **this clone** in Cursor: `D:\Hari\quantromon`. New chat: read this file plus `phase3.md` and `status_and_next.md`. Do not open the Ubuntu laptop tree.

Repo: https://github.com/AcadHM/quantromon (public, AcadHM only). Branch `main`.

## What you are doing

QuantroTa_01 lumped Maxwell C of islands P1, P2, P3. No on-chip ground. Palace already ran on the Ubuntu laptop. This PC is Ansys **Q3D Extractor** (Metal `LOManalysis(..., "q3d")`), not HFSS eigenmode.

Pass bar (phase 3): two \(C_J\) still match each other, \(C_R\) within about 10-20% of Palace 600 fF. Bit equality is not expected.

## This machine

HP Z2 Tower G9, Windows 11 Pro, i9-14900 (24c/32t), 128 GB RAM. Disks: `C:` ~953 GB, `D:` ~1.8 TB (use `D:\Hari`), `G:` ~953 GB. Ansys Electronics Desktop **2025.2**. Project folder `D:\HFSS_projects\`, design `quantrota_al_meander`.

Existing conda envs `qmetal` and `pyeprsetup` are not ours. Use **`chip`** (Python 3.11) at `C:\Users\Admin\anaconda3`.

## Git on this PC

Cursor's terminal often cannot see `git`. Use:

```powershell
& "C:\Program Files\Git\cmd\git.exe"
```

Lab HTTPS inspection breaks OpenSSL. This clone should use the Windows cert store:

```powershell
cd D:\Hari\quantromon
& "C:\Program Files\Git\cmd\git.exe" config --local http.sslBackend schannel
& "C:\Program Files\Git\cmd\git.exe" pull
```

Do not set `http.sslVerify false`.

Identity for this clone only (GitHub blocked the gmail with GH007):

```text
user.name  AcadHM
user.email 169357734+AcadHM@users.noreply.github.com
```

Set with `--local` if missing. Do not use `hari.m@qpiai.tech` here. QpiAI git is scoped on the laptop to `/home/hm/QpiAi/` only.

Shared Windows user is **Admin**. Prefer pull-and-run. If you push, you are AcadHM. Sign out of Cursor/GitHub when you leave if others will use Admin.

## Env

```powershell
conda activate chip
cd D:\Hari\quantromon
python -c "import quantromon; from quantromon.sim.q3d import ansys_status; print(quantromon.__version__); print(ansys_status())"
```

Need `(True, 'Windows + pyEPR import ok ...')`. PowerShell: always quote extras, `pip install -e ".[ansys]"`. `pythoncom` is `pywin32`.

Editable install lives in this clone (`src\quantromon`). `git pull` is enough after that.

## Q3D status (do this next)

First `--run --case al_meander` **did** solve. pandas 2.2+ / pyEPR `delim_whitespace` was patched (`0cac10a`). Numbers:

| | Palace | Q3D (ground sheet still in model) |
|---|---|---|
| \(C_J\) P1-P2 | 32.74 fF | 35.04 fF |
| \(C_J\) P3-P2 | 32.54 fF | 34.94 fF |
| \(C_R\) P1-P3 | 600.27 fF | **324.43 fF** |

Ansys tree: SignalNet `P1_P1`, `P2_P2`, `P3_P3`. **Unassigned `ground_main_plane`**. Q3D treats unassigned conductors as grounded, so that sheet screens the IDC. The script called `q3d.modeler.delete`, which does not exist, and swallowed the error.

Fix on `main` (`17b97bd`): COM `oEditor.Delete` on every `ground_*` object, then abort if any remain. Log must contain `deleted ['ground_main_plane']`.

```powershell
conda activate chip
cd D:\Hari\quantromon
& "C:\Program Files\Git\cmd\git.exe" pull
python -m quantromon.sim.q3d --run --case al_meander
```

Writes `out\phase3_q3d_al_meander_C_fF.csv` and fills `out\phase3_q3d_vs_palace.csv`. Those CSVs are not gitignored; commit them only when the ground-free run is the one you trust.

If you already deleted `ground_main_plane` in the GUI and re-analyzed, read that matrix first. Then still pull `17b97bd` so the next scripted run does it.

GUI: hide Solids `main`/`sapphire` if they hide sheets. Delete Unassigned `ground_main_plane`. Q3D Extractor → Analyze All. Results → Solution Data / Matrix. Do not assign that sheet to a net.

## Not done yet (do not start until Q3D \(C_R\) is honest)

- gmsh: `conda install -c conda-forge geopandas` then `pip install "quantum-metal[mesh]"`
- SQDMetal: clone `https://github.com/sqdlab/SQDMetal.git` to `D:\Hari\SQDMetal`, `pip install -e D:\Hari\SQDMetal` in `chip` (needs Python 3.11, pins pandas 2.3.3). Wait until Q3D is not running to pip.
- Palace binary: no official Windows build. WSL2 Ubuntu + Spack is the documented path. Cap WSL RAM (for example 64 GB) so Ansys still has room. SQDMetal `palace_mode: wsl`. Native `palace.exe` is a Visual Studio Fortran project, not required for phase 3.

Q3D does not need gmsh. The gmsh skip line in the log is Metal's other renderer.

## Laptop (do not mix)

Ubuntu, i5-1240P, 16 GB. Palace 0.16 via spack. Workdir `/home/hm/IITB/TIFR/Software/Hari_Quantromon/quantromon`. Do not remesh 0.15 um JJ or `--fine` there.

## Code map

| Path | Role |
|---|---|
| `src/quantromon/sim/q3d.py` | Q3D run, pandas shim, ground COM delete |
| `src/quantromon/sim/palace.py` | Palace (needs SQDMetal + palace binary) |
| `src/quantromon/geometry/pads.py` | Metal P1/P2/P3, no on-chip ground in physics |
| `out/phase2_C_fF_al_meander.csv` | Palace reference C |
| `devnotes/phase3.md` | Q3D physics notes |

## Do not

- Commit as QpiAI or as Windows `Admin`
- Force-push `main`
- Use `qmetal` / `pyeprsetup` / `base` for this package
- Treat 324 fF as the Q3D answer
- Turn off git SSL verify
- Union `L3` or close the meander at \(y = 0\)
