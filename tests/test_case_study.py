import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_studies.http_rfc_metadata import download_corpus as rfc_download
from case_studies.http_rfc_metadata.rag import (
    build_fts as build_rfc_fts,
)
from case_studies.http_rfc_metadata.rag import (
    rank_fts as rank_rfc_fts,
)
from case_studies.http_rfc_metadata.rfc_corpus import metadata_text, parse_rfc
from case_studies.owasp_context_depth import download_corpus as owasp_download
from case_studies.owasp_context_depth.rag import (
    build_fts as build_owasp_fts,
)
from case_studies.owasp_context_depth.rag import (
    format_excerpts,
)
from case_studies.owasp_context_depth.rag import (
    rank_fts as rank_owasp_fts,
)
from case_studies.python_concurrency import download_corpus
from case_studies.python_concurrency.rag import (
    build_fts,
    rank_fts,
    rank_fts_reversed,
    rank_overlap,
)
from case_studies.summarize_usage import summarize


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


def test_rfc_parser_keeps_hard_chunk_limit_and_section_metadata():
    text = """Front matter

1.  Introduction

This paragraph explains the protocol in enough detail to require splitting.

1.1.  Connection Details

Connections have deterministic behavior for this synthetic example.

2.  References

This section must be excluded.
"""

    chunks = parse_rfc(
        text,
        source="case_studies/http_rfc_metadata/corpus/rfc9999.txt",
        rfc=9999,
        document_title="Synthetic HTTP",
        max_chars=36,
    )

    assert chunks
    assert max(chunk["char_count"] for chunk in chunks) <= 36
    assert {chunk["section_number"] for chunk in chunks} == {"1", "1.1"}
    assert all(not str(chunk["source"]).startswith("/Users/") for chunk in chunks)
    assert "RFC 9999: Synthetic HTTP" in metadata_text(chunks[0])


def test_rfc_metadata_index_returns_raw_chunks_only():
    chunks = [
        {
            "source": "rfc9114.txt",
            "chunk_id": "rfc9114.txt::4::0",
            "text": "A client can migrate a connection to a new network path.",
            "rfc": 9114,
            "document_title": "HTTP/3",
            "section_number": "4",
            "section_title": "HTTP Request Lifecycle",
        },
        {
            "source": "rfc9112.txt",
            "chunk_id": "rfc9112.txt::2::0",
            "text": "Message parsing uses a start line and header fields.",
            "rfc": 9112,
            "document_title": "HTTP/1.1",
            "section_number": "2",
            "section_title": "Message Format",
        },
    ]

    ranked = rank_rfc_fts(build_rfc_fts(chunks, include_metadata=True), "HTTP/3 lifecycle", 2)

    assert ranked[0]["chunk_id"] == "rfc9114.txt::4::0"
    assert ranked[0]["text"] == chunks[0]["text"]
    assert "HTTP Request Lifecycle" not in ranked[0]["text"]


def test_owasp_top_three_is_prefix_of_top_six():
    chunks = [
        {
            "source": f"sheet-{index}.md",
            "chunk_id": f"sheet-{index}.md::0",
            "text": f"authentication control shared guidance item {index}",
        }
        for index in range(8)
    ]
    connection = build_owasp_fts(chunks)

    top_three = rank_owasp_fts(connection, "authentication control guidance", 3)
    top_six = rank_owasp_fts(connection, "authentication control guidance", 6)

    assert [chunk["chunk_id"] for chunk in top_three] == [
        chunk["chunk_id"] for chunk in top_six[:3]
    ]


def test_owasp_context_bundle_enforces_judge_limit():
    safe = [{"source": "sheet.md", "text": "x" * 550} for _ in range(6)]
    assert len(format_excerpts(safe)) < 4_000

    with pytest.raises(ValueError, match="joined context exceeds"):
        format_excerpts([{"source": "sheet.md", "text": "x" * 4_001}])


def test_new_downloaders_reject_url_variants():
    rfc_urls = {record["url"] for record in rfc_download._sources()}
    rfc_url = next(iter(rfc_urls))
    assert rfc_download._allowed(rfc_url, rfc_urls)
    assert not rfc_download._allowed(f"{rfc_url}?download=1", rfc_urls)

    assert owasp_download._allowed(owasp_download.LICENSE_URL)
    assert not owasp_download._allowed(f"{owasp_download.LICENSE_URL}#fragment")


def test_rfc_manifest_rejects_unsafe_output_name(tmp_path, monkeypatch):
    manifest = tmp_path / "sources.json"
    manifest.write_text(
        json.dumps(
            {
                "trusted_host": rfc_download.TRUSTED_HOST,
                "files": [
                    {
                        "name": "../outside.txt",
                        "url": "https://www.rfc-editor.org/rfc/rfc9110.txt",
                        "bytes": 10,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rfc_download, "MANIFEST", manifest)

    with pytest.raises(ValueError, match="unsafe RFC filename"):
        rfc_download._sources()


def test_usage_summary_uses_provider_tokens_and_pinned_prices(tmp_path):
    rows = [
        {
            "provider": "openai",
            "model": "gpt-4o-mini-2024-07-18",
            "response_model": "gpt-4o-mini-2024-07-18",
            "system_fingerprint": "fp_test",
            "input_tokens": 1_000,
            "output_tokens": 100,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 200,
        }
    ]
    (tmp_path / "usage-generation.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = summarize(tmp_path)

    assert result["totals"]["calls"] == 1
    assert result["totals"]["input_tokens"] == 1_000
    assert result["phases"]["generation"]["system_fingerprints"] == ["fp_test"]
    assert result["totals"]["estimated_usd"] == 0.000195
