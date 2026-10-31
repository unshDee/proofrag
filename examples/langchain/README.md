# LangChain RAG adapter

This example builds an in-memory vector index from the bundled Markdown corpus,
uses OpenAI embeddings and a chat model, and exposes the `answer(question)` callable
that `proofrag run` expects. The LangChain packages are optional and do not become
dependencies of proofrag.

## Run it

From the repository root, install proofrag and the example dependencies:

```bash
uv sync
uv pip install -r examples/langchain/requirements.txt
```

Set `OPENAI_API_KEY`, then generate and review a small golden set. With only this key
set, proofrag also uses OpenAI for generation and evaluation:

```bash
export OPENAI_API_KEY=...
# PowerShell: $env:OPENAI_API_KEY = "..."
cd examples/langchain
uv run proofrag generate --corpus ../docs-rag/corpus --out goldenset.jsonl --n 8
uv run proofrag validate --goldenset goldenset.jsonl --corpus ../docs-rag/corpus
```

Run the adapter and evaluate its predictions:

```bash
uv run proofrag run --goldenset goldenset.jsonl --callable app:answer --out predictions.jsonl
uv run proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
```

`OPENAI_API_KEY` is used by LangChain embeddings and chat. Set `OPENAI_MODEL` to choose
a different chat model; it defaults to `gpt-4o-mini`. proofrag uses the same OpenAI key
for golden-set generation and evaluation. See the [environment template](../../.env.example)
for other provider options.
