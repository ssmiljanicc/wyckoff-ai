#!/usr/bin/env python3
"""Build isolated pre-T strategy assessments and freeze deterministic plans.

The model-facing package contains only an anonymized analyst result, normalized
pre-cutoff candles, a frozen rule bundle, the prompt, and the output schema.
Case identity and all post-cutoff material stay outside that package.  A later
replay stage may consume only the frozen plan bundle produced here.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import validate as validate_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval.runtime_adapters import CodexRuntimeAdapter, RuntimeRequest
from spikes.wiki_assisted_batch import parse_event_stream, parse_events, validate_tool_trace
from spikes.wiki_trade_replay import _validate_plan


MODEL = "gpt-5.6-luna"
EFFORT = "xhigh"
TIMEOUT_SECONDS = 900
MAX_ATTEMPTS = 2
MAX_INFRA_FAILURES = 2
MAX_TOTAL_ATTEMPTS = MAX_ATTEMPTS + MAX_INFRA_FAILURES
ASSESSMENT_SCHEMA_VERSION = "strategy_assessment.v2"
PLAN_BUNDLE_SCHEMA_VERSION = "frozen_strategy_plans.v1"
MANIFEST_SCHEMA_VERSION = "frozen_strategy_manifest.v1"
STRATEGY_IDS = (
    "phase_c_shake_direct",
    "phase_c_test",
    "phase_d_break_test",
    "phase_e_continuation",
)
STATUSES = {"eligible", "ineligible", "insufficient_evidence"}
SKIP_REASONS = {
    "setup_absent",
    "contradictory_evidence",
    "insufficient_numeric_anchors",
    "invalid_ordering",
    "below_3r",
    "unsupported_strategy",
    "not_ready",
}
SETUPS_BY_STRATEGY = {
    "phase_c_shake_direct": {"spring_direct", "utad_direct"},
    "phase_c_test": {"spring_test", "utad_test"},
    "phase_d_break_test": {"buec_lps", "fti_lpsy"},
    "phase_e_continuation": {"phase_e_long_reaction", "phase_e_short_rally"},
}
DIRECTION_BY_SETUP = {
    "spring_direct": "long",
    "utad_direct": "short",
    "spring_test": "long",
    "utad_test": "short",
    "buec_lps": "long",
    "fti_lpsy": "short",
    "phase_e_long_reaction": "long",
    "phase_e_short_rally": "short",
}
FORBIDDEN_PATH_PARTS = {
    ".git", "answer", "expert", "judge", "ground_truth", "post_t", "future",
    "private", "provenance", "registry", "source", "raw", "log", "index",
}
FORBIDDEN_JSON_KEYS = {
    "answer_key", "asset", "case_id", "cutoff", "exchange", "expert",
    "extract_path", "image_path", "market", "post_t", "provenance", "source",
    "symbol",
}


RULE_BUNDLE: dict[str, Any] = {
    "schema_version": "wyckoff_strategy_rules.v2",
    "common": {
        "single_entry_only": True,
        "minimum_reward_risk": 3.0,
        "target_policy": "Use a real numeric target supported by the frozen analysis or an observable pre-T structural level. Never manufacture a 3R target.",
        "evidence_policy": "For analyst text, source_field must equal the first component of field_path. Copy one contiguous verbatim substring from the exact field_path; do not paraphrase or omit words. Set bar_index to null for every analyst-field citation. Use a non-null zero-based bar_index only when source_field is pre_t_bar and field_path starts with candles[index].",
        "skip_policy": "When evidence or any numeric anchor is missing or ambiguous, return insufficient_evidence. A setup that is absent, contradicted, or not ready is ineligible.",
    },
    "strategies": [
        {
            "strategy_id": "phase_c_shake_direct",
            "setups": ["spring_direct", "utad_direct"],
            "rule": "Direct Spring #3 long or direct UTAD/SOW short only when the shake is complete, price has returned through the range boundary, commitment is explicitly ready, and the stop is beyond the shake extreme.",
        },
        {
            "strategy_id": "phase_c_test",
            "setups": ["spring_test", "utad_test"],
            "rule": "Spring/Test long or UTAD/Test short only after a lower-activity confirmation test; the stop stays beyond the shake extreme.",
        },
        {
            "strategy_id": "phase_d_break_test",
            "setups": ["buec_lps", "fti_lpsy"],
            "rule": "Trade a confirmed break-and-test: BUEC/LPS long or FTI/LPSY short. A break without a completed test is not ready.",
        },
        {
            "strategy_id": "phase_e_continuation",
            "setups": ["phase_e_long_reaction", "phase_e_short_rally"],
            "rule": "Continue an already confirmed Phase E trend only on a reaction/test (long) or rally/test (short). Do not chase the initial breakout.",
        },
    ],
}

ASSESSMENT_PROMPT = """You are a physically isolated Wyckoff strategy normalizer.

Your complete evidence universe is the current /workspace package. Do not use
the network, environment, process metadata, parent paths, or anything outside
/workspace. If inspection is needed, use only ls, head, tail, and cat, without
shell chaining, redirection, substitution, or executable paths.

Read input/analysis.json, input/candles.json, and strategy_rules.json. The
candles end at decision time T and contain no future bars. The analyst JSON is
already frozen. Assess every strategy in the exact rule-bundle order. Do not
infer the asset, date, case identity, arm, or future outcome. Do not reinterpret
free prose into a numeric level: every numeric entry, stop, and target must be
directly supported by a cited analyst field or an observable pre-T bar. A target
must exist independently; never construct one merely to reach 3R.

Evidence is machine-checked. For an analyst-field citation, quote_or_fact must
be a contiguous verbatim substring copied from the resolved field_path, without
paraphrase, ellipsis, or omitted middle words, and bar_index must be null.
source_field must exactly equal the first component of field_path; for example,
uncertainties[2] requires source_field "uncertainties". Set a non-null bar_index
only when source_field is pre_t_bar; then field_path must start with
candles[that exact zero-based index]. Never attach a bar_index to an analyst
field.

