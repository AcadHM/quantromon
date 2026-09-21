"""DXF location and work directories (cwd, not site-packages)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DXF_NAME = "QuantroTa_01_726_22_finger_130nm_SJ_01_04_25.dxf"

_LAPTOP_PALACE = Path(
    "/home/hm/repo/spack/opt/spack/linux-alderlake/"
    "palace-0.16.0-k47wlt5uelpxxmtpoj46frfzw7mkmc34/bin/palace"
)


def default_dxf() -> Path:
    """Packaged QuantroTa_01 DXF (real filesystem path for ezdxf)."""
    path = Path(__file__).resolve().parent / "data" / "model_" / DXF_NAME
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def outdir(explicit: Path | str | None = None) -> Path:
    """Figures and CSV. Default ``./out`` under the current working directory."""
    path = Path(explicit) if explicit is not None else Path.cwd() / "out"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reference_outdir() -> Path:
    """Clone ``out/`` holding Palace reference CSVs, if present."""
    return repo_root() / "out"


def simdir(explicit: Path | str | None = None) -> Path:
    """Palace mesh / JSON. Default ``./sims`` under the current working directory."""
    path = Path(explicit) if explicit is not None else Path.cwd() / "sims"
    path.mkdir(parents=True, exist_ok=True)
    return path


def palace_binary(explicit: str | Path | None = None) -> str:
    """Palace executable: ``--palace``, then ``QUANTROMON_PALACE``, then this laptop."""
    if explicit is not None:
        return str(explicit)
    env = os.environ.get("QUANTROMON_PALACE")
    if env:
        return env
    if _LAPTOP_PALACE.is_file():
        return str(_LAPTOP_PALACE)
    return "palace"


def repo_root() -> Path:
    """Install root (``quantromon/`` clone), two levels above this file."""
    return Path(__file__).resolve().parents[2]


def ensure_sqdmetal_on_path() -> None:
    """Make ``import SQDMetal`` work. No-op if it is already installed.

    Order: already importable, ``QUANTROMON_SQDMETAL``, sibling
    ``Hari_Quantromon/SQDMetal``.
    """
    try:
        import SQDMetal  # noqa: F401
        return
    except ImportError:
        pass

    candidates: list[Path] = []
    env = os.environ.get("QUANTROMON_SQDMETAL")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[3] / "SQDMetal")

    for root in candidates:
        if not root.is_dir():
            continue
        path = str(root)
        if path not in sys.path:
            sys.path.insert(0, path)
        try:
            import SQDMetal  # noqa: F401
            return
        except ImportError:
            if path in sys.path:
                sys.path.remove(path)

    raise ImportError(
        "SQDMetal is not importable. "
        "pip install -e /path/to/SQDMetal, or set QUANTROMON_SQDMETAL."
    )
