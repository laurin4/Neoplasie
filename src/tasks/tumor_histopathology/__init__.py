"""Tumor histopathology classification task.

Reads a KISIM pathology Excel export (multiple rows per patient), aggregates
all pathology reports per patient, and assigns exactly one final
neuro-oncological tumor category per patient using a single-stage LLM
classification. See ``docs/ARCHITECTURE.md`` and ``docs/CLINICAL_RULES.md``.
"""
