"""Controlled vocabulary and output schema for tumor histopathology.

Single source of truth. Everything about tumor categories -- the canonical
labels, their Excel output columns, and the accepted synonym/spelling variants
-- lives here. Do NOT scatter label mappings across other modules.

The target output columns and their order are taken verbatim from the NCH
registry template supplied in the project brief. There are 38 tumor-category
columns (the ``12_*`` columns).

Ambiguity note (see docs/CLINICAL_RULES.md): the semantic distinction between
``12_AndereCB`` and ``12_Andere`` is NOT documented anywhere authoritative in
this repository. Both are preserved as valid targets and any patient assigned
to either is flagged for manual review. No clinical definition is invented.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Patient / report input columns carried through to outputs (from template).
# ---------------------------------------------------------------------------
COL_PATNR = "patnr"
COL_P_DAT = "p_dat"
COL_P_KOM = "p_kom"

# Full set of input columns we expect from the KISIM export (some optional).
EXPECTED_INPUT_COLUMNS: Tuple[str, ...] = (
    "patnr",
    "lst_fnr",
    "anz_op",
    "min_opdat",
    "max_opdat",
    "p_nr",
    "p_fnr",
    "p_dat",
    "p_name",
    "p_kom",
)

# Only these are strictly required for the pipeline to run.
REQUIRED_INPUT_COLUMNS: Tuple[str, ...] = (COL_PATNR, COL_P_KOM)

# Marker column for patients with no usable tumor information.
COL_KEINE_TUMORINFORMATION = "Keine_Tumorinformation"


# ---------------------------------------------------------------------------
# Canonical categories -> Excel output column (ordered).
# The ORDER of this dict defines the output column order.
# ---------------------------------------------------------------------------
TUMOR_CATEGORY_TO_COLUMN: Dict[str, str] = {
    "astrocytom_grad_ii": "12_AstrocytomGradII",
    "anaplastisches_astrozytom": "12_AnaplastischesAstrozytom",
    "glioblastom": "12_Glioblastom",
    "gliosarkom": "12_Gliosarkom",
    "pilozytisches_astrocytom": "12_PilozytischesAstrocytom",
    "pleomorphes_xanthoastrocytom": "12_PleomorphesXanthoastrocytom",
    "subependymales_riesenzellastrozytom": "12_SubependymalesRiesenzellastrozytom",
    "oligodendrogliom": "12_Oligodendrogliom",
    "ependymom": "12_Ependymom",
    "anaplastisches_ependymom": "12_AnaplastischesEpendymom",
    "oligoastrozytom": "12_Oligoastrozytom",
    "plexuspapillom": "12_Plexuspapillom",
    "gangliocytom": "12_Gangliocytom",
    "pineocytom": "12_Pineocytom",
    "pineoblastom": "12_Pineoblastom",
    "neuroblastom": "12_Neuroblastom",
    "pnet": "12_PNET",
    "meningeom": "12_Meningeom",
    "atypisches_meningeom": "12_AtypischesMeningeom",
    "anaplastisches_meningeom": "12_AnaplastischesMeningeom",
    "metastase": "12_Metastase",
    "schwannom": "12_Schwannom",
    "neurofibrom": "12_Neurofibrom",
    "nervenscheidentumor": "12_Nervenscheidentumor",
    "lymphom": "12_Lymphom",
    "plasmozytom": "12_Plasmozytom",
    "germinom": "12_Germinom",
    "embryonales_carcinom": "12_EmbryonalesCarcinom",
    "coriocarcinom": "12_Coriocarcinom",
    "teratom": "12_Teratom",
    "tasche_cyste": "12_TascheCyste",
    "epidermoidcyste": "12_Epidermoidcyste",
    "dermoidcyste": "12_Dermoidcyste",
    "kolloidcyste": "12_Kolloidcyste",
    "hypophysenadenom": "12_Hypophysenadenom",
    "kraniopharyngeom": "12_Kraniopharyngeom",
    "andere_cb": "12_AndereCB",
    "andere": "12_Andere",
}

# Ordered lists derived from the mapping above.
CANONICAL_CATEGORIES: List[str] = list(TUMOR_CATEGORY_TO_COLUMN.keys())
TARGET_COLUMNS: List[str] = list(TUMOR_CATEGORY_TO_COLUMN.values())
COLUMN_TO_CATEGORY: Dict[str, str] = {v: k for k, v in TUMOR_CATEGORY_TO_COLUMN.items()}

# Categories whose meaning is undefined / catch-all: always route to review.
AMBIGUOUS_CATEGORIES = frozenset({"andere_cb", "andere"})


# ---------------------------------------------------------------------------
# Human-readable German display names (for prompt vocabulary + review output).
# ---------------------------------------------------------------------------
CATEGORY_DISPLAY: Dict[str, str] = {
    "astrocytom_grad_ii": "Astrozytom Grad II",
    "anaplastisches_astrozytom": "Anaplastisches Astrozytom (Grad III)",
    "glioblastom": "Glioblastom (Grad IV)",
    "gliosarkom": "Gliosarkom",
    "pilozytisches_astrocytom": "Pilozytisches Astrozytom",
    "pleomorphes_xanthoastrocytom": "Pleomorphes Xanthoastrozytom",
    "subependymales_riesenzellastrozytom": "Subependymales Riesenzellastrozytom (SEGA)",
    "oligodendrogliom": "Oligodendrogliom",
    "ependymom": "Ependymom",
    "anaplastisches_ependymom": "Anaplastisches Ependymom",
    "oligoastrozytom": "Oligoastrozytom",
    "plexuspapillom": "Plexuspapillom",
    "gangliocytom": "Gangliozytom",
    "pineocytom": "Pineozytom",
    "pineoblastom": "Pineoblastom",
    "neuroblastom": "Neuroblastom",
    "pnet": "PNET (primitiver neuroektodermaler Tumor; inkl. Medulloblastom)",
    "meningeom": "Meningeom (Grad I)",
    "atypisches_meningeom": "Atypisches Meningeom (Grad II)",
    "anaplastisches_meningeom": "Anaplastisches/malignes Meningeom (Grad III)",
    "metastase": "Metastase",
    "schwannom": "Schwannom / Neurinom",
    "neurofibrom": "Neurofibrom",
    "nervenscheidentumor": "Maligner peripherer Nervenscheidentumor (MPNST)",
    "lymphom": "Lymphom (z. B. primäres ZNS-Lymphom)",
    "plasmozytom": "Plasmozytom",
    "germinom": "Germinom",
    "embryonales_carcinom": "Embryonales Karzinom",
    "coriocarcinom": "Choriokarzinom",
    "teratom": "Teratom",
    "tasche_cyste": "Rathke-Taschenzyste",
    "epidermoidcyste": "Epidermoidzyste",
    "dermoidcyste": "Dermoidzyste",
    "kolloidcyste": "Kolloidzyste",
    "hypophysenadenom": "Hypophysenadenom",
    "kraniopharyngeom": "Kraniopharyngeom",
    "andere_cb": "Andere (CB) - Bedeutung im Repository nicht dokumentiert",
    "andere": "Andere - nicht anderweitig klassifizierbar",
}


# ---------------------------------------------------------------------------
# Synonyms / spelling / language / WHO variants -> canonical category.
# Values are matched after normalization (see normalize_key).
# Only map to a neuro-oncological category when the term IS that category.
# Extracranial primaries are intentionally NOT mapped to a neuro category.
# ---------------------------------------------------------------------------
CATEGORY_SYNONYMS: Dict[str, List[str]] = {
    "astrocytom_grad_ii": [
        "astrocytom grad ii", "astrozytom grad ii", "astrozytom grad 2",
        "diffuses astrozytom", "diffuse astrocytoma", "low grade astrocytoma",
        "astrocytoma grade ii", "astrozytom who grad ii", "diffuses gliom grad ii",
    ],
    "anaplastisches_astrozytom": [
        "anaplastisches astrozytom", "anaplastic astrocytoma",
        "astrozytom grad iii", "astrocytoma grade iii", "astrozytom who grad iii",
    ],
    "glioblastom": [
        "glioblastom", "glioblastoma", "glioblastoma multiforme",
        "glioblastoma multiplex", "gbm", "glioblastom grad iv",
        "glioblastoma grade iv", "glioblastom idh wildtyp", "glioblastom idh wildtyp grad iv",
    ],
    "gliosarkom": ["gliosarkom", "gliosarcoma"],
    "pilozytisches_astrocytom": [
        "pilozytisches astrozytom", "pilozytisches astrocytom",
        "pilocytic astrocytoma", "juveniles pilozytisches astrozytom",
    ],
    "pleomorphes_xanthoastrocytom": [
        "pleomorphes xanthoastrozytom", "pleomorphes xanthoastrocytom",
        "pleomorphic xanthoastrocytoma", "pxa",
    ],
    "subependymales_riesenzellastrozytom": [
        "subependymales riesenzellastrozytom", "subependymal giant cell astrocytoma",
        "sega", "riesenzellastrozytom",
    ],
    "oligodendrogliom": [
        "oligodendrogliom", "oligodendroglioma", "oligodendrogliom idh mutiert",
    ],
    "ependymom": ["ependymom", "ependymoma"],
    "anaplastisches_ependymom": [
        "anaplastisches ependymom", "anaplastic ependymoma", "ependymom grad iii",
    ],
    "oligoastrozytom": [
        "oligoastrozytom", "oligoastrocytoma", "mischgliom", "oligoastrozytom mischgliom",
    ],
    "plexuspapillom": [
        "plexuspapillom", "choroid plexus papilloma", "plexus papillom",
        "papillom des plexus choroideus",
    ],
    "gangliocytom": ["gangliozytom", "gangliocytom", "gangliocytoma", "gangliocytoma zns"],
    "pineocytom": ["pineozytom", "pineocytom", "pineocytoma"],
    "pineoblastom": ["pineoblastom", "pineoblastoma"],
    "neuroblastom": ["neuroblastom", "neuroblastoma", "zns neuroblastom"],
    "pnet": [
        "pnet", "primitiver neuroektodermaler tumor",
        "primitive neuroectodermal tumor", "primitiv neuroektodermaler tumor",
        # Clinical supervisor (2026-07): Medulloblastom is a special form of PNET.
        "medulloblastom", "medulloblastoma", "medullo blastom",
        "medulloblastom who", "embryonaler tumor medulloblastom",
    ],
    "meningeom": [
        "meningeom", "meningioma", "meningeom grad i", "meningioma grade i",
        "meningeom who grad i",
    ],
    "atypisches_meningeom": [
        "atypisches meningeom", "atypical meningioma", "meningeom grad ii",
        "meningioma grade ii", "meningeom who grad ii",
    ],
    "anaplastisches_meningeom": [
        "anaplastisches meningeom", "anaplastic meningioma", "malignes meningeom",
        "meningeom grad iii", "meningioma grade iii", "meningeom who grad iii",
    ],
    "metastase": [
        "metastase", "metastasis", "metastasen", "hirnmetastase", "hirnmetastasen",
        "zerebrale metastase", "cerebral metastasis", "brain metastasis",
        "zns metastase", "filia", "filiae", "metastatischer tumor",
        "metastase eines karzinoms", "metastasis of carcinoma",
    ],
    "schwannom": [
        "schwannom", "schwannoma", "neurinom", "akustikusneurinom",
        "vestibularisschwannom", "vestibular schwannoma", "acoustic neuroma",
        "vestibularis schwannom", "n viii schwannom",
    ],
    "neurofibrom": ["neurofibrom", "neurofibroma"],
    "nervenscheidentumor": [
        "nervenscheidentumor", "maligner peripherer nervenscheidentumor",
        "malignant peripheral nerve sheath tumor", "mpnst",
        "peripherer nervenscheidentumor",
    ],
    "lymphom": [
        "lymphom", "lymphoma", "zns lymphom", "primaeres zns lymphom",
        "primary cns lymphoma", "pcnsl", "b zell lymphom", "malignes lymphom",
    ],
    "plasmozytom": ["plasmozytom", "plasmacytoma", "plasmozytom myelom", "solitaeres plasmozytom"],
    "germinom": ["germinom", "germinoma", "keimzelltumor germinom"],
    "embryonales_carcinom": ["embryonales karzinom", "embryonales carcinom", "embryonal carcinoma"],
    "coriocarcinom": ["choriokarzinom", "coriocarcinom", "choriocarcinoma", "chorionkarzinom"],
    "teratom": ["teratom", "teratoma", "reifes teratom", "unreifes teratom"],
    "tasche_cyste": [
        "rathke", "rathke tasche", "rathke taschenzyste", "rathke cleft cyst",
        "taschenzyste", "tasche cyste", "rathke zyste",
    ],
    "epidermoidcyste": ["epidermoidzyste", "epidermoidcyste", "epidermoid cyst", "epidermoid", "epidermoidtumor"],
    "dermoidcyste": ["dermoidzyste", "dermoidcyste", "dermoid cyst", "dermoid"],
    "kolloidcyste": ["kolloidzyste", "kolloidcyste", "colloid cyst"],
    "hypophysenadenom": [
        "hypophysenadenom", "pituitary adenoma", "adenom der hypophyse",
        "hypophysen adenom", "hypophysentumor adenom",
    ],
    "kraniopharyngeom": ["kraniopharyngeom", "craniopharyngioma", "kraniopharyngiom"],
    "andere_cb": ["andere cb", "anderecb"],
    "andere": ["andere", "sonstige", "other", "nicht klassifizierbar"],
}


def normalize_key(value: object) -> str:
    """Normalize a label/term to an ascii snake_case key.

    Folds German umlauts (ä->ae, ö->oe, ü->ue, ß->ss), lowercases, converts
    whitespace/hyphens to underscores, and strips remaining non-alphanumerics.
    This is the shared normalization used both to build the synonym lookup and
    to resolve model output labels.
    """
    if value is None:
        return ""
    s = str(value).strip().lower()
    if not s or s in ("nan", "none", "null", "na", "<na>"):
        return ""
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    # Drop any remaining diacritics.
    s = "".join(
        ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
    )
    s = re.sub(r"[\s\-/]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _build_synonym_index() -> Dict[str, str]:
    """Map normalized-variant -> canonical category (canonical keys included)."""
    index: Dict[str, str] = {}
    # Canonical keys always resolve to themselves.
    for canonical in CANONICAL_CATEGORIES:
        index[normalize_key(canonical)] = canonical
        index[normalize_key(CATEGORY_DISPLAY.get(canonical, canonical))] = canonical
    # Then synonyms (do not overwrite an existing canonical self-mapping).
    for canonical, variants in CATEGORY_SYNONYMS.items():
        for variant in variants:
            key = normalize_key(variant)
            if key and key not in index:
                index[key] = canonical
    return index


_SYNONYM_INDEX: Dict[str, str] = _build_synonym_index()


def resolve_category(raw: object) -> Optional[str]:
    """Resolve a raw model label to a canonical category, or ``None``.

    Tries: exact normalized match, then a longest-substring fallback so that
    e.g. "wahrscheinlich glioblastom idh-wildtyp" still resolves to
    ``glioblastom`` when no exact key matches.
    """
    key = normalize_key(raw)
    if not key:
        return None
    if key in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[key]

    # Substring fallback: pick the longest known variant contained in the key.
    best: Optional[str] = None
    best_len = 0
    for variant_key, canonical in _SYNONYM_INDEX.items():
        if len(variant_key) < 4:
            continue
        if variant_key in key and len(variant_key) > best_len:
            best = canonical
            best_len = len(variant_key)
    return best


def category_column(category: Optional[str]) -> Optional[str]:
    """Return the Excel output column for a canonical category, or ``None``."""
    if not category:
        return None
    return TUMOR_CATEGORY_TO_COLUMN.get(category)


def is_valid_category(category: Optional[str]) -> bool:
    return bool(category) and category in TUMOR_CATEGORY_TO_COLUMN
