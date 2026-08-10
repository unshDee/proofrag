"""Fail-closed publication gate for the project-audited OWASP golden set."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from proofrag.corpus import load_corpus

from .download_corpus import COMMIT, MANIFEST, SOURCE_NAMES, _atomic_write
from .rag import CHUNK_CHARS

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
GENERATED = HERE / "goldenset.generated.jsonl"
REVIEWED = HERE / "goldenset.reviewed.jsonl"
REVIEW = HERE / "review.json"
OUTPUT = HERE / "goldenset.jsonl"
AUDIT = HERE / "artifacts" / "goldenset-audit.json"
EXPECTED_COUNTS = {"single_doc": 16, "multi_doc": 5, "unanswerable": 3}
DECISIONS = {"accepted", "edited", "replaced"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise ValueError(f"refusing symlinked review input: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_number} must be a JSON object")
        records.append(value)
    return records


def _nonempty_string(value: object, field: str, record_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{record_id} needs a non-empty {field}")
    return value.strip()


def _string_list(value: object, field: str, record_id: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{record_id} needs a string list for {field}")
    return value


def _source_basename(source: str) -> str:
    return Path(source).name


def _load_corpus(
    corpus: Path, source_manifest: Path
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]]]:
    if corpus.is_symlink() or source_manifest.is_symlink():
        raise ValueError("refusing symlinked corpus or source manifest")
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if manifest.get("commit") != COMMIT:
        raise ValueError("source manifest does not match the pinned OWASP commit")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("source manifest needs a files list")
    expected = {
        entry["name"]: entry["sha256"]
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("sha256"), str)
    }
    if set(expected) != set(SOURCE_NAMES):
        raise ValueError("source manifest file names do not match the fixed allowlist")
    paths = sorted(corpus.glob("*.md"))
    if {path.name for path in paths} != set(SOURCE_NAMES):
        raise ValueError("downloaded corpus does not match the source manifest")
    texts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"refusing symlinked corpus file: {path}")
        digest = _sha256(path)
        if digest != expected[path.name]:
            raise ValueError(f"SHA-256 mismatch for {path.name}")
        texts[path.name] = path.read_text(encoding="utf-8", errors="strict")
        hashes[path.name] = digest
    chunks = load_corpus(str(corpus), max_chars=CHUNK_CHARS)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    if len(chunks_by_id) != len(chunks):
        raise ValueError("corpus chunk IDs are not unique")
    return texts, hashes, chunks_by_id


def verify_review(
    generated_path: Path = GENERATED,
    reviewed_path: Path = REVIEWED,
    review_path: Path = REVIEW,
    corpus: Path = CORPUS,
    source_manifest: Path = MANIFEST,
) -> dict[str, Any]:
    """Validate provenance, coverage, review decisions, and source-bound evidence."""
    for path in (generated_path, reviewed_path, review_path, source_manifest):
        if not path.is_file():
            raise ValueError(f"required review input is missing: {path}")
        if path.is_symlink():
            raise ValueError(f"refusing symlinked review input: {path}")

    review = json.loads(review_path.read_text(encoding="utf-8"))
    if not isinstance(review, dict) or review.get("schema_version") != 1:
        raise ValueError("review.json needs schema_version 1")
    if review.get("source_commit") != COMMIT:
        raise ValueError("review.json does not name the pinned OWASP commit")
    _nonempty_string(review.get("reviewed_by"), "reviewed_by", "review.json")
    _nonempty_string(review.get("reviewed_at"), "reviewed_at", "review.json")
    review_scope = _nonempty_string(review.get("review_scope"), "review_scope", "review.json")
    if review.get("generated_sha256") != _sha256(generated_path):
        raise ValueError("generated golden-set hash does not match review.json")
    if review.get("reviewed_sha256") != _sha256(reviewed_path):
        raise ValueError("reviewed golden-set hash does not match review.json")

    generated = _read_jsonl(generated_path)
    reviewed = _read_jsonl(reviewed_path)
    expected_ids = [f"q{index:03d}" for index in range(24)]
    generated_ids = [record.get("id") for record in generated]
    reviewed_ids = [record.get("id") for record in reviewed]
    if generated_ids != expected_ids or reviewed_ids != expected_ids:
        raise ValueError("generated and reviewed sets must contain q000 through q023 in order")

    cases = review.get("cases")
    if not isinstance(cases, dict) or set(cases) != set(expected_ids):
        raise ValueError("review.json must contain one audit entry for every case")
    corpus_text, corpus_hashes, chunks_by_id = _load_corpus(corpus, source_manifest)
    generated_by_id = {record["id"]: record for record in generated}
    difficulties: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    used_sources: set[str] = set()
    audited_unanswerable: list[str] = []
    audited_multi: list[str] = []
    full_corpus = "\n".join(corpus_text.values()).casefold()

    for record in reviewed:
        record_id = str(record["id"])
        question = _nonempty_string(record.get("question"), "question", record_id)
        _nonempty_string(record.get("gold_answer"), "gold_answer", record_id)
        if len(question) < 10:
            raise ValueError(f"{record_id} question is too short for a reviewed case")
        difficulty = _nonempty_string(record.get("difficulty"), "difficulty", record_id)
        if difficulty not in EXPECTED_COUNTS:
            raise ValueError(f"{record_id} has an invalid difficulty")
        difficulties[difficulty] += 1
        contexts = _string_list(record.get("gold_contexts"), "gold_contexts", record_id)
        sources = _string_list(record.get("sources"), "sources", record_id)
        metadata = record.get("context_metadata")
        if not isinstance(metadata, list) or any(not isinstance(item, dict) for item in metadata):
            raise ValueError(f"{record_id} needs an object list for context_metadata")
        if not len(contexts) == len(sources) == len(metadata):
            raise ValueError(f"{record_id} context, source, and metadata counts must match")
        source_names = list(dict.fromkeys(_source_basename(source) for source in sources))
        if any(Path(source).is_absolute() for source in sources):
            raise ValueError(f"{record_id} sources must use stable repo-relative paths")
        if any(Path(str(item.get("source", ""))).is_absolute() for item in metadata):
            raise ValueError(f"{record_id} context metadata must use repo-relative paths")
        if any(name not in corpus_text for name in source_names):
            raise ValueError(f"{record_id} cites a source outside the pinned corpus")

        case = cases[record_id]
        if not isinstance(case, dict):
            raise ValueError(f"{record_id} review entry must be an object")
        decision = case.get("decision")
        if decision not in DECISIONS:
            raise ValueError(f"{record_id} needs a valid review decision")
        decisions[str(decision)] += 1
        _nonempty_string(case.get("note"), "review note", record_id)
        changed = record != generated_by_id[record_id]
        if decision == "accepted" and changed:
            raise ValueError(f"{record_id} is marked accepted but differs from generated data")
        if decision in {"edited", "replaced"} and not changed:
            raise ValueError(f"{record_id} is marked {decision} but was not changed")

        if difficulty == "unanswerable":
            if contexts or sources or metadata:
                raise ValueError(f"{record_id} unanswerable case must not cite evidence")
            queries = _string_list(case.get("absence_queries"), "absence_queries", record_id)
            if len(queries) < 2:
                raise ValueError(f"{record_id} needs at least two full-corpus absence queries")
            for query in queries:
                normalized_query = query.strip().casefold()
                if len(normalized_query) < 3:
                    raise ValueError(f"{record_id} absence query is too short")
                if normalized_query in full_corpus:
                    raise ValueError(
                        f"{record_id} absence query is present in the full corpus: {query!r}"
                    )
            audited_unanswerable.append(record_id)
            continue

        if not contexts or not source_names:
            raise ValueError(f"{record_id} answerable case needs contexts and sources")
        if difficulty == "single_doc" and len(source_names) != 1:
            raise ValueError(f"{record_id} single_doc case must cite exactly one source")
        if difficulty == "multi_doc" and len(source_names) < 2:
            raise ValueError(f"{record_id} multi_doc case must cite distinct sources")
        for context, source, item in zip(contexts, sources, metadata, strict=True):
            chunk_id = item.get("chunk_id")
            if not isinstance(chunk_id, str) or chunk_id not in chunks_by_id:
                raise ValueError(f"{record_id} cites an unknown corpus chunk: {chunk_id!r}")
            chunk = chunks_by_id[chunk_id]
            if context != chunk["text"]:
                raise ValueError(f"{record_id} context does not exactly match {chunk_id}")
            expected_source = _source_basename(str(chunk["source"]))
            if _source_basename(source) != expected_source:
                raise ValueError(f"{record_id} source does not match {chunk_id}")
            if _source_basename(str(item.get("source", ""))) != expected_source:
                raise ValueError(f"{record_id} context metadata source does not match {chunk_id}")
            for field in ("chunk_index", "char_count", "extension"):
                if item.get(field) != chunk[field]:
                    raise ValueError(
                        f"{record_id} context metadata {field} does not match {chunk_id}"
                    )
        audited_sources = _string_list(case.get("evidence_sources"), "evidence_sources", record_id)
        if set(audited_sources) != set(source_names):
            raise ValueError(f"{record_id} audited evidence sources do not match the record")
        used_sources.update(source_names)
        if difficulty == "multi_doc":
            audited_multi.append(record_id)

    if dict(difficulties) != EXPECTED_COUNTS:
        raise ValueError(
            f"reviewed difficulty counts must be {EXPECTED_COUNTS}, got {dict(difficulties)}"
        )
    if used_sources != set(SOURCE_NAMES):
        missing = sorted(set(SOURCE_NAMES) - used_sources)
        raise ValueError(f"reviewed set does not cover all pinned sources: {missing}")

    return {
        "kind": "goldenset_project_review_audit",
        "schema_version": 1,
        "source_commit": COMMIT,
        "generated_sha256": _sha256(generated_path),
        "reviewed_sha256": _sha256(reviewed_path),
        "reviewed_by": review["reviewed_by"],
        "reviewed_at": review["reviewed_at"],
        "review_scope": review_scope,
        "records": len(reviewed),
        "difficulty_counts": dict(difficulties),
        "decision_counts": dict(decisions),
        "source_coverage": {"covered": len(used_sources), "total": len(SOURCE_NAMES)},
        "corpus_sha256": corpus_hashes,
        "multi_document_cases": audited_multi,
        "full_corpus_unanswerable_cases": audited_unanswerable,
    }


def publish_review(
    output: Path = OUTPUT,
    audit_path: Path = AUDIT,
    **verify_paths: Any,
) -> dict[str, Any]:
    """Publish the reviewed bytes only after every audit check succeeds."""
    audit = verify_review(**verify_paths)
    reviewed_path = verify_paths.get("reviewed_path", REVIEWED)
    if not isinstance(reviewed_path, Path):
        raise TypeError("reviewed_path must be a pathlib.Path")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    if audit_path.parent.is_symlink():
        raise ValueError(f"refusing symlinked artifact directory: {audit_path.parent}")
    _atomic_write(output, reviewed_path.read_bytes())
    _atomic_write(audit_path, (json.dumps(audit, indent=2) + "\n").encode())
    return audit


def main() -> None:
    audit = publish_review()
    print(
        f"Published {audit['records']} reviewed cases -> {OUTPUT} (audit: {AUDIT})",
        flush=True,
    )


if __name__ == "__main__":
    main()
