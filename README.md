# proofrag

[![CI](https://github.com/unshDee/proofrag/actions/workflows/ci.yml/badge.svg)](https://github.com/unshDee/proofrag/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Point your agent at your docs and your RAG app. Get a golden test set, an
LLM-as-judge + retrieval scorecard, and a CI gate — in one command.**

Evaluation is the #1 unmet pain in production RAG/LLM work, and the hardest part
is building a good test set in the first place. `proofrag` generates one from
*your own corpus*, judges your system on it, and emits a shareable HTML scorecard.
It's an [Agent Skill](https://agentskills.io) (works in Claude Code, Codex, Cursor)
**and** a plain Python CLI — wrapping the eval loop, not reinventing the metrics.

<p align="center">
  <img src="docs/scorecard.png" alt="RAG eval scorecard" width="760">
  <br><em>Try it now — no API key needed:</em>
</p>

```bash
git clone https://github.com/unshDee/proofrag && cd proofrag
uv run proofrag demo --out scorecard.html && open scorecard.html
```

> Uses [uv](https://docs.astral.sh/uv/). `uv run` auto-creates the environment on
> first call — nothing else to install. Prefer pip? `pipx install proofrag`.

## Install as an Agent Skill

`proofrag` is a skill (the [agentskills.io](https://agentskills.io) open standard) backed
by a real CLI — so any agent can run *"evaluate my RAG"* and get a reproducible scorecard.

**Claude Code (plugin):**
```
/plugin marketplace add unshDee/proofrag
/plugin install proofrag@proofrag
```
Then ask *"evaluate my RAG"* (auto-triggered) or type `/proofrag`.

**Claude Code (manual)** — `cp -r skills/proofrag ~/.claude/skills/`
**Codex / other agents** — `cp -r skills/proofrag .agents/skills/`

The skill drives the `proofrag` CLI; install it with `uv tool install "proofrag[anthropic]"`
(or `pipx install`, or run ad-hoc via `uvx`). See [AGENTS.md](AGENTS.md) for details.

## Why this exists

> "Running evals aren't the problem — the problem is acquiring or building a
> high-quality, non-contaminated dataset."

Most RAG systems reach production with no evals because writing a balanced golden
set by hand is tedious. So teams ship prompt and model changes blind. This closes
that loop: **change something → re-run → see if quality moved → gate the merge.**

## The loop

```bash
# 1. Generate a golden set from YOUR docs (questions + gold answers + gold contexts)
proofrag generate --corpus ./docs --out goldenset.jsonl --n 20

# 2. Run your RAG over each question -> predictions.jsonl  (one line per question)
#    {"id": "q000", "answer": "...", "retrieved_contexts": ["...", "..."]}
#    See examples/docs-rag/naive_rag.py for a runnable driver.

# 3. Judge: groundedness, correctness, completeness, citation quality + retrieval recall
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json

# 4. Shareable HTML scorecard
proofrag report --results results.json --out scorecard.html
```

Run the whole thing end-to-end against the bundled example:

```bash
uv sync --extra anthropic && export ANTHROPIC_API_KEY=...
uv run proofrag generate --corpus examples/docs-rag/corpus --out goldenset.jsonl --n 8
uv run python examples/docs-rag/naive_rag.py --goldenset goldenset.jsonl --corpus examples/docs-rag/corpus --out predictions.jsonl
uv run proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl --out results.json
uv run proofrag report --results results.json --out scorecard.html
```

## CI gate

```bash
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl \
  --out results.json --fail-under 0.7      # non-zero exit if overall score drops below 0.7
```

## What makes it different

- **Golden set from your corpus** — the wedge. Difficulty tiers: single-doc,
  multi-doc, and *unanswerable* (so you catch hallucination-instead-of-refusal).
- **Retriever vs generator split** — deterministic retrieval recall separates "the
  context never arrived" from "the model fluffed it."
- **Pinned, fingerprinted judge** — every scorecard records its judge model, so you
  never compare scores produced by different judges.
- **Cheap & portable** — defaults to a small model; Anthropic, OpenAI, or local/Ollama
  (`OPENAI_BASE_URL`). Self-contained HTML, zero JS, zero external assets.
- **Agent-native** — drop it in as a skill and say *"evaluate my RAG"*; the agent
  wires your pipeline to the kit.

## Configuration

| Env | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | Anthropic backend (default) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | OpenAI-compatible / local |
| `PROOFRAG_PROVIDER` | auto | `anthropic` or `openai` |
| `PROOFRAG_MODEL` | Haiku / gpt-4o-mini | judge & generator model |

## Roadmap

- [x] v0.1 — golden-set generator, LLM-as-judge, retrieval recall, HTML scorecard, CI gate
- [ ] v0.2 — embedding-based retrieval metrics (NDCG@k / Recall@k / Precision@k)
- [ ] v0.3 — GitHub Action + baseline diffing (regression-aware gate)
- [ ] v0.4 — A/B comparator (vector vs GraphRAG) with blind judging
- [ ] v0.5 — Ragas / DeepEval backends as pluggable scorers

Issues and PRs welcome. MIT licensed.
