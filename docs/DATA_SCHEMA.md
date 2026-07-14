# Data schema

## Input (KISIM Excel export)

| Column | Required | Notes |
|--------|----------|-------|
| `patnr` | yes | Patient id; preserved as string (`12345.0` -> `12345`) |
| `p_kom` | yes | Free-text pathology report; empty/whitespace/NaN = missing |
| `p_dat` | no | Report timestamp; ISO (`YYYY-MM-DD`) and European (`DD.MM.YYYY`) accepted |
| `p_nr`, `p_fnr` | no | Pathology reference numbers (kept as context) |
| `p_name` | no | Report/document name |
| `lst_fnr`, `anz_op`, `min_opdat`, `max_opdat` | no | Additional context |

Multiple rows per patient are expected. Column names are normalized
case-insensitively; unknown columns are kept (never silently dropped).

### Row-level quality status

- `usable` -- `p_kom` has content.
- `missing_text` -- `p_kom` empty / whitespace / NaN.

### Dataset summary (printed at startup)

total rows, unique patients, rows with/without pathology text, patients with/
without a usable report, date-parse failures, duplicate rows.

## Classification status taxonomy

| Status | Meaning |
|--------|---------|
| `success` | One valid tumor category assigned |
| `no_tumor_information` | No usable report, or model reports none available |
| `parse_failed` | LLM output could not be parsed into valid JSON |
| `llm_failed` | LLM call failed after retries |
| `unsupported_category` | Model returned a category outside the vocabulary |
| `uncertain` | Multiple current diagnoses, or text present but no definitive category |
| `llm_disabled` | Run mode `--no-llm` (plumbing only; not a clinical outcome) |

## Patient-level output (`tumor_histopathology_patient_predictions.xlsx`/`.csv`)

Metadata columns, then the missing-info marker, then the 38 tumor columns:

`patnr, latest_p_dat, report_count, usable_report_count, source_row_indices,
classification_status, predicted_tumor_category, predicted_output_column,
certainty, reasoning, evidence_summary, historical_diagnoses_summary,
no_tumor_information, parse_failed, llm_failed, context_truncated,
manual_review_required, Keine_Tumorinformation, 12_AstrocytomGradII ... 12_Andere`

Rules:

- Exactly one `12_*` column is `1` for `success` patients; all other tumor
  columns are blank.
- `no_tumor_information` patients have `Keine_Tumorinformation = 1` and no tumor
  column set. They are **kept**, never dropped.
- `latest_p_dat` is the most recent usable report date for the patient.

### Template compatibility

`io/schema.py::template_output_columns()` provides the registry template order
(`patnr, p_dat, p_kom, 12_*`). The patient predictions file uses the richer
layout above; the trailing 38 tumor columns match the template order exactly.

## Controlled vocabulary (38 categories)

Canonical label -> Excel column, e.g. `glioblastom -> 12_Glioblastom`. Full map
and synonyms in `src/tasks/tumor_histopathology/constants.py`. `andere_cb` and
`andere` are catch-all categories flagged as ambiguous.

## Missing-information output (`tumor_histopathology_missing_information.csv`)

`patnr, report_count, usable_report_count, latest_p_dat, classification_status, note`

## Review output (`tumor_histopathology_review.csv`)

`patnr, predicted_tumor_category, predicted_output_column, certainty,
latest_report_date, classification_status, reasoning, supporting_excerpts,
historical_diagnoses_mentioned, all_report_dates, manual_review_required,
manual_review_reasons`

Sorted so rows requiring manual review appear first.

## LLM JSON schema

```json
{
  "tumor_information_available": true,
  "current_tumor_category": "",
  "certainty": "low | medium | high",
  "reasoning": "",
  "supporting_evidence": [
    {"report_date": "", "text_excerpt": "", "interpretation": ""}
  ],
  "historical_diagnoses_mentioned": [
    {"diagnosis": "", "report_date": "", "reason_not_selected": ""}
  ],
  "uncertainty_reasons": []
}
```
