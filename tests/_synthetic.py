"""Synthetic test helpers for the tumor histopathology task.

NO REAL PATIENT DATA. Every fixture here is fabricated in memory / temp files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.tasks.tumor_histopathology.inference.llm_client import LLMCallError


def make_input_df(rows: List[Dict[str, object]]) -> pd.DataFrame:
    """Build a KISIM-like input DataFrame from row dicts.

    Missing columns are filled with blanks so callers only specify what matters.
    """
    columns = ["patnr", "lst_fnr", "anz_op", "min_opdat", "max_opdat",
               "p_nr", "p_fnr", "p_dat", "p_name", "p_kom"]
    normed = []
    for r in rows:
        normed.append({c: r.get(c, "") for c in columns})
    return pd.DataFrame(normed, columns=columns)


def write_xlsx(df: pd.DataFrame, path: Path, sheet_name: str = "Sheet1") -> Path:
    df.to_excel(path, index=False, sheet_name=sheet_name, engine="openpyxl")
    return path


def tumor_json(
    category: Optional[str],
    *,
    available: bool = True,
    certainty: str = "high",
    reasoning: str = "synthetic",
    evidence: Optional[List[dict]] = None,
    historical: Optional[List[dict]] = None,
    uncertainty: Optional[List[str]] = None,
) -> str:
    payload = {
        "tumor_information_available": available,
        "current_tumor_category": category,
        "certainty": certainty,
        "reasoning": reasoning,
        "supporting_evidence": evidence or [],
        "historical_diagnoses_mentioned": historical or [],
        "uncertainty_reasons": uncertainty or [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _user_content(messages: list) -> str:
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


class StubLLM:
    """Deterministic stub LLM.

    - ``default``: response returned when no substring rule matches.
    - ``by_substring``: {needle: response} matched against the user prompt.
    - ``raise_error``: raise ``LLMCallError`` on every call.
    """

    def __init__(
        self,
        default: str = "",
        by_substring: Optional[Dict[str, str]] = None,
        raise_error: bool = False,
    ):
        self.default = default
        self.by_substring = by_substring or {}
        self.raise_error = raise_error
        self.calls: List[list] = []

    def __call__(self, messages: list) -> str:
        self.calls.append(messages)
        if self.raise_error:
            raise LLMCallError("synthetic transport failure")
        user = _user_content(messages)
        for needle, response in self.by_substring.items():
            if needle in user:
                return response
        return self.default
