"""Normalization helper tests (Phase 4, scenario 15)."""

from __future__ import annotations

import pandas as pd

from src.tasks.tumor_histopathology.preprocessing.normalize import (
    is_missing_text,
    normalize_columns,
    parse_date,
    to_str_id,
)


def test_to_str_id_preserves_strings_and_strips_float_zero():
    assert to_str_id("A00123") == "A00123"
    assert to_str_id(12345) == "12345"
    assert to_str_id(12345.0) == "12345"
    assert to_str_id("12345.0") == "12345"
    assert to_str_id(float("nan")) == ""
    assert to_str_id(None) == ""


def test_is_missing_text():
    assert is_missing_text(None) is True
    assert is_missing_text("") is True
    assert is_missing_text("   ") is True
    assert is_missing_text(float("nan")) is True
    assert is_missing_text("nan") is True
    assert is_missing_text("Glioblastom WHO IV") is False


def test_parse_date_valid_and_invalid():
    ts, ok = parse_date("2021-05-04")
    assert ok is True and isinstance(ts, pd.Timestamp)
    ts, ok = parse_date("04.05.2021")
    assert ok is True and ts.year == 2021
    ts, ok = parse_date("not a date")
    assert ok is False and ts is None
    ts, ok = parse_date("")
    assert ok is True and ts is None  # empty is not a parse failure


def test_normalize_columns_maps_headers():
    df = pd.DataFrame({"PatNr": [1], "P_Kom": ["x"], "P_Dat": ["2020-01-01"]})
    out = normalize_columns(df)
    assert "patnr" in out.columns
    assert "p_kom" in out.columns
    assert "p_dat" in out.columns
