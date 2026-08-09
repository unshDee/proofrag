"""Provider-agnostic LLM client.

Auto-detects Anthropic or OpenAI-compatible (incl. local/Ollama via OPENAI_BASE_URL).
Defaults to a cheap model so generating a golden set + judging doesn't cost much.
The judge model is pinned and surfaced as a `fingerprint` so scores stay comparable.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# Cheap-by-default. Override with PROOFRAG_MODEL.
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini-2024-07-18"


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
        # OPENAI_BASE_URL alone (no key) covers local/compatible servers like Ollama.
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"):
            return "openai"
        raise LLMError(
            "No LLM credentials found. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
            "OPENAI_BASE_URL (local/compatible). Or run `proofrag demo` (no key needed)."
        )

    def _default_model(self) -> str:
        return DEFAULT_ANTHROPIC_MODEL if self.provider == "anthropic" else DEFAULT_OPENAI_MODEL

    @property
    def fingerprint(self) -> str:
        """Stable id of the judge backend, recorded in every scorecard."""
        endpoint = os.environ.get("OPENAI_BASE_URL") if self.provider == "openai" else None
        endpoint_hash = (
            f":endpoint={hashlib.sha256(endpoint.encode()).hexdigest()[:8]}" if endpoint else ""
        )
        return f"{self.provider}:{self.model}:temperature=0{endpoint_hash}"

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        """Complete and parse the first JSON object out of the response."""
        try:
            return _extract_json(self._complete(system, prompt))
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001 - normalize provider SDK failures for the CLI
            raise LLMError(f"{self.provider} request failed: {e}") from e

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
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        )

    def _openai(self, system: str, prompt: str) -> str:
        if self._client is None:
            self._client = openai_client()
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""


def openai_client(require_key: bool = True):
    """Create an OpenAI-compatible client, honoring OPENAI_BASE_URL.

    For a local/compatible endpoint (base URL set) an API key is optional — many
    local servers (Ollama, vLLM, LM Studio) accept any token.
    """
    try:
        import openai
    except ImportError as e:
        raise LLMError("OpenAI backend needs: pip install 'proofrag[openai]'") from e
    base = os.environ.get("OPENAI_BASE_URL")
    key = os.environ.get("OPENAI_API_KEY") or ("not-needed" if base else None)
    if key is None and require_key:
        raise LLMError(
            "OpenAI backend needs OPENAI_API_KEY, or set OPENAI_BASE_URL for a "
            "local/compatible endpoint."
        )
    return openai.OpenAI(base_url=base, api_key=key) if base else openai.OpenAI(api_key=key)


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (handles code fences)."""
    text = text.strip()
    decoder = json.JSONDecoder(parse_constant=_invalid_constant)
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[start:])
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    raise LLMError(f"No valid JSON object in response: {text[:200]!r}")


def _invalid_constant(value: str):
    raise ValueError(f"invalid JSON constant {value}")
