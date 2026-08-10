"""Regression tests for evaluation integrity and untrusted inputs."""

from __future__ import annotations

import json
from typing import cast

import pytest

from proofrag.cli import main
from proofrag.compare import compare
from proofrag.diffing import diff
from proofrag.goldenset import generate, goldenset_fingerprint
from proofrag.judge import evaluate
from proofrag.llm import LLM, LLMError, _extract_json
from proofrag.metrics import exact_matcher, lexical_matcher, ndcg_at_k
from proofrag.run import RunError, endpoint_runner, join_predictions
from proofrag.scorecard import render
from proofrag.summary import render_markdown


class _JudgeFailure:
    fingerprint = "fake:failure"

    def complete_json(self, system, prompt):
        raise LLMError("offline")


class _Generator:
    def complete_json(self, system, prompt):
        return {"question": "What is documented?", "gold_answer": "A grounded answer."}


class _IncompleteJudge:
    fingerprint = "fake:incomplete"

    def complete_json(self, system, prompt):
        return {"groundedness": 1.0}


def _gold() -> list[dict]:
    return [
        {
            "id": "q001",
            "question": "Question?",
            "gold_answer": "Answer.",
            "gold_contexts": ["Context."],
            "difficulty": "single_doc",
            "sources": ["docs.md"],
        }
    ]


def _predictions() -> list[dict]:
    return [{"id": "q001", "answer": "Answer.", "retrieved_contexts": ["Context."]}]


def _write_jsonl(path, records) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_json_extraction_handles_braces_in_strings_and_rejects_nan():
    assert _extract_json('{"text": "use } and { literally", "score": 1}') == {
        "text": "use } and { literally",
        "score": 1,
    }
    with pytest.raises(LLMError):
        _extract_json('{"score": NaN}')


def test_openai_fingerprint_hashes_compatible_endpoint(monkeypatch):
    endpoint = "http://private-host:11434/v1"
    monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
    fingerprint = LLM(provider="openai", model="local-model").fingerprint
    assert "endpoint=" in fingerprint
    assert endpoint not in fingerprint


def test_exact_matcher_avoids_lexical_near_match():
    gold = "alpha beta gamma delta"
    near = "alpha beta gamma delta extra"
    assert lexical_matcher()(gold, near) is True
    assert exact_matcher()(gold, near) is False


def test_ndcg_penalizes_missing_gold_evidence_and_duplicate_hits():
    matcher = exact_matcher()
    gold = ["evidence a", "evidence b"]
    assert ndcg_at_k(gold, ["evidence a"], 2, matcher) < 1.0
    assert ndcg_at_k(gold, ["evidence a", "evidence a"], 2, matcher) < 1.0
    assert ndcg_at_k(gold, gold, 2, matcher) == 1.0


def test_ndcg_reassigns_ambiguous_matches_to_preserve_unique_evidence():
    matches = {
        ("gold-a", "ambiguous"),
        ("gold-b", "ambiguous"),
        ("gold-a", "only-a"),
    }

    def matcher(gold: str, chunk: str) -> bool:
        return (gold, chunk) in matches

    assert ndcg_at_k(["gold-a", "gold-b"], ["ambiguous", "only-a"], 2, matcher) == 1.0


def test_prediction_join_requires_unique_exact_coverage():
    with pytest.raises(ValueError, match="missing prediction ids"):
        join_predictions(_gold(), [])
    with pytest.raises(ValueError, match="duplicate id"):
        join_predictions(_gold(), [*_predictions(), *_predictions()])
    with pytest.raises(ValueError, match="unexpected prediction ids"):
        join_predictions(_gold(), [*_predictions(), {"id": "extra"}])
    with pytest.raises(ValueError, match="must be a JSON object"):
        join_predictions(_gold(), cast(list[dict], ["not an object"]))


