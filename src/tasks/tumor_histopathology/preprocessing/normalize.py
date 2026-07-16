"""Safe normalization helpers for KISIM pathology inputs.

Handles column-name normalization, string-preserving patient identifiers,
tolerant date parsing, and missing-text detection. Nothing here drops rows.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

import pandas as pd

from src.tasks.tumor_histopathology.constants import EXPECTED_INPUT_COLUMNS


def _norm_header(name: object) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


# Map of normalized header -> canonical expected column name.
_CANONICAL_BY_NORM = {_norm_header(c): c for c in EXPECTED_INPUT_COLUMNS}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename recognized headers to canonical names; leave unknowns as-is.

    Non-destructive: unknown columns are kept (normalized to lowercase/underscore)
    so nothing is silently lost.
    """
    rename = {}
    for col in df.columns:
        norm = _norm_header(col)
        rename[col] = _CANONICAL_BY_NORM.get(norm, norm)
    out = df.rename(columns=rename)
    # If duplicate canonical names result, keep the first occurrence's data.
    out = out.loc[:, ~out.columns.duplicated()]
    return out


def to_str_id(value: object) -> str:
    """Convert an identifier to a clean string, preserving it as text.

    Handles Excel's habit of reading integer IDs as floats (e.g. ``12345.0``)
    by stripping a trailing ``.0`` while never touching genuinely non-numeric IDs.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value)
    s = str(value).strip()
    if s.lower() in ("nan", "none", "<na>", "null"):
        return ""
    # "12345.0" -> "12345" (only for pure numeric-with-trailing-zero strings).
    m = re.fullmatch(r"(\d+)\.0+", s)
    if m:
        return m.group(1)
    return s


# Markers after which a pathology report degenerates into a gene-panel coverage
# list (accession numbers, gene symbols, "Hotspot, Exon ..." lines). Everything
# from the first marker onward is non-diagnostic boilerplate and is cut before
# the text reaches the LLM. Matched case-insensitively.
REFERENCE_CUT_MARKERS: Tuple[str, ...] = (
    "Untersuchte Genabschnitte",
)


def strip_reference_section(
    value: object, markers: Tuple[str, ...] = REFERENCE_CUT_MARKERS
) -> str:
    """Return report text with any trailing gene-panel reference section removed.

    Cuts everything from the first occurrence of a known marker (e.g.
    ``"Untersuchte Genabschnitte"``) onward, preserving the diagnostic prose that
    precedes it. Returns the text unchanged if no marker is present.
    """
    if value is None:
        return ""
    text = str(value)
    lowered = text.lower()
    cut: Optional[int] = None
    for marker in markers:
        idx = lowered.find(marker.lower())
        if idx != -1:
            cut = idx if cut is None else min(cut, idx)
    if cut is None:
        return text
    return text[:cut].rstrip()


def is_missing_text(value: object) -> bool:
    """True if the pathology text is missing (NaN, empty, or whitespace-only)."""
    if value is None:
        return True
    try:
        if isinstance(value, float) and pd.isna(value):
            return True
    except TypeError:
        pass
    if value is pd.NaT:
        return True
    s = str(value).strip()
    return s == "" or s.lower() in ("nan", "none", "<na>", "null")


def parse_date(value: object) -> Tuple[Optional[pd.Timestamp], bool]:
    """Parse a value into a Timestamp.

    Returns ``(timestamp_or_None, parse_ok)``. A genuinely empty value returns
    ``(None, True)`` (nothing to parse, not a failure); an unparseable non-empty
    value returns ``(None, False)`` (a parse failure to be counted).
    """
    if value is None or value is pd.NaT:
        return None, True
    if isinstance(value, float) and pd.isna(value):
        return None, True
    if isinstance(value, pd.Timestamp):
        return value, True

    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "<na>", "null"):
        return None, True

    # ISO-like dates (start with a 4-digit year) must NOT use dayfirst, which
    # would swap month/day. European formats (DD.MM.YYYY) do use dayfirst.
    iso_like = bool(re.match(r"^\d{4}[-/.]", s))
    ts = pd.to_datetime(s, errors="coerce", dayfirst=not iso_like)
    if pd.isna(ts):
        # Fallback: retry with the opposite dayfirst setting.
        ts = pd.to_datetime(s, errors="coerce", dayfirst=iso_like)
    if pd.isna(ts):
        return None, False
    return ts, True
