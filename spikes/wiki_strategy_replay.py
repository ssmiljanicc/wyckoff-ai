#!/usr/bin/env python3
"""Replay frozen Wyckoff strategy plans against private post-T candles.

This process is deliberately downstream of every semantic/model decision.  It
accepts a hash-verified frozen plan bundle plus private transforms and post-T
candles, then delegates execution mechanics to ``wiki_trade_replay``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spikes.wiki_trade_replay import evaluate_trade


SCHEMA_VERSION = "wiki_strategy_replay.v1"
FROZEN_BUNDLE_SCHEMA = "frozen_strategy_plans.v1"
FROZEN_MANIFEST_SCHEMA = "frozen_strategy_manifest.v1"
STRATEGY_IDS = (
    "phase_c_shake_direct",
    "phase_c_test",
    "phase_d_break_test",
    "phase_e_continuation",
)
ASSESSMENT_STATUSES = {"eligible", "ineligible", "insufficient_evidence"}
SAFE_COMPONENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


class StrategyReplayError(RuntimeError):
    """Raised when a frozen or private replay input violates the contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StrategyReplayError(f"cannot load JSON {path}: {exc}") from exc


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _safe_component(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(char not in SAFE_COMPONENT_CHARS for char in value)
        or value in {".", ".."}
    ):
        raise StrategyReplayError(
            f"{field} must be a non-empty filesystem-safe identifier"
        )
    return value


def _plan_namespace(case_id: str) -> str:
    """Return the opaque directory name owned by the frozen-plan producer."""
    return hashlib.sha256(case_id.encode()).hexdigest()[:16]


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _manifest_file_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise StrategyReplayError("frozen manifest files must be a non-empty array")
    paths: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise StrategyReplayError(
                f"frozen manifest files[{index}] must contain path, sha256, bytes"
            )
        path = row["path"]
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or path == "frozen_manifest.json"
        ):
            raise StrategyReplayError(f"unsafe frozen manifest path: {path!r}")
        if not isinstance(row["sha256"], str) or len(row["sha256"]) != 64:
            raise StrategyReplayError(f"invalid frozen hash for {path}")
        if (
            not isinstance(row["bytes"], int)
            or isinstance(row["bytes"], bool)
            or row["bytes"] < 0
        ):
            raise StrategyReplayError(f"invalid frozen byte count for {path}")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise StrategyReplayError("frozen manifest file paths must be unique and sorted")
    return rows


