# CI gates

There are two gates; use either or both.

**An absolute floor.** Exit non-zero if the overall score falls below a threshold:

```bash
proofrag evaluate --goldenset goldenset.jsonl --predictions predictions.jsonl \
  --out results.json --fail-under 0.7
```

**A regression check against a committed baseline**, which is a known-good `results.json`:

```bash
proofrag diff --baseline baseline.json --candidate results.json --tolerance 0.02
```

This prints a per-metric delta table and exits 1 if any metric drops by more than the
tolerance. `diff` refuses to compare runs whose datasets, backends, k values, matchers
or metric schemas differ. A different judge model also needs `--allow-judge-mismatch`.

## GitHub Action

The Action installs the CLI, evaluates, writes the scorecard and a job summary,
uploads both as an artifact (even when a gate fails), and applies both gates:

```yaml
- uses: unshDee/proofrag@v0.10.0
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  with:
    goldenset: eval/goldenset.jsonl
    predictions: predictions.jsonl     # produced by your RAG earlier in the job
    baseline: eval/baseline.json       # optional regression gate
    fail-under: "0.7"                  # optional absolute gate
```

If your workflow already handles the artifact or summary, turn them off with
`upload-artifact: "false"` or `summary: "false"`.

For a full runnable workflow, see [`examples/ci/proofrag-eval.yml`](../examples/ci/proofrag-eval.yml).
