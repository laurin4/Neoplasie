"""Parse and validate tumor histopathology LLM JSON responses (stdlib only).

The low-level JSON extraction/repair engine (brace matching, control-char
sanitization, markdown-fence stripping, trailing-comma removal) is robust to
common LLM formatting mistakes. The tumor-specific layer validates the schema,
resolves the category against the controlled vocabulary, and maps the outcome
onto the classification-status taxonomy.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.tasks.tumor_histopathology.constants import (
    AMBIGUOUS_CATEGORIES,
    category_column,
    is_valid_category,
    resolve_category,
)
from src.tasks.tumor_histopathology.io.schema import (
    CERTAINTY_VALUES,
    STATUS_NO_TUMOR_INFORMATION,
    STATUS_PARSE_FAILED,
    STATUS_SUCCESS,
    STATUS_UNCERTAIN,
    STATUS_UNSUPPORTED_CATEGORY,
)

_USZ_TOKENS_TO_STRIP = (
    "<start_of_turn>user",
    "<start_of_turn>model",
    "<start_of_turn>",
    "<end_of_turn>",
)


# ---------------------------------------------------------------------------
# Low-level JSON extraction / repair (reused engine)
# ---------------------------------------------------------------------------
def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def _strip_usz_template_tokens(text: str) -> str:
    out = text
    for tok in _USZ_TOKENS_TO_STRIP:
        out = out.replace(tok, "")
    return out


def _unescape_csv_style_quotes(text: str) -> str:
    s = text.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1].replace('""', '"')
        if inner.lstrip().startswith("{"):
            return inner
    return text


def _strip_markdown_fences(text: str) -> str:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, flags=re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _remove_trailing_commas(json_text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", json_text)


def extract_first_json_object(text: str) -> str:
    """Return the first complete top-level JSON object substring."""
    if text is None:
        return ""
    original_stripped = text.strip()
    if not original_stripped:
        return ""

    cleaned = _strip_usz_template_tokens(original_stripped).strip()
    start = cleaned.find("{")
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1].strip()
    return ""


def sanitize_json_control_chars_in_strings(json_text: str) -> str:
    """Escape raw control characters that appear inside JSON string values."""
    if not json_text:
        return json_text

    out: List[str] = []
    in_string = False
    escape = False
    for ch in json_text:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
            else:
                out.append(ch)
            continue
        out.append(ch)
        if ch == '"':
            in_string = True
            escape = False
    return "".join(out)


def _try_json_loads(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
    if not text or not text.strip():
        return None, "empty text", ""

    raw = text.strip()
    candidates: List[Tuple[str, str]] = [(raw, "")]
    no_trail = _remove_trailing_commas(raw)
    if no_trail != raw:
        candidates.append((no_trail, ""))

    sanitized = sanitize_json_control_chars_in_strings(raw)
    if sanitized != raw:
        candidates.append((sanitized, "control_chars_escaped"))
        no_trail_sanitized = _remove_trailing_commas(sanitized)
        if no_trail_sanitized != sanitized:
            candidates.append((no_trail_sanitized, "control_chars_escaped"))

    last_err = ""
    seen: set[str] = set()
    for candidate, repair in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed, None, repair
            if isinstance(parsed, str):
                nested, _nested_err, nested_repair = _try_json_loads(parsed)
                if nested is not None:
                    return nested, None, repair or nested_repair
        except json.JSONDecodeError as exc:
            last_err = str(exc)
    return None, last_err, ""


def _parse_llm_json_dict(raw_output: str) -> Tuple[Optional[Dict[str, Any]], str, str]:
    if not raw_output or not str(raw_output).strip():
        return None, "empty LLM response", ""
    text = _strip_bom(str(raw_output))
    text = _unescape_csv_style_quotes(text)
    text = _strip_markdown_fences(text)

    parsed, err, repair = _try_json_loads(text)
    if parsed is not None:
        return parsed, "", repair

    snippet = extract_first_json_object(text)
    if snippet:
        parsed, err, repair = _try_json_loads(snippet)
        if parsed is not None:
            return parsed, "", repair
    return None, err or "no JSON object found", ""


# ---------------------------------------------------------------------------
# Field normalization helpers
# ---------------------------------------------------------------------------
def _parse_bool(value: object, default: Optional[bool] = None) -> Optional[bool]:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if not s or s in ("nan", "none", "null", "<na>"):
        return default
    if s in ("true", "1", "yes", "ja", "wahr"):
        return True
    if s in ("false", "0", "no", "nein", "falsch"):
        return False
    return default


def _normalize_certainty(raw: object) -> str:
    s = str(raw or "").strip().lower()
    mapping = {
        "niedrig": "low", "gering": "low",
        "mittel": "medium", "moderat": "medium", "mittelgradig": "medium",
        "hoch": "high",
    }
    s = mapping.get(s, s)
    return s if s in CERTAINTY_VALUES else "low"


def _clean_control_chars(text: str) -> str:
    return "".join(
        ch for ch in text if ch in ("\n", "\t") or unicodedata.category(ch) != "Cc"
    )


def _as_list_of_dicts(raw: object) -> List[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _as_list_of_str(raw: object) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(u).strip() for u in raw if str(u).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _resolve_category_field(raw: object) -> Tuple[Optional[str], bool]:
    """Resolve the current_tumor_category field.

    Returns ``(canonical_or_None, multiple_detected)``. ``multiple_detected`` is
    True only when the field is a list resolving to >1 distinct valid category.
    """
    if isinstance(raw, list):
        resolved = {c for c in (resolve_category(x) for x in raw) if c}
        if len(resolved) > 1:
            return None, True
        if len(resolved) == 1:
            return next(iter(resolved)), False
        return None, False
    return resolve_category(raw), False


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class TumorParseResult:
    success: bool = False
    status: str = STATUS_PARSE_FAILED
    tumor_information_available: Optional[bool] = None
    current_tumor_category: Optional[str] = None
    predicted_output_column: Optional[str] = None
    certainty: str = "low"
    reasoning: str = ""
    supporting_evidence: List[dict] = field(default_factory=list)
    historical_diagnoses_mentioned: List[dict] = field(default_factory=list)
    uncertainty_reasons: List[str] = field(default_factory=list)
    category_ambiguous: bool = False
    multiple_categories: bool = False
    error_message: str = ""
    parse_error_reason: str = ""
    parse_error_detail: str = ""
    parse_repair_applied: str = ""
    raw_response: str = ""


def parse_tumor_response(raw_output: str, *, context: str = "") -> TumorParseResult:
    """Parse a single-stage tumor classification LLM response.

    Maps the outcome onto the status taxonomy: ``success``,
    ``no_tumor_information``, ``unsupported_category``, ``uncertain``, or
    ``parse_failed``. ``llm_failed`` is set by the runner, not here.
    """
    result = TumorParseResult(raw_response=str(raw_output or ""))

    if not raw_output or not str(raw_output).strip():
        result.status = STATUS_PARSE_FAILED
        result.parse_error_reason = "empty_llm_response"
        result.error_message = "empty LLM response"
        return result

    try:
        parsed, detail, repair = _parse_llm_json_dict(str(raw_output))
    except Exception as exc:  # noqa: BLE001 - never crash the pipeline on parse
        result.status = STATUS_PARSE_FAILED
        result.parse_error_reason = "unexpected_exception"
        result.parse_error_detail = str(exc)[:2000]
        result.error_message = f"unexpected_exception: {exc}"
        return result

    if parsed is None:
        result.status = STATUS_PARSE_FAILED
        result.parse_error_reason = (
            "json_decode_error" if detail and "json" in detail.lower()
            else "no_json_object_found"
        )
        result.parse_error_detail = (detail or "")[:2000]
        result.error_message = detail or "no JSON object found"
        return result

    result.parse_repair_applied = repair
    result.certainty = _normalize_certainty(parsed.get("certainty"))
    result.reasoning = _clean_control_chars(str(parsed.get("reasoning", "") or "")).strip()
    result.supporting_evidence = _as_list_of_dicts(parsed.get("supporting_evidence"))
    result.historical_diagnoses_mentioned = _as_list_of_dicts(
        parsed.get("historical_diagnoses_mentioned")
    )
    result.uncertainty_reasons = _as_list_of_str(parsed.get("uncertainty_reasons"))

    available = _parse_bool(parsed.get("tumor_information_available"), default=None)
    raw_category = parsed.get("current_tumor_category")
    category, multiple = _resolve_category_field(raw_category)
    result.multiple_categories = multiple

    # Explicit "no tumor information".
    category_is_empty = raw_category in (None, "", "null") or (
        isinstance(raw_category, str)
        and str(raw_category).strip().lower() in ("", "null", "none", "kein", "keine")
    )
    if available is False or (available is None and category_is_empty and category is None):
        result.status = STATUS_NO_TUMOR_INFORMATION
        result.tumor_information_available = False
        result.current_tumor_category = None
        return result

    result.tumor_information_available = True

    if multiple:
        result.status = STATUS_UNCERTAIN
        if "multiple_final_categories" not in result.uncertainty_reasons:
            result.uncertainty_reasons.append("multiple_final_categories")
        return result

    if category is None:
        # Text present but no resolvable category.
        if raw_category in (None, "") or category_is_empty:
            result.status = STATUS_UNCERTAIN
            if "no_definitive_category" not in result.uncertainty_reasons:
                result.uncertainty_reasons.append("no_definitive_category")
            return result
        result.status = STATUS_UNSUPPORTED_CATEGORY
        result.error_message = f"unsupported category: {raw_category!r}"
        return result

    if not is_valid_category(category):
        result.status = STATUS_UNSUPPORTED_CATEGORY
        result.error_message = f"unsupported category: {category!r}"
        return result

    result.success = True
    result.status = STATUS_SUCCESS
    result.current_tumor_category = category
    result.predicted_output_column = category_column(category)
    result.category_ambiguous = category in AMBIGUOUS_CATEGORIES
    return result
