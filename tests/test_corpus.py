"""Offline tests for corpus loading and filtering."""

import builtins

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


def test_load_corpus_honors_gitignore_negation(tmp_path):
    docs = tmp_path / "docs"
    drafts = docs / "drafts"
    drafts.mkdir(parents=True)
    (docs / ".gitignore").write_text("drafts/**\n!drafts/keep.md\n", encoding="utf-8")
    (drafts / "drop.md").write_text("drop", encoding="utf-8")
    (drafts / "keep.md").write_text("keep", encoding="utf-8")

    chunks = load_corpus(str(docs))

    assert [chunk["text"] for chunk in chunks] == ["keep"]


def test_load_corpus_adds_chunk_metadata(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("alpha\n\nbeta", encoding="utf-8")

    chunks = load_corpus(str(path), max_chars=20)

    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["char_count"] == len("alpha\n\nbeta")
    assert chunks[0]["extension"] == ".md"


def test_load_corpus_uses_unique_relative_chunk_ids(tmp_path):
    docs = tmp_path / "docs"
    for folder in (docs / "api", docs / "guide"):
        folder.mkdir(parents=True)
        (folder / "index.md").write_text(str(folder), encoding="utf-8")

    chunk_ids = [chunk["chunk_id"] for chunk in load_corpus(str(docs))]

    assert chunk_ids == ["api/index.md::0", "guide/index.md::0"]


def test_load_corpus_skips_symlinks_and_ignores_only_relative_build_dirs(tmp_path):
    docs = tmp_path / "build" / "docs"
    docs.mkdir(parents=True)
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    (docs / "guide.md").write_text("public", encoding="utf-8")
    (docs / "linked.md").symlink_to(outside)

    chunks = load_corpus(str(docs))

    assert [chunk["text"] for chunk in chunks] == ["public"]


def test_load_corpus_enforces_chunk_limit_for_long_paragraphs(tmp_path):
    path = tmp_path / "long.md"
    path.write_text("a" * 25, encoding="utf-8")

    chunks = load_corpus(str(path), max_chars=10)

    assert [chunk["char_count"] for chunk in chunks] == [10, 10, 5]
    with pytest.raises(ValueError, match="greater than zero"):
        load_corpus(str(path), max_chars=0)


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


def test_read_document_pdf_reports_missing_extra(tmp_path, monkeypatch):
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ValueError, match="proofrag\\[pdf\\]"):
        read_document(path)


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
