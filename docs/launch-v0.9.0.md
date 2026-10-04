# Launch packet for proofrag 0.9.0

Prepared October 4, 2026. These are proposals and drafts, not messages sent.
The goal is useful adoption that can lead to stars. No channel guarantees stars.

## The hook

A portable agent skill for repeatable RAG evaluation, with a dependency-free CLI,
human-reviewed golden sets, separate retrieval metrics, shareable scorecards, and
CI gates. The new release adds optional typed Jev judging and fixes cases where
an evaluation failure could look like valid evidence.

Lead with one real problem and a working demo. Avoid vague claims about being the
best evaluation framework or about Jev eliminating hallucinations.

## Reach out in this order

| Target | Why it fits | What to send | Read before posting |
| --- | --- | --- | --- |
| TypeSafe AI team | Direct relevance to the new Jev integration | Short technical walkthrough, scorecard, uncertainty metadata, request for API feedback and an optional showcase | [Official site](https://typesafe.ai/) and its linked [LinkedIn page](https://www.linkedin.com/company/typesafe-ai/) or hello@typesafe.ai |
| Your LinkedIn and X audience | Builders can understand a concrete RAG regression | Screenshot or short recording plus a copyable demo command and release link | Explain your role as maintainer and the limits of offline Jev tests |
| DEV Community | Python, testing, AI, and open source readers | Useful tutorial showing one retrieval failure and a CI gate, with proofrag disclosed as your project | [DEV](https://dev.to/) |
| Hacker News | Runnable developer tool with no signup needed for demo | Show HN for the overall tool only if it has not already been shown and you can stay to answer questions | [Show HN guidelines](https://news.ycombinator.com/showhn.html) say routine feature updates usually do not qualify |
| VoltAgent awesome-agent-skills | Existing portable skill is directly relevant | Concise directory entry after demonstrating real community usage | [Contribution rules](https://github.com/VoltAgent/awesome-agent-skills/blob/main/CONTRIBUTING.md) require usage and a description of ten words or fewer |

Do not submit to MCP server directories. This project ships an Agent Skill and a
CLI. A directory entry should describe the interface that actually exists.

## A two-week sequence

- Day 1: verify PyPI install, publish the release announcement on your own account,
  include one screenshot and the keyless demo, and answer every concrete question
- Day 2: send the TypeSafe note below with a reproducible request and an honest
  statement that hosted RAG accuracy has not been benchmarked
- Days 3 through 5: publish a tutorial called "When a RAG scorecard should fail CI"
  with one broken retrieval example, one corrected run, and both raw JSON artifacts
- Days 6 through 9: help two or three builders evaluate an existing docs chatbot,
  record their integration friction, and turn a recurring issue into a small fix
- Days 10 through 14: publish findings from those pilots with permission and clear
  sample sizes, then consider the skill directory submission if usage is established

Use existing case studies as evidence for the exact experiments they measure.
They do not benchmark the new Jev backend.

## LinkedIn draft

I maintain proofrag, a small open-source tool for checking RAG changes before they
ship. It generates candidate test cases from your docs, scores saved answers and
retrieved evidence separately, and writes a scorecard you can attach to a PR.

Version 0.9.0 adds an optional Jev judge with raw probabilities and confidence in
the result JSON. It also fixes several ways failed or malformed evaluations could
look like valid scores, including failed comparisons being counted as ties.

The core CLI has no runtime dependencies. Try the sample scorecard without an API
key:

`uvx proofrag==0.9.0 demo --out scorecard.html`

Jev integration has offline contract coverage. I have not benchmarked its hosted
accuracy on these RAG tasks. I would like feedback from people with a docs chatbot
and an existing test set.

https://github.com/unshDee/proofrag

## X draft

proofrag 0.9.0: optional Jev judge, separate retrieval scores, HTML scorecards and
CI regression gates. Failures stay failures, with raw uncertainty metadata.

Try without a key:
uvx proofrag==0.9.0 demo

https://github.com/unshDee/proofrag

## TypeSafe outreach draft

Hi TypeSafe team,

I maintain proofrag, an open-source RAG evaluation CLI and portable Agent Skill.
The 0.9.0 release adds optional Jev scoring through your documented System One
API. It retains model identity, rubric fingerprints, confidence, probabilities,
and token usage, and rejects malformed responses and model drift.

I have tested the API contract offline and kept calibration on user datasets
explicitly unknown. Would someone on your team be willing to check the integration
or suggest representative RAG judgment cases? If it looks useful, a link from your
examples or community showcase would help developers find it.

Repository: https://github.com/unshDee/proofrag
Release: https://github.com/unshDee/proofrag/releases/tag/v0.9.0
Backend: https://github.com/unshDee/proofrag/blob/v0.9.0/src/proofrag/backends/jev_backend.py

Thanks,
Ansh

## Potential directory entry

Title: `Add skill: unshDee/proofrag`

- **[unshDee/proofrag](https://github.com/unshDee/proofrag/tree/main/skills/proofrag)** - Evaluate RAG answers and retrieval with scorecards and CI gates

Use only after meeting the directory's community usage requirement. Check for an
existing entry or open PR immediately before submitting.

## Measure whether this works

Record GitHub stars, unique visitors, clones, new issue reporters, and integrations
on launch day and after seven and fourteen days. GitHub traffic covers a short
window, so capture it weekly. Ask adopters where they found the project. PyPI
versions being downloaded do not directly measure distinct users.

Prefer three genuine pilots and one reproducible tutorial over mass outreach.
Ask for feedback and useful issues. A small "star if useful" line on your own
announcement is fine. Do not ask for HN upvotes or coordinated comments.
