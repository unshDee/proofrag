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

2. **Validate the golden set before committing it.**
   ```bash
   proofrag validate --goldenset goldenset.jsonl --corpus ./docs --out validation.json
   ```
   This checks the JSONL contract, duplicate ids/questions, answerable cases without
   gold contexts, unanswerable cases that still cite context, source coverage, and a
   stable fingerprint. It exits non-zero on hard errors; add `--strict` to fail on
   warnings too.

3. **Run the user's RAG over every question to produce predictions.**
   Prefer `proofrag run` when the app exposes a local HTTP endpoint or Python callable:
   ```bash
   proofrag run --goldenset goldenset.jsonl \
     --endpoint http://localhost:8000/ask \
     --out predictions.jsonl

   proofrag run --goldenset goldenset.jsonl \
     --callable myapp.rag:answer \
     --out predictions.jsonl
   ```
   HTTP mode POSTs `{"id": "...", "question": "..."}`. Callable mode calls
   `answer(question)` by default; add `--call-style record` to pass the full golden
   record. The adapter may return an answer string, `(answer, contexts)`, or:
   ```json
   {"id": "q000", "answer": "<system answer>", "retrieved_contexts": ["<chunk>", "..."]}
   ```
   `retrieved_contexts` are the chunks their retriever returned (used for retrieval
   metrics). If neither adapter fits, write a small driver script that emits the same
   JSONL shape. If you can't find their entrypoint, ask the user where their "ask a
   question" function lives.

4. **Judge.**
   ```bash
   proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
   ```
   Scores groundedness, correctness, completeness, citation_quality (LLM-as-judge,
   pinned + fingerprinted) and rank-aware retrieval metrics — Recall@k, Precision@k,
   NDCG@k, MRR (`--k` sets the cutoff; lexical by default, `--semantic` for embeddings).
   To score generation with DeepEval instead, add `--backend deepeval` (needs the
   `proofrag[deepeval]` extra; metrics become faithfulness / answer_relevancy / correctness).
   Retrieval metrics and everything downstream stay the same. DeepEval metric reasons,
   when available, are preserved in the scorecard's weakest-case notes.

5. **Report.**
   ```bash
   proofrag report --results results.json --out scorecard.html
   proofrag summary --results results.json   # optional markdown for CI/logs
   ```
   Self-contained HTML — open it, attach it to a PR, screenshot it. Surfaces overall
   score, per-metric bars, and the weakest cases with the judge's rationale. The
   markdown summary gives CI systems a compact score table without opening the HTML.

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
commit a baseline results.json from a good run, then diff every PR against it. The
action writes a GitHub Actions job summary and uploads the scorecard/results artifact
by default, including when a gate fails.

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
