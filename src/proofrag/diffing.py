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

import math

from .judge import JUDGE_DIMENSIONS
from .metrics import RETRIEVAL_METRICS

_CONFIG_FIELDS = ["backend", "k", "n", "goldenset_fingerprint", "matcher", "generation_metrics"]


def diff(baseline: dict, candidate: dict, tolerance: float = 0.02) -> dict:
    """Compare candidate vs baseline aggregates. All metrics are higher-is-better."""
    if _number(tolerance) is None or tolerance < 0:
        raise ValueError("tolerance must be a finite nonnegative number")
    b = baseline.get("aggregate", {})
    c = candidate.get("aggregate", {})
    if not isinstance(b, dict) or not isinstance(c, dict):
        raise ValueError("baseline and candidate aggregates must be JSON objects")
    if not any(_number(value) is not None for value in b.values()):
        raise ValueError("baseline aggregate needs at least one finite numeric metric")
    rows = []
    regressed = []
    declared = [
        *(baseline.get("generation_metrics") or JUDGE_DIMENSIONS),
        *(candidate.get("generation_metrics") or JUDGE_DIMENSIONS),
        *RETRIEVAL_METRICS,
        *b,
        *c,
    ]
    for m in dict.fromkeys(declared):
        if m not in b and m not in c:
            continue
        bv, cv = _number(b.get(m)), _number(c.get(m))
        raw_delta = None if bv is None or cv is None else cv - bv
        delta = None if raw_delta is None else round(raw_delta, 3)
        missing = m in b and (m not in c or cv is None)
        # Round for display only so a small real regression still fails the gate.
        is_reg = missing or (
            raw_delta is not None
            and raw_delta < -tolerance
            and not math.isclose(raw_delta, -tolerance, rel_tol=1e-12, abs_tol=1e-12)
        )
        rows.append(
            {
                "metric": m,
                "baseline": bv,
                "candidate": cv,
                "delta": delta,
                "missing": missing,
                "regressed": is_reg,
            }
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
        "configuration_mismatches": [
            {
                "field": field,
                "baseline": baseline.get(field),
                "candidate": candidate.get(field),
            }
            for field in _CONFIG_FIELDS
            if (field in baseline or field in candidate)
            and baseline.get(field) != candidate.get(field)
        ],
    }


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


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
