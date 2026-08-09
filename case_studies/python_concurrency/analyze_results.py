"""Build deterministic summary metrics for the Python concurrency case study."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from proofrag import __version__ as proofrag_version
from proofrag.compare import CMP_SYS, CMP_TMPL
from proofrag.corpus import corpus_stats, load_corpus
from proofrag.goldenset import _MULTI, _SINGLE, _UNANS  # noqa: PLC2701
from proofrag.goldenset import SYS as GOLD_SYS
from proofrag.judge import JUDGE_DIMENSIONS, JUDGE_SYS, JUDGE_TMPL
from proofrag.metrics import RETRIEVAL_METRICS, retrieval_metrics

from .rag import SYSTEM, build_fts, rank_fts, rank_overlap

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
GOLD_PATH = HERE / "goldenset.jsonl"
GENERATED_PATH = HERE / "goldenset.generated.jsonl"
REFUSAL = "I don't have enough information in the provided context to answer that."

VARIANTS = {
    "overlap": (
        ARTIFACTS / "predictions-overlap.jsonl",
        ARTIFACTS / "results-overlap.json",
    ),
    "fts5": (
        ARTIFACTS / "predictions-fts5.jsonl",
        ARTIFACTS / "results-fts5.json",
    ),
    "fts5_reversed": (
        ARTIFACTS / "predictions-fts5-reversed.jsonl",
        ARTIFACTS / "results-fts5-reversed.json",
    ),
}

OBSERVED_WALL_SECONDS = {
    "goldenset_generate": 52.86,
    "answer_overlap": 52.49,
    "answer_fts5": 48.56,
    "answer_fts5_reversed": 51.61,
    "evaluate_overlap": 48.26,
    "evaluate_fts5": 52.58,
    "evaluate_fts5_reversed": 45.87,
    "compare": 42.95,
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def _generation_score(record: dict[str, Any]) -> float:
    return statistics.fmean(record["scores"][key] for key in JUDGE_DIMENSIONS)


def _group_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, Any] = {}
    for difficulty in ("single_doc", "multi_doc", "unanswerable"):
        rows = [record for record in records if record["difficulty"] == difficulty]
        generation = {key: _mean([row["scores"][key] for row in rows]) for key in JUDGE_DIMENSIONS}
        generation["overall"] = _mean([score for row in rows for score in row["scores"].values()])
        retrieval_rows = [row["retrieval"] for row in rows if row["retrieval"]]
        retrieval = (
            {key: _mean([row[key] for row in retrieval_rows]) for key in RETRIEVAL_METRICS}
            if retrieval_rows
            else None
        )
        grouped[difficulty] = {
            "n": len(rows),
            "generation": generation,
            "retrieval": retrieval,
        }
    return grouped


def _variant_summary(predictions: list[dict[str, Any]], results: dict[str, Any]) -> dict[str, Any]:
    records = results["records"]
    answerable = [record for record in records if record["retrieval"]]
    multi_doc = [record for record in answerable if record["difficulty"] == "multi_doc"]
    unanswerable_ids = {
        record["id"] for record in records if record["difficulty"] == "unanswerable"
    }
    prediction_map = {prediction["id"]: prediction for prediction in predictions}
    joined_lengths = [
        len("\n\n---\n\n".join(prediction["retrieved_contexts"])) for prediction in predictions
    ]
    weak = sorted(records, key=lambda row: (_generation_score(row), row["id"]))[:5]
    quadrants = {
        "retrieval_linked": [],
        "generation_side": [],
        "suspicious_or_prior_knowledge": [],
    }
    for row in answerable:
        recall = row["retrieval"]["recall_at_k"]
        generation = _generation_score(row)
        if recall < 1 and generation < 0.65:
            quadrants["retrieval_linked"].append(row["id"])
        elif recall == 1 and generation < 0.65:
            quadrants["generation_side"].append(row["id"])
        elif recall < 1 and generation >= 0.65:
            quadrants["suspicious_or_prior_knowledge"].append(row["id"])

    return {
        "aggregate": results["aggregate"],
        "overall_generation": _mean([_generation_score(row) for row in records]),
        "by_difficulty": _group_metrics(records),
        "retrieval_rates": {
            "denominator": len(answerable),
            "any_hit": sum(row["retrieval"]["mrr"] > 0 for row in answerable),
            "full_context_hit": sum(row["retrieval"]["recall_at_k"] == 1 for row in answerable),
            "zero_hit": sum(row["retrieval"]["recall_at_k"] == 0 for row in answerable),
            "multi_doc_full_evidence": sum(
                row["retrieval"]["recall_at_k"] == 1 for row in multi_doc
            ),
            "multi_doc_denominator": len(multi_doc),
        },
        "safe_refusals": {
            "count": sum(
                prediction_map[record_id]["answer"].startswith(REFUSAL)
                for record_id in unanswerable_ids
            ),
            "denominator": len(unanswerable_ids),
        },
        "prediction_integrity": {
            "n": len(predictions),
            "unique_ids": len(prediction_map),
            "min_contexts": min(len(row["retrieved_contexts"]) for row in predictions),
            "max_contexts": max(len(row["retrieved_contexts"]) for row in predictions),
            "max_joined_context_chars": max(joined_lengths),
            "joined_contexts_over_4000": sum(length > 4000 for length in joined_lengths),
            "empty_answers": sum(not row["answer"] for row in predictions),
        },
        "judge_errors": sum(row["rationale"].startswith("judge error:") for row in records),
        "weakest_cases": [
            {
                "id": row["id"],
                "difficulty": row["difficulty"],
                "generation": round(_generation_score(row), 3),
                "recall_at_5": (row["retrieval"]["recall_at_k"] if row["retrieval"] else None),
                "rationale": row["rationale"],
            }
            for row in weak
        ],
        "recall_below_one": [
            row["id"] for row in answerable if row["retrieval"]["recall_at_k"] < 1
        ],
        "diagnostic_quadrants": quadrants,
    }


def _pairwise_summary(comparison: dict[str, Any], gold: list[dict[str, Any]]) -> dict[str, Any]:
    difficulty = {record["id"]: record["difficulty"] for record in gold}
    by_difficulty: dict[str, Any] = {}
    for tier in ("single_doc", "multi_doc", "unanswerable"):
        rows = [row for row in comparison["records"] if difficulty[row["id"]] == tier]
        wins = Counter(row["winner"] for row in rows)
        decided = wins["a"] + wins["b"]
        by_difficulty[tier] = {
            "n": len(rows),
            "fts5": wins["a"],
            "overlap": wins["b"],
            "tie": wins["tie"],
            "fts5_decided_win_rate": round(wins["a"] / decided, 3) if decided else None,
        }
    wins = comparison["wins"]
    decided = wins["a"] + wins["b"]
    return {
        "n": comparison["n"],
        "wins": {"fts5": wins["a"], "overlap": wins["b"], "tie": wins["tie"]},
        "fts5_decided_win_rate": round(wins["a"] / decided, 3),
        "fts5_all_case_win_share": round(wins["a"] / comparison["n"], 3),
        "tie_rate": round(wins["tie"] / comparison["n"], 3),
        "by_difficulty": by_difficulty,
        "judge_errors": sum(
            row["reason"].startswith("judge error:") for row in comparison["records"]
        ),
    }


def _exact_match_sensitivity(
    gold: list[dict[str, Any]], predictions: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Post-hoc check: require exact chunk text instead of fuzzy Jaccard relevance."""
    answerable = [record for record in gold if record["gold_contexts"]]
    summary: dict[str, Any] = {}
    for name, rows in predictions.items():
        prediction_map = {row["id"]: row for row in rows}
        scored = [
            (
                record,
                retrieval_metrics(
                    record["gold_contexts"],
                    prediction_map[record["id"]]["retrieved_contexts"],
                    5,
                    lambda expected, actual: expected == actual,
                ),
            )
            for record in answerable
        ]
        by_difficulty = {}
        for difficulty in ("single_doc", "multi_doc"):
            tier = [metrics for record, metrics in scored if record["difficulty"] == difficulty]
            by_difficulty[difficulty] = {
                key: _mean([row[key] for row in tier]) for key in RETRIEVAL_METRICS
            }
        summary[name] = {
            "aggregate": {
                key: _mean([metrics[key] for _, metrics in scored]) for key in RETRIEVAL_METRICS
            },
            "by_difficulty": by_difficulty,
            "rates": {
                "denominator": len(scored),
                "any_hit": sum(metrics["mrr"] > 0 for _, metrics in scored),
                "full_context_hit": sum(metrics["recall_at_k"] == 1 for _, metrics in scored),
                "zero_hit": sum(metrics["recall_at_k"] == 0 for _, metrics in scored),
            },
            "recall_below_one": [
                record["id"] for record, metrics in scored if metrics["recall_at_k"] < 1
            ],
        }
    return summary


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _retriever_benchmark(gold: list[dict[str, Any]]) -> dict[str, Any]:
    chunks = load_corpus(str(HERE / "corpus"), max_chars=700)
    questions = [record["question"] for record in gold]
    build_times: list[float] = []
    for _ in range(15):
        started = time.perf_counter_ns()
        connection = build_fts(chunks)
        build_times.append((time.perf_counter_ns() - started) / 1_000_000)
        connection.close()

    connection = build_fts(chunks)
    timings: dict[str, list[float]] = {"overlap": [], "fts5": []}
    for _ in range(30):
        for question in questions:
            started = time.perf_counter_ns()
            rank_overlap(chunks, question)
            timings["overlap"].append((time.perf_counter_ns() - started) / 1_000_000)
            started = time.perf_counter_ns()
            rank_fts(connection, question)
            timings["fts5"].append((time.perf_counter_ns() - started) / 1_000_000)
    connection.close()
    return {
        "scope": "retrieval only; warm in-memory index; 900 queries per variant",
        "fts5_index_build_ms": {
            "median": round(statistics.median(build_times), 3),
            "p95": round(_percentile(build_times, 0.95), 3),
        },
        "query_latency_ms": {
            name: {
                "median": round(statistics.median(values), 3),
                "p95": round(_percentile(values, 0.95), 3),
            }
            for name, values in timings.items()
        },
    }


