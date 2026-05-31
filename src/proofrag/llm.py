"""Provider-agnostic LLM client.

Auto-detects Anthropic or OpenAI-compatible (incl. local/Ollama via OPENAI_BASE_URL).
Defaults to a cheap model so generating a golden set + judging doesn't cost much.
The judge model is pinned and surfaced as a `fingerprint` so scores stay comparable.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

# Cheap-by-default. Override with PROOFRAG_MODEL.
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class LLMError(RuntimeError):
    """Raised when the LLM backend is misconfigured or unavailable."""


class LLM:
    """Thin wrapper over Anthropic / OpenAI-compatible chat completions."""

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider or os.environ.get("PROOFRAG_PROVIDER") or self._autodetect()
        self.model = model or os.environ.get("PROOFRAG_MODEL") or self._default_model()
        self._client: Any = None  # one of several backend SDK clients, set lazily

    @staticmethod
    def _autodetect() -> str:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        raise LLMError(
            "No LLM credentials found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "(or run `proofrag demo` to see a scorecard with no API key)."
        )

    def _default_model(self) -> str:
        return DEFAULT_ANTHROPIC_MODEL if self.provider == "anthropic" else DEFAULT_OPENAI_MODEL

    @property
    def fingerprint(self) -> str:
        """Stable id of the judge backend, recorded in every scorecard."""
        return f"{self.provider}:{self.model}"

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        """Complete and parse the first JSON object out of the response."""
        return _extract_json(self._complete(system, prompt))

    # -- backends ---------------------------------------------------------

    def _complete(self, system: str, prompt: str) -> str:
        if self.provider == "anthropic":
            return self._anthropic(system, prompt)
        if self.provider == "openai":
            return self._openai(system, prompt)
        raise LLMError(f"Unknown provider: {self.provider!r}")

    def _anthropic(self, system: str, prompt: str) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise LLMError("Anthropic backend needs: pip install 'proofrag[anthropic]'") from e
        if self._client is None:
            self._client = anthropic.Anthropic()
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        )

    def _openai(self, system: str, prompt: str) -> str:
        try:
            import openai
        except ImportError as e:
            raise LLMError("OpenAI backend needs: pip install 'proofrag[openai]'") from e
        if self._client is None:
            base = os.environ.get("OPENAI_BASE_URL")
            self._client = openai.OpenAI(base_url=base) if base else openai.OpenAI()
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (handles code fences)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start == -1:
        raise LLMError(f"No JSON object in response: {text[:200]!r}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise LLMError(f"Unbalanced JSON in response: {text[:200]!r}")
