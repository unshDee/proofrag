"""Score integrity checks that do not require optional provider SDKs."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from proofrag.backends import deepeval_backend as de
from proofrag.backends import ragas_backend as ragas
from proofrag.cli import main
from proofrag.diffing import diff
from proofrag.metrics import RETRIEVAL_METRICS
from proofrag.run import join_predictions


class _Metric:
    reason = "Checked against the evidence."

    def __init__(self, score):
        self.score = score

    def measure(self, case):
        return None


@pytest.mark.parametrize(
    "score", [True, False, "0.9", None, -0.01, 1.01, float("nan"), float("inf"), 10**1000]
)
def test_optional_backends_reject_invalid_scores_instead_of_coercing_them(score):
    assert de._measure(_Metric(score), object()) == (None, "")
    assert ragas._score(score) is None


@pytest.mark.parametrize("score", [0, 1, 0.7996])
def test_optional_backends_preserve_valid_numeric_scores(score):
    assert de._measure(_Metric(score), object()) == (float(score), _Metric.reason)
    assert ragas._score(score) == float(score)


@pytest.mark.parametrize("backend", [de, ragas])
def test_optional_aggregates_keep_precision_and_skip_unavailable_values(backend):
    records = [
        {
            "scores": dict.fromkeys(backend.GENERATION_METRICS, 0.7996),
            "retrieval": dict.fromkeys(RETRIEVAL_METRICS, 0.666),
        },
        {
            "scores": dict.fromkeys(backend.GENERATION_METRICS),
            "retrieval": dict.fromkeys(RETRIEVAL_METRICS, 0.667),
        },
    ]
    aggregate = (
        ragas._aggregate(records, backend.GENERATION_METRICS)
        if backend is ragas
        else de._aggregate(records)
    )
    assert all(aggregate[metric] == 0.7996 for metric in backend.GENERATION_METRICS)
    assert aggregate["recall_at_k"] == pytest.approx(0.6665)


def _stub_optional_backend(monkeypatch, backend, score):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    if backend == "deepeval":
        monkeypatch.setitem(
            sys.modules,
            "deepeval.test_case",
            SimpleNamespace(LLMTestCase=lambda **kwargs: SimpleNamespace(**kwargs)),
        )
        monkeypatch.setattr(de, "_deepeval_model", lambda provider, model: object())
        monkeypatch.setattr(
            de, "_build_metrics", lambda model: tuple(_Metric(score) for _ in range(3))
        )
    else:
        monkeypatch.setattr(ragas, "_ProofragRagasLLM", lambda cfg: SimpleNamespace(inner=object()))
        monkeypatch.setattr(ragas, "_ragas_embeddings", lambda: None)
        monkeypatch.setattr(
            ragas, "_build_metrics", lambda llm, embeddings: ([], ragas.GENERATION_METRICS)
        )
        monkeypatch.setattr(
            ragas, "_samples", lambda gold, predictions: ([], join_predictions(gold, predictions))
        )
        monkeypatch.setattr(
            ragas,
            "_evaluate_ragas_dataset",
            lambda samples, metrics: SimpleNamespace(
                scores=[dict.fromkeys(ragas.GENERATION_METRICS, score)]
            ),
        )


@pytest.mark.parametrize("backend", ["deepeval", "ragas"])
@pytest.mark.parametrize("score, expected_status", [(0.7996, 1), (True, 2), (1.01, 2)])
def test_optional_cli_gates_use_full_precision_and_fail_on_invalid_scores(
    tmp_path, monkeypatch, backend, score, expected_status
):
    _stub_optional_backend(monkeypatch, backend, score)
    gold_path = tmp_path / "gold.jsonl"
    pred_path = tmp_path / "predictions.jsonl"
    result_path = tmp_path / "results.json"
    gold_path.write_text(
        json.dumps({"id": "q1", "question": "q", "gold_answer": "a"}) + "\n",
        encoding="utf-8",
    )
    pred_path.write_text(
        json.dumps({"id": "q1", "answer": "a", "retrieved_contexts": ["a"]}) + "\n",
        encoding="utf-8",
    )
    status = main(
        [
            "evaluate",
            "--backend",
            backend,
            "--goldenset",
            str(gold_path),
            "--predictions",
            str(pred_path),
            "--out",
            str(result_path),
            "--fail-under",
            "0.8",
        ]
    )
    assert status == expected_status
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["judge_fingerprint"].startswith(f"{backend}-v2/")
    if expected_status == 1:
        assert result["aggregate"]["faithfulness"] == 0.7996
        assert result["evaluation_errors"] == []
    else:
        assert result["records"][0]["scores"]["faithfulness"] is None
        assert result["evaluation_errors"]


@pytest.mark.parametrize(
    "aggregate", [None, [], "bad", {}, {"correctness": None}, {"correctness": True}]
)
def test_diff_rejects_baselines_that_cannot_define_a_numeric_gate(aggregate):
    with pytest.raises(ValueError, match="aggregate"):
        diff({"aggregate": aggregate}, {"aggregate": {"correctness": 0.8}})


@pytest.mark.parametrize("aggregate", [None, [], "bad"])
def test_diff_rejects_nonobject_candidate_aggregates(aggregate):
    with pytest.raises(ValueError, match="aggregate"):
        diff({"aggregate": {"correctness": 0.8}}, {"aggregate": aggregate})


def test_diff_still_flags_an_empty_candidate_as_missing_metrics():
    assert diff({"aggregate": {"correctness": 0.8}}, {"aggregate": {}})["regressed"] == [
        "correctness"
    ]
