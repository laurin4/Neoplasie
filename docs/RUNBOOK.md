# Runbook

Operational guide for running the tumor histopathology pipeline.

## 1. Setup

```bash
python3 -m venv tumor_venv
source tumor_venv/bin/activate
pip install -r requirements.txt
python3 -m pytest tests        # sanity check (synthetic only)
```

Offline Ubuntu: build wheels once with `scripts/build_wheelhouse_linux.sh`, then
`pip install --no-index --find-links wheelhouse_linux -r requirements.txt`.

## 2. Configure the LLM

Set the provider and endpoint (defaults target a local USZ API):

```bash
export TUMOR_HISTOLOGY_LLM_PROVIDER=usz_api
export TUMOR_HISTOLOGY_USZ_LLM_URL=http://localhost:8100/generate
```

For a local Ollama model:

```bash
export TUMOR_HISTOLOGY_LLM_PROVIDER=ollama
export TUMOR_HISTOLOGY_OLLAMA_URL=http://127.0.0.1:11500
export TUMOR_HISTOLOGY_OLLAMA_MODEL=qwen2.5:7b
```

Verify connectivity: `python3 scripts/test_usz_llm_api.py`.

## 3. Place the input

Copy the KISIM export to `data/raw/` (git-ignored). Or generate a synthetic
demo file:

```bash
python3 scripts/generate_synthetic_tumor_data.py --out data/raw/synthetic_tumor_input.xlsx
```

## 4. Inspect before running

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --dry-run
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --prompt-preview --patient-id <patnr>
```

The dry run prints the dataset summary (rows, patients, usable/missing) and the
resolved output paths without calling the LLM.

## 5. Pilot run

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --limit 20
```

Review `data/outputs/tumor_histopathology_review.csv` before scaling up.

## 6. Full run

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx
```

Results stream to `tumor_histopathology_progress.jsonl` as each patient finishes.

## 7. Resume an interrupted run

```bash
python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/<export>.xlsx --resume
```

Completed patients are skipped. To start over, add `--overwrite`.

## 8. Review workflow

1. Open `tumor_histopathology_review.csv` (rows needing review sorted first).
2. Prioritize `manual_review_required = 1`: low certainty, multiple diagnoses,
   `AndereCB`/`Andere`, parser repairs, truncated context, unsupported category,
   or failed/uncertain status.
3. Cross-check `tumor_histopathology_missing_information.csv` -- these patients
   need an alternative data source.
4. The one-hot `12_*` columns live in `tumor_histopathology_patient_predictions.xlsx`.

## 9. Troubleshooting

| Symptom | Action |
|---------|--------|
| `Missing required column(s)` | Ensure the sheet has `patnr` and `p_kom`; set `--sheet` if needed |
| Many `llm_failed` | Check endpoint/URL and `TUMOR_HISTOLOGY_LLM_TIMEOUT_SECONDS` |
| Many `parse_failed` | Inspect `raw_response` in the progress JSONL; consider lowering temperature |
| Dates not parsed | Confirm `p_dat` format; ISO and `DD.MM.YYYY` are supported |
| Broken venv after moving the repo | Recreate the venv (step 1); venvs are not relocatable |

## 10. Before committing

```bash
python3 scripts/check_no_sensitive_files.py
git status
```

Never commit files under `data/raw/`, generated outputs, `.env`, or any
patient-identifiable content.
