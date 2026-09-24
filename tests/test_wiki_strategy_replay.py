"""End-to-end tests for frozen multi-strategy replay."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from spikes import wiki_strategy_assessment as assessment
from spikes import wiki_strategy_replay as replay


REPO = Path(__file__).resolve().parents[1]


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def candle(open_: float, high: float, low: float, close: float) -> dict:
    return {
        "open_time": 1,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 10,
    }


def transform(case_id: str, packaged_input_sha256: str = "a" * 64) -> dict:
    return {
        "case_id": case_id,
        "packaged_input_sha256": packaged_input_sha256,
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


def trade_plan(
    *,
    action: str = "wait_for_trigger",
    entry: float | None = 105,
    stop: float | None = 95,
    target: float | None = 135,
    max_bars: int | None = 3,
    expiry: int | None = 2,
) -> dict:
    if action == "no_trade":
        return {
            "action": "no_trade",
            "direction": "none",
            "entry_type": "none",
            "entry_level": None,
            "stop_loss": None,
            "take_profit": None,
            "entry_expiry_bars": None,
            "max_holding_bars": None,
            "cancellation_condition": "Skip this setup.",
        }
    return {
        "action": action,
        "direction": "long",
        "entry_type": "market" if action == "enter_now" else "stop",
        "entry_level": entry,
        "stop_loss": stop,
        "take_profit": target,
        "entry_expiry_bars": expiry if action == "wait_for_trigger" else None,
        "max_holding_bars": max_bars,
        "cancellation_condition": "Cancel at the stop boundary.",
    }


SCENARIOS = {
    "target": (
        trade_plan(),
        [candle(100, 106, 99, 104), candle(104, 136, 103, 135)],
    ),
    "stop": (
        trade_plan(action="enter_now", entry=100, stop=95, target=115),
        [candle(100, 104, 94, 96)],
    ),
    "time": (
        trade_plan(action="enter_now", entry=100, stop=90, target=130, max_bars=2),
        [candle(100, 104, 96, 102), candle(102, 108, 100, 105)],
    ),
    "cancel": (
        trade_plan(),
        [candle(100, 104, 94, 96), candle(96, 110, 96, 108)],
    ),
    "expiry": (
        trade_plan(expiry=2),
        [candle(100, 104, 99, 102), candle(102, 104, 99, 103)],
    ),
    "ambiguous": (
        trade_plan(),
        [candle(100, 106, 94, 103)],
    ),
    "entry_horizon": (
        trade_plan(expiry=3),
        [candle(100, 104, 99, 102)],
    ),
    "holding_horizon": (
        trade_plan(action="enter_now", entry=100, stop=90, target=130, max_bars=3),
        [candle(100, 104, 96, 102)],
    ),
}


def fixture_tree(tmp_path: Path, names: tuple[str, ...] = tuple(SCENARIOS)):
    plans_root = tmp_path / "plans"
    transforms_root = tmp_path / "transforms"
    post_t_root = tmp_path / "post_t"
    cases = []
    manifest_inputs = []
    for index, name in enumerate(names):
        case_id = f"case_{name}"
        plan_namespace = hashlib.sha256(case_id.encode()).hexdigest()[:16]
        selected = replay.STRATEGY_IDS[index % len(replay.STRATEGY_IDS)]
        selected_plan, candles = SCENARIOS[name]
        strategies = []
        for strategy_id in replay.STRATEGY_IDS:
            if strategy_id == selected:
                item = {
                    "strategy_id": strategy_id,
                    "assessment_status": "eligible",
                    "skip_reason": None,
                    "trade_plan": selected_plan,
                    "reward_risk": 3.0,
                    "evidence": [{"source": "analyst.trade_plan"}],
                }
            else:
                status = (
                    "insufficient_evidence" if index % 2 else "ineligible"
                )
                item = {
                    "strategy_id": strategy_id,
                    "assessment_status": status,
                    "skip_reason": "setup_absent",
                    "trade_plan": trade_plan(action="no_trade"),
                    "reward_risk": None,
                    "evidence": [],
                }
            strategies.append(item)
            dump(
                plans_root / "plans" / plan_namespace / "arm_a" / f"{strategy_id}.json",
                item,
            )
        baseline = {
            "origin": "analyst_trade_plan",
            "trade_plan": trade_plan(action="no_trade"),
        }
        dump(
            plans_root / "plans" / plan_namespace / "arm_a" / "baseline.json",
            baseline,
        )
        case = {
            "case_id": case_id,
            "arm": "arm_a",
            "analyst_input_sha256": f"{index + 1:064x}",
            "candles_input_sha256": f"{index + 101:064x}",
            "packaged_candles_sha256": "a" * 64,
            "sidecar_sha256": f"{index + 201:064x}",
            "result_output_sha256": "b" * 64,
            "result_meta_sha256": "c" * 64,
            "result_origin": "model_accepted",
            "source_failure_sha256s": [],
            "strategies": strategies,
            "baseline": baseline,
        }
        cases.append(case)
        manifest_inputs.append(
            {
                key: case[key]
                for key in (
                    "case_id",
                    "arm",
                    "analyst_input_sha256",
                    "candles_input_sha256",
                    "packaged_candles_sha256",
                    "sidecar_sha256",
                    "result_output_sha256",
                    "result_meta_sha256",
                    "result_origin",
                    "source_failure_sha256s",
                )
            }
        )
        dump(transforms_root / f"{case_id}.json", transform(case_id))
        dump(post_t_root / f"{case_id}.json", candles)

    bundle = {
        "schema_version": replay.FROZEN_BUNDLE_SCHEMA,
        "strategy_ids": list(replay.STRATEGY_IDS),
        "cases": cases,
    }
    dump(plans_root / "frozen_plans.json", bundle)
    file_rows = [
        {
            "path": path.relative_to(plans_root).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(plans_root.rglob("*.json"))
    ]
    manifest = {
        "schema_version": replay.FROZEN_MANIFEST_SCHEMA,
        "bundle_schema_version": replay.FROZEN_BUNDLE_SCHEMA,
        "builder_script_sha256": "a" * 64,
        "assessment_schema_sha256": "b" * 64,
        "rule_bundle_sha256": "c" * 64,
        "inputs": manifest_inputs,
        "files": file_rows,
    }
    manifest["content_fingerprint"] = canonical_sha256(
        {
            key: manifest[key]
            for key in (
                "builder_script_sha256",
                "assessment_schema_sha256",
                "rule_bundle_sha256",
                "inputs",
                "files",
            )
        }
    )
    dump(plans_root / "frozen_manifest.json", manifest)
    return plans_root, transforms_root, post_t_root


def test_real_freezer_bundle_is_accepted_by_replay(tmp_path: Path) -> None:
    case_id = "case_freezer_integration"
    selected = {
        "strategy_id": replay.STRATEGY_IDS[0],
        "assessment_status": "eligible",
        "skip_reason": None,
        "trade_plan": trade_plan(),
        "reward_risk": 3.0,
        "evidence": [],
    }
    skipped = [
        {
            "strategy_id": strategy_id,
            "assessment_status": "ineligible",
            "skip_reason": "setup_absent",
            "trade_plan": trade_plan(action="no_trade"),
            "reward_risk": None,
            "evidence": [],
        }
        for strategy_id in replay.STRATEGY_IDS[1:]
    ]
    skipped[0].update(skip_reason="below_3r", reward_risk=1.5)
    record = {
        "case_id": case_id,
        "arm": "arm_a",
        "analyst_input_sha256": "1" * 64,
        "candles_input_sha256": "2" * 64,
        "packaged_candles_sha256": "a" * 64,
        "sidecar_sha256": "3" * 64,
        "result_output_sha256": "b" * 64,
        "result_meta_sha256": "c" * 64,
        "result_origin": "model_accepted",
        "source_failure_sha256s": [],
        "strategies": [selected, *skipped],
        "baseline": {
            "origin": "analyst_trade_plan",
            "trade_plan": trade_plan(action="no_trade"),
        },
    }
    plans_root = tmp_path / "frozen"
    assessment.freeze_plan_bundle([record], plans_root)
    transforms_root = tmp_path / "transforms"
    post_t_root = tmp_path / "post_t"
    dump(transforms_root / f"{case_id}.json", transform(case_id))
    dump(post_t_root / f"{case_id}.json", SCENARIOS["target"][1])

    replay.generate(
        plans_root=plans_root,
        transforms_root=transforms_root,
        post_t_root=post_t_root,
        output_root=tmp_path / "output",
    )
    summary = json.loads((tmp_path / "output" / "summary.json").read_text())
    assert summary["case_arm_count"] == 1
    assert summary["strategies"]["entered_count"] == 1


def test_generate_separates_denominators_outcomes_costs_and_baseline(
    tmp_path: Path,
) -> None:
    plans, transforms, post_t = fixture_tree(tmp_path)
    output = tmp_path / "output"

    replay.generate(
        plans_root=plans,
        transforms_root=transforms,
        post_t_root=post_t,
        output_root=output,
    )

    summary = json.loads((output / "summary.json").read_text())
    aggregate = summary["strategies"]
    assert summary["case_arm_count"] == 8
    assert summary["strategy_assessment_count"] == 32
    assert aggregate["total_count"] == 32
    assert aggregate["eligible_count"] == 8
    assert aggregate["skipped_count"] == 24
    assert aggregate["entered_count"] == 4
    assert aggregate["pnl_scorable_count"] == 5
    assert aggregate["entered_pnl_scorable_count"] == 3
    assert aggregate["triggered_count"] == 1
    assert aggregate["canceled_before_entry_count"] == 1
    assert aggregate["expired_before_entry_count"] == 1
    assert aggregate["insufficient_horizon_count"] == 2
    assert aggregate["exit_reason_counts"] == {
        "max_holding_reached": 1,
        "stop_loss": 1,
        "take_profit": 1,
    }
    assert aggregate["wins"] == 2
    assert aggregate["losses"] == 1
    assert aggregate["breakeven"] == 2
    assert aggregate["win_rate_pct"] == pytest.approx(40.0)
    assert aggregate["entered_wins"] == 2
    assert aggregate["entered_losses"] == 1
    assert aggregate["entered_breakeven"] == 0
    assert aggregate["entered_win_rate_pct"] == pytest.approx(200 / 3)
    assert aggregate["metrics"]["net_r"]["count"] == 5
    assert aggregate["fixed_risk_account_impact_pct"]["count"] == 5
    assert summary["fixed_risk_policy"]["initial_account_risk_pct"] == 1.0
    assert "no balance chaining" in summary["fixed_risk_policy"]["interpretation"]
    assert summary["baseline"]["total_count"] == 8
    assert summary["baseline"]["pnl_scorable_count"] == 8
    assert summary["baseline"]["entered_pnl_scorable_count"] == 0
    assert summary["baseline"]["breakeven"] == 8

    skipped = json.loads(
        (
            output
            / "replays"
            / "case_target"
            / "arm_a"
            / "phase_c_test.json"
        ).read_text()
    )
    assert skipped["assessment_status"] == "ineligible"
    assert skipped["replay"] is None
    target = json.loads(
        (
            output
            / "replays"
            / "case_target"
            / "arm_a"
            / "phase_c_shake_direct.json"
        ).read_text()
    )
    assert target["replay"]["exit_reason"] == "take_profit"
    assert target["fixed_risk_account_impact_pct"] == pytest.approx(
        target["replay"]["net_r"]
    )
    manifest = json.loads((output / "manifest.json").read_text())
    assert set(manifest["inputs"]["scripts"]) == {
        "wiki_strategy_replay.py",
        "wiki_trade_replay.py",
    }
    assert set(manifest["inputs"]["post_t"]) == {
        f"case_{name}" for name in SCENARIOS
    }


def test_rejects_tampered_or_non_exact_frozen_and_private_inputs(tmp_path: Path) -> None:
    plans, transforms, post_t = fixture_tree(tmp_path, ("target",))
    frozen_entry = (
        plans
        / "plans"
        / hashlib.sha256(b"case_target").hexdigest()[:16]
        / "arm_a"
        / "phase_c_shake_direct.json"
    )
    frozen_entry.write_text(frozen_entry.read_text() + " ")

    with pytest.raises(replay.StrategyReplayError, match="hash mismatch"):
        replay.generate(
            plans_root=plans,
            transforms_root=transforms,
            post_t_root=post_t,
            output_root=tmp_path / "tampered",
        )

    plans, transforms, post_t = fixture_tree(tmp_path / "exact", ("target",))
    dump(post_t / "extra.json", [candle(100, 101, 99, 100)])
    with pytest.raises(replay.StrategyReplayError, match="exact case set mismatch"):
        replay.generate(
            plans_root=plans,
            transforms_root=transforms,
            post_t_root=post_t,
            output_root=tmp_path / "extra-output",
        )

    plans, transforms, post_t = fixture_tree(tmp_path / "binding", ("target",))
    bad_transform = transform("case_target", packaged_input_sha256="f" * 64)
    dump(transforms / "case_target.json", bad_transform)
    with pytest.raises(replay.StrategyReplayError, match="packaged candle hash mismatch"):
        replay.generate(
            plans_root=plans,
            transforms_root=transforms,
            post_t_root=post_t,
            output_root=tmp_path / "binding-output",
        )


def test_verify_is_byte_identical_and_generate_never_overwrites(tmp_path: Path) -> None:
    plans, transforms, post_t = fixture_tree(tmp_path, ("target", "ambiguous"))
    output = tmp_path / "output"
    kwargs = {
        "plans_root": plans,
        "transforms_root": transforms,
        "post_t_root": post_t,
        "output_root": output,
    }
    replay.generate(**kwargs)
    replay.verify(**kwargs)

    with pytest.raises(replay.StrategyReplayError, match="already exists"):
        replay.generate(**kwargs)

    summary = output / "summary.json"
    summary.write_text(summary.read_text().replace('"status": "complete"', '"status": "edited"'))
    with pytest.raises(replay.StrategyReplayError, match="byte mismatch"):
        replay.verify(**kwargs)


def test_cli_has_only_replay_inputs_and_can_generate_then_verify(tmp_path: Path) -> None:
    plans, transforms, post_t = fixture_tree(tmp_path, ("target",))
    output = tmp_path / "output"
    help_text = replay.build_parser().format_help()
    assert "--model" not in help_text
    assert "--prompt" not in help_text
    assert "--package" not in help_text

    command = [
        sys.executable,
        str(REPO / "spikes" / "wiki_strategy_replay.py"),
        "--plans-root",
        str(plans),
        "--transforms-root",
        str(transforms),
        "--post-t-root",
        str(post_t),
        "--output-root",
        str(output),
    ]
    subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True)
    subprocess.run(
        [*command, "--verify"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
