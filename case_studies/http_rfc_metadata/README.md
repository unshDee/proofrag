# Case study: body-only vs section-metadata BM25 on HTTP RFCs

This completed, reproducible study tests whether adding deterministic RFC structure to
an FTS5 index improves retrieval across seven closely related HTTP standards. Both
variants use the same section-bound 700-character chunks, OR query, SQLite BM25 ranking,
top-five cutoff, answer prompt, and pinned model. Only indexed text changes:

- `body_fts5` indexes the raw chunk body;
- `metadata_fts5` indexes RFC number, document title, nearest section heading, and body.

Both return the same raw chunk format. Indexed metadata never appears in
`retrieved_contexts`, so exact chunk comparison remains fair.

## Result

| Exact metric | Body-only | Metadata | Delta |
| --- | ---: | ---: | ---: |
| Recall@5 | 0.816 | 0.842 | +0.026 |
| Precision@5 | 0.189 | 0.200 | +0.011 |
| NDCG@5 | 0.711 | 0.729 | +0.018 |
| MRR | 0.689 | 0.711 | +0.022 |

Metadata did not meet the predeclared materiality rule of at least +0.05 NDCG@5 with no
more than -0.02 Recall@5. It improved aggregate metrics for the structure-oriented and
multi-document groups but hurt lexical-control ranking. The body-only absolute generation
score was 0.850 versus 0.827 for metadata. Blind comparison returned 4 metadata wins, 1
body win, and 16 ties; the project answer audit disagreed with 3 of the 5 non-ties.

See [`REPORT.md`](REPORT.md) for subgroup tables, per-difficulty generation scores,
failure analysis, tokens, cost, wall times, hashes, and limitations.

## Pinned corpus and golden set

[`sources.json`](sources.json) pins seven exact official RFC Editor plaintext files:
RFCs 9110, 9111, 9112, 9113, 9114, 9204, and 9931. The secure downloader permits only
their exact HTTPS URLs and verifies content type, UTF-8, byte counts, and SHA-256.
Downloaded files remain ignored by Git and are never executed. Source and license terms
are in [`NOTICE.md`](NOTICE.md).

The parser produced 1,859 chunks. The final golden set contains 21 records: 8 structural
single-document, 7 lexical-control single-document, 4 multi-document, and 2
unanswerable. Its SHA-256 is
`72199ecc772d92cd1ac540d503f181812b5817976a04d018c50bca8d26bebe2d`.

Candidate generation was followed by a project-authored semantic audit: 9 records were
accepted, 5 edited over the same evidence, and 7 replaced. This was not independent
human or domain-expert validation. The final audit binds every record and evidence chunk,
requires both chunks for multi-document cases, and verifies literal full-corpus absence
searches for unanswerables.

## Integrity checks

- golden-set audit: pass;
- strict Proofrag validation: 21 records, 7/7 source coverage, no errors or warnings;
- predictions: 21/21 ordered IDs per variant, five contexts each, no empty answers;
- maximum actual five-context bundle: 3,172 characters;
- absolute evaluations: 21/21 records each, exact k=5, zero evaluation errors;
- blind comparison: 21/21 records, exact k=5, zero evaluation errors;
- paid phases: 21 successful usage rows each, no observed retries or partial records;
- safe refusal: both variants refused both unanswerables correctly.

## Exact successful workflow

These commands document the published run while sending a fresh execution to a new
temporary artifact directory. `PROOFRAG_USAGE_LOG` appends records; never point a rerun
at the published artifacts.

Run from the repository root with the project environment installed. Credentials stay in
`.env` and are never printed or committed:

```bash
set -a
source .env
set +a
export PYTHONPATH=src:.
RFC_RERUN_ARTIFACTS="$(mktemp -d "${TMPDIR:-/tmp}/proofrag-rfc-rerun.XXXXXX")"
export RFC_RERUN_ARTIFACTS
```

Optionally repeat candidate generation. Its output can differ and is not reviewed ground
truth; the committed final golden set remains the scoring input:

```bash
export PROOFRAG_PROVIDER=openai
export PROOFRAG_MODEL=gpt-4o-mini-2024-07-18
PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-generation.jsonl" \
  /usr/bin/time -p .venv/bin/python \
  -m case_studies.http_rfc_metadata.generate_goldenset \
  --out "$RFC_RERUN_ARTIFACTS/goldenset.generated.jsonl" \
  --seed 9110 --model gpt-4o-mini-2024-07-18
```

Download or verify the corpus, recreate the committed reviewed file, and validate it:

```bash
.venv/bin/python -m case_studies.http_rfc_metadata.download_corpus
.venv/bin/python -m case_studies.http_rfc_metadata.apply_review
.venv/bin/python -m case_studies.http_rfc_metadata.audit_goldenset
.venv/bin/python -m proofrag.cli validate \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --corpus case_studies/http_rfc_metadata/corpus \
  --out case_studies/http_rfc_metadata/artifacts/validation.json --strict
```

