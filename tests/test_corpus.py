"""Offline tests for corpus loading and filtering."""

import pytest

from proofrag.cli import main
from proofrag.corpus import corpus_stats, load_corpus, read_document


def test_load_corpus_skips_default_ignored_dirs(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("public docs", encoding="utf-8")
    ignored = docs / "node_modules"
    ignored.mkdir()
    (ignored / "package.md").write_text("vendor docs", encoding="utf-8")

    chunks = load_corpus(str(docs))

    assert [c["source"] for c in chunks] == [str(docs / "guide.md")]


def test_load_corpus_honors_include_exclude_and_gitignore(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / ".gitignore").write_text("drafts/\n*.tmp.md\n", encoding="utf-8")
    (docs / "api.md").write_text("api docs", encoding="utf-8")
    (docs / "notes.txt").write_text("notes", encoding="utf-8")
    (docs / "scratch.tmp.md").write_text("scratch", encoding="utf-8")
    drafts = docs / "drafts"
    drafts.mkdir()
    (drafts / "future.md").write_text("future", encoding="utf-8")

    with pytest.raises(ValueError):
        load_corpus(str(docs), include=["*.md"], exclude=["api.md"])


def test_load_corpus_adds_chunk_metadata(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("alpha\n\nbeta", encoding="utf-8")

    chunks = load_corpus(str(path), max_chars=20)

    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["char_count"] == len("alpha\n\nbeta")
    assert chunks[0]["extension"] == ".md"


def test_read_document_extracts_html_text(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><style>.x{}</style></head><body><h1>Title</h1><script>x()</script><p>A &amp; B</p></body></html>",
        encoding="utf-8",
    )

    text = read_document(path)

    assert "Title" in text
    assert "A & B" in text
    assert "script" not in text.lower()


def test_corpus_stats_counts_sources_chunks_chars_and_extensions(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("a" * 10, encoding="utf-8")
    (docs / "b.txt").write_text("b" * 10, encoding="utf-8")

    stats = corpus_stats(load_corpus(str(docs)))

    assert stats["sources"] == 2
    assert stats["chunks"] == 2
    assert stats["chars"] == 20
    assert stats["extensions"] == {".md": 1, ".txt": 1}


def test_corpus_cli_prints_stats(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide docs", encoding="utf-8")

    assert main(["corpus", str(docs)]) == 0
    err = capsys.readouterr().err

    assert "Loaded 1 sources into 1 chunks" in err
    assert ".md: 1" in err


def test_corpus_cli_respects_exclude(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide docs", encoding="utf-8")

    assert main(["corpus", str(docs), "--exclude", "*.md"]) == 2
    assert "No readable text chunks" in capsys.readouterr().err
