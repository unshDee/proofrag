# LlamaIndex RAG adapter

This example builds an in-memory `VectorStoreIndex` from the bundled Markdown
corpus and exposes `answer(question)` for `proofrag run --callable`. It returns
the generated answer together with the source text retrieved by LlamaIndex.
LlamaIndex is an optional example dependency and is not added to proofrag's
runtime dependencies.

## Install

From the repository root:

```bash
uv sync
uv pip install -r examples/llamaindex/requirements.txt
```

Set `OPENAI_API_KEY`, then create and review a small golden set:

```bash
proofrag generate --corpus examples/docs-rag/corpus --out examples/llamaindex/goldenset.jsonl --n 5
proofrag validate --goldenset examples/llamaindex/goldenset.jsonl --corpus examples/docs-rag/corpus
```

Run the adapter from its directory so `app:answer` resolves:

```bash
cd examples/llamaindex
proofrag run --goldenset goldenset.jsonl --callable app:answer --out predictions.jsonl
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
```

The example uses OpenAI's `text-embedding-3-small` embeddings and `gpt-4o-mini`
for generation. The first question builds the in-memory index; later questions
reuse it.