An eligible assessment requires: a supported setup, explicit readiness, the
correct direction, entry action/type, positive ordered entry/stop/target,
expiry/holding horizon, and evidence roles setup/readiness/entry/stop/target.
For each eligible numeric anchor, include an evidence item whose field_path
resolves directly to the same numeric scalar, not to prose containing that
number or to a parent object. Prefer trade_plan.entry_level,
trade_plan.stop_loss, and trade_plan.take_profit when they match; scenario
trigger_level/invalidation_level or candles[index].open/high/low/close are also
valid numeric leaves. A string-valued condition is never numeric evidence.
If a matching setup may exist but a required fact or numeric anchor is missing,
return insufficient_evidence. If the setup is absent, contradicted, or not
ready, return ineligible. Every non-eligible assessment must use entry_action
"none", entry_type "none", and null entry_level, stop_loss, take_profit,
entry_expiry_bars, and max_holding_bars. The deterministic builder, not you,
applies the final 3R admission filter. Return only JSON matching
strategy_assessment.schema.json.
"""


def _evidence_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["role", "source_field", "field_path", "bar_index", "quote_or_fact"],
        "properties": {
            "role": {"type": "string", "enum": ["setup", "readiness", "entry", "stop", "target", "contradiction"]},
            "source_field": {"type": "string", "enum": [
                "observations", "structure", "phase", "key_events",
                "leading_scenario", "alternative_scenario", "confidence",
                "uncertainties", "trade_plan", "process_assessment", "pre_t_bar",
            ]},
            "field_path": {"type": "string", "minLength": 1},
            "bar_index": {"type": ["integer", "null"], "minimum": 0},
            "quote_or_fact": {"type": "string", "minLength": 1},
        },
    }


ASSESSMENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "assessments"],
    "properties": {
        "schema_version": {"type": "string", "const": ASSESSMENT_SCHEMA_VERSION},
        "assessments": {
            "type": "array", "minItems": 4, "maxItems": 4,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": [
                    "strategy_id", "status", "skip_reason", "setup", "direction",
                    "readiness", "entry_action", "entry_type", "entry_level",
                    "stop_loss", "take_profit", "entry_expiry_bars",
                    "max_holding_bars", "evidence",
                ],
                "properties": {
                    "strategy_id": {"type": "string", "enum": list(STRATEGY_IDS)},
                    "status": {"type": "string", "enum": sorted(STATUSES)},
                    "skip_reason": {"type": ["string", "null"], "enum": [None, *sorted(SKIP_REASONS)]},
                    "setup": {"type": ["string", "null"], "enum": [None, *sorted(DIRECTION_BY_SETUP)]},
                    "direction": {"type": "string", "enum": ["long", "short", "none"]},
                    "readiness": {"type": "string", "enum": ["ready", "not_ready", "uncertain"]},
                    "entry_action": {"type": "string", "enum": ["enter_now", "wait_for_trigger", "none"]},
                    "entry_type": {"type": "string", "enum": ["market", "stop", "limit", "none"]},
                    "entry_level": {"type": ["number", "null"], "exclusiveMinimum": 0},
                    "stop_loss": {"type": ["number", "null"], "exclusiveMinimum": 0},
                    "take_profit": {"type": ["number", "null"], "exclusiveMinimum": 0},
                    "entry_expiry_bars": {"type": ["integer", "null"], "minimum": 1, "maximum": 60},
                    "max_holding_bars": {"type": ["integer", "null"], "minimum": 1, "maximum": 60},
                    "evidence": {"type": "array", "items": _evidence_schema()},
                },
            },
        },
    },
}


class LeakageError(RuntimeError):
    """A model-facing package crossed the pre-T allowlist boundary."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode())


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def file_manifest(root: Path, *, ignored: set[str] | None = None) -> list[dict[str, Any]]:
    ignored = ignored or set()
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise LeakageError(f"symlink forbidden: {path}")
        if path.is_file() and path.relative_to(root).as_posix() not in ignored:
            files.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    return files


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _validate_anonymous_candles(candles: Any) -> None:
    if not isinstance(candles, list) or not candles:
        raise LeakageError("pre-T candles must be a non-empty array")
    opens: list[float] = []
    base_keys = {"open_time", "open", "high", "low", "close", "volume"}
    extended_keys = base_keys | {"is_complete", "elapsed_fraction"}
    expected_keys = set(candles[0]) if isinstance(candles[0], dict) else set()
    if expected_keys not in {frozenset(base_keys), frozenset(extended_keys)}:
        raise LeakageError("candles must use the base or extended anonymous OHLCV schema")
    for index, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise LeakageError(f"candle {index} must be an object")
        if set(candle) != expected_keys:
            raise LeakageError(
                f"candle {index} must contain exactly {sorted(expected_keys)}"
            )
        if _walk_keys(candle) & FORBIDDEN_JSON_KEYS:
            raise LeakageError(f"candle {index} contains identity/provenance fields")
        for key in ("open", "high", "low", "close", "volume"):
            value = candle.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise LeakageError(f"candle {index} has invalid {key}")
        if candle["high"] < max(candle["open"], candle["close"]) or candle["low"] > min(candle["open"], candle["close"]):
            raise LeakageError(f"candle {index} has inconsistent OHLC")
        open_time = candle.get("open_time")
        if not isinstance(open_time, (int, float)) or isinstance(open_time, bool):
            raise LeakageError(f"candle {index} lacks numeric anonymous open_time")
        opens.append(float(open_time))
        if expected_keys == extended_keys:
            is_complete = candle["is_complete"]
            elapsed_fraction = candle["elapsed_fraction"]
            if not isinstance(is_complete, bool):
                raise LeakageError(f"candle {index} has invalid is_complete")
            if (
                not isinstance(elapsed_fraction, (int, float))
                or isinstance(elapsed_fraction, bool)
                or not math.isfinite(elapsed_fraction)
                or not 0 < elapsed_fraction <= 1
            ):
                raise LeakageError(f"candle {index} has invalid elapsed_fraction")
            if is_complete != (elapsed_fraction == 1):
                raise LeakageError(f"candle {index} has inconsistent completion fields")
    if opens[0] != 0 or any(right <= left for left, right in zip(opens, opens[1:])):
        raise LeakageError("candles must use increasing anonymous open_time starting at zero")
    if len(opens) > 2:
        intervals = {round(right - left, 9) for left, right in zip(opens, opens[1:])}
        if len(intervals) != 1:
            raise LeakageError("anonymous candle intervals must be uniform")


def _forbidden_marker_hits(root: Path, markers: list[str]) -> list[str]:
    hits: list[str] = []
    lowered = [marker.strip().lower() for marker in markers if marker.strip()]
    for path in root.rglob("*"):
        if path.is_symlink():
            raise LeakageError(f"symlink forbidden: {path}")
        relative = path.relative_to(root)
        if any(part.lower() in FORBIDDEN_PATH_PARTS for part in relative.parts):
            hits.append(f"forbidden path class:{relative.as_posix()}")
        if not path.is_file() or path.name == "allowlist_manifest.json":
            continue
        if path.suffix in {".json", ".txt", ".md"}:
            text = path.read_text(errors="replace").lower()
            for marker in lowered:
                if marker in text or marker in relative.as_posix().lower():
                    hits.append(f"marker {marker!r} in {relative.as_posix()}")
    return sorted(set(hits))


