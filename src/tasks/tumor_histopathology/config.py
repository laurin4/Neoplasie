"""Configuration for the tumor histopathology task.

All task-specific paths and environment variables. Environment variables use
the ``TUMOR_HISTOLOGY_`` prefix. Every value has a safe default so the pipeline
runs (with a dry-run / synthetic input) without any configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.pipeline.paths import OUTPUTS_DIR, PROMPTS_DIR, RAW_DIR, ensure_dir

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_INPUT_PATH = RAW_DIR / "tumor_histopathology_input.xlsx"
OUTPUT_DIR = OUTPUTS_DIR
PROMPT_FILE = PROMPTS_DIR / "tumor_histopathology_classification.txt"

# Output file names (Phase 9-10).
PATIENT_PREDICTIONS_XLSX = "tumor_histopathology_patient_predictions.xlsx"
PATIENT_PREDICTIONS_CSV = "tumor_histopathology_patient_predictions.csv"
MISSING_INFORMATION_CSV = "tumor_histopathology_missing_information.csv"
REVIEW_CSV = "tumor_histopathology_review.csv"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def get_input_path() -> Path:
    raw = _env("TUMOR_HISTOLOGY_INPUT_PATH")
    return Path(raw) if raw else DEFAULT_INPUT_PATH


def get_output_dir() -> Path:
    raw = _env("TUMOR_HISTOLOGY_OUTPUT_DIR")
    out = Path(raw) if raw else OUTPUT_DIR
    return ensure_dir(out)


def get_sheet_name() -> Optional[str]:
    raw = _env("TUMOR_HISTOLOGY_SHEET")
    return raw or None


# ---------------------------------------------------------------------------
# LLM configuration (TUMOR_HISTOLOGY_* with generic fallbacks).
# ---------------------------------------------------------------------------
SUPPORTED_PROVIDERS = ("usz_api", "ollama")


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        val = os.environ.get(name)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def get_provider() -> str:
    return _env_first(
        "TUMOR_HISTOLOGY_LLM_PROVIDER", "LLM_PROVIDER", default="usz_api"
    ).lower()


def get_usz_url() -> str:
    return _env_first(
        "TUMOR_HISTOLOGY_USZ_LLM_URL", "USZ_LLM_URL",
        default="http://localhost:8100/generate",
    )


def get_ollama_url() -> str:
    return _env_first(
        "TUMOR_HISTOLOGY_OLLAMA_URL", "OLLAMA_URL", default="http://127.0.0.1:11500"
    )


def get_ollama_model() -> str:
    return _env_first("TUMOR_HISTOLOGY_OLLAMA_MODEL", "OLLAMA_MODEL", default="qwen2.5:7b")


def _float_env(default: float, *names: str) -> float:
    raw = _env_first(*names)
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _int_env(default: int, *names: str) -> int:
    raw = _env_first(*names)
    if not raw:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def get_temperature() -> float:
    return _float_env(0.1, "TUMOR_HISTOLOGY_LLM_TEMPERATURE", "LLM_TEMPERATURE")


def get_top_p() -> float:
    return _float_env(0.9, "TUMOR_HISTOLOGY_LLM_TOP_P", "LLM_TOP_P")


def get_max_tokens() -> int:
    return _int_env(1200, "TUMOR_HISTOLOGY_LLM_MAX_TOKENS", "LLM_MAX_TOKENS")


def get_timeout_seconds() -> int:
    return max(1, _int_env(240, "TUMOR_HISTOLOGY_LLM_TIMEOUT_SECONDS", "LLM_TIMEOUT"))


def get_max_retries() -> int:
    return max(0, _int_env(1, "TUMOR_HISTOLOGY_LLM_MAX_RETRIES"))


def get_ollama_num_ctx() -> int:
    return _int_env(8192, "TUMOR_HISTOLOGY_OLLAMA_NUM_CTX", "OLLAMA_NUM_CTX")


def get_disable_think() -> bool:
    return _env_first("TUMOR_HISTOLOGY_LLM_DISABLE_THINK", "LLM_DISABLE_THINK").lower() in (
        "1", "true", "yes",
    )


# ---------------------------------------------------------------------------
# Aggregation / context configuration (Phase 5).
# ---------------------------------------------------------------------------
def get_max_context_chars() -> int:
    """Maximum characters of combined report context sent to the model."""
    return max(1000, _int_env(24000, "TUMOR_HISTOLOGY_MAX_CONTEXT_CHARS"))
