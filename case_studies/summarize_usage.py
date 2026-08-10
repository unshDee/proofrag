"""Summarize opt-in provider token logs for reproducible case-study cost tables."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

PRICING_DATE = "2026-08-10"
PRICING_SOURCES = {
    "anthropic": "https://claude.com/pricing",
    "openai": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
}
RATES_PER_MILLION = {
    ("anthropic", "claude-haiku-4-5-20251001"): {
        "input": 1.0,
        "output": 5.0,
        "cache_creation": 1.25,
        "cache_read": 0.10,
    },
    ("openai", "gpt-4o-mini-2024-07-18"): {
        "input": 0.15,
        "output": 0.60,
        "cache_creation": 0.0,
        "cache_read": 0.075,
    },
}


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"usage log is empty or malformed: {path}")
    return rows


def _cost(row: dict[str, Any]) -> float:
    provider = str(row["provider"])
    model = str(row["model"])
    try:
        rates = RATES_PER_MILLION[(provider, model)]
    except KeyError as error:
        raise ValueError(f"no pricing snapshot for {provider}:{model}") from error
    input_tokens = int(row.get("input_tokens", 0))
    output_tokens = int(row.get("output_tokens", 0))
    cache_creation = int(row.get("cache_creation_input_tokens", 0))
    cache_read = int(row.get("cache_read_input_tokens", 0))
    if min(input_tokens, output_tokens, cache_creation, cache_read) < 0:
        raise ValueError("usage token counts must not be negative")
    billable_input = input_tokens - cache_read if provider == "openai" else input_tokens
    if billable_input < 0:
        raise ValueError("cached input tokens exceed total input tokens")
    return (
        billable_input * rates["input"]
        + output_tokens * rates["output"]
        + cache_creation * rates["cache_creation"]
        + cache_read * rates["cache_read"]
    ) / 1_000_000


def summarize(artifact_dir: Path) -> dict[str, Any]:
    logs = sorted(artifact_dir.glob("usage-*.jsonl"))
    if not logs:
        raise ValueError(f"no usage-*.jsonl files under {artifact_dir}")
    phases: dict[str, Any] = {}
    provider_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "estimated_usd": 0.0,
        }
    )
    for path in logs:
        rows = _read_rows(path)
        providers = {str(row.get("provider", "")) for row in rows}
        models = {str(row.get("model", "")) for row in rows}
        if len(providers) != 1 or len(models) != 1:
            raise ValueError(f"usage phase mixes providers or models: {path}")
        provider = providers.pop()
        model = models.pop()
        phase = path.stem.removeprefix("usage-")
        entry = {
            "provider": provider,
            "model": model,
            "response_models": sorted({str(row.get("response_model", "")) for row in rows}),
            "system_fingerprints": sorted(
                {str(row.get("system_fingerprint", "")) for row in rows} - {""}
            ),
            "calls": len(rows),
            "input_tokens": sum(int(row.get("input_tokens", 0)) for row in rows),
            "output_tokens": sum(int(row.get("output_tokens", 0)) for row in rows),
            "cache_creation_input_tokens": sum(
                int(row.get("cache_creation_input_tokens", 0)) for row in rows
            ),
            "cache_read_input_tokens": sum(
                int(row.get("cache_read_input_tokens", 0)) for row in rows
            ),
            "estimated_usd": round(sum(_cost(row) for row in rows), 6),
        }
        phases[phase] = entry
        totals = provider_totals[provider]
        for key in (
            "calls",
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            totals[key] += entry[key]
        totals["estimated_usd"] += entry["estimated_usd"]

    for totals in provider_totals.values():
        totals["estimated_usd"] = round(totals["estimated_usd"], 6)
    return {
        "schema_version": 1,
        "pricing_snapshot": {
            "date": PRICING_DATE,
            "currency": "USD",
            "sources": PRICING_SOURCES,
            "rates_per_million_tokens": {
                f"{provider}:{model}": rates
                for (provider, model), rates in RATES_PER_MILLION.items()
            },
        },
        "phases": phases,
        "providers": dict(provider_totals),
        "totals": {
            "calls": sum(entry["calls"] for entry in phases.values()),
            "input_tokens": sum(entry["input_tokens"] for entry in phases.values()),
            "output_tokens": sum(entry["output_tokens"] for entry in phases.values()),
            "estimated_usd": round(sum(entry["estimated_usd"] for entry in phases.values()), 6),
        },
        "cost_note": (
            "Estimate from provider-reported tokens and public list prices on the snapshot "
            "date; provider billing consoles remain authoritative."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or args.artifact_dir / "usage.json"
    output.write_text(json.dumps(summarize(args.artifact_dir), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote usage summary -> {output}", flush=True)


if __name__ == "__main__":
    main()