def validate_package(root: Path, *, forbidden_markers: list[str] | None = None) -> dict[str, Any]:
    allowed = {
        "input", "strategy_rules.json", "prompt.txt",
        "strategy_assessment.schema.json", "allowlist_manifest.json",
    }
    if not root.is_dir():
        raise LeakageError(f"package root does not exist: {root}")
    actual_top = {path.name for path in root.iterdir()}
    if actual_top != allowed:
        raise LeakageError(f"package top-level allowlist mismatch: {sorted(actual_top ^ allowed)}")
    input_files = {path.name for path in (root / "input").iterdir()}
    if input_files != {"analysis.json", "candles.json"}:
        raise LeakageError(f"input allowlist mismatch: {sorted(input_files)}")
    analysis = json.loads((root / "input/analysis.json").read_text())
    if _walk_keys(analysis) & FORBIDDEN_JSON_KEYS:
        raise LeakageError("analysis contains identity, provenance, expert, or future fields")
    _validate_anonymous_candles(json.loads((root / "input/candles.json").read_text()))
    if json.loads((root / "strategy_rules.json").read_text()) != RULE_BUNDLE:
        raise LeakageError("strategy rule bundle mismatch")
    if json.loads((root / "strategy_assessment.schema.json").read_text()) != ASSESSMENT_SCHEMA:
        raise LeakageError("assessment schema mismatch")
    if (root / "prompt.txt").read_text() != ASSESSMENT_PROMPT:
        raise LeakageError("assessment prompt mismatch")
    hits = _forbidden_marker_hits(root, forbidden_markers or [])
    if hits:
        raise LeakageError("; ".join(hits))
    expected = json.loads((root / "allowlist_manifest.json").read_text())
    actual_files = file_manifest(root, ignored={"allowlist_manifest.json"})
    actual = {
        "schema_version": "strategy_package_manifest.v1",
        "files": actual_files,
        "content_fingerprint": sha256_json(actual_files),
    }
    if expected != actual:
        raise LeakageError("allowlist manifest mismatch")
    return actual


def _stage_directory(target: Path) -> tuple[Path, Path]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    return temp, target


def _promote_exact(staged: Path, target: Path) -> None:
    if target.exists():
        staged_files = file_manifest(staged)
        target_files = file_manifest(target)
        shutil.rmtree(staged)
        if staged_files != target_files:
            raise RuntimeError(f"refusing to overwrite different frozen tree: {target}")
        return
    staged.replace(target)


def build_package(
    *, analyst_output: Path, pre_t_candles: Path, destination: Path,
    forbidden_markers: list[str] | None = None,
) -> dict[str, Any]:
    analysis = json.loads(analyst_output.read_text())
    candles = json.loads(pre_t_candles.read_text())
    if _walk_keys(analysis) & FORBIDDEN_JSON_KEYS:
        raise LeakageError("analyst output contains forbidden identity/provenance fields")
    _validate_anonymous_candles(candles)
    staged, target = _stage_directory(destination)
    try:
        dump_json(staged / "input/analysis.json", analysis)
        dump_json(staged / "input/candles.json", candles)
        dump_json(staged / "strategy_rules.json", RULE_BUNDLE)
        dump_json(staged / "strategy_assessment.schema.json", ASSESSMENT_SCHEMA)
        (staged / "prompt.txt").write_text(ASSESSMENT_PROMPT)
        files = file_manifest(staged)
        manifest = {
            "schema_version": "strategy_package_manifest.v1",
            "files": files,
            "content_fingerprint": sha256_json(files),
        }
        dump_json(staged / "allowlist_manifest.json", manifest)
        validate_package(staged, forbidden_markers=forbidden_markers)
        _promote_exact(staged, target)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    validate_package(target, forbidden_markers=forbidden_markers)
    return {
        "package_sha256": json.loads((target / "allowlist_manifest.json").read_text())["content_fingerprint"],
        "analyst_input_sha256": sha256_file(target / "input/analysis.json"),
        "candles_input_sha256": sha256_file(target / "input/candles.json"),
    }


def _resolve_evidence(
    evidence: dict[str, Any], analyst_output: dict[str, Any],
    pre_t_candles: list[dict[str, Any]],
) -> Any:
    source = evidence["source_field"]
    path = evidence["field_path"]
    expected_root = "candles" if source == "pre_t_bar" else source
    token_pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")
    tokens: list[str | int] = []
    position = 0
    while position < len(path):
        if path[position] == ".":
            position += 1
        match = token_pattern.match(path, position)
        if match is None:
            raise ValueError(f"invalid evidence field_path: {path}")
        tokens.append(match.group(1) if match.group(1) is not None else int(match.group(2)))
        position = match.end()
    if not tokens or tokens[0] != expected_root:
        raise ValueError(f"evidence path {path} must start with {expected_root}")
    value: Any = pre_t_candles if source == "pre_t_bar" else analyst_output
    walk_tokens = tokens[1:] if source == "pre_t_bar" else tokens
    try:
        for token in walk_tokens:
            value = value[token]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"evidence path does not resolve: {path}") from exc
    if source == "pre_t_bar":
        bar_tokens = [token for token in tokens if isinstance(token, int)]
        if not bar_tokens or evidence["bar_index"] != bar_tokens[0]:
            raise ValueError(f"pre_t_bar evidence index mismatch: {path}")
    quote = evidence["quote_or_fact"].strip().lower()
    if isinstance(value, str):
        if quote not in value.lower():
            raise ValueError(f"evidence quote is not present at {path}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            quoted_number = float(evidence["quote_or_fact"].strip())
        except ValueError as exc:
            raise ValueError(f"numeric evidence fact is invalid at {path}") from exc
        if not math.isclose(quoted_number, float(value), rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"numeric evidence fact does not match {path}")
    else:
        raise ValueError(f"evidence path must resolve to a string or number: {path}")
    return value


def validate_assessment(
    output: dict[str, Any], *, analyst_output: dict[str, Any] | None = None,
    pre_t_candles: list[dict[str, Any]] | None = None,
) -> None:
    if (analyst_output is None) != (pre_t_candles is None):
        raise ValueError("analyst_output and pre_t_candles must be supplied together")
    validate_json(output, ASSESSMENT_SCHEMA)
    assessments = output["assessments"]
    ids = [item["strategy_id"] for item in assessments]
    if ids != list(STRATEGY_IDS):
        raise ValueError(f"assessments must use exact strategy order: {list(STRATEGY_IDS)}")
    for item in assessments:
        strategy_id = item["strategy_id"]
        status = item["status"]
        setup = item["setup"]
        direction = item["direction"]
        evidence = item["evidence"]
        for evidence_item in evidence:
            is_bar = evidence_item["source_field"] == "pre_t_bar"
            if is_bar != (evidence_item["bar_index"] is not None):
                raise ValueError(f"{strategy_id}: bar_index is required only for pre_t_bar evidence")
        resolved_evidence: list[tuple[dict[str, Any], Any]] = []
        if analyst_output is not None and pre_t_candles is not None:
            resolved_evidence = [
                (evidence_item, _resolve_evidence(evidence_item, analyst_output, pre_t_candles))
                for evidence_item in evidence
            ]
        if setup is not None and setup not in SETUPS_BY_STRATEGY[strategy_id]:
            raise ValueError(f"{strategy_id}: unsupported setup {setup}")
        if setup is not None and direction not in {DIRECTION_BY_SETUP[setup], "none"}:
            raise ValueError(f"{strategy_id}: setup/direction contradiction")
        if status == "eligible":
            if item["skip_reason"] is not None:
                raise ValueError(f"{strategy_id}: eligible assessment cannot have skip_reason")
            if setup is None or direction != DIRECTION_BY_SETUP[setup] or item["readiness"] != "ready":
                raise ValueError(f"{strategy_id}: eligible assessment lacks supported ready setup")
            if item["entry_action"] not in {"enter_now", "wait_for_trigger"}:
                raise ValueError(f"{strategy_id}: eligible assessment lacks actionable entry")
            if item["entry_action"] == "enter_now" and item["entry_type"] != "market":
                raise ValueError(f"{strategy_id}: enter_now requires market")
            if item["entry_action"] == "wait_for_trigger" and item["entry_type"] not in {"stop", "limit"}:
                raise ValueError(f"{strategy_id}: wait_for_trigger requires stop or limit")
            if item["entry_action"] == "enter_now" and item["entry_expiry_bars"] is not None:
                raise ValueError(f"{strategy_id}: enter_now requires null entry expiry")
            if item["entry_action"] == "wait_for_trigger" and item["entry_expiry_bars"] is None:
                raise ValueError(f"{strategy_id}: wait_for_trigger requires entry expiry")
            values = [item[key] for key in ("entry_level", "stop_loss", "take_profit")]
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in values):
                raise ValueError(f"{strategy_id}: eligible assessment requires all numeric anchors")
            if item["max_holding_bars"] is None:
                raise ValueError(f"{strategy_id}: eligible assessment requires holding horizon")
            entry, stop, target = values
            ordered = stop < entry < target if direction == "long" else target < entry < stop
            if not ordered:
                raise ValueError(f"{strategy_id}: unordered eligible levels")
            roles = {entry["role"] for entry in evidence}
            missing = {"setup", "readiness", "entry", "stop", "target"} - roles
            if missing:
                raise ValueError(f"{strategy_id}: missing evidence roles {sorted(missing)}")
            if resolved_evidence:
                for role, anchor in (
                    ("entry", item["entry_level"]),
                    ("stop", item["stop_loss"]),
                    ("target", item["take_profit"]),
                ):
                    supported = any(
                        evidence_item["role"] == role
                        and isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isclose(float(value), float(anchor), rel_tol=0, abs_tol=1e-9)
                        for evidence_item, value in resolved_evidence
                    )
                    if not supported:
                        raise ValueError(
                            f"{strategy_id}: {role} anchor is not directly supported by cited numeric evidence"
                        )
        else:
            if item["skip_reason"] is None:
                raise ValueError(f"{strategy_id}: non-eligible assessment requires skip_reason")
            if item["entry_action"] != "none" or item["entry_type"] != "none":
                raise ValueError(f"{strategy_id}: skipped assessment must not be actionable")
            if status == "insufficient_evidence" and item["skip_reason"] != "insufficient_numeric_anchors":
                raise ValueError(f"{strategy_id}: insufficient evidence needs numeric-anchor reason")
            if status == "ineligible" and item["skip_reason"] not in {
                "setup_absent", "contradictory_evidence", "not_ready", "unsupported_strategy",
            }:
                raise ValueError(f"{strategy_id}: invalid model-stage ineligible reason")


