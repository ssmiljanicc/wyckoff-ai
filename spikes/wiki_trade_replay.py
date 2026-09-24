#!/usr/bin/env python3
"""Deterministic trade replay for frozen wiki-assisted analyst outputs.

The replay consumes only an analyst's pre-cutoff JSON and private post-cutoff
OHLC candles. It never calls a model and never attempts to interpret free-text
conditions. ``stop_loss`` is therefore the numeric cancellation boundary before
entry as well as the protective stop after entry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ACTIONS = {"enter_now", "wait_for_trigger", "no_trade"}
DIRECTIONS = {"long", "short", "none"}
ENTRY_TYPES = {"market", "stop", "limit", "none"}


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _base_result(
    *,
    mode: str,
    fee_bps: float,
    slippage_bps: float,
    bar_duration_seconds: int | None,
    bar_duration_source: str | None,
) -> dict[str, Any]:
    finite_fee = fee_bps if _number(fee_bps) else None
    finite_slippage = slippage_bps if _number(slippage_bps) else None
    round_trip_cost = (
        2 * (fee_bps + slippage_bps) / 100
        if finite_fee is not None and finite_slippage is not None
        else None
    )
    return {
        "schema_version": "1.0",
        "mode": mode,
        "status": "invalid",
        "validation_errors": [],
        "action": None,
        "direction": None,
        "entry_type": None,
        "planned_entry_level": None,
        "stop_loss": None,
        "take_profit": None,
        "max_holding_bars": None,
        "entry_expiry_bars": None,
        "cancellation_condition": None,
        "trigger_bar": None,
        "entry_touch_bar": None,
        "stop_touch_bar": None,
        "cancellation_bar": None,
        "resolution_bar": None,
        "resolution_reason": None,
        "entry_bar": None,
        "entry_price": None,
        "exit_bar": None,
        "exit_price": None,
        "exit_reason": None,
        "duration_bars": None,
        "duration_seconds": None,
        "duration_human": None,
        "bar_duration_seconds": bar_duration_seconds,
        "bar_duration_source": bar_duration_source,
        "normalization_applied": False,
        "price_scale": "input_as_provided",
        "normalization_transform_sha256": None,
        "gross_return_pct": None,
        "net_return_pct": None,
        "gross_return_pct_bounds": None,
        "net_return_pct_bounds": None,
        "initial_risk": None,
        "initial_risk_pct": None,
        "gross_r": None,
        "net_r": None,
        "gross_r_bounds": None,
        "net_r_bounds": None,
        "mfe_pct": None,
        "mae_pct": None,
        "mfe_pct_bounds": None,
        "mae_pct_bounds": None,
        "mfe_r": None,
        "mae_r": None,
        "mfe_r_bounds": None,
        "mae_r_bounds": None,
        "fee_bps_per_side": finite_fee,
        "slippage_bps_per_side": finite_slippage,
        "round_trip_cost_pct": round_trip_cost,
        "same_bar_ambiguity": False,
        "exit_bar_excursion_ambiguity": False,
        "ambiguities": [],
        "excursion_policy": "full_bar_extrema_inclusive",
        "pnl_scorable": False,
    }


def _validate_costs(fee_bps: Any, slippage_bps: Any) -> list[str]:
    errors = []
    for name, value in (("fee_bps", fee_bps), ("slippage_bps", slippage_bps)):
        if not _number(value) or value < 0:
            errors.append(f"{name} must be a finite non-negative number")
    return errors


def _validate_candles(candles: Any, *, require_open_close: bool) -> list[str]:
    if not isinstance(candles, list) or not candles:
        return ["answer_key.post_t_candles must be a non-empty array"]
    errors: list[str] = []
    required = (
        ("open", "high", "low", "close") if require_open_close else ("high", "low")
    )
    for index, candle in enumerate(candles, start=1):
        if not isinstance(candle, dict):
            errors.append(f"post_t_candles[{index}] must be an object")
            continue
        missing = [field for field in required if not _number(candle.get(field))]
        if missing:
            errors.append(
                f"post_t_candles[{index}] missing finite numeric fields: {', '.join(missing)}"
            )
            continue
        high, low = float(candle["high"]), float(candle["low"])
        if high < low:
            errors.append(f"post_t_candles[{index}] high must be >= low")
        if require_open_close:
            open_, close = float(candle["open"]), float(candle["close"])
            if high < max(open_, close) or low > min(open_, close):
                errors.append(f"post_t_candles[{index}] OHLC values are inconsistent")
    return errors


def _extract_candles(answer_key: Any) -> Any:
    """Accept a full answer-key object or a deliberately minimal private list."""
    if isinstance(answer_key, dict):
        return answer_key.get("post_t_candles")
    return answer_key


def _extract_normalization_transform(answer_key: Any, explicit_transform: Any) -> Any:
    if explicit_transform is not None:
        return explicit_transform
    if isinstance(answer_key, dict):
        return answer_key.get("normalization_transform")
    return None


def _validate_normalization_transform(
    transform: Any,
) -> tuple[dict[str, Any], list[str]]:
    if transform is None:
        return {
            "normalization_applied": False,
            "price_scale": "input_as_provided",
            "normalization_transform_sha256": None,
        }, []
    if not isinstance(transform, dict):
        return {}, ["normalization_transform must be an object"]
    errors: list[str] = []
    if transform.get("price_scale") != "first_close_100":
        errors.append("normalization_transform.price_scale must be first_close_100")
    reference = transform.get("price_reference")
    multiplier = transform.get("price_multiplier")
    decimals = transform.get("round_decimals")
    if not _number(reference) or reference <= 0:
        errors.append(
            "normalization_transform.price_reference must be positive and finite"
        )
    if not _number(multiplier) or multiplier <= 0:
        errors.append(
            "normalization_transform.price_multiplier must be positive and finite"
        )
    if (
        _number(reference)
        and reference > 0
        and _number(multiplier)
        and multiplier > 0
        and not math.isclose(multiplier, 100 / reference, rel_tol=1e-9, abs_tol=1e-12)
    ):
        errors.append(
            "normalization_transform.price_multiplier must equal 100/price_reference"
        )
    if (
        not isinstance(decimals, int)
        or isinstance(decimals, bool)
        or not 0 <= decimals <= 15
    ):
        errors.append(
            "normalization_transform.round_decimals must be an integer from 0 to 15"
        )

    volume_scale = transform.get("volume_scale")
    if volume_scale is not None:
        if volume_scale != "pre_t_median_volume_100":
            errors.append(
                "normalization_transform.volume_scale must be pre_t_median_volume_100"
            )
        volume_reference = transform.get("volume_reference")
        volume_multiplier = transform.get("volume_multiplier")
        if not _number(volume_reference) or volume_reference <= 0:
            errors.append(
                "normalization_transform.volume_reference must be positive and finite"
            )
        if not _number(volume_multiplier) or volume_multiplier <= 0:
            errors.append(
                "normalization_transform.volume_multiplier must be positive and finite"
            )
        if (
            _number(volume_reference)
            and volume_reference > 0
            and _number(volume_multiplier)
            and volume_multiplier > 0
            and not math.isclose(
                volume_multiplier,
                100 / volume_reference,
                rel_tol=1e-9,
                abs_tol=1e-12,
            )
        ):
            errors.append(
                "normalization_transform.volume_multiplier must equal 100/volume_reference"
            )
    digest = hashlib.sha256(
        json.dumps(transform, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "normalization_applied": not errors,
        "price_scale": "first_close_100" if not errors else "invalid_transform",
        "normalization_transform_sha256": digest,
    }, errors


def _apply_normalization_transform(
    candles: list[dict[str, Any]], transform: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if transform is None:
        return candles
    price_multiplier = float(transform["price_multiplier"])
    volume_multiplier = transform.get("volume_multiplier")
    decimals = int(transform["round_decimals"])
    normalized: list[dict[str, Any]] = []
    for candle in candles:
        converted = dict(candle)
        for field in ("open", "high", "low", "close"):
            if _number(converted.get(field)):
                converted[field] = round(
                    float(converted[field]) * price_multiplier, decimals
                )
        if _number(converted.get("volume")) and _number(volume_multiplier):
            converted["volume"] = round(
                float(converted["volume"]) * float(volume_multiplier), decimals
            )
        normalized.append(converted)
    return normalized


def _parse_timeframe(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([1-9][0-9]*)([mhdw])", value.strip().lower())
    if not match:
        return None
    quantity = int(match.group(1))
    unit_seconds = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    return quantity * unit_seconds[match.group(2)]


def _resolve_bar_duration(
    answer_key: Any,
    *,
    bar_duration_seconds: Any = None,
    timeframe: Any = None,
    normalization_transform: Any = None,
) -> tuple[int | None, str | None, list[str]]:
    """Resolve explicit metadata without consulting anonymized candle timestamps."""
    candidates = [
        ("call.bar_duration_seconds", bar_duration_seconds, "seconds"),
        ("call.timeframe", timeframe, "timeframe"),
    ]
    if isinstance(answer_key, dict):
        candidates.extend(
            [
                (
                    "answer_key.bar_duration_seconds",
                    answer_key.get("bar_duration_seconds"),
                    "seconds",
                ),
                ("answer_key.timeframe", answer_key.get("timeframe"), "timeframe"),
            ]
        )
    if isinstance(normalization_transform, dict):
        candidates.extend(
            [
                (
                    "normalization_transform.bar_duration_ms",
                    normalization_transform.get("bar_duration_ms"),
                    "milliseconds",
                ),
                (
                    "normalization_transform.timeframe",
                    normalization_transform.get("timeframe"),
                    "timeframe",
                ),
            ]
        )
    for source, value, kind in candidates:
        if value is None:
            continue
        if kind == "seconds":
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return None, source, [f"{source} must be a positive integer"]
            return value, source, []
        if kind == "milliseconds":
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
                or value % 1000 != 0
            ):
                return (
                    None,
                    source,
                    [f"{source} must be a positive whole-second integer"],
                )
            return value // 1000, source, []
        parsed = _parse_timeframe(value)
        if parsed is None:
            return None, source, [f"{source} must match <positive integer><m|h|d|w>"]
        return parsed, source, []
    return None, None, []


def _human_duration(seconds: int) -> str:
    for suffix, unit in (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60)):
        if seconds % unit == 0:
            return f"{seconds // unit}{suffix}"
    return f"{seconds}s"


def _validate_plan(plan: Any) -> list[str]:
    if not isinstance(plan, dict):
        return ["trade_plan must be an object"]
    errors: list[str] = []
    action = plan.get("action")
    direction = plan.get("direction")
    entry_type = plan.get("entry_type")
    if action not in ACTIONS:
        errors.append(f"trade_plan.action must be one of {sorted(ACTIONS)}")
    if direction not in DIRECTIONS:
        errors.append(f"trade_plan.direction must be one of {sorted(DIRECTIONS)}")
    if entry_type not in ENTRY_TYPES:
        errors.append(f"trade_plan.entry_type must be one of {sorted(ENTRY_TYPES)}")
    if (
        not isinstance(plan.get("cancellation_condition"), str)
        or not plan.get("cancellation_condition", "").strip()
    ):
        errors.append("trade_plan.cancellation_condition must be a non-empty string")

    if action == "no_trade":
        if direction != "none":
            errors.append("no_trade requires direction=none")
        if entry_type != "none":
            errors.append("no_trade requires entry_type=none")
        for field in ("entry_level", "stop_loss", "take_profit"):
            if plan.get(field) is not None:
                errors.append(f"no_trade requires {field}=null")
        if plan.get("max_holding_bars") is not None:
            errors.append("no_trade requires max_holding_bars=null")
        if plan.get("entry_expiry_bars") is not None:
            errors.append("no_trade requires entry_expiry_bars=null")
        return errors

    if action in {"enter_now", "wait_for_trigger"}:
        if direction not in {"long", "short"}:
            errors.append("actionable trade requires direction=long or short")
        expected_types = {"market"} if action == "enter_now" else {"stop", "limit"}
        if entry_type not in expected_types:
            errors.append(f"{action} requires entry_type in {sorted(expected_types)}")
        for field in ("entry_level", "stop_loss", "take_profit"):
            value = plan.get(field)
            if not _number(value) or value <= 0:
                errors.append(f"actionable trade requires positive finite {field}")
        max_bars = plan.get("max_holding_bars")
        if not isinstance(max_bars, int) or isinstance(max_bars, bool) or max_bars <= 0:
            errors.append("actionable trade requires positive integer max_holding_bars")
        expiry = plan.get("entry_expiry_bars")
        if action == "wait_for_trigger" and (
            not isinstance(expiry, int) or isinstance(expiry, bool) or expiry <= 0
        ):
            errors.append(
                "wait_for_trigger requires positive integer entry_expiry_bars"
            )
        if action == "enter_now" and expiry is not None:
            errors.append("enter_now requires entry_expiry_bars=null")
        entry, stop, target = (
            plan.get("entry_level"),
            plan.get("stop_loss"),
            plan.get("take_profit"),
        )
        if all(_number(value) for value in (entry, stop, target)):
            if direction == "long" and not (stop < entry < target):
                errors.append(
                    "long levels must satisfy stop_loss < entry_level < take_profit"
                )
            if direction == "short" and not (target < entry < stop):
                errors.append(
                    "short levels must satisfy take_profit < entry_level < stop_loss"
                )
    return errors


def _touches_cancel(candle: dict[str, Any], direction: str, stop: float) -> bool:
    return (
        float(candle["low"]) <= stop
        if direction == "long"
        else float(candle["high"]) >= stop
    )


def _touches_entry(
    candle: dict[str, Any], direction: str, entry_type: str, entry: float
) -> bool:
    if (direction, entry_type) in {("long", "stop"), ("short", "limit")}:
        return float(candle["high"]) >= entry
    return float(candle["low"]) <= entry


def _touches_target(candle: dict[str, Any], direction: str, target: float) -> bool:
    return (
        float(candle["high"]) >= target
        if direction == "long"
        else float(candle["low"]) <= target
    )


def _zero_pnl(result: dict[str, Any]) -> None:
    for field in ("gross_return_pct", "net_return_pct", "gross_r", "net_r"):
        result[field] = 0.0


def _set_ambiguous_entry_cancel_bounds(
    result: dict[str, Any], *, entry: float, stop: float
) -> None:
    """Bound an OHLC bar that touched both pending entry and cancellation."""
    risk_pct = abs(entry - stop) / entry * 100
    cost_pct = result["round_trip_cost_pct"]
    result.update(
        {
            "gross_return_pct_bounds": {
                "pessimistic": -risk_pct,
                "optimistic": 0.0,
            },
            "net_return_pct_bounds": {
                "pessimistic": -risk_pct - cost_pct,
                "optimistic": 0.0,
            },
            "gross_r_bounds": {"pessimistic": -1.0, "optimistic": 0.0},
            "net_r_bounds": {
                "pessimistic": (-risk_pct - cost_pct) / risk_pct,
                "optimistic": 0.0,
            },
        }
    )


def _finish_pnl(
    result: dict[str, Any],
    candles: list[dict[str, Any]],
    *,
    entry_index: int,
    exit_index: int,
    entry_price: float,
    exit_price: float,
    stop: float,
    direction: str,
    exit_reason: str,
    exclude_entry_favorable_extreme: bool,
) -> None:
    result["entry_bar"] = entry_index + 1
    result["entry_price"] = entry_price
    result["exit_bar"] = exit_index + 1
    result["exit_price"] = exit_price
    result["duration_bars"] = exit_index - entry_index + 1
    if result["bar_duration_seconds"] is not None:
        result["duration_seconds"] = (
            result["duration_bars"] * result["bar_duration_seconds"]
        )
        result["duration_human"] = _human_duration(result["duration_seconds"])
    risk = abs(entry_price - stop)
    risk_pct = risk / entry_price * 100
    gross_pct = ((exit_price - entry_price) / entry_price * 100) * (
        1 if direction == "long" else -1
    )
    net_pct = gross_pct - result["round_trip_cost_pct"]
    window = candles[entry_index : exit_index + 1]

    def observed_extremes(
        bars: list[dict[str, Any]], *, exclude_first_favorable: bool
    ) -> tuple[float, float]:
        mfe, mae = 0.0, 0.0
        for offset, bar in enumerate(bars):
            if direction == "long":
                favorable = (float(bar["high"]) - entry_price) / entry_price * 100
                adverse = (float(bar["low"]) - entry_price) / entry_price * 100
            else:
                favorable = (entry_price - float(bar["low"])) / entry_price * 100
                adverse = (entry_price - float(bar["high"])) / entry_price * 100
            if offset == 0 and exclude_first_favorable:
                favorable = 0.0
            mfe = max(mfe, favorable)
            mae = min(mae, adverse)
        return mfe, mae

    if exit_reason in {"stop_loss", "take_profit"}:
        result["excursion_policy"] = (
            "full_pre_exit_bars; exit_bar_extrema_reported_as_bounds_due_unknown_order"
        )
        prior_mfe, prior_mae = observed_extremes(
            window[:-1], exclude_first_favorable=exclude_entry_favorable_extreme
        )
        exit_mfe, exit_mae = observed_extremes(
            window[-1:], exclude_first_favorable=False
        )
        if exit_reason == "take_profit":
            known_mfe = max(prior_mfe, gross_pct)
            mfe_bounds = {"guaranteed": known_mfe, "possible": max(known_mfe, exit_mfe)}
            mae_bounds = {
                "best_case": prior_mae,
                "worst_case": min(prior_mae, exit_mae),
            }
        else:
            known_mae = min(prior_mae, gross_pct)
            mfe_bounds = {
                "guaranteed": prior_mfe,
                "possible": max(prior_mfe, exit_mfe),
            }
            mae_bounds = {
                "best_case": known_mae,
                "worst_case": min(known_mae, exit_mae),
            }
    else:
        exact_mfe, exact_mae = observed_extremes(
            window, exclude_first_favorable=exclude_entry_favorable_extreme
        )
        mfe_bounds = {"guaranteed": exact_mfe, "possible": exact_mfe}
        mae_bounds = {"best_case": exact_mae, "worst_case": exact_mae}

    mfe_exact = math.isclose(mfe_bounds["guaranteed"], mfe_bounds["possible"])
    mae_exact = math.isclose(mae_bounds["best_case"], mae_bounds["worst_case"])
    mfe_pct = mfe_bounds["guaranteed"] if mfe_exact else None
    mae_pct = mae_bounds["best_case"] if mae_exact else None
    if not (mfe_exact and mae_exact):
        result["exit_bar_excursion_ambiguity"] = True
        result["ambiguities"].append(
            "exit_bar_extreme_order_unknown; MFE_MAE_reported_as_bounds"
        )
    result.update(
        {
            "gross_return_pct": gross_pct,
            "net_return_pct": net_pct,
            "initial_risk": risk,
            "initial_risk_pct": risk_pct,
            "gross_r": gross_pct / risk_pct,
            "net_r": net_pct / risk_pct,
            "mfe_pct": mfe_pct,
            "mae_pct": mae_pct,
            "mfe_pct_bounds": mfe_bounds,
            "mae_pct_bounds": mae_bounds,
            "mfe_r": mfe_pct / risk_pct if mfe_pct is not None else None,
            "mae_r": mae_pct / risk_pct if mae_pct is not None else None,
            "mfe_r_bounds": {
                key: value / risk_pct for key, value in mfe_bounds.items()
            },
            "mae_r_bounds": {
                key: value / risk_pct for key, value in mae_bounds.items()
            },
            "pnl_scorable": True,
        }
    )


def evaluate_trade(
    analysis: dict[str, Any],
    answer_key: Any,
    *,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    bar_duration_seconds: int | None = None,
    timeframe: str | None = None,
    normalization_transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay one analysis without using information beyond its frozen contract."""
    plan = analysis.get("trade_plan") if isinstance(analysis, dict) else None
    if plan is None:
        return evaluate_legacy(
            analysis,
            answer_key,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            bar_duration_seconds=bar_duration_seconds,
            timeframe=timeframe,
            normalization_transform=normalization_transform,
        )

    transform = _extract_normalization_transform(answer_key, normalization_transform)
    normalization_info, normalization_errors = _validate_normalization_transform(
        transform
    )
    resolved_duration, duration_source, duration_errors = _resolve_bar_duration(
        answer_key,
        bar_duration_seconds=bar_duration_seconds,
        timeframe=timeframe,
        normalization_transform=transform,
    )
    result = _base_result(
        mode="trade_plan",
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        bar_duration_seconds=resolved_duration,
        bar_duration_source=duration_source,
    )
    result.update(normalization_info)
    errors = (
        _validate_costs(fee_bps, slippage_bps)
        + _validate_plan(plan)
        + duration_errors
        + normalization_errors
    )
    action = plan.get("action") if isinstance(plan, dict) else None
    result.update(
        {
            "action": action,
            "direction": plan.get("direction") if isinstance(plan, dict) else None,
            "entry_type": plan.get("entry_type") if isinstance(plan, dict) else None,
            "planned_entry_level": plan.get("entry_level")
            if isinstance(plan, dict)
            else None,
            "stop_loss": plan.get("stop_loss") if isinstance(plan, dict) else None,
            "take_profit": plan.get("take_profit") if isinstance(plan, dict) else None,
            "max_holding_bars": plan.get("max_holding_bars")
            if isinstance(plan, dict)
            else None,
            "entry_expiry_bars": plan.get("entry_expiry_bars")
            if isinstance(plan, dict)
            else None,
            "cancellation_condition": plan.get("cancellation_condition")
            if isinstance(plan, dict)
            else None,
        }
    )
    if action == "no_trade":
        result["validation_errors"] = errors
        if errors:
            return result
        result.update(
            {
                "status": "no_trade",
                "resolution_reason": "no_trade",
                "pnl_scorable": True,
            }
        )
        _zero_pnl(result)
        return result

    candles = _extract_candles(answer_key)
    if not normalization_errors and isinstance(candles, list):
        candles = _apply_normalization_transform(candles, transform)
    errors += _validate_candles(candles, require_open_close=True)
    result["validation_errors"] = errors
    if errors:
        return result

    direction = plan["direction"]
    entry_type = plan["entry_type"]
    planned_entry = float(plan["entry_level"])
    stop = float(plan["stop_loss"])
    target = float(plan["take_profit"])
    entry_index: int | None = None
    entry_price: float | None = None

    if action == "enter_now":
        entry_index, entry_price = 0, float(candles[0]["open"])
        if direction == "long" and not (stop < entry_price < target):
            result["validation_errors"].append(
                "actual market fill must lie between long stop and target"
            )
        if direction == "short" and not (target < entry_price < stop):
            result["validation_errors"].append(
                "actual market fill must lie between short target and stop"
            )
        if result["validation_errors"]:
            return result
    else:
        expiry_bars = int(plan["entry_expiry_bars"])
        replay_horizon = min(len(candles), expiry_bars)
        for index, candle in enumerate(candles[:replay_horizon]):
            canceled = _touches_cancel(candle, direction, stop)
            triggered = _touches_entry(candle, direction, entry_type, planned_entry)
            if canceled and triggered:
                result.update(
                    {
                        "status": "intrabar_ambiguous_entry_cancel",
                        "same_bar_ambiguity": True,
                        "entry_touch_bar": index + 1,
                        "stop_touch_bar": index + 1,
                        "resolution_bar": index + 1,
                        "resolution_reason": "entry_and_cancellation_order_unknown",
                    }
                )
                result["ambiguities"].append(
                    "entry_and_cancellation_touched_same_bar; "
                    "path_is_between_no_entry_cancel_and_entry_then_stop"
                )
                _set_ambiguous_entry_cancel_bounds(
                    result, entry=planned_entry, stop=stop
                )
                return result
            if canceled:
                result.update(
                    {
                        "status": "canceled_before_entry",
                        "stop_touch_bar": index + 1,
                        "cancellation_bar": index + 1,
                        "resolution_bar": index + 1,
                        "resolution_reason": "cancellation_before_entry",
                        "pnl_scorable": True,
                    }
                )
                _zero_pnl(result)
                return result
            if triggered:
                entry_index, entry_price = index, planned_entry
                result["entry_touch_bar"] = index + 1
                result["trigger_bar"] = index + 1
                break
        if entry_index is None:
            if len(candles) >= expiry_bars:
                result.update(
                    {
                        "status": "expired_before_entry",
                        "resolution_bar": expiry_bars,
                        "resolution_reason": "entry_expiry_reached",
                        "pnl_scorable": True,
                    }
                )
                _zero_pnl(result)
            else:
                result.update(
                    {
                        "status": "horizon_before_entry_expiry",
                        "resolution_bar": len(candles),
                        "resolution_reason": "insufficient_post_t_horizon_for_entry_expiry",
                    }
                )
            return result

    assert entry_index is not None and entry_price is not None
    result["entry_bar"] = entry_index + 1
    result["entry_price"] = entry_price
    max_holding_index = entry_index + int(plan["max_holding_bars"]) - 1
    last_index = min(len(candles) - 1, max_holding_index)
    exit_index: int | None = None
    exit_price: float | None = None
    reason: str | None = None
    target_on_entry_ignored = False
    for index in range(entry_index, last_index + 1):
        candle = candles[index]
        stop_hit = _touches_cancel(candle, direction, stop)
        target_hit = _touches_target(candle, direction, target)
        if (
            action == "wait_for_trigger"
            and index == entry_index
            and target_hit
            and not stop_hit
        ):
            result["same_bar_ambiguity"] = True
            result["ambiguities"].append(
                "target_touched_on_pending_entry_bar; target_not_credited"
            )
            target_on_entry_ignored = True
            target_hit = False
        if stop_hit and target_hit:
            result["same_bar_ambiguity"] = True
            result["ambiguities"].append("stop_and_target_touched_same_bar; stop_wins")
            exit_index, exit_price, reason = index, stop, "stop_loss"
            break
        if stop_hit:
            exit_index, exit_price, reason = index, stop, "stop_loss"
            break
        if target_hit:
            exit_index, exit_price, reason = index, target, "take_profit"
            break

    if exit_index is None:
        if max_holding_index > len(candles) - 1:
            result.update(
                {
                    "status": "data_horizon_before_max_holding",
                    "resolution_bar": len(candles),
                    "resolution_reason": "insufficient_post_t_horizon_for_time_exit",
                }
            )
            return result
        exit_index = max_holding_index
        exit_price = float(candles[exit_index]["close"])
        reason = "max_holding_reached"

    assert exit_price is not None and reason is not None
    result.update(
        {
            "status": "exited",
            "exit_reason": reason,
            "resolution_bar": exit_index + 1,
            "resolution_reason": reason,
        }
    )
    _finish_pnl(
        result,
        candles,
        entry_index=entry_index,
        exit_index=exit_index,
        entry_price=entry_price,
        exit_price=exit_price,
        stop=stop,
        direction=direction,
        exit_reason=reason,
        exclude_entry_favorable_extreme=(
            (action == "wait_for_trigger" and entry_type == "limit")
            or target_on_entry_ignored
        ),
    )
    if (
        action == "wait_for_trigger" and entry_type == "limit"
    ) or target_on_entry_ignored:
        result["excursion_policy"] += (
            "; "
            "pending_entry_bar_favorable_extreme_excluded_when_order_unknown; "
            "subsequent_pre_exit_bars_use_full_extrema"
        )
    return result


