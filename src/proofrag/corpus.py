"""Load and chunk a corpus from a file or directory tree."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

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
    ".html",
    ".htm",
    ".pdf",
}

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "site-packages",
}


def load_corpus(
    path: str,
    max_chars: int = 1200,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    respect_gitignore: bool = True,
) -> list[dict]:
    """Return a flat list of chunks: {source, chunk_id, text}."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Corpus path not found: {path}")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    if p.is_symlink():
        raise ValueError(f"Corpus path must not be a symlink: {path}")
    root = p.parent if p.is_file() else p
    ignore_patterns = _ignore_patterns(root) if respect_gitignore and root.is_dir() else []
    files = [p] if p.is_file() else _walk_files(root, include, exclude, ignore_patterns)
    chunks: list[dict] = []
    for f in files:
        text = read_document(f)
        if not text:
            continue
        chunk_source = f.name if p.is_file() else f.relative_to(root).as_posix()
        for i, body in enumerate(_split(text, max_chars)):
            chunks.append(
                {
                    "source": str(f),
                    "chunk_id": f"{chunk_source}::{i}",
                    "text": body,
                    "chunk_index": i,
                    "char_count": len(body),
                    "extension": f.suffix.lower(),
                }
            )
    if not chunks:
        raise ValueError(f"No readable text chunks found under {path}")
    return chunks


def corpus_stats(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize loaded corpus chunks."""
    sources = sorted({str(c["source"]) for c in chunks})
    total_chars = sum(int(c.get("char_count") or len(c.get("text", ""))) for c in chunks)
    by_ext: dict[str, int] = {}
    for c in chunks:
        ext = str(c.get("extension") or Path(str(c.get("source", ""))).suffix.lower() or "(none)")
        by_ext[ext] = by_ext.get(ext, 0) + 1
    return {
        "sources": len(sources),
        "chunks": len(chunks),
        "chars": total_chars,
        "avg_chunk_chars": round(total_chars / len(chunks)) if chunks else 0,
        "extensions": dict(sorted(by_ext.items())),
    }


def read_document(path: Path) -> str:
    """Read a supported document into plain text."""
    if path.suffix.lower() not in TEXT_EXT:
        return ""
    if path.suffix.lower() == ".pdf":
        return _pdf_to_text(path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if path.suffix.lower() in {".html", ".htm"}:
        return _html_to_text(text)
    return text


def _split(text: str, max_chars: int) -> list[str]:
    """Greedy paragraph packing so chunks stay under max_chars where possible."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    paras: list[str] = []
    for raw in text.split("\n\n"):
        para = raw.strip()
        paras.extend(para[start : start + max_chars] for start in range(0, len(para), max_chars))
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


def _walk_files(
    root: Path,
    include: list[str] | None,
    exclude: list[str] | None,
    ignore_patterns: list[str],
) -> list[Path]:
    include = include or []
    exclude = exclude or []
    files: list[Path] = []
    for f in sorted(root.rglob("*")):
        if f.is_symlink() or not f.is_file():
            continue
        rel = f.relative_to(root).as_posix()
        if _ignored(rel, include, exclude, ignore_patterns):
            continue
        if f.suffix.lower() in TEXT_EXT:
            files.append(f)
    return files


def _ignored(
    rel: str,
    include: list[str],
    exclude: list[str],
    ignore_patterns: list[str],
) -> bool:
    if any(part in DEFAULT_IGNORE_DIRS for part in Path(rel).parts):
        return True
    if include and not _matches_any(rel, include):
        return True
    if _gitignored(rel, ignore_patterns) or _matches_any(rel, exclude):
        return True
    return False


def _matches_any(rel: str, patterns: list[str]) -> bool:
    return any(_matches(rel, p) for p in patterns)


def _gitignored(rel: str, patterns: list[str]) -> bool:
    ignored = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if _matches(rel, pattern[1:] if negated else pattern):
            ignored = not negated
    return ignored


def _matches(rel: str, pattern: str) -> bool:
    pattern = pattern.strip()
    if not pattern or pattern.startswith("#"):
        return False
    pattern = pattern.rstrip("/")
    if pattern.startswith("/"):
        pattern = pattern[1:]
    return (
        fnmatch(rel, pattern) or fnmatch(Path(rel).name, pattern) or rel.startswith(pattern + "/")
    )


def _ignore_patterns(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []
    try:
        return [
            line.strip()
            for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except OSError:
        return []


def _html_to_text(text: str) -> str:
    import html
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|section|article|h[1-6]|li)>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _pdf_to_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ValueError("PDF corpus loading needs: pip install 'proofrag[pdf]'") from e
    try:
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception as e:  # noqa: BLE001 - keep corpus loading resilient
        raise ValueError(f"Could not read PDF {path}: {e}") from e