def _no_trade(reason: str) -> dict[str, Any]:
    return {
        "action": "no_trade", "direction": "none", "entry_type": "none",
        "entry_level": None, "stop_loss": None, "take_profit": None,
        "entry_expiry_bars": None, "max_holding_bars": None,
        "cancellation_condition": reason,
    }


def _reward_risk(item: dict[str, Any]) -> float:
    entry = float(item["entry_level"])
    stop = float(item["stop_loss"])
    target = float(item["take_profit"])
    return abs(target - entry) / abs(entry - stop)


def build_strategy_plan(item: dict[str, Any]) -> dict[str, Any]:
    strategy_id = item.get("strategy_id")
    if strategy_id not in STRATEGY_IDS:
        return {
            "strategy_id": str(strategy_id), "assessment_status": "ineligible",
            "skip_reason": "unsupported_strategy", "reward_risk": None,
            "evidence": item.get("evidence", []),
            "trade_plan": _no_trade("unsupported_strategy"),
        }
    status = item.get("status")
    skip_reason = item.get("skip_reason")
    if status != "eligible":
        reason = skip_reason if skip_reason in SKIP_REASONS else "unsupported_strategy"
        return {
            "strategy_id": strategy_id, "assessment_status": status,
            "skip_reason": reason, "reward_risk": None,
            "evidence": item.get("evidence", []), "trade_plan": _no_trade(reason),
        }
    plan = {
        "action": item["entry_action"], "direction": item["direction"],
        "entry_type": item["entry_type"], "entry_level": item["entry_level"],
        "stop_loss": item["stop_loss"], "take_profit": item["take_profit"],
        "entry_expiry_bars": item["entry_expiry_bars"],
        "max_holding_bars": item["max_holding_bars"],
        "cancellation_condition": (
            f"Cancel if stop_loss {item['stop_loss']} is touched before entry"
            + (f" or after {item['entry_expiry_bars']} bars." if item["entry_expiry_bars"] is not None else ".")
        ),
    }
    errors = _validate_plan(plan)
    if errors:
        return {
            "strategy_id": strategy_id, "assessment_status": "ineligible",
            "skip_reason": "invalid_ordering", "reward_risk": None,
            "evidence": item["evidence"], "trade_plan": _no_trade("invalid_ordering"),
        }
    reward_risk = _reward_risk(item)
    if reward_risk < 3.0:
        return {
            "strategy_id": strategy_id, "assessment_status": "ineligible",
            "skip_reason": "below_3r", "reward_risk": reward_risk,
            "evidence": item["evidence"], "trade_plan": _no_trade("below_3r"),
        }
    return {
        "strategy_id": strategy_id, "assessment_status": "eligible",
        "skip_reason": None, "reward_risk": reward_risk,
        "evidence": item["evidence"], "trade_plan": plan,
    }


def freeze_case_record(
    *, case_id: str, arm: str, analyst_output: dict[str, Any],
    pre_t_candles: list[dict[str, Any]], sidecar: dict[str, Any],
    packaged_candles_sha256: str, result_output_sha256: str,
    result_meta_sha256: str, result_origin: str = "model_accepted",
    source_failure_sha256s: list[str] | None = None,
) -> dict[str, Any]:
    validate_assessment(
        sidecar, analyst_output=analyst_output, pre_t_candles=pre_t_candles,
    )
    baseline = analyst_output.get("trade_plan")
    if not isinstance(baseline, dict) or _validate_plan(baseline):
        raise ValueError("modern analyst output requires a valid baseline trade_plan")
    return {
        "case_id": case_id,
        "arm": arm,
        "analyst_input_sha256": sha256_json(analyst_output),
        "candles_input_sha256": sha256_json(pre_t_candles),
        "packaged_candles_sha256": packaged_candles_sha256,
        "sidecar_sha256": sha256_json(sidecar),
        "result_output_sha256": result_output_sha256,
        "result_meta_sha256": result_meta_sha256,
        "result_origin": result_origin,
        "source_failure_sha256s": source_failure_sha256s or [],
        "strategies": [build_strategy_plan(item) for item in sidecar["assessments"]],
        "baseline": {"origin": "analyst_trade_plan", "trade_plan": baseline},
    }


