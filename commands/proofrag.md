---
description: Evaluate a RAG/LLM app — generate a golden set, judge it, and produce a scorecard
---

Use the **proofrag** skill to evaluate the RAG/LLM system in this project.

Target / focus (optional): $ARGUMENTS

Do this:
1. Make sure the `proofrag` CLI is available: run `proofrag --version`, and if it's
   missing install it with `uv tool install "proofrag[anthropic]"` (or `pipx install`),
   or just prefix commands with `uvx`.
2. Follow the proofrag skill workflow end to end:
   - generate a golden set from this project's docs/corpus,
   - run the project's RAG over each question to produce `predictions.jsonl`,
   - `proofrag evaluate` to judge,
   - `proofrag report` to render the HTML scorecard.
3. Report the scorecard path and the aggregate scores, and call out the weakest cases.

If you can't find the project's "ask a question" entrypoint, ask the user where it lives
before writing the prediction driver.
