"""Download a byte-pinned corpus from the official RFC Editor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
MANIFEST = HERE / "sources.json"
TRUSTED_HOST = "www.rfc-editor.org"
MAX_FILE_BYTES = 600_000
MAX_TOTAL_BYTES = 1_500_000
_RFC_NAME = re.compile(r"rfc[0-9]+\.txt")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _sources() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("trusted_host") != TRUSTED_HOST:
        raise ValueError("sources.json has an unexpected trusted host")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("sources.json must contain a non-empty files list")
    names: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("sources.json file entries must be objects")
        name = record.get("name")
        if not isinstance(name, str) or _RFC_NAME.fullmatch(name) is None:
            raise ValueError("sources.json has an unsafe RFC filename")
        if name in names:
            raise ValueError(f"sources.json repeats {name}")
        names.add(name)
        if record.get("url") != f"https://{TRUSTED_HOST}/rfc/{name}":
            raise ValueError(f"sources.json has an unexpected URL for {name}")
        size = record.get("bytes")
        if not isinstance(size, int) or not 0 < size <= MAX_FILE_BYTES:
            raise ValueError(f"sources.json has an invalid byte count for {name}")
        digest = record.get("sha256")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError(f"sources.json has an invalid SHA-256 for {name}")
    return records


def _allowed(url: str, allowed_urls: set[str]) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == TRUSTED_HOST
        and parsed.username is None
        and parsed.password is None
        and url in allowed_urls
    )


def _download(url: str, allowed_urls: set[str]) -> bytes:
    if not _allowed(url, allowed_urls):
        raise ValueError(f"refusing non-allowlisted URL: {url}")
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/plain", "User-Agent": "proofrag-rfc-case-study/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        final_url = response.geturl()
        if not _allowed(final_url, allowed_urls):
            raise ValueError(f"refusing redirect outside allowlist: {final_url}")
        if response.headers.get_content_type() != "text/plain":
            raise ValueError(f"expected text/plain from {url}")
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_FILE_BYTES:
            raise ValueError(f"refusing oversized file: {url}")
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"refusing oversized file: {url}")
    data.decode("utf-8-sig")
    if b"\x00" in data:
        raise ValueError(f"refusing binary-looking file: {url}")
    return data


def _atomic_write(destination: Path, data: bytes) -> None:
    """Replace a file without following destination or temporary-file symlinks."""
    if destination.parent.is_symlink():
        raise ValueError(f"refusing symlinked output directory: {destination.parent}")
    if destination.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {destination}")
    fd, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    records = _sources()
    allowed_urls = {str(record["url"]) for record in records}
    if CORPUS_DIR.is_symlink():
        raise ValueError(f"refusing symlinked corpus directory: {CORPUS_DIR}")
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    expected_names = {str(record["name"]) for record in records}
    existing_names = {path.name for path in CORPUS_DIR.iterdir() if path.is_file()}
    unexpected = existing_names - expected_names
    if unexpected:
        raise ValueError(f"refusing corpus directory with unexpected files: {sorted(unexpected)}")

    total = 0
    for record in records:
        name = str(record["name"])
        url = str(record["url"])
        data = _download(url, allowed_urls)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"refusing corpus larger than {MAX_TOTAL_BYTES:,} bytes")
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != int(record["bytes"]):
            raise ValueError(f"byte-size mismatch for {name}")
        if digest != record["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {name}")
        _atomic_write(CORPUS_DIR / name, data)
        print(f"{name}: {len(data):,} bytes sha256:{digest[:12]}", flush=True)

    print(f"Wrote {len(records)} verified RFCs to {CORPUS_DIR}", flush=True)


if __name__ == "__main__":
    main()
