"""Golden set validation and coverage reporting.

Generated eval data is only useful if teams trust it enough to commit it. This
module checks the JSONL contract, catches common quality issues, and records a
stable fingerprint for review/CI logs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .corpus import load_corpus

ALLOWED_DIFFICULTIES = {"single_doc", "multi_doc", "unanswerable"}
REFUSAL_HINTS = ("not enough information", "provided context", "cannot answer")
_WORD = re.compile(r"[a-z0-9]+")


def validate_goldenset(path: str, corpus: str | None = None) -> dict[str, Any]:
    """Validate a golden set JSONL file and return a structured report."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    records = _read_records(path, errors)

    ids: set[str] = set()
    questions: dict[str, str] = {}
    difficulty_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for record in records:
        line = record["_line"]
        data = record["data"]
        if not isinstance(data, dict):
            _issue(errors, "record_type", "record must be a JSON object", line=line)
            continue

        record_id = _string(data.get("id"))
        if not record_id:
            _issue(errors, "missing_id", "record id is required", line=line)
        elif record_id in ids:
            _issue(errors, "duplicate_id", f"duplicate id {record_id!r}", line=line, id=record_id)
        else:
            ids.add(record_id)

        question = _string(data.get("question"))
        if not question:
            _issue(errors, "missing_question", "question is required", line=line, id=record_id)
        else:
            normalized = _normalize_question(question)
            previous = questions.get(normalized)
            if previous and previous != record_id:
                _issue(
                    warnings,
                    "duplicate_question",
                    f"question is very similar to {previous!r}",
                    line=line,
                    id=record_id,
                )
            questions[normalized] = record_id

        gold_answer = _string(data.get("gold_answer"))
        if not gold_answer:
            _issue(
                errors, "missing_gold_answer", "gold_answer is required", line=line, id=record_id
            )

        difficulty = _string(data.get("difficulty")) or "single_doc"
        difficulty_counts[difficulty] += 1
        if difficulty not in ALLOWED_DIFFICULTIES:
            _issue(
                errors,
                "invalid_difficulty",
                f"difficulty must be one of {sorted(ALLOWED_DIFFICULTIES)}",
                line=line,
                id=record_id,
            )

        contexts = data.get("gold_contexts")
        context_list = _string_list(contexts)
        if contexts is None:
            _issue(
                errors,
                "missing_gold_contexts",
                "gold_contexts is required",
                line=line,
                id=record_id,
            )
        elif context_list is None:
            _issue(
                errors,
                "invalid_gold_contexts",
                "gold_contexts must be a list",
                line=line,
                id=record_id,
            )

        sources = data.get("sources")
        source_list = _string_list(sources)
        if sources is None:
            _issue(errors, "missing_sources", "sources is required", line=line, id=record_id)
        elif source_list is None:
            _issue(errors, "invalid_sources", "sources must be a list", line=line, id=record_id)
        else:
            source_counts.update(source_list)

        if difficulty == "unanswerable":
            if context_list:
                _issue(
                    warnings,
                    "unanswerable_has_contexts",
                    "unanswerable cases should not include gold_contexts",
                    line=line,
                    id=record_id,
                )
            if source_list:
                _issue(
                    warnings,
                    "unanswerable_has_sources",
                    "unanswerable cases usually should not cite sources",
                    line=line,
                    id=record_id,
                )
            if gold_answer and not any(hint in gold_answer.lower() for hint in REFUSAL_HINTS):
                _issue(
                    warnings,
                    "weak_refusal_answer",
                    "unanswerable gold_answer should clearly refuse from missing context",
                    line=line,
                    id=record_id,
                )
        elif difficulty in {"single_doc", "multi_doc"}:
            if context_list == []:
                _issue(
                    errors,
                    "answerable_missing_contexts",
                    "answerable cases need at least one gold context",
                    line=line,
                    id=record_id,
                )
            if source_list == []:
                _issue(
                    warnings,
                    "answerable_missing_sources",
                    "answerable cases should cite at least one source",
                    line=line,
                    id=record_id,
                )
            if difficulty == "multi_doc" and context_list is not None and len(context_list) < 2:
                _issue(
                    warnings,
                    "multi_doc_single_context",
                    "multi_doc cases should include at least two gold contexts",
                    line=line,
                    id=record_id,
                )
            if difficulty == "multi_doc" and source_list is not None and len(set(source_list)) < 2:
                _issue(
                    warnings,
                    "multi_doc_single_source",
                    "multi_doc cases should cite at least two distinct sources",
                    line=line,
                    id=record_id,
                )

    coverage = _coverage(corpus, source_counts, warnings) if corpus else None
    if not records:
        _issue(errors, "empty_goldenset", "golden set must contain at least one record")
    return {
        "kind": "goldenset_validation",
        "schema_version": 1,
        "path": path,
        "fingerprint": _fingerprint(path) if Path(path).exists() else None,
        "n": len(records),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "coverage": coverage,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def format_report(report: dict[str, Any], strict: bool = False) -> str:
    """Format a validation report for terminal output."""
    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    status = "PASS" if not errors and (not strict or not warnings) else "FAIL"
    lines = [
        f"goldenset validation: {status}",
        f"  records: {report.get('n', 0)}",
        f"  fingerprint: {report.get('fingerprint') or '-'}",
    ]
    counts = report.get("difficulty_counts") or {}
    if counts:
        lines.append("  difficulties: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    coverage = report.get("coverage")
    if coverage:
        lines.append(
            "  source coverage: {covered}/{total} ({pct:.0%})".format(
                covered=coverage["covered_sources"],
                total=coverage["total_sources"],
                pct=coverage["coverage"],
            )
        )
    lines.extend(_issue_lines("errors", errors))
    lines.extend(_issue_lines("warnings", warnings))
    return "\n".join(lines)


def write_report(report: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def _read_records(path: str, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    records.append({"_line": line_no, "data": json.loads(line)})
                except json.JSONDecodeError as e:
                    _issue(errors, "invalid_json", f"invalid JSON: {e.msg}", line=line_no)
    except OSError as e:
        _issue(errors, "read_error", str(e))
    return records


def _coverage(
    corpus: str,
    source_counts: Counter[str],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        corpus_sources = sorted({chunk["source"] for chunk in load_corpus(corpus)})
    except (OSError, ValueError) as e:
        _issue(warnings, "corpus_read_error", f"could not read corpus for coverage: {e}")
        return {
            "corpus": corpus,
            "total_sources": 0,
            "covered_sources": 0,
            "coverage": 0.0,
            "missing_sources": [],
            "unknown_sources": sorted(source_counts),
        }

    corpus_set = set(corpus_sources)
    used_set = set(source_counts)
    covered = sorted(corpus_set & used_set)
    missing = sorted(corpus_set - used_set)
    unknown = sorted(used_set - corpus_set)
    if unknown:
        _issue(
            warnings,
            "unknown_sources",
            f"golden set cites {len(unknown)} source(s) outside the loaded corpus",
        )
    return {
        "corpus": corpus,
        "total_sources": len(corpus_sources),
        "covered_sources": len(covered),
        "coverage": round(len(covered) / len(corpus_sources), 3) if corpus_sources else 0.0,
        "missing_sources": missing,
        "unknown_sources": unknown,
    }


def _fingerprint(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()[:16]


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        return None
    return [v.strip() for v in value if v.strip()]


def _normalize_question(question: str) -> str:
    return " ".join(_WORD.findall(question.lower()))


def _issue(
    sink: list[dict[str, Any]],
    code: str,
    message: str,
    *,
    line: int | None = None,
    id: str | None = None,  # noqa: A002 - JSON report field name
) -> None:
    issue: dict[str, Any] = {"code": code, "message": message}
    if line is not None:
        issue["line"] = line
    if id:
        issue["id"] = id
    sink.append(issue)


def _issue_lines(label: str, issues: list[dict[str, Any]]) -> list[str]:
    if not issues:
        return [f"  {label}: none"]
    lines = [f"  {label}:"]
    for issue in issues[:10]:
        loc = []
        if issue.get("line") is not None:
            loc.append(f"line {issue['line']}")
        if issue.get("id"):
            loc.append(str(issue["id"]))
        prefix = f" ({', '.join(loc)})" if loc else ""
        lines.append(f"    - {issue['code']}{prefix}: {issue['message']}")
    if len(issues) > 10:
        lines.append(f"    - ... {len(issues) - 10} more")
    return lines
