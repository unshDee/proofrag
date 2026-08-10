# Does RFC section metadata improve BM25 retrieval across HTTP standards?

**Case-study date:** 2026-08-10<br>
**Study release:** Proofrag v0.8.0<br>
**Golden-set SHA-256:** `72199ecc772d92cd1ac540d503f181812b5817976a04d018c50bca8d26bebe2d`<br>
**Corpus manifest:** [`sources.json`](sources.json)

## Result in one paragraph

Adding RFC number, document title, and section heading to the FTS5 index produced a
small deterministic retrieval improvement, but not the predeclared material win. Exact
NDCG@5 rose from **0.711 to 0.729** (+0.018) and Recall@5 from **0.816 to 0.842**
(+0.026); the required NDCG gain was +0.05. Metadata improved aggregate metrics for the
multi-document and structure-oriented groups, while lexical-control NDCG fell.
The body-only variant also received the higher absolute generation score, 0.850 versus
0.827. A blind judge chose metadata four times, body once, and tied 16 times, but a
project audit disagreed with three of those five non-ties. On this small, project-reviewed
HTTP corpus, section metadata looks useful for particular structured queries, not like a
demonstrated general replacement for body-only BM25.

## Question and predeclared decision rule

Both systems use identical RFC files, 700-character section-bound chunks, query terms,
SQLite FTS5/BM25 ranking, top-five cutoff, answer prompt, and pinned answer model. The
only change is indexed text:

- `body_fts5`: raw chunk body;
- `metadata_fts5`: `RFC + document title + nearest section heading + body`.

Both return only the same raw chunk bodies. Metadata is never returned to the answer
model or evaluator as retrieved evidence.

The primary metric was exact NDCG@5. Metadata would count as materially better only if
NDCG@5 improved by at least 0.05 while Recall@5 did not fall by more than 0.02. The
observed NDCG gain was +0.018 and Recall changed by +0.026, so the decision is
**threshold not met**.

## Corpus and provenance

The corpus contains seven immutable plaintext publications downloaded from the official
RFC Editor host. [`download_corpus.py`](download_corpus.py) enforces an exact HTTPS URL
allowlist, same-host redirects, `text/plain`, UTF-8, byte limits, no NUL bytes or
symlinks, and exact byte-count and SHA-256 verification. Raw files are ignored by Git
and never executed.

The deterministic parser skips publication front matter, stops before references, binds
text to the nearest recognized section heading, and hard-caps chunks at 700 characters.
It produced 1,859 chunks from 1,165,186 bytes. RFC 9931 is included because it updates
HTTP/1.1 requirements in RFC 9112. Errata and later update metadata are outside this
pinned publication snapshot. Source terms are documented in [`NOTICE.md`](NOTICE.md).

| RFC | Title | Bytes | SHA-256 |
| ---: | --- | ---: | --- |
| 9110 | HTTP Semantics | 502,941 | `21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a` |
| 9111 | HTTP Caching | 84,477 | `aeb52adb3279d5f23dae34f68af11bd5cef0a0aff7ffcd014c9ca93c5302cf3e` |
| 9112 | HTTP/1.1 | 109,913 | `e4f426bac6206b67fdf9e0da826154f70588db2133a0a86b15cde4ff725d8937` |
| 9113 | HTTP/2 | 191,811 | `a00ef91b64e111a282e77ec66980f5242e77c0bb5e33e0927e3b6757080506de` |
| 9114 | HTTP/3 | 155,206 | `6b84555c88eeebcf5d2b2e1d9d7b58630abc97ab877b2cf62dee4cd635db34e4` |
| 9204 | QPACK: Field Compression for HTTP/3 | 99,258 | `926b4d7e9772b5c316fe87a1e160f5ced118101459ede5b13d11bf9a9273c931` |
| 9931 | Security Considerations for Optimistic Protocol Transitions in HTTP/1.1 | 21,580 | `692ae7b87ee5eba34c96f664595357ae1dd498b75fb2cd49e3ae29567da01fc8` |

## Golden-set construction and project audit

The 21-case design was fixed before evaluation:

| Group | Cases | Purpose |
| --- | ---: | --- |
| Structure-dependent single-document | 8 | Questions expected to benefit from headings or RFC identity |
| Lexical-control single-document | 7 | Questions answerable through body terms without structural help |
| Multi-document | 4 | Questions requiring two named RFC chunks |
| Unanswerable | 2 | Questions absent from the full seven-RFC corpus |

Single-document coverage is RFC 9110 three times and each other RFC twice. The four
multi-document pairs are 9110+9111, 9112+9931, 9113+9114, and 9114+9204.

