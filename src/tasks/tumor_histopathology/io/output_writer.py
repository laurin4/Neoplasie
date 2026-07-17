"""Write the four tumor histopathology output files.

- patient predictions (xlsx + csv), template-compatible column order
- missing-information (csv)
- review (csv)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.export.patient_output import (
    build_failed_dataframe,
    build_missing_dataframe,
    build_patient_dataframe,
)
from src.tasks.tumor_histopathology.export.registry_output import build_registry_dataframe
from src.tasks.tumor_histopathology.export.review_output import build_review_dataframe
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.pipeline.paths import ensure_dir

LOGGER = logging.getLogger(__name__)


def _write_excel(df, path: Path, fallback_csv: Path) -> None:
    try:
        df.to_excel(path, index=False, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - xlsx optional; csv is authoritative
        LOGGER.warning("Failed to write xlsx (%s); csv written at %s", exc, fallback_csv)


def write_all_outputs(
    results: List[PatientResult],
    output_dir: Path,
    latest_text_by_patnr: Optional[Mapping[str, str]] = None,
) -> Dict[str, Path]:
    output_dir = ensure_dir(Path(output_dir))

    patient_df = build_patient_dataframe(results)
    missing_df = build_missing_dataframe(results)
    review_df = build_review_dataframe(results)
    failed_df = build_failed_dataframe(results)
    registry_df = build_registry_dataframe(results, latest_text_by_patnr)

    xlsx_path = output_dir / config.PATIENT_PREDICTIONS_XLSX
    csv_path = output_dir / config.PATIENT_PREDICTIONS_CSV
    missing_path = output_dir / config.MISSING_INFORMATION_CSV
    review_path = output_dir / config.REVIEW_CSV
    failed_path = output_dir / config.FAILED_CSV
    registry_xlsx_path = output_dir / config.REGISTRY_TEMPLATE_XLSX
    registry_csv_path = output_dir / config.REGISTRY_TEMPLATE_CSV

    patient_df.to_csv(csv_path, index=False)
    _write_excel(patient_df, xlsx_path, csv_path)
    missing_df.to_csv(missing_path, index=False)
    review_df.to_csv(review_path, index=False)
    failed_df.to_csv(failed_path, index=False)
    registry_df.to_csv(registry_csv_path, index=False)
    _write_excel(registry_df, registry_xlsx_path, registry_csv_path)

    paths = {
        "patient_predictions_xlsx": xlsx_path,
        "patient_predictions_csv": csv_path,
        "registry_template_xlsx": registry_xlsx_path,
        "registry_template_csv": registry_csv_path,
        "missing_information_csv": missing_path,
        "failed_csv": failed_path,
        "review_csv": review_path,
    }
    LOGGER.info(
        "Wrote outputs: %d patients, %d missing-info, %d failed, %d review rows",
        len(patient_df), len(missing_df), len(failed_df), len(review_df),
    )
    return paths
