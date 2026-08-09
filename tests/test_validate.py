"""Offline tests for golden set validation."""

from __future__ import annotations

import json

from proofrag.cli import main
from proofrag.validate import format_report, validate_goldenset


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_validate_clean_goldenset_with_corpus_coverage(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    source = corpus / "api.md"
    source.write_text("Proofrag evaluates RAG apps with golden sets.", encoding="utf-8")
    goldenset = tmp_path / "goldenset.jsonl"
    _write_jsonl(
        goldenset,
        [
            {
                "id": "q001",
                "question": "What does proofrag evaluate?",
                "gold_answer": "Proofrag evaluates RAG apps with golden sets.",
                "gold_contexts": ["Proofrag evaluates RAG apps with golden sets."],
                "difficulty": "single_doc",
                "sources": [str(source)],
            }
        ],
    )

    report = validate_goldenset(str(goldenset), corpus=str(corpus))

    assert report["ok"] is True
    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["fingerprint"].startswith("sha256:")
    assert report["difficulty_counts"] == {"single_doc": 1}
    assert report["coverage"]["coverage"] == 1.0


def test_validate_reports_schema_errors_and_duplicate_ids(tmp_path):
    goldenset = tmp_path / "bad.jsonl"
    goldenset.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "q001",
                        "question": "What is missing?",
                        "gold_answer": "",
                        "gold_contexts": [],
                        "difficulty": "single_doc",
                        "sources": [],
                    }
                ),
                json.dumps(
                    {
                        "id": "q001",
                        "question": "What is missing?",
                        "gold_answer": "answer",
                        "gold_contexts": ["ctx"],
                        "difficulty": "made_up",
                        "sources": ["doc.md"],
                    }
                ),
                "{not json}",
            ]
        ),
        encoding="utf-8",
    )

    report = validate_goldenset(str(goldenset))
    codes = {issue["code"] for issue in report["errors"]}

    assert report["ok"] is False
    assert {
        "missing_gold_answer",
        "answerable_missing_contexts",
        "duplicate_id",
        "invalid_difficulty",
        "invalid_json",
    } <= codes


def test_validate_warns_for_unanswerable_contexts_and_strict_cli_fails(tmp_path):
    goldenset = tmp_path / "warn.jsonl"
    _write_jsonl(
        goldenset,
        [
            {
                "id": "q001",
                "question": "What is the private roadmap?",
                "gold_answer": "Maybe next quarter.",
                "gold_contexts": ["roadmap context"],
                "difficulty": "unanswerable",
                "sources": ["roadmap.md"],
            }
        ],
    )

    report = validate_goldenset(str(goldenset))
    codes = {issue["code"] for issue in report["warnings"]}

    assert report["errors"] == []
    assert {"unanswerable_has_contexts", "unanswerable_has_sources", "weak_refusal_answer"} <= codes
    assert main(["validate", "--goldenset", str(goldenset)]) == 0
    assert main(["validate", "--goldenset", str(goldenset), "--strict"]) == 1


def test_validate_writes_json_report_from_cli(tmp_path):
    goldenset = tmp_path / "goldenset.jsonl"
    report_path = tmp_path / "validation.json"
    _write_jsonl(
        goldenset,
        [
            {
                "id": "q001",
                "question": "What is proofrag?",
                "gold_answer": "An eval tool.",
                "gold_contexts": ["Proofrag is an eval tool."],
                "difficulty": "single_doc",
                "sources": ["docs.md"],
            }
        ],
    )

    assert main(["validate", "--goldenset", str(goldenset), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["kind"] == "goldenset_validation"


def test_format_report_includes_counts_and_issues(tmp_path):
    goldenset = tmp_path / "goldenset.jsonl"
    _write_jsonl(
        goldenset,
        [
            {
                "id": "q001",
                "question": "Question?",
                "gold_answer": "Answer.",
                "gold_contexts": ["Context."],
                "difficulty": "single_doc",
                "sources": [],
            }
        ],
    )

    out = format_report(validate_goldenset(str(goldenset)))
    assert "goldenset validation: PASS" in out
    assert "single_doc=1" in out
    assert "answerable_missing_sources" in out


def test_validate_rejects_empty_and_non_string_lists(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert {issue["code"] for issue in validate_goldenset(str(empty))["errors"]} == {
        "empty_goldenset"
    }

    invalid = tmp_path / "invalid.jsonl"
    _write_jsonl(
        invalid,
        [
            {
                "id": "q001",
                "question": "Question?",
                "gold_answer": "Answer.",
                "gold_contexts": [123],
                "difficulty": "single_doc",
                "sources": [456],
            }
        ],
    )
    codes = {issue["code"] for issue in validate_goldenset(str(invalid))["errors"]}
    assert {"invalid_gold_contexts", "invalid_sources"} <= codes


def test_validate_warns_when_multi_doc_uses_one_source(tmp_path):
    goldenset = tmp_path / "single-source.jsonl"
    _write_jsonl(
        goldenset,
        [
            {
                "id": "q001",
                "question": "Question?",
                "gold_answer": "Answer.",
                "gold_contexts": ["First.", "Second."],
                "difficulty": "multi_doc",
                "sources": ["same.md", "same.md"],
            }
        ],
    )

    codes = {issue["code"] for issue in validate_goldenset(str(goldenset))["warnings"]}
    assert "multi_doc_single_source" in codes
