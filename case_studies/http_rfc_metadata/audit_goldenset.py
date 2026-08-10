"""Bind the final golden set to its corpus and documented human review."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .rfc_corpus import CORPUS_DIR, load_chunks

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "goldenset.generated.jsonl"
GOLDENSET = HERE / "goldenset.jsonl"
REVIEW = HERE / "review.json"
AUDIT = HERE / "artifacts" / "goldenset-audit.json"
EXPECTED_DIFFICULTIES = {"single_doc": 15, "multi_doc": 4, "unanswerable": 2}
EXPECTED_GROUPS = {"structure": 8, "lexical": 7, "multi": 4, "unanswerable": 2}
EXPECTED_SINGLE_SOURCES = {9110: 3, 9111: 2, 9112: 2, 9113: 2, 9114: 2, 9204: 2, 9931: 2}
EXPECTED_REVIEW_SCOPE = (
    "Project-authored semantic audit against the pinned RFC corpus; not independent "
    "human validation."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _record_sha256(record: dict) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _chunk_ids(record: dict) -> list[str]:
    metadata = record.get("context_metadata")
    if not isinstance(metadata, list):
        return []
    return [str(item.get("chunk_id", "")) for item in metadata if isinstance(item, dict)]


def _review_decision(generated: dict, final: dict) -> str:
    if generated == final:
        return "accepted"
    if final.get("difficulty") == "unanswerable":
        return "replaced"
    if generated.get("difficulty") == final.get("difficulty") and _chunk_ids(
        generated
    ) == _chunk_ids(final):
        return "edited"
    return "replaced"


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def audit(
    generated_path: Path = GENERATED,
    goldenset_path: Path = GOLDENSET,
    review_path: Path = REVIEW,
    corpus_dir: Path = CORPUS_DIR,
) -> dict:
    generated_records = _read_jsonl(generated_path)
    records = _read_jsonl(goldenset_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    chunks = load_chunks(corpus_dir)
    by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    errors: list[str] = []

    generated_ids = [str(record.get("id", "")) for record in generated_records]
    generated_by_id = {str(record.get("id", "")): record for record in generated_records}
    ids = [str(record.get("id", "")) for record in records]
    expected_ids = [f"q{index:03d}" for index in range(21)]
    if generated_ids != expected_ids:
        errors.append("generated records must have ordered IDs q000 through q020")
    if ids != expected_ids:
        errors.append("records must have ordered IDs q000 through q020")
    difficulties = Counter(str(record.get("difficulty", "")) for record in records)
    groups = Counter(str(record.get("study_group", "")) for record in records)
    if dict(difficulties) != EXPECTED_DIFFICULTIES:
        errors.append(f"difficulty distribution must be {EXPECTED_DIFFICULTIES}")
    if dict(groups) != EXPECTED_GROUPS:
        errors.append(f"study_group distribution must be {EXPECTED_GROUPS}")

    single_sources: Counter[int] = Counter()
    corpus_text = "\n".join(str(chunk["text"]) for chunk in chunks).casefold()
    case_reviews = review.get("cases") if isinstance(review, dict) else None
    if not isinstance(case_reviews, dict):
        errors.append("review.json needs a cases object")
        case_reviews = {}
    if review.get("schema_version") != 2:
        errors.append("review.json schema_version must be 2")
    if review.get("reviewer") != "project audit":
        errors.append("review.json reviewer must be 'project audit'")
    if not _nonempty(review.get("reviewed_at")):
        errors.append("review.json needs a non-empty reviewed_at date")
    if review.get("validation_scope") != EXPECTED_REVIEW_SCOPE:
        errors.append("review.json must state that validation was not independent")
    if review.get("generated_goldenset_sha256") != _sha256(generated_path):
        errors.append("review.json is not bound to this generated golden-set SHA-256")
    if review.get("goldenset_sha256") != _sha256(goldenset_path):
        errors.append("review.json is not bound to this goldenset SHA-256")

    decisions: Counter[str] = Counter()
    for record in records:
        record_id = str(record.get("id", ""))
        difficulty = str(record.get("difficulty", ""))
        if not _nonempty(record.get("question")):
            errors.append(f"{record_id}: question must be non-empty")
        if not _nonempty(record.get("gold_answer")):
            errors.append(f"{record_id}: gold_answer must be non-empty")
        if not _nonempty(record.get("study_group")):
            errors.append(f"{record_id}: study_group must be non-empty")
        contexts = record.get("gold_contexts") or []
        sources = record.get("sources") or []
        metadata = record.get("context_metadata") or []
        if not all(isinstance(value, list) for value in (contexts, sources, metadata)):
            errors.append(f"{record_id}: contexts, sources, and context_metadata must be lists")
            continue
        if not (len(contexts) == len(sources) == len(metadata)):
            errors.append(f"{record_id}: context/source/metadata counts differ")

        if difficulty == "unanswerable":
            if contexts or sources or metadata:
                errors.append(f"{record_id}: unanswerable case must not carry evidence")
        else:
            if not contexts:
                errors.append(f"{record_id}: answerable case needs evidence")
            if difficulty == "single_doc" and len(contexts) != 1:
                errors.append(f"{record_id}: single_doc case must bind exactly one chunk")
            if difficulty == "multi_doc" and len(contexts) != 2:
                errors.append(f"{record_id}: multi_doc case must bind exactly two chunks")
            for index, item in enumerate(metadata):
                if not isinstance(item, dict):
                    errors.append(f"{record_id}: context metadata must contain objects")
                    continue
                chunk = by_id.get(str(item.get("chunk_id", "")))
                if chunk is None:
                    errors.append(f"{record_id}: unknown chunk_id {item.get('chunk_id')!r}")
                    continue
                if index >= len(contexts) or contexts[index] != chunk["text"]:
                    errors.append(f"{record_id}: gold context does not exactly match chunk_id")
                if index >= len(sources) or sources[index] != chunk["source"]:
                    errors.append(f"{record_id}: source does not match chunk_id")
                expected_metadata = {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                    "rfc": chunk["rfc"],
                    "section_number": chunk["section_number"],
                    "section_title": chunk["section_title"],
                    "char_count": chunk["char_count"],
                }
                if item != expected_metadata:
                    errors.append(f"{record_id}: context metadata does not exactly match chunk")
            if any(Path(str(value)).is_absolute() for value in sources):
                errors.append(f"{record_id}: sources must use stable repo-relative labels")
            if difficulty == "multi_doc" and len({Path(str(value)).name for value in sources}) < 2:
                errors.append(f"{record_id}: multi_doc evidence must use distinct RFCs")
            if difficulty == "single_doc" and metadata and isinstance(metadata[0], dict):
                single_sources[int(metadata[0].get("rfc", 0))] += 1

        decision = case_reviews.get(record_id)
        if not isinstance(decision, dict) or decision.get("approved") is not True:
            errors.append(f"{record_id}: missing approved project review")
            continue
        generated_record = generated_by_id.get(record_id)
        if generated_record is None:
            errors.append(f"{record_id}: no matching generated record")
            continue
        expected_decision = _review_decision(generated_record, record)
        actual_decision = decision.get("decision")
        if actual_decision not in {"accepted", "edited", "replaced"}:
            errors.append(f"{record_id}: decision must be accepted, edited, or replaced")
        elif actual_decision != expected_decision:
            errors.append(
                f"{record_id}: decision {actual_decision!r} conflicts with object change "
                f"({expected_decision!r})"
            )
        else:
            decisions[actual_decision] += 1
        if decision.get("generated_record_sha256") != _record_sha256(generated_record):
            errors.append(f"{record_id}: generated record SHA-256 is stale")
        if decision.get("final_record_sha256") != _record_sha256(record):
            errors.append(f"{record_id}: final record SHA-256 is stale")
        if not _nonempty(decision.get("notes")):
            errors.append(f"{record_id}: review notes must be non-empty")
        if decision.get("question_natural") is not True:
            errors.append(f"{record_id}: natural-question review is not confirmed")
        if difficulty == "unanswerable":
            searches = decision.get("absence_searches")
            if decision.get("full_corpus_absence_confirmed") is not True:
                errors.append(f"{record_id}: full-corpus absence is not confirmed")
            if (
                not isinstance(searches, list)
                or not searches
                or not all(_nonempty(search) for search in searches)
            ):
                errors.append(f"{record_id}: record at least one literal absence search")
            elif any(str(search).casefold() in corpus_text for search in searches):
                errors.append(f"{record_id}: an absence-search phrase occurs in the corpus")
        else:
            if decision.get("answer_supported") is not True:
                errors.append(f"{record_id}: answer support is not confirmed")
            if difficulty == "multi_doc" and decision.get("requires_all_contexts") is not True:
                errors.append(f"{record_id}: multi-context necessity is not confirmed")

    if dict(single_sources) != EXPECTED_SINGLE_SOURCES:
        errors.append(f"single-doc source distribution must be {EXPECTED_SINGLE_SOURCES}")
    if set(case_reviews) != set(expected_ids):
        errors.append("review.json case IDs must exactly match q000 through q020")

    return {
        "kind": "http_rfc_goldenset_audit",
        "schema_version": 2,
        "ok": not errors,
        "generated_goldenset_sha256": _sha256(generated_path),
        "goldenset_sha256": _sha256(goldenset_path),
        "records": len(records),
        "corpus_chunks": len(chunks),
        "difficulty_counts": dict(difficulties),
        "study_group_counts": dict(groups),
        "single_source_counts": dict(single_sources),
        "review_decision_counts": dict(decisions),
        "reviewer": review.get("reviewer"),
        "reviewed_at": review.get("reviewed_at"),
        "validation_scope": review.get("validation_scope"),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated", type=Path, default=GENERATED)
    parser.add_argument("--goldenset", type=Path, default=GOLDENSET)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--out", type=Path, default=AUDIT)
    args = parser.parse_args()
    result = audit(args.generated, args.goldenset, args.review)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"golden-set audit: {'PASS' if result['ok'] else 'FAIL'}", flush=True)
    for error in result["errors"]:
        print(f"  - {error}", flush=True)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