def manifest_content_fingerprint(manifest: dict[str, Any]) -> str:
    payload = {
        key: manifest[key]
        for key in (
            "builder_script_sha256", "assessment_schema_sha256",
            "rule_bundle_sha256", "inputs", "files",
        )
    }
    return sha256_json(payload)


def _plan_file_path(record: dict[str, Any], strategy_id: str) -> Path:
    safe_case = hashlib.sha256(record["case_id"].encode()).hexdigest()[:16]
    return Path("plans") / safe_case / record["arm"] / f"{strategy_id}.json"


def freeze_plan_bundle(records: list[dict[str, Any]], destination: Path) -> dict[str, Any]:
    keys = [(record["case_id"], record["arm"]) for record in records]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate case_id/arm in frozen plans")
    records = sorted(records, key=lambda item: (item["case_id"], item["arm"]))
    for record in records:
        if [item["strategy_id"] for item in record["strategies"]] != list(STRATEGY_IDS):
            raise ValueError(f"{record['case_id']}/{record['arm']} lacks exact strategy set")
    staged, target = _stage_directory(destination)
    try:
        bundle = {
            "schema_version": PLAN_BUNDLE_SCHEMA_VERSION,
            "strategy_ids": list(STRATEGY_IDS),
            "cases": records,
        }
        dump_json(staged / "frozen_plans.json", bundle)
        for record in records:
            for strategy in record["strategies"]:
                dump_json(staged / _plan_file_path(record, strategy["strategy_id"]), strategy)
            dump_json(staged / _plan_file_path(record, "baseline"), record["baseline"])
        files = file_manifest(staged)
        inputs = [
            {key: record[key] for key in (
                "case_id", "arm", "analyst_input_sha256", "candles_input_sha256",
                "packaged_candles_sha256", "sidecar_sha256",
                "result_output_sha256", "result_meta_sha256",
                "result_origin", "source_failure_sha256s",
            )}
            for record in records
        ]
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "bundle_schema_version": PLAN_BUNDLE_SCHEMA_VERSION,
            "builder_script_sha256": sha256_file(Path(__file__)),
            "assessment_schema_sha256": sha256_json(ASSESSMENT_SCHEMA),
            "rule_bundle_sha256": sha256_json(RULE_BUNDLE),
            "inputs": inputs,
            "files": files,
        }
        manifest["content_fingerprint"] = manifest_content_fingerprint(manifest)
        dump_json(staged / "frozen_manifest.json", manifest)
        verify_frozen_bundle(staged)
        _promote_exact(staged, target)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return verify_frozen_bundle(target)


def verify_frozen_bundle(root: Path) -> dict[str, Any]:
    manifest_path = root / "frozen_manifest.json"
    bundle_path = root / "frozen_plans.json"
    if not manifest_path.is_file() or not bundle_path.is_file():
        raise RuntimeError("frozen bundle requires manifest and aggregate plans")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("unsupported frozen manifest schema")
    if manifest.get("bundle_schema_version") != PLAN_BUNDLE_SCHEMA_VERSION:
        raise RuntimeError("unsupported frozen plan schema")
    expected_code_hashes = {
        "builder_script_sha256": sha256_file(Path(__file__)),
        "assessment_schema_sha256": sha256_json(ASSESSMENT_SCHEMA),
        "rule_bundle_sha256": sha256_json(RULE_BUNDLE),
    }
    for key, value in expected_code_hashes.items():
        if manifest.get(key) != value:
            raise RuntimeError(f"frozen manifest {key} mismatch")
    if manifest.get("content_fingerprint") != manifest_content_fingerprint(manifest):
        raise RuntimeError("frozen manifest content fingerprint mismatch")
    actual = file_manifest(root, ignored={"frozen_manifest.json"})
    if actual != manifest.get("files"):
        raise RuntimeError("frozen bundle file manifest mismatch")
    bundle = json.loads(bundle_path.read_text())
    if bundle.get("schema_version") != PLAN_BUNDLE_SCHEMA_VERSION:
        raise RuntimeError("aggregate frozen plan schema mismatch")
    if bundle.get("strategy_ids") != list(STRATEGY_IDS):
        raise RuntimeError("aggregate strategy set/order mismatch")
    cases = bundle.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("aggregate cases must be an array")
    if [(item["case_id"], item["arm"]) for item in cases] != sorted(
        (item["case_id"], item["arm"]) for item in cases
    ):
        raise RuntimeError("aggregate cases are not canonically ordered")
    if len({(item["case_id"], item["arm"]) for item in cases}) != len(cases):
        raise RuntimeError("duplicate aggregate case/arm")
    expected_inputs = []
    for record in cases:
        if [entry["strategy_id"] for entry in record["strategies"]] != list(STRATEGY_IDS):
            raise RuntimeError("case lacks exact strategy set/order")
        if record.get("baseline", {}).get("origin") != "analyst_trade_plan":
            raise RuntimeError("case lacks analyst baseline")
        if _validate_plan(record["baseline"].get("trade_plan")):
            raise RuntimeError("invalid analyst baseline")
        expected_inputs.append({key: record[key] for key in (
            "case_id", "arm", "analyst_input_sha256", "candles_input_sha256",
            "packaged_candles_sha256", "sidecar_sha256",
            "result_output_sha256", "result_meta_sha256",
            "result_origin", "source_failure_sha256s",
        )})
        for strategy in record["strategies"]:
            if _validate_plan(strategy.get("trade_plan")):
                raise RuntimeError("invalid frozen strategy trade plan")
            path = root / _plan_file_path(record, strategy["strategy_id"])
            if json.loads(path.read_text()) != strategy:
                raise RuntimeError(f"per-strategy plan differs from aggregate: {path}")
        baseline_path = root / _plan_file_path(record, "baseline")
        if json.loads(baseline_path.read_text()) != record["baseline"]:
            raise RuntimeError(f"baseline differs from aggregate: {baseline_path}")
    if manifest.get("inputs") != expected_inputs:
        raise RuntimeError("frozen manifest inputs differ from aggregate")
    return manifest


def verify_from_artifacts(artifacts: Path, frozen_root: Path) -> dict[str, Any]:
    verified = verify_frozen_bundle(frozen_root)
    with tempfile.TemporaryDirectory(prefix="wiki-strategy-verify-") as raw_temp:
        rebuilt = Path(raw_temp) / "rebuilt"
        freeze_from_artifacts(artifacts, rebuilt)
        if file_manifest(rebuilt) != file_manifest(frozen_root):
            raise RuntimeError("frozen plans are not byte-identical to regenerated artifacts")
    return verified


