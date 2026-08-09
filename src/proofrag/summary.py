"""Markdown summaries for CI systems.

GitHub Actions exposes `$GITHUB_STEP_SUMMARY`; writing a compact markdown version
of the scorecard there makes proofrag visible directly on the workflow page.
"""

from __future__ import annotations

import html

from .judge import JUDGE_DIMENSIONS
from .metrics import RETRIEVAL_METRICS

_LABELS = {
    "groundedness": "Groundedness",
    "correctness": "Correctness",
    "completeness": "Completeness",
    "citation_quality": "Citation quality",
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer relevancy",
    "relevancy": "Relevancy",
    "recall_at_k": "Recall@{k}",
    "precision_at_k": "Precision@{k}",
    "ndcg_at_k": "NDCG@{k}",
    "mrr": "MRR",
}


def render_markdown(results: dict) -> str:
    """Render normal or comparison results as markdown."""
    if results.get("kind") == "comparison":
        return render_comparison_markdown(results)
    return render_scorecard_markdown(results)


def render_scorecard_markdown(results: dict) -> str:
    agg = results.get("aggregate", {})
    records = results.get("records", [])
    gen = results.get("generation_metrics") or JUDGE_DIMENSIONS
    k = int(results.get("k", 5))

    vals = [agg.get(m, 0.0) for m in gen if agg.get(m) is not None]
    overall = sum(vals) / len(vals) if vals else 0.0
    lines = [
        "## proofrag scorecard",
        "",
        f"**Overall generation score:** {_pct(overall)}",
        "",
        f"- Cases: `{results.get('n', len(records))}`",
        f"- Backend: `{_inline(results.get('backend', 'proofrag'))}`",
        f"- Judge: `{_inline(results.get('judge_fingerprint', 'unknown'))}`",
        f"- Created: `{_inline(results.get('created', ''))}`",
        "",
        "### Metrics",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
    ]
    for metric in [*gen, *RETRIEVAL_METRICS]:
        lines.append(f"| {_cell(_label(metric, k))} | {_pct(agg.get(metric))} |")

    lines.extend(["", "### Weakest cases", "", "| Question | Difficulty | Gen | NDCG | Note |"])
    lines.append("| --- | --- | ---: | ---: | --- |")

    for record in _weakest(records, gen)[:5]:
        scores = record.get("scores", {})
        gen_score = _mean([scores[m] for m in gen if scores.get(m) is not None])
        retrieval = record.get("retrieval") or {}
        lines.append(
            "| {question} | {difficulty} | {gen} | {ndcg} | {note} |".format(
                question=_cell(record.get("question", "")),
                difficulty=_cell(record.get("difficulty", "")),
                gen=_pct(gen_score),
                ndcg=_pct(retrieval.get("ndcg_at_k")),
                note=_cell(record.get("rationale", "")),
            )
        )
    if not records:
        lines.append("| No records. |  |  |  |  |")
    return "\n".join(lines) + "\n"


def render_comparison_markdown(results: dict) -> str:
    wins = results.get("wins", {})
    a = _inline(results.get("a_name", "A"))
    b = _inline(results.get("b_name", "B"))
    lines = [
        "## proofrag A/B comparison",
        "",
        f"- Cases: `{results.get('n', 0)}`",
        f"- Judge: `{_inline(results.get('judge_fingerprint', 'unknown'))}`",
        f"- {a}: `{wins.get('a', 0)}` wins",
        f"- {b}: `{wins.get('b', 0)}` wins",
        f"- Tie: `{wins.get('tie', 0)}`",
    ]
    if results.get("win_rate_a") is not None:
        lines.append(f"- {a} win rate: `{_pct(results['win_rate_a'])}`")
    return "\n".join(lines) + "\n"


def write_markdown(markdown: str, path: str, append: bool = False) -> None:
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        if append:
            f.write("\n")
        f.write(markdown)


def _label(metric: str, k: int) -> str:
    return _LABELS.get(metric, metric.replace("_", " ").title()).format(k=k)


def _pct(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{round(float(value) * 100)}%"
    except (TypeError, ValueError):
        return "-"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _weakest(records: list[dict], gen: list[str]) -> list[dict]:
    def score(record: dict) -> float:
        scores = record.get("scores", {})
        return _mean([scores[m] for m in gen if scores.get(m) is not None]) or 0.0

    return sorted(records, key=score)


def _cell(value: object, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return html.escape(text, quote=False).replace("|", "\\|")


def _inline(value: object) -> str:
    return html.escape(str(value or ""), quote=False).replace("`", "\\`")
