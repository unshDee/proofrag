# Upgrading

Changing the judge invalidates old baselines. In each case below, rerun your baseline
with the new version and the same judge before gating new results. `diff` refuses
mismatched fingerprints on its own.

## To 0.10

The Anthropic judge no longer sends `temperature` (current API versions reject it),
and its fingerprint now reads `temperature=default`. Rerun Anthropic-judged baselines.
OpenAI baselines are unaffected.

## To 0.9

- The native generation and comparison prompts moved to version 3. They now encode
  evaluated text as data, and generation judging sees every retrieved context instead
  of only the first 4000 characters. JSON framing makes prompt confusion less likely,
  but it doesn't guarantee protection from prompt injection.
- Generation scores keep full precision for gates. Only displayed values are rounded.
- Adapters must return text answers and text contexts. Ambiguous objects and numeric
  answers are rejected instead of converted. Empty and `None` answers are still valid
  refusals.
- DeepEval and Ragas fingerprints moved to v2. Regenerate those baselines too.
