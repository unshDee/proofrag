# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `proofrag summary` renders a compact markdown score summary for CI logs and
  GitHub Actions job summaries, including aggregate metrics and weakest cases.
- The GitHub Action now writes a job summary and uploads `results.json` plus the
  HTML scorecard as a workflow artifact by default. It also renders those artifacts
  even when an absolute or regression gate fails, so failed PRs are easier to debug.
- `proofrag run` generates `predictions.jsonl` directly from a golden set by calling
  either an HTTP endpoint (`--endpoint`, POSTing `{id, question}`) or a Python
  callable (`--callable module:function`, with optional `--call-style record`).
  Adapters may return a string, `(answer, contexts)`, or a dict with
  `answer`/`retrieved_contexts`, making the first integration step much lighter
  for real RAG apps.

## [0.5.2] - 2026-06-01

### Changed
- Redesigned the HTML scorecard and blind A/B comparison reports with a clean,
  professional light theme. Adopts shadcn-style design tokens (neutral palette,
  thin borders, soft shadows, tabular numerals) and uses color only to flag weak
  scores instead of saturating every metric. Still zero-dependency, self-contained
  static HTML — no JS, no external assets — so it stays drop-in for PRs and CI
  artifacts.

## [0.5.1] - 2026-06-01

### Changed
- Provider completeness across the whole pipeline (generate / judge / compare /
  `--semantic` / DeepEval backend) for Anthropic, OpenAI, and OpenAI-compatible
  local endpoints. `OPENAI_BASE_URL` now works **without** an API key (Ollama,
  vLLM, LM Studio); provider auto-detect picks OpenAI when only a base URL is set;
  the DeepEval backend honors `OPENAI_BASE_URL` via `GPTModel(base_url=...)`.
- Trimmed the sdist (~1 MB of README demo media no longer shipped in the package).

## [0.5.0] - 2026-06-01

### Added
- Pluggable scoring backends via `evaluate --backend`. New **DeepEval** backend
  (`proofrag[deepeval]`, verified against deepeval 4.0.5) swaps generation scoring
  to faithfulness / answer_relevancy / correctness (GEval), using the same model
  config as proofrag. Retrieval metrics, scorecard, `diff`, and `compare` are
  unchanged. The scorecard now renders each backend's metric set dynamically.

## [0.4.0] - 2026-06-01

### Added
- `proofrag compare` — blind A/B comparison of two RAG variants over the same
  golden set: the pinned judge picks the better answer per question with answers
  shown in randomized order (position bias shuffled out), plus per-variant retrieval
  metrics and a shareable HTML report. `proofrag report` auto-detects the format,
  and `proofrag demo --compare` renders a sample with no API key.

## [0.3.0] - 2026-06-01

### Added
- `proofrag diff` — compare a run against a committed baseline results.json and
  fail on regression (per-metric delta table, `--tolerance`, refuses to compare
  across different judge models unless `--allow-judge-mismatch`).
- Reusable composite GitHub Action (`action.yml`): `uses: unshDee/proofrag@v0`
  installs the CLI, evaluates, writes the scorecard, and gates on the absolute
  floor and/or the baseline. Example workflow in `examples/ci/`.

## [0.2.0] - 2026-05-31

### Added
- Rank-aware retrieval metrics: Recall@k, Precision@k, NDCG@k, MRR, with a
  pluggable relevance matcher (`metrics.py`).
- Optional embedding-based semantic matcher (`embeddings.py`); `evaluate --semantic`
  and `--k` to set the cutoff.
- Scorecard split into Generation and Retrieval panels with an NDCG@k headline.
- Animated demo GIF of the full eval loop (`docs/demo.gif`, reproducible via
  `docs/demo.tape`).
- Installable as a Claude Code plugin: `.claude-plugin/` manifests, `/proofrag`
  slash command, `AGENTS.md`, and skill-discovery layout under `skills/proofrag/`.

### Changed
- Unanswerable cases skip retrieval scoring so they don't skew the averages.

## [0.1.0] - 2026-05-31

### Added
- Golden-set generator from a corpus, with single-doc / multi-doc / unanswerable
  difficulty tiers.
- LLM-as-judge scoring (groundedness, correctness, completeness, citation quality),
  pinned and fingerprinted.
- Self-contained, shareable HTML scorecard, plus a keyless `demo` command.
- `--fail-under` CI gate; provider-agnostic backend (Anthropic / OpenAI / local).

[Unreleased]: https://github.com/unshDee/proofrag/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/unshDee/proofrag/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/unshDee/proofrag/releases/tag/v0.1.0