def evaluate_legacy(
    analysis: dict[str, Any],
    answer_key: Any,
    *,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    bar_duration_seconds: int | None = None,
    timeframe: str | None = None,
    normalization_transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the old pilot's setup sequence without inventing a target/P&L."""
    transform = _extract_normalization_transform(answer_key, normalization_transform)
    normalization_info, normalization_errors = _validate_normalization_transform(
        transform
    )
    resolved_duration, duration_source, duration_errors = _resolve_bar_duration(
        answer_key,
        bar_duration_seconds=bar_duration_seconds,
        timeframe=timeframe,
        normalization_transform=transform,
    )
    result = _base_result(
        mode="legacy_scenario",
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        bar_duration_seconds=resolved_duration,
        bar_duration_source=duration_source,
    )
    result.update(normalization_info)
    errors = (
        _validate_costs(fee_bps, slippage_bps) + duration_errors + normalization_errors
    )
    scenario = analysis.get("leading_scenario") if isinstance(analysis, dict) else None
    if not isinstance(scenario, dict):
        errors.append("analysis must contain trade_plan or leading_scenario")
        result["validation_errors"] = errors
        return result
    raw_direction = scenario.get("direction")
    direction = {"up": "long", "down": "short", "long": "long", "short": "short"}.get(
        raw_direction
    )
    trigger, stop = scenario.get("trigger_level"), scenario.get("invalidation_level")
    if direction is None:
        errors.append("legacy leading_scenario.direction must be up/down/long/short")
    if not _number(trigger) or trigger <= 0:
        errors.append("legacy trigger_level must be a positive finite number")
    if not _number(stop) or stop <= 0:
        errors.append("legacy invalidation_level must be a positive finite number")
    if direction == "long" and _number(trigger) and _number(stop) and stop >= trigger:
        errors.append("legacy long invalidation_level must be below trigger_level")
    if direction == "short" and _number(trigger) and _number(stop) and stop <= trigger:
        errors.append("legacy short invalidation_level must be above trigger_level")
    candles = _extract_candles(answer_key)
    if not normalization_errors and isinstance(candles, list):
        candles = _apply_normalization_transform(candles, transform)
    errors += _validate_candles(candles, require_open_close=False)
    result.update(
        {
            "action": "wait_for_trigger",
            "direction": direction,
            "entry_type": "stop",
            "planned_entry_level": trigger,
            "stop_loss": stop,
            "cancellation_condition": scenario.get("invalidation_condition"),
            "validation_errors": errors,
        }
    )
    if errors:
        return result

    trigger, stop = float(trigger), float(stop)
    for index, candle in enumerate(candles, start=1):
        canceled = _touches_cancel(candle, direction, stop)
        triggered = _touches_entry(candle, direction, "stop", trigger)
        if canceled and triggered:
            result.update(
                {
                    "status": "intrabar_ambiguous_entry_cancel",
                    "same_bar_ambiguity": True,
                    "entry_touch_bar": index,
                    "stop_touch_bar": index,
                    "resolution_bar": index,
                    "resolution_reason": "trigger_and_invalidation_order_unknown",
                }
            )
            result["ambiguities"].append(
                "trigger_and_invalidation_touched_same_bar; "
                "path_is_between_no_entry_cancel_and_entry_then_stop"
            )
            _set_ambiguous_entry_cancel_bounds(result, entry=trigger, stop=stop)
            return result
        if canceled:
            result.update(
                {
                    "status": "canceled_before_entry",
                    "stop_touch_bar": index,
                    "cancellation_bar": index,
                    "resolution_bar": index,
                    "resolution_reason": "invalidation_before_trigger",
                }
            )
            return result
        if triggered:
            result.update(
                {
                    "status": "triggered_pnl_unscorable",
                    "entry_bar": index,
                    "entry_price": trigger,
                    "entry_touch_bar": index,
                    "trigger_bar": index,
                    "resolution_bar": index,
                    "resolution_reason": "triggered_but_missing_numeric_target",
                }
            )
            return result
    result.update(
        {
            "status": "not_triggered",
            "resolution_bar": len(candles),
            "resolution_reason": "horizon_without_trigger",
        }
    )
    return result


def evaluate_batch(
    payload: Any,
    *,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    bar_duration_seconds: int | None = None,
    timeframe: str | None = None,
    normalization_transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise TypeError("batch input must be an array or an object with a cases array")
    results = []
    for index, item in enumerate(items):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("analysis"), dict)
            or not isinstance(item.get("answer_key"), (dict, list))
        ):
            results.append(
                {
                    "case_id": item.get("case_id") if isinstance(item, dict) else None,
                    "replay": {
                        "status": "invalid",
                        "validation_errors": [
                            f"batch item {index} requires analysis and answer_key objects"
                        ],
                    },
                }
            )
            continue
        results.append(
            {
                "case_id": item.get("case_id"),
                "replay": evaluate_trade(
                    item["analysis"],
                    item["answer_key"],
                    fee_bps=fee_bps,
                    slippage_bps=slippage_bps,
                    bar_duration_seconds=item.get(
                        "bar_duration_seconds", bar_duration_seconds
                    ),
                    timeframe=item.get("timeframe", timeframe),
                    normalization_transform=item.get(
                        "normalization_transform", normalization_transform
                    ),
                ),
            }
        )
    return {"schema_version": "1.0", "results": results}


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", help="single analyst JSON")
    parser.add_argument("--answer-key", help="single private answer-key JSON")
    parser.add_argument(
        "--batch", help="batch JSON containing embedded analysis and answer_key objects"
    )
    parser.add_argument("--output", help="write JSON here instead of stdout")
    parser.add_argument(
        "--fee-bps", type=float, default=0.0, help="fee per side in basis points"
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=0.0,
        help="slippage per side in basis points",
    )
    parser.add_argument(
        "--bar-duration-seconds",
        type=int,
        help="trusted duration of one candle; never inferred from open_time",
    )
    parser.add_argument(
        "--timeframe",
        help="trusted candle timeframe such as 4h or 1w",
    )
    parser.add_argument(
        "--normalization-transform",
        help="private JSON transform used for the normalized analyst package",
    )
    args = parser.parse_args()
    if bool(args.batch) == bool(args.analysis or args.answer_key):
        parser.error("use either --batch or both --analysis and --answer-key")
    if not args.batch and not (args.analysis and args.answer_key):
        parser.error("single mode requires both --analysis and --answer-key")

    try:
        if args.batch:
            output = evaluate_batch(
                _load(args.batch),
                fee_bps=args.fee_bps,
                slippage_bps=args.slippage_bps,
                bar_duration_seconds=args.bar_duration_seconds,
                timeframe=args.timeframe,
                normalization_transform=(
                    _load(args.normalization_transform)
                    if args.normalization_transform
                    else None
                ),
            )
        else:
            output = evaluate_trade(
                _load(args.analysis),
                _load(args.answer_key),
                fee_bps=args.fee_bps,
                slippage_bps=args.slippage_bps,
                bar_duration_seconds=args.bar_duration_seconds,
                timeframe=args.timeframe,
                normalization_transform=(
                    _load(args.normalization_transform)
                    if args.normalization_transform
                    else None
                ),
            )
        rendered = json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    if args.output:
        Path(args.output).write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
