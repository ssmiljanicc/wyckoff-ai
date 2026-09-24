#!/usr/bin/env python3
"""Create a reproducible token, duration, and API-equivalent cost ledger."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


LONG_CONTEXT_THRESHOLD = 272_000
PRICE_SNAPSHOT_DATE = "2026-09-23"
PRICE_SOURCES = {
    "gpt-5.6-luna": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
    "gpt-5.6-sol": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
}
PRICES_USD_PER_MILLION = {
    "gpt-5.6-luna": {
        "short": {"uncached_input": 0.20, "cached_input": 0.02, "output": 1.20},
        "long": {"uncached_input": 0.40, "cached_input": 0.04, "output": 1.80},
    },
    "gpt-5.6-sol": {
        "short": {"uncached_input": 4.00, "cached_input": 0.40, "output": 20.00},
        "long": {"uncached_input": 8.00, "cached_input": 0.80, "output": 30.00},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_attempts(path: Path) -> list[dict[str, Any]]:
    attempts = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            attempts.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on {path}:{line_number}: {exc}") from exc
    return attempts


def label_arm(label: str) -> str | None:
    if label.endswith("__arm_a"):
        return "arm_a"
    if label.endswith("__arm_b"):
        return "arm_b"
    return None


def price_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    usage = attempt.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    if cached_input_tokens > input_tokens:
        raise ValueError(f"Cached input exceeds input for {attempt.get('label')}")

    model = attempt.get("resolved_model") or attempt.get("requested_model")
    if model not in PRICES_USD_PER_MILLION:
        raise ValueError(f"No price snapshot for model {model!r}")
    context_band = "long" if input_tokens > LONG_CONTEXT_THRESHOLD else "short"
    rates = PRICES_USD_PER_MILLION[model][context_band]
    uncached_input_tokens = input_tokens - cached_input_tokens
    cost = (
        uncached_input_tokens * rates["uncached_input"]
        + cached_input_tokens * rates["cached_input"]
        + output_tokens * rates["output"]
    ) / 1_000_000
    return {
        "label": attempt.get("label"),
        "stage": attempt.get("stage"),
        "arm": label_arm(str(attempt.get("label") or "")),
        "attempt": attempt.get("attempt"),
        "accepted": bool(attempt.get("accepted")),
        "model": model,
        "effort": attempt.get("effort"),
        "duration_seconds": float(attempt.get("duration_seconds") or 0),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "output_tokens": output_tokens,
        "context_band": context_band,
        "api_equivalent_cost_usd": round(cost, 9),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups["all_attempts"].append(row)
        groups[f"stage:{row['stage']}"].append(row)
        if row["arm"]:
            groups[f"stage:{row['stage']}:{row['arm']}"].append(row)

    result = {}
    for name, group in sorted(groups.items()):
        result[name] = {
            "call_count": len(group),
            "accepted_call_count": sum(bool(row["accepted"]) for row in group),
            "long_context_call_count": sum(row["context_band"] == "long" for row in group),
            "duration_seconds_sum": round(sum(row["duration_seconds"] for row in group), 3),
            "input_tokens": sum(row["input_tokens"] for row in group),
            "cached_input_tokens": sum(row["cached_input_tokens"] for row in group),
            "uncached_input_tokens": sum(row["uncached_input_tokens"] for row in group),
            "output_tokens": sum(row["output_tokens"] for row in group),
            "api_equivalent_cost_usd": round(
                sum(row["api_equivalent_cost_usd"] for row in group), 9
            ),
        }
    return result


def main() -> None:
    args = parse_args()
    attempts = load_attempts(args.attempt_ledger)
    rows = [price_attempt(attempt) for attempt in attempts]
    payload = {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "price_snapshot_date": PRICE_SNAPSHOT_DATE,
        "currency": "USD",
        "long_context_threshold_input_tokens": LONG_CONTEXT_THRESHOLD,
        "price_sources": PRICE_SOURCES,
        "prices_usd_per_million_tokens": PRICES_USD_PER_MILLION,
        "cost_semantics": (
            "API-equivalent estimate from reported Codex CLI tokens; not an observed CLI charge. "
            "The long-context rate applies to the whole call when input_tokens exceeds 272,000."
        ),
        "per_call": rows,
        "aggregates": aggregate(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
