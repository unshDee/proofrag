"""Download the case-study corpus from immutable, allowlisted OWASP sources."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

COMMIT = "da4c967e9de854727f72bb2748dd98f76c888b06"
HOST = "raw.githubusercontent.com"
ROOT = f"https://{HOST}/OWASP/CheatSheetSeries/{COMMIT}/cheatsheets"
LICENSE_URL = f"https://{HOST}/OWASP/CheatSheetSeries/{COMMIT}/LICENSE.md"
HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
MANIFEST = HERE / "sources.json"
LICENSE_PATH = HERE / "LICENSE.owasp.md"
MAX_FILE_BYTES = 96 * 1024
MAX_TOTAL_BYTES = 512 * 1024
SOURCE_NAMES = (
    "Authentication_Cheat_Sheet.md",
    "Session_Management_Cheat_Sheet.md",
    "Password_Storage_Cheat_Sheet.md",
    "Forgot_Password_Cheat_Sheet.md",
    "Multifactor_Authentication_Cheat_Sheet.md",
    "Credential_Stuffing_Prevention_Cheat_Sheet.md",
)
ALLOWED_URLS = {f"{ROOT}/{name}" for name in SOURCE_NAMES} | {LICENSE_URL}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers
        raise ValueError(f"refusing redirect to {newurl}")


def _manifest_data() -> dict[str, Any]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("commit") != COMMIT:
        raise ValueError("sources.json does not match the pinned OWASP commit")
    entries = data.get("files")
    if not isinstance(entries, list) or len(entries) != len(SOURCE_NAMES):
        raise ValueError("sources.json has an unexpected file list")
    by_name = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
    if set(by_name) != set(SOURCE_NAMES):
        raise ValueError("sources.json file names do not match the fixed allowlist")
    for name, entry in by_name.items():
        if entry.get("url") != f"{ROOT}/{name}":
            raise ValueError(f"sources.json has an unexpected URL for {name}")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"sources.json has an invalid SHA-256 for {name}")
        size = entry.get("bytes")
        if not isinstance(size, int) or not 0 < size <= MAX_FILE_BYTES:
            raise ValueError(f"sources.json has an invalid byte count for {name}")
    license_entry = data.get("license")
    if not isinstance(license_entry, dict):
        raise ValueError("sources.json needs a license entry")
    if license_entry.get("url") != LICENSE_URL:
        raise ValueError("sources.json has an unexpected license URL")
    if license_entry.get("bytes") != 18_637:
        raise ValueError("sources.json has an unexpected license byte count")
    license_digest = license_entry.get("sha256")
    if not isinstance(license_digest, str) or len(license_digest) != 64:
        raise ValueError("sources.json has an invalid license SHA-256")
    data["files"] = [by_name[name] for name in SOURCE_NAMES]
    return data


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == HOST
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and url in ALLOWED_URLS
    )


def _download(url: str) -> bytes:
    if not _allowed(url):
        raise ValueError(f"refusing non-allowlisted URL: {url}")
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/plain", "User-Agent": "proofrag-owasp-case-study/1"},
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError(f"refusing redirected URL: {response.geturl()}")
        if getattr(response, "status", None) != 200:
            raise ValueError(f"expected HTTP 200 from {url}")
        content_type = response.headers.get_content_type()
        if content_type != "text/plain":
            raise ValueError(f"expected text/plain from {url}, got {content_type}")
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                declared_bytes = int(declared)
            except ValueError as error:
                raise ValueError(f"invalid Content-Length from {url}") from error
            if declared_bytes > MAX_FILE_BYTES:
                raise ValueError(f"refusing oversized file: {url}")
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"refusing oversized file: {url}")
    data.decode("utf-8", errors="strict")
    if b"\x00" in data:
        raise ValueError(f"refusing binary-looking file: {url}")
    return data


def _atomic_write(destination: Path, data: bytes) -> None:
    """Replace a regular file without following destination or temp-file symlinks."""
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
    if HERE.is_symlink() or CORPUS_DIR.is_symlink():
        raise ValueError("refusing a symlinked case-study or corpus directory")
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    manifest = _manifest_data()
    for entry in manifest["files"]:
        name = entry["name"]
        data = _download(entry["url"])
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError(f"refusing corpus larger than {MAX_TOTAL_BYTES:,} bytes")
        if len(data) != entry["bytes"]:
            raise ValueError(
                f"byte-count mismatch for {name}: expected {entry['bytes']}, got {len(data)}"
            )
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(
                f"SHA-256 mismatch for {name}: expected {entry['sha256']}, got {digest}"
            )
        _atomic_write(CORPUS_DIR / name, data)
        print(f"{name}: {len(data):,} bytes sha256:{digest[:12]}", flush=True)
    license_entry = manifest["license"]
    license_data = _download(license_entry["url"])
    total_bytes += len(license_data)
    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError(f"refusing download larger than {MAX_TOTAL_BYTES:,} bytes")
    license_digest = hashlib.sha256(license_data).hexdigest()
    if len(license_data) != license_entry["bytes"]:
        raise ValueError("byte-count mismatch for LICENSE.owasp.md")
    if license_digest != license_entry["sha256"]:
        raise ValueError("SHA-256 mismatch for LICENSE.owasp.md")
    _atomic_write(LICENSE_PATH, license_data)
    print(
        f"LICENSE.owasp.md: {len(license_data):,} bytes sha256:{license_digest[:12]}",
        flush=True,
    )
    print(f"Wrote {len(SOURCE_NAMES)} files to {CORPUS_DIR}", flush=True)


if __name__ == "__main__":
    main()
