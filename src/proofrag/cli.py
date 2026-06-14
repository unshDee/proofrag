"""proofrag command-line interface.

proofrag generate --corpus DIR     # docs  -> goldenset.jsonl
proofrag validate --goldenset ...  # check eval set quality/schema
proofrag run --goldenset ...       # app   -> predictions.jsonl
proofrag evaluate --goldenset ...  # +preds -> results.json  (+ optional CI gate)
proofrag report   --results ...    # results -> scorecard.html
proofrag summary  --results ...    # results -> markdown summary
proofrag diff      --baseline ...  # compare vs a baseline; fail on regression
proofrag compare   --a ... --b ... # blind A/B of two RAG variants
proofrag demo                      # canned scorecard, no API key
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .judge import JUDGE_DIMENSIONS


def _eprint(*a):
    print(*a, file=sys.stderr)


def cmd_generate(args) -> int:
    from .corpus import load_corpus
    from .goldenset import generate, write_jsonl
    from .llm import LLM, LLMError

    chunks = load_corpus(
        args.corpus,
        max_chars=args.chunk_chars,
        include=args.include,
        exclude=args.exclude,
        respect_gitignore=not args.no_gitignore,
    )
    _eprint(f"Loaded {len(chunks)} chunks from {args.corpus}")
    try:
        records = generate(chunks, n=args.n, seed=args.seed, llm=LLM(model=args.model))
    except LLMError as e:
        _eprint(f"error: {e}")
        return 2
    write_jsonl(records, args.out)
    tiers = {}
    for r in records:
        tiers[r["difficulty"]] = tiers.get(r["difficulty"], 0) + 1
    _eprint(f"Wrote {len(records)} golden cases -> {args.out}  ({dict(tiers)})")
    return 0


def cmd_corpus(args) -> int:
    from .corpus import corpus_stats, load_corpus

    try:
        chunks = load_corpus(
            args.path,
            max_chars=args.chunk_chars,
            include=args.include,
            exclude=args.exclude,
            respect_gitignore=not args.no_gitignore,
        )
    except (OSError, ValueError) as e:
        _eprint(f"error: {e}")
        return 2

    stats = corpus_stats(chunks)
    _eprint(f"Loaded {stats['sources']} sources into {stats['chunks']} chunks")
    _eprint(f"  chars: {stats['chars']}")
    _eprint(f"  avg chunk chars: {stats['avg_chunk_chars']}")
    if stats["extensions"]:
        _eprint("  extensions:")
        for ext, count in stats["extensions"].items():
            _eprint(f"    {ext}: {count}")
    return 0


def cmd_evaluate(args) -> int:
    from .goldenset import read_jsonl
    from .judge import evaluate, write_results
    from .llm import LLM, LLMError

    goldenset = read_jsonl(args.goldenset)
    predictions = read_jsonl(args.predictions)
    matcher = None
    if args.semantic:
        from .embeddings import embedding_matcher

        matcher = embedding_matcher()
    try:
        if args.backend == "deepeval":
            from .backends import BackendError
            from .backends.deepeval_backend import evaluate_deepeval

            try:
                results = evaluate_deepeval(
                    goldenset, predictions, model=args.model, k=args.k, matcher=matcher
                )
            except BackendError as e:
                _eprint(f"error: {e}")
                return 2
        elif args.backend == "ragas":
            from .backends import BackendError
            from .backends.ragas_backend import evaluate_ragas

            try:
                results = evaluate_ragas(
                    goldenset, predictions, model=args.model, k=args.k, matcher=matcher
                )
            except BackendError as e:
                _eprint(f"error: {e}")
                return 2
        else:
            results = evaluate(
                goldenset, predictions, llm=LLM(model=args.model), k=args.k, matcher=matcher
            )
    except LLMError as e:
        _eprint(f"error: {e}")
        return 2
    write_results(results, args.out)
    agg = results["aggregate"]
    _eprint(f"Judged {results['n']} cases with {results['judge_fingerprint']} -> {args.out}")
    for k, v in agg.items():
        _eprint(f"  {k:>18}: {v:.3f}")

    gen = results.get("generation_metrics") or JUDGE_DIMENSIONS
    if args.fail_under is not None:
        vals = [agg[d] for d in gen if agg.get(d) is not None]
        overall = sum(vals) / len(vals) if vals else 0.0
        if overall < args.fail_under:
            _eprint(f"GATE FAIL: overall {overall:.3f} < {args.fail_under:.3f}")
            return 1
        _eprint(f"GATE PASS: overall {overall:.3f} >= {args.fail_under:.3f}")
    return 0


def cmd_run(args) -> int:
    from .goldenset import read_jsonl
    from .run import (
        RunError,
        callable_runner,
        endpoint_runner,
        parse_headers,
        run_predictions,
        write_predictions,
    )

    try:
        goldenset = read_jsonl(args.goldenset)
        if args.endpoint:
            runner = endpoint_runner(
                args.endpoint,
                timeout=args.timeout,
                headers=parse_headers(args.header),
            )
            adapter = args.endpoint
        else:
            runner = callable_runner(args.callable_spec, style=args.call_style)
            adapter = args.callable_spec

        predictions = run_predictions(goldenset, runner)
        write_predictions(predictions, args.out)
    except (OSError, RunError) as e:
        _eprint(f"error: {e}")
        return 2

    _eprint(f"Ran {len(predictions)} cases via {adapter} -> {args.out}")
    return 0


def cmd_validate(args) -> int:
    from .validate import format_report, validate_goldenset, write_report

    report = validate_goldenset(args.goldenset, corpus=args.corpus)
    if args.out:
        write_report(report, args.out)
    _eprint(format_report(report, strict=args.strict))
    if report["errors"] or (args.strict and report["warnings"]):
        return 1
    return 0


def cmd_report(args) -> int:
    from .judge import read_results
    from .scorecard import write_html

    results = read_results(args.results)
    if results.get("kind") == "comparison":
        from .scorecard import write_comparison_html

        write_comparison_html(results, args.out)
    else:
        write_html(results, args.out)
    _eprint(f"Wrote scorecard -> {args.out}")
    return 0


def cmd_summary(args) -> int:
    from .judge import read_results
    from .summary import render_markdown, write_markdown

    results = read_results(args.results)
    markdown = render_markdown(results)
    if args.out:
        write_markdown(markdown, args.out, append=args.append)
        _eprint(f"Wrote summary -> {args.out}")
    else:
        print(markdown, end="")
    return 0


def cmd_compare(args) -> int:
    from .compare import compare, write_comparison
    from .goldenset import read_jsonl
    from .llm import LLM, LLMError

    goldenset = read_jsonl(args.goldenset)
    preds_a = read_jsonl(args.a)
    preds_b = read_jsonl(args.b)
    matcher = None
    if args.semantic:
        from .embeddings import embedding_matcher

        matcher = embedding_matcher()
    try:
        res = compare(
            goldenset,
            preds_a,
            preds_b,
            a_name=args.a_name,
            b_name=args.b_name,
            llm=LLM(model=args.model),
            k=args.k,
            matcher=matcher,
            seed=args.seed,
        )
    except LLMError as e:
        _eprint(f"error: {e}")
        return 2
    write_comparison(res, args.out)
    w = res["wins"]
    _eprint(f"Compared {res['n']} cases (blind) with {res['judge_fingerprint']} -> {args.out}")
    _eprint(f"  {args.a_name}: {w['a']} wins | {args.b_name}: {w['b']} wins | tie: {w['tie']}")
    if res["win_rate_a"] is not None:
        _eprint(f"  {args.a_name} win rate: {res['win_rate_a']:.0%} of decided")
    if args.html:
        from .scorecard import write_comparison_html

        write_comparison_html(res, args.html)
        _eprint(f"  report -> {args.html}")
    return 0


def cmd_diff(args) -> int:
    from .diffing import diff, format_table
    from .judge import read_results

    baseline = read_results(args.baseline)
    candidate = read_results(args.candidate)
    res = diff(baseline, candidate, tolerance=args.tolerance)
    _eprint(format_table(res))

    if res["judge_mismatch"]:
        msg = (
            f"judge mismatch: baseline={res['baseline_judge']} vs "
            f"candidate={res['candidate_judge']} — scores are not comparable across judges"
        )
        if not args.allow_judge_mismatch:
            _eprint(
                f"error: {msg} (re-run both with the same judge, or pass --allow-judge-mismatch)"
            )
            return 2
        _eprint(f"warning: {msg}")

    if res["regressed"]:
        _eprint(f"REGRESSION: {', '.join(res['regressed'])} dropped more than {args.tolerance}")
        return 1
    _eprint(f"OK: no metric regressed beyond {args.tolerance}")
    return 0


def cmd_demo(args) -> int:
    if args.compare:
        from .demo import DEMO_COMPARISON
        from .scorecard import write_comparison_html

        write_comparison_html(DEMO_COMPARISON, args.out)
        _eprint(f"Wrote demo A/B comparison -> {args.out}  (open it in a browser)")
        return 0
    from .demo import DEMO_RESULTS
    from .scorecard import write_html

    write_html(DEMO_RESULTS, args.out)
    _eprint(f"Wrote demo scorecard -> {args.out}  (open it in a browser)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="proofrag", description="Zero-config RAG/LLM evaluation.")
    p.add_argument("--version", action="version", version=f"proofrag {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="synthesize a golden set from a corpus")
    g.add_argument("--corpus", required=True, help="file or directory of docs/code")
    g.add_argument("--out", default="goldenset.jsonl")
    g.add_argument("--n", type=int, default=20, help="number of cases")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--chunk-chars", type=int, default=1200)
    g.add_argument(
        "--include", action="append", default=[], help="include glob, e.g. 'docs/**/*.md'"
    )
    g.add_argument("--exclude", action="append", default=[], help="exclude glob, e.g. 'drafts/**'")
    g.add_argument("--no-gitignore", action="store_true", help="ignore .gitignore patterns")
    g.add_argument("--model", default=None, help="override judge/generator model")
    g.set_defaults(func=cmd_generate)

    co = sub.add_parser("corpus", help="inspect corpus loading and chunking")
    co.add_argument("path", help="file or directory of docs/code")
    co.add_argument("--chunk-chars", type=int, default=1200)
    co.add_argument("--include", action="append", default=[], help="include glob")
    co.add_argument("--exclude", action="append", default=[], help="exclude glob")
    co.add_argument("--no-gitignore", action="store_true", help="ignore .gitignore patterns")
    co.set_defaults(func=cmd_corpus)

    v = sub.add_parser("validate", help="validate a golden set before committing it")
    v.add_argument("--goldenset", required=True)
    v.add_argument("--corpus", default=None, help="optional corpus path for source coverage")
    v.add_argument("--out", default=None, help="write a JSON validation report")
    v.add_argument("--strict", action="store_true", help="fail on warnings as well as errors")
    v.set_defaults(func=cmd_validate)

    rn = sub.add_parser("run", help="run a RAG adapter over a golden set")
    rn.add_argument("--goldenset", required=True)
    source = rn.add_mutually_exclusive_group(required=True)
    source.add_argument("--endpoint", help="HTTP endpoint to POST {id, question} JSON")
    source.add_argument(
        "--callable",
        dest="callable_spec",
        help="Python callable as module:function; returns answer or {answer, retrieved_contexts}",
    )
    rn.add_argument("--out", default="predictions.jsonl")
    rn.add_argument(
        "--call-style",
        choices=["question", "record"],
        default="question",
        help="callable argument: question string or full golden record",
    )
    rn.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    rn.add_argument(
        "--header",
        action="append",
        default=[],
        help="HTTP header for --endpoint, e.g. 'Authorization: Bearer ...'",
    )
    rn.set_defaults(func=cmd_run)

    e = sub.add_parser("evaluate", help="judge predictions against a golden set")
    e.add_argument("--goldenset", required=True)
    e.add_argument("--predictions", required=True, help="jsonl of {id, answer, retrieved_contexts}")
    e.add_argument("--out", default="results.json")
    e.add_argument("--model", default=None)
    e.add_argument(
        "--backend",
        choices=["proofrag", "deepeval", "ragas"],
        default="proofrag",
        help="generation scoring backend (deepeval/ragas need matching extras)",
    )
    e.add_argument(
        "--k", type=int, default=5, help="cutoff for retrieval metrics (Recall@k, NDCG@k, ...)"
    )
    e.add_argument(
        "--semantic",
        action="store_true",
        help="use embedding cosine for chunk relevance instead of token overlap (needs [openai])",
    )
    e.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="CI gate: exit 1 if overall generation score < this (0-1)",
    )
    e.set_defaults(func=cmd_evaluate)

    r = sub.add_parser("report", help="render results.json to an HTML scorecard")
    r.add_argument("--results", required=True)
    r.add_argument("--out", default="scorecard.html")
    r.set_defaults(func=cmd_report)

    sm = sub.add_parser("summary", help="render results.json to markdown for CI")
    sm.add_argument("--results", required=True)
    sm.add_argument("--out", default=None, help="write markdown to this path (stdout if omitted)")
    sm.add_argument("--append", action="store_true", help="append to --out instead of replacing it")
    sm.set_defaults(func=cmd_summary)

    df = sub.add_parser("diff", help="compare results against a baseline; fail on regression")
    df.add_argument("--baseline", required=True, help="baseline results.json (a known-good run)")
    df.add_argument("--candidate", required=True, help="new results.json to compare")
    df.add_argument(
        "--tolerance", type=float, default=0.02, help="allowed drop before flagging a regression"
    )
    df.add_argument(
        "--allow-judge-mismatch", action="store_true", help="compare even if judge models differ"
    )
    df.set_defaults(func=cmd_diff)

    c = sub.add_parser("compare", help="blind A/B comparison of two RAG variants")
    c.add_argument("--goldenset", required=True)
    c.add_argument("--a", required=True, help="variant A predictions JSONL")
    c.add_argument("--b", required=True, help="variant B predictions JSONL")
    c.add_argument("--a-name", default="A", help="label for variant A (e.g. vector)")
    c.add_argument("--b-name", default="B", help="label for variant B (e.g. graphrag)")
    c.add_argument("--out", default="comparison.json")
    c.add_argument("--html", default=None, help="also write an HTML comparison report here")
    c.add_argument("--model", default=None)
    c.add_argument("--k", type=int, default=5)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument(
        "--semantic",
        action="store_true",
        help="embedding cosine for retrieval relevance (needs [openai])",
    )
    c.set_defaults(func=cmd_compare)

    d = sub.add_parser("demo", help="render a sample scorecard (no API key needed)")
    d.add_argument("--out", default="scorecard.html")
    d.add_argument("--compare", action="store_true", help="render a sample A/B comparison instead")
    d.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
