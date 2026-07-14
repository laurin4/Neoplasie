"""Generic project paths shared across tasks.

Only project-wide roots live here. Task-specific paths (inputs, outputs,
prompts) belong in the individual task's ``config.py`` module.
"""

from __future__ import annotations

from pathlib import Path

# Repository root: .../NCH_Neoplasie
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUTS_DIR = DATA_DIR / "outputs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
LOGS_DIR = PROJECT_ROOT / "logs"


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
