"""Parser tests (Phase 8, scenarios 10/11)."""

from __future__ import annotations

from _synthetic import tumor_json

from src.tasks.tumor_histopathology.inference.parse import parse_tumor_response
from src.tasks.tumor_histopathology.io.schema import (
    STATUS_NO_TUMOR_INFORMATION,
    STATUS_PARSE_FAILED,
    STATUS_SUCCESS,
    STATUS_UNCERTAIN,
    STATUS_UNSUPPORTED_CATEGORY,
)


def test_success_resolves_category_and_column():
    res = parse_tumor_response(tumor_json("Glioblastom"))
    assert res.success is True
    assert res.status == STATUS_SUCCESS
    assert res.current_tumor_category == "glioblastom"
    assert res.predicted_output_column == "12_Glioblastom"


def test_success_with_synonym():
    res = parse_tumor_response(tumor_json("glioblastoma multiforme"))
    assert res.current_tumor_category == "glioblastom"


def test_markdown_fenced_json_parses():
    raw = "```json\n" + tumor_json("Meningeom") + "\n```"
    res = parse_tumor_response(raw)
    assert res.status == STATUS_SUCCESS
    assert res.current_tumor_category == "meningeom"


def test_no_tumor_information():
    res = parse_tumor_response(tumor_json(None, available=False))
    assert res.status == STATUS_NO_TUMOR_INFORMATION
    assert res.current_tumor_category is None


def test_unsupported_category():
    res = parse_tumor_response(tumor_json("Pankreaskarzinom"))
    assert res.status == STATUS_UNSUPPORTED_CATEGORY
    assert res.current_tumor_category is None


def test_multiple_categories_marked_uncertain():
    res = parse_tumor_response(tumor_json(["Glioblastom", "Meningeom"]))
    assert res.status == STATUS_UNCERTAIN
    assert res.multiple_categories is True
    assert "multiple_final_categories" in res.uncertainty_reasons


def test_malformed_json_is_parse_failed():
    res = parse_tumor_response('{"current_tumor_category": "Glioblastom" ')  # missing brace
    # brace-matching recovers nothing complete -> parse failure
    assert res.status == STATUS_PARSE_FAILED
    assert res.parse_error_reason in ("no_json_object_found", "json_decode_error")


def test_empty_response_is_parse_failed():
    res = parse_tumor_response("")
    assert res.status == STATUS_PARSE_FAILED
    assert res.parse_error_reason == "empty_llm_response"


def test_certainty_normalized_from_german():
    res = parse_tumor_response(tumor_json("Glioblastom", certainty="hoch"))
    assert res.certainty == "high"


def test_ambiguous_category_flagged():
    res = parse_tumor_response(tumor_json("Andere"))
    assert res.status == STATUS_SUCCESS
    assert res.category_ambiguous is True
