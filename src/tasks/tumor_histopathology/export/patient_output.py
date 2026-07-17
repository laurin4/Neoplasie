"""Build the patient-level prediction table (one row per patient).

Exactly one ``12_*`` column is set to 1 for successfully classified patients;
all other tumor columns stay blank. Patients without usable tumor information
get ``Keine_Tumorinformation = 1`` and no tumor column set -- they are kept in
the output, never dropped.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.tasks.tumor_histopathology.constants import (
    COL_KEINE_TUMORINFORMATION,
    COL_PATNR,
    TARGET_COLUMNS,
)
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.tasks.tumor_histopathology.io.schema import (
    FAILED_COLUMNS,
    FAILED_STATUSES,
    MISSING_INFO_COLUMNS,
    STATUS_SUCCESS,
    patient_output_columns,
    status_sort_key,
)


def tumor_onehot(result: PatientResult) -> Dict[str, object]:
    """One-hot tumor columns: all blank, exactly one set to 1 on success."""
    row: Dict[str, object] = {col: "" for col in TARGET_COLUMNS}
    if (
        result.classification_status == STATUS_SUCCESS
        and result.predicted_output_column in TARGET_COLUMNS
    ):
        row[result.predicted_output_column] = 1
    return row


def _evidence_summary(result: PatientResult) -> str:
    parts = []
    for e in result.supporting_evidence:
        excerpt = str(e.get("text_excerpt", "") or "").strip()
        if excerpt:
            parts.append(excerpt)
    return " | ".join(parts)


def _historical_summary(result: PatientResult) -> str:
    parts = []
    for h in result.historical_diagnoses_mentioned:
        diag = str(h.get("diagnosis", "") or "").strip()
        reason = str(h.get("reason_not_selected", "") or "").strip()
        if diag:
            parts.append(f"{diag} ({reason})" if reason else diag)
    return " | ".join(parts)


def build_patient_row(result: PatientResult) -> Dict[str, object]:
    row: Dict[str, object] = {
        COL_PATNR: result.patnr,
        "latest_p_dat": result.latest_p_dat,
        "report_count": result.report_count,
        "usable_report_count": result.usable_report_count,
        "source_row_indices": ";".join(str(i) for i in result.source_row_indices),
        "classification_status": result.classification_status,
        "predicted_tumor_category": result.predicted_tumor_category or "",
        "predicted_output_column": result.predicted_output_column or "",
        "certainty": result.certainty,
        "reasoning": result.reasoning,
        "evidence_summary": _evidence_summary(result),
        "historical_diagnoses_summary": _historical_summary(result),
        "no_tumor_information": 1 if result.no_tumor_information else "",
        "parse_failed": 1 if result.parse_failed else "",
        "llm_failed": 1 if result.llm_failed else "",
        "context_truncated": 1 if result.context_truncated else "",
        "manual_review_required": 1 if result.manual_review_required else "",
    }

    # Missing-information marker.
    row[COL_KEINE_TUMORINFORMATION] = 1 if result.no_tumor_information else ""

    # One-hot tumor columns: blank by default, exactly one set to 1 on success.
    row.update(tumor_onehot(result))

    return row


def _sorted_results(results: List[PatientResult]) -> List[PatientResult]:
    """Success first, then no-tumor-info, then failed / unresolved last."""
    return sorted(
        results,
        key=lambda r: (status_sort_key(r.classification_status), r.patnr),
    )


def build_patient_dataframe(results: List[PatientResult]) -> pd.DataFrame:
    rows = [build_patient_row(r) for r in _sorted_results(results)]
    df = pd.DataFrame(rows, columns=patient_output_columns())
    return df


def build_missing_dataframe(results: List[PatientResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        if not r.no_tumor_information:
            continue
        rows.append(
            {
                COL_PATNR: r.patnr,
                "report_count": r.report_count,
                "usable_report_count": r.usable_report_count,
                "latest_p_dat": r.latest_p_dat,
                "classification_status": r.classification_status,
                "note": (
                    "Keine verwertbare Tumorinformation im Pathologietext; "
                    "andere Datenquelle noetig."
                ),
            }
        )
    return pd.DataFrame(rows, columns=MISSING_INFO_COLUMNS)


def build_failed_dataframe(results: List[PatientResult]) -> pd.DataFrame:
    """Patients that had text but were not classified (need attention / re-run)."""
    rows = []
    for r in results:
        if r.classification_status not in FAILED_STATUSES:
            continue
        rows.append(
            {
                COL_PATNR: r.patnr,
                "classification_status": r.classification_status,
                "usable_report_count": r.usable_report_count,
                "latest_p_dat": r.latest_p_dat,
                "predicted_tumor_category": r.predicted_tumor_category or "",
                "certainty": r.certainty,
                "reasoning": r.reasoning,
                "error_message": r.error_message,
                "manual_review_reasons": "; ".join(r.manual_review_reasons),
            }
        )
    return pd.DataFrame(rows, columns=FAILED_COLUMNS)
