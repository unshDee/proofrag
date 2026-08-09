"""Apply the documented human-review edits to the generated golden set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
GENERATED = HERE / "goldenset.generated.jsonl"
OUTPUT = HERE / "goldenset.jsonl"
AUDIT = HERE / "artifacts" / "goldenset-audit.json"
PUBLISHED_CHUNK_CHARS = 700

REFUSAL = "I don't have enough information in the provided context to answer that."
EXPECTED_GENERATED_SHA256 = "775811372aff5a6c43cf56dab59acb0fe15730dcb3dc2bd755bb288f60652397"

EDITS: dict[str, dict[str, Any]] = {
    "q001": {
        "question": (
            "Can a ShareableList element change data type, and what happens if a "
            "replacement string exceeds its allocated storage?"
        ),
        "gold_answer": (
            "Yes. Replacing the float with 'dry ice' succeeds. Assigning a longer "
            "string raises ValueError because it exceeds the storage available for "
            "the existing string, and the previous value remains 'dry ice'."
        ),
    },
    "q003": {
        "question": (
            "Why does wait_on_future() deadlock in a ThreadPoolExecutor with max_workers=1?"
        ),
        "gold_answer": (
            "wait_on_future() occupies the executor's only worker, submits pow(5, 2) "
            "back to that executor, and blocks on f.result(). No free worker remains "
            "to run the queued task, so the Future never completes."
        ),
    },
    "q004": {
        "question": (
            "How does an InterpreterPoolExecutor worker report an uncaught exception "
            "raised by its current task?"
        ),
    },
    "q005": {
        "question": (
            "What does queue.Queue.put(item, block=False) raise when no slot is "
            "immediately available?"
        ),
        "gold_answer": "It raises queue.Full.",
    },
    "q007": {
        "question": (
            "When is a Python thread name reflected at OS level, and what truncation "
            "limits do the docs give for Linux and macOS?"
        ),
        "gold_answer": (
            "On supported platforms, the OS-level name is set when the thread starts. "
            "It may be truncated to 15 bytes on Linux or 63 bytes on macOS. Later "
            "changes reach the OS only when the currently running thread renames itself."
        ),
    },
    "q008": {
        "gold_answer": (
            "ProcessPoolExecutor.kill_workers() calls Process.kill() on every living "
            "worker, then calls Executor.shutdown() to free associated resources. No "
            "tasks should be submitted afterward."
        ),
        "chunk_ids": ["concurrent.futures.rst::36"],
    },
    "q010": {
        "question": (
            "For an asyncio.Queue that has not been shut down, what exception does "
            "get_nowait() raise when the queue is empty?"
        ),
        "gold_answer": "It raises asyncio.QueueEmpty.",
    },
    "q015": {
        "question": (
            "How do set(), clear(), and wait() affect an asyncio.Event's internal "
            "flag, and what is its initial state?"
        ),
        "gold_answer": (
            "set() makes the flag true, clear() resets it to false, and wait() blocks "
            "until it becomes true. The flag starts false."
        ),
    },
    "q017": {
        "question": (
            "What do asyncio streams let async/await code do without callbacks or "
            "low-level protocols and transports?"
        ),
        "gold_answer": (
            "They provide high-level primitives for sending and receiving data over "
            "network connections."
        ),
    },
    "q019": {
        "question": (
            "What workaround do the Python docs recommend when ShareableList strips "
            "trailing NUL bytes from bytes or str values?"
        ),
        "gold_answer": (
            "Append an extra non-NUL byte before storing the value, then remove that "
            "extra byte after fetching it."
        ),
        "chunk_ids": [
            "multiprocessing.shared_memory.rst::23",
            "multiprocessing.shared_memory.rst::24",
        ],
    },
    "q021": {
        "question": (
            "How should code handle two lifecycle hazards: a ThreadPoolExecutor "
            "initializer that raises, and an asyncio background Task without a strong "
            "reference?"
        ),
        "gold_answer": (
            "If a ThreadPoolExecutor initializer raises, all pending jobs and later "
            "submissions raise BrokenThreadPool. By contrast, an asyncio event loop "
            "keeps only weak references to Tasks, so an otherwise unreferenced "
            "background Task may be garbage-collected before completion. Retain a "
            "strong reference, such as storing Tasks in a set."
        ),
    },
    "q022": {
        "question": (
            "In the TCP echo-server example, which call is awaited to keep the server "
            "serving, and what happens generally when a Task's coroutine awaits a Future?"
        ),
        "gold_answer": (
            "The example enters async with server and awaits server.serve_forever(). "
            "When a Task's coroutine awaits a Future, the Task suspends that coroutine "
            "until the Future completes, then resumes it."
        ),
    },
    "q024": {
        "question": (
            "How do an asyncio.Condition and the stream operations in the TCP echo-client "
            "example solve different coordination problems?"
        ),
        "gold_answer": (
            "An asyncio.Condition combines Event and Lock behavior so tasks can wait "
            "for shared-state changes while coordinating exclusive access; its preferred "
            "form is async with, and multiple Conditions may share one Lock. Streams "
            "handle network I/O: open_connection() supplies a reader and writer used to "
            "send, drain, receive, close, and await closure."
        ),
    },
    "q025": {
        "question": (
            "What happens if Future.set_exception() is called after the Future is "
            "already done, and why can a thread awakened by Condition.notify() still "
            "not return from wait() immediately?"
        ),
        "gold_answer": (
            "Future.set_exception() raises InvalidStateError if the Future is already "
            "done. Condition.notify() and notify_all() do not release the lock, so "
            "awakened threads cannot return from wait() until the notifying thread "
            "relinquishes that lock."
        ),
    },
    "q026": {
        "question": (
            "Compare what qsize() tells callers and how shutdown affects puts and gets "
            "for asyncio.Queue and queue.Queue."
        ),
        "gold_answer": (
            "asyncio.Queue.qsize() returns the current number of items. After shutdown, "
            "future or blocked puts raise QueueShutDown, while graceful shutdown allows "
            "loaded items to be drained. queue.Queue.qsize() is approximate and does not "
            "guarantee that a later get or put will not block. A shut-down queue.Queue "
            "raises ShutDown from affected put or get operations."
        ),
    },
    "q027": {
        "question": (
            "What measured throughput or latency improvement does "
            "multiprocessing.shared_memory provide over multiprocessing.Queue for a "
            "1 GiB NumPy array?"
        ),
        "gold_answer": REFUSAL,
    },
    "q029": {
        "question": (
            "For what input size does the documented asyncio factorial example become "
            "faster than a synchronous iterative implementation?"
        ),
        "gold_answer": REFUSAL,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _published_chunks() -> list[dict[str, Any]]:
    """Load with proofrag 0.7.0's published paragraph-packing semantics."""
    manifest = json.loads((HERE / "sources.json").read_text())
    expected = {entry["name"]: entry["sha256"] for entry in manifest["files"]}
    paths = sorted(CORPUS.glob("*.rst"))
    if {path.name for path in paths} != set(expected):
        raise SystemExit("corpus files do not match sources.json")

    chunks: list[dict[str, Any]] = []
    for path in paths:
        if _sha256(path) != expected[path.name]:
            raise SystemExit(f"corpus SHA-256 mismatch for {path.name}")
        paragraphs = [part.strip() for part in path.read_text().split("\n\n") if part.strip()]
        bodies: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            if buffer and len(buffer) + len(paragraph) > PUBLISHED_CHUNK_CHARS:
                bodies.append(buffer.strip())
                buffer = ""
            buffer += paragraph + "\n\n"
        if buffer.strip():
            bodies.append(buffer.strip())

        for index, body in enumerate(bodies):
            chunks.append(
                {
                    "source": str(path),
                    "chunk_id": f"{path.name}::{index}",
                    "text": body,
                    "chunk_index": index,
                    "char_count": len(body),
                    "extension": path.suffix.lower(),
                }
            )
    return chunks


