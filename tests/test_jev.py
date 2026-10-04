"""Offline contract checks for the optional Jev backend."""

from __future__ import annotations

import copy
import io
import json
import urllib.error
from email.message import Message

import pytest

from proofrag.backends import BackendError
from proofrag.backends import jev_backend as jev
from proofrag.cli import main
from proofrag.metrics import exact_matcher


def _gold():
    return [
        {
            "id": "q1",
            "question": "What is documented?",
            "gold_answer": "A fact",
            "gold_contexts": ["A fact"],
        }
    ]


def _predictions():
    return [{"id": "q1", "answer": "A fact", "retrieved_contexts": ["A fact"]}]


def _response():
    return {
        "model": "jev-1.13.0",
        "answers": {
            dimension: {
                "type": "score",
                "score": 3.0,
                "confidence": 1.0,
                "probabilities": {"0": 0.0, "1": 0.0, "2": 0.0, "3": 1.0, "4": 0.0},
                "legend": dict(enumerate(question["criteria"])),
            }
            for dimension, question in jev._QUESTIONS.items()
        },
        "usage": {"input_tokens": 200, "output_tokens": 30},
    }


def test_jev_posts_typed_questions_and_preserves_uncertainty(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    requests = []

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 30
            return io.BytesIO(json.dumps(_response()).encode())

    monkeypatch.setattr(jev.urllib.request, "build_opener", lambda *args: Opener())
    result = jev.evaluate_jev(_gold(), _predictions(), model="jev-latest", matcher=exact_matcher())

    payload = json.loads(requests[0].data)
    assert requests[0].full_url == jev.ENDPOINT
    assert requests[0].get_header("Authorization") == "Bearer test-key"
    assert payload["state"]["retrieved_contexts"] == ["A fact"]
    assert payload["model"] == "jev-latest"
    assert all(
        q["type"] == "score" and len(q["criteria"]) == 5 for q in payload["questions"].values()
    )
    assert all("untrusted data" in q["instructions"] for q in payload["questions"].values())
    assert result["aggregate"]["correctness"] == 0.75
    assert result["aggregate"]["recall_at_k"] == 1.0
    assert result["records"][0]["judge_metadata"]["correctness"]["confidence"] == 1.0
    assert result["records"][0]["judge_metadata"]["usage"] == {
        "input_tokens": 200,
        "output_tokens": 30,
    }
    assert result["judge_metadata"]["calibration_status"] == "unknown"
    assert "jev-1.13.0" in result["judge_fingerprint"]
    assert "jev-latest" not in result["judge_fingerprint"]
    assert result["evaluation_errors"] == []


@pytest.mark.parametrize(
    "replacement",
    [
        {"score": float("nan")},
        {"score": True},
        {"score": 5.0},
        {"score": "3"},
        {"score": 10**1000},
        {"type": "noul"},
        {"confidence": -0.1},
        {"probabilities": {"3": 1.0}},
        {"probabilities": {str(i): 0.5 for i in range(5)}},
        {"score": 2.0},
    ],
)
def test_jev_records_invalid_metrics_without_inventing_scores(monkeypatch, replacement):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    response = copy.deepcopy(_response())
    response["answers"]["correctness"].update(replacement)
    monkeypatch.setattr(jev, "_request", lambda payload, key: response)

    result = jev.evaluate_jev(_gold(), _predictions())

    assert result["records"][0]["scores"]["correctness"] is None
    assert result["records"][0]["scores"]["groundedness"] == 0.75
    assert len(result["evaluation_errors"]) == 1
    assert result["evaluation_errors"][0]["error"].startswith("correctness unavailable")


def test_jev_requires_key_and_valid_coverage_before_network(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(BackendError, match="TYPESAFE_API_KEY"):
        jev.evaluate_jev(_gold(), _predictions())
    with pytest.raises(ValueError, match="missing prediction ids"):
        jev.evaluate_jev(_gold(), [])
    with pytest.raises(ValueError, match="greater than zero"):
        jev.evaluate_jev(_gold(), _predictions(), k=0)


def test_jev_failure_is_reported_and_retrieval_still_runs(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    def unavailable(payload, key):
        raise BackendError("Jev returned HTTP 401")

    monkeypatch.setattr(jev, "_request", unavailable)
    result = jev.evaluate_jev(_gold(), _predictions(), matcher=exact_matcher())

    assert all(score is None for score in result["records"][0]["scores"].values())
    assert result["evaluation_errors"] == [{"id": "q1", "error": "Jev returned HTTP 401"}]
    assert result["aggregate"]["recall_at_k"] == 1.0


def test_jev_backoff_honors_retry_after(monkeypatch):
    attempts = []
    pauses = []
    headers = Message()
    headers["Retry-After"] = "3"

    class Opener:
        def open(self, request, timeout):
            attempts.append(request)
            if len(attempts) < 3:
                raise urllib.error.HTTPError(jev.ENDPOINT, 429, "busy", headers, io.BytesIO())
            return io.BytesIO(json.dumps(_response()).encode())

    monkeypatch.setattr(jev.urllib.request, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(jev.time, "sleep", pauses.append)
    assert jev._request({}, "test-key")["model"] == "jev-1.13.0"
    assert len(attempts) == 3
    assert pauses == [3.0, 3.0]


@pytest.mark.parametrize("body", [b"not json", b"[]", b"x" * (jev._MAX_RESPONSE_BYTES + 1)])
def test_jev_rejects_invalid_or_oversized_response(monkeypatch, body):
    class Opener:
        def open(self, request, timeout):
            return io.BytesIO(body)

    monkeypatch.setattr(jev.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(BackendError):
        jev._request({}, "test-key")


def test_jev_cli_writes_results_and_fails_on_provider_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    golden_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    result_path = tmp_path / "results.json"
    card_path = tmp_path / "scorecard.html"
    golden_path.write_text(json.dumps(_gold()[0]) + "\n", encoding="utf-8")
    prediction_path.write_text(json.dumps(_predictions()[0]) + "\n", encoding="utf-8")
    arguments = [
        "evaluate",
        "--backend",
        "jev",
        "--goldenset",
        str(golden_path),
        "--predictions",
        str(prediction_path),
        "--out",
        str(result_path),
    ]
    monkeypatch.setattr(jev, "_request", lambda payload, key: _response())
    assert main(arguments) == 0
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["backend"] == "jev"
    assert main(["report", "--results", str(result_path), "--out", str(card_path)]) == 0
    assert "correctness" in card_path.read_text(encoding="utf-8")

    def unavailable(payload, key):
        raise BackendError("Jev returned HTTP 529")

    monkeypatch.setattr(jev, "_request", unavailable)
    assert main(arguments) == 2
    failed = json.loads(result_path.read_text(encoding="utf-8"))
    assert failed["evaluation_errors"]
    assert main(["report", "--results", str(result_path), "--out", str(card_path)]) == 0
    assert "Jev returned HTTP 529" in card_path.read_text(encoding="utf-8")


def test_jev_alias_is_locked_and_model_drift_invalidates_aggregate(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    requests = []
    gold = _gold() + [_gold()[0] | {"id": "q2"}]
    predictions = _predictions() + [_predictions()[0] | {"id": "q2"}]

    def drifting_provider(payload, key):
        requests.append(payload["model"])
        return _response() | {"model": "jev-1.13.0" if len(requests) == 1 else "jev-1.14.0"}

    monkeypatch.setattr(jev, "_request", drifting_provider)
    result = jev.evaluate_jev(gold, predictions, model="jev-latest")

    assert requests == ["jev-latest", "jev-1.13.0"]
    assert result["judge_metadata"]["model_consistent"] is False
    assert result["records"][0]["scores"]["correctness"] == 0.75
    assert result["records"][0]["judge_metadata"]["correctness"]["confidence"] == 1.0
    assert result["records"][0]["judge_metadata"]["usage"]["input_tokens"] == 200
    assert result["records"][1]["judge_metadata"]["model"] == "jev-1.14.0"
    assert all(value is None for value in result["records"][1]["scores"].values())
    assert all(result["aggregate"][dimension] == 0.0 for dimension in jev.JUDGE_DIMENSIONS)
    assert result["evaluation_errors"][0]["id"] == "q2"
    assert "model mismatch" in result["evaluation_errors"][0]["error"]


def test_jev_rejects_provider_model_that_disagrees_with_requested_version(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(jev, "_request", lambda payload, key: _response() | {"model": "jev-1.14.0"})

    result = jev.evaluate_jev(_gold(), _predictions(), model="jev-1.13.0")

    assert result["judge_metadata"]["model_consistent"] is False
    assert all(value is None for value in result["records"][0]["scores"].values())
    assert result["aggregate"]["correctness"] == 0.0
    assert "model mismatch" in result["evaluation_errors"][0]["error"]
