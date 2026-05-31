# Contributing to proofrag

Thanks for considering a contribution! proofrag is an Agent Skill + Python CLI for
evaluating RAG/LLM apps. This guide covers the dev setup and the workflow.

## Dev setup

Uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/unshDee/proofrag && cd proofrag
uv sync --all-extras          # installs the package + both backends + dev tools
```

Run the checks (CI runs exactly these):

```bash
make test     # or: uv run pytest
make lint     # or: uv run python devtools/lint.py   (ruff + codespell + basedpyright)
```

No API key needed for tests — they're fully offline. For a live end-to-end run, copy
the env template and add a key, then load it:

```bash
cp .env.example .env          # then put your key in .env
set -a && source .env && set +a
```

`.env` is gitignored; never commit real keys.

## Workflow (GitHub Flow)

`main` is always green and releasable. All changes land via pull request.

1. Branch off `main`. Name it by type:
   - `feat/<short-name>` — new capability
   - `fix/<short-name>` — bug fix
   - `docs/<short-name>` — docs only
   - `chore/<short-name>` — tooling, deps, CI, refactors
2. Make focused commits using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat: …`, `fix: …`, `docs: …`, `chore: …`, `refactor: …`, `test: …`.
3. Keep the change scoped — one logical thing per PR.
4. Make sure `make lint` and `make test` pass locally.
5. Open a PR into `main`. CI (lint + tests on Python 3.11–3.13) must pass.
6. PRs are **squash-merged** — your PR becomes one clean commit on `main`.
7. Note user-facing changes under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Project layout

- `skills/proofrag/SKILL.md` — the Agent Skill (the interface agents load)
- `src/proofrag/` — the engine: `corpus`, `goldenset`, `judge`, `metrics`,
  `embeddings`, `scorecard`, `llm`, `cli`
- `examples/docs-rag/` — a runnable end-to-end example
- `.claude-plugin/` — plugin + marketplace manifests
- `tests/` — offline smoke tests

## Releases

Maintainer cuts a [SemVer](https://semver.org/) tag and a GitHub Release from `main`;
that triggers the PyPI publish workflow. Versions are derived from git tags.
