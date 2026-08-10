"""Deterministically parse RFC Editor plain text into section-bound chunks."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
MANIFEST = HERE / "sources.json"
CHUNK_CHARS = 700

_HEADING = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*|Appendix [A-Z]|[A-Z](?:\.\d+)*)\.\s{2,}"
    r"(?P<title>\S.*)$"
)
_STOP_TITLES = {"references", "acknowledgments", "acknowledgements", "authors' addresses"}


def load_chunks(corpus_dir: Path = CORPUS_DIR, max_chars: int = CHUNK_CHARS) -> list[dict]:
    """Verify the pinned corpus and return one common chunk universe."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if corpus_dir.is_symlink():
        raise ValueError(f"corpus path must not be a symlink: {corpus_dir}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("sources.json must contain source records")

    expected_names = {str(record["name"]) for record in records}
    paths = {path.name: path for path in corpus_dir.glob("*.txt") if path.is_file()}
    if set(paths) != expected_names:
        raise ValueError("corpus files do not match sources.json")

    chunks: list[dict] = []
    for record in records:
        path = paths[str(record["name"])]
        data = path.read_bytes()
        if len(data) != int(record["bytes"]):
            raise ValueError(f"byte-size mismatch for {path.name}")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path.name}")
        text = data.decode("utf-8-sig")
        chunks.extend(
            parse_rfc(
                text,
                source=f"case_studies/http_rfc_metadata/corpus/{path.name}",
                rfc=int(record["rfc"]),
                document_title=str(record["title"]),
                max_chars=max_chars,
            )
        )
    if not chunks:
        raise ValueError("verified RFC corpus produced no chunks")
    return chunks


def parse_rfc(
    text: str,
    *,
    source: str | Path,
    rfc: int,
    document_title: str,
    max_chars: int = CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """Parse body sections, omitting front matter, references, and layout noise."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    sections: list[tuple[str, str, list[str]]] = []
    current: tuple[str, str, list[str]] | None = None
    started = False

    for line in lines:
        match = _HEADING.match(line)
        if match:
            number = match.group("number")
            title = match.group("title").strip()
            if not started:
                if number != "1":
                    continue
                started = True
            if _top_level(number) and title.casefold() in _STOP_TITLES:
                break
            if current is not None:
                sections.append(current)
            current = (number, title, [])
        elif started and current is not None:
            current[2].append(line.rstrip())

    if current is not None:
        sections.append(current)
    if not sections:
        raise ValueError(f"could not find RFC body sections in {source}")

    chunks: list[dict[str, Any]] = []
    source_path = str(source)
    source_name = Path(source_path).name
    for number, title, body_lines in sections:
        paragraphs = _paragraphs(body_lines)
        for index, body in enumerate(_pack(paragraphs, max_chars)):
            chunks.append(
                {
                    "source": source_path,
                    "chunk_id": f"{source_name}::{number}::{index}",
                    "text": body,
                    "chunk_index": index,
                    "char_count": len(body),
                    "extension": ".txt",
                    "rfc": rfc,
                    "document_title": document_title,
                    "section_number": number,
                    "section_title": title,
                }
            )
    return chunks


def metadata_text(chunk: dict) -> str:
    """Text added only to the metadata-enriched search index."""
    return (
        f"RFC {chunk['rfc']}: {chunk['document_title']}\n"
        f"Section {chunk['section_number']}: {chunk['section_title']}\n"
        f"{chunk['text']}"
    )


def _top_level(number: str) -> bool:
    return number.isdigit() or number.startswith("Appendix ")


def _paragraphs(lines: list[str]) -> list[str]:
    text = "\n".join(lines).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"\n[ \t]*\n+", text) if part.strip()]


def _pack(paragraphs: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        for piece in _split_long(paragraph, max_chars):
            candidate = f"{buffer}\n\n{piece}" if buffer else piece
            if buffer and len(candidate) > max_chars:
                chunks.append(buffer)
                buffer = piece
            else:
                buffer = candidate
    if buffer:
        chunks.append(buffer)
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        cut = max(remaining.rfind("\n", 0, max_chars + 1), remaining.rfind(" ", 0, max_chars + 1))
        if cut < max_chars // 2:
            cut = max_chars
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces
