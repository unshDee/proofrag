# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Renamed the project to **proofrag** (was ragproof; "ragproof" read like
  "rag-free"). Package, CLI, and env vars are now `proofrag` / `PROOFRAG_*`.
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
