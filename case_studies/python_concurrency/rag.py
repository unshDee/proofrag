"""Two tiny RAG variants used by the Python concurrency case study."""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from proofrag.corpus import load_corpus
from proofrag.llm import LLM

CORPUS_DIR = Path(__file__).with_name("corpus")
CHUNK_CHARS = 700
K = 5
_WORD = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "which",
    "with",
}

SYSTEM = (
    "Answer using only the supplied Python documentation excerpts. "
    "If they do not support an answer, say: I don't have enough information in the "
    "provided context to answer that. Cite supporting source filenames in square brackets."
)


def _tokens(text: str) -> list[str]:
    return list(dict.fromkeys(_WORD.findall(text.lower())))


def rank_overlap(chunks: list[dict], question: str, k: int = K) -> list[dict]:
    """Rank chunks by unique token overlap: intentionally naive baseline."""
    query = set(_tokens(question))
    return sorted(
        chunks,
        key=lambda chunk: (-len(query & set(_tokens(chunk["text"]))), chunk["chunk_id"]),
    )[:k]


def build_fts(chunks: list[dict]) -> sqlite3.Connection:
    """Build an in-memory FTS5 index using SQLite's built-in BM25 ranking."""
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE VIRTUAL TABLE chunks USING fts5(source UNINDEXED, chunk_id UNINDEXED, text)"
    )
    connection.executemany(
        "INSERT INTO chunks(source, chunk_id, text) VALUES (?, ?, ?)",
        [(chunk["source"], chunk["chunk_id"], chunk["text"]) for chunk in chunks],
    )
    return connection


def rank_fts(connection: sqlite3.Connection, question: str, k: int = K) -> list[dict[str, str]]:
    """Rank chunks with FTS5 OR matching and BM25."""
    terms = [token for token in _tokens(question) if token not in _STOPWORDS and len(token) > 1]
    if not terms:
        return []
    query = " OR ".join(f'"{term}"' for term in terms)
    rows = connection.execute(
        "SELECT source, chunk_id, text FROM chunks "
        "WHERE chunks MATCH ? ORDER BY bm25(chunks), chunk_id LIMIT ?",
        (query, k),
    ).fetchall()
    return [
        {"source": source, "chunk_id": chunk_id, "text": text} for source, chunk_id, text in rows
    ]


def rank_fts_reversed(
    connection: sqlite3.Connection, question: str, k: int = K
) -> list[dict[str, str]]:
    """Fault injection: reverse BM25 ordering while keeping the same top-k contract."""
    terms = [token for token in _tokens(question) if token not in _STOPWORDS and len(token) > 1]
    if not terms:
        return []
    query = " OR ".join(f'"{term}"' for term in terms)
    rows = connection.execute(
        "SELECT source, chunk_id, text FROM chunks "
        "WHERE chunks MATCH ? ORDER BY bm25(chunks) DESC, chunk_id LIMIT ?",
        (query, k),
    ).fetchall()
    return [
        {"source": source, "chunk_id": chunk_id, "text": text} for source, chunk_id, text in rows
    ]


@lru_cache(maxsize=1)
def _chunks() -> list[dict]:
    return load_corpus(str(CORPUS_DIR), max_chars=CHUNK_CHARS)


@lru_cache(maxsize=1)
def _fts() -> sqlite3.Connection:
    return build_fts(_chunks())


@lru_cache(maxsize=1)
def _llm() -> LLM:
    return LLM()


def _answer(question: str, retrieved: list[dict]) -> dict:
    excerpts = "\n\n---\n\n".join(
        f"Source: {Path(chunk['source']).name}\n{chunk['text']}" for chunk in retrieved
    )
    prompt = f"Documentation excerpts:\n{excerpts}\n\nQuestion: {question}\nAnswer concisely."
    answer = _llm()._complete(SYSTEM, prompt).strip()  # noqa: SLF001 - example adapter
    return {"answer": answer, "retrieved_contexts": [chunk["text"] for chunk in retrieved]}


def answer_overlap(question: str) -> dict:
    """proofrag callable adapter for naive token-overlap retrieval."""
    return _answer(question, rank_overlap(_chunks(), question))


def answer_fts5(question: str) -> dict:
    """proofrag callable adapter for SQLite FTS5/BM25 retrieval."""
    return _answer(question, rank_fts(_fts(), question))


def answer_fts5_reversed(question: str) -> dict:
    """Deliberately reverse BM25 ranking to demonstrate regression gating."""
    return _answer(question, rank_fts_reversed(_fts(), question))
