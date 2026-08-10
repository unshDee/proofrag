# Does doubling retrieved context improve OWASP account-security answers?

## Result

In this 24-question study, doubling one lexical retriever's context from three to six
chunks recovered slightly more reference evidence but did not improve answer quality.
Exact Recall@6 rose from `0.881` to `0.905`, while judged completeness fell from `0.875`
to `0.854` and groundedness fell from `0.917` to `0.875`. In the blind comparison,
top-6 won 5 cases, top-3 won 7, and 12 tied. Top-6 therefore won 41.7% of decided pairs.

The expanded system failed all three pre-registered adoption thresholds. Its formatted
context was 2.04 times larger in aggregate, its answer calls used 78% more input tokens,
and its answer phase cost estimate was 49% higher. This is a small, curated experiment,
so the defensible conclusion is narrow: for this corpus, ranker, prompt, model, and
question set, increasing `k` from 3 to 6 was not worthwhile.

| Headline measure | Top 3 | Top 6 | Top-6 change |
| --- | ---: | ---: | ---: |
| Completeness | 0.875 | 0.854 | -0.021 |
| Groundedness | 0.917 | 0.875 | -0.042 |
| Exact Recall@6 | 0.881 | 0.905 | +0.024 |
| Blind wins | 7 | 5 | -2 |
| Formatted context characters | 33,785 | 68,813 | 2.04× |
| Answer-phase input tokens | 10,460 | 18,634 | 1.78× |
| Answer-phase estimated cost | $0.020720 | $0.030884 | 1.49× |

The run completed on 2026-08-10 with 144 successful API calls, 78,050 reported input
tokens, 10,347 reported output tokens, 206.501 seconds of observed wall time, and an
estimated list-price cost of `$0.077633`. No unexpected retry was observed, and the
retained artifacts contain no partial records or evaluation errors. Provider SDK
transport retries, if any, are not separately exposed by the usage logs.

## Research question and pre-registration

Many RAG systems increase `k` when retrieval misses evidence. More context can recover
supporting passages, but it can also increase cost and distract the generator. This
study changes only retrieval depth while holding the corpus, chunking, ranker, query,
tie-break, prompt, questions, answer model, and judge fixed.

Before seeing the final results, expanded context was defined as worthwhile only if all
three conditions held:

1. completeness improved by at least `0.05`;
2. top-6 won at least 60% of decided blind comparisons; and
3. groundedness did not fall by more than `0.03`.

Retrieval scores, context size, difficulty slices, runtime, tokens, and cost were
secondary measurements. Because top-6 is a strict ranking superset of top-3, a modest
recall increase alone was not treated as evidence that the larger context was better.

## Corpus and provenance

