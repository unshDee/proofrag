"""LLM-as-judge scoring + rank-aware retrieval metrics → results.json.

Generation quality is scored by a pinned judge model on four dimensions
(groundedness, correctness, completeness, citation_quality). Retrieval quality is
scored separately (Recall@k, Precision@k, NDCG@k, MRR), so a retriever miss is
never blamed on the generator. The judge fingerprint is recorded so two scorecards
are only compared when they used the same judge.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from .llm import LLM
from .metrics import RETRIEVAL_METRICS, Matcher, lexical_matcher, retrieval_metrics

JUDGE_DIMENSIONS = ["groundedness", "correctness", "completeness", "citation_quality"]

JUDGE_SYS = (
    "You are a strict, consistent evaluator of RAG answers. "
    "Score each dimension from 0.0 to 1.0. Be calibrated: 1.0 means flawless, "
    "0.5 means partially right, 0.0 means absent or wrong. Output JSON only."
)

JUDGE_TMPL = '''Question: {q}

Reference (gold) answer: {gold}

Context the system retrieved:
"""{ctx}"""

System's answer: {ans}

Score 0.0-1.0:
- groundedness: is the answer supported by the retrieved context (no hallucination)?
- correctness: do its facts match the reference answer?
- completeness: does it cover what the reference covers?
- citation_quality: are claims attributable to the retrieved context?

Return JSON:
{{"groundedness": 0.0, "correctness": 0.0, "completeness": 0.0, "citation_quality": 0.0, "rationale": "one short sentence"}}'''


def evaluate(
    goldenset: list[dict],
    predictions: list[dict],
    llm: LLM | None = None,
    k: int = 5,
    matcher: Matcher | None = None,
) -> dict:
    """Join goldenset to predictions by id, judge each, aggregate.

    `k` is the cutoff for retrieval metrics. `matcher` decides chunk relevance
    (defaults to lexical token-overlap; pass `embedding_matcher()` for semantic).
    """
    llm = llm or LLM()
    matcher = matcher or lexical_matcher()
    preds = {p["id"]: p for p in predictions}

    records: list[dict] = []
    for g in goldenset:
        pred = preds.get(g["id"])
        if pred is None:
            continue
        retrieved = pred.get("retrieved_contexts", []) or []
        answer = pred.get("answer", "")
        gold_contexts = g.get("gold_contexts", []) or []

        scores = _judge_one(llm, g, answer, retrieved)
        # Unanswerable cases have no gold context to retrieve — skip retrieval scoring.
        retrieval = (
            retrieval_metrics(gold_contexts, retrieved, k, matcher) if gold_contexts else None
        )

        records.append(
            {
                "id": g["id"],
                "question": g["question"],
                "difficulty": g.get("difficulty", "single_doc"),
                "answer": answer,
                "scores": scores,
                "retrieval": retrieval,
                "rationale": scores.pop("rationale", ""),
            }
        )

    return {
        "judge_fingerprint": llm.fingerprint,
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "k": k,
        "n": len(records),
        "aggregate": _aggregate(records),
        "records": records,
    }


def _judge_one(llm: LLM, gold: dict, answer: str, retrieved: list[str]) -> dict:
    ctx = "\n\n---\n\n".join(retrieved) if retrieved else "(no context retrieved)"
    prompt = JUDGE_TMPL.format(
        q=gold["question"],
        gold=gold.get("gold_answer", ""),
        ctx=ctx[:4000],
        ans=answer or "(no answer)",
    )
    try:
        out = llm.complete_json(JUDGE_SYS, prompt)
    except Exception as e:  # noqa: BLE001 - record the failure, keep going
        return {d: 0.0 for d in JUDGE_DIMENSIONS} | {"rationale": f"judge error: {e}"}
    result: dict[str, Any] = {d: _clamp(out.get(d, 0.0)) for d in JUDGE_DIMENSIONS}
    result["rationale"] = str(out.get("rationale", ""))[:300]
    return result


def _clamp(v) -> float:
    try:
        return round(max(0.0, min(1.0, float(v))), 3)
    except (TypeError, ValueError):
        return 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _aggregate(records: list[dict]) -> dict:
    agg = {d: _mean([r["scores"][d] for r in records]) for d in JUDGE_DIMENSIONS}
    scored = [r["retrieval"] for r in records if r.get("retrieval")]
    for m in RETRIEVAL_METRICS:
        agg[m] = _mean([r[m] for r in scored])
    return agg


def write_results(results: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def read_results(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
