# Architecture

## Overview

A linear, patient-centric pipeline. One KISIM Excel export in, one row per
patient out, with a single final tumor category per patient.

```
Excel export
   -> io/input_loader        load, validate, normalize, per-row quality status, dataset summary
   -> preprocessing/aggregate_patient_reports  group by patnr, sort by p_dat, build PATIENT CONTEXT
   -> inference/prompt        single-stage prompt (system rules + controlled vocabulary)
   -> inference/llm_client    USZ API / Ollama, bounded retries
   -> inference/parse         extract JSON, validate, resolve category, status taxonomy
   -> inference/runner        per-patient loop, missing bypass, incremental JSONL progress
   -> export + io/output_writer   patient predictions (xlsx/csv), missing-info, review
```

Patients with **zero usable reports** skip the LLM and go straight to a
`no_tumor_information` result.

## Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `constants.py` | Single source of truth: canonical categories, `12_*` output columns, synonyms, `resolve_category()`, `normalize_key()` |
| `config.py` | Paths + `TUMOR_HISTOLOGY_*` environment configuration |
| `io/schema.py` | Classification-status taxonomy, output column ordering |
| `io/input_loader.py` | Robust Excel/CSV load, column validation, quality status, `DatasetSummary` |
| `preprocessing/normalize.py` | Column-name normalization, string IDs, tolerant date parsing, missing-text detection |
| `preprocessing/aggregate_patient_reports.py` | `PatientRecord`, chronological ordering, context building + truncation |
| `inference/prompt.py` | Loads the prompt template and injects the vocabulary block |
| `inference/llm_client.py` | Provider-agnostic HTTP client with retries (`call_llm`) |
| `inference/parse.py` | JSON extraction/repair engine + tumor-specific validation -> `TumorParseResult` |
| `inference/result.py` | `PatientResult` dataclass + JSON (de)serialization |
| `inference/runner.py` | Orchestration, manual-review logic, incremental/resumable writes |
| `export/patient_output.py` | One-hot patient rows + missing-information rows |
| `export/review_output.py` | Manual-review table |
| `io/output_writer.py` | Writes the four output files |
| `run_pipeline.py` | CLI + startup banner |

Shared, task-agnostic roots live in `src/pipeline/paths.py`.

## Data flow types

- `LoadedData(df, summary, ...)` -- normalized DataFrame with internal
  annotation columns (`_source_row_index`, `_patnr_str`, `_p_dat_parsed`,
  `_date_parse_ok`, `_row_status`).
- `PatientRecord` -- one per patient: usable `ReportEntry` list (chronological),
  counts, source rows, `latest_p_dat`, `context_text`, `context_truncated`.
- `TumorParseResult` -- parser output with status + resolved category.
- `PatientResult` -- final per-patient record persisted to the progress JSONL and
  rendered into all output files.

## Design choices

- **Single-stage classification.** The model returns one canonical category, not
  38 independent booleans; the one-hot expansion happens deterministically in
  `export/patient_output.py`.
- **Never drop a patient.** Every input patient appears in the output; missing
  information is an explicit state, never a silent drop or a negative label.
- **Deterministic vocabulary.** Category resolution and column mapping are pure
  functions in one module, so the prompt and the output schema cannot drift.
- **Crash-safe.** Each patient result is appended to a JSONL progress file as it
  completes; `--resume` continues without re-classifying finished patients.