def test_evaluation_records_judge_failures_and_cli_exits_two(tmp_path, monkeypatch):
    result = evaluate(_gold(), _predictions(), llm=cast(LLM, _JudgeFailure()))
    assert result["evaluation_errors"][0]["id"] == "q001"
    incomplete = evaluate(_gold(), _predictions(), llm=cast(LLM, _IncompleteJudge()))
    assert incomplete["evaluation_errors"]

    golden_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    result_path = tmp_path / "results.json"
    _write_jsonl(golden_path, _gold())
    _write_jsonl(prediction_path, _predictions())
    monkeypatch.setattr("proofrag.llm.LLM", lambda model=None: _JudgeFailure())

    assert (
        main(
            [
                "evaluate",
                "--goldenset",
                str(golden_path),
                "--predictions",
                str(prediction_path),
                "--out",
                str(result_path),
                "--exact",
            ]
        )
        == 2
    )
    written = json.loads(result_path.read_text(encoding="utf-8"))
    assert written["evaluation_errors"]
    assert written["matcher"] == "exact"


def test_diff_uses_declared_metrics_and_rejects_incompatible_runs():
    base = {
        "judge_fingerprint": "judge",
        "backend": "ragas",
        "k": 5,
        "n": 1,
        "generation_metrics": ["faithfulness"],
        "aggregate": {"faithfulness": 0.9},
    }
    candidate = base | {"aggregate": {"faithfulness": 0.1}}
    assert diff(base, candidate)["regressed"] == ["faithfulness"]

    missing = base | {"aggregate": {}}
    assert diff(base, missing)["regressed"] == ["faithfulness"]

    mismatch = diff(base, candidate | {"k": 10})
    assert [row["field"] for row in mismatch["configuration_mismatches"]] == ["k"]

    missing_fingerprint = diff(
        base,
        candidate | {"goldenset_fingerprint": "sha256:abc"},
    )
    assert [row["field"] for row in missing_fingerprint["configuration_mismatches"]] == [
        "goldenset_fingerprint"
    ]


def test_compare_records_reproducibility_metadata():
    class _Tie:
        fingerprint = "fake:tie"

        def complete_json(self, system, prompt):
            return {"winner": 0, "reason": "equal"}

    result = compare(_gold(), _predictions(), _predictions(), llm=cast(LLM, _Tie()), k=3)
    assert result["k"] == 3
    assert result["matcher"] == "lexical_jaccard_0.4"
    assert result["goldenset_fingerprint"] == goldenset_fingerprint(_gold())


def test_generation_returns_exact_count_and_uses_distinct_multi_doc_sources():
    chunks = [
        {"source": "a.md", "text": "A", "chunk_id": "a::0"},
        {"source": "b.md", "text": "B", "chunk_id": "b::0"},
    ]
    records = generate(chunks, n=10, llm=cast(LLM, _Generator()))
    assert len(records) == 10
    assert all(
        len(set(record["sources"])) == 2
        for record in records
        if record["difficulty"] == "multi_doc"
    )


def test_endpoint_rejects_remote_plaintext_with_or_without_credentials():
    for headers in ({}, {"X-API-Key": "secret"}):
        with pytest.raises(RunError, match="remote endpoints must use HTTPS"):
            endpoint_runner("http://example.com/ask", headers=headers)


def test_reports_escape_artifact_controlled_html():
    results = {
        "n": 1,
        "generation_metrics": ["<img src=x onerror=alert(1)>"],
        "aggregate": {"<img src=x onerror=alert(1)>": 1.0, "ndcg_at_k": 1.0},
        "records": [
            {
                "question": "<script>alert(1)</script>",
                "difficulty": "single_doc",
                "scores": {"<img src=x onerror=alert(1)>": 1.0},
                "retrieval": {"ndcg_at_k": 1.0},
                "rationale": "<b>unsafe</b>",
            }
        ],
    }
    assert "<script>" not in render(results)
    assert "<img src=x" not in render(results)
    assert "<script>" not in render_markdown(results)
