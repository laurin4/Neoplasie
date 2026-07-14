"""Provider-agnostic LLM client for tumor histopathology inference.

Supports the USZ generate API and a local Ollama chat endpoint. Reads all
configuration at call time (via ``config``) so tests can override the
environment after import. Only depends on ``requests``.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

import requests

from src.tasks.tumor_histopathology import config
from src.tasks.tumor_histopathology.inference.parse import extract_first_json_object

LOGGER = logging.getLogger(__name__)

RETRY_WAIT_SECONDS = 5
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ReadTimeout,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)


class LLMCallError(RuntimeError):
    """Raised when an LLM call fails after exhausting retries."""


def _extract_system_user(messages: list) -> Tuple[str, str]:
    sys_parts: List[str] = []
    user_parts: List[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "")).strip().lower()
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        if role == "system":
            sys_parts.append(content)
        elif role == "user":
            user_parts.append(content)
    return (
        "\n\n".join(p for p in sys_parts if p),
        "\n\n".join(p for p in user_parts if p),
    )


def _build_chat_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/api/chat"):
        return clean
    if clean.endswith("/api/generate"):
        return f"{clean[:-len('/api/generate')]}/api/chat"
    if clean.endswith("/api"):
        return f"{clean}/chat"
    return f"{clean}/api/chat"


def call_usz_api(system_prompt: str, user_prompt: str) -> str:
    payload = {
        "prompt": (user_prompt or "").strip(),
        "system_prompt": system_prompt or "",
        "temperature": config.get_temperature(),
        "top_p": config.get_top_p(),
        "max_tokens": config.get_max_tokens(),
        "disable_think": config.get_disable_think(),
    }
    response = requests.post(
        config.get_usz_url(), json=payload, timeout=config.get_timeout_seconds()
    )
    if response.status_code != 200:
        snippet = (response.text or "")[:500]
        raise RuntimeError(f"USZ LLM API HTTP {response.status_code}: {snippet}")
    body = response.json()
    result = body.get("response", "")
    if isinstance(result, list):
        final_text = "\n".join(str(x) for x in result)
    else:
        final_text = str(result)
    return extract_first_json_object(final_text.strip())


def _call_ollama_messages(messages: list) -> str:
    chat_url = _build_chat_url(config.get_ollama_url())
    response = requests.post(
        chat_url,
        json={
            "model": config.get_ollama_model(),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": config.get_temperature(),
                "top_p": config.get_top_p(),
                "num_predict": config.get_max_tokens(),
                "num_ctx": config.get_ollama_num_ctx(),
            },
        },
        timeout=config.get_timeout_seconds(),
    )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message", {})
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Ollama response missing message.content")
    return content.strip()


def _call_provider_once(messages: list) -> str:
    provider = config.get_provider()
    system_prompt, user_prompt = _extract_system_user(messages)

    if provider == "ollama":
        return _call_ollama_messages(messages)
    if provider == "usz_api":
        return call_usz_api(system_prompt, user_prompt)
    raise ValueError(
        f"Unknown provider={provider!r}; allowed: {config.SUPPORTED_PROVIDERS}"
    )


def call_llm(messages: list) -> str:
    """Provider-agnostic entry point with bounded retries.

    Retries only on transient transport errors. After all retries are exhausted
    it raises ``LLMCallError`` so the caller can mark the patient ``llm_failed``
    without crashing the pipeline.
    """
    timeout = config.get_timeout_seconds()
    max_retries = config.get_max_retries()
    total_attempts = max_retries + 1

    last_exc: Optional[BaseException] = None
    for attempt in range(1, total_attempts + 1):
        try:
            return _call_provider_once(messages)
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt <= max_retries:
                LOGGER.warning(
                    "LLM transient failure (%s) attempt=%d/%d; retrying in %ds",
                    type(exc).__name__, attempt, total_attempts, RETRY_WAIT_SECONDS,
                )
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            break

    err_name = type(last_exc).__name__ if last_exc is not None else "Timeout"
    raise LLMCallError(
        f"{err_name} after {timeout}s (retries={max_retries})"
    ) from last_exc