OpenAI generated candidate cases; they were not accepted as ground truth without review.
The repository's project-authored semantic audit accepted 9 objects unchanged, edited 5
over the same evidence, and replaced 7. Every answerable record is bound to exact parsed
chunks. Each multi-document record has two distinct RFC chunks and was checked for the
need for both. The two unanswerables have recorded literal absence searches over all
1,859 chunks.

This was **project audit**, not independent human validation and not domain-expert
certification. The schema-v2 [`review.json`](review.json) binds every generated and final
record hash. [`goldenset-audit.json`](artifacts/goldenset-audit.json) passed with no
errors, and strict [`validation.json`](artifacts/validation.json) reported 21 records,
7/7 source coverage, no errors, and no warnings.

| Bound input | SHA-256 |
| --- | --- |
| Corpus manifest | `584a8ad2b2942b94d1db5dc137e3c5690d94c5d7da1de178bf8497d6f65d14bc` |
| Generated candidates | `cad443de0cd98135b688e2b8b5febc8ae113c0d60c26d338ebd973809aa4640b` |
| Final golden set | `72199ecc772d92cd1ac540d503f181812b5817976a04d018c50bca8d26bebe2d` |
| Project review | `2eb2dafede971ee90ad1c47a48d866a8141ba38f428ce073bb7c63d928936cba` |
| Golden-set audit | `7577e4b07f25212661cb32987e672abba6d299ab1d57b83566045c6bb07d5be0` |
| Strict validation | `c9e23df6de43b13f33c61bdeda62c9115a29377c5ba8b6f97bfec32d86332f9f` |

## Prediction and evaluation integrity

| Check | Body-only | Metadata |
| --- | ---: | ---: |
| Ordered unique IDs | 21/21 | 21/21 |
| Non-empty answers | 21/21 | 21/21 |
| Retrieved contexts per case | 5 | 5 |
| Maximum joined context | 3,172 characters | 3,172 characters |
| Successful answer-model usage rows | 21 | 21 |
| Evaluation records | 21 | 21 |
| Evaluation errors | 0 | 0 |

The theoretical maximum bundle is 3,528 characters: five 700-character chunks plus four
seven-character separators. Both actual maxima are below Proofrag's 4,000-character
judge-context cap. Source labels are stable repository-relative paths; no workstation
path appears in predictions or golden data.

The answer model was `gpt-4o-mini-2024-07-18` at temperature 0. Provider responses
reported that same dated model. The absolute judge was
`proofrag-v2/anthropic:claude-haiku-4-5-20251001:temperature=0`; the blind judge was
`proofrag-compare-v2/anthropic:claude-haiku-4-5-20251001:temperature=0`. All exact OpenAI
system-fingerprint values are retained in [`usage.json`](artifacts/usage.json); they
varied across calls even though the requested and returned model ID stayed pinned.

## Exact retrieval results

Exact equality is the primary relevance rule because both variants select from the same
raw chunk universe. Unanswerable cases have no gold evidence and are excluded, leaving
19 retrieval-scored questions.

| Metric | Body-only | Metadata | Delta |
| --- | ---: | ---: | ---: |
| Recall@5 | 0.816 | 0.842 | +0.026 |
| Precision@5 | 0.189 | 0.200 | +0.011 |
| NDCG@5 | 0.711 | 0.729 | +0.018 |
| MRR | 0.689 | 0.711 | +0.022 |
| Full-evidence rate | 15/19 (78.9%) | 15/19 (78.9%) | 0 |
| Rank-one hit rate | 11/19 (57.9%) | 11/19 (57.9%) | 0 |

### By predeclared study group

| Group | n | Variant | Recall@5 | Precision@5 | NDCG@5 | MRR | Full evidence | Rank one |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Structure | 8 | Body | 0.875 | 0.175 | 0.783 | 0.750 | 7/8 | 5/8 |
| Structure | 8 | Metadata | 0.875 | 0.175 | 0.829 | 0.812 | 7/8 | 6/8 |
| Lexical control | 7 | Body | 0.857 | 0.171 | 0.723 | 0.679 | 6/7 | 4/7 |
| Lexical control | 7 | Metadata | 0.857 | 0.171 | 0.670 | 0.607 | 6/7 | 3/7 |
| Multi-document | 4 | Body | 0.625 | 0.250 | 0.546 | 0.583 | 2/4 | 2/4 |
| Multi-document | 4 | Metadata | 0.750 | 0.300 | 0.632 | 0.688 | 2/4 | 2/4 |

