"""A tiny, dependency-free RAG you can actually run end-to-end.

This is the step you normally adapt to the user's own codebase. It shows the
contract: read the golden set, run a retriever + an LLM per question, and write
predictions.jsonl ({id, answer, retrieved_contexts}). Retrieval here is keyword
overlap — deliberately mediocre so the scorecard has something to flag.

Usage:
    python examples/docs-rag/naive_rag.py \
        --goldenset goldenset.jsonl --corpus examples/docs-rag/corpus \
        --out predictions.jsonl --k 2
"""

from __future__ import annotations

import argparse
import json
import re

from ragproof.corpus import load_corpus
from ragproof.goldenset import read_jsonl
from ragproof.llm import LLM

_WORD = re.compile(r"[a-z0-9]+")


def _score(query: str, chunk: str) -> int:
    q = set(_WORD.findall(query.lower()))
    c = set(_WORD.findall(chunk.lower()))
    return len(q & c)


def retrieve(query: str, chunks: list[dict], k: int) -> list[str]:
    ranked = sorted(chunks, key=lambda c: _score(query, c["text"]), reverse=True)
    return [c["text"] for c in ranked[:k]]


ANSWER_SYS = "Answer the question using ONLY the provided context. If the answer is not in the context, say you don't have that information."


def answer(llm: LLM, question: str, contexts: list[str]) -> str:
    ctx = "\n\n---\n\n".join(contexts)
    prompt = f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer concisely."
    try:
        # reuse the chat path via a tiny JSON-free call
        text = llm._complete(ANSWER_SYS, prompt)  # noqa: SLF001 - example driver
    except Exception as e:  # noqa: BLE001
        text = f"(error: {e})"
    return text.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldenset", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", default="predictions.jsonl")
    ap.add_argument("--k", type=int, default=2)
    args = ap.parse_args()

    chunks = load_corpus(args.corpus)
    golden = read_jsonl(args.goldenset)
    llm = LLM()

    with open(args.out, "w", encoding="utf-8") as f:
        for g in golden:
            ctxs = retrieve(g["question"], chunks, args.k)
            ans = answer(llm, g["question"], ctxs)
            f.write(json.dumps({"id": g["id"], "answer": ans, "retrieved_contexts": ctxs}) + "\n")
    print(f"Wrote predictions -> {args.out}")


if __name__ == "__main__":
    main()
