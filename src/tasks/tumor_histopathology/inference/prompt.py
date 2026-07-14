"""Build the single-stage tumor classification prompt.

The controlled vocabulary block is injected from ``constants`` at build time so
the prompt can never drift out of sync with the output schema.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.constants import (
    CANONICAL_CATEGORIES,
    CATEGORY_DISPLAY,
)

_VOCAB_PLACEHOLDER = "{VOCABULARY}"


def build_vocabulary_block() -> str:
    lines: List[str] = []
    for cat in CANONICAL_CATEGORIES:
        lines.append(f"- {cat}  ({CATEGORY_DISPLAY.get(cat, cat)})")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _load_template() -> str:
    path = config.PROMPT_FILE
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def load_system_prompt() -> str:
    template = _load_template()
    return template.replace(_VOCAB_PLACEHOLDER, build_vocabulary_block())


def build_user_prompt(context_text: str) -> str:
    return (
        "Nachfolgend der vollstaendige Pathologie-Kontext des Patienten.\n"
        "Bestimme daraus die EINE finale, aktuell gueltige Tumor-Kategorie.\n\n"
        f"{context_text}"
    )


def build_messages(context_text: str) -> list:
    return [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": build_user_prompt(context_text)},
    ]
