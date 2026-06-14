"""Synthesize a golden evaluation set from a corpus.

The wedge: most teams never build evals because hand-writing a balanced,
non-contaminated test set is tedious. This generates one from your own docs,
with difficulty tiers that catch the failure modes papers flag as worst:
multi-document questions and unanswerable (refusal) cases.

Output is versioned JSONL. One record per line:
  {id, question, gold_answer, gold_contexts[], difficulty, sources[]}
"""

from __future__ import annotations

import json
import random

from .llm import LLM

SYS = "You write evaluation questions for a RAG system. Output strict JSON only, no prose."

_SINGLE = '''From this passage write ONE specific question fully answerable from it, and the ideal grounded answer.
Source: {source}
Passage:
"""{text}"""
Return JSON: {{"question": "...", "gold_answer": "..."}}'''

_MULTI = '''From these TWO passages write ONE question that requires BOTH to answer, and the ideal answer that synthesizes them.
Passage A ({src_a}):
"""{text_a}"""
Passage B ({src_b}):
"""{text_b}"""
Return JSON: {{"question": "...", "gold_answer": "..."}}'''

_UNANS = '''Here is a passage from a knowledge base. Write ONE realistic question that is on-topic but CANNOT be answered from this passage (the info is simply not present).
Passage:
"""{text}"""
Return JSON: {{"question": "..."}}'''

_REFUSAL = "I don't have enough information in the provided context to answer that."


def generate(chunks: list[dict], n: int = 20, seed: int = 0, llm: LLM | None = None) -> list[dict]:
    """Generate `n` golden records with ~70% single / 20% multi / 10% unanswerable."""
    llm = llm or LLM()
    rng = random.Random(seed)
    pool = chunks[:]
    rng.shuffle(pool)

    n_single = max(1, round(n * 0.7))
    n_multi = round(n * 0.2) if len(pool) >= 2 else 0
    n_unans = max(0, n - n_single - n_multi)

    records: list[dict] = []
    cursor = 0

    for c in pool[:n_single]:
        out = _try(llm, _SINGLE.format(source=c["source"], text=c["text"][:1500]))
        if out and out.get("question"):
            records.append(
                _record(
                    out["question"],
                    out.get("gold_answer", ""),
                    [c],
                    "single_doc",
                )
            )
    cursor = n_single

    for _ in range(n_multi):
        if cursor + 1 >= len(pool):
            break
        a, b = pool[cursor], pool[cursor + 1]
        cursor += 2
        out = _try(
            llm,
            _MULTI.format(
                src_a=a["source"], text_a=a["text"][:900], src_b=b["source"], text_b=b["text"][:900]
            ),
        )
        if out and out.get("question"):
            records.append(
                _record(
                    out["question"],
                    out.get("gold_answer", ""),
                    [a, b],
                    "multi_doc",
                )
            )

    for c in pool[cursor : cursor + n_unans]:
        out = _try(llm, _UNANS.format(text=c["text"][:1500]))
        if out and out.get("question"):
            records.append(_record(out["question"], _REFUSAL, [], "unanswerable"))

    for i, r in enumerate(records):
        r["id"] = f"q{i:03d}"
    return records


def _try(llm: LLM, prompt: str) -> dict | None:
    try:
        return llm.complete_json(SYS, prompt)
    except Exception:  # noqa: BLE001 - one bad generation shouldn't abort the run
        return None


def _record(question, gold_answer, chunks, difficulty) -> dict:
    gold_contexts = [c["text"] for c in chunks]
    sources = [c["source"] for c in chunks]
    return {
        "id": "",
        "question": question.strip(),
        "gold_answer": gold_answer.strip(),
        "gold_contexts": gold_contexts,
        "difficulty": difficulty,
        "sources": sources,
        "context_metadata": [
            {
                "source": c.get("source", ""),
                "chunk_id": c.get("chunk_id", ""),
                "chunk_index": c.get("chunk_index"),
                "char_count": c.get("char_count", len(c.get("text", ""))),
                "extension": c.get("extension", ""),
            }
            for c in chunks
        ],
    }


def write_jsonl(records: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
