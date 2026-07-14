"""Controlled vocabulary + output schema tests (Phase 6, scenarios 10/14/15)."""

from __future__ import annotations

from src.tasks.tumor_histopathology import constants as c
from src.tasks.tumor_histopathology.io.schema import (
    patient_output_columns,
    template_output_columns,
)

EXPECTED_TARGET_COLUMNS = [
    "12_AstrocytomGradII",
    "12_AnaplastischesAstrozytom",
    "12_Glioblastom",
    "12_Gliosarkom",
    "12_PilozytischesAstrocytom",
    "12_PleomorphesXanthoastrocytom",
    "12_SubependymalesRiesenzellastrozytom",
    "12_Oligodendrogliom",
    "12_Ependymom",
    "12_AnaplastischesEpendymom",
    "12_Oligoastrozytom",
    "12_Plexuspapillom",
    "12_Gangliocytom",
    "12_Pineocytom",
    "12_Pineoblastom",
    "12_Neuroblastom",
    "12_PNET",
    "12_Meningeom",
    "12_AtypischesMeningeom",
    "12_AnaplastischesMeningeom",
    "12_Metastase",
    "12_Schwannom",
    "12_Neurofibrom",
    "12_Nervenscheidentumor",
    "12_Lymphom",
    "12_Plasmozytom",
    "12_Germinom",
    "12_EmbryonalesCarcinom",
    "12_Coriocarcinom",
    "12_Teratom",
    "12_TascheCyste",
    "12_Epidermoidcyste",
    "12_Dermoidcyste",
    "12_Kolloidcyste",
    "12_Hypophysenadenom",
    "12_Kraniopharyngeom",
    "12_AndereCB",
    "12_Andere",
]


def test_target_column_order_matches_template():
    assert c.TARGET_COLUMNS == EXPECTED_TARGET_COLUMNS


def test_every_category_maps_to_a_column():
    for cat in c.CANONICAL_CATEGORIES:
        assert c.category_column(cat) in c.TARGET_COLUMNS
    assert len(c.TUMOR_CATEGORY_TO_COLUMN) == len(EXPECTED_TARGET_COLUMNS)


def test_synonym_resolution_variants():
    assert c.resolve_category("Glioblastoma multiforme") == "glioblastom"
    assert c.resolve_category("GBM") == "glioblastom"
    assert c.resolve_category("vestibular schwannoma") == "schwannom"
    assert c.resolve_category("Akustikusneurinom") == "schwannom"
    assert c.resolve_category("meningioma") == "meningeom"
    assert c.resolve_category("Hirnmetastase") == "metastase"
    assert c.resolve_category("brain metastasis") == "metastase"


def test_extracranial_primary_not_mapped():
    # An extracranial primary must NOT auto-map to a neuro-oncological category.
    assert c.resolve_category("Pankreaskarzinom") is None
    assert c.resolve_category("ampulläres Adenokarzinom") is None


def test_andere_categories_are_ambiguous():
    assert "andere_cb" in c.AMBIGUOUS_CATEGORIES
    assert "andere" in c.AMBIGUOUS_CATEGORIES
    assert c.category_column("andere_cb") == "12_AndereCB"
    assert c.category_column("andere") == "12_Andere"


def test_output_column_layout():
    cols = patient_output_columns()
    assert cols[0] == "patnr"
    assert c.COL_KEINE_TUMORINFORMATION in cols
    # Tumor columns appear at the end in template order.
    assert cols[-len(EXPECTED_TARGET_COLUMNS):] == EXPECTED_TARGET_COLUMNS
    template = template_output_columns()
    assert template[:3] == ["patnr", "p_dat", "p_kom"]
