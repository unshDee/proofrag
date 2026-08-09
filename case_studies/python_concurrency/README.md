# Case study: overlap vs SQLite FTS5 on Python concurrency docs

This reproducible case study compares two deliberately small RAG retrievers over
official Python 3.14 documentation:

- unique token overlap (`overlap`), matching proofrag's bundled naive example;
- SQLite FTS5 with built-in BM25 ranking (`fts5`), still dependency-free.

Both variants use identical 700-character target chunking, retrieve exactly five chunks,
and ask the same pinned Anthropic model to answer the same reviewed golden set.
Proofrag scores generation and retrieval separately, performs a blind pairwise
comparison, then checks a deliberately reversed-BM25 run as a CI regression.

The corpus, audit, retrieval, and metric workflow is reproducible. Paid model outputs
are not byte-for-byte deterministic: Proofrag 0.7.0 did not fix Anthropic sampling, so
fresh generation, answering, judging, or pairwise calls can differ from the frozen
published artifacts even with the same model and seeds.

See [REPORT.md](REPORT.md) for methodology, results, limitations, and publication-ready
tables. Raw JSONL/JSON and self-contained HTML scorecards live in `artifacts/`.

## Trusted corpus

`download_corpus.py` downloads eight UTF-8 reStructuredText files from the official
[`python/cpython`](https://github.com/python/cpython) repository at release `v3.14.7`,
immutable commit `823f0323ee6ec1402088b73bce1a38473cac36dc`. It permits only exact
pinned HTTPS URLs, rejects redirects outside the allowlist, non-text responses, NUL
bytes, oversized downloads, and SHA-256 mismatches.

Corpus contains unmodified CPython documentation. Copyright © Python Software
Foundation and other upstream copyright holders. Python documentation is licensed under the
[Python Software Foundation License Version 2](https://docs.python.org/3.14/license.html).
Examples and recipes are additionally available under the Zero-Clause BSD License.
Complete upstream terms are retained in `LICENSE.python`. Downloaded source files stay
local; published JSONL artifacts contain only the excerpts needed to reproduce the
study. `sources.json` records exact URLs, commit, sizes, and hashes. No PSF endorsement
is implied.

## Reproduce

From repository root:

```bash
uv run python case_studies/python_concurrency/download_corpus.py
uv run python case_studies/python_concurrency/audit_goldenset.py
set -a && source .env && set +a
export PROOFRAG_PROVIDER=anthropic
export PROOFRAG_MODEL=claude-haiku-4-5-20251001
export PYTHONPATH=.

uvx --from "proofrag[anthropic]==0.7.0" proofrag validate \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --corpus case_studies/python_concurrency/corpus \
  --out case_studies/python_concurrency/artifacts/validation.json \
  --strict

uvx --from "proofrag[anthropic]==0.7.0" proofrag run \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --callable case_studies.python_concurrency.rag:answer_overlap \
  --out case_studies/python_concurrency/artifacts/predictions-overlap.jsonl

uvx --from "proofrag[anthropic]==0.7.0" proofrag run \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --callable case_studies.python_concurrency.rag:answer_fts5 \
  --out case_studies/python_concurrency/artifacts/predictions-fts5.jsonl
```

Remaining evaluation, report, comparison, and regression commands are recorded in
`REPORT.md`. API credentials are read only from exported environment variables;
proofrag intentionally does not auto-load `.env`.

`audit_goldenset.py` verifies the downloaded source hashes and embeds Proofrag 0.7.0's
published paragraph-packing semantics. Its q008/q019 evidence therefore cannot shift
when the installed Proofrag chunker changes.

The published measurements are a frozen Proofrag 0.7.0 study. Version 0.8.0 fixes the
NDCG normalization and `diff` precondition gaps the study uncovered; pinning 0.7.0
above preserves the published metric semantics instead of silently changing them.
