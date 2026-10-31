# Judges, providers and backends

## Providers

The same provider handles generation, judging, `compare` and the DeepEval/Ragas
backends. Set one of:

| Provider | Enable with | Notes |
|----------|-------------|-------|
| Anthropic (default) | `ANTHROPIC_API_KEY` | Haiku judge by default |
| OpenAI | `OPENAI_API_KEY` | |
| OpenAI-compatible / local | `OPENAI_BASE_URL` (Ollama, vLLM, LM Studio) | Key optional; local servers accept any token |

If both keys are set, Anthropic wins. `PROOFRAG_PROVIDER=openai` forces OpenAI.
proofrag does not read `.env` automatically, so run `set -a && source .env && set +a`
first.

| Env | Default | Purpose |
|-----|---------|---------|
| `PROOFRAG_PROVIDER` | auto | Force `anthropic` or `openai` |
| `PROOFRAG_MODEL` | Haiku 4.5 / gpt-4o-mini-2024-07-18 | Judge and generator model |
| `PROOFRAG_EMBED_MODEL` | text-embedding-3-small | Embeddings for `--semantic` |
| `PROOFRAG_USAGE_LOG` | | Append token counts as JSONL (no prompt or answer text) |
| `TYPESAFE_API_KEY` | | Only for `evaluate --backend jev` |

The Anthropic judge samples at the model's default temperature, because current API
versions reject sampling parameters. Its fingerprint records `temperature=default`.

### Embeddings

`--semantic` retrieval matching needs embeddings. Anthropic has no embeddings API, so
this needs `OPENAI_API_KEY` or `OPENAI_BASE_URL` even when the judge is Anthropic.

## Scoring backends

proofrag's own pinned LLM judge is the default. An external library can score
generation instead; retrieval metrics, scorecards and `diff` keep the same output.
Blind `compare` always uses proofrag's judge.

```bash
pip install "proofrag[deepeval]"
proofrag evaluate ... --backend deepeval   # faithfulness, answer_relevancy, correctness (GEval)

pip install "proofrag[ragas]"
proofrag evaluate ... --backend ragas      # faithfulness, factual_correctness (+ answer_relevancy with embeddings)
```

- **DeepEval** (checked against 4.2.8) uses proofrag's model config: an Anthropic key
  selects `AnthropicModel`, an OpenAI key `GPTModel`. The scorecard's weakest-case notes
  keep DeepEval's reasons.
- **Ragas** (checked against 0.4.3) uses the configured provider. Answer relevancy
  needs embeddings, so it runs only when `OPENAI_API_KEY` or `OPENAI_BASE_URL` is set.

Keep a separate baseline per backend, even where metric names match.

## Typed Jev judge

Jev scores existing predictions through the official TypeSafe API. It needs no extra
dependency and no Anthropic or OpenAI key:

```bash
export TYPESAFE_API_KEY=your_key
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl \
  --backend jev --model jev-1.13.0 --out results.json
```

- Each case sends four ordered five-level rubrics in one request. Jev's
  probability-weighted 0–4 scores map to proofrag's 0–1 scale.
- Raw probabilities, confidence, resolved model and token usage stay in the JSON. The
  rubric hash and resolved model identify the judge for `diff`.
- Confidence describes rubric uncertainty, not a measured chance of being right on your
  data. Check representative cases against human labels before you pick CI thresholds.
- An invalid response or a provider failure invalidates the run (exit code 2), and
  the reports flag it.
- The integration is covered by offline contract tests. proofrag has not benchmarked
  hosted accuracy or calibration. See TypeSafe's
  [documented limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) and our
  [research notes](research-v0.9.0.md).

Jev applies only to `evaluate`. `generate` and `compare` still use the Anthropic or
OpenAI-compatible provider.
