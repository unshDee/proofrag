"""LLM-as-judge scoring + retrieval metrics → results.json.

Generation quality is scored by a pinned judge model on four dimensions
(groundedness, correctness, completeness, citation_quality). Retrieval quality
is scored separately via token-overlap recall, so a retriever miss is never
blamed on the generator. The judge fingerprint is recorded so two scorecards
are only compared when they used the same judge.
"""

from __future__ import annotations

import datetime as _dt
import json

from .llm import LLM
from .metrics import retrieval_recall

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


def evaluate(goldenset: list[dict], predictions: list[dict], llm: LLM | None = None) -> dict:
    """Join goldenset to predictions by id, judge each, aggregate."""
    llm = llm or LLM()
    preds = {p["id"]: p for p in predictions}

    records: list[dict] = []
    for g in goldenset:
        pred = preds.get(g["id"])
        if pred is None:
            continue
        retrieved = pred.get("retrieved_contexts", []) or []
        answer = pred.get("answer", "")

        scores = _judge_one(llm, g, answer, retrieved)
        recall = retrieval_recall(g.get("gold_contexts", []), retrieved)

        records.append({
            "id": g["id"],
            "question": g["question"],
            "difficulty": g.get("difficulty", "single_doc"),
            "answer": answer,
            "scores": scores,
            "retrieval_recall": round(recall, 3),
            "rationale": scores.pop("rationale", ""),
        })

    return {
        "judge_fingerprint": llm.fingerprint,
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "n": len(records),
        "aggregate": _aggregate(records),
        "records": records,
    }


def _judge_one(llm: LLM, gold: dict, answer: str, retrieved: list[str]) -> dict:
    ctx = "\n\n---\n\n".join(retrieved) if retrieved else "(no context retrieved)"
    prompt = JUDGE_TMPL.format(
        q=gold["question"], gold=gold.get("gold_answer", ""),
        ctx=ctx[:4000], ans=answer or "(no answer)",
    )
    try:
        out = llm.complete_json(JUDGE_SYS, prompt)
    except Exception as e:  # noqa: BLE001 - record the failure, keep going
        return {d: 0.0 for d in JUDGE_DIMENSIONS} | {"rationale": f"judge error: {e}"}
    result = {d: _clamp(out.get(d, 0.0)) for d in JUDGE_DIMENSIONS}
    result["rationale"] = str(out.get("rationale", ""))[:300]
    return result


def _clamp(v) -> float:
    try:
        return round(max(0.0, min(1.0, float(v))), 3)
    except (TypeError, ValueError):
        return 0.0


def _aggregate(records: list[dict]) -> dict:
    if not records:
        return {d: 0.0 for d in JUDGE_DIMENSIONS} | {"retrieval_recall": 0.0}
    agg = {}
    for d in JUDGE_DIMENSIONS:
        agg[d] = round(sum(r["scores"][d] for r in records) / len(records), 3)
    agg["retrieval_recall"] = round(sum(r["retrieval_recall"] for r in records) / len(records), 3)
    return agg


def write_results(results: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def read_results(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
