"""Optional semantic matcher for retrieval metrics.

Lexical (token-overlap) matching is the zero-dependency default. When chunks are
paraphrased rather than copied, swap in an embedding matcher: it marks a retrieved
chunk relevant to a gold context when their cosine similarity clears a threshold.

Uses the OpenAI-compatible embeddings API (also covers local servers via
OPENAI_BASE_URL). Requires the `openai` extra and either OPENAI_API_KEY or
OPENAI_BASE_URL. (Anthropic has no embeddings API, so `--semantic` always routes
through an OpenAI-compatible endpoint.)
"""

from __future__ import annotations

import math
import os

from .llm import openai_client
from .metrics import Matcher

DEFAULT_EMBED_MODEL = "text-embedding-3-small"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embedding_matcher(threshold: float = 0.75, model: str | None = None) -> Matcher:
    """Return a matcher backed by embedding cosine similarity.

    Embeddings are cached per text within the matcher, so repeated gold/retrieved
    strings across a run are embedded once.
    """
    client = openai_client()
    model = model or os.environ.get("PROOFRAG_EMBED_MODEL") or DEFAULT_EMBED_MODEL
    cache: dict[str, list[float]] = {}

    def embed(text: str) -> list[float]:
        key = text[:2000]
        if key not in cache:
            cache[key] = client.embeddings.create(model=model, input=key).data[0].embedding
        return cache[key]

    def match(gold: str, chunk: str) -> bool:
        return _cosine(embed(gold), embed(chunk)) >= threshold

    return match
