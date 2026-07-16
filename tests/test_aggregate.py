"""Patient aggregation tests (Phase 5, scenarios 5/6/13)."""

from __future__ import annotations

from _synthetic import make_input_df, write_xlsx

from src.tasks.tumor_histopathology.io.input_loader import load_input
from src.tasks.tumor_histopathology.preprocessing.aggregate_patient_reports import (
    build_patient_records,
)


def _records_from_rows(rows, tmp_path, **kwargs):
    path = write_xlsx(make_input_df(rows), tmp_path / "in.xlsx")
    loaded = load_input(path)
    return build_patient_records(loaded.df, **kwargs)


def test_reports_aggregated_chronologically(tmp_path):
    recs = _records_from_rows([
        {"patnr": "P1", "p_dat": "2021-05-01", "p_kom": "Zweiter Bericht: Glioblastom"},
        {"patnr": "P1", "p_dat": "2019-01-01", "p_kom": "Erster Bericht: Gliom"},
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": "Verlauf"},
    ], tmp_path)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.usable_report_count == 3
    order = [e.date_str for e in rec.reports]
    assert order == ["2019-01-01", "2020-01-01", "2021-05-01"]
    assert rec.latest_p_dat.strftime("%Y-%m-%d") == "2021-05-01"


def test_blank_rows_excluded_from_context(tmp_path):
    recs = _records_from_rows([
        {"patnr": "P1", "p_dat": "2020-01-01", "p_kom": ""},
        {"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Meningeom Grad I"},
    ], tmp_path)
    rec = recs[0]
    assert rec.report_count == 2
    assert rec.usable_report_count == 1
    assert "Meningeom" in rec.context_text
    assert rec.has_usable_reports is True


def test_patient_with_only_blank_has_no_usable_reports(tmp_path):
    recs = _records_from_rows([
        {"patnr": "P9", "p_dat": "2020-01-01", "p_kom": "   "},
    ], tmp_path)
    rec = recs[0]
    assert rec.usable_report_count == 0
    assert rec.has_usable_reports is False
    assert rec.context_text == ""


def test_reference_gene_section_stripped_by_default(tmp_path):
    report = (
        "Diagnose: Glioblastom, IDH-Wildtyp, WHO Grad 4.\n"
        "MGMT-Promotor methyliert.\n\n"
        "Untersuchte Genabschnitte\n"
        "NM_004333.6\nCDK4\nHotspot, Exon 2\n"
        "NM_000075.4\nCDKN2A\nHotspot, Exon 2\n"
        "EGFR\nHotspot, Exon 3, 7, (11), 12, 15, 18-21, (24-26)\nNM_005228.5\n"
    )
    recs = _records_from_rows([
        {"patnr": "P1", "p_dat": "2024-01-01", "p_kom": report},
    ], tmp_path)
    ctx = recs[0].context_text
    assert "Glioblastom" in ctx                       # diagnosis kept
    assert "MGMT-Promotor methyliert" in ctx          # finding kept
    assert "Untersuchte Genabschnitte" not in ctx     # marker + list removed
    assert "NM_005228.5" not in ctx
    assert "CDKN2A" not in ctx


def test_reference_gene_section_kept_when_disabled(tmp_path):
    report = "Diagnose: Meningeom.\nUntersuchte Genabschnitte\nNM_004333.6\nCDK4\n"
    recs = _records_from_rows([
        {"patnr": "P1", "p_dat": "2024-01-01", "p_kom": report},
    ], tmp_path, strip_reference=False)
    ctx = recs[0].context_text
    assert "Untersuchte Genabschnitte" in ctx
    assert "NM_004333.6" in ctx


def test_truncation_keeps_most_recent(tmp_path):
    long_text = "X" * 500
    recs = _records_from_rows([
        {"patnr": "P1", "p_dat": "2015-01-01", "p_kom": "OLD " + long_text},
        {"patnr": "P1", "p_dat": "2016-01-01", "p_kom": "MID " + long_text},
        {"patnr": "P1", "p_dat": "2022-01-01", "p_kom": "RECENT " + long_text},
    ], tmp_path, max_context_chars=800)
    rec = recs[0]
    assert rec.context_truncated is True
    assert rec.dropped_report_count >= 1
    assert "RECENT" in rec.context_text  # most recent retained
