"""Aggregate pathology rows into one structured context per patient.

Groups rows by ``patnr``, orders usable pathology reports chronologically,
and builds a single ``PATIENT CONTEXT`` block per patient with a configurable
maximum length. When truncation is required the most recent reports are kept
and the truncation is recorded (never a blind one-sided cut).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.constants import COL_P_KOM
from src.tasks.tumor_histopathology.io.input_loader import (
    COL_DATE_PARSE_OK,
    COL_P_DAT_PARSED,
    COL_PATNR_STR,
    COL_ROW_INDEX,
    COL_ROW_STATUS,
)
from src.tasks.tumor_histopathology.io.schema import ROW_STATUS_USABLE
from src.tasks.tumor_histopathology.preprocessing.normalize import strip_reference_section


@dataclass
class ReportEntry:
    source_row_index: int
    date: Optional[pd.Timestamp]
    date_str: str
    p_nr: str
    p_fnr: str
    text: str


@dataclass
class PatientRecord:
    patnr: str
    reports: List[ReportEntry] = field(default_factory=list)  # usable, chronological
    report_count: int = 0
    usable_report_count: int = 0
    source_row_indices: List[int] = field(default_factory=list)
    all_report_dates: List[str] = field(default_factory=list)
    latest_p_dat: Optional[pd.Timestamp] = None
    context_text: str = ""
    context_truncated: bool = False
    dropped_report_count: int = 0

    @property
    def has_usable_reports(self) -> bool:
        return self.usable_report_count > 0


def _date_str(ts: Optional[pd.Timestamp]) -> str:
    if ts is None or ts is pd.NaT:
        return "unbekannt"
    try:
        return ts.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return str(ts)


def _cell_str(row: pd.Series, col: str) -> str:
    if col not in row.index:
        return ""
    val = row.get(col)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "<na>") else s


def _sort_key(entry: ReportEntry):
    # Dated reports first (ascending), undated last (by source row), all stable.
    if entry.date is not None and entry.date is not pd.NaT:
        return (0, entry.date, entry.source_row_index)
    return (1, pd.Timestamp.max, entry.source_row_index)


def build_patient_records(
    df: pd.DataFrame,
    *,
    max_context_chars: Optional[int] = None,
    strip_reference: bool = True,
) -> List[PatientRecord]:
    """Build one :class:`PatientRecord` per patient (order preserved by first row).

    When ``strip_reference`` is true (default), the trailing gene-panel coverage
    section of each report (from ``"Untersuchte Genabschnitte"`` onward) is
    removed before it enters the LLM context, cutting token-heavy boilerplate
    without losing the diagnostic prose.
    """
    if max_context_chars is None:
        max_context_chars = config.get_max_context_chars()

    records: List[PatientRecord] = []
    # Preserve first-appearance order of patients (stable, reproducible).
    seen: set[str] = set()
    ordered_ids: List[str] = []
    for pid in df[COL_PATNR_STR]:
        if pid not in seen:
            seen.add(pid)
            ordered_ids.append(pid)

    for pid in ordered_ids:
        sub = df[df[COL_PATNR_STR] == pid]
        rec = PatientRecord(patnr=pid, report_count=len(sub))
        rec.source_row_indices = [int(i) for i in sub[COL_ROW_INDEX].tolist()]

        usable = sub[sub[COL_ROW_STATUS] == ROW_STATUS_USABLE]
        entries: List[ReportEntry] = []
        dates: List[str] = []
        for _, row in usable.iterrows():
            ts = row.get(COL_P_DAT_PARSED)
            if isinstance(ts, float) and pd.isna(ts):
                ts = None
            text = _cell_str(row, COL_P_KOM)
            if strip_reference:
                stripped = strip_reference_section(text).strip()
                if stripped:  # never blank out a report entirely
                    text = stripped
            entry = ReportEntry(
                source_row_index=int(row[COL_ROW_INDEX]),
                date=ts if isinstance(ts, pd.Timestamp) else None,
                date_str=_date_str(ts if isinstance(ts, pd.Timestamp) else None),
                p_nr=_cell_str(row, "p_nr"),
                p_fnr=_cell_str(row, "p_fnr"),
                text=text,
            )
            entries.append(entry)
            dates.append(entry.date_str)

        entries.sort(key=_sort_key)
        rec.reports = entries
        rec.usable_report_count = len(entries)
        rec.all_report_dates = [e.date_str for e in entries]

        dated = [e.date for e in entries if e.date is not None]
        if dated:
            rec.latest_p_dat = max(dated)
        rec.context_text, rec.context_truncated, rec.dropped_report_count = _build_context(
            entries, max_context_chars
        )
        records.append(rec)

    return records


def _format_block(idx: int, entry: ReportEntry) -> str:
    lines = [f"[Report {idx}]", f"Date: {entry.date_str}", f"Source row: {entry.source_row_index}"]
    ref = []
    if entry.p_nr:
        ref.append(f"p_nr={entry.p_nr}")
    if entry.p_fnr:
        ref.append(f"p_fnr={entry.p_fnr}")
    if ref:
        lines.append("Reference: " + ", ".join(ref))
    lines.append("Text:")
    lines.append(entry.text)
    return "\n".join(lines)


def _build_context(
    entries: List[ReportEntry], max_chars: int
) -> tuple[str, bool, int]:
    """Return ``(context_text, truncated, dropped_count)``.

    Reports are displayed oldest-first so the model can follow diagnostic
    progression. If the budget is exceeded, the OLDEST reports are dropped
    (most recent retained) and truncation is recorded.
    """
    if not entries:
        return "", False, 0

    header = "PATIENT CONTEXT"
    kept = list(entries)
    truncated = False
    dropped = 0

    def render(items: List[ReportEntry], note: str = "") -> str:
        blocks = [_format_block(i + 1, e) for i, e in enumerate(items)]
        parts = [header]
        if note:
            parts.append(note)
        parts.extend(blocks)
        return "\n\n".join(parts)

    # Drop from the oldest end until within budget (keep >=1 most recent report).
    while len(kept) > 1 and len(render(kept)) > max_chars:
        kept.pop(0)
        dropped += 1
        truncated = True

    if truncated:
        note = (
            f"[Hinweis: {dropped} aeltere(r) Bericht(e) wurden aus Laengengruenden "
            f"entfernt; die {len(kept)} aktuellsten Berichte sind unten aufgefuehrt.]"
        )
        text = render(kept, note)
    else:
        text = render(kept)

    # Hard safety cap if even a single report exceeds the budget.
    if len(text) > max_chars * 2:
        text = text[: max_chars * 2]
        truncated = True

    return text, truncated, dropped
