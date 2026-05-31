"""rag-eval command-line interface.

  rag-eval generate --corpus DIR     # docs  -> goldenset.jsonl
  rag-eval evaluate --goldenset ...  # +preds -> results.json  (+ optional CI gate)
  rag-eval report   --results ...    # results -> scorecard.html
  rag-eval demo                      # canned scorecard, no API key
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

    chunks = load_corpus(args.corpus, max_chars=args.chunk_chars)
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


def cmd_evaluate(args) -> int:
    from .goldenset import read_jsonl
    from .judge import evaluate, write_results
    from .llm import LLM, LLMError

    goldenset = read_jsonl(args.goldenset)
    predictions = read_jsonl(args.predictions)
    try:
        results = evaluate(goldenset, predictions, llm=LLM(model=args.model))
    except LLMError as e:
        _eprint(f"error: {e}")
        return 2
    write_results(results, args.out)
    agg = results["aggregate"]
    _eprint(f"Judged {results['n']} cases with {results['judge_fingerprint']} -> {args.out}")
    for k, v in agg.items():
        _eprint(f"  {k:>18}: {v:.3f}")

    if args.fail_under is not None:
        overall = sum(agg[d] for d in JUDGE_DIMENSIONS) / len(JUDGE_DIMENSIONS)
        if overall < args.fail_under:
            _eprint(f"GATE FAIL: overall {overall:.3f} < {args.fail_under:.3f}")
            return 1
        _eprint(f"GATE PASS: overall {overall:.3f} >= {args.fail_under:.3f}")
    return 0


def cmd_report(args) -> int:
    from .judge import read_results
    from .scorecard import write_html

    results = read_results(args.results)
    write_html(results, args.out)
    _eprint(f"Wrote scorecard -> {args.out}")
    return 0


def cmd_demo(args) -> int:
    from .demo import DEMO_RESULTS
    from .scorecard import write_html

    write_html(DEMO_RESULTS, args.out)
    _eprint(f"Wrote demo scorecard -> {args.out}  (open it in a browser)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rag-eval", description="Zero-config RAG/LLM evaluation.")
    p.add_argument("--version", action="version", version=f"rag-eval-kit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="synthesize a golden set from a corpus")
    g.add_argument("--corpus", required=True, help="file or directory of docs/code")
    g.add_argument("--out", default="goldenset.jsonl")
    g.add_argument("--n", type=int, default=20, help="number of cases")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--chunk-chars", type=int, default=1200)
    g.add_argument("--model", default=None, help="override judge/generator model")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("evaluate", help="judge predictions against a golden set")
    e.add_argument("--goldenset", required=True)
    e.add_argument("--predictions", required=True, help="jsonl of {id, answer, retrieved_contexts}")
    e.add_argument("--out", default="results.json")
    e.add_argument("--model", default=None)
    e.add_argument("--fail-under", type=float, default=None,
                   help="CI gate: exit 1 if overall generation score < this (0-1)")
    e.set_defaults(func=cmd_evaluate)

    r = sub.add_parser("report", help="render results.json to an HTML scorecard")
    r.add_argument("--results", required=True)
    r.add_argument("--out", default="scorecard.html")
    r.set_defaults(func=cmd_report)

    d = sub.add_parser("demo", help="render a sample scorecard (no API key needed)")
    d.add_argument("--out", default="scorecard.html")
    d.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
