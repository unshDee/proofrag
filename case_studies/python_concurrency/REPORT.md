# Does SQLite FTS5 beat token overlap for Python concurrency documentation retrieval?

**Case-study date:** August 9, 2026<br>
**Proofrag source:** `v0.7.0`, commit `c74d3c1a7f576d9ffe1d6f55020991f24f4f6d2e`<br>
**Golden-set fingerprint:** `sha256:d8dbb57996d021c0`

## Result in one paragraph

On this 30-question benchmark, SQLite FTS5/BM25 was stronger on multi-document
retrieval than a simple unique-token-overlap baseline, but the overall claim depends
on how relevance is matched. Proofrag's pre-specified Jaccard matcher gave FTS5 a
3.7-point Recall@5 gain and 3.2-point NDCG@5 gain. A post-hoc exact-chunk check tied
overall Recall@5 at 0.852 and narrowed the NDCG@5 advantage to 0.007, while preserving
a large multi-document advantage: exact-match NDCG@5 was 0.857 versus 0.534. A blind
judge preferred FTS5 13 times, overlap 6 times, and called 11 ties, so FTS5 won
**13/19 (68.4%)** of decided comparisons. This is evidence for this corpus and setup,
not a general claim that FTS5 beats every lexical retriever.

## Why this study exists

The study asks a deliberately modest product question:

> If a small documentation RAG system replaces a dependency-free token-overlap
> retriever with SQLite FTS5/BM25, does retrieval or answer quality measurably improve?

The hypothesis, fixed before evaluation, was that FTS5 would improve rank-sensitive
retrieval, especially when an answer required evidence from two documents.

It also demonstrates the full Proofrag workflow rather than only publishing a score:

1. build a balanced golden set from a real corpus;
2. validate and fingerprint it;
3. score retrieval separately from generation;
4. compare two variants blindly on identical questions; and
5. turn an observed scorecard into a CI regression gate.

## Corpus and provenance

