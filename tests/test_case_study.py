import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_studies.python_concurrency import download_corpus
from case_studies.python_concurrency.rag import (
    build_fts,
    rank_fts,
    rank_fts_reversed,
    rank_overlap,
)


def _chunks():
    return [
        {
            "source": "futures.rst",
            "chunk_id": "futures::0",
            "text": "A Future can be cancelled before its callable starts running.",
        },
        {
            "source": "queues.rst",
            "chunk_id": "queues::0",
            "text": "A queue coordinates items between producer and consumer threads.",
        },
        {
            "source": "tasks.rst",
            "chunk_id": "tasks::0",
            "text": "An asyncio Task wraps a coroutine and schedules its execution.",
        },
    ]


def test_case_study_retrievers_rank_matching_chunk_first():
    question = "When can a Future callable be cancelled?"
    chunks = _chunks()

    assert rank_overlap(chunks, question, k=1)[0]["chunk_id"] == "futures::0"
    assert rank_fts(build_fts(chunks), question, k=1)[0]["chunk_id"] == "futures::0"


def test_fault_injection_reverses_fts_rank_without_changing_result_count():
    chunks = _chunks()
    connection = build_fts(chunks)
    question = "Future queue Task callable producer coroutine"

    normal = rank_fts(connection, question, k=3)
    reversed_rank = rank_fts_reversed(connection, question, k=3)

    assert len(normal) == len(reversed_rank) == 3
    assert normal[0]["chunk_id"] == reversed_rank[-1]["chunk_id"]
    assert [chunk["chunk_id"] for chunk in normal] != [chunk["chunk_id"] for chunk in reversed_rank]


def test_published_audit_keeps_q008_and_q019_evidence():
    path = (
        Path(__file__).resolve().parents[1]
        / "case_studies"
        / "python_concurrency"
        / "goldenset.jsonl"
    )
    records = {
        record["id"]: record
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
        for record in [json.loads(line)]
    }

    q008 = "\n".join(records["q008"]["gold_contexts"])
    assert "Process.kill" in q008
    assert "Executor.shutdown" in q008

    q019 = records["q019"]
    assert [item["chunk_id"] for item in q019["context_metadata"]] == [
        "multiprocessing.shared_memory.rst::23",
        "multiprocessing.shared_memory.rst::24",
    ]
    evidence = "\n".join(q019["gold_contexts"])
    assert "silently stripped" in evidence
    assert "appending an extra non-0" in evidence
    assert "removing it when fetching" in evidence


def test_downloader_atomic_write_refuses_symlink_destination(tmp_path):
    target = tmp_path / "outside.txt"
    target.write_bytes(b"do not overwrite")
    destination = tmp_path / "document.rst"
    destination.symlink_to(target)

    with pytest.raises(ValueError, match="refusing to overwrite symlink"):
        download_corpus._atomic_write(destination, b"downloaded")

    assert target.read_bytes() == b"do not overwrite"


def test_downloader_atomic_write_does_not_use_predictable_temp_symlink(tmp_path):
    target = tmp_path / "outside.txt"
    target.write_bytes(b"do not overwrite")
    destination = tmp_path / "document.rst"
    destination.with_suffix(".rst.tmp").symlink_to(target)

    download_corpus._atomic_write(destination, b"downloaded")

    assert destination.read_bytes() == b"downloaded"
    assert target.read_bytes() == b"do not overwrite"


def test_downloader_routes_documents_license_and_manifest_through_atomic_write(
    tmp_path, monkeypatch
):
    corpus = tmp_path / "corpus"
    manifest = tmp_path / "sources.json"
    license_path = tmp_path / "LICENSE.python"
    document = b"trusted documentation"
    license_data = b"trusted license"
    document_url = "https://example.invalid/document.rst"
    license_url = "https://example.invalid/LICENSE"

    monkeypatch.setattr(download_corpus, "CORPUS_DIR", corpus)
    monkeypatch.setattr(download_corpus, "MANIFEST", manifest)
    monkeypatch.setattr(download_corpus, "LICENSE_PATH", license_path)
    monkeypatch.setattr(download_corpus, "LICENSE_URL", license_url)
    monkeypatch.setattr(download_corpus, "SOURCES", {"document.rst": document_url})
    monkeypatch.setattr(
        download_corpus,
        "EXPECTED_SHA256",
        {
            "document.rst": hashlib.sha256(document).hexdigest(),
            "LICENSE.python": hashlib.sha256(license_data).hexdigest(),
        },
    )
    monkeypatch.setattr(
        download_corpus,
        "_download",
        lambda url: license_data if url == license_url else document,
    )

    written = []
    atomic_write = download_corpus._atomic_write

    def record_write(path, data):
        written.append(path)
        atomic_write(path, data)

    monkeypatch.setattr(download_corpus, "_atomic_write", record_write)

    download_corpus.main()

    assert written == [corpus / "document.rst", license_path, manifest]
    assert (corpus / "document.rst").read_bytes() == document
    assert license_path.read_bytes() == license_data