def _run_process(argv: list[str], *, cwd: Path, prompt: str) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(prompt, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(exc.cmd, exc.timeout, output=stdout, stderr=stderr) from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _accepted_ledger_record(meta: dict[str, Any]) -> dict[str, Any]:
    return {**meta, "accepted": True}


def _is_infrastructure_failure(error: str) -> bool:
    return error.startswith("TimeoutExpired:") or error.startswith(
        "RuntimeError: Codex exit"
    )


def _conservative_fallback_sidecar() -> dict[str, Any]:
    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "assessments": [
            {
                "strategy_id": strategy_id,
                "status": "insufficient_evidence",
                "skip_reason": "insufficient_numeric_anchors",
                "setup": None,
                "direction": "none",
                "readiness": "uncertain",
                "entry_action": "none",
                "entry_type": "none",
                "entry_level": None,
                "stop_loss": None,
                "take_profit": None,
                "entry_expiry_bars": None,
                "max_holding_bars": None,
                "evidence": [],
            }
            for strategy_id in STRATEGY_IDS
        ],
    }


def _ensure_accepted_ledger(ledger_path: Path, meta: dict[str, Any]) -> None:
    expected = _accepted_ledger_record(meta)
    existing = (
        [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        if ledger_path.is_file() else []
    )
    matches = sum(row == expected for row in existing)
    if matches > 1:
        raise RuntimeError("accepted strategy attempt is duplicated in ledger")
    if matches == 0:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a") as handle:
            handle.write(canonical_json(expected) + "\n")


def _promote_result(
    *, result_dir: Path, output: dict[str, Any], meta: dict[str, Any],
) -> None:
    staged, target = _stage_directory(result_dir)
    try:
        dump_json(staged / "output.json", output)
        dump_json(staged / "meta.json", meta)
        _promote_exact(staged, target)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise


def _validate_accepted_attempt_trace(
    *, attempt_root: Path, output: dict[str, Any], meta: dict[str, Any],
) -> None:
    raw_path = attempt_root / "raw.jsonl"
    stderr_path = attempt_root / "stderr.txt"
    if not raw_path.is_file() or not stderr_path.is_file():
        raise RuntimeError(f"accepted attempt trace missing: {attempt_root}")
    raw = raw_path.read_text()
    stderr = stderr_path.read_text()
    if sha256_bytes(raw.encode()) != meta.get("stdout_sha256"):
        raise RuntimeError(f"accepted attempt stdout hash mismatch: {attempt_root}")
    if sha256_bytes(stderr.encode()) != meta.get("stderr_sha256"):
        raise RuntimeError(f"accepted attempt stderr hash mismatch: {attempt_root}")
    events, usage = parse_event_stream(raw)
    validate_tool_trace(events)
    if parse_events(events) != output:
        raise RuntimeError(f"accepted attempt raw output mismatch: {attempt_root}")
    if usage != meta.get("usage"):
        raise RuntimeError(f"accepted attempt raw usage mismatch: {attempt_root}")


def run_package(
    *, adapter: CodexRuntimeAdapter, package: Path, result_dir: Path,
    run_id: str, resume: bool, forbidden_markers: list[str] | None = None,
) -> dict[str, Any]:
    validate_package(package, forbidden_markers=forbidden_markers)
    package_manifest = json.loads((package / "allowlist_manifest.json").read_text())
    contract = {
        "run_id": run_id,
        "stage": "strategy_assessment",
        "requested_model": MODEL,
        "resolved_model": adapter.model_map.get(MODEL, MODEL),
        "effort": EFFORT,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "package_fingerprint": package_manifest["content_fingerprint"],
        "prompt_sha256": sha256_bytes(ASSESSMENT_PROMPT.encode()),
        "schema_sha256": sha256_json(ASSESSMENT_SCHEMA),
        "rule_bundle_sha256": sha256_json(RULE_BUNDLE),
    }
    verdict_path = getattr(adapter, "verdict_path", None)
    if isinstance(verdict_path, Path) and verdict_path.is_file():
        verdict = json.loads(verdict_path.read_text())
        identity = verdict.get("execution_identity", {})
        contract.update({
            "runtime_image_id": identity.get("image_id"),
            "runtime_repo_digest": identity.get("repo_digest", ""),
            "runtime_cli_version": identity.get("cli_version"),
            "runtime_profile_fingerprint": verdict.get("profile_fingerprint"),
        })
    if result_dir.exists():
        if not resume:
            raise RuntimeError(f"result already exists; use resume: {result_dir}")
        output = json.loads((result_dir / "output.json").read_text())
        meta = json.loads((result_dir / "meta.json").read_text())
        if any(meta.get(key) != value for key, value in contract.items()):
            raise RuntimeError("saved strategy assessment contract mismatch")
        validate_assessment(
            output,
            analyst_output=json.loads((package / "input/analysis.json").read_text()),
            pre_t_candles=json.loads((package / "input/candles.json").read_text()),
        )
        _ensure_accepted_ledger(result_dir.parent / "attempt_ledger.jsonl", meta)
        return {"output": output, "meta": meta, "resumed": True}
    request = RuntimeRequest(
        ASSESSMENT_PROMPT, package, package / "strategy_assessment.schema.json",
        MODEL, EFFORT, TIMEOUT_SECONDS,
    )
    errors: list[str] = []
    attempts_root = result_dir.parent / f"{result_dir.name}.attempts"
    existing_attempts = sorted(attempts_root.glob("attempt_*")) if attempts_root.exists() else []
    expected_names = [f"attempt_{number:02d}" for number in range(1, len(existing_attempts) + 1)]
    if [path.name for path in existing_attempts] != expected_names:
        raise RuntimeError("saved strategy attempts are not sequential")
    if existing_attempts and not resume:
        raise RuntimeError(f"attempts already exist; use resume: {attempts_root}")
    semantic_failures = 0
    infrastructure_failures = 0
    for path in existing_attempts:
        failure_path = path / "failure.json"
        parsed_path = path / "parsed_output.json"
        attempt_meta_path = path / "meta.json"
        if parsed_path.is_file() and attempt_meta_path.is_file():
            recovered_output = json.loads(parsed_path.read_text())
            recovered_meta = json.loads(attempt_meta_path.read_text())
            if any(recovered_meta.get(key) != value for key, value in contract.items()):
                raise RuntimeError("saved accepted strategy attempt contract mismatch")
            validate_assessment(
                recovered_output,
                analyst_output=json.loads((package / "input/analysis.json").read_text()),
                pre_t_candles=json.loads((package / "input/candles.json").read_text()),
            )
            _validate_accepted_attempt_trace(
                attempt_root=path, output=recovered_output, meta=recovered_meta,
            )
            _ensure_accepted_ledger(
                result_dir.parent / "attempt_ledger.jsonl", recovered_meta,
            )
            _promote_result(
                result_dir=result_dir, output=recovered_output, meta=recovered_meta,
            )
            return {"output": recovered_output, "meta": recovered_meta, "resumed": True}
        if failure_path.is_file():
            failure = json.loads(failure_path.read_text())
            if any(failure.get(key) != value for key, value in contract.items()):
                raise RuntimeError("saved strategy attempt contract mismatch")
            error = str(failure.get("error", "prior failed attempt"))
            errors.append(error)
            if _is_infrastructure_failure(error):
                infrastructure_failures += 1
            else:
                semantic_failures += 1
        else:
            raise RuntimeError(f"partial strategy attempt requires reconciliation: {path}")
    next_attempt = len(existing_attempts) + 1
    if semantic_failures >= MAX_ATTEMPTS:
        return {
            "output": _conservative_fallback_sidecar(),
            "meta": {"origin": "deterministic_validation_fallback", "errors": errors},
            "resumed": True,
        }
    if infrastructure_failures >= MAX_INFRA_FAILURES:
        raise RuntimeError(
            f"strategy assessment infrastructure retry budget exhausted: {errors}"
        )
    for attempt in range(next_attempt, MAX_TOTAL_ATTEMPTS + 1):
        attempt_dir = attempts_root / f"attempt_{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=False)
        started_at = utc_now()
        started = time.monotonic()
        raw_stdout = ""
        raw_stderr = ""
        usage: dict[str, int] | None = None
        try:
            process = _run_process(adapter.build_argv(request), cwd=package, prompt=ASSESSMENT_PROMPT)
            duration = round(time.monotonic() - started, 3)
            raw_stdout, raw_stderr = process.stdout, process.stderr
            (attempt_dir / "raw.jsonl").write_text(raw_stdout)
            (attempt_dir / "stderr.txt").write_text(raw_stderr)
            events, usage = parse_event_stream(raw_stdout)
            if process.returncode:
                raise RuntimeError(f"Codex exit {process.returncode}: {raw_stderr[-1200:]}")
            output = parse_events(events)
            validate_tool_trace(events)
            validate_assessment(
                output,
                analyst_output=json.loads((package / "input/analysis.json").read_text()),
                pre_t_candles=json.loads((package / "input/candles.json").read_text()),
            )
            if usage is None:
                raise RuntimeError("successful response omitted token usage")
            meta = {
                **contract,
                "attempt": attempt,
                "started_at": started_at,
                "duration_seconds": duration,
                "usage": usage,
                "stdout_sha256": sha256_bytes(raw_stdout.encode()),
                "stderr_sha256": sha256_bytes(raw_stderr.encode()),
            }
            dump_json(attempt_dir / "parsed_output.json", output)
            dump_json(attempt_dir / "meta.json", meta)
            _ensure_accepted_ledger(result_dir.parent / "attempt_ledger.jsonl", meta)
            _promote_result(result_dir=result_dir, output=output, meta=meta)
            return {"output": output, "meta": meta, "resumed": False}
        except Exception as exc:
            duration = round(time.monotonic() - started, 3)
            if isinstance(exc, subprocess.TimeoutExpired):
                raw_stdout = (
                    exc.stdout.decode(errors="replace")
                    if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                )
                raw_stderr = (
                    exc.stderr.decode(errors="replace")
                    if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                )
                _, usage = parse_event_stream(raw_stdout)
            (attempt_dir / "raw.jsonl").write_text(raw_stdout)
            (attempt_dir / "stderr.txt").write_text(raw_stderr)
            failure = {
                **contract, "attempt": attempt, "started_at": started_at,
                "duration_seconds": duration, "accepted": False,
                "error": f"{type(exc).__name__}: {exc}",
                "usage": usage,
                "usage_status": "partial" if usage is not None else "unavailable",
                "stdout_sha256": sha256_bytes(raw_stdout.encode()),
                "stderr_sha256": sha256_bytes(raw_stderr.encode()),
            }
            dump_json(attempt_dir / "failure.json", failure)
            with (result_dir.parent / "attempt_ledger.jsonl").open("a") as handle:
                handle.write(canonical_json(failure) + "\n")
            errors.append(failure["error"])
            if _is_infrastructure_failure(failure["error"]):
                infrastructure_failures += 1
            else:
                semantic_failures += 1
            if (
                semantic_failures >= MAX_ATTEMPTS
                or infrastructure_failures >= MAX_INFRA_FAILURES
            ):
                break
    if semantic_failures >= MAX_ATTEMPTS:
        return {
            "output": _conservative_fallback_sidecar(),
            "meta": {"origin": "deterministic_validation_fallback", "errors": errors},
            "resumed": False,
        }
    raise RuntimeError(f"strategy assessment failed after retries: {' | '.join(errors)}")


async def preflight(repo: Path) -> CodexRuntimeAdapter:
    adapter = CodexRuntimeAdapter(
        model_map={MODEL: MODEL},
        verdict_path=repo / "scripts/eval/state/codex_isolation_verdict.json",
    )
    await adapter.preflight(MODEL, EFFORT)
    return adapter


def load_registry(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("registry requires a non-empty cases array")
    keys = [(item.get("case_id"), item.get("arm")) for item in cases]
    if len(set(keys)) != len(keys) or any(not all(key) for key in keys):
        raise ValueError("registry case_id/arm pairs must be unique and non-empty")
    return value


def build_from_registry(registry_path: Path, artifacts: Path) -> dict[str, Any]:
    registry = load_registry(registry_path)
    private_index = []
    for item in sorted(registry["cases"], key=lambda entry: (entry["case_id"], entry["arm"])):
        package_id = sha256_bytes(f"{item['case_id']}\0{item['arm']}".encode())[:20]
        summary = build_package(
            analyst_output=Path(item["analyst_output"]),
            pre_t_candles=Path(item["pre_t_candles"]),
            destination=artifacts / "packages" / package_id,
            forbidden_markers=[item["case_id"], *item.get("forbidden_markers", [])],
        )
        private_index.append({
            "package_id": package_id, "case_id": item["case_id"], "arm": item["arm"],
            "analyst_output": str(Path(item["analyst_output"]).resolve()),
            "pre_t_candles": str(Path(item["pre_t_candles"]).resolve()),
            "forbidden_markers": [item["case_id"], *item.get("forbidden_markers", [])],
            **summary,
        })
    index = {"schema_version": "strategy_package_index.v1", "packages": private_index}
    dump_json(artifacts / "_private/package_index.json", index)
    return index


def verify_packages(artifacts: Path) -> None:
    index = json.loads((artifacts / "_private/package_index.json").read_text())
    for item in index["packages"]:
        manifest = validate_package(
            artifacts / "packages" / item["package_id"],
            forbidden_markers=item["forbidden_markers"],
        )
        if manifest["content_fingerprint"] != item["package_sha256"]:
            raise LeakageError(f"package index hash mismatch: {item['package_id']}")


def _validated_result_binding(
    *, package: Path, package_index_item: dict[str, Any], result_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    output_path = result_root / "output.json"
    meta_path = result_root / "meta.json"
    expected = {
        "stage": "strategy_assessment",
        "requested_model": MODEL,
        "resolved_model": MODEL,
        "effort": EFFORT,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "package_fingerprint": package_index_item["package_sha256"],
        "prompt_sha256": sha256_bytes(ASSESSMENT_PROMPT.encode()),
        "schema_sha256": sha256_json(ASSESSMENT_SCHEMA),
        "rule_bundle_sha256": sha256_json(RULE_BUNDLE),
    }
    packaged_candles = package / "input/candles.json"
    if sha256_file(packaged_candles) != package_index_item["candles_input_sha256"]:
        raise RuntimeError(f"packaged candle hash mismatch: {package}")
    if not output_path.is_file() or not meta_path.is_file():
        attempts_root = result_root.parent / f"{result_root.name}.attempts"
        failures = []
        ledger_path = result_root.parent / "attempt_ledger.jsonl"
        if not ledger_path.is_file():
            raise RuntimeError(f"accepted result requires output and meta: {result_root}")
        ledger = [
            json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()
        ]
        for failure_path in sorted(attempts_root.glob("attempt_*/failure.json")):
            failure = json.loads(failure_path.read_text())
            if any(failure.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"fallback attempt contract mismatch: {failure_path}")
            if sum(row == failure for row in ledger) != 1:
                raise RuntimeError(f"fallback attempt is not bound in ledger: {failure_path}")
            attempt_root = failure_path.parent
            raw_path, stderr_path = attempt_root / "raw.jsonl", attempt_root / "stderr.txt"
            if not raw_path.is_file() or not stderr_path.is_file():
                raise RuntimeError(f"fallback attempt trace missing: {attempt_root}")
            if sha256_file(raw_path) != failure.get("stdout_sha256"):
                raise RuntimeError(f"fallback stdout hash mismatch: {attempt_root}")
            if sha256_file(stderr_path) != failure.get("stderr_sha256"):
                raise RuntimeError(f"fallback stderr hash mismatch: {attempt_root}")
            if not _is_infrastructure_failure(str(failure.get("error", ""))):
                failures.append(failure_path)
        if len(failures) < MAX_ATTEMPTS:
            raise RuntimeError(f"accepted result requires output and meta: {result_root}")
        output = _conservative_fallback_sidecar()
        source_hashes = [sha256_file(path) for path in failures]
        fallback_meta = {
            "origin": "deterministic_validation_fallback",
            "source_failure_sha256s": source_hashes,
        }
        return output, {
            "packaged_candles_sha256": sha256_file(packaged_candles),
            "result_output_sha256": sha256_json(output),
            "result_meta_sha256": sha256_json(fallback_meta),
            "result_origin": fallback_meta["origin"],
            "source_failure_sha256s": source_hashes,
        }
    output = json.loads(output_path.read_text())
    meta = json.loads(meta_path.read_text())
    if any(meta.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"accepted result contract mismatch: {result_root}")
    if not isinstance(meta.get("run_id"), str) or not meta["run_id"]:
        raise RuntimeError(f"accepted result lacks run_id: {result_root}")
    attempt = meta.get("attempt")
    if not isinstance(attempt, int) or not 1 <= attempt <= MAX_TOTAL_ATTEMPTS:
        raise RuntimeError(f"accepted result has invalid attempt: {result_root}")
    usage = meta.get("usage")
    if not isinstance(usage, dict) or any(
        not isinstance(usage.get(key), int) or usage[key] < 0
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    ):
        raise RuntimeError(f"accepted result lacks valid usage: {result_root}")
    attempt_root = result_root.parent / f"{result_root.name}.attempts" / f"attempt_{attempt:02d}"
    parsed_path = attempt_root / "parsed_output.json"
    attempt_meta_path = attempt_root / "meta.json"
    if not parsed_path.is_file() or not attempt_meta_path.is_file():
        raise RuntimeError(f"accepted attempt artifacts missing: {attempt_root}")
    if sha256_file(parsed_path) != sha256_file(output_path):
        raise RuntimeError(f"accepted parsed output mismatch: {result_root}")
    if json.loads(attempt_meta_path.read_text()) != meta:
        raise RuntimeError(f"accepted attempt meta mismatch: {result_root}")
    _validate_accepted_attempt_trace(
        attempt_root=attempt_root, output=output, meta=meta,
    )
    ledger_path = result_root.parent / "attempt_ledger.jsonl"
    accepted_record = {**meta, "accepted": True}
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
    if sum(row == accepted_record for row in ledger) != 1:
        raise RuntimeError(f"accepted result is not bound exactly once in ledger: {result_root}")
    return output, {
        "packaged_candles_sha256": sha256_file(packaged_candles),
        "result_output_sha256": sha256_file(output_path),
        "result_meta_sha256": sha256_file(meta_path),
        "result_origin": "model_accepted",
        "source_failure_sha256s": [],
    }


def freeze_from_artifacts(artifacts: Path, destination: Path) -> dict[str, Any]:
    verify_packages(artifacts)
    index = json.loads((artifacts / "_private/package_index.json").read_text())
    records = []
    for item in index["packages"]:
        package = artifacts / "packages" / item["package_id"]
        result_root = artifacts / "results" / item["package_id"]
        sidecar, binding = _validated_result_binding(
            package=package, package_index_item=item, result_root=result_root,
        )
        records.append(freeze_case_record(
            case_id=item["case_id"], arm=item["arm"],
            analyst_output=json.loads((package / "input/analysis.json").read_text()),
            pre_t_candles=json.loads((package / "input/candles.json").read_text()),
            sidecar=sidecar,
            **binding,
        ))
    return freeze_plan_bundle(records, destination)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--registry", type=Path, required=True)
    build.add_argument("--artifacts", type=Path, required=True)
    for name in ("run", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--repo", type=Path, required=True)
        command.add_argument("--artifacts", type=Path, required=True)
        command.add_argument("--run-id", required=True)
    verify_packages_parser = sub.add_parser("verify-packages")
    verify_packages_parser.add_argument("--artifacts", type=Path, required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--artifacts", type=Path, required=True)
    freeze.add_argument("--destination", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--frozen-root", type=Path, required=True)
    verify.add_argument("--artifacts", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        print(json.dumps(build_from_registry(args.registry, args.artifacts), sort_keys=True))
    elif args.command == "verify-packages":
        verify_packages(args.artifacts)
        print("packages verified")
    elif args.command in {"run", "resume"}:
        verify_packages(args.artifacts)
        adapter = asyncio.run(preflight(args.repo))
        index = json.loads((args.artifacts / "_private/package_index.json").read_text())
        for item in index["packages"]:
            run_package(
                adapter=adapter,
                package=args.artifacts / "packages" / item["package_id"],
                result_dir=args.artifacts / "results" / item["package_id"],
                run_id=args.run_id,
                resume=args.command == "resume",
                forbidden_markers=item["forbidden_markers"],
            )
        print("strategy assessments complete")
    elif args.command == "freeze":
        manifest = freeze_from_artifacts(args.artifacts, args.destination)
        print(json.dumps(manifest, sort_keys=True))
    else:
        manifest = (
            verify_from_artifacts(args.artifacts, args.frozen_root)
            if args.artifacts is not None else verify_frozen_bundle(args.frozen_root)
        )
        print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
