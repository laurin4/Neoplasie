"""Load and validate a KISIM pathology Excel/CSV export.

Preserves every input row (never drops patients), records a per-row quality
status, parses dates tolerantly, keeps identifiers and report text intact, and
produces a dataset summary for the startup banner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.tasks.tumor_histopathology.constants import (
    COL_P_DAT,
    COL_P_KOM,
    COL_PATNR,
    REQUIRED_INPUT_COLUMNS,
)
from src.tasks.tumor_histopathology.io.schema import (
    ROW_STATUS_MISSING_TEXT,
    ROW_STATUS_USABLE,
)
from src.tasks.tumor_histopathology.preprocessing.normalize import (
    is_missing_text,
    normalize_columns,
    parse_date,
    to_str_id,
)

LOGGER = logging.getLogger(__name__)

# Internal columns added to the working DataFrame.
COL_ROW_INDEX = "_source_row_index"
COL_PATNR_STR = "_patnr_str"
COL_P_DAT_PARSED = "_p_dat_parsed"
COL_DATE_PARSE_OK = "_date_parse_ok"
COL_ROW_STATUS = "_row_status"


class InputValidationError(ValueError):
    """Raised when required columns are missing from the input."""


@dataclass
class DatasetSummary:
    total_rows: int = 0
    unique_patients: int = 0
    rows_with_text: int = 0
    rows_without_text: int = 0
    patients_with_usable_report: int = 0
    patients_without_usable_report: int = 0
    date_parse_failures: int = 0
    duplicate_rows: int = 0

    def as_lines(self) -> List[str]:
        return [
            f"total rows:                    {self.total_rows}",
            f"unique patients:               {self.unique_patients}",
            f"rows with pathology text:      {self.rows_with_text}",
            f"rows without pathology text:   {self.rows_without_text}",
            f"patients with usable report:   {self.patients_with_usable_report}",
            f"patients without usable report:{self.patients_without_usable_report}",
            f"date parse failures:           {self.date_parse_failures}",
            f"duplicate rows:                {self.duplicate_rows}",
        ]


@dataclass
class LoadedData:
    df: pd.DataFrame
    summary: DatasetSummary
    sheet_name: str = ""
    source_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


def _read_raw(path: Path, sheet_name: Optional[str]) -> tuple[pd.DataFrame, str, List[str]]:
    errors: List[str] = []
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if path.suffix.lower() in (".csv", ".tsv"):
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(path, dtype=object, sep=sep, keep_default_na=True)
        return df.reset_index(drop=True), "", errors

    xl = pd.ExcelFile(path, engine="openpyxl")
    use_sheet = sheet_name
    if use_sheet is None:
        use_sheet = xl.sheet_names[0] if xl.sheet_names else ""
    elif use_sheet not in xl.sheet_names:
        raise InputValidationError(
            f"Sheet {use_sheet!r} not in workbook (available: {xl.sheet_names})"
        )
    df = pd.read_excel(xl, sheet_name=use_sheet, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True), use_sheet, errors


def load_input(
    path: Path, *, sheet_name: Optional[str] = None
) -> LoadedData:
    """Load, validate, normalize, and annotate a KISIM export."""
    path = Path(path)
    df_raw, used_sheet, errors = _read_raw(path, sheet_name)
    df = normalize_columns(df_raw)

    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]
    if missing:
        raise InputValidationError(
            f"Missing required column(s): {missing}. Found: {list(df.columns)}"
        )

    has_date_col = COL_P_DAT in df.columns

    # Deterministic source-row index preserved for traceability.
    df[COL_ROW_INDEX] = range(len(df))
    df[COL_PATNR_STR] = df[COL_PATNR].map(to_str_id)

    parsed_dates: List[Optional[pd.Timestamp]] = []
    date_ok_flags: List[bool] = []
    row_statuses: List[str] = []
    date_parse_failures = 0

    for _, row in df.iterrows():
        if has_date_col:
            ts, ok = parse_date(row.get(COL_P_DAT))
        else:
            ts, ok = None, True
        parsed_dates.append(ts)
        date_ok_flags.append(ok)
        if not ok:
            date_parse_failures += 1

        missing_text = is_missing_text(row.get(COL_P_KOM))
        row_statuses.append(ROW_STATUS_MISSING_TEXT if missing_text else ROW_STATUS_USABLE)

    df[COL_P_DAT_PARSED] = parsed_dates
    df[COL_DATE_PARSE_OK] = date_ok_flags
    df[COL_ROW_STATUS] = row_statuses

    summary = _summarize(df, date_parse_failures)
    LOGGER.info(
        "Loaded %s: rows=%d patients=%d usable_rows=%d",
        path.name, summary.total_rows, summary.unique_patients, summary.rows_with_text,
    )
    return LoadedData(
        df=df, summary=summary, sheet_name=used_sheet, source_path=path, errors=errors
    )


def _summarize(df: pd.DataFrame, date_parse_failures: int) -> DatasetSummary:
    total = len(df)
    usable_mask = df[COL_ROW_STATUS] == ROW_STATUS_USABLE
    rows_with_text = int(usable_mask.sum())

    patients = df[COL_PATNR_STR]
    unique_patients = int(patients.nunique())

    usable_patient_ids = set(df.loc[usable_mask, COL_PATNR_STR])
    all_patient_ids = set(patients)
    patients_with = len(usable_patient_ids)
    patients_without = len(all_patient_ids - usable_patient_ids)

    # Duplicate rows on (patnr, p_kom) content.
    dup_cols = [COL_PATNR_STR, COL_P_KOM] if COL_P_KOM in df.columns else [COL_PATNR_STR]
    duplicate_rows = int(df.duplicated(subset=dup_cols, keep="first").sum())

    return DatasetSummary(
        total_rows=total,
        unique_patients=unique_patients,
        rows_with_text=rows_with_text,
        rows_without_text=total - rows_with_text,
        patients_with_usable_report=patients_with,
        patients_without_usable_report=patients_without,
        date_parse_failures=date_parse_failures,
        duplicate_rows=duplicate_rows,
    )