The benchmark uses six official OWASP Cheat Sheet Series Markdown files at immutable
commit [`da4c967e9de854727f72bb2748dd98f76c888b06`](https://github.com/OWASP/CheatSheetSeries/commit/da4c967e9de854727f72bb2748dd98f76c888b06).

| Source | Bytes | SHA-256 prefix |
| --- | ---: | --- |
| Authentication | 38,556 | `5efff7cd4250` |
| Session Management | 54,052 | `bf6d4c21941a` |
| Password Storage | 20,169 | `59e6ce03452b` |
| Forgot Password | 9,566 | `b10808d3a665` |
| Multifactor Authentication | 32,339 | `0c1de91561bd` |
| Credential Stuffing Prevention | 17,596 | `4d3524a77547` |
| **Total** | **172,278** | — |

Exact URLs, byte counts, and full digests are retained in [`sources.json`](sources.json).
The exact upstream CC-BY-SA-4.0 license is hash-verified and retained as
[`LICENSE.owasp.md`](LICENSE.owasp.md); [`ATTRIBUTION.md`](ATTRIBUTION.md) records the
attribution. OWASP does not sponsor or endorse this study.

The downloader accepts only seven exact HTTPS URLs at `raw.githubusercontent.com`,
disables redirects, rejects credentials and query strings, requires plain-text UTF-8,
rejects NUL bytes and symlink outputs, caps individual and total response sizes, and
verifies byte counts and SHA-256 before atomic writes. Markdown is stored as inert text;
its embedded links and images are not fetched or executed.

| Parsed corpus property | Value |
| --- | ---: |
| Sources | 6 |
| Parsed characters | 171,483 |
| 550-character chunks | 414 |
| Average chunk characters | 414 |
| Maximum chunk characters | 550 |

The parsed-character count is the sum of the normalized chunk texts produced by
Proofrag's paragraph-aware chunker, not the raw downloaded byte count.

## Golden-set construction and project audit

Pinned Anthropic model `claude-haiku-4-5-20251001` generated 24 candidates with seed
`0`. The untouched generated set, project-audited set, per-case review decisions, and
published set are retained separately.

The reviewer label is `project audit`. This was a project-level semantic and
exact-evidence audit, not independent or security-domain-expert validation.

| Stage | Count |
| --- | ---: |
| Requested and generated | 24 |
| Accepted unchanged | 13 |
| Edited | 6 |
| Replaced | 5 |
| Published | 24 |

| Difficulty | Cases |
| --- | ---: |
| Single-document | 16 |
| Multi-document | 5 |
| Corpus-unanswerable | 3 |

The audit reloads the pinned corpus with the same 550-character chunker. For every
answerable record it verifies exact context text, source, chunk ID, chunk index,
character count, extension, and metadata cardinality. Each multi-document case requires
at least two sources whose evidence is independently necessary. Each unanswerable case
has at least two literal, case-insensitive absence searches over the concatenated six
files plus a semantic review note; literal absence by itself is not treated as proof of
semantic absence.

| Integrity check | Result |
| --- | ---: |
| IDs present and unique | 24/24 |
| Source coverage | 6/6 |
| Multi-document evidence audit | 5/5 |
| Full-corpus unanswerable audit | 3/3 |
| Strict validation errors/warnings | 0/0 |
| Generated file SHA-256 | `c5607d88e82289f1d5c9758b0e40335ebdb4fcdc356b4eb990ec305089e0c5be` |
| Final file SHA-256 | `43b27c86dc24de0d2e53dd80aae0c90166c2e7f3453e2d1bdaba938affbc308b` |
| Proofrag evaluation fingerprint | `sha256:1a94a5f86e982d96` |

Substantive review changes narrowed unsupported claims, rebuilt all five multi-document
questions around exact evidence, replaced an answerable OIDC/SAML question, and created
three corpus-bounded unanswerable cases. The complete decisions are in
[`review.json`](review.json), and the machine audit is in
[`artifacts/goldenset-audit.json`](artifacts/goldenset-audit.json).

## Systems under test

| Property | Top 3 | Top 6 |
| --- | --- | --- |
| Retriever | SQLite FTS5/BM25 | Same |
| Chunk target and hard maximum | 550 characters | Same |
| Returned contexts | 3 | 6 |
| Query | Lowercase non-stopword terms joined with `OR` | Same |
| Tie-break | Chunk ID | Same |
| Answer model | `claude-haiku-4-5-20251001` | Same |
| Answer prompt | Grounded OWASP answer with filename citations | Same |

For every question, the top-3 contexts exactly equal the first three top-6 contexts.
All 24 prediction IDs were present once, every answer was non-empty, all compact records
contained exactly three contexts, and all expanded records contained exactly six.

Formatted context size includes the source labels and separators supplied to the answer
model. The p95 is the nearest-rank value over 24 questions.

| Formatted context characters | Top 3 | Top 6 |
| --- | ---: | ---: |
| Minimum | 1,013 | 1,886 |
| Median | 1,451.5 | 2,930.5 |
| p95 | 1,710 | 3,286 |
| Maximum | 1,738 | 3,332 |
| Aggregate | 33,785 | 68,813 |

The expanded adapter rejects formatted context above 4,000 characters; the observed
maximum was 3,332. Aggregate expanded context was 2.037 times compact context.

## Evaluation method

OpenAI model `gpt-4o-mini-2024-07-18` judged groundedness, correctness, completeness,
and citation quality at temperature 0. A different provider from the answer model
reduces direct same-model self-preference, but it does not make the judge objective.

Proofrag separately computed Recall@6, Precision@6, NDCG@6, and MRR over the 21
answerable cases using exact chunk equality. Both variants used the same `k=6` and
`--exact` configuration. Top-3 still returned only three chunks; the common cutoff
keeps the scorecards comparable without implying that it retrieved six. Retrieval
metrics are not defined for the three corpus-unanswerable cases.

The absolute-judge fingerprint was
`proofrag-v2/openai:gpt-4o-mini-2024-07-18:temperature=0`. The blind-comparison
fingerprint was
`proofrag-compare-v2/openai:gpt-4o-mini-2024-07-18:temperature=0`. Provider response
models and all returned OpenAI system fingerprints are retained in
[`artifacts/usage.json`](artifacts/usage.json).

## Results

### Generation quality

| Metric | Top 3 | Top 6 | Top-6 change |
| --- | ---: | ---: | ---: |
| Groundedness | 0.917 | 0.875 | -0.042 |
| Correctness | 0.896 | 0.854 | -0.042 |
| Completeness | 0.875 | 0.854 | -0.021 |
| Citation quality | 0.917 | 0.792 | -0.125 |
| Mean of four metrics | 0.901 | 0.844 | -0.057 |

These are the retained raw judge scores. They include the q013 inconsistency discussed
below; no case was rerun or selected based on its score.

### Retrieval

| Metric | Top 3 | Top 6 | Top-6 change |
| --- | ---: | ---: | ---: |
| Exact Recall@6 | 0.881 | 0.905 | +0.024 |
| Exact Precision@6 | 0.333 | 0.175 | -0.158 |
| Exact NDCG@6 | 0.897 | 0.908 | +0.011 |
| MRR | 0.952 | 0.962 | +0.010 |
| Full-evidence cases | 17/21 | 17/21 | 0 |

The extra three chunks eliminated the only zero-recall case, q017, but did not increase
the number of cases with complete reference evidence. Precision fell mechanically
because top-6 returned twice as many chunks while exact relevance remained sparse.

### Results by difficulty

“Overall” is the unweighted mean of the four generation scores. Recall uses exact
matching and excludes unanswerable cases.

| Difficulty | n | Top-3 overall | Top-6 overall | Top-3 recall | Top-6 recall | Full evidence, top-3/top-6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single-document | 16 | 1.000 | 0.953 | 1.000 | 1.000 | 16/16, 16/16 |
| Multi-document | 5 | 0.525 | 0.600 | 0.500 | 0.600 | 1/5, 1/5 |
| Corpus-unanswerable | 3 | 1.000 | 0.667 | n/a | n/a | n/a |

The raw unanswerable difference is entirely driven by q013's inconsistent absolute
judgment. Manual review found correct safe refusals on all three unanswerable questions
for both variants: 3/3 for top-3 and 3/3 for top-6.

### Blind comparison

Top-6 was variant A and top-3 was variant B in the retained result. The judge saw
randomized “Response 1” and “Response 2” labels rather than system names.

| Outcome | Cases | Share of all 24 | Share of 12 decided |
| --- | ---: | ---: | ---: |
| Top-6 wins | 5 | 20.8% | 41.7% |
| Top-3 wins | 7 | 29.2% | 58.3% |
| Ties | 12 | 50.0% | n/a |

| Difficulty | Top-6 wins | Top-3 wins | Ties | Top-6 decided rate |
| --- | ---: | ---: | ---: | ---: |
| Single-document | 1 | 4 | 11 | 20.0% |
| Multi-document | 2 | 2 | 1 | 50.0% |
| Corpus-unanswerable | 2 | 1 | 0 | 66.7% |

With seed `0`, top-6 appeared as Response 1 in 16 cases and top-3 appeared first in 8.
The judge remained blind to system identity, but this realized position imbalance is
another reason not to over-interpret twelve decided pairs.

## Decision against the pre-registration

| Criterion | Required | Observed | Pass? |
| --- | ---: | ---: | --- |
| Completeness improvement | at least +0.050 | -0.021 | No |
| Top-6 decided win rate | at least 60% | 41.7% | No |
| Groundedness change | at least -0.030 | -0.042 | No |

**Decision:** retain top-3 for this configuration. Top-6 improved exact recall slightly,
but the benefit did not translate into better judged answers and came with materially
more context, tokens, and estimated cost.

## Manual answer audit and judge sensitivity

The project audit inspected every non-tie—12 answer pairs in total—which also covered
all three unanswerable cases. The audit was performed against the exact retained
contexts. Its structured record is
[`artifacts/answer-audit.json`](artifacts/answer-audit.json).

### q013: contradictory judge outputs

Both q013 answers explicitly and correctly state that the context does not name a Rust
crate or version. The absolute judge gave top-3 four scores of `1.0`, but gave the
equivalent top-6 refusal four scores of `0.0` and claimed it failed to answer. The blind
judge preferred top-6. This is an identifiable judge inconsistency, not an API error.
The raw scorecard is preserved unchanged.

A transparent sensitivity replaces only q013's four top-6 zeros with ones:

| Top-6 metric | Raw | q013 sensitivity | Top 3 |
| --- | ---: | ---: | ---: |
| Groundedness | 0.875000 | 0.916667 | 0.916667 |
| Correctness | 0.854167 | 0.895833 | 0.895833 |
| Completeness | 0.854167 | 0.895833 | 0.875000 |
| Citation quality | 0.791667 | 0.833333 | 0.916667 |
| Mean of four | 0.843750 | 0.885417 | 0.901042 |

Under that sensitivity, corrected groundedness ties top-3 and completeness improves by
only `0.020833`, still below the required `0.05`. The blind win rate remains 5/12, or
41.7%. The pre-registered decision therefore does not change.

### Case-level gains and failures

- **q017, partial retrieval gain:** top-3 exact recall was 0 and top-6 recall was 0.5.
  The automated judge changed all four generation scores from 0 to 1 and the blind judge
  preferred top-6. Manual review found that top-6 recovered and answered the MFA-factor
  clause, but substituted an MFA recommendation for the gold requirement to check the
  account's current credentials. Top-3 disclosed that the first requirement was absent.
  The measured gain is real at retrieval level but overstated by the absolute judge.

- **q020, completeness gain with a grounding caveat:** top-3 refused the password-work-
  factor half because its first three chunks covered only session entropy. Top-6 added a
  password-storage chunk and gave the intended work-factor-versus-entropy comparison;
  both judges preferred it and its four scores rose from 0 to 1. However, the added
  excerpt discusses upgrading work factors rather than explicitly stating that a higher
  factor increases computation per guess. The answer is factually aligned with the gold
  answer, but that particular mechanism is not fully supported by the retained excerpt.

- **q018, evidence remained incomplete:** both variants retrieved only one of two gold
  contexts, for recall 0.5. Top-6's sixth chunk begins the password-reset-token section
  but ends before the lifecycle list. Both answers therefore covered repository security
  and refused or omitted much of the token lifecycle. The blind comparison tied them;
  the absolute judge scored top-3 partially and top-6 at zero.

- **q019, unsupported generalization:** both variants had recall 0.5. Both distinguished
  client-side certificate authentication from stored-hash protection, but generalized
  beyond the retained evidence: top-6 asserted broad man-in-the-middle protection,
  top-3 asserted prevention of unauthorized access through certificate possession, and
  both framed peppering mainly as password-shucking protection instead of stating the
  gold database-only-compromise boundary. Top-3 won the blind comparison, while its
  absolute scores were all 1 and top-6's were all 0; the manual audit does not support
  treating that contrast as a clean four-point quality difference.

Top-6 also added an alternate email-change process on q002 that was present in the
retrieved text but outside the narrower question, and received unexplained citation
zeros on q008 and q015 despite naming the same source as top-3. These cases reinforce
that one LLM judge should be treated as a measurement instrument with observable noise,
not as ground truth.

No unsafe non-refusal was found among the three corpus-unanswerable cases. “Safe” here
means appropriately refusing based on these six documents; it is not a broader security
certification.

## Runtime, provider tokens, and estimated cost

Usage comes from provider-reported token fields, one distinct append-only log per phase.
Costs use the public list-price snapshot retained in `usage.json` for 2026-08-10;
provider billing consoles remain authoritative. Wall time is observational and includes
network latency.

| Phase | Provider/model | Calls | Wall seconds | Input tokens | Output tokens | Estimated USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Golden generation | Anthropic Haiku 4.5 | 24 | 42.250 | 5,408 | 2,405 | $0.017433 |
| Top-3 answers | Anthropic Haiku 4.5 | 24 | 30.002 | 10,460 | 2,052 | $0.020720 |
| Top-6 answers | Anthropic Haiku 4.5 | 24 | 41.276 | 18,634 | 2,450 | $0.030884 |
| Top-3 evaluation | OpenAI GPT-4o mini | 24 | 35.675 | 14,289 | 1,418 | $0.002994 |
| Top-6 evaluation | OpenAI GPT-4o mini | 24 | 30.650 | 20,937 | 1,454 | $0.004013 |
| Blind comparison | OpenAI GPT-4o mini | 24 | 26.648 | 8,322 | 568 | $0.001589 |
| **Total** | — | **144** | **206.501** | **78,050** | **10,347** | **$0.077633** |

Anthropic accounted for 72 calls, 34,502 input tokens, 6,907 output tokens, and an
estimated `$0.069037`. OpenAI accounted for 72 calls, 43,548 input tokens, 3,440 output
tokens, and an estimated `$0.008596`. No cache-token usage was reported.

## Reproduction

The commands below document the published run and its artifact names. The committed
usage logs already contain 24 rows each and are append-only: **never run these commands
against the published log or output paths**. For a fresh rerun, replace every usage-log
and output path with paths under a new, empty run directory, or use an isolated copy in
which those artifacts are absent.

```bash
uv sync --extra anthropic --extra openai
export PYTHONPATH=src:.

uv run python -m case_studies.owasp_context_depth.download_corpus

set -a
source .env
set +a

export PROOFRAG_PROVIDER=anthropic
export PROOFRAG_MODEL=claude-haiku-4-5-20251001
```

Generate candidates, then reproduce the recorded project-review transformation and
machine audit:

```bash
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

The review gate is deliberately hash-bound. Provider output can vary even with a pinned
model and temperature setting, so a newly generated candidate file may require a fresh
project audit rather than silently reusing the retained decisions.

Run the two answer variants with separate usage logs:

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

Evaluate both variants with the same exact matcher and common cutoff, then compare them
blind with top-6 as A and top-3 as B:

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

Render the scorecards and summarize the six usage logs:

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

## Artifact index

| Artifact | Purpose |
| --- | --- |
| [`sources.json`](sources.json) | Pinned URLs, sizes, and hashes |
| [`LICENSE.owasp.md`](LICENSE.owasp.md), [`ATTRIBUTION.md`](ATTRIBUTION.md) | License and attribution |
| [`goldenset.generated.jsonl`](goldenset.generated.jsonl) | Untouched generated candidates |
| [`goldenset.reviewed.jsonl`](goldenset.reviewed.jsonl) | Project-audited records |
| [`goldenset.jsonl`](goldenset.jsonl) | Published golden set |
| [`review.json`](review.json) | Per-case decisions and evidence bindings |
| [`artifacts/goldenset-audit.json`](artifacts/goldenset-audit.json) | Machine audit result |
| [`artifacts/validation.json`](artifacts/validation.json) | Strict validation and 6/6 coverage |
| [`artifacts/predictions-top3.jsonl`](artifacts/predictions-top3.jsonl) | Compact predictions and contexts |
| [`artifacts/predictions-top6.jsonl`](artifacts/predictions-top6.jsonl) | Expanded predictions and contexts |
| [`artifacts/results-top3.json`](artifacts/results-top3.json), [`artifacts/results-top6.json`](artifacts/results-top6.json) | Raw scorecards |
| [`artifacts/report-top3.html`](artifacts/report-top3.html), [`artifacts/report-top6.html`](artifacts/report-top6.html) | Rendered scorecards |
| [`artifacts/comparison.json`](artifacts/comparison.json), [`artifacts/comparison.html`](artifacts/comparison.html) | Blind comparison and report |
| [`artifacts/answer-audit.json`](artifacts/answer-audit.json) | Manual review and q013 sensitivity |
| [`artifacts/usage.json`](artifacts/usage.json) | Calls, provider tokens, price snapshot, and estimates |
| [`artifacts/runtime.json`](artifacts/runtime.json) | Per-phase wall time |
| [`rag.py`](rag.py) | Shared FTS5 ranker and top-3/top-6 adapters |

## Limitations

- Twenty-four curated questions provide directional evidence, not a universal estimate.
- The review was performed inside the project and was not independent or a formal
  security assessment.
- Six files in one OWASP topic cluster do not represent other corpora or RAG workloads.
- One lexical ranker, one chunk size, one answer model, and one judge were tested.
- Top-6 is a strict superset, so its recall advantage is partly mechanical.
- Exact chunk equality is reproducible but does not credit semantically equivalent text.
- The q013 contradiction and other case-level anomalies show material judge noise.
- “Unanswerable” means absent from these six pinned files, not from all OWASP guidance.
- The immutable 2026-08-10 snapshot will not track later security-guidance changes.
- API outputs may vary despite pinned models and temperature 0.
- Runtime reflects one machine and network path; listed costs are estimates from a
  retained public-price snapshot rather than billing-console totals.
