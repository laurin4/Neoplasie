"""Column schemas and status taxonomy for the tumor histopathology task.

Defines the classification-status vocabulary plus the exact, ordered column
layout of every output file. The tumor-category columns themselves come from
``constants.TARGET_COLUMNS`` so there is a single source of truth.
"""

from __future__ import annotations

from typing import List

from src.tasks.tumor_histopathology.constants import (
    COL_KEINE_TUMORINFORMATION,
    COL_P_DAT,
    COL_P_KOM,
    COL_PATNR,
    TARGET_COLUMNS,
)

# ---------------------------------------------------------------------------
# Classification status taxonomy (Phase 8).
# ---------------------------------------------------------------------------
STATUS_SUCCESS = "success"
STATUS_NO_TUMOR_INFORMATION = "no_tumor_information"
STATUS_PARSE_FAILED = "parse_failed"
STATUS_LLM_FAILED = "llm_failed"
STATUS_UNSUPPORTED_CATEGORY = "unsupported_category"
STATUS_UNCERTAIN = "uncertain"

# Run-mode status (not a classification outcome): produced by --no-llm/dry runs.
STATUS_LLM_DISABLED = "llm_disabled"

ALL_STATUSES = (
    STATUS_SUCCESS,
    STATUS_NO_TUMOR_INFORMATION,
    STATUS_PARSE_FAILED,
    STATUS_LLM_FAILED,
    STATUS_UNSUPPORTED_CATEGORY,
    STATUS_UNCERTAIN,
)

# Statuses for which exactly one tumor-category column is set to 1.
POSITIVE_STATUSES = frozenset({STATUS_SUCCESS})

CERTAINTY_VALUES = frozenset({"low", "medium", "high"})

# Patient-level output row order: classified first, missing info next,
# unresolved / failed last (so missing and failed sit at the bottom).
STATUS_SORT_ORDER: dict[str, int] = {
    STATUS_SUCCESS: 0,
    STATUS_UNCERTAIN: 1,
    STATUS_NO_TUMOR_INFORMATION: 2,
    STATUS_UNSUPPORTED_CATEGORY: 3,
    STATUS_PARSE_FAILED: 4,
    STATUS_LLM_FAILED: 5,
    STATUS_LLM_DISABLED: 6,
}


def status_sort_key(status: str) -> int:
    """Lower = earlier in the patient / registry lists."""
    return STATUS_SORT_ORDER.get(status, 99)


# ---------------------------------------------------------------------------
# Row-level input quality status (Phase 4).
# ---------------------------------------------------------------------------
ROW_STATUS_USABLE = "usable"
ROW_STATUS_MISSING_TEXT = "missing_text"


# ---------------------------------------------------------------------------
# Patient-level output: metadata columns that precede the tumor columns.
# ---------------------------------------------------------------------------
PATIENT_META_COLUMNS: List[str] = [
    COL_PATNR,
    "latest_p_dat",
    "report_count",
    "usable_report_count",
    "source_row_indices",
    "classification_status",
    "predicted_tumor_category",
    "predicted_output_column",
    "certainty",
    "reasoning",
    "evidence_summary",
    "historical_diagnoses_summary",
    "no_tumor_information",
    "parse_failed",
    "llm_failed",
    "context_truncated",
    "manual_review_required",
]


def patient_output_columns() -> List[str]:
    """Full ordered column list for the patient-level output file.

    Layout: metadata columns, then the missing-information marker, then every
    tumor-category target column in template order.
    """
    return [*PATIENT_META_COLUMNS, COL_KEINE_TUMORINFORMATION, *TARGET_COLUMNS]


# Template-compatible column order (patnr, p_dat, p_kom, then the 12_* columns).
def template_output_columns() -> List[str]:
    """Column order matching the registry template exactly."""
    return [COL_PATNR, COL_P_DAT, COL_P_KOM, *TARGET_COLUMNS]


# ---------------------------------------------------------------------------
# Review output (Phase 10).
# ---------------------------------------------------------------------------
REVIEW_COLUMNS: List[str] = [
    COL_PATNR,
    "predicted_tumor_category",
    "predicted_output_column",
    "certainty",
    "latest_report_date",
    "classification_status",
    "reasoning",
    "supporting_excerpts",
    "historical_diagnoses_mentioned",
    "all_report_dates",
    "manual_review_required",
    "manual_review_reasons",
]


# ---------------------------------------------------------------------------
# Missing-information output (Phase 9).
# ---------------------------------------------------------------------------
MISSING_INFO_COLUMNS: List[str] = [
    COL_PATNR,
    "report_count",
    "usable_report_count",
    "latest_p_dat",
    "classification_status",
    "note",
]


# ---------------------------------------------------------------------------
# Failed / unresolved output: patients that had text but were not classified
# (llm_failed, parse_failed, unsupported_category). Not the same as missing
# information -- these still need attention or a re-run.
# ---------------------------------------------------------------------------
FAILED_STATUSES = frozenset(
    {STATUS_LLM_FAILED, STATUS_PARSE_FAILED, STATUS_UNSUPPORTED_CATEGORY}
)

FAILED_COLUMNS: List[str] = [
    COL_PATNR,
    "classification_status",
    "usable_report_count",
    "latest_p_dat",
    "predicted_tumor_category",
    "certainty",
    "reasoning",
    "error_message",
    "manual_review_reasons",
]
