# Clinical classification rules

Authoritative rules from the clinical supervisor. The model classifies the
**current / final** neuro-oncological histopathology diagnosis for the patient.

## Core rules

1. **One final tumor classification per patient** in the registry.
2. A patient changing classification is rare.
3. On uncertainty or progression over time, **prefer the later diagnosis**.
   - earlier: `Gliom`
   - later: `Glioblastom`
   - final class: **Glioblastom**
4. Historical diagnoses mentioned only as comparison or origin must **not** be
   classified.
5. Metastasis example:
   - current report: metastasis
   - report compares it with an ampullary adenocarcinoma from 2007
   - final classification: **Metastase** only
   - do **not** classify the historical adenocarcinoma
6. Full patient context is preferred when it improves classification.
7. Patients with no usable tumor information must be **clearly marked** so
   another data source can be used later.

## Diagnostic distinctions the system tracks

- confirmed / current tumor diagnosis
- historical diagnosis
- differential diagnosis or suspicion (`V. a.`)
- excluded / negated diagnosis
- insufficient information
- no pathology text available

The final tumor class is based on the current / latest supported diagnosis, not
on every tumor term mentioned in the text.

## How the rules are enforced

- **Prompt** (`prompts/tumor_histopathology_classification.txt`) states all rules
  explicitly, including the two worked examples, and restricts output to the
  controlled vocabulary.
- **Parser** (`inference/parse.py`) maps outcomes to the status taxonomy:
  - `tumor_information_available = false` -> `no_tumor_information`
  - multiple final categories -> `uncertain` (never a silent pick)
  - text present but no resolvable category -> `uncertain`
  - out-of-vocabulary category -> `unsupported_category`
- **Manual review** (`inference/runner.py`) is required when: certainty is low,
  multiple current diagnoses, category is `AndereCB`/`Andere`, parser repairs
  were applied, context was truncated, category unsupported, or the status is
  `uncertain` / `parse_failed` / `llm_failed`.

## Missing information

Missing tumor information is **not** a negative classification. Such patients
are retained in all outputs, marked `Keine_Tumorinformation = 1`, and listed in
`tumor_histopathology_missing_information.csv`.

## Unresolved ambiguity: `AndereCB` vs `Andere`

The registry template contains both `12_AndereCB` and `12_Andere`. The semantic
distinction is **not documented** anywhere authoritative in this repository, and
no clinical definition has been invented.

- Both are preserved as valid target categories.
- Any patient assigned to either is flagged for manual review.
- Action required: obtain an authoritative definition from the clinical owners
  and record it here, then (if needed) refine `CATEGORY_SYNONYMS` /
  `CATEGORY_DISPLAY` in `constants.py`.

## Not clinically validated

This is LLM-based decision support. It is **not** a validated diagnostic device
and its output must be reviewed by qualified clinical staff.
