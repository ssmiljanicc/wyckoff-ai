#!/usr/bin/env python3
"""Deterministic post-processing for a completed next-10 v8 benchmark run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spikes.wiki_expert_outcome import evaluate_expert_outcome
from spikes.wiki_trade_replay import evaluate_trade


SCHEMA_VERSION = "next10-postprocess.v1"
ARMS = ("arm_a", "arm_b")
EVENTS = ("trigger", "invalidation", "target")
HORIZONS = [1, 5, 10, 20, 40, 60]
DIRECTION_MAP = {
    "up": "long",
    "up_conditional": "long",
    "down": "short",
    "down_conditional": "short",
}
NUMERIC_FIELDS = {
    "trigger": "numeric_entry",
    "invalidation": "numeric_stop",
    "target": "numeric_target",
}


class PostprocessError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PostprocessError(f"cannot read valid JSON from {path}: {exc}") from exc


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _registry_cases(registry: Any) -> list[dict[str, Any]]:
    if not isinstance(registry, dict) or not isinstance(registry.get("cases"), list):
        raise PostprocessError("source registry must contain a cases array")
    cases = registry["cases"]
    if len(cases) != 10:
        raise PostprocessError(f"source registry must contain exactly 10 cases, got {len(cases)}")
    ids = [case.get("case_id") if isinstance(case, dict) else None for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise PostprocessError("every registry case must have a non-empty case_id")
    if len(ids) != len(set(ids)):
        raise PostprocessError("source registry contains duplicate case ids")
    for case in cases:
        contract = case.get("outcome_contract")
        if not isinstance(contract, dict):
            raise PostprocessError(f"{case['case_id']} is missing outcome_contract")
        if contract.get("schema_version") != "expert-outcome-contract.v1":
            raise PostprocessError(
                f"{case['case_id']} outcome_contract schema must be expert-outcome-contract.v1"
            )
    return cases


def _numeric_is_scorable(source: dict[str, Any], event_name: str) -> bool:
    explicit = source.get(f"{NUMERIC_FIELDS[event_name]}_scorable")
    if explicit is not None:
        return explicit is True
    if event_name == "target":
        if source.get("numeric_target_scorable") is not True:
            return False
        if source.get("target_scorable_on_anonymous_scale") is False:
            return False
        return source.get("deterministic_trade_replay_eligible") is True
    return source.get("deterministic_trade_replay_eligible") is True


def _unavailable_reason(source: dict[str, Any], text: str | None) -> str | None:
    combined = " ".join(
        str(value) for value in (
            source.get("event_scoring"), source.get("non_replay_reason"), text,
        ) if value is not None
    ).lower()
    if "benchmark" in combined:
        return "benchmark_unavailable"
    if "point-and-figure" in combined or "point and figure" in combined or "pnf" in combined:
        return "point_and_figure_unavailable"
    return None


def _compile_event(source: dict[str, Any], event_name: str) -> dict[str, Any]:
    numeric_field = NUMERIC_FIELDS[event_name]
    numeric = source.get(numeric_field)
    description = source.get(event_name)
    if numeric is not None:
        if not _number(numeric) or float(numeric) <= 0:
            raise PostprocessError(f"outcome_contract.{numeric_field} must be positive and finite")
        if _numeric_is_scorable(source, event_name):
            event: dict[str, Any] = {"kind": "numeric", "level": numeric}
            if isinstance(description, str) and description.strip():
                event["description"] = description
            return event
    if description is None:
        return {"kind": "not_stated"}
    if not isinstance(description, str) or not description.strip():
        raise PostprocessError(f"outcome_contract.{event_name} must be a string or null")
    unavailable = _unavailable_reason(source, description)
    if unavailable:
        return {
            "kind": "unavailable", "reason": unavailable,
            "description": description,
        }
    lowered = description.lower()
    if "prior low" in lowered or "previous low" in lowered:
        return {"kind": "reference", "reference": "prior_low", "description": description}
    if "prior high" in lowered or "previous high" in lowered:
        return {"kind": "reference", "reference": "prior_high", "description": description}
    return {"kind": "qualitative", "description": description}


def compile_outcome_contract(case_id: str, source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise PostprocessError(f"{case_id} outcome_contract must be an object")
    if source.get("schema_version") != "expert-outcome-contract.v1":
        raise PostprocessError(f"{case_id} has unsupported outcome contract schema")
    raw_direction = source.get("direction")
    direction = DIRECTION_MAP.get(raw_direction)
    events = {name: _compile_event(source, name) for name in EVENTS}
    numeric = any(event["kind"] == "numeric" for event in events.values())
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "direction": direction,
        **events,
        "horizons": HORIZONS,
        "numeric_level_scale": "raw" if numeric else "not_applicable",
        "source_direction": raw_direction,
        "direction_evaluable": direction is not None,
        "deterministic_trade_replay_eligible": (
            source.get("deterministic_trade_replay_eligible") is True
        ),
        "non_replay_reason": source.get("non_replay_reason"),
    }


def _strict_expert_contract(compiled: dict[str, Any]) -> dict[str, Any]:
    return {
        key: compiled[key]
        for key in (
            "schema_version", "case_id", "direction", "trigger", "invalidation",
            "target", "horizons", "numeric_level_scale",
        )
    }


def _na_expert_result(compiled: dict[str, Any]) -> dict[str, Any]:
    events: dict[str, Any] = {}
    for name in EVENTS:
        event = compiled[name]
        reason = (
            "expert_direction_sideways"
            if compiled["source_direction"] == "sideways"
            else "expert_direction_not_stated"
        )
        events[name] = {
            "kind": event["kind"],
            "description": event.get("description"),
            "source_level": event.get("level"),
            "evaluated_level": None,
            "scorable": False,
            "status": "na",
            "first_touch_bar": None,
            "na_reason": reason,
        }
        if "reference" in event:
            events[name]["reference"] = event["reference"]
    return {
        "schema_version": "1.0",
        "evaluator": "wiki_expert_outcome_v1",
        "status": "not_applicable",
        "case_id": compiled["case_id"],
        "direction": None,
        "numeric_level_scale": compiled["numeric_level_scale"],
        "validation_errors": [],
        "normalization": {
            "normalization_applied": False,
            "price_scale": "input_as_provided",
            "normalization_transform_sha256": None,
        },
        "scorable_fields": {
            "trigger": False, "invalidation": False, "target": False,
            "event_ordering": False,
        },
        "events": events,
        "event_ordering": {
            "status": "not_applicable", "activation_bar": None,
            "outcome": None, "outcome_bar": None, "sequence": [],
            "ambiguities": [],
        },
        "directional_observation": {
            "trade_executed": False, "baseline": None,
            "returns_by_horizon": {}, "full_horizon": None,
        },
        "limitations": [
            "Expert direction is sideways or unstated; directional outcome evaluation is N/A.",
            "No expert trade execution is claimed.",
        ],
    }


def _validate_input_sets(
    run_root: Path, cases: list[dict[str, Any]], post_t_root: Path,
) -> dict[str, dict[str, Path]]:
    case_ids = {case["case_id"] for case in cases}
    results_root = run_root / "results"
    if not results_root.is_dir():
        raise PostprocessError(f"missing run results directory: {results_root}")
    result_cases = {path.name for path in results_root.iterdir() if path.is_dir()}
    if result_cases != case_ids:
        raise PostprocessError(
            f"run result case mismatch: missing={sorted(case_ids - result_cases)}, "
            f"extra={sorted(result_cases - case_ids)}"
        )
    transforms_root = run_root / "_private/package_transforms"
    if not transforms_root.is_dir():
        raise PostprocessError(f"missing transform directory: {transforms_root}")
    post_files = {path.stem: path for path in post_t_root.glob("*.json")}
    transform_files = {path.stem: path for path in transforms_root.glob("*.json")}
    for label, found in (("post-T", set(post_files)), ("transform", set(transform_files))):
        if found != case_ids:
            raise PostprocessError(
                f"{label} case mismatch: missing={sorted(case_ids - found)}, "
                f"extra={sorted(found - case_ids)}"
            )
    analyst_outputs: dict[str, Path] = {}
    for case_id in sorted(case_ids):
        for arm in ARMS:
            path = results_root / case_id / arm / "output.json"
            if not path.is_file():
                raise PostprocessError(f"missing analyst output: {path}")
            analyst_outputs[f"{case_id}/{arm}"] = path
    return {
        "analyst_outputs": analyst_outputs,
        "post_t": post_files,
        "transforms": transform_files,
    }


def _metric_summary(values: list[float | int]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    numeric = [float(value) for value in values]
    return {
        "count": len(numeric),
        "mean": statistics.fmean(numeric),
        "median": statistics.median(numeric),
        "min": min(numeric),
        "max": max(numeric),
    }


def _normalized_llm_direction(analysis: dict[str, Any]) -> str | None:
    scenario = analysis.get("leading_scenario")
    if not isinstance(scenario, dict):
        return None
    return {"up": "long", "down": "short", "long": "long", "short": "short"}.get(
        scenario.get("direction")
    )


def _direction_comparison(llm_direction: str | None, expert_direction: str | None) -> dict[str, Any]:
    if expert_direction is None:
        return {
            "status": "na", "reason": "expert_direction_sideways_or_unstated",
            "llm_direction": llm_direction, "expert_direction": None, "matches": None,
        }
    if llm_direction is None:
        return {
            "status": "na", "reason": "llm_leading_direction_not_directional",
            "llm_direction": None, "expert_direction": expert_direction, "matches": None,
        }
    return {
        "status": "compared", "reason": None,
        "llm_direction": llm_direction, "expert_direction": expert_direction,
        "matches": llm_direction == expert_direction,
    }


def _trade_forward_comparison(
    replay: dict[str, Any], expert_result: dict[str, Any], expert_direction: str | None,
) -> dict[str, Any]:
    if expert_direction is None:
        reason = "expert_direction_sideways_or_unstated"
    elif replay.get("entry_bar") is None or replay.get("net_return_pct") is None:
        reason = "llm_trade_not_entered_or_return_unscorable"
    else:
        full = expert_result["directional_observation"].get("full_horizon")
        if not isinstance(full, dict) or full.get("directional_return_pct") is None:
            reason = "expert_forward_outcome_unavailable"
        else:
            llm_return = float(replay["net_return_pct"])
            expert_return = float(full["directional_return_pct"])
            return {
                "status": "compared", "reason": None,
                "llm_trade_direction": replay.get("direction"),
                "expert_direction": expert_direction,
                "llm_net_return_pct": llm_return,
                "expert_directional_forward_return_pct": expert_return,
                "same_sign": (llm_return > 0) == (expert_return > 0)
                if llm_return != 0 and expert_return != 0 else llm_return == expert_return,
            }
    return {
        "status": "na", "reason": reason,
        "llm_trade_direction": replay.get("direction"),
        "expert_direction": expert_direction,
        "llm_net_return_pct": None,
        "expert_directional_forward_return_pct": None,
        "same_sign": None,
    }


def _arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts = {action: sum(row["action"] == action for row in rows) for action in (
        "enter_now", "wait_for_trigger", "no_trade",
    )}
    valid_trades = [
        row for row in rows
        if row["entered"] and row["net_return_pct"] is not None
    ]
    return {
        "calls": len(rows),
        "action_counts": action_counts,
        "entered_count": sum(row["entered"] for row in rows),
        "cancelled_count": sum(row["cancelled"] for row in rows),
        "no_trade_count": action_counts["no_trade"],
        "target_exit_count": sum(row["exit_reason"] == "take_profit" for row in rows),
        "stop_exit_count": sum(row["exit_reason"] == "stop_loss" for row in rows),
        "time_exit_count": sum(row["exit_reason"] == "max_holding_reached" for row in rows),
        "ambiguous_count": sum(row["ambiguous"] for row in rows),
        "wins": sum(float(row["net_return_pct"]) > 0 for row in valid_trades),
        "losses": sum(float(row["net_return_pct"]) < 0 for row in valid_trades),
        "breakeven": sum(float(row["net_return_pct"]) == 0 for row in valid_trades),
        "net_return_pct": _metric_summary([
            row["net_return_pct"] for row in valid_trades
        ]),
        "net_r": _metric_summary([
            row["net_r"] for row in valid_trades if row["net_r"] is not None
        ]),
        "mfe_pct": _metric_summary([
            row["mfe_pct"] for row in valid_trades if row["mfe_pct"] is not None
        ]),
        "mfe_pct_bounds_count": sum(
            row["mfe_pct_bounds"] is not None for row in valid_trades
        ),
        "mae_pct": _metric_summary([
            row["mae_pct"] for row in valid_trades if row["mae_pct"] is not None
        ]),
        "mae_pct_bounds_count": sum(
            row["mae_pct_bounds"] is not None for row in valid_trades
        ),
        "duration_bars": _metric_summary([
            row["duration_bars"] for row in valid_trades if row["duration_bars"] is not None
        ]),
    }


def _expert_summary(
    cases: list[dict[str, Any]], compiled: dict[str, dict[str, Any]],
    expert_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    directional = [
        case_id for case_id, value in compiled.items() if value["direction_evaluable"]
    ]
    horizon_summary: dict[str, Any] = {}
    for horizon in HORIZONS:
        values = [
            expert_results[case_id]["directional_observation"]["returns_by_horizon"].get(str(horizon))
            for case_id in directional
        ]
        available = [value for value in values if isinstance(value, dict) and value.get("available")]
        horizon_summary[str(horizon)] = {
            "case_count": len(available),
            "directional_return_pct": _metric_summary([
                value["directional_return_pct"] for value in available
            ]),
            "mfe_pct": _metric_summary([value["mfe_pct"] for value in available]),
            "mae_pct": _metric_summary([value["mae_pct"] for value in available]),
        }
    na_reasons: dict[str, int] = {}
    for result in expert_results.values():
        for event in result["events"].values():
            reason = event.get("na_reason")
            if reason:
                na_reasons[reason] = na_reasons.get(reason, 0) + 1
    return {
        "case_count": len(cases),
        "trade_replay_eligible_count": sum(
            case["outcome_contract"].get("deterministic_trade_replay_eligible") is True
            for case in cases
        ),
        "trade_executed_claimed": False,
        "directional_case_count": len(directional),
        "direction_na_count": len(cases) - len(directional),
        "event_na_reason_counts": dict(sorted(na_reasons.items())),
        "direction_only_forward_metrics_by_horizon": horizon_summary,
    }


def _generated_manifest(output_root: Path) -> dict[str, str]:
    return {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*.json"))
        if path.name != "manifest.json"
    }


def generate(
    *, run_root: Path, source_registry: Path, post_t_root: Path,
    output_root: Path,
) -> None:
    run_contract_path = run_root / "run_contract.json"
    if not run_contract_path.is_file():
        raise PostprocessError(f"missing run contract: {run_contract_path}")
    load_json(run_contract_path)
    registry = load_json(source_registry)
    cases = _registry_cases(registry)
    inputs = _validate_input_sets(run_root, cases, post_t_root)

    compiled_by_case: dict[str, dict[str, Any]] = {}
    expert_by_case: dict[str, dict[str, Any]] = {}
    analyses: dict[str, dict[str, Any]] = {}
    replays: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda value: value["case_id"]):
        case_id = case["case_id"]
        post_t = load_json(inputs["post_t"][case_id])
        transform = load_json(inputs["transforms"][case_id])
        if transform.get("case_id") != case_id:
            raise PostprocessError(f"transform case_id mismatch for {case_id}")
        compiled = compile_outcome_contract(case_id, case["outcome_contract"])
        compiled_by_case[case_id] = compiled
        dump_json(output_root / "compiled_contracts" / f"{case_id}.json", compiled)
        if compiled["direction_evaluable"]:
            expert = evaluate_expert_outcome(
                _strict_expert_contract(compiled), post_t,
                normalization_transform=(
                    transform if compiled["numeric_level_scale"] == "raw" else None
                ),
            )
            if expert["status"] != "evaluated":
                raise PostprocessError(
                    f"expert evaluator rejected compiled contract for {case_id}: "
                    f"{expert['validation_errors']}"
                )
        else:
            expert = _na_expert_result(compiled)
        expert_by_case[case_id] = expert
        dump_json(output_root / "expert_results" / f"{case_id}.json", expert)

        for arm in ARMS:
            key = f"{case_id}/{arm}"
            analysis = load_json(inputs["analyst_outputs"][key])
            if not isinstance(analysis, dict):
                raise PostprocessError(f"analyst output must be an object: {key}")
            analyses[key] = analysis
            replay = evaluate_trade(
                analysis, post_t, fee_bps=10, slippage_bps=5,
                normalization_transform=transform,
            )
            replays[key] = replay
            dump_json(output_root / "trade_replays" / case_id / f"{arm}.json", replay)
            llm_direction = _normalized_llm_direction(analysis)
            direction_comparison = _direction_comparison(
                llm_direction, compiled["direction"],
            )
            trade_comparison = _trade_forward_comparison(
                replay, expert, compiled["direction"],
            )
            valid_trade_metrics = (
                replay.get("pnl_scorable") is True
                and replay.get("entry_bar") is not None
            )
            row = {
                "case_id": case_id,
                "arm": arm,
                "action": replay.get("action"),
                "status": replay.get("status"),
                "entered": replay.get("entry_bar") is not None,
                "cancelled": replay.get("status") == "canceled_before_entry",
                "exit_reason": replay.get("exit_reason"),
                "ambiguous": bool(replay.get("same_bar_ambiguity"))
                or str(replay.get("status", "")).startswith("intrabar_ambiguous"),
                "net_return_pct": replay.get("net_return_pct")
                if valid_trade_metrics else None,
                "net_r": replay.get("net_r") if valid_trade_metrics else None,
                "mfe_pct": replay.get("mfe_pct") if valid_trade_metrics else None,
                "mfe_pct_bounds": replay.get("mfe_pct_bounds")
                if valid_trade_metrics else None,
                "mae_pct": replay.get("mae_pct") if valid_trade_metrics else None,
                "mae_pct_bounds": replay.get("mae_pct_bounds")
                if valid_trade_metrics else None,
                "duration_bars": replay.get("duration_bars")
                if valid_trade_metrics else None,
                "llm_leading_vs_expert_direction": direction_comparison,
                "llm_trade_vs_expert_forward_outcome": trade_comparison,
            }
            rows.append(row)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "case_count": len(cases),
        "analyst_call_count": len(rows),
        "fee_bps_per_side": 10,
        "slippage_bps_per_side": 5,
        "arms": {
            arm: _arm_summary([row for row in rows if row["arm"] == arm])
            for arm in ARMS
        },
        "expert": _expert_summary(cases, compiled_by_case, expert_by_case),
        "comparison": {
            "leading_direction_compared_count": sum(
                row["llm_leading_vs_expert_direction"]["status"] == "compared"
                for row in rows
            ),
            "leading_direction_match_count": sum(
                row["llm_leading_vs_expert_direction"]["matches"] is True
                for row in rows
            ),
            "trade_forward_compared_count": sum(
                row["llm_trade_vs_expert_forward_outcome"]["status"] == "compared"
                for row in rows
            ),
            "trade_forward_same_sign_count": sum(
                row["llm_trade_vs_expert_forward_outcome"]["same_sign"] is True
                for row in rows
            ),
            "note": (
                "Expert forward outcomes are direction-adjusted descriptive observations; "
                "they are not expert trade executions."
            ),
        },
        "per_case": rows,
    }
    dump_json(output_root / "summary.json", summary)

    repo = Path(__file__).resolve().parents[1]
    script_paths = {
        "spikes/wiki_next10_postprocess.py": Path(__file__).resolve(),
        "spikes/wiki_trade_replay.py": repo / "spikes/wiki_trade_replay.py",
        "spikes/wiki_expert_outcome.py": repo / "spikes/wiki_expert_outcome.py",
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "evaluator_scripts": {name: sha256(path) for name, path in script_paths.items()},
            "run_contract": sha256(run_contract_path),
            "source_registry": sha256(source_registry),
            "analyst_outputs": {
                key: sha256(path) for key, path in sorted(inputs["analyst_outputs"].items())
            },
            "post_t": {
                key: sha256(path) for key, path in sorted(inputs["post_t"].items())
            },
            "transforms": {
                key: sha256(path) for key, path in sorted(inputs["transforms"].items())
            },
        },
        "generated": _generated_manifest(output_root),
    }
    dump_json(output_root / "manifest.json", manifest)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def verify(
    *, run_root: Path, source_registry: Path, post_t_root: Path,
    output_root: Path,
) -> None:
    if not output_root.is_dir():
        raise PostprocessError(f"verification output root does not exist: {output_root}")
    with tempfile.TemporaryDirectory(prefix="wiki-next10-verify-") as temporary:
        regenerated = Path(temporary) / "output"
        regenerated.mkdir()
        generate(
            run_root=run_root, source_registry=source_registry,
            post_t_root=post_t_root, output_root=regenerated,
        )
        expected = _tree_bytes(output_root)
        actual = _tree_bytes(regenerated)
        if expected.keys() != actual.keys():
            raise PostprocessError(
                "verification file set mismatch: "
                f"missing={sorted(actual.keys() - expected.keys())}, "
                f"extra={sorted(expected.keys() - actual.keys())}"
            )
        changed = [name for name in actual if expected[name] != actual[name]]
        if changed:
            raise PostprocessError(f"verification byte mismatch: {changed}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--post-t-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    source_registry = args.source_registry.resolve()
    post_t_root = args.post_t_root.resolve()
    output_root = args.output_root.resolve()
    try:
        if args.verify:
            verify(
                run_root=run_root, source_registry=source_registry,
                post_t_root=post_t_root, output_root=output_root,
            )
            print(json.dumps({"status": "verified", "output_root": str(output_root)}))
            return 0
        if output_root.exists():
            raise PostprocessError("output root already exists; refusing to overwrite")
        output_root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{output_root.name}-build-", dir=output_root.parent,
        ) as temporary:
            staged = Path(temporary) / "output"
            staged.mkdir()
            generate(
                run_root=run_root, source_registry=source_registry,
                post_t_root=post_t_root, output_root=staged,
            )
            staged.rename(output_root)
        print(json.dumps({"status": "complete", "output_root": str(output_root)}))
        return 0
    except PostprocessError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
