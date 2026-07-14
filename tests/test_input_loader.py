"""Input loading + dataset summary tests (Phase 4, scenarios 6/7/15/16)."""

from __future__ import annotations

import pytest
from _synthetic import make_input_df, write_xlsx

from src.tasks.tumor_histopathology.io.input_loader import (
    COL_PATNR_STR,
    InputValidationError,
    load_input,
)


def test_load_counts_and_never_drops_rows(tmp_path):
    df = make_input_df([
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": "Glioblastom"},
        {"patnr": "P1", "p_dat": "2021-01-01", "p_kom": ""},          # blank
        {"patnr": "P2", "p_dat": "2019-06-01", "p_kom": "Meningeom"},
        {"patnr": "P3", "p_dat": "2018-01-01", "p_kom": "   "},       # whitespace only
    ])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    loaded = load_input(path)

    assert loaded.summary.total_rows == 4
    assert loaded.summary.unique_patients == 3
    assert loaded.summary.rows_with_text == 2
    assert loaded.summary.rows_without_text == 2
    assert loaded.summary.patients_with_usable_report == 2   # P1, P2
    assert loaded.summary.patients_without_usable_report == 1  # P3
    # No rows dropped.
    assert len(loaded.df) == 4


def test_patient_ids_preserved_as_strings(tmp_path):
    df = make_input_df([
        {"patnr": 12345, "p_kom": "Glioblastom"},
        {"patnr": "00042", "p_kom": "Meningeom"},
    ])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    loaded = load_input(path)
    ids = set(loaded.df[COL_PATNR_STR])
    assert ids == {"12345", "00042"}


def test_missing_required_column_raises(tmp_path):
    df = make_input_df([{"patnr": "P1", "p_kom": "x"}]).drop(columns=["p_kom"])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    with pytest.raises(InputValidationError):
        load_input(path)


def test_date_parse_failures_counted(tmp_path):
    df = make_input_df([
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": "Glioblastom"},
        {"patnr": "P2", "p_dat": "kaputt", "p_kom": "Meningeom"},
    ])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    loaded = load_input(path)
    assert loaded.summary.date_parse_failures == 1


def test_duplicate_reports_removed_by_default(tmp_path):
    df = make_input_df([
        {"patnr": "P1", "p_dat": "2021-05-01", "p_kom": "Glioblastom WHO IV"},
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": "  glioblastom  who   iv "},  # same text, earlier
        {"patnr": "P1", "p_dat": "2022-01-01", "p_kom": ""},                          # blank kept
        {"patnr": "P2", "p_dat": "2019-06-01", "p_kom": "Meningeom"},
    ])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    loaded = load_input(path)

    assert loaded.summary.duplicate_rows == 1
    assert loaded.summary.duplicates_removed == 1
    # One duplicate usable row dropped; blank row retained -> 3 rows remain.
    assert len(loaded.df) == 3
    # The earliest-dated copy of the duplicated text is the one kept.
    from src.tasks.tumor_histopathology.io.input_loader import COL_P_DAT_PARSED
    mask = loaded.df["p_kom"].str.strip().str.lower().str.startswith("glioblastom", na=False)
    kept = loaded.df[mask]
    assert len(kept) == 1
    assert kept.iloc[0][COL_P_DAT_PARSED].year == 2020


def test_keep_duplicates_when_disabled(tmp_path):
    df = make_input_df([
        {"patnr": "P1", "p_dat": "2021-05-01", "p_kom": "Glioblastom"},
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": "Glioblastom"},
    ])
    path = write_xlsx(df, tmp_path / "in.xlsx")
    loaded = load_input(path, deduplicate=False)
    assert loaded.summary.duplicate_rows == 1
    assert loaded.summary.duplicates_removed == 0
    assert len(loaded.df) == 2
