---
description: Evaluate a RAG/LLM app — generate a golden set, judge it, and produce a scorecard
---

Use the **ragproof** skill to evaluate the RAG/LLM system in this project.

Target / focus (optional): $ARGUMENTS

Do this:
1. Make sure the `ragproof` CLI is available: run `ragproof --version`, and if it's
   missing install it with `uv tool install "ragproof[anthropic]"` (or `pipx install`),
   or just prefix commands with `uvx`.
2. Follow the ragproof skill workflow end to end:
   - generate a golden set from this project's docs/corpus,
   - run the project's RAG over each question to produce `predictions.jsonl`,
   - `ragproof evaluate` to judge,
   - `ragproof report` to render the HTML scorecard.
3. Report the scorecard path and the aggregate scores, and call out the weakest cases.

If you can't find the project's "ask a question" entrypoint, ask the user where it lives
before writing the prediction driver.
