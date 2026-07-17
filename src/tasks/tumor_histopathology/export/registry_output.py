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
)
from src.tasks.tumor_histopathology.export.patient_output import tumor_onehot
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.tasks.tumor_histopathology.io.schema import template_output_columns


def build_registry_dataframe(
    results: List[PatientResult],
    latest_text_by_patnr: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """One row per patient in the exact registry-template column order."""
    latest_text_by_patnr = latest_text_by_patnr or {}
    rows: List[Dict[str, object]] = []
    for r in results:
        row: Dict[str, object] = {
            COL_PATNR: r.patnr,
            COL_P_DAT: r.latest_p_dat,
            COL_P_KOM: latest_text_by_patnr.get(r.patnr, ""),
        }
        row.update(tumor_onehot(r))
        rows.append(row)
    return pd.DataFrame(rows, columns=template_output_columns())
