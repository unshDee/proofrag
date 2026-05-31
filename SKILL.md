---
name: proofrag
description: Evaluate a RAG or LLM app. Use when the user wants to test, score, benchmark, or catch regressions in a retrieval/RAG/LLM system, generate an evaluation/golden dataset from their docs, measure hallucination/groundedness/correctness, or gate CI on answer quality. Generates a golden set from the user's own corpus, runs LLM-as-judge plus retrieval metrics, and produces a shareable HTML scorecard.
---

# proofrag

Turn "did my change make the RAG better or worse?" into one reproducible command.
You (the agent) wire the user's app to the kit; the kit does dataset generation,
judging, and reporting.

## When to use
- User changed a prompt, model, chunker, embedder, or retriever and wants to know if quality moved.
- User has docs/a knowledge base but no evaluation set.
- User wants a hallucination/groundedness number, or a CI gate on answer quality.

## Install
```bash
pip install -e .            # from this repo
# backend (pick one): pip install 'proofrag[anthropic]'  OR  'proofrag[openai]'
```
Credentials: `ANTHROPIC_API_KEY` (default, cheap Haiku judge) or `OPENAI_API_KEY`
(`OPENAI_BASE_URL` for local/Ollama). No key? `rag-eval demo` renders a sample scorecard.

## The loop
1. **Generate a golden set from the user's corpus.**
   ```bash
   rag-eval generate --corpus ./docs --out goldenset.jsonl --n 20
   ```
   Produces JSONL: `{id, question, gold_answer, gold_contexts[], difficulty, sources[]}`
   with tiers `single_doc` / `multi_doc` / `unanswerable`. Commit this file — it is versioned.

2. **Run the user's RAG over every question to produce predictions.**
   This is the step you adapt to their codebase. For each golden record, call their
   pipeline and emit one line to `predictions.jsonl`:
   ```json
   {"id": "q000", "answer": "<system answer>", "retrieved_contexts": ["<chunk>", "..."]}
   ```
   Match `id` to the golden set. `retrieved_contexts` are the chunks their retriever
   returned (used for retrieval recall). If you can't find their entrypoint, ask the
   user where their "ask a question" function lives, then write a small driver script.

3. **Judge.**
   ```bash
   rag-eval evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
   ```
   Scores groundedness, correctness, completeness, citation_quality (LLM-as-judge,
   pinned + fingerprinted) and retrieval_recall (token-overlap, no embeddings).

4. **Report.**
   ```bash
   rag-eval report --results results.json --out scorecard.html
   ```
   Self-contained HTML — open it, attach it to a PR, screenshot it. Surfaces overall
   score, per-metric bars, and the weakest cases with the judge's rationale.

## CI gate
```bash
rag-eval evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl \
  --out results.json --fail-under 0.7      # exits 1 if overall generation score < 0.7
```

## A/B comparison
Run steps 2–4 for variant A and variant B (e.g. vector vs GraphRAG, or two prompts),
keeping the **same goldenset and the same judge model**, then compare the two
`results.json` aggregates. Never compare scorecards produced by different judge
models — the fingerprint in each scorecard tells you whether that's safe.

## Credibility rules (state these to the user)
- Judge model is pinned; mixing judges makes scores non-comparable.
- LLM-as-judge has variance — treat single-point differences cautiously; the
  retrieval_recall metric is deterministic and separates retriever from generator faults.
- A low score on `unanswerable` cases means the system hallucinates instead of refusing.

## Files
- `proofrag/` — `corpus`, `goldenset`, `judge`, `metrics`, `scorecard`, `llm`, `cli`.
- `examples/docs-rag/` — a runnable end-to-end example (corpus + naive RAG driver).