`apply_review.py` is bound to the committed generated-candidate hash and refuses silent
model-output drift.

Run both OpenAI answer variants with separate provider-usage logs:

```bash
export PROOFRAG_PROVIDER=openai
export PROOFRAG_MODEL=gpt-4o-mini-2024-07-18
export OPENAI_LOG=info

PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-predictions-body.jsonl" \
  /usr/bin/time -p .venv/bin/proofrag run \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --callable case_studies.http_rfc_metadata.rag:answer_body_fts5 \
  --out "$RFC_RERUN_ARTIFACTS/predictions-body.jsonl"

PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-predictions-metadata.jsonl" \
  /usr/bin/time -p .venv/bin/proofrag run \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --callable case_studies.http_rfc_metadata.rag:answer_metadata_fts5 \
  --out "$RFC_RERUN_ARTIFACTS/predictions-metadata.jsonl"
```

Evaluate both and run blind comparison with the same pinned Anthropic judge:

```bash
export PROOFRAG_PROVIDER=anthropic
export PROOFRAG_MODEL=claude-haiku-4-5-20251001
export ANTHROPIC_LOG=info

PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-evaluation-body.jsonl" \
  /usr/bin/time -p .venv/bin/proofrag evaluate \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --predictions "$RFC_RERUN_ARTIFACTS/predictions-body.jsonl" \
  --out "$RFC_RERUN_ARTIFACTS/results-body.json" \
  --model claude-haiku-4-5-20251001 --k 5 --exact

PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-evaluation-metadata.jsonl" \
  /usr/bin/time -p .venv/bin/proofrag evaluate \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --predictions "$RFC_RERUN_ARTIFACTS/predictions-metadata.jsonl" \
  --out "$RFC_RERUN_ARTIFACTS/results-metadata.json" \
  --model claude-haiku-4-5-20251001 --k 5 --exact

PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-comparison.jsonl" \
  /usr/bin/time -p .venv/bin/proofrag compare \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --a "$RFC_RERUN_ARTIFACTS/predictions-metadata.jsonl" \
  --b "$RFC_RERUN_ARTIFACTS/predictions-body.jsonl" \
  --a-name metadata_fts5 --b-name body_fts5 \
  --seed 0 --k 5 --exact --model claude-haiku-4-5-20251001 \
  --out "$RFC_RERUN_ARTIFACTS/comparison.json" \
  --html "$RFC_RERUN_ARTIFACTS/comparison.html"
```

Render individual scorecards and summarize provider-reported usage:

```bash
.venv/bin/proofrag report \
  --results "$RFC_RERUN_ARTIFACTS/results-body.json" \
  --out "$RFC_RERUN_ARTIFACTS/scorecard-body.html"
.venv/bin/proofrag report \
  --results "$RFC_RERUN_ARTIFACTS/results-metadata.json" \
  --out "$RFC_RERUN_ARTIFACTS/scorecard-metadata.html"
.venv/bin/python -m case_studies.summarize_usage \
  "$RFC_RERUN_ARTIFACTS" \
  --out "$RFC_RERUN_ARTIFACTS/usage.json"
```

## Artifacts

| File | Contents |
| --- | --- |
| [`goldenset.jsonl`](goldenset.jsonl) | Final audited 21-case golden set |
| [`review.json`](review.json) | Schema-v2 record-level project review and hash binding |
| [`goldenset-audit.json`](artifacts/goldenset-audit.json) | Corpus/evidence/distribution audit |
| [`validation.json`](artifacts/validation.json) | Strict Proofrag validation |
| [`predictions-body.jsonl`](artifacts/predictions-body.jsonl) | Body-only answers and retrieved chunks |
| [`predictions-metadata.jsonl`](artifacts/predictions-metadata.jsonl) | Metadata-index answers and retrieved chunks |
| [`results-body.json`](artifacts/results-body.json) | Body score data |
| [`results-metadata.json`](artifacts/results-metadata.json) | Metadata score data |
| [`comparison.json`](artifacts/comparison.json) | Blind verdicts and comparison metrics |
| [`answer-audit.json`](artifacts/answer-audit.json) | Manual project review of misses, non-ties, and refusals |
| [`usage.json`](artifacts/usage.json) | Token totals and 2026-08-10 list-price estimate |
| [`runtime.json`](artifacts/runtime.json) | Per-phase wall times and run-integrity record |
| [`scorecard-body.html`](artifacts/scorecard-body.html) | Self-contained body scorecard |
| [`scorecard-metadata.html`](artifacts/scorecard-metadata.html) | Self-contained metadata scorecard |
| [`comparison.html`](artifacts/comparison.html) | Self-contained blind-comparison report |

Total paid workflow: 126 calls, 82,887 input tokens, 9,207 output tokens, 201.47 seconds,
and a **$0.082795 list-price estimate**. Provider billing consoles remain authoritative.
