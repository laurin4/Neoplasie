# NCH Neoplasie -- Tumor Histopathology Classification

Extract and classify the **final neuro-oncological tumor diagnosis per patient**
from KISIM pathology report exports.

The pipeline reads an Excel export with (potentially) multiple pathology entries
per patient, aggregates all reports for each patient, and uses a single-stage
LLM classification to assign **exactly one** final tumor category per patient.
Patients without usable tumor information are clearly marked so another data
source can be used later.

> Privacy: This project processes clinical pathology text. **Never commit real
> patient data.** All committed fixtures and tests use synthetic data only. See
> [Privacy](#privacy).

## Clinical target

- One final tumor classification per patient (registry semantics).
- Prefer the **later / current** diagnosis when a diagnosis changes over time
  (e.g. earlier `Gliom` -> later `Glioblastom` -> classify **Glioblastom**).
- Historical diagnoses mentioned only for comparison/origin are **not** selected
  (e.g. current `Metastase` compared with a 2007 adenocarcinoma ->
  classify **Metastase** only).
- Missing tumor information is **not** the same as a negative classification.

Full rules: [docs/CLINICAL_RULES.md](docs/CLINICAL_RULES.md).

## Input schema

A KISIM Excel export with (at least) these columns:

| Column | Meaning |
|--------|---------|
| `patnr` | Patient identifier (kept as string) |
| `p_dat` | Pathology report timestamp |
| `p_kom` | Free-text pathology report |
| `p_nr`, `p_fnr`, `p_name`, `lst_fnr`, `anz_op`, `min_opdat`, `max_opdat` | Additional context (optional) |

Only `patnr` and `p_kom` are strictly required. Multiple rows per patient are
expected; some `p_kom` values may be empty. Details:
[docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md).

## Patient-level aggregation

All rows for a patient are grouped by `patnr`, usable reports are sorted
chronologically by `p_dat`, and a single `PATIENT CONTEXT` block is built for the
model. Context length is bounded (`TUMOR_HISTOLOGY_MAX_CONTEXT_CHARS`); when
truncation is needed the **most recent** reports are retained and the truncation
is recorded. Patients with zero usable reports bypass the LLM entirely and are
marked `no_tumor_information`.

## Controlled vocabulary

A single authoritative mapping (`src/tasks/tumor_histopathology/constants.py`)
maps canonical category labels to the 38 `12_*` Excel output columns and covers
synonym / spelling / umlaut / German-English / WHO variants (e.g.
`glioblastoma multiforme -> glioblastom`, `vestibular schwannoma -> schwannom`,
`Hirnmetastase -> metastase`). Extracranial primary cancers are **not**
auto-mapped to a neuro-oncological category.

## Installation

Developer machine (with internet):

```bash
python3 -m venv tumor_venv
source tumor_venv/bin/activate
pip install -r requirements.txt
```

Air-gapped server (offline, Linux x86_64, Python 3.12) — dependency wheels are
committed under `wheelhouse/`:

```bash
python3 -m venv tumor_venv
source tumor_venv/bin/activate
pip install --no-index --find-links=wheelhouse -r requirements.txt
```

The venv is never committed (machine-specific, not relocatable). Rebuild the
wheelhouse after changing `requirements.txt` with `scripts/build_wheelhouse.sh`.
See `docs/RUNBOOK.md` for details.

## Configuration

All environment variables use the `TUMOR_HISTOLOGY_` prefix and have safe
defaults (generic fallbacks in parentheses):

| Variable | Default | Purpose |
|----------|---------|---------|
| `TUMOR_HISTOLOGY_LLM_PROVIDER` (`LLM_PROVIDER`) | `usz_api` | `usz_api` or `ollama` |
| `TUMOR_HISTOLOGY_USZ_LLM_URL` (`USZ_LLM_URL`) | `http://localhost:8100/generate` | USZ endpoint |
| `TUMOR_HISTOLOGY_OLLAMA_URL` / `_OLLAMA_MODEL` | `http://127.0.0.1:11500` / `qwen2.5:7b` | Ollama fallback |
| `TUMOR_HISTOLOGY_LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `TUMOR_HISTOLOGY_LLM_MAX_TOKENS` | `1200` | Max output tokens |
| `TUMOR_HISTOLOGY_LLM_TIMEOUT_SECONDS` | `240` | Request timeout |
| `TUMOR_HISTOLOGY_LLM_MAX_RETRIES` | `1` | Transient-error retries |
| `TUMOR_HISTOLOGY_INPUT_PATH` | `data/raw/tumor_histopathology_input.xlsx` | Default input |
| `TUMOR_HISTOLOGY_OUTPUT_DIR` | `data/outputs` | Output directory |
| `TUMOR_HISTOLOGY_SHEET` | first sheet | Worksheet name |
| `TUMOR_HISTOLOGY_MAX_CONTEXT_CHARS` | `24000` | Max context characters |

No secrets are read from the environment and none may be committed.

## Commands

Generate a synthetic demo input (no real data required):

```bash
python3 scripts/generate_synthetic_tumor_data.py --out data/raw/synthetic_tumor_input.xlsx
```

Inspect the data and prompt without classifying:

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/synthetic_tumor_input.xlsx --dry-run
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/synthetic_tumor_input.xlsx --prompt-preview
```

Pilot run (first 20 patients):

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --limit 20
```

Full run (resumable):

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --resume
```

Useful flags: `--sheet`, `--output`, `--limit`, `--patient-id`, `--dry-run`,
`--resume`, `--overwrite`, `--no-llm`, `--prompt-preview`.

## Output files

Written to `data/outputs/` (see [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md)):

- `tumor_histopathology_patient_predictions.xlsx` / `.csv` -- one row per patient,
  one-hot `12_*` tumor column, plus `Keine_Tumorinformation` for missing-info patients.
- `tumor_histopathology_missing_information.csv` -- patients without usable tumor text.
- `tumor_histopathology_review.csv` -- manual-review-focused table.
- `tumor_histopathology_progress.jsonl` -- incremental progress store (enables `--resume`).

## Tests

```bash
python3 -m pytest tests
```

All tests use synthetic data and a stubbed LLM (no network, no real data).

## Privacy

- Real raw data, generated patient-level outputs, `.env`, Excel/CSV files,
  caches, virtualenvs and logs are git-ignored.
- `scripts/check_no_sensitive_files.py` blocks accidental staging of sensitive
  paths -- run it before committing.

## Known limitations

- The distinction between `12_AndereCB` and `12_Andere` is **not documented**
  in this repository; both are preserved and any patient assigned to either is
  flagged for manual review. See [docs/CLINICAL_RULES.md](docs/CLINICAL_RULES.md).
- The classification is LLM-based and **not clinically validated**. Outputs are
  a decision-support draft requiring human review.
- The real NCH registry Excel template is not included; column order follows the
  project specification.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) -- pipeline stages, modules, data flow
- [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) -- input/output columns, statuses, vocabulary
- [docs/CLINICAL_RULES.md](docs/CLINICAL_RULES.md) -- classification rules
- [docs/RUNBOOK.md](docs/RUNBOOK.md) -- setup, runs, resume, review, troubleshooting
