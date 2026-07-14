"""Output file tests (Phase 9-10, scenarios 12/13/14/16 + resume)."""

from __future__ import annotations

import pandas as pd
from _synthetic import StubLLM, make_input_df, tumor_json, write_xlsx

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.constants import TARGET_COLUMNS
from src.tasks.tumor_histopathology.io.input_loader import load_input
from src.tasks.tumor_histopathology.io.output_writer import write_all_outputs
from src.tasks.tumor_histopathology.io.schema import (
    patient_output_columns,
    template_output_columns,
)
from src.tasks.tumor_histopathology.preprocessing.aggregate_patient_reports import (
    build_patient_records,
)
from src.tasks.tumor_histopathology.inference.runner import run_inference


def _run(rows, stub, tmp_path, **kwargs):
    path = write_xlsx(make_input_df(rows), tmp_path / "in.xlsx")
    loaded = load_input(path)
    records = build_patient_records(loaded.df)
    return run_inference(records, output_dir=tmp_path, llm_callable=stub, **kwargs)


def test_write_all_outputs_files_and_columns(tmp_path):
    stub = StubLLM(by_substring={
        "Glioblastom": tumor_json("Glioblastom"),
        "Meningeom": tumor_json("Meningeom"),
    }, default=tumor_json(None, available=False))
    results = _run([
        {"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"},
        {"patnr": "P2", "p_dat": "2020-01-01", "p_kom": "Meningeom"},
        {"patnr": "P3", "p_kom": ""},  # missing info
    ], stub, tmp_path)

    out_dir = tmp_path / "out"
    paths = write_all_outputs(results, out_dir)
    for p in paths.values():
        assert p.exists()

    pdf = pd.read_csv(paths["patient_predictions_csv"], dtype=object)
    assert list(pdf.columns) == patient_output_columns()
    assert len(pdf) == 3  # scenario 16: nobody dropped

    # scenario 14: tumor columns at end in template order.
    assert list(pdf.columns)[-len(TARGET_COLUMNS):] == TARGET_COLUMNS

    # Missing-info file contains P3 only.
    mdf = pd.read_csv(paths["missing_information_csv"], dtype=object)
    assert set(mdf["patnr"]) == {"P3"}

    # Review file exists and lists all patients.
    rdf = pd.read_csv(paths["review_csv"], dtype=object)
    assert set(rdf["patnr"]) == {"P1", "P2", "P3"}


def test_patient_ids_preserved_as_strings_in_output(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    results = _run([{"patnr": "00042", "p_dat": "2021-01-01", "p_kom": "Glioblastom"}], stub, tmp_path)
    paths = write_all_outputs(results, tmp_path / "out")
    pdf = pd.read_csv(paths["patient_predictions_csv"], dtype=object)
    assert pdf.iloc[0]["patnr"] == "00042"


def test_latest_p_dat_retained(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    results = _run([
        {"patnr": "P1", "p_dat": "2018-01-01", "p_kom": "Erst"},
        {"patnr": "P1", "p_dat": "2023-07-07", "p_kom": "Glioblastom"},
    ], stub, tmp_path)
    assert results[0].latest_p_dat == "2023-07-07"


def test_resume_skips_completed_patients(tmp_path):
    stub1 = StubLLM(default=tumor_json("Glioblastom"))
    _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"}], stub1, tmp_path)
    assert len(stub1.calls) == 1

    # Second run with resume: same patient should be skipped (no new LLM calls).
    stub2 = StubLLM(default=tumor_json("Meningeom"))
    results = _run(
        [{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"}],
        stub2, tmp_path, resume=True,
    )
    assert len(stub2.calls) == 0
    assert results[0].predicted_tumor_category == "glioblastom"  # original result kept


def test_template_columns_start_with_patnr_pdat_pkom():
    assert template_output_columns()[:3] == ["patnr", "p_dat", "p_kom"]


def test_output_xlsx_readable(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    results = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"}], stub, tmp_path)
    paths = write_all_outputs(results, tmp_path / "out")
    xdf = pd.read_excel(paths["patient_predictions_xlsx"], dtype=object, engine="openpyxl")
    assert "12_Glioblastom" in xdf.columns
    assert str(xdf.iloc[0]["patnr"]) == "P1"
