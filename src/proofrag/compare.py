"""Blind A/B comparison of two RAG variants (e.g. vector vs GraphRAG).

Both variants answer the *same* golden set; the *same* pinned judge then picks
the better answer for each question — **blind**: the two answers are shown as
"Response 1" / "Response 2" in a per-question randomized order, so the judge
never knows which system produced which, and position bias is shuffled out.

The pairwise verdict (which answer is better vs the reference) is the headline.
Deterministic retrieval metrics for each variant are reported alongside so you
can see whether a win came from better retrieval or better generation.
"""

from __future__ import annotations

import datetime as _dt
import json
import random

from .llm import LLM
from .metrics import RETRIEVAL_METRICS, lexical_matcher, retrieval_metrics

CMP_SYS = (
    "You are a strict, impartial judge comparing two RAG answers to the same question. "
    "You do not know which system produced which. Judge only on quality versus the "
    "reference answer. Output JSON only."
)

CMP_TMPL = """Question: {q}

Reference (gold) answer: {gold}

Response 1: {r1}

Response 2: {r2}

Which response is better overall — more correct, complete, and faithful to the
reference? Return JSON:
{{"winner": 1, "reason": "one short sentence"}}
Use winner 1 or 2, or 0 for a genuine tie."""


def compare(
    goldenset: list[dict],
    preds_a: list[dict],
    preds_b: list[dict],
    a_name: str = "A",
    b_name: str = "B",
    llm: LLM | None = None,
    k: int = 5,
    matcher=None,
    seed: int = 0,
) -> dict:
    """Blind pairwise comparison of two prediction sets over one golden set."""
    llm = llm or LLM()
    matcher = matcher or lexical_matcher()
    rng = random.Random(seed)
    a = {p["id"]: p for p in preds_a}
    b = {p["id"]: p for p in preds_b}

    records: list[dict] = []
    wins = {"a": 0, "b": 0, "tie": 0}
    ret_a: list[dict] = []
    ret_b: list[dict] = []

    for g in goldenset:
        pa, pb = a.get(g["id"]), b.get(g["id"])
        if pa is None or pb is None:
            continue

        # blind: randomize which variant is "Response 1" per question
        swap = rng.random() < 0.5
        first, second = (pb, pa) if swap else (pa, pb)
        winner, reason = _judge_pair(llm, g, first.get("answer", ""), second.get("answer", ""))
        if winner == 1:
            side = "b" if swap else "a"
        elif winner == 2:
            side = "a" if swap else "b"
        else:
            side = "tie"
        wins[side] += 1

        records.append(
            {
                "id": g["id"],
                "question": g["question"],
                "winner": side,
                "reason": reason,
                "a_answer": pa.get("answer", ""),
                "b_answer": pb.get("answer", ""),
            }
        )

        if g.get("gold_contexts"):
            ret_a.append(
                retrieval_metrics(
                    g["gold_contexts"], pa.get("retrieved_contexts") or [], k, matcher
                )
            )
            ret_b.append(
                retrieval_metrics(
                    g["gold_contexts"], pb.get("retrieved_contexts") or [], k, matcher
                )
            )

    decisive = wins["a"] + wins["b"]
    return {
        "kind": "comparison",
        "judge_fingerprint": llm.fingerprint,
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "a_name": a_name,
        "b_name": b_name,
        "n": len(records),
        "wins": wins,
        "win_rate_a": round(wins["a"] / decisive, 3) if decisive else None,
        "retrieval_a": _mean_metrics(ret_a),
        "retrieval_b": _mean_metrics(ret_b),
        "records": records,
    }


def _judge_pair(llm: LLM, gold: dict, r1: str, r2: str) -> tuple[int, str]:
    prompt = CMP_TMPL.format(
        q=gold["question"],
        gold=gold.get("gold_answer", ""),
        r1=r1 or "(no answer)",
        r2=r2 or "(no answer)",
    )
    try:
        out = llm.complete_json(CMP_SYS, prompt)
    except Exception as e:  # noqa: BLE001 - a bad judgment shouldn't abort the run
        return 0, f"judge error: {e}"
    w = out.get("winner")
    w = w if w in (1, 2) else 0
    return w, str(out.get("reason", ""))[:300]


def _mean_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {m: None for m in RETRIEVAL_METRICS}
    return {m: round(sum(r[m] for r in rows) / len(rows), 3) for m in RETRIEVAL_METRICS}


def write_comparison(result: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
