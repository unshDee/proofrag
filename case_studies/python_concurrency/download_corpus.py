"""Download a small, pinned corpus from the official CPython repository."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

RELEASE = "v3.14.7"
COMMIT = "823f0323ee6ec1402088b73bce1a38473cac36dc"
HOST = "raw.githubusercontent.com"
ROOT = f"https://{HOST}/python/cpython/{COMMIT}/Doc/library"
CORPUS_DIR = Path(__file__).with_name("corpus")
MANIFEST = Path(__file__).with_name("sources.json")
LICENSE_PATH = Path(__file__).with_name("LICENSE.python")
LICENSE_URL = f"https://{HOST}/python/cpython/{COMMIT}/LICENSE"
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 300_000

SOURCES = {
    "asyncio-queue.rst": f"{ROOT}/asyncio-queue.rst",
    "asyncio-stream.rst": f"{ROOT}/asyncio-stream.rst",
    "asyncio-sync.rst": f"{ROOT}/asyncio-sync.rst",
    "asyncio-task.rst": f"{ROOT}/asyncio-task.rst",
    "concurrent.futures.rst": f"{ROOT}/concurrent.futures.rst",
    "multiprocessing.shared_memory.rst": f"{ROOT}/multiprocessing.shared_memory.rst",
    "queue.rst": f"{ROOT}/queue.rst",
    "threading.rst": f"{ROOT}/threading.rst",
}

# Verified against the official release files on 2026-08-09.
EXPECTED_SHA256 = {
    "asyncio-queue.rst": "c7312064e8c18f1e45656bbabb59949cdd0adf258f32595d073b2e66593244d2",
    "asyncio-stream.rst": "afc4687dca45f27cbe19750686e48a1d20bd48875c615a262e991f7331e74eb9",
    "asyncio-sync.rst": "ce9b6b4f31a3efaa71d58756696da49ec44b2c5547288c4009d4053273081f88",
    "asyncio-task.rst": "fec575ef139ea66769f9a1aa73e61933de267daf94c5c924e00af922f8a53a74",
    "concurrent.futures.rst": "a860180e171dce9f4d7925813fb9644eb24085c8ca34e1a26c1e933499cdfe7c",
    "multiprocessing.shared_memory.rst": "10f04327f469db0cca9f84d735a5660fa03da5fa9363559bab22940385938f5c",
    "queue.rst": "f621645ca7cae6602e5fc0ce64f4342ac741ace30cd98e42b45cb77d657b5ba8",
    "threading.rst": "19b4cb7d9eb59874a76812e850e7f67b71c501d774c8af5c91139b4fc6713b92",
    "LICENSE.python": "b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231",
}

ALLOWED_URLS = {*SOURCES.values(), LICENSE_URL}


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == HOST and url in ALLOWED_URLS


def _download(url: str) -> bytes:
    if not _allowed(url):
        raise ValueError(f"refusing non-allowlisted URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "proofrag-case-study/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        final_url = response.geturl()
        if not _allowed(final_url):
            raise ValueError(f"refusing redirect outside allowlist: {final_url}")
        content_type = response.headers.get_content_type()
        if content_type != "text/plain":
            raise ValueError(f"expected text/plain from {url}, got {content_type}")
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_FILE_BYTES:
            raise ValueError(f"refusing oversized file: {url}")
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"refusing oversized file: {url}")
    data.decode("utf-8")
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
    if CORPUS_DIR.is_symlink():
        raise ValueError(f"refusing symlinked corpus directory: {CORPUS_DIR}")
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    total_bytes = 0
    for name, url in SOURCES.items():
        data = _download(url)
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError(f"refusing corpus larger than {MAX_TOTAL_BYTES:,} bytes")
        digest = hashlib.sha256(data).hexdigest()
        expected = EXPECTED_SHA256.get(name)
        if expected and digest != expected:
            raise ValueError(f"SHA-256 mismatch for {name}: expected {expected}, got {digest}")
        destination = CORPUS_DIR / name
        _atomic_write(destination, data)
        files.append({"name": name, "url": url, "bytes": len(data), "sha256": digest})
        print(f"{name}: {len(data):,} bytes sha256:{digest[:12]}")

    license_data = _download(LICENSE_URL)
    license_digest = hashlib.sha256(license_data).hexdigest()
    if license_digest != EXPECTED_SHA256["LICENSE.python"]:
        raise ValueError(
            "SHA-256 mismatch for LICENSE.python: "
            f"expected {EXPECTED_SHA256['LICENSE.python']}, got {license_digest}"
        )
    _atomic_write(LICENSE_PATH, license_data)

    manifest = {
        "source": "Official CPython documentation",
        "release": RELEASE,
        "commit": COMMIT,
        "license": "Python Software Foundation License Version 2",
        "license_url": LICENSE_URL,
        "license_file": "LICENSE.python",
        "files": files,
    }
    _atomic_write(MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode())
    print(f"Wrote {len(files)} files to {CORPUS_DIR}")


if __name__ == "__main__":
    main()
