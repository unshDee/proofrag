"""Baseline diffing: compare two results.json runs and flag regressions.

A baseline is just a results.json from a known-good run (commit it to the repo).
On every change you re-evaluate and `diff` against it: any metric that drops by
more than the tolerance is a regression and fails the build. Because all metrics
here are higher-is-better, "regression" simply means delta < -tolerance.

Judge models are pinned for a reason — comparing scores produced by different
judges is meaningless, so a fingerprint mismatch is refused unless explicitly
overridden.
"""

from __future__ import annotations

from .judge import JUDGE_DIMENSIONS
from .metrics import RETRIEVAL_METRICS

ALL_METRICS = JUDGE_DIMENSIONS + RETRIEVAL_METRICS


def diff(baseline: dict, candidate: dict, tolerance: float = 0.02) -> dict:
    """Compare candidate vs baseline aggregates. All metrics are higher-is-better."""
    b = baseline.get("aggregate", {})
    c = candidate.get("aggregate", {})
    rows = []
    regressed = []
    for m in ALL_METRICS:
        if m not in b and m not in c:
            continue
        bv, cv = b.get(m), c.get(m)
        delta = None if bv is None or cv is None else round(cv - bv, 3)
        is_reg = delta is not None and delta < -tolerance
        rows.append(
            {"metric": m, "baseline": bv, "candidate": cv, "delta": delta, "regressed": is_reg}
        )
        if is_reg:
            regressed.append(m)
    return {
        "rows": rows,
        "regressed": regressed,
        "tolerance": tolerance,
        "judge_mismatch": baseline.get("judge_fingerprint") != candidate.get("judge_fingerprint"),
        "baseline_judge": baseline.get("judge_fingerprint"),
        "candidate_judge": candidate.get("judge_fingerprint"),
    }


def format_table(result: dict) -> str:
    """Plain-text delta table for the terminal / CI logs."""
    out = [f"{'metric':>16}  {'base':>7}  {'cand':>7}  {'delta':>7}"]
    for r in result["rows"]:
        b = "—" if r["baseline"] is None else f"{r['baseline']:.3f}"
        c = "—" if r["candidate"] is None else f"{r['candidate']:.3f}"
        d = "—" if r["delta"] is None else f"{r['delta']:+.3f}"
        flag = "   << REGRESSION" if r["regressed"] else ""
        out.append(f"{r['metric']:>16}  {b:>7}  {c:>7}  {d:>7}{flag}")
    return "\n".join(out)
