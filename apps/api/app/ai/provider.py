"""Optional chat provider: env-gated, replaceable, never required.

The assistant answers on engine/book facts alone; a large language model is a
*garnish* that may only re-phrase those facts (the grounding guard in
`compose.py` rejects any move it invents). So the whole LLM path is optional:

* configured only from environment/settings — never from a client value;
* the key is never logged or returned;
* if nothing is configured, :func:`open_chat_provider` reports unavailable and
  the service uses the deterministic composer instead (this is the default, and
  the default the offline test/CI world runs in).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import requests

from app.core.database import settings


class AssistantUnavailableError(RuntimeError):
    """No chat provider is configured (or the call failed) — use the fallback."""


class ChatProvider(Protocol):
    """Minimal chat seam: system + user text in, prose out."""

    @property
    def name(self) -> str:
        """Provider label (read-only, so a frozen implementation still conforms)."""
        ...

    def complete(self, system: str, user: str) -> str:
        """Return a short prose answer. Raises AssistantUnavailableError."""
        ...


def assistant_configured() -> bool:
    """Whether an LLM is available: a key must be present in settings/env."""
    return bool(settings.assistant_api_key)


@dataclass(frozen=True)
class OpenAICompatProvider:
    """OpenAI-compatible chat completions (base_url/model/key all from settings).

    Works against any endpoint that speaks the `/chat/completions` shape, so the
    vendor is a configuration choice, not a code change. Low temperature: the
    facts are fixed, only their wording is ours to choose.
    """

    api_key: str
    base_url: str
    model: str
    max_tokens: int
    name: str = "llm"

    def complete(self, system: str, user: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:  # network/JSON/auth
            raise AssistantUnavailableError(str(exc)) from exc
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AssistantUnavailableError("Malformed chat response") from exc


def open_chat_provider() -> ChatProvider:
    """Build the configured provider, or raise when none is available.

    Callers must treat :class:`AssistantUnavailableError` as 'use the deterministic
    composer', not as an HTTP error — the answer does not depend on this succeeding.
    """
    if not assistant_configured():
        raise AssistantUnavailableError("No assistant API key configured")
    return OpenAICompatProvider(
        api_key=settings.assistant_api_key,
        base_url=settings.assistant_base_url,
        model=settings.assistant_model,
        max_tokens=settings.assistant_max_tokens,
    )