The corpus is a small, balanced snapshot of official Python concurrency documentation
from the [Python 3.14.7 release](https://www.python.org/downloads/release/python-3147/),
pinned to CPython commit
[`823f0323ee6ec1402088b73bce1a38473cac36dc`](https://github.com/python/cpython/commit/823f0323ee6ec1402088b73bce1a38473cac36dc).
The release was published August 5, 2026. The immutable commit matters because the
rolling `docs.python.org/3.14` pages can change with maintenance releases.

| Corpus property | Value |
| --- | ---: |
| Official source files | 8 |
| Downloaded bytes | 202,098 |
| Parsed characters | 195,561 |
| Chunks | 333 |
| Average chunk | 587 characters |
| Target chunk size | 700 characters |
| Maximum chunk | 1,181 characters |
| Oversized source paragraphs | 8 |
| File type | reStructuredText (`.rst`) only |

The chunker preserves a paragraph that is longer than the 700-character target, so
the target is not a hard upper bound. Eight of 333 chunks exceeded it.

| File | Bytes | SHA-256 prefix |
| --- | ---: | --- |
| `asyncio-queue.rst` | 7,682 | `c7312064e8c1` |
| `asyncio-stream.rst` | 18,016 | `afc4687dca45` |
| `asyncio-sync.rst` | 12,876 | `ce9b6b4f31a3` |
| `asyncio-task.rst` | 51,411 | `fec575ef139e` |
| `concurrent.futures.rst` | 29,730 | `a860180e171d` |
| `multiprocessing.shared_memory.rst` | 17,528 | `10f04327f469` |
| `queue.rst` | 12,258 | `f621645ca7ca` |
| `threading.rst` | 52,597 | `19b4cb7d9eb5` |

Full URLs and hashes are in [`sources.json`](sources.json). The downloader accepts
only exact, commit-pinned HTTPS URLs from `raw.githubusercontent.com`; rejects an
off-allowlist redirect, non-`text/plain` response, invalid UTF-8, NUL bytes, symlink
overwrite, or oversized response; and verifies every SHA-256 before use. Files are
read as text and never executed or built with Sphinx.

The corpus and retained [`LICENSE.python`](LICENSE.python) are covered by the
[Python Software Foundation License Version 2](https://docs.python.org/3.14/license.html);
documentation examples and recipes are additionally available under the Zero-Clause
BSD license. No PSF endorsement is implied.

## Golden-set construction and audit

Proofrag generated 30 candidate questions with Anthropic Claude Haiku 4.5 using a
700-character corpus target and sampling seed `21661`. That seed was selected for
source balance before answers or scores were inspected. It covered all eight documents,
and all six multi-document samples paired different sources.

| Stage | Count |
| --- | ---: |
| Requested | 30 |
| Generated | 30 |
| Human reviewed | 30 |
| Edited after review | 17 (56.7%) |
| Unchanged | 13 (43.3%) |
| Rejected | 0 |
| Final | 30 |

| Difficulty | Count | Share |
| --- | ---: | ---: |
| Single-document | 21 | 70.0% |
| Multi-document | 6 | 20.0% |
| Unanswerable | 3 | 10.0% |

Human review was substantive. It caught, among other issues:

- `q008` paired `kill_workers()` with the neighboring `Process.terminate()` passage;
  the correct evidence says `Process.kill()`;
- one supposedly unanswerable shared-memory question was answered qualitatively in
  the corpus and had to become a genuinely absent benchmark question;
- the original factorial complexity question was inferable from included code and
  had to become an absent comparative-performance question; and
- several multi-document questions claimed a relationship that their two passages
  did not actually establish.

All six multi-document cases were manually checked to require both evidence passages.
All three unanswerable cases were searched against the full eight-file corpus, not
only against the passage used by the generator. The exact ID-bound audit is recorded
by [`audit_goldenset.py`](audit_goldenset.py) and
[`goldenset-audit.json`](artifacts/goldenset-audit.json). The audit script refuses to
apply those edits if the generated artifact or pinned corpus hashes change, and it
embeds Proofrag 0.7.0's paragraph-packing semantics so later chunker changes cannot
silently remap q008 or q019 evidence.

Strict validation produced:

| Integrity check | Result |
| --- | ---: |
| Records | 30/30 |
| Unique IDs | 30/30 |
| Difficulty distribution | 21 / 6 / 3 |
| Source coverage | 8/8 (100%) |
| Validation errors | 0 |
| Validation warnings | 0 |
| Multi-document evidence audit | 6/6 |
| Full-corpus unanswerable audit | 3/3 |
| Final SHA-256 | `d8dbb57996d021c06b2876ebf488fd5c482aaa71aa418ea759839ab0fa570088` |

## Systems under test

Only the retriever changed.

| Property | Token overlap | SQLite FTS5 |
| --- | --- | --- |
| Query representation | Unique lowercase tokens | Non-stopword lowercase tokens |
| Candidate score | Count of shared unique tokens | FTS5 built-in BM25 |
| Query form | All tokens | Quoted terms joined with `OR` |
| Tie-break | Chunk ID | Chunk ID |
| Index | None | In-memory SQLite FTS5 |
| Returned contexts | Exactly 5 | Exactly 5 |

Both used the same:

- eight-file corpus and 700-character target chunking;
- top-five retrieval contract;
- answer prompt, including an explicit refusal instruction;
- Anthropic model ID `claude-haiku-4-5-20251001`; and
- 30-question audited golden set.

The answer prompt asked the model to use only retrieved Python documentation, refuse
when unsupported, and cite source filenames. Prediction integrity was complete:

| Variant | IDs | Contexts/case | Empty answers | Maximum judge context | Over 4,000 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Token overlap | 30/30 | 5 | 0 | 3,695 chars | 0 |
| FTS5 | 30/30 | 5 | 0 | 3,908 chars | 0 |

## Evaluation method

Generation was judged once per case by the same pinned Haiku model on four dimensions:

- **groundedness:** support from retrieved text;
- **correctness:** agreement with the audited reference answer;
- **completeness:** coverage of the reference answer; and
- **citation quality:** whether claims are attributable to retrieved text.

“Citation quality” does not validate a literal URL or citation syntax. It measures
attribution to the supplied context. The derived generation **Overall** is the macro
mean of those four dimensions.

Retrieval was deterministic and scored only on 27 answerable questions:

- **Recall@5:** fraction of gold evidence chunks found;
- **Precision@5:** fraction of the five returned chunks considered relevant;
- **NDCG@5:** rank-sensitive binary relevance; and
- **MRR:** reciprocal rank of the first relevant returned chunk.

The default relevance matcher treated a retrieved chunk as relevant when whole-chunk
token Jaccard similarity with a gold chunk was at least `0.4`. Because the RAG adapters
returned exact corpus chunks, this is a reproducible dependency-free rule, not proof of
semantic equivalence; `q008` below shows a concrete false positive.

The blind A/B comparison randomized answer position per question with seed `0`. The
judge saw the question, reference answer, and two unlabeled responses. Ties were
allowed. The seed fixes answer position, not Anthropic sampling; judge outputs can vary.

## Pre-specified result: Proofrag's default relevance matcher

| Metric | Token overlap | FTS5 | FTS5 − overlap |
| --- | ---: | ---: | ---: |
| Recall@5 | 0.870 | **0.907** | +0.037 (+3.7 pp) |
| Precision@5 | 0.259 | **0.281** | +0.022 (+2.2 pp) |
| NDCG@5 | 0.876 | **0.908** | +0.032 (+3.2 pp) |
| MRR | 0.852 | **0.889** | +0.037 (+3.7 pp) |

Precision looks low because each case returns five chunks while most references need
only one or two. Both systems always returned exactly five, so their denominators match.

| Variant | Tier | Any evidence | Full evidence | Zero evidence |
| --- | --- | ---: | ---: | ---: |
| FTS5 | All answerable | 27/27 (100%) | 22/27 (81.5%) | 0/27 |
| Overlap | All answerable | 26/27 (96.3%) | 21/27 (77.8%) | 1/27 (3.7%) |
| FTS5 | Single-document | 21/21 (100%) | 20/21 (95.2%) | 0/21 |
| Overlap | Single-document | 21/21 (100%) | 20/21 (95.2%) | 0/21 |
| FTS5 | Multi-document | 6/6 (100%) | 2/6 (33.3%) | 0/6 |
| Overlap | Multi-document | 5/6 (83.3%) | 1/6 (16.7%) | 1/6 (16.7%) |

The main retrieval problem is clear: neither retriever consistently found both passages
for multi-document questions. FTS5 reduced the severity—no total misses and twice as
many full-evidence cases—but 4/6 multi-document questions still lacked some evidence.

### Post-hoc sensitivity: exact chunk identity

Failure inspection found that the default matcher counted some near-duplicate but wrong
chunks as relevant. Because both adapters return exact text from the same corpus, I
recomputed retrieval offline with strict string identity. This was a post-hoc sensitivity
check; it does not replace or alter the persisted Proofrag results.

| Metric | Token overlap | FTS5 | FTS5 − overlap |
| --- | ---: | ---: | ---: |
| Exact Recall@5 | 0.852 | 0.852 | 0.000 |
| Exact Precision@5 | 0.193 | 0.200 | +0.007 |
| Exact NDCG@5 | 0.837 | 0.844 | +0.007 |
| Exact MRR | 0.802 | 0.809 | +0.007 |

| Variant | Difficulty | Recall@5 | Precision@5 | NDCG@5 | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| FTS5 | Single | 0.929 | 0.190 | 0.841 | 0.802 |
| Overlap | Single | **0.976** | **0.200** | **0.923** | **0.897** |
| FTS5 | Multi | **0.583** | **0.233** | **0.857** | **0.833** |
| Overlap | Multi | 0.417 | 0.167 | 0.534 | 0.472 |

Under exact matching, FTS5 found some evidence for 26/27 answerable cases versus 25/27
for overlap, but retrieved every required chunk for 20/27 versus overlap's 21/27. The
overall retrieval result becomes nearly tied; the multi-document separation remains.

`q008` explains why the sensitivity check matters. FTS5 retrieved the adjacent
`terminate_workers()` passage rather than the gold `kill_workers()` passage. The two
paragraphs share enough boilerplate to exceed Jaccard 0.4, so the default metric recorded
Recall@5 of 1.0 even though the answer followed the wrong `Process.terminate()` evidence.
Exact matching correctly recorded zero recall for that case.

## Secondary result: generated answers

| Metric | Token overlap | FTS5 | FTS5 − overlap |
| --- | ---: | ---: | ---: |
| Groundedness | 0.913 | **0.920** | +0.007 |
| Correctness | **0.892** | 0.870 | −0.022 |
| Completeness | 0.793 | **0.857** | +0.064 |
| Citation quality | 0.882 | **0.925** | +0.043 |
| **Overall** | 0.870 | **0.893** | +0.023 |
| **Answerable-only Overall** | 0.856 | **0.881** | +0.025 |

FTS5 improved completeness and attribution, but correctness fell by 2.2 points. The
result is mixed rather than a clean generation-quality win. Reporting answerable-only
Overall matters because three perfect refusals otherwise lift both all-case averages.

### Generation by difficulty

| Variant | Difficulty | n | Grounded | Correct | Complete | Citation | Overall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FTS5 | Single | 21 | 0.960 | 0.950 | 0.967 | 0.964 | 0.960 |
| Overlap | Single | 21 | 0.950 | 0.950 | 0.900 | 0.924 | 0.931 |
| FTS5 | Multi | 6 | 0.742 | 0.525 | 0.400 | 0.750 | 0.604 |
| Overlap | Multi | 6 | 0.742 | 0.633 | 0.317 | 0.675 | 0.592 |
| FTS5 | Unanswerable | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Overlap | Unanswerable | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Both variants safely refused all **3/3** unanswerable questions. Proofrag does not have
a dedicated refusal metric, so this rate was manually checked by requiring each answer
to begin with the specified refusal. Retrieval is not scored for unanswerable cases.

### Retrieval by difficulty

| Variant | Difficulty | n | Recall@5 | Precision@5 | NDCG@5 | MRR |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| FTS5 | Single | 21 | 0.976 | 0.267 | 0.921 | 0.905 |
| Overlap | Single | 21 | 0.976 | 0.267 | **0.949** | **0.944** |
| FTS5 | Multi | 6 | **0.667** | **0.333** | **0.862** | **0.833** |
| Overlap | Multi | 6 | 0.500 | 0.233 | 0.617 | 0.528 |

Single-document recall and precision tied, while overlap ranked the evidence slightly
higher. FTS5's aggregate advantage came from multi-document retrieval, where it improved
every metric substantially.

## Blind pairwise comparison

| Difficulty | n | FTS5 wins | Overlap wins | Ties | FTS5 wins among decided |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 30 | 13 | 6 | 11 | 13/19 (68.4%) |
| Single-document | 21 | 6 | 5 | 10 | 6/11 (54.5%) |
| Multi-document | 6 | 5 | 1 | 0 | 5/6 (83.3%) |
| Unanswerable | 3 | 2 | 0 | 1 | 2/2 (100%) |

FTS5 won 43.3% of all cases, overlap won 20.0%, and 36.7% tied. The decided-only rate
excludes ties and must not be presented as “FTS5 won 68.4% of all questions.”

All unanswerable answers received perfect absolute scores. FTS5's two pairwise wins in
that tier reflect more specific refusal wording, not better refusal safety.

## What failed, and why

Per-case generation score is `G = (groundedness + correctness + completeness +
citation quality) / 4`.

| Variant | ID | Difficulty | G | Recall@5 | Main failure |
| --- | --- | --- | ---: | ---: | --- |
| FTS5 | `q021` | Multi | 0.450 | 0.500 | Retrieved asyncio evidence but missed `BrokenThreadPool`. |
| FTS5 | `q022` | Multi | 0.450 | 0.500 | Retrieved server evidence but missed Task/Future behavior. |
| FTS5 | `q023` | Multi | 0.450 | 0.500 | Retrieved shared-memory benefits but missed `BrokenProcessPool`. |
| FTS5 | `q024` | Multi | 0.500 | 0.500 | Missed Condition evidence and declined most of the answer. |
| FTS5 | `q007` | Single | 0.575 | 1.000 | Full evidence arrived; answer omitted initial OS-name behavior. |
| Overlap | `q004` | Single | 0.000 | 1.000 | Full evidence arrived; answer incorrectly refused. |
| Overlap | `q022` | Multi | 0.375 | 0.500 | Found Task/Future text but missed the server example. |
| Overlap | `q025` | Multi | 0.450 | 0.500 | Found only half of the Future/Condition explanation. |
| Overlap | `q021` | Multi | 0.600 | 0.500 | Missed initializer-failure behavior. |
| Overlap | `q026` | Multi | 0.613 | 0.500 | Missed threaded-queue sizing and graceful-shutdown details. |

A simple diagnostic split used `G < 0.65` as low generation quality and Recall@5 `< 1`
as incomplete retrieval:

| Variant | Retrieval-linked | Generation-side | High score despite retrieval miss | Strong/full |
| --- | ---: | ---: | ---: | ---: |
| FTS5 | 4 | 1 | 1 | 21 |
| Overlap | 4 | 1 | 2 | 20 |

- FTS5 retrieval-linked: `q021`, `q022`, `q023`, `q024`.
- FTS5 generation-side: `q007`.
- Overlap retrieval-linked: `q021`, `q022`, `q025`, `q026`.
- Overlap generation-side: `q004`.

Two details are especially useful for diagnosis:

1. **A reported retrieval hit can be wrong.** Overlap retrieved the full `q004`
   evidence, but the answer model refused—a genuine generation-side failure. For FTS5
   `q008`, the default fuzzy matcher marked the neighboring `terminate_workers()` text
   as a hit even though the gold passage was absent. The answer correctly followed the
   retrieved text and was wrong relative to the question.
2. **A retrieval miss does not always imply an unusable answer.** `q019` had two gold
   chunks from one document. Both variants retrieved one, producing Recall@5 of 0.5;
   FTS5 still gave the complete workaround. This exposes a limit of exact lexical
   gold-context matching rather than proving model prior knowledge.

## CI regression demonstration

The controlled fault injection reversed SQLite's BM25 ordering—higher/worse scores
first—while preserving the same corpus, questions, prompt, model, and exactly five
returned contexts. It models a realistic sign/direction bug rather than making the
candidate obviously invalid by returning fewer results.

| Metric | FTS5 baseline | Reversed BM25 | Delta | Gate at 0.02 |
| --- | ---: | ---: | ---: | --- |
| Groundedness | 0.920 | 1.000 | +0.080 | Pass |
| Correctness | 0.870 | 0.400 | −0.470 | **Regression** |
| Completeness | 0.857 | 0.100 | −0.757 | **Regression** |
| Citation quality | 0.925 | 1.000 | +0.075 | Pass |
| Recall@5 | 0.907 | 0.000 | −0.907 | **Regression** |
| Precision@5 | 0.281 | 0.000 | −0.281 | **Regression** |
| NDCG@5 | 0.908 | 0.000 | −0.908 | **Regression** |
| MRR | 0.889 | 0.000 | −0.889 | **Regression** |

`proofrag diff --tolerance 0.02` exited with code **1** and named six regressed metrics.
Judge fingerprints matched. The gate treats a drop strictly greater than `0.02` as a
regression.

All 27 answerable cases had zero retrieval hits after reversal. Groundedness and
citation quality rose because the model usually refused instead of inventing an answer
from irrelevant text. That is the point of keeping eight dimensions: a groundedness-only
gate would have approved a completely broken retriever.

One reversed-rank context bundle was 4,071 characters, so the generation judge truncated
71 characters. Deterministic retrieval metrics were unaffected; regression generation
scores carry that additional limitation. The captured output is in
[`regression-diff.txt`](artifacts/regression-diff.txt).

Before invoking `diff`, this study separately asserted equal golden-set hash, IDs,
record count, backend, `k`, judge fingerprint, and project commit. The published v0.7.0
`diff` command checked the eight built-in scores and judge fingerprint, but not every
control. Proofrag 0.8.0 now records dataset and matcher fingerprints, gates dynamic
backend metrics, and rejects incompatible configurations.

## Runtime and cost

Proofrag's Anthropic client currently discards provider token-usage fields. The table
therefore reports a transparent **character-based proxy**, not billed token usage:
persisted system, prompt, and output characters divided by four. Anthropic listed
Claude Haiku 4.5 at **$1 per million input tokens and $5 per million output tokens** on
the direct API when this study ran; see the official
[model overview](https://platform.claude.com/docs/en/about-claude/models/overview) and
[API pricing](https://platform.claude.com/docs/en/about-claude/pricing).

| Phase | Calls | Wall time | Approx input tokens | Approx output tokens | List-price proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Golden-set generation | 30 | 52.86 s | 8,109 | 3,316 | $0.0247 |
| Overlap answers | 30 | 52.49 s | 28,387 | 2,937 | $0.0431 |
| Overlap evaluation | 30 | 48.26 s | 35,030 | 2,337 | $0.0467 |
| FTS5 answers | 30 | 48.56 s | 27,438 | 3,076 | $0.0428 |
| FTS5 evaluation | 30 | 52.58 s | 34,167 | 2,221 | $0.0453 |
| Reversed-rank answers | 30 | 51.61 s | 29,696 | 2,269 | $0.0410 |
| Reversed-rank evaluation | 30 | 45.87 s | 35,683 | 2,132 | $0.0463 |
| Blind comparison | 30 | 42.95 s | 11,646 | 1,663 | $0.0200 |
| **Total persisted workflow** | **240** | **395.18 s** | **210,156** | **19,951** | **$0.3099** |

The proxy excludes provider framing and may differ materially from billed tokens. It
also excludes a five-case pilot (9.84 seconds) and one interrupted generation attempt
whose completed-call count was not captured, so it must not be presented as actual
account spend. The Anthropic console is the source of truth for remaining credit. No
OpenAI API calls were made.

### Retriever-only latency

A local observational microbenchmark ran 900 warm in-memory queries per retriever on
an arm64 Mac with 10 logical CPUs, Python 3.12.12, and SQLite 3.50.4.

| Operation | Median | p95 |
| --- | ---: | ---: |
| Token-overlap query | 3.173 ms | 3.262 ms |
| FTS5 query | 0.396 ms | 0.681 ms |
| FTS5 index build | 2.457 ms | 2.662 ms |

FTS5 was about 8× faster at the median in this implementation because the baseline
re-tokenizes all 333 chunks for each question. This is not a general search-engine
benchmark. End-to-end API timings are observational and dominated by network/model
latency.

## Reproduce the published artifacts

The `.env` file is gitignored. An `ANTHROPIC_API_KEY` is sufficient for this pinned
workflow, but Proofrag intentionally does not auto-load `.env`; export it first. The
commands use Proofrag 0.7.0 because these are frozen v0.7.0 measurements. Version 0.8.0
corrects the NDCG and `diff` limitations discovered here.

The corpus, audit, retrieval, and metric steps are deterministic. Proofrag 0.7.0 did
not fix Anthropic sampling, so the paid generation, answer, judge, and blind-comparison
calls can vary even with the same pinned model and seeds. These commands reproduce the
workflow and controls; they do not promise byte-identical paid outputs. The committed
artifacts are the frozen measurements reported above.

From repository root:

```bash
uv run python case_studies/python_concurrency/download_corpus.py
uv run python case_studies/python_concurrency/audit_goldenset.py

set -a
source .env
set +a
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

uvx --from "proofrag[anthropic]==0.7.0" proofrag evaluate \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --predictions case_studies/python_concurrency/artifacts/predictions-overlap.jsonl \
  --out case_studies/python_concurrency/artifacts/results-overlap.json \
  --model claude-haiku-4-5-20251001 --k 5

uvx --from "proofrag[anthropic]==0.7.0" proofrag evaluate \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --predictions case_studies/python_concurrency/artifacts/predictions-fts5.jsonl \
  --out case_studies/python_concurrency/artifacts/results-fts5.json \
  --model claude-haiku-4-5-20251001 --k 5

uvx --from "proofrag[anthropic]==0.7.0" proofrag compare \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --a case_studies/python_concurrency/artifacts/predictions-fts5.jsonl \
  --b case_studies/python_concurrency/artifacts/predictions-overlap.jsonl \
  --a-name fts5 --b-name overlap --seed 0 --k 5 \
  --model claude-haiku-4-5-20251001 \
  --out case_studies/python_concurrency/artifacts/comparison.json \
  --html case_studies/python_concurrency/artifacts/comparison.html

uvx --from "proofrag[anthropic]==0.7.0" proofrag run \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --callable case_studies.python_concurrency.rag:answer_fts5_reversed \
  --out case_studies/python_concurrency/artifacts/predictions-fts5-reversed.jsonl

uvx --from "proofrag[anthropic]==0.7.0" proofrag evaluate \
  --goldenset case_studies/python_concurrency/goldenset.jsonl \
  --predictions case_studies/python_concurrency/artifacts/predictions-fts5-reversed.jsonl \
  --out case_studies/python_concurrency/artifacts/results-fts5-reversed.json \
  --model claude-haiku-4-5-20251001 --k 5

for name in overlap fts5 fts5-reversed; do
  uvx --from "proofrag[anthropic]==0.7.0" proofrag report \
    --results "case_studies/python_concurrency/artifacts/results-$name.json" \
    --out "case_studies/python_concurrency/artifacts/report-$name.html"
done

uvx --from "proofrag[anthropic]==0.7.0" proofrag diff \
  --baseline case_studies/python_concurrency/artifacts/results-fts5.json \
  --candidate case_studies/python_concurrency/artifacts/results-fts5-reversed.json \
  --tolerance 0.02

PYTHONPATH=. uv run --no-project --with "proofrag==0.7.0" python \
  -m case_studies.python_concurrency.analyze_results
```

The published `goldenset.generated.jsonl` is intentionally retained. LLM generation is
not deterministic even with the corpus sampling seed. To create a fresh candidate set,
run the following and then manually audit it; the published ID-based audit script will
refuse the new hash:

```bash
uvx --from "proofrag[anthropic]==0.7.0" proofrag generate \
  --corpus case_studies/python_concurrency/corpus \
  --out case_studies/python_concurrency/goldenset.generated.jsonl \
  --n 30 --seed 21661 --chunk-chars 700 \
  --model claude-haiku-4-5-20251001
```

The expected `diff` exit code is 1 because the reversed ranking is an intentional
regression.

## Threats to validity

- **Small, single-domain sample.** Thirty questions, including only six multi-document
  and three unanswerable cases, cannot support universal retriever claims.
- **Lexical systems only.** This does not compare embeddings, hybrid retrieval,
  reranking, or GraphRAG.
- **Generated then reviewed goldenset.** Human review corrected 17/30 records, improving
  validity while introducing reviewer judgment.
- **One judge pass.** Absolute LLM scores and pairwise choices can vary. No confidence
  interval or repeated-judge stability estimate is claimed.
- **Same model family.** Haiku generated candidates, answered, and judged them, which can
  create self-preference. Human review reduced dataset errors but does not remove it.
- **Public facts.** The answer model may know Python documentation from training. The
  explicit context-only prompt and refusal cases reduce, but cannot eliminate, prior
  knowledge.
- **Lexical relevance matching.** Whole-chunk Jaccard at 0.4 can miss alternate evidence,
  partial passages, or chunk-boundary equivalents, and `q008` shows it can count a
  near-duplicate but contradictory passage as relevant. Exact-match sensitivity removed
  the headline overall Recall advantage while preserving the multi-document advantage.
- **NDCG implementation.** The frozen v0.7.0 result normalized over relevance found in
  the returned list, not the ideal number of gold contexts; interpret it alongside
  Recall@5. Proofrag 0.8.0 corrects this behavior.
- **Citation semantics.** Citation quality is attribution to retrieved context, not a
  check of citation formatting, URL validity, or source authority.
- **Unanswerable retrieval is skipped.** The 3/3 refusal rate is a separate manual check.
- **Judge context cap.** Main variants stayed below 4,000 characters; one intentional
  regression record was truncated.
- **Cost and runtime are snapshots.** Pricing, network latency, model behavior, and local
  machine performance can change.
- **Diff preconditions.** Proofrag 0.7.0 did not fingerprint every experimental input;
  the study asserted them separately. Version 0.8.0 records and checks them.

## Artifact index

| Artifact | Purpose |
| --- | --- |
| [`sources.json`](sources.json) | Immutable source URLs, sizes, and SHA-256 hashes |
| [`download_corpus.py`](download_corpus.py) | Allowlisted, hash-verifying downloader |
| [`goldenset.generated.jsonl`](goldenset.generated.jsonl) | Unedited model output |
| [`goldenset.jsonl`](goldenset.jsonl) | Audited final evaluation set |
| [`goldenset-audit.json`](artifacts/goldenset-audit.json) | Review counts and artifact hashes |
| [`validation.json`](artifacts/validation.json) | Strict schema and source-coverage result |
| [`rag.py`](rag.py) | Both retrievers and controlled fault injection |
| [`predictions-overlap.jsonl`](artifacts/predictions-overlap.jsonl) | Baseline answers and contexts |
| [`predictions-fts5.jsonl`](artifacts/predictions-fts5.jsonl) | FTS5 answers and contexts |
| [`results-overlap.json`](artifacts/results-overlap.json) | Baseline per-case and aggregate scores |
| [`results-fts5.json`](artifacts/results-fts5.json) | FTS5 per-case and aggregate scores |
| [`comparison.json`](artifacts/comparison.json) | Blind pairwise verdicts and rationales |
| [`comparison.html`](artifacts/comparison.html) | Self-contained visual A/B report |
| [`report-overlap.html`](artifacts/report-overlap.html) | Baseline scorecard |
| [`report-fts5.html`](artifacts/report-fts5.html) | FTS5 scorecard |
| [`predictions-fts5-reversed.jsonl`](artifacts/predictions-fts5-reversed.jsonl) | Raw fault-injection answers and contexts |
| [`results-fts5-reversed.json`](artifacts/results-fts5-reversed.json) | Fault-injection scores |
| [`report-fts5-reversed.html`](artifacts/report-fts5-reversed.html) | Fault-injection scorecard |
| [`regression-diff.txt`](artifacts/regression-diff.txt) | Expected failing CI diff |
| [`analysis.json`](artifacts/analysis.json) | Derived tables, integrity checks, timings, and usage proxy |

## Bottom line

The credible claim is narrow: **for this audited Python concurrency benchmark, FTS5
improved multi-document retrieval and won the blind comparison, while overall exact
retrieval was nearly tied and overlap was stronger on single-document ranking.** More
importantly for Proofrag, the workflow exposed a wrong golden context before scoring,
found a false-positive relevance match during failure analysis, separated retrieval
misses from answer-model failures, prevented perfect refusal scores from hiding weak
retrieval, and made a reversed-ranking bug fail CI with an explainable exit code.
