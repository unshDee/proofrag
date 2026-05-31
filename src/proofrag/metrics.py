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
    return lambda gold, chunk: _jaccard(gold, chunk) >= threshold


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
    rels = [1.0 if _relevance(gold_contexts, c, matcher) else 0.0 for c in retrieved[:k]]
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(sorted(rels, reverse=True)))
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