Metadata raised structure NDCG by 0.046 and multi-document NDCG by 0.086, but lowered
lexical-control NDCG by 0.053. Single-document aggregate metrics were identical across
variants: Recall@5 0.867, Precision@5 0.173, NDCG@5 0.755, and MRR 0.717. Metadata's
overall Recall gain came from retrieving one of q018's two gold chunks; no case lost
Recall. Paired NDCG improved on 3 cases, was unchanged on 15, and fell on 1. No lexical
or semantic sensitivity metric was added after seeing the result; the claim remains the
predeclared exact-chunk comparison.

## Generated-answer results

The absolute Anthropic judge scored four dimensions from 0 to 1. “Overall” below is the
unweighted mean of those four aggregate dimensions.

| Metric | Body-only | Metadata | Delta |
| --- | ---: | ---: | ---: |
| Groundedness | 0.895 | 0.876 | -0.019 |
| Correctness | 0.829 | 0.814 | -0.015 |
| Completeness | 0.817 | 0.814 | -0.003 |
| Citation quality | 0.860 | 0.805 | -0.055 |
| Overall | 0.850 | 0.827 | -0.023 |

### By difficulty

| Difficulty | n | Variant | Groundedness | Correctness | Completeness | Citation | Overall |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Single-document | 15 | Body | 0.910 | 0.863 | 0.837 | 0.877 | 0.872 |
| Single-document | 15 | Metadata | 0.910 | 0.863 | 0.847 | 0.853 | 0.868 |
| Multi-document | 4 | Body | 0.787 | 0.613 | 0.650 | 0.725 | 0.694 |
| Multi-document | 4 | Metadata | 0.688 | 0.537 | 0.600 | 0.525 | 0.588 |
| Unanswerable | 2 | Body | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Unanswerable | 2 | Metadata | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

The largest answer-score separation was on four multi-document questions. With only four
records and one temperature-zero generation per variant, this is a failure-analysis cue,
not evidence that indexed metadata intrinsically harms generation.

## Blind pairwise comparison

The same Anthropic model compared answers without variant labels. Seed 0 randomized
answer position independently for each question.

| Verdict | Count | Share of all 21 | Share of 5 decided |
| --- | ---: | ---: | ---: |
| Metadata wins | 4 | 19.0% | 80.0% |
| Body wins | 1 | 4.8% | 20.0% |
| Ties | 16 | 76.2% | — |

The 80% figure applies only to five decided questions, not the full set. The raw outcome
is four metadata wins, one body win, and sixteen ties.

## Failure analysis and manual judge disagreements

After paid scoring, a second project-authored audit inspected every retrieval miss, all
five blind non-ties, and both unanswerable answer pairs against retrieved excerpts. It is
recorded in [`answer-audit.json`](artifacts/answer-audit.json) and is not independent or
domain-expert review.

### Retrieval misses

| ID | Body Recall@5 | Metadata Recall@5 | Finding |
| --- | ---: | ---: | --- |
| q002 | 0.0 | 0.0 | Neither retrieved RFC 9110's definition of HTTP. Both safely refused, so the answers were grounded but end-to-end incomplete. |
| q007 | 0.0 | 0.0 | Both saw adjacent HTTP/2 framing chunks, then incorrectly put `END_STREAM` on `HEADERS` and omitted the required `DATA` sequence. |
| q016 | 0.5 | 0.5 | Both retrieved the RFC 9931 mitigation but missed RFC 9112's authority-form chunk. Both incorrectly answered absolute-form despite a retrieved excerpt explicitly excluding CONNECT. |
| q018 | 0.0 | 0.5 | Metadata found the QPACK capacity instruction at rank four but not the HTTP/3 rationale; body found neither exact gold chunk. Both refused instead of answering half. |

The clear shared answer failures were q007 and q016. The absolute judge also identified
both. q002 and q018 were conservative refusals caused by retrieval gaps.

### Review of the five blind non-ties

| ID | Blind judge | Project-audit view | Reason |
| --- | --- | --- | --- |
| q000 | Body | Tie | Both state the exact byte-range rule; body's extra general Range note is true but not discriminating. |
| q001 | Metadata | Body | Metadata adds response-time and backend-load claims not stated in its retrieved excerpts; body stays within the evidence. |
| q005 | Metadata | Metadata | Both are correct; metadata adds an accurate Trailer-field detail. The judge rationale incorrectly calls that declaration mandatory. |
| q013 | Metadata | Tie | The answers are semantically identical; adding “HTTP” before “upgrade tokens” is not a material difference here. |
| q017 | Metadata | Metadata | Metadata states the HTTP/2 preface versus HTTP/3 SETTINGS distinction more clearly. |