def _replace_contexts(record: dict[str, Any], chunk_ids: list[str]) -> None:
    chunks = {chunk["chunk_id"]: chunk for chunk in _published_chunks()}
    selected = [chunks[chunk_id] for chunk_id in chunk_ids]
    record["gold_contexts"] = [chunk["text"] for chunk in selected]
    record["sources"] = list(
        dict.fromkeys(
            f"case_studies/python_concurrency/corpus/{Path(chunk['source']).name}"
            for chunk in selected
        )
    )
    record["context_metadata"] = [
        {
            "source": f"case_studies/python_concurrency/corpus/{Path(chunk['source']).name}",
            "chunk_id": chunk["chunk_id"],
            "chunk_index": chunk["chunk_index"],
            "char_count": chunk["char_count"],
            "extension": chunk["extension"],
        }
        for chunk in selected
    ]


def main() -> None:
    if _sha256(GENERATED) != EXPECTED_GENERATED_SHA256:
        raise SystemExit(
            "goldenset.generated.jsonl changed; manually audit the new generated set "
            "instead of applying ID-based edits from the published run"
        )
    records = [json.loads(line) for line in GENERATED.read_text().splitlines() if line]
    assert [record["id"] for record in records] == [f"q{i:03d}" for i in range(30)]

    for record in records:
        edit = EDITS.get(record["id"])
        if not edit:
            continue
        for field in ("question", "gold_answer"):
            if field in edit:
                record[field] = edit[field]
        if "chunk_ids" in edit:
            _replace_contexts(record, edit["chunk_ids"])

    counts = {
        difficulty: sum(record["difficulty"] == difficulty for record in records)
        for difficulty in ("single_doc", "multi_doc", "unanswerable")
    }
    assert counts == {"single_doc": 21, "multi_doc": 6, "unanswerable": 3}
    assert all(
        record["gold_contexts"] == [] and record["sources"] == []
        for record in records
        if record["difficulty"] == "unanswerable"
    )

    OUTPUT.write_text("".join(json.dumps(record) + "\n" for record in records))
    AUDIT.parent.mkdir(exist_ok=True)
    audit = {
        "review_date": "2026-08-09",
        "reviewed_records": len(records),
        "edited_records": len(EDITS),
        "unchanged_records": len(records) - len(EDITS),
        "rejected_records": 0,
        "edited_ids": sorted(EDITS),
        "difficulty_counts": counts,
        "multi_doc_evidence_audited": "6/6; both contexts required for each answer",
        "unanswerable_full_corpus_audited": "3/3; no requested quantitative answer found",
        "chunker": "proofrag-0.7.0 paragraph packing; 700-character target",
        "corpus_hashes_verified": "8/8 against sources.json",
        "generated_sha256": _sha256(GENERATED),
        "goldenset_sha256": _sha256(OUTPUT),
    }
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n")


if __name__ == "__main__":
    main()
