"""Load and chunk a corpus from a file or directory tree."""

from __future__ import annotations

from pathlib import Path

TEXT_EXT = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".mdx",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".rs",
}


def load_corpus(path: str, max_chars: int = 1200) -> list[dict]:
    """Return a flat list of chunks: {source, chunk_id, text}."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Corpus path not found: {path}")
    files = (
        [p]
        if p.is_file()
        else sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in TEXT_EXT)
    )
    chunks: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, body in enumerate(_split(text, max_chars)):
            chunks.append({"source": str(f), "chunk_id": f"{f.name}::{i}", "text": body})
    if not chunks:
        raise ValueError(f"No readable text chunks found under {path}")
    return chunks


def _split(text: str, max_chars: int) -> list[str]:
    """Greedy paragraph packing so chunks stay under max_chars where possible."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: list[str] = []
    buf = ""
    for para in paras:
        if buf and len(buf) + len(para) > max_chars:
            out.append(buf.strip())
            buf = ""
        buf += para + "\n\n"
    if buf.strip():
        out.append(buf.strip())
    return out
