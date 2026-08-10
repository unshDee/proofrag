# Case study: compact vs expanded OWASP context

This completed case study asks whether doubling the same SQLite FTS5/BM25 retriever
from three to six chunks improves grounded answers about OWASP account-security
guidance. It did not: top-6 recovered slightly more exact evidence, but top-3 produced
better raw generation scores and won more blind comparisons.

Read [`REPORT.md`](REPORT.md) for the website-ready analysis, case-level audit, cost
table, sensitivity analysis, and limitations.

## Outcome

| Measure | Top 3 | Top 6 |
| --- | ---: | ---: |
| Groundedness | 0.917 | 0.875 |
| Correctness | 0.896 | 0.854 |
| Completeness | 0.875 | 0.854 |
| Citation quality | 0.917 | 0.792 |
| Exact Recall@6 | 0.881 | 0.905 |
| Exact Precision@6 | 0.333 | 0.175 |
| Blind wins | 7 | 5 |

The blind result was 5 top-6 wins, 7 top-3 wins, and 12 ties, so top-6 won 41.7%
of decided pairs. Expanded context failed all three pre-registered thresholds:

- completeness changed by `-0.021`, below the required `+0.050`;
- top-6's decided win rate was `41.7%`, below the required `60%`; and
- groundedness changed by `-0.042`, worse than the allowed `-0.030`.

The result is scoped to this corpus and configuration. It does not establish that
smaller context is generally better.

## Fixed configuration

- **Compact variant:** SQLite FTS5/BM25, top three chunks.
- **Expanded variant:** the same index and ranking, top six chunks.
- **Chunking:** paragraph-aware, 550-character hard maximum.
- **Answer model:** Anthropic `claude-haiku-4-5-20251001`.
- **Judge:** OpenAI `gpt-4o-mini-2024-07-18`, temperature 0.
- **Evaluation:** both variants use `k=6` and exact chunk equality.
- **Blind comparison:** top-6 is A, top-3 is B, seed `0`.

For all 24 questions, top-3 is the exact first-three prefix of top-6. Every compact
prediction has three contexts, every expanded prediction has six, and expanded formatted
context never exceeds the adapter's 4,000-character limit. Aggregate formatted context
grew from 33,785 to 68,813 characters, or 2.037×.

## Trusted corpus and review disclosure

The corpus consists of six official OWASP Cheat Sheet Series Markdown files pinned to
commit [`da4c967e9de854727f72bb2748dd98f76c888b06`](https://github.com/OWASP/CheatSheetSeries/commit/da4c967e9de854727f72bb2748dd98f76c888b06).
[`sources.json`](sources.json) records the seven exact allowlisted URLs—the six files
plus license—along with byte counts and SHA-256 hashes. [`ATTRIBUTION.md`](ATTRIBUTION.md)
and [`LICENSE.owasp.md`](LICENSE.owasp.md) retain attribution and the verified upstream
CC-BY-SA-4.0 license. OWASP does not sponsor or endorse this study.

The downloader disables redirects, rejects credentials, query strings, NUL bytes,
symlink outputs, invalid UTF-8, unexpected content types, oversized responses, and any
size or digest mismatch. Downloaded Markdown is treated as inert text.

The final golden set contains 24 project-audited cases: 16 single-document, five
multi-document, and three corpus-unanswerable. The reviewer label is `project audit`.
This is a project-level semantic and exact-evidence audit, not independent or
security-domain-expert validation.

The audit verifies every context and metadata field against Proofrag's exact 550-character
chunks, enforces all six sources, checks that each multi-document question genuinely
needs multiple sources, and tests at least two literal absence queries per unanswerable
case against the complete six-file corpus.

| Audit property | Result |
| --- | ---: |
| Accepted unchanged / edited / replaced | 13 / 6 / 5 |
| Source coverage | 6/6 |
| Multi-document audit | 5/5 |
| Unanswerable audit | 3/3 |
| Strict validation errors/warnings | 0/0 |
| Final SHA-256 | `43b27c86dc24de0d2e53dd80aae0c90166c2e7f3453e2d1bdaba938affbc308b` |

## Reproduce

The commands below document the published run and its artifact names. The committed
usage logs already contain 24 rows each and are append-only: **never run these commands
against the published log or output paths**. For a fresh rerun, replace every usage-log
and output path with paths under a new, empty run directory, or use an isolated copy in
which those artifacts are absent. Then install both provider extras, load the pinned
corpus, and expose the package and case-study modules:

```bash
uv sync --extra anthropic --extra openai
export PYTHONPATH=src:.
uv run python -m case_studies.owasp_context_depth.download_corpus

set -a
source .env
set +a
```

### Generate and audit the golden set

```bash
export PROOFRAG_PROVIDER=anthropic
export PROOFRAG_MODEL=claude-haiku-4-5-20251001

PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-generation.jsonl \
uv run proofrag generate \
  --corpus case_studies/owasp_context_depth/corpus \
  --out case_studies/owasp_context_depth/goldenset.generated.jsonl \
  --n 24 --seed 0 --chunk-chars 550 \
  --model claude-haiku-4-5-20251001

uv run python -m case_studies.owasp_context_depth.prepare_review
uv run python -m case_studies.owasp_context_depth.audit_goldenset

uv run proofrag validate \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --corpus case_studies/owasp_context_depth/corpus --strict \
  --out case_studies/owasp_context_depth/artifacts/validation.json
```

The recorded review is bound to the generated file's full SHA-256. A fresh model response
that differs from the retained candidates requires a fresh project audit; the scripts
will not silently apply old decisions to changed input.

### Run top-3 and top-6 answers

```bash
PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-answer-top3.jsonl \
uv run proofrag run \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --callable case_studies.owasp_context_depth.rag:answer_top3 \
  --out case_studies/owasp_context_depth/artifacts/predictions-top3.jsonl

PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-answer-top6.jsonl \
uv run proofrag run \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --callable case_studies.owasp_context_depth.rag:answer_top6 \
  --out case_studies/owasp_context_depth/artifacts/predictions-top6.jsonl
```

### Evaluate at the common exact cutoff

```bash
export PROOFRAG_PROVIDER=openai
export PROOFRAG_MODEL=gpt-4o-mini-2024-07-18

PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-evaluate-top3.jsonl \
uv run proofrag evaluate \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --predictions case_studies/owasp_context_depth/artifacts/predictions-top3.jsonl \
  --out case_studies/owasp_context_depth/artifacts/results-top3.json \
  --model gpt-4o-mini-2024-07-18 --k 6 --exact

PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-evaluate-top6.jsonl \
uv run proofrag evaluate \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --predictions case_studies/owasp_context_depth/artifacts/predictions-top6.jsonl \
  --out case_studies/owasp_context_depth/artifacts/results-top6.json \
  --model gpt-4o-mini-2024-07-18 --k 6 --exact

PROOFRAG_USAGE_LOG=case_studies/owasp_context_depth/artifacts/usage-compare.jsonl \
uv run proofrag compare \
  --goldenset case_studies/owasp_context_depth/goldenset.jsonl \
  --a case_studies/owasp_context_depth/artifacts/predictions-top6.jsonl \
  --b case_studies/owasp_context_depth/artifacts/predictions-top3.jsonl \
  --a-name top6 --b-name top3 --seed 0 --k 6 --exact \
  --model gpt-4o-mini-2024-07-18 \
  --out case_studies/owasp_context_depth/artifacts/comparison.json \
  --html case_studies/owasp_context_depth/artifacts/comparison.html
```

### Render and summarize

```bash
uv run proofrag report \
  --results case_studies/owasp_context_depth/artifacts/results-top3.json \
  --out case_studies/owasp_context_depth/artifacts/report-top3.html

uv run proofrag report \
  --results case_studies/owasp_context_depth/artifacts/results-top6.json \
  --out case_studies/owasp_context_depth/artifacts/report-top6.html

uv run python case_studies/summarize_usage.py \
  case_studies/owasp_context_depth/artifacts \
  --out case_studies/owasp_context_depth/artifacts/usage.json
```

The retained run contains 144 completed usage rows, complete 24-record outputs for every
phase, and no evaluation errors. No unexpected retry was observed; provider SDK
transport retries, if any, are not separately exposed by the usage logs. Provider usage
was 78,050 input tokens and 10,347 output tokens; the retained 2026-08-10 price snapshot
estimates `$0.077633`. Provider billing consoles remain authoritative.

## Artifacts

| File | Contents |
| --- | --- |
| [`goldenset.generated.jsonl`](goldenset.generated.jsonl) | Untouched model candidates |
| [`goldenset.reviewed.jsonl`](goldenset.reviewed.jsonl) | Project-audited cases |
| [`goldenset.jsonl`](goldenset.jsonl) | Published 24-case set |
| [`review.json`](review.json) | Per-case decisions and evidence bindings |
| [`artifacts/goldenset-audit.json`](artifacts/goldenset-audit.json) | Audit result |
| [`artifacts/validation.json`](artifacts/validation.json) | Strict validation and source coverage |
| [`artifacts/predictions-top3.jsonl`](artifacts/predictions-top3.jsonl) | Compact answers and contexts |
| [`artifacts/predictions-top6.jsonl`](artifacts/predictions-top6.jsonl) | Expanded answers and contexts |
| [`artifacts/results-top3.json`](artifacts/results-top3.json) | Compact raw scorecard |
| [`artifacts/results-top6.json`](artifacts/results-top6.json) | Expanded raw scorecard |
| [`artifacts/report-top3.html`](artifacts/report-top3.html) | Compact HTML scorecard |
| [`artifacts/report-top6.html`](artifacts/report-top6.html) | Expanded HTML scorecard |
| [`artifacts/comparison.json`](artifacts/comparison.json) | Blind pairwise result |
| [`artifacts/comparison.html`](artifacts/comparison.html) | Blind comparison report |
| [`artifacts/answer-audit.json`](artifacts/answer-audit.json) | Manual non-tie audit and q013 sensitivity |
| [`artifacts/usage.json`](artifacts/usage.json) | Calls, tokens, model responses, and estimated cost |
| [`artifacts/runtime.json`](artifacts/runtime.json) | Per-phase wall time |

## Judge caveat

For q013, both variants correctly refused a Rust crate/version question that the corpus
cannot answer. The absolute judge awarded top-3 four ones but top-6 four zeros, while the
blind judge preferred top-6. The raw result is preserved. A sensitivity that corrects
only those four top-6 scores still does not satisfy the pre-registered completeness or
blind-preference thresholds. See the report and structured answer audit for details.