Project audit agreed with 2 of the 5 non-tie verdicts and disagreed with 3. This does not
replace the blind result; it shows why five model-decided cases are too few for a strong
pairwise claim.

### Refusal behavior

Each variant refused four questions: q002, q018, q019, and q020. The two predeclared
unanswerables, q019 and q020, were refused correctly by both systems, for a **2/2 safe
refusal rate** in each variant. The other two refusals occurred on answerable cases after
retrieval misses, or **2/19 answerable questions (10.5%)** per variant. Neither system
hallucinated a worker-thread default or per-user cache-storage requirement.

## Runtime, tokens, and list-price estimate

Every paid phase used a distinct `PROOFRAG_USAGE_LOG`. Counts below are provider-reported
tokens. Cost is an estimate using public list prices captured on 2026-08-10, not a bill:
OpenAI gpt-4o-mini at $0.15/M input and $0.60/M output, and Anthropic Haiku 4.5 at
$1.00/M input and $5.00/M output. No cache tokens were reported. Provider billing
consoles remain authoritative.

| Phase | Provider/model | Calls | Input tokens | Output tokens | Estimated USD | Wall time |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Golden candidates | OpenAI / `gpt-4o-mini-2024-07-18` | 21 | 5,041 | 1,543 | $0.001682 | 36.56 s |
| Body predictions | OpenAI / `gpt-4o-mini-2024-07-18` | 21 | 14,715 | 1,087 | $0.002859 | 32.55 s |
| Metadata predictions | OpenAI / `gpt-4o-mini-2024-07-18` | 21 | 15,057 | 1,128 | $0.002935 | 30.77 s |
| Body evaluation | Anthropic / `claude-haiku-4-5-20251001` | 21 | 20,498 | 2,180 | $0.031398 | 37.25 s |
| Metadata evaluation | Anthropic / `claude-haiku-4-5-20251001` | 21 | 20,900 | 2,179 | $0.031795 | 34.94 s |
| Blind comparison | Anthropic / `claude-haiku-4-5-20251001` | 21 | 6,676 | 1,090 | $0.012126 | 29.40 s |
| **Total** |  | **126** | **82,887** | **9,207** | **$0.082795** | **201.47 s** |

OpenAI accounted for 63 calls and an estimated $0.007476; Anthropic accounted for 63
calls and $0.075319. Provider INFO output showed 21 HTTP 200 responses per phase and no
retry messages. No partial record was used or replaced; this observation is persisted in
[`runtime.json`](artifacts/runtime.json).

## Reproducibility metadata

| Property | Recorded value |
| --- | --- |
| Execution date | 2026-08-10 |
| Git branch | `release/v0.8.0-case-studies` |
| Git base at execution | `28190af88e32e715eb2d2deeb3efff0ea0ca1b33` |
| Python | 3.12.12 |
| SQLite | 3.50.4 with FTS5 |
| OpenAI SDK | 2.38.0 |
| Anthropic SDK | 0.105.2 |
| Requested/returned answer model | `gpt-4o-mini-2024-07-18` |
| Absolute judge | `proofrag-v2/anthropic:claude-haiku-4-5-20251001:temperature=0` |
| Blind judge | `proofrag-compare-v2/anthropic:claude-haiku-4-5-20251001:temperature=0` |
| Retrieval matcher | `exact`, k=5 |
| Randomization seed | 0 |

The console-script distribution metadata reported Proofrag 0.7.0 because the v0.8.0 tag
did not exist during execution. Commands set `PYTHONPATH=src:.`, so they loaded the
v0.8.0 study source tree rather than an older installed module.

## Exact workflow

These commands document the published run while directing a fresh execution to a new
temporary artifact directory. `PROOFRAG_USAGE_LOG` is append-only; never point a rerun at
the published artifacts.

From the repository root, load credentials without printing them and set the local source
path:

```bash
set -a
source .env
set +a
export PYTHONPATH=src:.
RFC_RERUN_ARTIFACTS="$(mktemp -d "${TMPDIR:-/tmp}/proofrag-rfc-rerun.XXXXXX")"
export RFC_RERUN_ARTIFACTS
```

Optionally repeat candidate generation for cost and behavior comparison. Fresh model
output is not reviewed ground truth and can differ even at temperature 0:

```bash
export PROOFRAG_PROVIDER=openai
export PROOFRAG_MODEL=gpt-4o-mini-2024-07-18
PROOFRAG_USAGE_LOG="$RFC_RERUN_ARTIFACTS/usage-generation.jsonl" \
  /usr/bin/time -p .venv/bin/python \
  -m case_studies.http_rfc_metadata.generate_goldenset \
  --out "$RFC_RERUN_ARTIFACTS/goldenset.generated.jsonl" \
  --seed 9110 --model gpt-4o-mini-2024-07-18
```

