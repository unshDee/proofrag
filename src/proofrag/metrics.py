"""Rank-aware retrieval metrics (Recall@k, Precision@k, NDCG@k, MRR).

These separate retriever failures from generator failures: if NDCG@k is low, the
right context never reached the model in a usable rank, so a bad answer isn't the
LLM's fault.

Relevance is decided by a pluggable *matcher* `(gold_context, retrieved_chunk) ->
bool`. The default is token-overlap (Jaccard) — dependency-free, runs anywhere.
Swap in `embedding_matcher()` (see embeddings.py) for semantic matching without
touching the metric code.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

_WORD = re.compile(r"[a-z0-9]+")

Matcher = Callable[[str, str], bool]
RETRIEVAL_METRICS = ["recall_at_k", "precision_at_k", "ndcg_at_k", "mrr"]


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def lexical_matcher(threshold: float = 0.4) -> Matcher:
    """Default matcher: relevant if token-overlap (Jaccard) >= threshold."""

    def match(gold: str, chunk: str) -> bool:
        return _jaccard(gold, chunk) >= threshold

    match.__name__ = f"lexical_jaccard_{threshold:g}"
    return match


def exact_matcher() -> Matcher:
    """Match only identical chunks, ignoring surrounding whitespace."""

    def match(gold: str, chunk: str) -> bool:
        return gold.strip() == chunk.strip()

    match.__name__ = "exact"
    return match


def matcher_fingerprint(matcher: Matcher) -> str:
    """Return a compact matcher identifier for reproducible result metadata."""
    return getattr(matcher, "__name__", matcher.__class__.__name__)


def _relevance(gold_contexts: list[str], chunk: str, matcher: Matcher) -> bool:
    return any(matcher(g, chunk) for g in gold_contexts)


def recall_at_k(gold_contexts, retrieved, k, matcher) -> float:
    """Fraction of gold contexts found among the top-k retrieved."""
    if not gold_contexts:
        return 1.0  # nothing to retrieve (e.g. an unanswerable case)
    topk = retrieved[:k]
    hits = sum(1 for g in gold_contexts if any(matcher(g, c) for c in topk))
    return hits / len(gold_contexts)


def precision_at_k(gold_contexts, retrieved, k, matcher) -> float:
    """Fraction of the top-k retrieved that are relevant."""
    topk = retrieved[:k]
    if not topk:
        return 0.0
    rel = sum(1 for c in topk if _relevance(gold_contexts, c, matcher))
    return rel / len(topk)


def ndcg_at_k(gold_contexts, retrieved, k, matcher) -> float:
    """Normalized DCG@k with binary relevance — rewards relevant chunks ranked high."""
    # Track the maximum one-to-one matching after each retrieved chunk. A plain
    # greedy assignment can waste an ambiguous chunk on evidence that a later,
    # more specific chunk is uniquely able to match.
    chunk_matches: list[list[int]] = []
    gold_to_chunk: dict[int, int] = {}

    def augment(chunk_index: int, seen_gold: set[int]) -> bool:
        for gold_index in chunk_matches[chunk_index]:
            if gold_index in seen_gold:
                continue
            seen_gold.add(gold_index)
            previous = gold_to_chunk.get(gold_index)
            if previous is None or augment(previous, seen_gold):
                gold_to_chunk[gold_index] = chunk_index
                return True
        return False

    rels: list[float] = []
    for chunk_index, chunk in enumerate(retrieved[:k]):
        chunk_matches.append(
            [i for i, gold_context in enumerate(gold_contexts) if matcher(gold_context, chunk)]
        )
        rels.append(1.0 if augment(chunk_index, set()) else 0.0)
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
    ideal_hits = min(len(gold_contexts), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(gold_contexts, retrieved, matcher) -> float:
    """Reciprocal rank of the first relevant chunk (0 if none)."""
    for i, c in enumerate(retrieved):
        if _relevance(gold_contexts, c, matcher):
            return 1.0 / (i + 1)
    return 0.0


def retrieval_metrics(
    gold_contexts: list[str],
    retrieved: list[str],
    k: int = 5,
    matcher: Matcher | None = None,
) -> dict:
    """All retrieval metrics for one (gold_contexts, retrieved) pair."""
    matcher = matcher or lexical_matcher()
    return {
        "recall_at_k": round(recall_at_k(gold_contexts, retrieved, k, matcher), 3),
        "precision_at_k": round(precision_at_k(gold_contexts, retrieved, k, matcher), 3),
        "ndcg_at_k": round(ndcg_at_k(gold_contexts, retrieved, k, matcher), 3),
        "mrr": round(mrr(gold_contexts, retrieved, matcher), 3),
    }


# --- back-compat -------------------------------------------------------------


def context_matches(gold: str, retrieved: list[str], threshold: float = 0.4) -> bool:
    """True if any retrieved context matches the gold context above threshold."""
    m = lexical_matcher(threshold)
    return any(m(gold, r) for r in retrieved)


def retrieval_recall(gold_contexts, retrieved, threshold: float = 0.4) -> float:
    """Recall over all retrieved (k = len). Kept for back-compat."""
    return recall_at_k(gold_contexts, retrieved, len(retrieved) or 1, lexical_matcher(threshold))
