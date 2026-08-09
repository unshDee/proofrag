# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.0] - 2026-08-10

### Added
- Audited, reproducible Python-concurrency case study comparing unique-token overlap
  with SQLite FTS5/BM25 on 30 reviewed questions from hash-checked official sources,
  including raw artifacts, blind A/B results, failure analysis, and a CI fault injection.
- Exact-chunk retrieval matching via `evaluate --exact`, `compare --exact`, and the
  composite Action, alongside the existing Jaccard and semantic matchers.
- Evaluation metadata now records the golden-set fingerprint, matcher, cutoff, and
  versioned judge prompt so regression comparisons can verify their preconditions.

### Fixed
- Evaluation, A/B comparison, and optional scoring backends now reject missing,
  duplicate, or unexpected prediction IDs instead of silently scoring partial runs.
- Provider and judge failures are reported as failed runs instead of valid-looking zero
  scores or ties; golden-set generation likewise fails rather than writing partial data.
- NDCG@k now normalizes against the known ideal gold contexts and gives each gold context
  at most one relevance credit, so missing or duplicate evidence cannot score 1.0.
- `diff` gates backend-specific metrics, treats missing candidate metrics as regressions,
  and rejects incompatible dataset/backend/k/matcher/metric configurations.
- Corpus loading skips symlinks, produces unique relative-path chunk IDs, enforces chunk
  limits for long paragraphs, and no longer ignores a corpus because an ancestor folder
  happens to be named `build`.
- HTTP prediction adapters block cross-origin redirects, all remote plaintext
  requests, and oversized responses; generated HTML/Markdown escapes artifact data.
- LLM JSON parsing handles braces inside strings and rejects non-finite constants;
  Anthropic uses temperature zero and OpenAI defaults to a pinned low-cost snapshot.
- Validation rejects empty sets and non-string context/source lists and warns when a
  multi-document case cites fewer than two distinct sources.

### Changed
- CI and local linting are non-mutating, include case-study scripts, and cover Python
  3.14. Repository-only case-study artifacts are excluded from source distributions.
- Removed tracked DeepEval telemetry state and added the PEP 561 `py.typed` marker.

## [0.7.0] - 2026-06-14

### Added
- `proofrag corpus` inspects corpus loading before generation, including source,
  chunk, character, and extension counts.
- Corpus loading now skips common noisy directories by default, honors `.gitignore`,
  supports `--include`/`--exclude` filters on `corpus` and `generate`, extracts HTML
  text, and can load PDFs with the optional `proofrag[pdf]` extra.
- Generated golden sets now include `context_metadata` for each gold context so
  source path, chunk id, chunk index, character count, and extension survive review.

## [0.6.0] - 2026-06-13

### Added
- New Ragas scoring backend via `evaluate --backend ragas` and the `proofrag[ragas]`
  extra, verified against ragas 0.4.3. Ragas scores faithfulness and factual
  correctness with proofrag's configured LLM provider, and adds answer relevancy
  when OpenAI-compatible embeddings are available. Retrieval metrics, scorecards,
  summaries, `diff`, and CI gates use the same output contract as the built-in and
  DeepEval backends.
- DeepEval backend support is updated for deepeval 4.0.6 and now preserves metric
  reasons in record rationales when DeepEval provides them, so scorecards explain
  weak cases instead of showing scores alone.
- `proofrag validate` checks generated golden sets before they are committed:
  schema/JSONL shape, duplicate ids/questions, answerable cases without gold
  contexts, unanswerable cases that still cite context, source coverage against an
  optional corpus, and a stable file fingerprint. `--strict` fails on warnings for
  CI hygiene, and `--out` writes a JSON validation report.
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
  (`proofrag[deepeval]`, verified against deepeval 4.0.6) swaps generation scoring
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

[Unreleased]: https://github.com/unshDee/proofrag/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/unshDee/proofrag/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/unshDee/proofrag/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/unshDee/proofrag/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/unshDee/proofrag/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/unshDee/proofrag/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/unshDee/proofrag/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/unshDee/proofrag/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/unshDee/proofrag/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/unshDee/proofrag/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/unshDee/proofrag/releases/tag/v0.1.0
