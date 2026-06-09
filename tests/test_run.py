"""Offline tests for prediction adapters."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from proofrag.run import callable_runner, endpoint_runner, normalize_prediction, run_predictions


def test_callable_runner_loads_question_callable(tmp_path, monkeypatch):
    adapter = tmp_path / "rag_adapter.py"
    adapter.write_text(
        """
def answer(question):
    return {"answer": f"answered: {question}", "retrieved_contexts": ["ctx"]}
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    preds = run_predictions(
        [{"id": "q001", "question": "What is proofrag?"}],
        callable_runner("rag_adapter:answer"),
    )

    assert preds == [
        {
            "id": "q001",
            "answer": "answered: What is proofrag?",
            "retrieved_contexts": ["ctx"],
        }
    ]


def test_callable_runner_supports_record_style_and_tuple_return(tmp_path, monkeypatch):
    adapter = tmp_path / "record_adapter.py"
    adapter.write_text(
        """
def answer(record):
    return (record["question"].upper(), "single context")
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    preds = run_predictions(
        [{"id": "q002", "question": "record mode"}],
        callable_runner("record_adapter:answer", style="record"),
    )

    assert preds[0]["answer"] == "RECORD MODE"
    assert preds[0]["retrieved_contexts"] == ["single context"]


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        body = json.dumps(
            {
                "answer": f"endpoint answered: {payload['question']}",
                "retrieved_contexts": [self.headers.get("X-Proofrag-Test", "")],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


def test_endpoint_runner_posts_question_and_normalizes_response():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/ask"
        preds = run_predictions(
            [{"id": "q003", "question": "endpoint mode"}],
            endpoint_runner(url, timeout=5, headers={"X-Proofrag-Test": "ctx"}),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert preds == [
        {
            "id": "q003",
            "answer": "endpoint answered: endpoint mode",
            "retrieved_contexts": ["ctx"],
        }
    ]


def test_normalize_prediction_accepts_common_response_aliases():
    pred = normalize_prediction(
        {"id": "q004"},
        {"output": "answer text", "contexts": ["a", "b"]},
    )

    assert pred == {"id": "q004", "answer": "answer text", "retrieved_contexts": ["a", "b"]}
