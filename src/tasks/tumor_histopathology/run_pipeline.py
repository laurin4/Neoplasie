"""CLI entry point for the tumor histopathology pipeline.

    python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/input.xlsx

Loads a KISIM pathology export, aggregates reports per patient, classifies each
patient's final tumor category with a single-stage LLM call, and writes the
patient-level, missing-information, and review outputs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.inference import prompt as prompt_mod
from src.tasks.tumor_histopathology.inference.runner import (
    PROGRESS_FILENAME,
    run_inference,
)
from src.tasks.tumor_histopathology.io.input_loader import load_input
from src.tasks.tumor_histopathology.io.output_writer import write_all_outputs
from src.tasks.tumor_histopathology.preprocessing.aggregate_patient_reports import (
    PatientRecord,
    build_patient_records,
)

LOGGER = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tumor_histopathology",
        description="Classify the final neuro-oncological tumor category per patient.",
    )
    p.add_argument("--input", type=str, default=None, help="Path to KISIM Excel/CSV export.")
    p.add_argument("--sheet", type=str, default=None, help="Worksheet name (default: first).")
    p.add_argument("--output", type=str, default=None, help="Output directory.")
    p.add_argument("--limit", type=int, default=None, help="Only process the first N patients.")
    p.add_argument("--patient-id", type=str, default=None, help="Only process this patnr.")
    p.add_argument("--dry-run", action="store_true", help="Load + aggregate + summary; no LLM, no writes.")
    p.add_argument("--resume", action="store_true", help="Resume from the progress file.")
    p.add_argument("--overwrite", action="store_true", help="Delete prior progress/outputs first.")
    p.add_argument("--no-llm", action="store_true", help="Run plumbing without calling the LLM.")
    p.add_argument("--prompt-preview", action="store_true", help="Print the prompt for one patient and exit.")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return p


def _select_records(
    records: List[PatientRecord], *, patient_id: Optional[str], limit: Optional[int]
) -> List[PatientRecord]:
    selected = records
    if patient_id:
        selected = [r for r in selected if r.patnr == str(patient_id)]
    if limit is not None and limit >= 0:
        selected = selected[:limit]
    return selected


def _print_banner(
    *, input_path: Path, sheet: str, summary, output_dir: Path, selected: int, mode: str
) -> None:
    provider = config.get_provider()
    url = config.get_usz_url() if provider == "usz_api" else config.get_ollama_url()
    lines = [
        "=" * 60,
        "TUMOR HISTOPATHOLOGY PIPELINE",
        "=" * 60,
        f"input path:     {input_path}",
        f"sheet:          {sheet or '(first)'}",
        *summary.as_lines(),
        f"patients selected for this run: {selected}",
        f"output dir:     {output_dir}",
        f"LLM provider:   {provider} ({url})",
        f"run mode:       {mode}",
        "=" * 60,
    ]
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    input_path = Path(args.input) if args.input else config.get_input_path()
    sheet = args.sheet if args.sheet is not None else config.get_sheet_name()
    output_dir = Path(args.output) if args.output else config.get_output_dir()

    try:
        loaded = load_input(input_path, sheet_name=sheet)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    records = build_patient_records(loaded.df)
    selected = _select_records(records, patient_id=args.patient_id, limit=args.limit)

    mode = "dry-run" if args.dry_run else ("no-llm" if args.no_llm else "classify")
    _print_banner(
        input_path=input_path,
        sheet=loaded.sheet_name,
        summary=loaded.summary,
        output_dir=output_dir,
        selected=len(selected),
        mode=mode,
    )

    if args.prompt_preview:
        example = next((r for r in selected if r.has_usable_reports), None)
        print("\n----- SYSTEM PROMPT -----\n")
        print(prompt_mod.load_system_prompt())
        if example is not None:
            print("\n----- EXAMPLE USER PROMPT (patnr=%s) -----\n" % example.patnr)
            print(prompt_mod.build_user_prompt(example.context_text))
        else:
            print("\n(no patient with a usable report in the selection)")
        return 0

    if args.dry_run:
        print("\nDry run complete: no classification performed, no files written.")
        return 0

    progress_path = output_dir / PROGRESS_FILENAME
    if args.overwrite:
        for name in (
            PROGRESS_FILENAME,
            config.PATIENT_PREDICTIONS_XLSX,
            config.PATIENT_PREDICTIONS_CSV,
            config.MISSING_INFORMATION_CSV,
            config.REVIEW_CSV,
        ):
            fp = output_dir / name
            if fp.exists():
                fp.unlink()

    results = run_inference(
        selected,
        output_dir=output_dir,
        use_llm=not args.no_llm,
        resume=args.resume,
        progress_path=progress_path,
    )

    paths = write_all_outputs(results, output_dir)
    print("\nOutputs written:")
    for label, fp in paths.items():
        print(f"  {label}: {fp}")

    n_review = sum(1 for r in results if r.manual_review_required)
    n_missing = sum(1 for r in results if r.no_tumor_information)
    print(
        f"\nDone: {len(results)} patients | {n_missing} without tumor info | "
        f"{n_review} flagged for manual review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
