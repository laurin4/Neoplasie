"""Per-patient inference runner with incremental, resumable writes.

Orchestrates: patient records -> single-stage LLM classification -> parsed
result. Patients with no usable reports bypass the LLM entirely. Every result
is appended to a JSONL progress file as it completes so an interrupted run can
resume without losing finished patients.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from src.tasks.tumor_histopathology.inference import prompt as prompt_mod
from src.tasks.tumor_histopathology.inference.llm_client import call_llm
from src.tasks.tumor_histopathology.inference.parse import parse_tumor_response
from src.tasks.tumor_histopathology.inference.result import PatientResult
from src.tasks.tumor_histopathology.io.schema import (
    STATUS_LLM_DISABLED,
    STATUS_LLM_FAILED,
    STATUS_NO_TUMOR_INFORMATION,
    STATUS_PARSE_FAILED,
    STATUS_SUCCESS,
    STATUS_UNCERTAIN,
    STATUS_UNSUPPORTED_CATEGORY,
)
from src.tasks.tumor_histopathology.preprocessing.aggregate_patient_reports import (
    PatientRecord,
)

LOGGER = logging.getLogger(__name__)

LLMCallable = Callable[[list], str]

PROGRESS_FILENAME = "tumor_histopathology_progress.jsonl"


def _fmt_date(ts) -> str:
    if ts is None or ts is pd.NaT:
        return ""
    try:
        return ts.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return str(ts)


def _evidence_summary(evidence: List[dict]) -> str:
    parts = []
    for e in evidence:
        excerpt = str(e.get("text_excerpt", "") or "").strip()
        if excerpt:
            parts.append(excerpt)
    return " | ".join(parts)


def _historical_summary(items: List[dict]) -> str:
    parts = []
    for h in items:
        diag = str(h.get("diagnosis", "") or "").strip()
        reason = str(h.get("reason_not_selected", "") or "").strip()
        if diag:
            parts.append(f"{diag} ({reason})" if reason else diag)
    return " | ".join(parts)


def _compute_manual_review(result: PatientResult) -> None:
    """Set ``manual_review_required`` + reasons per the clinical review rules."""
    reasons: List[str] = []
    if result.classification_status in (
        STATUS_PARSE_FAILED, STATUS_LLM_FAILED, STATUS_UNSUPPORTED_CATEGORY,
        STATUS_UNCERTAIN,
    ):
        reasons.append(f"status={result.classification_status}")
    if result.multiple_categories:
        reasons.append("multiple_current_diagnoses")
    if result.category_ambiguous:
        reasons.append("ambiguous_category_andere")
    if result.parse_repair_applied:
        reasons.append("parser_repair_applied")
    if result.context_truncated:
        reasons.append("context_truncated")
    if result.classification_status == STATUS_SUCCESS and result.certainty == "low":
        reasons.append("low_certainty")
    result.manual_review_reasons = reasons
    result.manual_review_required = bool(reasons)


def _missing_result(record: PatientRecord) -> PatientResult:
    result = PatientResult(
        patnr=record.patnr,
        classification_status=STATUS_NO_TUMOR_INFORMATION,
        latest_p_dat=_fmt_date(record.latest_p_dat),
        report_count=record.report_count,
        usable_report_count=record.usable_report_count,
        source_row_indices=record.source_row_indices,
        all_report_dates=record.all_report_dates,
        no_tumor_information=True,
        context_truncated=record.context_truncated,
    )
    _compute_manual_review(result)
    return result


def classify_patient(
    record: PatientRecord, llm_callable: LLMCallable
) -> PatientResult:
    """Classify a single patient with >=1 usable report."""
    messages = prompt_mod.build_messages(record.context_text)

    result = PatientResult(
        patnr=record.patnr,
        classification_status=STATUS_PARSE_FAILED,
        latest_p_dat=_fmt_date(record.latest_p_dat),
        report_count=record.report_count,
        usable_report_count=record.usable_report_count,
        source_row_indices=record.source_row_indices,
        all_report_dates=record.all_report_dates,
        context_truncated=record.context_truncated,
    )

    try:
        raw = llm_callable(messages)
    except Exception as exc:  # noqa: BLE001 - never let one patient crash the run
        result.classification_status = STATUS_LLM_FAILED
        result.llm_failed = True
        result.error_message = f"{type(exc).__name__}: {exc}"
        _compute_manual_review(result)
        return result

    parsed = parse_tumor_response(raw, context=f"patnr={record.patnr}")
    result.raw_response = parsed.raw_response[:5000]
    result.classification_status = parsed.status
    result.certainty = parsed.certainty
    result.reasoning = parsed.reasoning
    result.supporting_evidence = parsed.supporting_evidence
    result.historical_diagnoses_mentioned = parsed.historical_diagnoses_mentioned
    result.uncertainty_reasons = parsed.uncertainty_reasons
    result.parse_repair_applied = parsed.parse_repair_applied
    result.multiple_categories = parsed.multiple_categories
    result.category_ambiguous = parsed.category_ambiguous
    result.error_message = parsed.error_message

    result.parse_failed = parsed.status == STATUS_PARSE_FAILED
    result.no_tumor_information = parsed.status == STATUS_NO_TUMOR_INFORMATION

    if parsed.status == STATUS_SUCCESS:
        result.predicted_tumor_category = parsed.current_tumor_category
        result.predicted_output_column = parsed.predicted_output_column

    _compute_manual_review(result)
    return result


def _disabled_result(record: PatientRecord) -> PatientResult:
    result = PatientResult(
        patnr=record.patnr,
        classification_status=STATUS_LLM_DISABLED,
        latest_p_dat=_fmt_date(record.latest_p_dat),
        report_count=record.report_count,
        usable_report_count=record.usable_report_count,
        source_row_indices=record.source_row_indices,
        all_report_dates=record.all_report_dates,
        context_truncated=record.context_truncated,
    )
    _compute_manual_review(result)
    return result


def run_inference(
    records: List[PatientRecord],
    *,
    output_dir: Path,
    llm_callable: Optional[LLMCallable] = None,
    use_llm: bool = True,
    resume: bool = False,
    progress_path: Optional[Path] = None,
) -> List[PatientResult]:
    """Classify all patient records, writing progress incrementally.

    Returns the full list of results (including any loaded from a prior run).
    """
    if llm_callable is None:
        llm_callable = call_llm
    if progress_path is None:
        progress_path = Path(output_dir) / PROGRESS_FILENAME

    done: dict[str, PatientResult] = {}
    if resume and progress_path.exists():
        loaded = _load_progress(progress_path)
        # Retry transient LLM failures on resume; keep every other outcome.
        done = {
            pid: r for pid, r in loaded.items()
            if r.classification_status != STATUS_LLM_FAILED
        }
        retryable = len(loaded) - len(done)
        LOGGER.info(
            "Resume: %d completed, %d previously-failed will be retried",
            len(done), retryable,
        )

    results: List[PatientResult] = []
    # Open in append mode so a resumed run continues the same file.
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("a", encoding="utf-8") as progress_fh:
        for record in records:
            if record.patnr in done:
                results.append(done[record.patnr])
                continue

            if not record.has_usable_reports:
                result = _missing_result(record)
            elif not use_llm:
                result = _disabled_result(record)
            else:
                result = classify_patient(record, llm_callable)

            progress_fh.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
            progress_fh.flush()
            results.append(result)

    return results


def _load_progress(path: Path) -> dict[str, PatientResult]:
    done: dict[str, PatientResult] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        patnr = str(data.get("patnr", ""))
        if patnr:
            done[patnr] = PatientResult.from_dict(data)
    return done
