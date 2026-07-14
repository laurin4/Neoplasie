"""Build the manual-review table (Phase 10).

Includes every patient so the file is a complete, clinically reviewable
overview, sorted so that cases requiring manual review appear first.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.tasks.tumor_histopathology.constants import COL_PATNR
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.tasks.tumor_histopathology.io.schema import REVIEW_COLUMNS


def _supporting_excerpts(result: PatientResult) -> str:
    parts = []
    for e in result.supporting_evidence:
        date = str(e.get("report_date", "") or "").strip()
        excerpt = str(e.get("text_excerpt", "") or "").strip()
        if excerpt:
            parts.append(f"[{date}] {excerpt}" if date else excerpt)
    return " | ".join(parts)


def _historical(result: PatientResult) -> str:
    parts = []
    for h in result.historical_diagnoses_mentioned:
        diag = str(h.get("diagnosis", "") or "").strip()
        date = str(h.get("report_date", "") or "").strip()
        reason = str(h.get("reason_not_selected", "") or "").strip()
        if diag:
            label = diag
            if date:
                label += f" [{date}]"
            if reason:
                label += f" ({reason})"
            parts.append(label)
    return " | ".join(parts)


def build_review_dataframe(results: List[PatientResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append(
            {
                COL_PATNR: r.patnr,
                "predicted_tumor_category": r.predicted_tumor_category or "",
                "predicted_output_column": r.predicted_output_column or "",
                "certainty": r.certainty,
                "latest_report_date": r.latest_p_dat,
                "classification_status": r.classification_status,
                "reasoning": r.reasoning,
                "supporting_excerpts": _supporting_excerpts(r),
                "historical_diagnoses_mentioned": _historical(r),
                "all_report_dates": ";".join(r.all_report_dates),
                "manual_review_required": 1 if r.manual_review_required else "",
                "manual_review_reasons": ";".join(r.manual_review_reasons),
            }
        )
    df = pd.DataFrame(rows, columns=REVIEW_COLUMNS)
    if not df.empty:
        df = df.sort_values(
            by=["manual_review_required", COL_PATNR],
            ascending=[False, True],
            kind="stable",
        ).reset_index(drop=True)
    return df
