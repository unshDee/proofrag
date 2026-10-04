# Research and release plan for 0.9.0

Reviewed on October 4, 2026. This note records the evidence behind this release,
its implementation decisions, and what has not been demonstrated.

## Implementation sequence

1. Fix evaluation integrity and regression gates with focused regression tests
2. Validate adapter inputs before any paid or stateful work and preserve artifacts
3. Add an optional typed Jev judge using the documented API and existing score schema
4. Refresh locked dependencies and pin current CI Actions to immutable commits
5. Update the portable skill, user docs, and release metadata
6. Run lint, full tests, package builds, installed artifact checks, and GitHub CI
7. Publish 0.9.0 only after required checks pass and prepare targeted outreach

## Evidence and decisions

- [Judging LLM-as-a-Judge](https://arxiv.org/abs/2609.02942), submitted August 31,
  2026 and accepted at EMNLP 2026, finds that rubric artifacts can influence judge
  outputs and counterfactual changes do not always change decisions appropriately.
  Decision: version prompts and rubrics and avoid equating a score with truth.
- [LongJudgeBench](https://arxiv.org/abs/2606.01629v4), revised August 28, 2026,
  reports judge instability on long-form outputs even with rubrics and references.
  Decision: fix the native judge's silent 4000-character context truncation. Include
  complete retrieved evidence and let provider context limits produce visible errors.
  This fixes a concrete information loss bug and does not solve judge instability.
- [TypeSafe API](https://docs.typesafe.ai/api) documents typed Score questions,
  ordered levels, probability-weighted scores, confidence, model identity, and usage.
  Decision: reuse proofrag's four generation dimensions with five explicit levels,
  normalize index scores, preserve uncertainty metadata, and keep core dependency-free.
- [Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13), reviewed
  October 2, 2026, documents prompt injection, long-context weaknesses, and numerical
  limitations. Decision: pin a model, frame state as untrusted data, validate every
  score distribution, and label dataset calibration as unknown.
- [Code Owns the Simulation, Jev Owns the Evaluation](https://arxiv.org/abs/2610.01834),
  submitted October 2, 2026, distinguishes judging supplied options from planning.
  Decision: integrate Jev as a judge of supplied answers. Keep generation and blind
  comparison on their current LLM providers.

## Limits

Offline tests establish request and response contracts and failure behavior. They
cannot establish hosted model quality, latency, cost, or calibration on a real RAG
workload. No human agreement or Jev speed claims are made in this release. Existing
0.8 case studies keep their original artifacts and measured results.

Before making comparative reliability claims, label representative correct answers,
unsupported claims, omissions, refusals, and injected instructions. Evaluate the
same frozen predictions with each backend, inspect disagreements with a human,
and report sample size, provider versions, token usage, and task-specific error
rates. Tune thresholds on one subset and report results on a held-out subset.
