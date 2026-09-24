#!/usr/bin/env python3
"""Deterministically evaluate explicit expert post-T outcome contracts."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spikes.wiki_trade_replay import (
    _apply_normalization_transform,
    _validate_normalization_transform,
)


SCHEMA_VERSION = "1.0"
DIRECTIONS = {"long", "short"}
EVENT_NAMES = ("trigger", "invalidation", "target")
EVENT_KINDS = {"numeric", "qualitative", "unavailable", "reference", "not_stated"}
UNAVAILABLE_REASONS = {
    "benchmark_unavailable",
    "point_and_figure_unavailable",
    "required_input_unavailable",
}
REFERENCES = {"prior_low", "prior_high", "benchmark_level", "pnf_objective"}
LEVEL_SCALES = {"raw", "input_as_provided", "not_applicable"}
CONTRACT_KEYS = {
    "schema_version", "case_id", "direction", "trigger", "invalidation",
    "target", "horizons", "numeric_level_scale",
}
TRANSFORM_KEYS = {
    "price_scale", "price_reference", "price_multiplier", "round_decimals",
    "volume_scale", "volume_reference", "volume_multiplier", "timeframe",
    "bar_duration_ms", "source_sha256", "package_sha256",
}
CANDLE_KEYS = {
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base_volume",
    "taker_buy_quote_volume",
}


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _rounded(value: float) -> float:
    return round(value, 10)


def _base_result(contract: Any) -> dict[str, Any]:
    case_id = contract.get("case_id") if isinstance(contract, dict) else None
    direction = contract.get("direction") if isinstance(contract, dict) else None
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluator": "wiki_expert_outcome_v1",
        "status": "invalid",
        "case_id": case_id,
        "direction": direction,
        "numeric_level_scale": None,
        "validation_errors": [],
        "normalization": {
            "normalization_applied": False,
            "price_scale": "input_as_provided",
            "normalization_transform_sha256": None,
        },
        "scorable_fields": {
            "trigger": False,
            "invalidation": False,
            "target": False,
            "event_ordering": False,
        },
        "events": {},
        "event_ordering": {
            "status": "not_evaluated",
            "activation_bar": None,
            "outcome": None,
            "outcome_bar": None,
            "sequence": [],
            "ambiguities": [],
        },
        "directional_observation": {
            "trade_executed": False,
            "baseline": None,
            "returns_by_horizon": {},
            "full_horizon": None,
        },
        "limitations": [],
    }


def _validate_event(name: str, event: Any) -> list[str]:
    prefix = f"contract.{name}"
    if not isinstance(event, dict):
        return [f"{prefix} must be an object"]
    kind = event.get("kind")
    if kind not in EVENT_KINDS:
        return [f"{prefix}.kind must be one of {sorted(EVENT_KINDS)}"]
    allowed = {"kind"}
    errors: list[str] = []
    if kind == "numeric":
        allowed |= {"level", "description"}
        if not _number(event.get("level")):
            errors.append(f"{prefix}.level must be a finite number for numeric events")
    elif kind == "qualitative":
        allowed.add("description")
        if not isinstance(event.get("description"), str) or not event["description"].strip():
            errors.append(f"{prefix}.description must be a non-empty string")
    elif kind == "unavailable":
        allowed |= {"reason", "description"}
        if event.get("reason") not in UNAVAILABLE_REASONS:
            errors.append(f"{prefix}.reason must be one of {sorted(UNAVAILABLE_REASONS)}")
    elif kind == "reference":
        allowed |= {"reference", "description"}
        if event.get("reference") not in REFERENCES:
            errors.append(f"{prefix}.reference must be one of {sorted(REFERENCES)}")
    extra = set(event) - allowed
    if extra:
        errors.append(f"{prefix} has unsupported fields: {sorted(extra)}")
    description = event.get("description")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        errors.append(f"{prefix}.description must be a non-empty string when present")
    return errors


def _validate_contract(contract: Any) -> list[str]:
    if not isinstance(contract, dict):
        return ["contract must be an object"]
    errors: list[str] = []
    missing = CONTRACT_KEYS - set(contract)
    extra = set(contract) - CONTRACT_KEYS
    if missing:
        errors.append(f"contract missing required fields: {sorted(missing)}")
    if extra:
        errors.append(f"contract has unsupported fields: {sorted(extra)}")
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"contract.schema_version must be {SCHEMA_VERSION}")
    if not isinstance(contract.get("case_id"), str) or not contract.get("case_id", "").strip():
        errors.append("contract.case_id must be a non-empty string")
    if contract.get("direction") not in DIRECTIONS:
        errors.append(f"contract.direction must be one of {sorted(DIRECTIONS)}")
    for name in EVENT_NAMES:
        errors.extend(_validate_event(name, contract.get(name)))
    horizons = contract.get("horizons")
    if (
        not isinstance(horizons, list)
        or not horizons
        or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in horizons)
        or len(horizons) != len(set(horizons))
        or horizons != sorted(horizons)
    ):
        errors.append("contract.horizons must be a sorted unique array of positive integers")
    scale = contract.get("numeric_level_scale")
    if scale not in LEVEL_SCALES:
        errors.append(f"contract.numeric_level_scale must be one of {sorted(LEVEL_SCALES)}")
    numeric = [
        name for name in EVENT_NAMES
        if isinstance(contract.get(name), dict) and contract[name].get("kind") == "numeric"
    ]
    if numeric and scale == "not_applicable":
        errors.append("numeric_level_scale cannot be not_applicable when numeric events exist")
    if not numeric and scale != "not_applicable":
        errors.append("numeric_level_scale must be not_applicable without numeric events")
    if not errors:
        levels = {
            name: float(contract[name]["level"])
            for name in numeric
        }
        direction = contract["direction"]
        trigger = levels.get("trigger")
        invalidation = levels.get("invalidation")
        target = levels.get("target")
        if trigger is not None and invalidation is not None:
            valid = invalidation < trigger if direction == "long" else invalidation > trigger
            if not valid:
                errors.append("numeric invalidation must be beyond trigger opposite the direction")
        if trigger is not None and target is not None:
            valid = target > trigger if direction == "long" else target < trigger
            if not valid:
                errors.append("numeric target must be beyond trigger in the stated direction")
        if trigger is None and invalidation is not None and target is not None:
            valid = invalidation < target if direction == "long" else target < invalidation
            if not valid:
                errors.append("numeric invalidation and target are inconsistent with direction")
    return errors


def _extract_candles(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) != {"post_t_candles"}:
            return None
        return value["post_t_candles"]
    return value


def _validate_candles(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["post-T OHLCV must be an array or an object containing only post_t_candles"]
    errors: list[str] = []
    for index, candle in enumerate(value, start=1):
        prefix = f"post_t_candles[{index}]"
        if not isinstance(candle, dict):
            errors.append(f"{prefix} must be an object")
            continue
        extra = set(candle) - CANDLE_KEYS
        if extra:
            errors.append(f"{prefix} has unsupported fields: {sorted(extra)}")
        missing = [name for name in ("open", "high", "low", "close") if not _number(candle.get(name))]
        if missing:
            errors.append(f"{prefix} missing finite numeric fields: {', '.join(missing)}")
            continue
        open_, high = float(candle["open"]), float(candle["high"])
        low, close = float(candle["low"]), float(candle["close"])
        if min(open_, high, low, close) <= 0:
            errors.append(f"{prefix} OHLC values must be positive")
        elif high < max(open_, close) or low > min(open_, close) or high < low:
            errors.append(f"{prefix} OHLC values are inconsistent")
        if "volume" in candle and (
            not _number(candle["volume"]) or float(candle["volume"]) < 0
        ):
            errors.append(f"{prefix}.volume must be a finite non-negative number")
    return errors


def _validate_transform_strict(transform: Any) -> tuple[dict[str, Any], list[str]]:
    if isinstance(transform, dict):
        extra = set(transform) - TRANSFORM_KEYS
        if extra:
            return {}, [f"normalization_transform has unsupported fields: {sorted(extra)}"]
    return _validate_normalization_transform(transform)


def _na_reason(event: dict[str, Any]) -> str:
    kind = event["kind"]
    if kind == "qualitative":
        return "qualitative_condition_not_deterministically_replayable"
    if kind == "unavailable":
        return str(event["reason"])
    if kind == "reference":
        return f"reference_without_numeric_level:{event['reference']}"
    return "not_stated"


def _event_touched(name: str, direction: str, level: float, candle: dict[str, Any]) -> bool:
    if name == "trigger":
        return float(candle["high"]) >= level if direction == "long" else float(candle["low"]) <= level
    if name == "invalidation":
        return float(candle["low"]) <= level if direction == "long" else float(candle["high"]) >= level
    return float(candle["high"]) >= level if direction == "long" else float(candle["low"]) <= level


def _event_result(
    name: str, event: dict[str, Any], direction: str,
    candles: list[dict[str, Any]], multiplier: float | None, decimals: int | None,
) -> dict[str, Any]:
    kind = event["kind"]
    base = {
        "kind": kind,
        "description": event.get("description"),
        "source_level": event.get("level"),
        "evaluated_level": None,
        "scorable": kind == "numeric",
        "status": "na",
        "first_touch_bar": None,
        "na_reason": None,
    }
    if kind != "numeric":
        base["na_reason"] = _na_reason(event)
        if kind == "reference":
            base["reference"] = event["reference"]
        return base
    level = float(event["level"])
    if multiplier is not None and decimals is not None:
        level = round(level * multiplier, decimals)
    base["evaluated_level"] = level
    for bar, candle in enumerate(candles, start=1):
        if _event_touched(name, direction, level, candle):
            base["status"] = "touched"
            base["first_touch_bar"] = bar
            return base
    base["status"] = "not_touched"
    return base


def _sequence(events: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_bar: dict[int, list[str]] = {}
    for name in EVENT_NAMES:
        bar = events[name]["first_touch_bar"]
        if bar is not None:
            by_bar.setdefault(int(bar), []).append(name)
    return [
        {"bar": bar, "events": names, "relation": "simultaneous" if len(names) > 1 else "single"}
        for bar, names in sorted(by_bar.items())
    ]


def _ordering(
    direction: str, events: dict[str, dict[str, Any]], candles: list[dict[str, Any]],
) -> dict[str, Any]:
    sequence = _sequence(events)
    ambiguities: list[str] = []
    trigger = events["trigger"]
    outcome = {
        "status": "not_applicable",
        "activation_bar": None,
        "outcome": None,
        "outcome_bar": None,
        "sequence": sequence,
        "ambiguities": ambiguities,
    }
    numeric_outcomes = [name for name in ("invalidation", "target") if events[name]["scorable"]]
    if not trigger["scorable"]:
        outcome["status"] = "direction_only" if not numeric_outcomes else "missing_numeric_trigger"
        return outcome
    trigger_bar = trigger["first_touch_bar"]
    if trigger_bar is None:
        prior_invalid = events["invalidation"]["first_touch_bar"]
        if prior_invalid is not None:
            outcome.update({
                "status": "resolved", "outcome": "invalidated_before_trigger",
                "outcome_bar": prior_invalid,
            })
        else:
            outcome["status"] = "trigger_not_reached"
        return outcome
    outcome["activation_bar"] = trigger_bar
    prior_invalid = events["invalidation"]["first_touch_bar"]
    if prior_invalid is not None and prior_invalid < trigger_bar:
        outcome.update({
            "status": "resolved", "outcome": "invalidated_before_trigger",
            "outcome_bar": prior_invalid,
        })
        return outcome
    same_bar = [
        name for name in numeric_outcomes
        if _event_touched(name, direction, float(events[name]["evaluated_level"]), candles[trigger_bar - 1])
    ]
    if same_bar:
        ambiguity = "trigger_and_" + "_and_".join(same_bar) + "_same_bar_order_unknown"
        ambiguities.append(ambiguity)
        outcome.update({
            "status": "intrabar_ambiguous", "outcome": "order_unknown",
            "outcome_bar": trigger_bar,
        })
        return outcome
    for bar in range(trigger_bar + 1, len(candles) + 1):
        touched = [
            name for name in numeric_outcomes
            if _event_touched(name, direction, float(events[name]["evaluated_level"]), candles[bar - 1])
        ]
        if len(touched) == 2:
            ambiguities.append("invalidation_and_target_same_bar_order_unknown")
            outcome.update({
                "status": "intrabar_ambiguous", "outcome": "order_unknown",
                "outcome_bar": bar,
            })
            return outcome
        if touched:
            name = touched[0]
            outcome.update({
                "status": "resolved",
                "outcome": "target_reached_after_trigger" if name == "target" else "invalidated_after_trigger",
                "outcome_bar": bar,
            })
            return outcome
    outcome["status"] = "activated_unresolved"
    return outcome


def _horizon_metrics(
    candles: list[dict[str, Any]], direction: str, horizon: int,
) -> dict[str, Any]:
    if not candles or horizon > len(candles):
        return {
            "available": False, "bars": horizon, "market_return_pct": None,
            "directional_return_pct": None, "mfe_pct": None, "mae_pct": None,
            "reason": "insufficient_post_t_bars",
        }
    observed = candles[:horizon]
    baseline = float(candles[0]["open"])
    close = float(observed[-1]["close"])
    market_return = (close - baseline) / baseline * 100
    if direction == "long":
        mfe = (max(float(item["high"]) for item in observed) - baseline) / baseline * 100
        mae = (min(float(item["low"]) for item in observed) - baseline) / baseline * 100
        directional_return = market_return
    else:
        mfe = (baseline - min(float(item["low"]) for item in observed)) / baseline * 100
        mae = (baseline - max(float(item["high"]) for item in observed)) / baseline * 100
        directional_return = -market_return
    return {
        "available": True,
        "bars": horizon,
        "market_return_pct": _rounded(market_return),
        "directional_return_pct": _rounded(directional_return),
        "mfe_pct": _rounded(mfe),
        "mae_pct": _rounded(mae),
        "reason": None,
    }


def evaluate_expert_outcome(
    contract: Any, post_t_ohlcv: Any,
    *, normalization_transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate only the expert conditions that are explicitly machine-scorable."""
    result = _base_result(contract)
    contract_errors = _validate_contract(contract)
    candles = _extract_candles(post_t_ohlcv)
    candle_errors = _validate_candles(candles)
    transform_info, transform_errors = _validate_transform_strict(normalization_transform)
    errors = contract_errors + candle_errors + transform_errors
    if isinstance(contract, dict):
        scale = contract.get("numeric_level_scale")
        result["numeric_level_scale"] = scale
        numeric = any(
            isinstance(contract.get(name), dict) and contract[name].get("kind") == "numeric"
            for name in EVENT_NAMES
        )
        if numeric and scale == "raw" and normalization_transform is None:
            errors.append("raw numeric levels require normalization_transform")
        if scale != "raw" and normalization_transform is not None:
            errors.append("normalization_transform is allowed only for raw numeric levels")
    if transform_info:
        result["normalization"] = transform_info
    if errors:
        result["validation_errors"] = errors
        result["limitations"] = ["invalid input was not evaluated"]
        return result

    assert isinstance(contract, dict)
    assert isinstance(candles, list)
    multiplier: float | None = None
    decimals: int | None = None
    evaluated_candles = candles
    if contract["numeric_level_scale"] == "raw":
        assert normalization_transform is not None
        multiplier = float(normalization_transform["price_multiplier"])
        decimals = int(normalization_transform["round_decimals"])
        evaluated_candles = _apply_normalization_transform(candles, normalization_transform)
    events = {
        name: _event_result(
            name, contract[name], contract["direction"], evaluated_candles,
            multiplier, decimals,
        )
        for name in EVENT_NAMES
    }
    ordering = _ordering(contract["direction"], events, evaluated_candles)
    horizons = {
        str(horizon): _horizon_metrics(evaluated_candles, contract["direction"], horizon)
        for horizon in contract["horizons"]
    }
    baseline = (
        {
            "kind": "first_post_t_open",
            "bar": 1,
            "price": float(evaluated_candles[0]["open"]),
        }
        if evaluated_candles else None
    )
    full_horizon = (
        _horizon_metrics(evaluated_candles, contract["direction"], len(evaluated_candles))
        if evaluated_candles else None
    )
    limitations = [
        "Forward returns and MFE/MAE are descriptive from the first post-T open; no trade execution is claimed.",
        "OHLC bars do not reveal intrabar path; simultaneous threshold touches remain unresolved.",
    ]
    limitations.extend(
        f"{name}: {event['na_reason']}"
        for name, event in events.items() if event["na_reason"] is not None
    )
    if not evaluated_candles:
        limitations.append("No post-T bars were available for event or return evaluation.")
    result.update({
        "status": "evaluated",
        "normalization": transform_info,
        "scorable_fields": {
            "trigger": events["trigger"]["scorable"],
            "invalidation": events["invalidation"]["scorable"],
            "target": events["target"]["scorable"],
            "event_ordering": events["trigger"]["scorable"] and any(
                events[name]["scorable"] for name in ("invalidation", "target")
            ),
        },
        "events": events,
        "event_ordering": ordering,
        "directional_observation": {
            "trade_executed": False,
            "baseline": baseline,
            "returns_by_horizon": horizons,
            "full_horizon": full_horizon,
        },
        "limitations": limitations,
    })
    return result


def _load(path: Path) -> Any:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--post-t-ohlcv", type=Path, required=True)
    parser.add_argument("--normalization-transform", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_expert_outcome(
        _load(args.contract),
        _load(args.post_t_ohlcv),
        normalization_transform=(
            _load(args.normalization_transform) if args.normalization_transform else None
        ),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
