"""Tests for deterministic expert post-T outcome evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spikes.wiki_expert_outcome import evaluate_expert_outcome


REPO = Path(__file__).resolve().parents[1]


def candle(open_: float, high: float, low: float, close: float) -> dict:
    return {"open_time": 1, "open": open_, "high": high, "low": low, "close": close, "volume": 10}


def event(kind: str, **values) -> dict:
    return {"kind": kind, **values}


def contract(
    *, direction: str = "long", trigger: dict | None = None,
    invalidation: dict | None = None, target: dict | None = None,
    scale: str = "input_as_provided", horizons: list[int] | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "case_id": "fixture",
        "direction": direction,
        "trigger": trigger or event("numeric", level=105),
        "invalidation": invalidation or event("numeric", level=95),
        "target": target or event("numeric", level=115),
        "horizons": horizons or [1, 2, 3],
        "numeric_level_scale": scale,
    }


def transform() -> dict:
    return {
        "price_scale": "first_close_100",
        "price_reference": 200,
        "price_multiplier": 0.5,
        "volume_scale": "pre_t_median_volume_100",
        "volume_reference": 10,
        "volume_multiplier": 10,
        "round_decimals": 8,
    }


def test_raw_numeric_long_contract_normalizes_and_resolves_target_after_trigger() -> None:
    result = evaluate_expert_outcome(
        contract(
            trigger=event("numeric", level=210, description="break resistance"),
            invalidation=event("numeric", level=190),
            target=event("numeric", level=230),
            scale="raw",
        ),
        [
            candle(200, 208, 198, 204),
            candle(204, 216, 202, 214),
            candle(214, 232, 210, 228),
        ],
        normalization_transform=transform(),
    )

    assert result["status"] == "evaluated"
    assert result["normalization"]["normalization_applied"] is True
    assert result["events"]["trigger"]["source_level"] == 210
    assert result["events"]["trigger"]["evaluated_level"] == 105
    assert result["events"]["trigger"]["first_touch_bar"] == 2
    assert result["events"]["target"]["first_touch_bar"] == 3
    assert result["event_ordering"] == {
        "status": "resolved",
        "activation_bar": 2,
        "outcome": "target_reached_after_trigger",
        "outcome_bar": 3,
        "sequence": [
            {"bar": 2, "events": ["trigger"], "relation": "single"},
            {"bar": 3, "events": ["target"], "relation": "single"},
        ],
        "ambiguities": [],
    }


def test_invalidation_before_trigger_is_resolved_without_trade_claim() -> None:
    result = evaluate_expert_outcome(
        contract(),
        [candle(100, 104, 94, 96), candle(96, 106, 95, 105)],
    )

    assert result["event_ordering"]["outcome"] == "invalidated_before_trigger"
    assert result["event_ordering"]["outcome_bar"] == 1
    assert result["directional_observation"]["trade_executed"] is False


def test_same_bar_trigger_and_target_is_conservatively_ambiguous() -> None:
    result = evaluate_expert_outcome(
        contract(),
        [candle(100, 116, 99, 110)],
    )

    assert result["event_ordering"]["status"] == "intrabar_ambiguous"
    assert result["event_ordering"]["outcome"] == "order_unknown"
    assert result["event_ordering"]["ambiguities"] == [
        "trigger_and_target_same_bar_order_unknown"
    ]


def test_same_later_bar_invalidation_and_target_is_ambiguous() -> None:
    result = evaluate_expert_outcome(
        contract(),
        [candle(100, 106, 99, 105), candle(105, 116, 94, 106)],
    )

    assert result["event_ordering"]["activation_bar"] == 1
    assert result["event_ordering"]["outcome_bar"] == 2
    assert result["event_ordering"]["ambiguities"] == [
        "invalidation_and_target_same_bar_order_unknown"
    ]


def test_short_numeric_contract_uses_directional_touch_rules() -> None:
    result = evaluate_expert_outcome(
        contract(
            direction="short",
            trigger=event("numeric", level=95),
            invalidation=event("numeric", level=105),
            target=event("numeric", level=80),
        ),
        [
            candle(100, 102, 96, 98),
            candle(98, 100, 94, 96),
            candle(96, 98, 79, 81),
        ],
    )

    assert result["events"]["trigger"]["first_touch_bar"] == 2
    assert result["events"]["target"]["first_touch_bar"] == 3
    assert result["event_ordering"]["outcome"] == "target_reached_after_trigger"


def test_partial_direction_only_contract_reports_returns_without_execution() -> None:
    value = contract(
        direction="short",
        trigger=event("qualitative", description="weak rally fails"),
        invalidation=event("unavailable", reason="benchmark_unavailable"),
        target=event("reference", reference="prior_low"),
        scale="not_applicable",
        horizons=[1, 2, 4],
    )
    result = evaluate_expert_outcome(
        value,
        [candle(100, 102, 95, 98), candle(98, 99, 90, 92), candle(92, 96, 91, 94)],
    )

    assert result["scorable_fields"] == {
        "trigger": False, "invalidation": False, "target": False,
        "event_ordering": False,
    }
    assert result["events"]["trigger"]["na_reason"] == (
        "qualitative_condition_not_deterministically_replayable"
    )
    assert result["events"]["invalidation"]["na_reason"] == "benchmark_unavailable"
    assert result["events"]["target"]["na_reason"] == (
        "reference_without_numeric_level:prior_low"
    )
    assert result["event_ordering"]["status"] == "direction_only"
    observations = result["directional_observation"]
    assert observations["trade_executed"] is False
    assert observations["baseline"] == {
        "kind": "first_post_t_open", "bar": 1, "price": 100,
    }
    assert observations["returns_by_horizon"]["2"] == pytest.approx({
        "available": True,
        "bars": 2,
        "market_return_pct": -8,
        "directional_return_pct": 8,
        "mfe_pct": 10,
        "mae_pct": -2,
        "reason": None,
    })
    assert observations["returns_by_horizon"]["4"]["available"] is False


def test_prior_high_is_scorable_only_when_encoded_as_numeric_level() -> None:
    result = evaluate_expert_outcome(
        contract(
            trigger=event("numeric", level=105),
            invalidation=event("not_stated"),
            target=event("numeric", level=112, description="explicit prior high"),
        ),
        [candle(100, 106, 99, 105), candle(105, 113, 103, 111)],
    )

    assert result["events"]["target"]["scorable"] is True
    assert result["events"]["target"]["first_touch_bar"] == 2
    assert result["event_ordering"]["outcome"] == "target_reached_after_trigger"


@pytest.mark.parametrize(
    "unavailable",
    ["benchmark_unavailable", "point_and_figure_unavailable"],
)
def test_explicitly_unavailable_inputs_are_na_with_reason(unavailable: str) -> None:
    result = evaluate_expert_outcome(
        contract(
            trigger=event("not_stated"),
            invalidation=event("not_stated"),
            target=event("unavailable", reason=unavailable),
            scale="not_applicable",
        ),
        [],
    )

    assert result["status"] == "evaluated"
    assert result["events"]["target"]["status"] == "na"
    assert result["events"]["target"]["na_reason"] == unavailable
    assert result["directional_observation"]["full_horizon"] is None


def test_raw_numeric_levels_require_valid_transform() -> None:
    result = evaluate_expert_outcome(contract(scale="raw"), [candle(100, 106, 94, 101)])

    assert result["status"] == "invalid"
    assert "raw numeric levels require normalization_transform" in result["validation_errors"]


def test_contract_and_ohlcv_reject_unknown_fields() -> None:
    value = contract()
    value["invented"] = True
    bad_candle = candle(100, 106, 94, 101)
    bad_candle["secret"] = 1
    result = evaluate_expert_outcome(value, [bad_candle])

    assert result["status"] == "invalid"
    assert any("contract has unsupported fields" in item for item in result["validation_errors"])
    assert any("unsupported fields" in item and "secret" in item for item in result["validation_errors"])


def test_empty_horizons_and_nonpositive_price_are_invalid() -> None:
    value = contract(horizons=[1])
    value["horizons"] = []
    result = evaluate_expert_outcome(value, [candle(0, 1, 0, 1)])

    assert result["status"] == "invalid"
    assert any("horizons" in item for item in result["validation_errors"])
    assert any("must be positive" in item for item in result["validation_errors"])


def test_cli_writes_stable_json_and_returns_zero(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    candles_path = tmp_path / "candles.json"
    output_path = tmp_path / "output.json"
    contract_path.write_text(json.dumps(contract()))
    candles_path.write_text(json.dumps([candle(100, 106, 99, 105)]))

    process = subprocess.run(
        [
            sys.executable, str(REPO / "spikes/wiki_expert_outcome.py"),
            "--contract", str(contract_path), "--post-t-ohlcv", str(candles_path),
            "--output", str(output_path),
        ],
        cwd=REPO, capture_output=True, text=True, check=False,
    )

    assert process.returncode == 0, process.stderr
    output = json.loads(output_path.read_text())
    assert output["status"] == "evaluated"
    assert output["schema_version"] == "1.0"
