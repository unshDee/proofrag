"""Cheap, dependency-free retrieval metrics based on token overlap.

These are intentionally embedding-free so the kit runs anywhere with no extra
deps. They separate retriever failures from generator failures: if recall is
low, the right context never reached the model, so a bad answer isn't the LLM's
fault. Swap in embedding similarity later without changing the interface.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / len(ta | tb)


def context_matches(gold: str, retrieved: list[str], threshold: float = 0.4) -> bool:
    """True if any retrieved context overlaps the gold context above threshold."""
    return any(_jaccard(gold, r) >= threshold for r in retrieved)


def retrieval_recall(
    gold_contexts: list[str], retrieved: list[str], threshold: float = 0.4
) -> float:
    """Fraction of gold contexts that show up among the retrieved contexts."""
    if not gold_contexts:
        return 1.0
    hits = sum(1 for g in gold_contexts if context_matches(g, retrieved, threshold))
    return hits / len(gold_contexts)
