"""End-to-end clinical scenario tests with a stub LLM (Phase 13).

Covers brief scenarios 1-4, 7-10, 12, 16, 17 plus the llm_failed path. All data
is synthetic; the LLM is stubbed, so no network and no real patient data.
"""

from __future__ import annotations

from _synthetic import StubLLM, make_input_df, tumor_json, write_xlsx

from src.tasks.tumor_histopathology.constants import TARGET_COLUMNS
from src.tasks.tumor_histopathology.export.patient_output import build_patient_row
from src.tasks.tumor_histopathology.inference.runner import run_inference
from src.tasks.tumor_histopathology.io.input_loader import load_input
from src.tasks.tumor_histopathology.io.schema import (
    STATUS_LLM_FAILED,
    STATUS_NO_TUMOR_INFORMATION,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED_CATEGORY,
)
from src.tasks.tumor_histopathology.preprocessing.aggregate_patient_reports import (
    build_patient_records,
)


def _run(rows, stub, tmp_path):
    path = write_xlsx(make_input_df(rows), tmp_path / "in.xlsx")
    loaded = load_input(path)
    records = build_patient_records(loaded.df)
    results = run_inference(records, output_dir=tmp_path, llm_callable=stub)
    return {r.patnr: r for r in results}, records


def test_scenario1_confirmed_glioblastoma(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom WHO IV"}], stub, tmp_path)
    r = results["P1"]
    assert r.classification_status == STATUS_SUCCESS
    assert r.predicted_tumor_category == "glioblastom"
    assert r.predicted_output_column == "12_Glioblastom"


def test_scenario2_gliom_then_glioblastom(tmp_path):
    stub = StubLLM(default=tumor_json(
        "Glioblastom",
        historical=[{"diagnosis": "Gliom", "report_date": "2019", "reason_not_selected": "superseded"}],
    ))
    results, _ = _run([
        {"patnr": "P1", "p_dat": "2019-01-01", "p_kom": "Gliom"},
        {"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"},
    ], stub, tmp_path)
    assert results["P1"].predicted_tumor_category == "glioblastom"


def test_scenario3_metastasis_not_historical_adenocarcinoma(tmp_path):
    stub = StubLLM(default=tumor_json(
        "Metastase",
        historical=[{
            "diagnosis": "ampulläres Adenokarzinom",
            "report_date": "2007",
            "reason_not_selected": "historical comparison",
        }],
    ))
    results, _ = _run([
        {"patnr": "P1", "p_dat": "2022-01-01", "p_kom": "Metastase, vgl. Adenokarzinom 2007"},
    ], stub, tmp_path)
    r = results["P1"]
    assert r.predicted_tumor_category == "metastase"
    row = build_patient_row(r)
    # Exactly one tumor column set, and it is the metastasis column.
    set_cols = [col for col in TARGET_COLUMNS if row[col] == 1]
    assert set_cols == ["12_Metastase"]
    assert "Adenokarzinom" in r.historical_diagnoses_mentioned[0]["diagnosis"]


def test_scenario4_historical_only_not_selected(tmp_path):
    stub = StubLLM(default=tumor_json(
        None, available=False,
        historical=[{"diagnosis": "Meningeom", "report_date": "2005", "reason_not_selected": "historical"}],
    ))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Z.n. Meningeom 2005, kein Tumor aktuell"}], stub, tmp_path)
    assert results["P1"].classification_status == STATUS_NO_TUMOR_INFORMATION


def test_scenario7_only_blank_bypasses_llm(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    results, _ = _run([{"patnr": "P9", "p_dat": "2020-01-01", "p_kom": "   "}], stub, tmp_path)
    r = results["P9"]
    assert r.classification_status == STATUS_NO_TUMOR_INFORMATION
    assert r.no_tumor_information is True
    # LLM must NOT be called for a patient with no usable report.
    assert len(stub.calls) == 0
    row = build_patient_row(r)
    assert row["Keine_Tumorinformation"] == 1
    assert all(row[col] == "" for col in TARGET_COLUMNS)


def test_scenario8_negated_diagnosis_not_positive(tmp_path):
    stub = StubLLM(default=tumor_json(None, available=False))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Kein Anhalt fuer Malignitaet"}], stub, tmp_path)
    r = results["P1"]
    assert r.predicted_tumor_category is None
    row = build_patient_row(r)
    assert all(row[col] == "" for col in TARGET_COLUMNS)


def test_scenario9_differential_then_confirmed(tmp_path):
    stub = StubLLM(default=tumor_json("Lymphom"))
    results, _ = _run([
        {"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "V.a. Gliom"},
        {"patnr": "P1", "p_dat": "2021-03-01", "p_kom": "Histologisch gesichertes ZNS-Lymphom"},
    ], stub, tmp_path)
    assert results["P1"].predicted_tumor_category == "lymphom"


def test_scenario10_unsupported_category_flagged(tmp_path):
    stub = StubLLM(default=tumor_json("Pankreaskarzinom"))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "..."}], stub, tmp_path)
    r = results["P1"]
    assert r.classification_status == STATUS_UNSUPPORTED_CATEGORY
    assert r.manual_review_required is True


def test_scenario12_exactly_one_output_column(tmp_path):
    stub = StubLLM(default=tumor_json("Meningeom"))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Meningeom"}], stub, tmp_path)
    row = build_patient_row(results["P1"])
    assert sum(1 for col in TARGET_COLUMNS if row[col] == 1) == 1


def test_scenario16_no_patient_dropped(tmp_path):
    stub = StubLLM(default=tumor_json("Glioblastom"))
    rows = [{"patnr": f"P{i}", "p_dat": "2021-01-01", "p_kom": "Glioblastom"} for i in range(5)]
    rows.append({"patnr": "PX", "p_kom": ""})  # missing info patient
    results, records = _run(rows, stub, tmp_path)
    assert len(results) == len(records) == 6


def test_scenario17_ambiguous_category_manual_review(tmp_path):
    stub = StubLLM(default=tumor_json("Andere"))
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "seltener Tumor"}], stub, tmp_path)
    r = results["P1"]
    assert r.category_ambiguous is True
    assert r.manual_review_required is True
    assert "ambiguous_category_andere" in r.manual_review_reasons


def test_llm_failure_marked(tmp_path):
    stub = StubLLM(raise_error=True)
    results, _ = _run([{"patnr": "P1", "p_dat": "2021-01-01", "p_kom": "Glioblastom"}], stub, tmp_path)
    r = results["P1"]
    assert r.classification_status == STATUS_LLM_FAILED
    assert r.llm_failed is True
    assert r.manual_review_required is True
