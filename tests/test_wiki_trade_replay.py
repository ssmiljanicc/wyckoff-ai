"""Focused tests for deterministic wiki-assisted trade replay."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spikes.wiki_trade_replay import evaluate_batch, evaluate_trade


def candle(open_: float, high: float, low: float, close: float) -> dict:
    return {"open_time": 1, "open": open_, "high": high, "low": low, "close": close}


def answer(*candles: dict) -> dict:
    return {"case_id": "case", "post_t_candles": list(candles)}


def normalization_transform(
    *, price_reference: float = 200, volume_reference: float = 50
) -> dict:
    return {
        "price_scale": "first_close_100",
        "price_reference": price_reference,
        "price_multiplier": 100 / price_reference,
        "volume_scale": "pre_t_median_volume_100",
        "volume_reference": volume_reference,
        "volume_multiplier": 100 / volume_reference,
        "round_decimals": 8,
        "timeframe": "4h",
        "bar_duration_ms": 4 * 3600 * 1000,
        "source_sha256": "a" * 64,
        "package_sha256": "b" * 64,
    }


def plan(
    *,
    action: str = "wait_for_trigger",
    direction: str = "long",
    entry_type: str = "stop",
    entry: float | None = 105,
    stop: float | None = 95,
    target: float | None = 115,
    max_bars: int | None = 10,
    expiry_bars: int | None = 10,
) -> dict:
    return {
        "trade_plan": {
            "action": action,
            "direction": direction,
            "entry_type": entry_type,
            "entry_level": entry,
            "stop_loss": stop,
            "take_profit": target,
            "max_holding_bars": max_bars,
            "entry_expiry_bars": expiry_bars if action == "wait_for_trigger" else None,
            "cancellation_condition": "Cancel at the numeric stop boundary.",
        }
    }


def test_long_stop_entry_then_target_with_r_and_excursions() -> None:
    result = evaluate_trade(
        plan(),
        answer(
            candle(100, 104, 99, 102),
            candle(102, 108, 101, 107),
            candle(107, 116, 104, 114),
        ),
    )

    assert result["status"] == "exited"
    assert result["entry_bar"] == 2
    assert result["exit_bar"] == 3
    assert result["exit_reason"] == "take_profit"
    assert result["entry_price"] == 105
    assert result["exit_price"] == 115
    assert result["gross_return_pct"] == pytest.approx(9.5238095)
    assert result["gross_r"] == pytest.approx(1.0)
    assert result["mfe_pct"] is None
    assert result["mfe_pct_bounds"] == pytest.approx(
        {"guaranteed": 10 / 105 * 100, "possible": 11 / 105 * 100}
    )
    assert result["mae_pct"] == pytest.approx(-4 / 105 * 100)
    assert result["exit_bar_excursion_ambiguity"] is True
    assert result["duration_bars"] == 2


def test_short_stop_entry_then_target() -> None:
    result = evaluate_trade(
        plan(direction="short", entry_type="stop", entry=95, stop=105, target=80),
        answer(
            candle(100, 102, 96, 97), candle(97, 100, 94, 96), candle(96, 98, 79, 81)
        ),
    )

    assert result["entry_bar"] == 2
    assert result["exit_bar"] == 3
    assert result["exit_reason"] == "take_profit"
    assert result["gross_return_pct"] == pytest.approx(15 / 95 * 100)
    assert result["gross_r"] == pytest.approx(1.5)
    assert result["mfe_pct"] is None
    assert result["mfe_pct_bounds"] == pytest.approx(
        {"guaranteed": 15 / 95 * 100, "possible": 16 / 95 * 100}
    )
    assert result["mae_pct"] == pytest.approx(-5 / 95 * 100)


@pytest.mark.parametrize(
    ("direction", "entry_type", "entry", "stop", "target", "bar"),
    [
        ("long", "limit", 95, 90, 110, candle(100, 101, 94, 97)),
        ("short", "limit", 105, 110, 90, candle(100, 106, 99, 104)),
    ],
)
def test_limit_entries(direction, entry_type, entry, stop, target, bar) -> None:
    result = evaluate_trade(
        plan(
            direction=direction,
            entry_type=entry_type,
            entry=entry,
            stop=stop,
            target=target,
            max_bars=1,
        ),
        answer(bar),
    )

    assert result["entry_bar"] == 1
    assert result["entry_price"] == entry
    assert result["exit_reason"] == "max_holding_reached"


@pytest.mark.parametrize(
    ("direction", "entry", "stop", "target", "first", "later"),
    [
        ("long", 105, 95, 115, candle(100, 104, 94, 96), candle(100, 110, 99, 108)),
        ("short", 95, 105, 80, candle(100, 106, 96, 104), candle(100, 101, 90, 92)),
    ],
)
def test_cancellation_before_entry_cannot_resurrect(
    direction, entry, stop, target, first, later
) -> None:
    result = evaluate_trade(
        plan(direction=direction, entry=entry, stop=stop, target=target),
        answer(first, later),
    )

    assert result["status"] == "canceled_before_entry"
    assert result["entry_bar"] is None
    assert result["exit_bar"] is None
    assert result["cancellation_bar"] == 1
    assert result["resolution_reason"] == "cancellation_before_entry"
    assert result["gross_return_pct"] == 0
    assert result["net_return_pct"] == 0


def test_entry_and_cancellation_same_bar_returns_unscorable_bounds() -> None:
    result = evaluate_trade(
        plan(),
        answer(candle(100, 106, 94, 103)),
        fee_bps=10,
        slippage_bps=5,
    )

    risk_pct = 10 / 105 * 100
    assert result["status"] == "intrabar_ambiguous_entry_cancel"
    assert result["same_bar_ambiguity"] is True
    assert "path_is_between" in result["ambiguities"][0]
    assert result["entry_bar"] is None
    assert result["pnl_scorable"] is False
    assert result["gross_return_pct"] is None
    assert result["gross_return_pct_bounds"] == pytest.approx(
        {"pessimistic": -risk_pct, "optimistic": 0}
    )
    assert result["net_return_pct_bounds"] == pytest.approx(
        {"pessimistic": -risk_pct - 0.3, "optimistic": 0}
    )
    assert result["gross_r_bounds"] == {"pessimistic": -1.0, "optimistic": 0.0}


def test_waiting_setup_expires_and_cannot_trigger_later() -> None:
    result = evaluate_trade(
        plan(expiry_bars=2),
        answer(
            candle(100, 104, 99, 102),
            candle(102, 104, 99, 103),
            candle(103, 110, 100, 109),
        ),
    )

    assert result["status"] == "expired_before_entry"
    assert result["resolution_bar"] == 2
    assert result["resolution_reason"] == "entry_expiry_reached"
    assert result["entry_bar"] is None
    assert result["gross_return_pct"] == 0


def test_short_post_t_horizon_does_not_pretend_expiry_was_reached() -> None:
    result = evaluate_trade(
        plan(expiry_bars=3),
        answer(candle(100, 104, 99, 102), candle(102, 104, 99, 103)),
    )

    assert result["status"] == "horizon_before_entry_expiry"
    assert result["resolution_bar"] == 2
    assert result["pnl_scorable"] is False


def test_enter_now_fills_at_first_open_and_stop_target_same_bar_uses_stop() -> None:
    result = evaluate_trade(
        plan(action="enter_now", entry_type="market", entry=101, stop=95, target=110),
        answer(candle(100, 111, 94, 105)),
    )

    assert result["entry_price"] == 100
    assert result["exit_price"] == 95
    assert result["exit_reason"] == "stop_loss"
    assert result["gross_return_pct"] == pytest.approx(-5)
    assert result["gross_r"] == pytest.approx(-1)
    assert result["same_bar_ambiguity"] is True


def test_stop_exit_bar_excursions_are_bounds_not_false_precision() -> None:
    result = evaluate_trade(
        plan(
            action="enter_now",
            entry_type="market",
            entry=100,
            stop=90,
            target=120,
        ),
        answer(candle(100, 119, 85, 95)),
    )

    assert result["exit_reason"] == "stop_loss"
    assert result["mfe_pct"] is None
    assert result["mae_pct"] is None
    assert result["mfe_pct_bounds"] == pytest.approx({"guaranteed": 0, "possible": 19})
    assert result["mae_pct_bounds"] == pytest.approx(
        {"best_case": -10, "worst_case": -15}
    )
    assert result["exit_bar_excursion_ambiguity"] is True


def test_target_exit_bar_excursions_are_bounds_not_false_precision() -> None:
    result = evaluate_trade(
        plan(
            action="enter_now",
            entry_type="market",
            entry=100,
            stop=90,
            target=110,
        ),
        answer(candle(100, 112, 91, 109)),
    )

    assert result["exit_reason"] == "take_profit"
    assert result["mfe_pct"] is None
    assert result["mae_pct"] is None
    assert result["mfe_pct_bounds"] == pytest.approx({"guaranteed": 10, "possible": 12})
    assert result["mae_pct_bounds"] == pytest.approx({"best_case": 0, "worst_case": -9})
    assert result["exit_bar_excursion_ambiguity"] is True


def test_short_enter_now_stop_exit() -> None:
    result = evaluate_trade(
        plan(
            action="enter_now",
            direction="short",
            entry_type="market",
            entry=99,
            stop=105,
            target=90,
        ),
        answer(candle(100, 106, 96, 104)),
    )

    assert result["entry_price"] == 100
    assert result["exit_reason"] == "stop_loss"
    assert result["gross_return_pct"] == pytest.approx(-5)


def test_pending_limit_entry_bar_target_is_not_credited_without_known_order() -> None:
    result = evaluate_trade(
        plan(entry_type="limit", entry=95, stop=90, target=110),
        answer(candle(100, 111, 94, 96), candle(96, 112, 95, 111)),
    )

    assert result["entry_bar"] == 1
    assert result["exit_bar"] == 2
    assert result["exit_reason"] == "take_profit"
    assert result["same_bar_ambiguity"] is True
    assert "target_not_credited" in result["ambiguities"][0]
    assert "pending_entry_bar_favorable_extreme_excluded" in result["excursion_policy"]


@pytest.mark.parametrize(
    ("direction", "entry", "stop", "target", "entry_bar", "next_bar", "expected_mfe"),
    [
        (
            "long",
            95,
            90,
            120,
            candle(100, 119, 94, 96),
            candle(96, 100, 95, 98),
            5 / 95 * 100,
        ),
        (
            "short",
            105,
            110,
            80,
            candle(100, 106, 81, 104),
            candle(104, 105, 100, 102),
            5 / 105 * 100,
        ),
    ],
)
def test_limit_entry_bar_pre_entry_favorable_extreme_is_excluded(
    direction, entry, stop, target, entry_bar, next_bar, expected_mfe
) -> None:
    result = evaluate_trade(
        plan(
            direction=direction,
            entry_type="limit",
            entry=entry,
            stop=stop,
            target=target,
            max_bars=2,
        ),
        answer(entry_bar, next_bar),
    )

    assert result["mfe_pct"] == pytest.approx(expected_mfe)
    assert "pending_entry_bar_favorable_extreme_excluded" in result["excursion_policy"]


def test_unresolved_trade_exits_at_max_holding_close() -> None:
    result = evaluate_trade(
        plan(max_bars=2),
        answer(
            candle(100, 106, 99, 104),
            candle(104, 110, 100, 108),
            candle(108, 114, 107, 112),
        ),
    )

    assert result["entry_bar"] == 1
    assert result["exit_bar"] == 2
    assert result["exit_price"] == 108
    assert result["duration_bars"] == 2
    assert result["exit_reason"] == "max_holding_reached"
    assert result["duration_seconds"] is None


def test_data_horizon_before_max_holding_is_open_and_unscorable() -> None:
    candles = [candle(100, 106, 99, 104)] + [
        candle(104, 109, 100, 105) for _ in range(11)
    ]
    result = evaluate_trade(plan(max_bars=60), answer(*candles))

    assert result["status"] == "data_horizon_before_max_holding"
    assert result["resolution_bar"] == 12
    assert result["resolution_reason"] == "insufficient_post_t_horizon_for_time_exit"
    assert result["entry_bar"] == 1
    assert result["exit_bar"] is None
    assert result["exit_price"] is None
    assert result["gross_return_pct"] is None
    assert result["gross_r"] is None
    assert result["pnl_scorable"] is False


@pytest.mark.parametrize(
    ("metadata_source", "metadata", "expected_seconds", "expected_human"),
    [
        ("answer_key", "4h", 2 * 4 * 3600, "8h"),
        ("call", "1w", 2 * 7 * 86400, "2w"),
    ],
)
def test_duration_uses_trusted_timeframe_metadata(
    metadata_source, metadata, expected_seconds, expected_human
) -> None:
    candles = [candle(100, 105, 95, 104), candle(104, 111, 103, 110)]
    key = {"post_t_candles": candles}
    kwargs = {}
    if metadata_source == "answer_key":
        key["timeframe"] = metadata
    else:
        kwargs["timeframe"] = metadata

    result = evaluate_trade(
        plan(action="enter_now", entry_type="market", entry=100, stop=90, target=110),
        key,
        **kwargs,
    )

    assert result["duration_bars"] == 2
    assert result["duration_seconds"] == expected_seconds
    assert result["duration_human"] == expected_human
    assert result["bar_duration_source"].startswith(metadata_source)


def test_duration_accepts_explicit_bar_duration_seconds() -> None:
    result = evaluate_trade(
        plan(action="enter_now", entry_type="market", entry=100, stop=90, target=110),
        answer(candle(100, 105, 95, 104), candle(104, 111, 103, 110)),
        bar_duration_seconds=4 * 3600,
    )

    assert result["duration_seconds"] == 8 * 3600
    assert result["duration_human"] == "8h"
    assert result["bar_duration_source"] == "call.bar_duration_seconds"


def test_invalid_timeframe_is_a_validation_error() -> None:
    result = evaluate_trade(
        plan(),
        {"timeframe": "daily", "post_t_candles": [candle(100, 106, 99, 104)]},
    )

    assert result["status"] == "invalid"
    assert any("must match" in error for error in result["validation_errors"])


def test_no_trade_needs_no_candles_and_has_zero_pnl() -> None:
    analysis = plan(
        action="no_trade",
        direction="none",
        entry_type="none",
        entry=None,
        stop=None,
        target=None,
        max_bars=None,
    )
    result = evaluate_trade(analysis, {})

    assert result["status"] == "no_trade"
    assert result["pnl_scorable"] is True
    assert result["exit_bar"] is None
    assert result["gross_return_pct"] == 0
    assert result["net_return_pct"] == 0


def test_private_answer_key_may_be_a_bare_candle_list() -> None:
    result = evaluate_trade(
        plan(action="enter_now", entry_type="market", entry=100, stop=90, target=110),
        [candle(100, 111, 99, 110)],
    )

    assert result["status"] == "exited"
    assert result["exit_reason"] == "take_profit"


def test_private_transform_maps_raw_post_t_prices_to_analyst_scale() -> None:
    raw = [
        {
            **candle(200, 242, 196, 240),
            "volume": 75,
        }
    ]
    result = evaluate_trade(
        plan(
            action="enter_now",
            entry_type="market",
            entry=100,
            stop=90,
            target=120,
            max_bars=1,
        ),
        raw,
        normalization_transform=normalization_transform(),
    )

    assert result["status"] == "exited"
    assert result["entry_price"] == 100
    assert result["exit_price"] == 120
    assert result["normalization_applied"] is True
    assert result["price_scale"] == "first_close_100"
    assert len(result["normalization_transform_sha256"]) == 64
    assert result["bar_duration_seconds"] == 4 * 3600
    assert result["bar_duration_source"] == "normalization_transform.bar_duration_ms"
    assert result["duration_human"] == "4h"
    assert raw[0]["open"] == 200
    assert raw[0]["volume"] == 75


def test_embedded_transform_preserves_cutoff_to_post_t_scale_continuity() -> None:
    key = {
        "post_t_candles": [candle(200, 210, 190, 205)],
        "normalization_transform": normalization_transform(),
    }
    result = evaluate_trade(
        plan(
            action="enter_now",
            entry_type="market",
            entry=100,
            stop=90,
            target=120,
            max_bars=1,
        ),
        key,
    )

    # The raw open equals the pre-T reference, so it must meet the package at 100.
    assert result["entry_price"] == 100
    assert result["exit_price"] == pytest.approx(102.5)
    assert result["exit_reason"] == "max_holding_reached"


def test_inconsistent_private_normalization_transform_is_rejected() -> None:
    transform = normalization_transform()
    transform["price_multiplier"] = 0.6
    result = evaluate_trade(
        plan(),
        [candle(200, 220, 180, 210)],
        normalization_transform=transform,
    )

    assert result["status"] == "invalid"
    assert result["normalization_applied"] is False
    assert result["price_scale"] == "invalid_transform"
    assert any(
        "price_multiplier must equal" in error for error in result["validation_errors"]
    )


def test_fees_and_slippage_are_charged_per_side() -> None:
    result = evaluate_trade(
        plan(action="enter_now", entry_type="market", entry=100, stop=90, target=110),
        answer(candle(100, 111, 99, 110)),
        fee_bps=10,
        slippage_bps=5,
    )

    assert result["gross_return_pct"] == pytest.approx(10)
    assert result["round_trip_cost_pct"] == pytest.approx(0.3)
    assert result["net_return_pct"] == pytest.approx(9.7)
    assert result["net_r"] == pytest.approx(0.97)


def test_non_finite_cost_is_reported_without_non_json_number() -> None:
    result = evaluate_trade(
        plan(), answer(candle(100, 110, 90, 100)), fee_bps=float("nan")
    )

    assert result["status"] == "invalid"
    assert result["fee_bps_per_side"] is None
    assert result["round_trip_cost_pct"] is None
    assert "NaN" not in json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "analysis, expected",
    [
        (plan(direction="none"), "actionable trade requires direction"),
        (plan(entry_type="market"), "wait_for_trigger requires entry_type"),
        (plan(stop=110), "long levels must satisfy"),
        (plan(max_bars=0), "positive integer max_holding_bars"),
        (plan(expiry_bars=0), "positive integer entry_expiry_bars"),
    ],
)
def test_invalid_contracts_return_validation_errors(analysis, expected) -> None:
    result = evaluate_trade(analysis, answer(candle(100, 110, 90, 100)))

    assert result["status"] == "invalid"
    assert any(expected in error for error in result["validation_errors"])
    assert result["pnl_scorable"] is False


def test_enter_now_rejects_entry_expiry() -> None:
    analysis = plan(action="enter_now", entry_type="market")
    analysis["trade_plan"]["entry_expiry_bars"] = 2

    result = evaluate_trade(analysis, answer(candle(100, 110, 90, 100)))

    assert result["status"] == "invalid"
    assert "enter_now requires entry_expiry_bars=null" in result["validation_errors"]


def test_no_trade_rejects_holding_or_expiry_fields() -> None:
    analysis = plan(
        action="no_trade",
        direction="none",
        entry_type="none",
        entry=None,
        stop=None,
        target=None,
        max_bars=None,
    )
    analysis["trade_plan"]["max_holding_bars"] = 3
    analysis["trade_plan"]["entry_expiry_bars"] = 2

    result = evaluate_trade(analysis, {})

    assert result["status"] == "invalid"
    assert "no_trade requires max_holding_bars=null" in result["validation_errors"]
    assert "no_trade requires entry_expiry_bars=null" in result["validation_errors"]


def test_invalid_ohlc_is_rejected() -> None:
    result = evaluate_trade(plan(), answer(candle(100, 90, 95, 100)))

    assert result["status"] == "invalid"
    assert any(
        "OHLC values are inconsistent" in error for error in result["validation_errors"]
    )


def test_legacy_canceled_before_trigger_has_unscorable_pnl() -> None:
    analysis = {
        "leading_scenario": {
            "direction": "up",
            "trigger_level": 105,
            "invalidation_level": 95,
        }
    }
    result = evaluate_trade(
        analysis,
        {"post_t_candles": [{"high": 104, "low": 94}, {"high": 110, "low": 100}]},
    )

    assert result["mode"] == "legacy_scenario"
    assert result["status"] == "canceled_before_entry"
    assert result["entry_bar"] is None
    assert result["cancellation_bar"] == 1
    assert result["pnl_scorable"] is False
    assert result["gross_return_pct"] is None


def test_legacy_triggered_without_target_is_unscorable() -> None:
    analysis = {
        "leading_scenario": {
            "direction": "down",
            "trigger_level": 95,
            "invalidation_level": 105,
        }
    }
    result = evaluate_trade(analysis, {"post_t_candles": [{"high": 100, "low": 94}]})

    assert result["status"] == "triggered_pnl_unscorable"
    assert result["entry_bar"] == 1
    assert result["entry_price"] == 95
    assert result["pnl_scorable"] is False


def test_legacy_same_bar_invalidation_wins() -> None:
    analysis = {
        "leading_scenario": {
            "direction": "up",
            "trigger_level": 105,
            "invalidation_level": 95,
        }
    }
    result = evaluate_trade(analysis, {"post_t_candles": [{"high": 106, "low": 94}]})

    assert result["status"] == "intrabar_ambiguous_entry_cancel"
    assert result["same_bar_ambiguity"] is True
    assert result["pnl_scorable"] is False
    assert result["gross_r_bounds"] == {"pessimistic": -1.0, "optimistic": 0.0}


def test_batch_keeps_case_ids_and_invalid_items() -> None:
    payload = {
        "cases": [
            {
                "case_id": "valid",
                "analysis": plan(),
                "answer_key": answer(candle(100, 104, 99, 101)),
            },
            {"case_id": "broken"},
        ]
    }
    result = evaluate_batch(payload)

    assert [item["case_id"] for item in result["results"]] == ["valid", "broken"]
    assert result["results"][0]["replay"]["status"] == "horizon_before_entry_expiry"
    assert result["results"][1]["replay"]["status"] == "invalid"


def test_cli_single_and_batch_emit_strict_json(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "spikes" / "wiki_trade_replay.py"
    analysis_path = tmp_path / "analysis.json"
    answer_path = tmp_path / "answer.json"
    batch_path = tmp_path / "batch.json"
    analysis_path.write_text(json.dumps(plan(max_bars=1)))
    answer_path.write_text(json.dumps(answer(candle(100, 106, 99, 104))))
    batch_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "one",
                        "analysis": plan(),
                        "answer_key": answer(candle(100, 104, 99, 101)),
                    }
                ]
            }
        )
    )

    single = subprocess.run(
        [
            sys.executable,
            str(script),
            "--analysis",
            str(analysis_path),
            "--answer-key",
            str(answer_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    batch = subprocess.run(
        [sys.executable, str(script), "--batch", str(batch_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(single.stdout)["status"] == "exited"
    assert json.loads(batch.stdout)["results"][0]["case_id"] == "one"
    assert "NaN" not in single.stdout + batch.stdout
