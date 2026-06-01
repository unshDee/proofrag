"""Optional external scoring backends (DeepEval, Ragas).

Each backend swaps only the *generation* judging. proofrag's deterministic
retrieval metrics (Recall@k / Precision@k / NDCG@k / MRR) are kept across all
backends so the scorecard, diff, and compare flows stay consistent. Backends
emit results in proofrag's schema with a backend-specific `generation_metrics`
list, which the scorecard renders dynamically.
"""

from __future__ import annotations


class BackendError(RuntimeError):
    """Raised when a backend is unavailable or misconfigured."""
