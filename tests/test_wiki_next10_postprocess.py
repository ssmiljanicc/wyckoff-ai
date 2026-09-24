"""Tests for deterministic next-10 post-processing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spikes import wiki_next10_postprocess as post


REPO = Path(__file__).resolve().parents[1]


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def candle(open_: float, high: float, low: float, close: float) -> dict:
    return {
        "open_time": 1, "open": open_, "high": high, "low": low,
        "close": close, "volume": 10,
    }


def transform(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "price_scale": "first_close_100",
        "price_reference": 100,
        "price_multiplier": 1,
        "volume_scale": "pre_t_median_volume_100",
        "volume_reference": 10,
        "volume_multiplier": 10,
        "round_decimals": 8,
        "timeframe": "4h",
        "bar_duration_ms": 14_400_000,
    }


def analysis(*, no_trade: bool, leading: str) -> dict:
    if no_trade:
        plan = {
            "action": "no_trade", "direction": "none", "entry_type": "none",
            "entry_level": None, "stop_loss": None, "take_profit": None,
            "entry_expiry_bars": None, "max_holding_bars": None,
            "cancellation_condition": "No trade.",
        }
    else:
        plan = {
            "action": "enter_now", "direction": "long", "entry_type": "market",
            "entry_level": 100, "stop_loss": 90, "take_profit": 110,
            "entry_expiry_bars": None, "max_holding_bars": 2,
            "cancellation_condition": "Stop at 90.",
        }
    return {
        "leading_scenario": {"direction": leading},
        "trade_plan": plan,
    }


def source_contract(direction: str | None = "up") -> dict:
    return {
        "schema_version": "expert-outcome-contract.v1",
        "direction": direction,
        "trigger": "demand remains present" if direction is not None else None,
        "invalidation": None,
        "target": "retest of prior highs" if direction is not None else None,
        "numeric_entry": None,
        "numeric_stop": None,
        "numeric_target": None,
        "deterministic_trade_replay_eligible": False,
        "non_replay_reason": "No explicit numeric entry, stop, or target.",
        "rule": "Never invent levels.",
    }


def fixture_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    run_root = tmp_path / "run"
    post_t_root = tmp_path / "post_t"
    registry_path = tmp_path / "registry.json"
    dump(run_root / "run_contract.json", {"run_id": "v8", "contract": {"version": 8}})
    cases = []
    for index in range(10):
        case_id = f"case_{index:02d}"
        direction = None if index == 9 else ("sideways" if index == 8 else "up")
        cases.append({"case_id": case_id, "outcome_contract": source_contract(direction)})
        dump(run_root / "_private/package_transforms" / f"{case_id}.json", transform(case_id))
        dump(post_t_root / f"{case_id}.json", [
            candle(100, 105, 95, 104),
            candle(104, 112, 103, 111),
            candle(111, 115, 108, 114),
        ])
        dump(run_root / "results" / case_id / "arm_a" / "output.json", analysis(
            no_trade=False, leading="up",
        ))
        dump(run_root / "results" / case_id / "arm_b" / "output.json", analysis(
            no_trade=True, leading="down",
        ))
    dump(registry_path, {
        "schema_version": "fixture", "frozen": True, "validated": True,
        "cases": cases,
    })
    return run_root, registry_path, post_t_root


def test_compile_never_parses_numeric_text_and_preserves_prior_reference() -> None:
    source = source_contract("down_conditional")
    source["target"] = "retest $26,000 near prior lows"
    source["numeric_target"] = None

    compiled = post.compile_outcome_contract("case", source)

    assert compiled["direction"] == "short"
    assert compiled["target"] == {
        "kind": "reference", "reference": "prior_low",
        "description": "retest $26,000 near prior lows",
    }
    assert compiled["numeric_level_scale"] == "not_applicable"


def test_compile_marks_benchmark_and_pnf_events_unavailable() -> None:
    benchmark = source_contract("up_conditional")
    benchmark.update({
        "event_scoring": "na_benchmark_dependent",
        "trigger": "LINK leads while BTC corrects",
        "target": "higher high",
        "non_replay_reason": "External BTC benchmark is unavailable.",
    })
    compiled_benchmark = post.compile_outcome_contract("benchmark", benchmark)
    assert compiled_benchmark["trigger"]["reason"] == "benchmark_unavailable"
    assert compiled_benchmark["target"]["reason"] == "benchmark_unavailable"

    pnf = source_contract("up")
    pnf.update({
        "trigger": "Point-and-Figure confirming count",
        "target": "$26,000",
        "non_replay_reason": "Point-and-Figure evidence is unavailable.",
    })
    compiled_pnf = post.compile_outcome_contract("pnf", pnf)
    assert compiled_pnf["trigger"]["reason"] == "point_and_figure_unavailable"
    assert compiled_pnf["target"]["reason"] == "point_and_figure_unavailable"


def test_numeric_fields_require_explicit_scorable_permission() -> None:
    blocked = source_contract("up")
    blocked["numeric_target"] = 120
    blocked["numeric_target_scorable"] = False
    compiled = post.compile_outcome_contract("blocked", blocked)
    assert compiled["target"]["kind"] != "numeric"

    eligible = source_contract("up")
    eligible.update({
        "deterministic_trade_replay_eligible": True,
        "numeric_entry": 105,
        "numeric_stop": 95,
        "numeric_target": 120,
        "numeric_target_scorable": True,
    })
    compiled = post.compile_outcome_contract("eligible", eligible)
    assert compiled["trigger"]["level"] == 105
    assert compiled["invalidation"]["level"] == 95
    assert compiled["target"]["level"] == 120
    assert compiled["numeric_level_scale"] == "raw"


def test_generate_writes_twenty_replays_expert_results_summary_and_manifest(
    tmp_path: Path,
) -> None:
    run_root, registry_path, post_t_root = fixture_tree(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    post.generate(
        run_root=run_root, source_registry=registry_path,
        post_t_root=post_t_root, output_root=output,
    )

    assert len(list((output / "trade_replays").glob("*/*.json"))) == 20
    assert len(list((output / "compiled_contracts").glob("*.json"))) == 10
    assert len(list((output / "expert_results").glob("*.json"))) == 10
    replay = json.loads((output / "trade_replays/case_00/arm_a.json").read_text())
    assert replay["fee_bps_per_side"] == 10
    assert replay["slippage_bps_per_side"] == 5
    assert replay["exit_reason"] == "take_profit"
    summary = json.loads((output / "summary.json").read_text())
    assert summary["analyst_call_count"] == 20
    assert summary["arms"]["arm_a"]["action_counts"] == {
        "enter_now": 10, "no_trade": 0, "wait_for_trigger": 0,
    }
    assert summary["arms"]["arm_a"]["entered_count"] == 10
    assert summary["arms"]["arm_a"]["target_exit_count"] == 10
    assert summary["arms"]["arm_a"]["wins"] == 10
    assert summary["arms"]["arm_b"]["no_trade_count"] == 10
    assert summary["expert"]["trade_replay_eligible_count"] == 0
    assert summary["expert"]["trade_executed_claimed"] is False
    assert summary["expert"]["directional_case_count"] == 8
    assert summary["comparison"]["leading_direction_compared_count"] == 16
    assert len(summary["per_case"]) == 20
    na_result = json.loads((output / "expert_results/case_09.json").read_text())
    assert na_result["status"] == "not_applicable"
    assert na_result["directional_observation"]["trade_executed"] is False

    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest["inputs"]["analyst_outputs"]) == 20
    assert len(manifest["inputs"]["post_t"]) == 10
    assert len(manifest["inputs"]["transforms"]) == 10
    assert len(manifest["generated"]) == 41
    assert set(manifest["inputs"]["evaluator_scripts"]) == {
        "spikes/wiki_next10_postprocess.py",
        "spikes/wiki_trade_replay.py",
        "spikes/wiki_expert_outcome.py",
    }


def test_verify_requires_bit_identical_output(tmp_path: Path) -> None:
    run_root, registry_path, post_t_root = fixture_tree(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    post.generate(
        run_root=run_root, source_registry=registry_path,
        post_t_root=post_t_root, output_root=output,
    )

    post.verify(
        run_root=run_root, source_registry=registry_path,
        post_t_root=post_t_root, output_root=output,
    )
    summary = json.loads((output / "summary.json").read_text())
    summary["case_count"] = 99
    dump(output / "summary.json", summary)
    with pytest.raises(post.PostprocessError, match="byte mismatch"):
        post.verify(
            run_root=run_root, source_registry=registry_path,
            post_t_root=post_t_root, output_root=output,
        )


def test_missing_or_extra_case_fails_strictly(tmp_path: Path) -> None:
    run_root, registry_path, post_t_root = fixture_tree(tmp_path)
    (post_t_root / "case_09.json").unlink()
    dump(post_t_root / "unexpected.json", [])
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(post.PostprocessError, match="post-T case mismatch"):
        post.generate(
            run_root=run_root, source_registry=registry_path,
            post_t_root=post_t_root, output_root=output,
        )


def test_cli_generates_and_verifies_without_overwriting(tmp_path: Path) -> None:
    run_root, registry_path, post_t_root = fixture_tree(tmp_path)
    output = tmp_path / "cli-output"
    base = [
        sys.executable, str(REPO / "spikes/wiki_next10_postprocess.py"),
        "--run-root", str(run_root),
        "--source-registry", str(registry_path),
        "--post-t-root", str(post_t_root),
        "--output-root", str(output),
    ]

    generated = subprocess.run(
        base, cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert generated.returncode == 0, generated.stderr
    verified = subprocess.run(
        [*base, "--verify"], cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert verified.returncode == 0, verified.stderr
    refused = subprocess.run(
        base, cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert refused.returncode == 2
    assert "refusing to overwrite" in refused.stderr
