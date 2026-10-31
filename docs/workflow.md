# The evaluation loop

Each step writes a plain file, so you can review it, commit it, or rerun from it.

```bash
proofrag generate --corpus ./docs --out goldenset.jsonl --n 20          # 1. golden set from your docs
proofrag validate --goldenset goldenset.jsonl --corpus ./docs           # 2. check it before committing
proofrag run --goldenset goldenset.jsonl \
  --endpoint http://localhost:8000/ask --out predictions.jsonl          # 3. run your app
proofrag evaluate --goldenset goldenset.jsonl \
  --predictions predictions.jsonl --out results.json                    # 4. judge + retrieval metrics
proofrag report --results results.json --out scorecard.html             # 5. HTML scorecard
proofrag summary --results results.json                                 # optional: Markdown for CI logs
```

`proofrag wizard` (from the `tui` extra) walks through the same steps interactively and
prints these commands at the end.

## Try it on the bundled example

```bash
uv sync --extra anthropic && export ANTHROPIC_API_KEY=...
uv run proofrag generate --corpus examples/docs-rag/corpus --out goldenset.jsonl --n 8
uv run proofrag validate --goldenset goldenset.jsonl --corpus examples/docs-rag/corpus
uv run python examples/docs-rag/naive_rag.py --goldenset goldenset.jsonl \
  --corpus examples/docs-rag/corpus --out predictions.jsonl
uv run proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
uv run proofrag report --results results.json --out scorecard.html
```

## 1. Corpus loading

See what proofrag will read before generating anything:

```bash
proofrag corpus ./docs
proofrag corpus ./docs --include "**/*.md" --exclude "drafts/**"
```

- Skips noisy directories (`.git`, `.venv`, `node_modules`, `dist`, `build`, caches) and
  honors `.gitignore`. Turn the latter off with `--no-gitignore`.
- `--include`, `--exclude`, `--no-gitignore` and `--chunk-chars` also work on `generate`.
- Reads Markdown, plain text, reStructuredText, MDX, HTML and common code files.
  For PDFs: `pip install "proofrag[pdf]"`.
- Every gold context keeps `context_metadata`: source path, chunk id and index,
  character count, extension.

## 2. Golden set validation

Review a generated set before it becomes your baseline. `validate` checks the JSONL
schema, duplicate ids and questions, answerable cases with no gold context,
unanswerable cases that still cite context, difficulty tiers, source coverage, and
computes a stable fingerprint.

```bash
proofrag validate --goldenset goldenset.jsonl --corpus ./docs --out validation.json
```

It exits non-zero on errors; `--strict` fails on warnings too.

The validator catches structure, not meaning. Search the corpus before accepting an
`unanswerable` case, and confirm a `multi_doc` case really needs both sources.

## 3. Prediction adapters

`proofrag run` produces `predictions.jsonl`, the only app-specific step:

```bash
# HTTP: POSTs {"id": "...", "question": "..."}
proofrag run --goldenset goldenset.jsonl --endpoint http://localhost:8000/ask \
  --header "Authorization: Bearer $TOKEN" --out predictions.jsonl

# Python: calls myapp.rag.answer(question)
proofrag run --goldenset goldenset.jsonl --callable myapp.rag:answer --out predictions.jsonl

# Python, record mode: calls myapp.rag.answer(full_golden_record)
proofrag run --goldenset goldenset.jsonl --callable myapp.rag:answer --call-style record \
  --out predictions.jsonl
```

An adapter returns an answer string, an `(answer, contexts)` tuple, or
`{"answer": "...", "retrieved_contexts": ["..."]}`. Endpoints return the same JSON.
For a fully custom driver, see
[`examples/docs-rag/naive_rag.py`](../examples/docs-rag/naive_rag.py).

## 4. Metrics

- **Retrieval:** Recall@k, Precision@k, NDCG@k and MRR show whether the right evidence
  arrived and ranked well. Matching is Jaccard overlap by default. Use `--exact` when
  your app returns the original chunks, or `--semantic` for embedding match
  (see [judges.md](judges.md#embeddings)).
- **Generation:** groundedness, correctness, completeness and context attribution,
  judged by an LLM. Swap in DeepEval, Ragas or Jev with `--backend`
  (see [judges.md](judges.md)).

Every run records the judge, prompt version, matcher, cutoff and golden-set
fingerprint, so `diff` can refuse to compare runs that don't match.

Next: [gate it in CI](ci.md) or [compare two variants](compare.md).
