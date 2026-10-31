"""The wizard runs the whole loop end to end through its prompts."""

import io
import itertools
import json
import logging
import sys

import pytest

pytest.importorskip("rich")
pytest.importorskip("typer")

from rich.console import Console  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from proofrag import tui  # noqa: E402
from proofrag.llm import LLM  # noqa: E402
from proofrag.tui import app  # noqa: E402


@pytest.mark.parametrize("terminal", [True, False])
def test_bar_routes_earlier_log_handlers_through_rich(monkeypatch, terminal):
    # A handler holding the real stderr would write under the live bar and leave a
    # stale copy of it per log line; on a terminal rich must receive the writes instead
    monkeypatch.setattr(tui, "console", Console(file=io.StringIO(), force_terminal=terminal))
    handler = logging.StreamHandler(sys.stderr)
    real = handler.stream
    logging.getLogger("proofrag-test-app").addHandler(handler)
    try:
        with tui._bar("Asking your app", 1) as tick:
            assert handler.stream is sys.stderr
            assert (handler.stream is not real) == terminal
            tick()
        assert handler.stream is real
    finally:
        logging.getLogger("proofrag-test-app").removeHandler(handler)


def test_wizard_writes_every_artifact(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "keys.md").write_text("Rotate API keys by creating a new key, then revoking the old.")
    (docs / "limits.md").write_text("The batch endpoint accepts payloads up to 10 MB per request.")
    # A project module next to the docs, found via the working directory like a real app
    (tmp_path / "myapp.py").write_text(
        "def answer(q):\n    return {'answer': 'a', 'retrieved_contexts': ['10 MB']}\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path[:])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    n = itertools.count()
    reply = {"gold_answer": "a", "rationale": "ok", "groundedness": 0.9, "correctness": 0.8}
    reply |= {"completeness": 0.5, "citation_quality": 0.4}
    monkeypatch.setattr(
        LLM, "_complete", lambda self, s, p: json.dumps(reply | {"question": f"q{next(n)}?"})
    )

    result = CliRunner().invoke(
        app, ["--corpus", "docs", "--cases", "3"], input="callable\nmyapp:answer\nn\n"
    )

    assert result.exit_code == 0, result.output
    assert "Results" in result.output and "Judging answers" in result.output
    assert json.loads((tmp_path / "results.json").read_text())["n"] == 3
    assert "RAG Eval Scorecard" in (tmp_path / "scorecard.html").read_text()
    assert len((tmp_path / "predictions.jsonl").read_text().splitlines()) == 3
