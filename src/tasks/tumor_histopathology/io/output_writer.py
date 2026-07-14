"""Write the four tumor histopathology output files.

- patient predictions (xlsx + csv), template-compatible column order
- missing-information (csv)
- review (csv)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.export.patient_output import (
    build_missing_dataframe,
    build_patient_dataframe,
)
from src.tasks.tumor_histopathology.export.review_output import build_review_dataframe
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.pipeline.paths import ensure_dir

LOGGER = logging.getLogger(__name__)


def write_all_outputs(
    results: List[PatientResult], output_dir: Path
) -> Dict[str, Path]:
    output_dir = ensure_dir(Path(output_dir))

    patient_df = build_patient_dataframe(results)
    missing_df = build_missing_dataframe(results)
    review_df = build_review_dataframe(results)

    xlsx_path = output_dir / config.PATIENT_PREDICTIONS_XLSX
    csv_path = output_dir / config.PATIENT_PREDICTIONS_CSV
    missing_path = output_dir / config.MISSING_INFORMATION_CSV
    review_path = output_dir / config.REVIEW_CSV

    patient_df.to_csv(csv_path, index=False)
    try:
        patient_df.to_excel(xlsx_path, index=False, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - xlsx optional; csv is authoritative
        LOGGER.warning("Failed to write xlsx (%s); csv written at %s", exc, csv_path)
    missing_df.to_csv(missing_path, index=False)
    review_df.to_csv(review_path, index=False)

    paths = {
        "patient_predictions_xlsx": xlsx_path,
        "patient_predictions_csv": csv_path,
        "missing_information_csv": missing_path,
        "review_csv": review_path,
    }
    LOGGER.info(
        "Wrote outputs: %d patients, %d missing-info, %d review rows",
        len(patient_df), len(missing_df), len(review_df),
    )
    return paths
