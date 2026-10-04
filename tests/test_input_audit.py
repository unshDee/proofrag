"""Regression checks for corpus privacy and evaluation input integrity."""

import pytest

from proofrag.corpus import load_corpus
from proofrag.goldenset import read_jsonl, write_jsonl
from proofrag.run import RunError, normalize_prediction, run_predictions
from proofrag.validate import validate_goldenset


@pytest.mark.parametrize(
    "raw",
    [
        {"error": "service unavailable"},
        {"answer": {"text": "answer"}},
        {"answer": False},
        {"answer": "answer", "contexts": {"secret": "text"}},
        {"answer": "answer", "contexts": ["valid", 42]},
        {"answer": "answer", "contexts": b"text"},
    ],
)
def test_adapter_rejects_malformed_answer_and_context_shapes(raw):
    with pytest.raises(RunError):
        normalize_prediction({"id": "q0"}, raw)


def test_adapter_accepts_empty_answer_and_context_iterators():
    result = normalize_prediction({"id": "q0"}, {"answer": None, "contexts": iter(["a", "b"])})
    assert result == {"id": "q0", "answer": "", "retrieved_contexts": ["a", "b"]}


@pytest.mark.parametrize(
    "records",
    [
        [],
        [{"id": "q0", "question": "one"}, {"id": "q0", "question": "two"}],
        [{"id": "q0", "question": "one"}, {"id": "q1", "question": " "}],
        [{"id": "q0", "question": "one"}, {"id": 1, "question": "two"}],
    ],
)
def test_invalid_golden_inputs_fail_before_running_any_adapter(records):
    calls = []

    def runner(record):
        calls.append(record)
        return "answer"

    with pytest.raises(RunError):
        run_predictions(records, runner)
    assert calls == []


@pytest.mark.parametrize("bad_value", [object(), float("nan"), float("inf")])
def test_failed_jsonl_serialization_preserves_existing_artifact(tmp_path, bad_value):
    output = tmp_path / "golden.jsonl"
    output.write_text('"existing artifact"\n', encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        write_jsonl([{"id": "q0"}, {"value": bad_value}], str(output))
    assert output.read_text(encoding="utf-8") == '"existing artifact"\n'
    assert list(tmp_path.iterdir()) == [output]


def test_jsonl_write_replaces_artifact_and_round_trips_unicode(tmp_path):
    output = tmp_path / "golden.jsonl"
    output.write_text("old output", encoding="utf-8")
    rows = [{"id": "q0", "question": "\u00e9"}]
    write_jsonl(rows, str(output))
    assert read_jsonl(str(output)) == rows
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("bad_line", ["{", "[]", "null", '"answer"'])
def test_jsonl_reports_physical_line_for_malformed_records(tmp_path, bad_line):
    path = tmp_path / "golden.jsonl"
    path.write_text('{"id": "q0"}\n\n' + bad_line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"golden.jsonl:3:"):
        read_jsonl(str(path))


def test_validate_reports_directory_input_without_crashing(tmp_path):
    report = validate_goldenset(str(tmp_path))
    assert not report["ok"]
    assert report["fingerprint"] is None
    assert "read_error" in {issue["code"] for issue in report["errors"]}


def test_validate_reports_invalid_utf8_without_crashing(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_bytes(b"\xff\n")
    report = validate_goldenset(str(path))
    assert not report["ok"]
    assert "read_error" in {issue["code"] for issue in report["errors"]}


def test_corpus_respects_nested_gitignore_with_local_negation(tmp_path):
    nested = tmp_path / "docs"
    nested.mkdir()
    (tmp_path / ".gitignore").write_text("*.private.md\n", encoding="utf-8")
    (nested / ".gitignore").write_text("*.md\n!public.md\n!visible.private.md\n", encoding="utf-8")
    (nested / "secret.md").write_text("nested secret", encoding="utf-8")
    (nested / "public.md").write_text("public", encoding="utf-8")
    (nested / "visible.private.md").write_text("explicitly visible", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path))] == [
        "public",
        "explicitly visible",
    ]
    assert len(load_corpus(str(tmp_path), respect_gitignore=False)) == 3


def test_corpus_anchored_ignore_applies_only_to_its_own_directory(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / ".gitignore").write_text("/guide.md\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("root secret", encoding="utf-8")
    (nested / "guide.md").write_text("public nested guide", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path))] == ["public nested guide"]


def test_corpus_does_not_reinclude_files_inside_ignored_directory(tmp_path):
    private = tmp_path / "nested" / "private"
    private.mkdir(parents=True)
    (tmp_path / ".gitignore").write_text("private/\n!nested/private/secret.md\n", encoding="utf-8")
    (private / "secret.md").write_text("secret", encoding="utf-8")
    (tmp_path / "public.md").write_text("public", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path))] == ["public"]


def test_corpus_does_not_follow_symlinked_gitignore(tmp_path):
    external = tmp_path.parent / (tmp_path.name + ".gitignore")
    external.write_text("*.md\n", encoding="utf-8")
    (tmp_path / ".gitignore").symlink_to(external)
    (tmp_path / "public.md").write_text("public", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path))] == ["public"]


def test_corpus_include_extension_does_not_match_parent_directory_name(tmp_path):
    nested = tmp_path / "draft.md"
    nested.mkdir()
    (nested / "notes.txt").write_text("text notes", encoding="utf-8")
    (tmp_path / "guide.md").write_text("markdown guide", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path), include=["*.md"])] == [
        "markdown guide"
    ]


def test_corpus_directory_ignore_does_not_hide_a_file_with_the_same_name(tmp_path):
    (tmp_path / ".gitignore").write_text("*.md/\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("public file", encoding="utf-8")
    private = tmp_path / "private.md"
    private.mkdir()
    (private / "secret.txt").write_text("private directory", encoding="utf-8")
    assert [chunk["text"] for chunk in load_corpus(str(tmp_path))] == ["public file"]