def _usage_character_proxy(
    gold: list[dict[str, Any]],
    generated: list[dict[str, Any]],
    predictions: dict[str, list[dict[str, Any]]],
    results: dict[str, dict[str, Any]],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    corpus_chunks = load_corpus(str(HERE / "corpus"), max_chars=700)
    source_by_text = {chunk["text"]: Path(chunk["source"]).name for chunk in corpus_chunks}
    gold_by_id = {record["id"]: record for record in gold}
    phases: dict[str, dict[str, int]] = {}

    pool = corpus_chunks[:]
    random.Random(21661).shuffle(pool)
    generation_prompts: list[str] = []
    for index in range(21):
        chunk = pool[index]
        source = f"case_studies/python_concurrency/corpus/{Path(chunk['source']).name}"
        generation_prompts.append(_SINGLE.format(source=source, text=chunk["text"][:1500]))
    cursor = 21
    for _ in range(6):
        first, second = pool[cursor], pool[cursor + 1]
        cursor += 2
        generation_prompts.append(
            _MULTI.format(
                src_a=(f"case_studies/python_concurrency/corpus/{Path(first['source']).name}"),
                text_a=first["text"][:900],
                src_b=(f"case_studies/python_concurrency/corpus/{Path(second['source']).name}"),
                text_b=second["text"][:900],
            )
        )
    for chunk in pool[cursor : cursor + 3]:
        generation_prompts.append(_UNANS.format(text=chunk["text"][:1500]))
    generation_outputs = [
        json.dumps(
            {
                "question": record["question"],
                **(
                    {"gold_answer": record["gold_answer"]}
                    if record["difficulty"] != "unanswerable"
                    else {}
                ),
            }
        )
        for record in generated
    ]
    phases["goldenset_generate"] = {
        "calls": 30,
        "input_chars": sum(len(GOLD_SYS) + len(prompt) for prompt in generation_prompts),
        "output_chars": sum(map(len, generation_outputs)),
    }

    for name, rows in predictions.items():
        answer_inputs = 0
        answer_outputs = 0
        for prediction in rows:
            excerpts = "\n\n---\n\n".join(
                f"Source: {source_by_text[context]}\n{context}"
                for context in prediction["retrieved_contexts"]
            )
            prompt = (
                f"Documentation excerpts:\n{excerpts}\n\n"
                f"Question: {gold_by_id[prediction['id']]['question']}\nAnswer concisely."
            )
            answer_inputs += len(SYSTEM) + len(prompt)
            answer_outputs += len(prediction["answer"])
        phases[f"answer_{name}"] = {
            "calls": len(rows),
            "input_chars": answer_inputs,
            "output_chars": answer_outputs,
        }

        result_rows = {row["id"]: row for row in results[name]["records"]}
        judge_inputs = 0
        judge_outputs = 0
        for prediction in rows:
            record = gold_by_id[prediction["id"]]
            context = "\n\n---\n\n".join(prediction["retrieved_contexts"])
            prompt = JUDGE_TMPL.format(
                q=record["question"],
                gold=record["gold_answer"],
                ctx=context[:4000],
                ans=prediction["answer"] or "(no answer)",
            )
            judged = result_rows[prediction["id"]]
            output = json.dumps(judged["scores"] | {"rationale": judged["rationale"]})
            judge_inputs += len(JUDGE_SYS) + len(prompt)
            judge_outputs += len(output)
        phases[f"evaluate_{name}"] = {
            "calls": len(rows),
            "input_chars": judge_inputs,
            "output_chars": judge_outputs,
        }

    compare_inputs = 0
    compare_outputs = 0
    for row in comparison["records"]:
        record = gold_by_id[row["id"]]
        prompt = CMP_TMPL.format(
            q=record["question"],
            gold=record["gold_answer"],
            r1=row["a_answer"],
            r2=row["b_answer"],
        )
        compare_inputs += len(CMP_SYS) + len(prompt)
        compare_outputs += len(json.dumps({"winner": row["winner"], "reason": row["reason"]}))
    phases["compare"] = {
        "calls": comparison["n"],
        "input_chars": compare_inputs,
        "output_chars": compare_outputs,
    }

    for phase in phases.values():
        phase["approx_input_tokens_chars_div_4"] = math.ceil(phase["input_chars"] / 4)
        phase["approx_output_tokens_chars_div_4"] = math.ceil(phase["output_chars"] / 4)
    return {
        "method": (
            "Proxy only: persisted system/prompt/output characters divided by four; "
            "excludes provider framing and may differ materially from billed tokens."
        ),
        "phases": phases,
        "total_known_calls": sum(phase["calls"] for phase in phases.values()),
        "total_approx_input_tokens": sum(
            phase["approx_input_tokens_chars_div_4"] for phase in phases.values()
        ),
        "total_approx_output_tokens": sum(
            phase["approx_output_tokens_chars_div_4"] for phase in phases.values()
        ),
    }


def main() -> None:
    if proofrag_version != "0.7.0":
        raise SystemExit(
            "published analysis requires proofrag 0.7.0; use the pinned command in REPORT.md"
        )
    gold = _read_jsonl(GOLD_PATH)
    generated = _read_jsonl(GENERATED_PATH)
    predictions = {name: _read_jsonl(paths[0]) for name, paths in VARIANTS.items()}
    results = {name: json.loads(paths[1].read_text()) for name, paths in VARIANTS.items()}
    comparison = json.loads((ARTIFACTS / "comparison.json").read_text())
    chunks = load_corpus(str(HERE / "corpus"), max_chars=700)
    manifest = json.loads((HERE / "sources.json").read_text())
    validation = json.loads((ARTIFACTS / "validation.json").read_text())

    gold_ids = [record["id"] for record in gold]
    assert all([row["id"] for row in value] == gold_ids for value in predictions.values())
    assert all(result["n"] == len(gold) for result in results.values())
    assert comparison["n"] == len(gold)
    assert len({result["judge_fingerprint"] for result in results.values()}) == 1
    assert comparison["judge_fingerprint"] == results["fts5"]["judge_fingerprint"]
    assert all(result["k"] == 5 for result in results.values())

    source_counts = Counter(
        Path(source).name for record in gold for source in record.get("sources", [])
    )
    total_wall = round(sum(OBSERVED_WALL_SECONDS.values()), 2)
    summary = {
        "study": "Python concurrency documentation: token overlap vs SQLite FTS5/BM25",
        "created_utc": results["fts5"]["created"],
        "integrity": {
            "goldenset_n": len(gold),
            "goldenset_sha256": _sha256(GOLD_PATH),
            "validation_fingerprint": validation["fingerprint"],
            "validation_errors": validation["errors"],
            "validation_warnings": validation["warnings"],
            "difficulty_counts": Counter(record["difficulty"] for record in gold),
            "source_coverage": f"{len(source_counts)}/{len(manifest['files'])}",
            "source_question_appearances": dict(sorted(source_counts.items())),
            "prediction_id_coverage": "30/30 for every variant",
            "result_id_coverage": "30/30 for every variant",
        },
        "corpus": corpus_stats(chunks)
        | {
            "max_chunk_chars": max(chunk["char_count"] for chunk in chunks),
            "release": manifest["release"],
            "upstream_commit": manifest["commit"],
            "download_bytes": sum(file["bytes"] for file in manifest["files"]),
        },
        "variants": {name: _variant_summary(predictions[name], results[name]) for name in VARIANTS},
        "posthoc_exact_match_sensitivity": _exact_match_sensitivity(gold, predictions),
        "pairwise": _pairwise_summary(comparison, gold),
        "retriever_microbenchmark": _retriever_benchmark(gold),
        "runtime": {
            "observed_wall_seconds_by_phase": OBSERVED_WALL_SECONDS,
            "main_workflow_total_seconds": total_wall,
            "seconds_per_case_across_all_main_phases": round(total_wall / len(gold), 2),
            "notes": (
                "Excludes a 5-case pilot (9.84 s) and one interrupted generation "
                "attempt whose completed-call count and duration were not captured."
            ),
        },
        "usage_proxy": _usage_character_proxy(gold, generated, predictions, results, comparison),
        "reproducibility": {
            "model": results["fts5"]["judge_fingerprint"],
            "backend": results["fts5"]["backend"],
            "k": 5,
            "chunk_chars": 700,
            "lexical_matcher_jaccard_threshold": 0.4,
            "goldenset_sampling_seed": 21661,
            "comparison_position_seed": 0,
            "python": platform.python_version(),
            "sqlite": __import__("sqlite3").sqlite_version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "answer_system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
            "judge_system_prompt_sha256": hashlib.sha256(JUDGE_SYS.encode()).hexdigest(),
        },
    }
    (ARTIFACTS / "analysis.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
