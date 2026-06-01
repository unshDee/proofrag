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

## Install the engine
This skill drives the `proofrag` CLI. Make sure it's on PATH (install once), or run
it ad-hoc with `uvx`:
```bash
uv tool install "proofrag[anthropic]"     # or: pipx install "proofrag[anthropic]"
# no install needed: uvx "proofrag[anthropic]" demo
```
Use `[openai]` instead of `[anthropic]` for an OpenAI-compatible/local backend.
Credentials: `ANTHROPIC_API_KEY` (default, cheap Haiku judge) or `OPENAI_API_KEY`
(`OPENAI_BASE_URL` for local/Ollama). No key? `proofrag demo` renders a sample scorecard.

## The loop
1. **Generate a golden set from the user's corpus.**
   ```bash
   proofrag generate --corpus ./docs --out goldenset.jsonl --n 20
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
   proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
   ```
   Scores groundedness, correctness, completeness, citation_quality (LLM-as-judge,
   pinned + fingerprinted) and rank-aware retrieval metrics — Recall@k, Precision@k,
   NDCG@k, MRR (`--k` sets the cutoff; lexical by default, `--semantic` for embeddings).
   To score generation with DeepEval instead, add `--backend deepeval` (needs the
   `proofrag[deepeval]` extra; metrics become faithfulness / answer_relevancy / correctness).
   Retrieval metrics and everything downstream stay the same.

4. **Report.**
   ```bash
   proofrag report --results results.json --out scorecard.html
   ```
   Self-contained HTML — open it, attach it to a PR, screenshot it. Surfaces overall
   score, per-metric bars, and the weakest cases with the judge's rationale.

## CI gate
Absolute floor:
```bash
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl \
  --out results.json --fail-under 0.7      # exits 1 if overall generation score < 0.7
```
Regression vs a committed baseline (a known-good results.json):
```bash
proofrag diff --baseline baseline.json --candidate results.json --tolerance 0.02
```
To wire this into GitHub Actions, use the bundled composite action
`uses: unshDee/proofrag@v0` (see the repo README / `examples/ci/`). Tell the user to
commit a baseline results.json from a good run, then diff every PR against it.

## A/B comparison (blind)
To compare two variants (vector vs GraphRAG, two prompts, two models), run each over
the **same** golden set to produce two prediction files, then:
```bash
proofrag compare --goldenset goldenset.jsonl \
  --a vector_preds.jsonl --a-name vector \
  --b graphrag_preds.jsonl --b-name graphrag \
  --out comparison.json --html comparison.html
```
The same pinned judge picks the better answer per question, **blind** — answers are
shown in randomized order so it never knows which variant is which. Output: win
counts + per-variant retrieval metrics + an HTML report. Render later with
`proofrag report --results comparison.json` (it auto-detects the comparison format).

## Credibility rules (state these to the user)
- Judge model is pinned; mixing judges makes scores non-comparable.
- LLM-as-judge has variance — treat single-point differences cautiously; the
  retrieval metrics are deterministic and separate retriever from generator faults.
- A low score on `unanswerable` cases means the system hallucinates instead of refusing.

## Reference
- Engine + source: https://github.com/unshDee/proofrag (`src/proofrag/`).
- Runnable end-to-end example: `examples/docs-rag/` in that repo (corpus + naive RAG driver).
- `proofrag --help` lists all commands and flags.
