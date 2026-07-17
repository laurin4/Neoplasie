"""Build the clean registry-template table (one row per patient).

Column order matches the registry template exactly: ``patnr``, ``p_dat``,
``p_kom``, then the one-hot ``12_*`` tumor columns. ``p_dat`` / ``p_kom`` carry
the patient's latest report (date and text); the text comes straight from the
freshly loaded input so it is correct even on a resumed run.
"""

from __future__ import annotations

from typing import Dict, List, Mapping

import pandas as pd

from src.tasks.tumor_histopathology.constants import (
    COL_P_DAT,
    COL_P_KOM,
    COL_PATNR,
    TARGET_COLUMNS,
)
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.tasks.tumor_histopathology.io.schema import (
    STATUS_SUCCESS,
    status_sort_key,
    template_output_columns,
)


def _binary_columns(result: PatientResult) -> Dict[str, int]:
    """Full 0/1 vector: all zero, exactly one 1 for a successfully classified
    patient. Non-success patients (missing info / failed) are all-zero."""
    cols: Dict[str, int] = {col: 0 for col in TARGET_COLUMNS}
    if (
        result.classification_status == STATUS_SUCCESS
        and result.predicted_output_column in TARGET_COLUMNS
    ):
        cols[result.predicted_output_column] = 1
    return cols


def build_registry_dataframe(
    results: List[PatientResult],
    latest_text_by_patnr: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """One row per patient in the exact registry-template column order.

    Tumor columns are a 0/1 binary matrix (every cell filled). A ``success``
    patient has exactly one ``1``; patients without a final classification
    (missing information or a failed/unsupported outcome) are all-zero -- cross
    reference the missing-information and failed output files for those.
    """
    latest_text_by_patnr = latest_text_by_patnr or {}
    ordered = sorted(
        results,
        key=lambda r: (status_sort_key(r.classification_status), r.patnr),
    )
    rows: List[Dict[str, object]] = []
    for r in ordered:
        row: Dict[str, object] = {
            COL_PATNR: r.patnr,
            COL_P_DAT: r.latest_p_dat,
            COL_P_KOM: latest_text_by_patnr.get(r.patnr, ""),
        }
        row.update(_binary_columns(r))
        rows.append(row)
    return pd.DataFrame(rows, columns=template_output_columns())