def _verify_frozen_manifest(plans_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not plans_root.is_dir() or plans_root.is_symlink():
        raise StrategyReplayError("plans root must be a real directory")
    manifest_path = plans_root / "frozen_manifest.json"
    bundle_path = plans_root / "frozen_plans.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise StrategyReplayError("missing real frozen_manifest.json")
    if not bundle_path.is_file() or bundle_path.is_symlink():
        raise StrategyReplayError("missing real frozen_plans.json")
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise StrategyReplayError("frozen manifest must be an object")
    if manifest.get("schema_version") != FROZEN_MANIFEST_SCHEMA:
        raise StrategyReplayError("unsupported frozen manifest schema")
    if manifest.get("bundle_schema_version") != FROZEN_BUNDLE_SCHEMA:
        raise StrategyReplayError("frozen manifest bundle schema mismatch")

    rows = _manifest_file_rows(manifest)
    declared = {row["path"]: row for row in rows}
    actual: dict[str, Path] = {}
    for path in sorted(plans_root.rglob("*")):
        if path == manifest_path:
            continue
        if path.is_symlink():
            raise StrategyReplayError(f"symlink forbidden in frozen plans: {path}")
        if path.is_file():
            actual[path.relative_to(plans_root).as_posix()] = path
    if set(actual) != set(declared):
        missing = sorted(set(declared) - set(actual))
        extra = sorted(set(actual) - set(declared))
        raise StrategyReplayError(
            f"frozen plan file set mismatch; missing={missing}, extra={extra}"
        )
    for relative, path in actual.items():
        row = declared[relative]
        if path.stat().st_size != row["bytes"] or _sha256(path) != row["sha256"]:
            raise StrategyReplayError(f"frozen plan hash mismatch: {relative}")

    fingerprint_payload = {
        "builder_script_sha256": manifest.get("builder_script_sha256"),
        "assessment_schema_sha256": manifest.get("assessment_schema_sha256"),
        "rule_bundle_sha256": manifest.get("rule_bundle_sha256"),
        "inputs": manifest.get("inputs"),
        "files": manifest.get("files"),
    }
    if manifest.get("content_fingerprint") != _canonical_sha256(fingerprint_payload):
        raise StrategyReplayError("frozen manifest content_fingerprint mismatch")
    bundle = _load_json(bundle_path)
    return manifest, bundle


def _validate_frozen_bundle(
    manifest: dict[str, Any], bundle: Any
) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        raise StrategyReplayError("frozen plans bundle must be an object")
    if bundle.get("schema_version") != FROZEN_BUNDLE_SCHEMA:
        raise StrategyReplayError("unsupported frozen plans schema")
    if bundle.get("strategy_ids") != list(STRATEGY_IDS):
        raise StrategyReplayError("frozen plans must declare four canonical strategies")
    cases = bundle.get("cases")
    if not isinstance(cases, list) or not cases:
        raise StrategyReplayError("frozen plans cases must be a non-empty array")

    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    expected_inputs: list[dict[str, Any]] = []
    expected_plan_paths = {"frozen_plans.json"}
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise StrategyReplayError(f"cases[{index}] must be an object")
        case_id = _safe_component(case.get("case_id"), "case_id")
        arm = _safe_component(case.get("arm"), "arm")
        key = (case_id, arm)
        if key in seen:
            raise StrategyReplayError(f"duplicate frozen case/arm: {case_id}/{arm}")
        seen.add(key)
        for hash_field in (
            "analyst_input_sha256",
            "candles_input_sha256",
            "packaged_candles_sha256",
            "sidecar_sha256",
            "result_output_sha256",
            "result_meta_sha256",
        ):
            if not isinstance(case.get(hash_field), str) or len(case[hash_field]) != 64:
                raise StrategyReplayError(
                    f"{case_id}/{arm} has invalid {hash_field}"
                )
        if case.get("result_origin") not in {
            "model_accepted", "deterministic_validation_fallback",
        }:
            raise StrategyReplayError(f"{case_id}/{arm} has invalid result_origin")
        source_failure_sha256s = case.get("source_failure_sha256s")
        if not isinstance(source_failure_sha256s, list) or any(
            not isinstance(value, str) or len(value) != 64
            for value in source_failure_sha256s
        ):
            raise StrategyReplayError(f"{case_id}/{arm} has invalid failure hashes")
        if (
            case["result_origin"] == "model_accepted" and source_failure_sha256s
        ) or (
            case["result_origin"] == "deterministic_validation_fallback"
            and len(source_failure_sha256s) < 2
        ):
            raise StrategyReplayError(f"{case_id}/{arm} has inconsistent result provenance")
        strategies = case.get("strategies")
        if not isinstance(strategies, list) or [
            item.get("strategy_id") if isinstance(item, dict) else None
            for item in strategies
        ] != list(STRATEGY_IDS):
            raise StrategyReplayError(
                f"{case_id}/{arm} must contain the four canonical strategies in order"
            )
        plan_namespace = _plan_namespace(case_id)
        for strategy in strategies:
            status = strategy.get("assessment_status")
            if status not in ASSESSMENT_STATUSES:
                raise StrategyReplayError(
                    f"{case_id}/{arm}/{strategy['strategy_id']} has invalid status"
                )
            if status == "eligible":
                if strategy.get("skip_reason") is not None:
                    raise StrategyReplayError("eligible strategy cannot have skip_reason")
                if (
                    not _number(strategy.get("reward_risk"))
                    or strategy["reward_risk"] < 3
                ):
                    raise StrategyReplayError("eligible strategy requires reward_risk >= 3")
                action = strategy.get("trade_plan", {}).get("action")
                if action not in {"enter_now", "wait_for_trigger"}:
                    raise StrategyReplayError("eligible strategy requires actionable plan")
            else:
                if not isinstance(strategy.get("skip_reason"), str):
                    raise StrategyReplayError("skipped strategy requires skip_reason")
                reward_risk = strategy.get("reward_risk")
                if strategy["skip_reason"] == "below_3r":
                    if not _number(reward_risk) or not 0 <= reward_risk < 3:
                        raise StrategyReplayError(
                            "below_3r strategy requires numeric reward_risk below 3"
                        )
                elif reward_risk is not None:
                    raise StrategyReplayError(
                        "skipped strategy cannot have reward_risk"
                    )
                if strategy.get("trade_plan", {}).get("action") != "no_trade":
                    raise StrategyReplayError("skipped strategy requires no_trade plan")
            expected_plan_paths.add(
                f"plans/{plan_namespace}/{arm}/{strategy['strategy_id']}.json"
            )
        baseline = case.get("baseline")
        if (
            not isinstance(baseline, dict)
            or baseline.get("origin") != "analyst_trade_plan"
            or not isinstance(baseline.get("trade_plan"), dict)
        ):
            raise StrategyReplayError(f"{case_id}/{arm} has invalid baseline")
        expected_plan_paths.add(f"plans/{plan_namespace}/{arm}/baseline.json")
        expected_inputs.append(
            {
                "case_id": case_id,
                "arm": arm,
                "analyst_input_sha256": case["analyst_input_sha256"],
                "candles_input_sha256": case["candles_input_sha256"],
                "packaged_candles_sha256": case["packaged_candles_sha256"],
                "sidecar_sha256": case["sidecar_sha256"],
                "result_output_sha256": case["result_output_sha256"],
                "result_meta_sha256": case["result_meta_sha256"],
                "result_origin": case["result_origin"],
                "source_failure_sha256s": case["source_failure_sha256s"],
            }
        )
        normalized.append(case)

    if manifest.get("inputs") != expected_inputs:
        raise StrategyReplayError("frozen manifest inputs do not match frozen plans")
    declared_paths = {row["path"] for row in manifest["files"]}
    if declared_paths != expected_plan_paths:
        raise StrategyReplayError("frozen manifest does not contain the exact plan file set")
    return normalized


def _private_inputs(root: Path, case_ids: set[str], label: str) -> dict[str, Path]:
    if not root.is_dir() or root.is_symlink():
        raise StrategyReplayError(f"{label} root must be a real directory")
    paths: dict[str, Path] = {}
    for path in sorted(root.iterdir()):
        if path.is_symlink():
            raise StrategyReplayError(f"symlink forbidden in {label} root: {path}")
        if not path.is_file() or path.suffix != ".json":
            raise StrategyReplayError(f"unexpected entry in {label} root: {path.name}")
        case_id = _safe_component(path.stem, f"{label} filename")
        paths[case_id] = path
    if set(paths) != case_ids:
        raise StrategyReplayError(
            f"{label} exact case set mismatch; expected={sorted(case_ids)}, "
            f"actual={sorted(paths)}"
        )
    return paths


def _metric_summary(values: Iterable[Any]) -> dict[str, Any]:
    numeric = [float(value) for value in values if _number(value)]
    if not numeric:
        return {"count": 0, "mean": None, "min": None, "max": None, "sum": None}
    return {
        "count": len(numeric),
        "mean": sum(numeric) / len(numeric),
        "min": min(numeric),
        "max": max(numeric),
        "sum": sum(numeric),
    }


def _fixed_risk_impact(replay: dict[str, Any] | None) -> float | None:
    if (
        replay is None
        or replay.get("pnl_scorable") is not True
        or not _number(replay.get("net_r"))
    ):
        return None
    return float(replay["net_r"]) * 1.0


def _aggregate(rows: list[dict[str, Any]], *, assessments: bool) -> dict[str, Any]:
    replays = [row["replay"] for row in rows if isinstance(row.get("replay"), dict)]
    entered = [replay for replay in replays if replay.get("entry_bar") is not None]
    pnl = [
        replay
        for replay in replays
        if replay.get("pnl_scorable") is True and _number(replay.get("net_r"))
    ]
    entered_pnl = [
        replay
        for replay in entered
        if replay.get("pnl_scorable") is True and _number(replay.get("net_r"))
    ]
    statuses = Counter(str(replay.get("status")) for replay in replays)
    exits = Counter(
        str(replay["exit_reason"])
        for replay in replays
        if replay.get("exit_reason") is not None
    )
    result: dict[str, Any] = {
        "total_count": len(rows),
        "actionable_count": sum(
            replay.get("action") in {"enter_now", "wait_for_trigger"}
            for replay in replays
        ),
        "triggered_count": sum(replay.get("trigger_bar") is not None for replay in replays),
        "entered_count": len(entered),
        "pnl_scorable_count": len(pnl),
        "entered_pnl_scorable_count": len(entered_pnl),
        "resolved_without_entry_count": sum(
            replay.get("status") in {"canceled_before_entry", "expired_before_entry"}
            for replay in replays
        ),
        "canceled_before_entry_count": statuses["canceled_before_entry"],
        "expired_before_entry_count": statuses["expired_before_entry"],
        "insufficient_horizon_count": sum(
            status in {
                "horizon_before_entry_expiry",
                "data_horizon_before_max_holding",
            }
            for status in statuses.elements()
        ),
        "ambiguous_count": sum(
            bool(replay.get("same_bar_ambiguity"))
            or str(replay.get("status", "")).startswith("intrabar_ambiguous")
            for replay in replays
        ),
        "status_counts": dict(sorted(statuses.items())),
        "exit_reason_counts": dict(sorted(exits.items())),
        "wins": sum(float(replay["net_r"]) > 0 for replay in pnl),
        "losses": sum(float(replay["net_r"]) < 0 for replay in pnl),
        "breakeven": sum(float(replay["net_r"]) == 0 for replay in pnl),
        "win_rate_pct": (
            sum(float(replay["net_r"]) > 0 for replay in pnl) / len(pnl) * 100
            if pnl
            else None
        ),
        "entered_wins": sum(float(replay["net_r"]) > 0 for replay in entered_pnl),
        "entered_losses": sum(float(replay["net_r"]) < 0 for replay in entered_pnl),
        "entered_breakeven": sum(
            float(replay["net_r"]) == 0 for replay in entered_pnl
        ),
        "entered_win_rate_pct": (
            sum(float(replay["net_r"]) > 0 for replay in entered_pnl)
            / len(entered_pnl)
            * 100
            if entered_pnl
            else None
        ),
        "metrics": {
            field: _metric_summary(replay.get(field) for replay in pnl)
            for field in (
                "gross_return_pct",
                "net_return_pct",
                "gross_r",
                "net_r",
                "mfe_pct",
                "mae_pct",
                "mfe_r",
                "mae_r",
                "duration_bars",
                "duration_seconds",
            )
        },
        "excursion_bounds": {
            "mfe_guaranteed_pct": _metric_summary(
                (replay.get("mfe_pct_bounds") or {}).get("guaranteed")
                for replay in pnl
            ),
            "mfe_possible_pct": _metric_summary(
                (replay.get("mfe_pct_bounds") or {}).get("possible")
                for replay in pnl
            ),
            "mae_best_case_pct": _metric_summary(
                (replay.get("mae_pct_bounds") or {}).get("best_case")
                for replay in pnl
            ),
            "mae_worst_case_pct": _metric_summary(
                (replay.get("mae_pct_bounds") or {}).get("worst_case")
                for replay in pnl
            ),
        },
        "fixed_risk_account_impact_pct": _metric_summary(
            row.get("fixed_risk_account_impact_pct") for row in rows
        ),
    }
    if assessments:
        assessment_counts = Counter(row["assessment_status"] for row in rows)
        skip_reasons = Counter(
            row["skip_reason"] for row in rows if row.get("skip_reason") is not None
        )
        result.update(
            {
                "eligible_count": assessment_counts["eligible"],
                "ineligible_count": assessment_counts["ineligible"],
                "insufficient_evidence_count": assessment_counts[
                    "insufficient_evidence"
                ],
                "skipped_count": len(rows) - assessment_counts["eligible"],
                "eligibility_coverage_pct": (
                    assessment_counts["eligible"] / len(rows) * 100 if rows else None
                ),
                "skip_reason_counts": dict(sorted(skip_reasons.items())),
            }
        )
    return result


def _strategy_result(
    case: dict[str, Any],
    strategy: dict[str, Any],
    post_t: Any,
    transform: Any,
    *,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    replay = None
    if strategy["assessment_status"] == "eligible":
        replay = evaluate_trade(
            {"trade_plan": strategy["trade_plan"]},
            post_t,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            normalization_transform=transform,
        )
        if replay.get("status") == "invalid":
            raise StrategyReplayError(
                f"evaluator rejected {case['case_id']}/{case['arm']}/"
                f"{strategy['strategy_id']}: {replay['validation_errors']}"
            )
    impact = _fixed_risk_impact(replay)
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": "strategy",
        "case_id": case["case_id"],
        "arm": case["arm"],
        "strategy_id": strategy["strategy_id"],
        "assessment_status": strategy["assessment_status"],
        "skip_reason": strategy["skip_reason"],
        "reward_risk": strategy["reward_risk"],
        "evidence": strategy.get("evidence"),
        "replay": replay,
        "fixed_risk_account_impact_pct": impact,
        "fixed_risk_policy": "1% initial account risk; independent trade; not portfolio P&L",
    }


def _baseline_result(
    case: dict[str, Any],
    post_t: Any,
    transform: Any,
    *,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    replay = evaluate_trade(
        {"trade_plan": case["baseline"]["trade_plan"]},
        post_t,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        normalization_transform=transform,
    )
    if replay.get("status") == "invalid":
        raise StrategyReplayError(
            f"evaluator rejected baseline {case['case_id']}/{case['arm']}: "
            f"{replay['validation_errors']}"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": "baseline",
        "case_id": case["case_id"],
        "arm": case["arm"],
        "origin": case["baseline"]["origin"],
        "replay": replay,
        "fixed_risk_account_impact_pct": _fixed_risk_impact(replay),
        "fixed_risk_policy": "1% initial account risk; independent trade; not portfolio P&L",
    }


def _script_path(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def _build_output(
    *,
    plans_root: Path,
    transforms_root: Path,
    post_t_root: Path,
    output_root: Path,
    fee_bps: float,
    slippage_bps: float,
) -> None:
    manifest, bundle = _verify_frozen_manifest(plans_root)
    cases = _validate_frozen_bundle(manifest, bundle)
    case_ids = {case["case_id"] for case in cases}
    transforms = _private_inputs(transforms_root, case_ids, "transforms")
    post_t = _private_inputs(post_t_root, case_ids, "post_t")

    strategy_rows: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    for case in cases:
        case_id, arm = case["case_id"], case["arm"]
        transform = _load_json(transforms[case_id])
        if not isinstance(transform, dict) or transform.get("case_id") != case_id:
            raise StrategyReplayError(f"transform case_id mismatch for {case_id}")
        if transform.get("packaged_input_sha256") != case["packaged_candles_sha256"]:
            raise StrategyReplayError(
                f"transform packaged candle hash mismatch for {case_id}"
            )
        candles = _load_json(post_t[case_id])
        for strategy in case["strategies"]:
            result = _strategy_result(
                case,
                strategy,
                candles,
                transform,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
            )
            strategy_rows.append(result)
            _dump_json(
                output_root
                / "replays"
                / case_id
                / arm
                / f"{strategy['strategy_id']}.json",
                result,
            )
        baseline = _baseline_result(
            case,
            candles,
            transform,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        baseline_rows.append(baseline)
        _dump_json(output_root / "replays" / case_id / arm / "baseline.json", baseline)

    arms = sorted({row["arm"] for row in strategy_rows})
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "case_arm_count": len(cases),
        "strategy_assessment_count": len(strategy_rows),
        "fee_bps_per_side": fee_bps,
        "slippage_bps_per_side": slippage_bps,
        "fixed_risk_policy": {
            "initial_account_risk_pct": 1.0,
            "calculation": "net_r * 1 percentage point",
            "interpretation": "independent trades; no balance chaining or equity curve",
        },
        "strategies": _aggregate(strategy_rows, assessments=True),
        "by_arm": {
            arm: _aggregate(
                [row for row in strategy_rows if row["arm"] == arm], assessments=True
            )
            for arm in arms
        },
        "by_strategy": {
            strategy_id: _aggregate(
                [
                    row
                    for row in strategy_rows
                    if row["strategy_id"] == strategy_id
                ],
                assessments=True,
            )
            for strategy_id in STRATEGY_IDS
        },
        "by_arm_strategy": {
            arm: {
                strategy_id: _aggregate(
                    [
                        row
                        for row in strategy_rows
                        if row["arm"] == arm
                        and row["strategy_id"] == strategy_id
                    ],
                    assessments=True,
                )
                for strategy_id in STRATEGY_IDS
            }
            for arm in arms
        },
        "baseline": _aggregate(baseline_rows, assessments=False),
        "baseline_by_arm": {
            arm: _aggregate(
                [row for row in baseline_rows if row["arm"] == arm],
                assessments=False,
            )
            for arm in arms
        },
    }
    _dump_json(output_root / "summary.json", summary)

    generated_files = {
        path.relative_to(output_root).as_posix(): _sha256(path)
        for path in sorted(output_root.rglob("*.json"))
        if path.name != "manifest.json"
    }
    replay_manifest = {
        "schema_version": SCHEMA_VERSION,
        "frozen_content_fingerprint": manifest["content_fingerprint"],
        "configuration": {
            "fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps,
            "initial_account_risk_pct": 1.0,
        },
        "inputs": {
            "frozen_manifest_sha256": _sha256(plans_root / "frozen_manifest.json"),
            "frozen_plan_files": {
                row["path"]: row["sha256"] for row in manifest["files"]
            },
            "transforms": {
                case_id: _sha256(path) for case_id, path in sorted(transforms.items())
            },
            "post_t": {
                case_id: _sha256(path) for case_id, path in sorted(post_t.items())
            },
            "scripts": {
                "wiki_strategy_replay.py": _sha256(Path(__file__).resolve()),
                "wiki_trade_replay.py": _sha256(_script_path("wiki_trade_replay.py")),
            },
        },
        "generated_files": generated_files,
    }
    _dump_json(output_root / "manifest.json", replay_manifest)


def generate(
    *,
    plans_root: Path,
    transforms_root: Path,
    post_t_root: Path,
    output_root: Path,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> None:
    """Generate replay artifacts without ever replacing an existing output."""
    if output_root.exists():
        raise StrategyReplayError(f"output root already exists: {output_root}")
    if not _number(fee_bps) or fee_bps < 0:
        raise StrategyReplayError("fee_bps must be a finite non-negative number")
    if not _number(slippage_bps) or slippage_bps < 0:
        raise StrategyReplayError("slippage_bps must be a finite non-negative number")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.stage-", dir=output_root.parent))
    try:
        _build_output(
            plans_root=plans_root,
            transforms_root=transforms_root,
            post_t_root=post_t_root,
            output_root=stage,
            fee_bps=float(fee_bps),
            slippage_bps=float(slippage_bps),
        )
        if output_root.exists():
            raise StrategyReplayError(f"output root appeared during build: {output_root}")
        stage.rename(output_root)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _tree_bytes(root: Path) -> dict[str, bytes]:
    if not root.is_dir() or root.is_symlink():
        raise StrategyReplayError(f"output root must be a real directory: {root}")
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StrategyReplayError(f"symlink forbidden in replay output: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def verify(
    *,
    plans_root: Path,
    transforms_root: Path,
    post_t_root: Path,
    output_root: Path,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> None:
    """Regenerate the replay and require an identical file set and bytes."""
    existing = _tree_bytes(output_root)
    with tempfile.TemporaryDirectory(prefix="wiki-strategy-replay-verify-") as tmp:
        rebuilt = Path(tmp) / "rebuilt"
        generate(
            plans_root=plans_root,
            transforms_root=transforms_root,
            post_t_root=post_t_root,
            output_root=rebuilt,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        regenerated = _tree_bytes(rebuilt)
    if existing.keys() != regenerated.keys():
        raise StrategyReplayError(
            "replay verification file set mismatch; "
            f"missing={sorted(regenerated.keys() - existing.keys())}, "
            f"extra={sorted(existing.keys() - regenerated.keys())}"
        )
    mismatched = sorted(path for path in existing if existing[path] != regenerated[path])
    if mismatched:
        raise StrategyReplayError(
            f"replay verification byte mismatch: {mismatched}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay hash-verified frozen Wyckoff plans against private post-T data"
    )
    parser.add_argument("--plans-root", required=True, type=Path)
    parser.add_argument("--transforms-root", required=True, type=Path)
    parser.add_argument("--post-t-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--verify", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    operation = verify if args.verify else generate
    try:
        operation(
            plans_root=args.plans_root,
            transforms_root=args.transforms_root,
            post_t_root=args.post_t_root,
            output_root=args.output_root,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
        )
    except StrategyReplayError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