Verify the pinned corpus and deterministically materialize the committed project review:

```bash
.venv/bin/python -m case_studies.http_rfc_metadata.download_corpus
.venv/bin/python -m case_studies.http_rfc_metadata.apply_review
.venv/bin/python -m case_studies.http_rfc_metadata.audit_goldenset
.venv/bin/python -m proofrag.cli validate \
  --goldenset case_studies/http_rfc_metadata/goldenset.jsonl \
  --corpus case_studies/http_rfc_metadata/corpus \
  --out case_studies/http_rfc_metadata/artifacts/validation.json --strict
```

The committed generated and final golden files are the audited scoring inputs.
`apply_review.py` deliberately rejects a committed generated-file hash that differs from
the reviewed one; it does not apply the project review to a fresh model sample.

Run both answer variants with isolated usage logs:

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

Evaluate and compare with the pinned Anthropic judge:

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

Render scorecards and rebuild the usage summary:

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

## Artifact index

| Artifact | Purpose | SHA-256 |
| --- | --- | --- |
| [`predictions-body.jsonl`](artifacts/predictions-body.jsonl) | Body-only answers and raw retrieved chunks | `4eb92be9bb6f18e114a4c2d43f3c5b0aa5f718aa0f7bed30c68b0f289a45ba08` |
| [`predictions-metadata.jsonl`](artifacts/predictions-metadata.jsonl) | Metadata-index answers and raw retrieved chunks | `1624dc099431563e9e9f1c2d5584fab3ba986713940df10bb06d5dc5ac5b330f` |
| [`results-body.json`](artifacts/results-body.json) | Exact retrieval and absolute answer scores | `b425230ea6563bf9a1590b40b41e721297f475e252e2bbff29d09656f0614fdc` |
| [`results-metadata.json`](artifacts/results-metadata.json) | Exact retrieval and absolute answer scores | `d3d93708128bd94d55c25e37f5694afb1acc1ce6fc0265a6e76a824684a1e0dd` |
| [`comparison.json`](artifacts/comparison.json) | Blind per-case verdicts and retrieval aggregates | `891aeee56b4078a35cfce274bdd903012217c684a6c0d429a6b8c491e470383b` |
| [`answer-audit.json`](artifacts/answer-audit.json) | Project review of misses, non-ties, and refusals | `a5520fdea87df19041e75030de6ad73f27fd5435537b262af2714000b80b3442` |
| [`usage.json`](artifacts/usage.json) | Per-phase provider token counts and price snapshot | `dbe35278e416a7d5cf0a1f4b9531b3728c6902076e95a96d1b3b595adc263026` |
| [`runtime.json`](artifacts/runtime.json) | Measured wall times and run-integrity observation | `ef617131cdc81d17b64a686cc2b1d634129e16b5ea3fb0ba53007b9674c086c9` |
| [`scorecard-body.html`](artifacts/scorecard-body.html) | Self-contained body scorecard | `01209e3e2925744c97f614873e6c8e26424a223e8a69226a31892fcdc78116cf` |
| [`scorecard-metadata.html`](artifacts/scorecard-metadata.html) | Self-contained metadata scorecard | `fc22f61e6025bcd70a7b4874b05788f383d02836dcfb905da04b8299f2a8512c` |
| [`comparison.html`](artifacts/comparison.html) | Self-contained blind-comparison report | `16c4feabacb7c06ae25fcf4b8f5a7acb250b27678e48120e367e262c0320dde6` |

## Limitations

- Seven HTTP-family standards and 21 questions cannot support a universal retrieval
  claim.
- Golden generation and both semantic audits were project-authored; there was no
  independent reviewer or HTTP standards expert.
- Four multi-document and two unanswerable questions are too few for stable subgroup
  estimates.
- Exact chunk equality can undercount alternate valid evidence, though it avoids fuzzy
  matching ambiguity when both systems share one chunk universe.
- Regex-derived section headings can be wrong despite parser checks and spot review.
- FTS5 OR-query BM25 is one lexical setup; this study does not compare embeddings,
  vector search, rerankers, or learned sparse retrieval.
- One temperature-zero answer and one judge pass per case do not measure model variance.
  The manual disagreement on three of five non-ties demonstrates judge sensitivity.
- OpenAI system fingerprints varied across calls. The dated model ID was stable, but
  provider-side deployment changes can still affect reproduction.
- RFC errata and later updates remain separate from this pinned publication snapshot.
- The $0.082795 figure is a list-price estimate from reported tokens, not authoritative
  billed spend.
