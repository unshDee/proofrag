"""Reports and CI artifacts must distinguish failures from valid scores."""

from proofrag.demo import DEMO_COMPARISON, DEMO_RESULTS
from proofrag.scorecard import render, render_comparison
from proofrag.summary import render_markdown


def test_failed_comparison_never_looks_like_a_winner_or_tie():
    result = DEMO_COMPARISON | {
        "wins": {"a": 1, "b": 0, "tie": 0},
        "n": 2,
        "n_judged": 1,
        "evaluation_errors": [{"id": "q2", "error": "timeout"}],
        "records": [
            {"question": "q1", "winner": "a"},
            {"question": "q2", "winner": "error"},
        ],
    }
    page = render_comparison(result)
    assert "Incomplete comparison" in page
    assert "Invalid run" in page
    assert "failed</span>" in page
    assert "width:100%" in page
    summary = render_markdown(result)
    assert "Failed judgments: `1`" in summary
    assert "Tie: `0`" in summary


def test_failed_evaluation_is_visible_in_both_reports():
    result = DEMO_RESULTS | {"evaluation_errors": [{"id": "q1", "error": "timeout"}]}
    assert "Invalid run" in render(result)
    assert "Invalid run" in render_markdown(result)


def test_compare_failure_still_writes_requested_html(tmp_path, monkeypatch):
    import json

    from proofrag.cli import main

    class FailingJudge:
        fingerprint = "offline"

        def __init__(self, **kwargs):
            pass

        def complete_json(self, *args):
            raise RuntimeError("offline provider failure")

    monkeypatch.setattr("proofrag.llm.LLM", FailingJudge)
    golden = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    golden.write_text(json.dumps({"id": "q1", "question": "Question?"}) + "\n")
    predictions.write_text(json.dumps({"id": "q1", "answer": "Answer"}) + "\n")
    page = tmp_path / "comparison.html"
    page.write_text("stale successful report")
    rc = main(
        [
            "compare",
            "--goldenset",
            str(golden),
            "--a",
            str(predictions),
            "--b",
            str(predictions),
            "--out",
            str(tmp_path / "comparison.json"),
            "--html",
            str(page),
        ]
    )
    assert rc == 2
    assert "Incomplete comparison" in page.read_text()
    assert "stale successful report" not in page.read_text()
