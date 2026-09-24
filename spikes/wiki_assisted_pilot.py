#!/usr/bin/env python3
"""One-case, physically isolated methodology-vs-examples Wyckoff pilot."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from jsonschema import validate as validate_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval.runtime_adapters import CodexRuntimeAdapter, RuntimeRequest


MODEL = "gpt-5.6-sol"
EFFORT = "high"
CASE_ID = "link_vol24_2020_06"
TARGET_EXTRACT = "crypto_v24_07_back-up-to-the-edge-of-the-creek_link.md"
EXPERT_PILOT_ALLOWLIST = {
    "book_p229_sign-of-strength_es-weekly-reaccumulation.md",
    "book_p231_back-up-to-the-edge-of-the-creek_6b-8h.md",
    "crypto_v28_04_back-up-to-the-edge-of-the-creek_xtz.md",
    "crypto_v29_02_back-up-to-the-edge-of-the-creek_small-cap-index.md",
    "crypto_v31_05_sign-of-strength_atom.md",
    "crypto_v34_01_flat-reaction_btc.md",
    "crypto_v51_03_back-up-to-the-edge-of-the-creek_crv.md",
    "fraser_p016_img04_back-up-to-the-edge-of-the-creek_expe.md",
    "fraser_p046_img02_last-point-of-support_djia-30m.md",
    "fraser_p060_img02_back-up-to-the-edge-of-the-creek_djia-pnf.md",
    "fraser_p102_img02_back-up-to-the-edge-of-the-creek_tsla.md",
    "fraser_p200_img04_sign-of-strength_work-daily.md",
}
ALIGNMENT_DIMENSIONS = (
    "structure",
    "phase",
    "key_events",
    "leading_scenario",
    "trigger",
    "invalidation",
    "alternative_scenario",
    "confidence",
)

ANALYST_PROMPT = """You are an isolated Wyckoff market analyst.

Your entire evidence universe is the current /workspace package. Do not use the
network, do not inspect credentials, process metadata, environment variables, or
paths outside /workspace. You may use shell commands only to inspect files under
/workspace.

Analyze input/candles.json as a frozen, anonymized OHLCV series ending at the
decision cutoff. The sequence contains no later bars. First describe observable
price/volume behavior, then assign Wyckoff labels. Review the methodology files
under knowledge/methodology. Focus on supply/demand, effort/result, Phase D,
accumulation/reaccumulation, Back Up, LPS, SOS, and scenario-contract pages; do
not exhaustively read unrelated files. If knowledge/expert_examples exists, read
its small fixed set of non-target examples and use them as analogical guidance
without copying their conclusions.

Do not infer or name the asset, exchange, calendar date, experimental arm, or
package provenance. Give one leading scenario and one credible alternative.
Trigger and invalidation levels must use the normalized price scale in the input;
use null only when no defensible numeric level exists. Return only the JSON object
required by analysis_output.schema.json, with no markdown or extra text.
"""

JUDGE_PROMPT = """You are the blind evaluator for two anonymized Wyckoff analyses.

Your entire evidence universe is the current /workspace package. Do not use the
network or inspect anything outside /workspace. Read expert_ground_truth.json and
both candidate_*.json files. You do not know which experimental arm produced a
candidate and must not guess.

The candidates use an anonymized normalized price scale, while the expert text
uses the original market price. Never compare their numeric levels directly and
never penalize a candidate for not reproducing the expert's $5.50 target. Compare
the relative structural path (backup, continuation, prior/overbought objective)
and the internal coherence of trigger/invalidation levels on the candidate scale.

Score each candidate independently on exactly the same 0-4 rubric:
- structure: match to the expert's structural read and supply/demand mechanism;
- phase: match where stated; when the expert did not state a phase, reward
  compatible restraint and penalize confident contradiction;
- key_events: semantic match to the expert event(s), allowing synonyms;
- leading_scenario: match to the expert's leading path;
- trigger: compatibility and operational clarity; when the expert did not state
  an exact trigger, do not invent one as the answer key;
- invalidation: compatibility and operational clarity under the same rule;
- alternative_scenario: credible structural alternative that does not erase the
  leading expert read;
- confidence: calibration to the expert's decisiveness and remaining ambiguity.

Use integer scores: 4 excellent, 3 materially correct with a minor gap, 2 mixed,
1 mostly wrong, 0 absent/contradictory. Do not use any future-market outcome in
these alignment scores. Return only judge_output.schema.json JSON.
"""

ANALYSIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "observations", "structure", "phase", "key_events", "leading_scenario",
        "alternative_scenario", "confidence", "uncertainties",
    ],
    "properties": {
        "observations": {"type": "array", "minItems": 3, "items": {"type": "string"}},
        "structure": {"type": "string"},
        "phase": {"type": "string"},
        "key_events": {"type": "array", "items": {"type": "string"}},
        "leading_scenario": {"$ref": "#/$defs/scenario"},
        "alternative_scenario": {"$ref": "#/$defs/scenario"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "$defs": {
        "scenario": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "direction", "thesis", "trigger_condition", "trigger_level",
                "invalidation_condition", "invalidation_level", "expected_path",
            ],
            "properties": {
                "direction": {"enum": ["up", "down", "none"]},
                "thesis": {"type": "string"},
                "trigger_condition": {"type": "string"},
                "trigger_level": {"type": ["number", "null"]},
                "invalidation_condition": {"type": "string"},
                "invalidation_level": {"type": ["number", "null"]},
                "expected_path": {"type": "string"},
            },
        }
    },
}


class LeakageError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_master_answer(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and isinstance(raw.get("cases"), list):
        items = raw["cases"]
    elif isinstance(raw, list):
        items = raw
    else:
        items = [dict(value, case_id=key) for key, value in raw.items()]
    return next(item for item in items if item["case_id"] == CASE_ID)


def leak_reasons(relative: Path, text: str) -> list[str]:
    lower_path = relative.as_posix().lower()
    lower = text.lower()
    reasons: list[str] = []
    if relative.name.lower() in {"index.md", "log.md"}:
        reasons.append("derived index/log excluded")
    markers = {
        "target case id": "link_vol24_2020_06",
        "target source": "wyckoff-crypto-report-vol-24",
        "target extract family": "crypto_v24",
        "target asset name": "chainlink",
        "target numeric objective": "$5.50",
        "target wording": "upsloping range shows that supply has been absorbed",
    }
    for label, marker in markers.items():
        if marker in lower_path or marker.lower() in lower:
            reasons.append(label)
    if re.search(r"\bLINK(?:/USD|/USDT|/BTC|USDT|USD|BTC)?\b", text):
        reasons.append("target asset ticker")
    return sorted(set(reasons))


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def copy_filtered_tree(
    source: Path,
    destination: Path,
    *,
    layer: str,
    target_words: set[str],
    exclusions: list[dict[str, Any]],
    selected_names: set[str] | None = None,
) -> int:
    count = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise LeakageError(f"symlink in source tree: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            exclusions.append({"layer": layer, "path": relative.as_posix(), "reasons": ["binary omitted"]})
            continue
        reasons = leak_reasons(relative, text)
        if layer.endswith(":expert_examples"):
            overlap = len(words(text) & target_words) / max(1, len(words(text) | target_words))
            if overlap >= 0.35:
                reasons.append(f"near-duplicate text Jaccard={overlap:.3f}")
        if selected_names is not None and relative.name not in selected_names:
            reasons.append("not selected in fixed 12-example pilot subset")
        if reasons:
            exclusions.append({"layer": layer, "path": relative.as_posix(), "reasons": sorted(set(reasons))})
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def manifest_for(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise LeakageError(f"symlink in analyst package: {path}")
        if path.is_file() and path.name != "allowlist_manifest.json":
            files.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            })
    return {"files": files, "count": len(files), "total_bytes": sum(item["bytes"] for item in files)}


def validate_package(root: Path) -> dict[str, Any]:
    allowed_top = {"input", "knowledge", "analysis_output.schema.json", "prompt.txt", "allowlist_manifest.json"}
    unexpected = sorted(item.name for item in root.iterdir() if item.name not in allowed_top)
    if unexpected:
        raise LeakageError(f"unexpected package entries: {unexpected}")
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        lower = relative.as_posix().lower()
        if path.is_symlink():
            raise LeakageError(f"symlink: {relative}")
        if any(part in {".git", "raw", "_answers"} for part in relative.parts):
            raise LeakageError(f"forbidden path: {relative}")
        if any(marker in lower for marker in ("answer", "ground_truth", "post_t", "future")):
            raise LeakageError(f"forbidden filename: {relative}")
        if path.is_file():
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                raise LeakageError(f"binary file in analyst package: {relative}")
            reasons = leak_reasons(relative, text)
            if reasons:
                raise LeakageError(f"forbidden content in {relative}: {reasons}")
    expected = json.loads((root / "allowlist_manifest.json").read_text())
    actual = manifest_for(root)
    if expected != actual:
        raise LeakageError("allowlist manifest mismatch")
    return actual


def build_packages(repo: Path, source_root: Path, artifacts: Path) -> dict[str, Any]:
    packages = artifacts / "packages"
    if packages.exists():
        shutil.rmtree(packages)
    packages.mkdir(parents=True)
    exclusions: list[dict[str, Any]] = []
    target_text = (repo / "research/expert-analyses/wiki/extracts" / TARGET_EXTRACT).read_text()
    target_words = words(target_text)
    source_candles = source_root / "data/eval/benchmark" / CASE_ID / "candles.json"
    counts: dict[str, Any] = {}
    for arm in ("arm_a", "arm_b"):
        root = packages / arm
        (root / "input").mkdir(parents=True)
        shutil.copy2(source_candles, root / "input/candles.json")
        (root / "prompt.txt").write_text(ANALYST_PROMPT)
        dump_json(root / "analysis_output.schema.json", ANALYSIS_SCHEMA)
        methodology_count = copy_filtered_tree(
            repo / "knowledge/wiki",
            root / "knowledge/methodology",
            layer=f"{arm}:methodology",
            target_words=target_words,
            exclusions=exclusions,
        )
        expert_count = 0
        if arm == "arm_b":
            expert_count = copy_filtered_tree(
                repo / "research/expert-analyses/wiki/extracts",
                root / "knowledge/expert_examples",
                layer="arm_b:expert_examples",
                target_words=target_words,
                exclusions=exclusions,
                selected_names=EXPERT_PILOT_ALLOWLIST,
            )
        manifest = manifest_for(root)
        dump_json(root / "allowlist_manifest.json", manifest)
        validate_package(root)
        counts[arm] = {
            "methodology_files": methodology_count,
            "expert_example_files": expert_count,
            "manifest": manifest,
        }
    common_a = {
        item["path"]: item["sha256"]
        for item in counts["arm_a"]["manifest"]["files"]
        if not item["path"].startswith("knowledge/expert_examples/")
    }
    common_b = {
        item["path"]: item["sha256"]
        for item in counts["arm_b"]["manifest"]["files"]
        if not item["path"].startswith("knowledge/expert_examples/")
    }
    if common_a != common_b:
        raise LeakageError("common analyst bytes differ across arms")
    dump_json(artifacts / "excluded_files.json", exclusions)
    dump_json(artifacts / "package_summary.json", counts)

    with tempfile.TemporaryDirectory(prefix="wyckoff-leak-control-") as raw:
        injected = Path(raw) / "package"
        shutil.copytree(packages / "arm_b", injected)
        forbidden = injected / "knowledge/expert_examples/forbidden_target.md"
        forbidden.write_text("ChainLink target $5.50 from wyckoff-crypto-report-vol-24")
        dump_json(injected / "allowlist_manifest.json", manifest_for(injected))
        try:
            validate_package(injected)
        except LeakageError as exc:
            leak_control = {"status": "passed", "injected": forbidden.relative_to(injected).as_posix(), "rejection": str(exc)}
        else:
            raise LeakageError("intentional leakage control was not rejected")
    dump_json(artifacts / "leakage_control.json", leak_control)
    return counts


def judge_schema(candidate_ids: list[str]) -> dict[str, Any]:
    score = {
        "type": "object",
        "additionalProperties": False,
        "required": ["score", "rationale"],
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 4},
            "rationale": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array", "minItems": 2, "maxItems": 2,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["candidate_id", "scores", "overall_comment"],
                    "properties": {
                        "candidate_id": {"enum": candidate_ids},
                        "scores": {
                            "type": "object", "additionalProperties": False,
                            "required": list(ALIGNMENT_DIMENSIONS),
                            "properties": {dimension: score for dimension in ALIGNMENT_DIMENSIONS},
                        },
                        "overall_comment": {"type": "string"},
                    },
                },
            }
        },
    }


def parse_events(stdout: str) -> tuple[dict[str, Any], dict[str, int], list[dict[str, Any]]]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    output: dict[str, Any] | None = None
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    for event in events:
        candidate_usage = event.get("usage")
        if isinstance(candidate_usage, dict):
            for key in usage:
                usage[key] = int(candidate_usage.get(key, usage[key]) or 0)
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"} and item.get("text"):
            value = item["text"]
            output = json.loads(value) if isinstance(value, str) else value
    if output is None:
        raise RuntimeError("no structured agent output")
    return output, usage, events


def validate_tool_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    forbidden = re.compile(
        r"(?:https?://|\bcurl\b|\bwget\b|\bnc\b|\bssh\b|\bgit\b|/users/|/proc/|"
        r"auth\.json|/home/codex|\.codex|printenv|\benv\b|urllib|socket|fetch\()",
        re.IGNORECASE,
    )
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))
        if "web_search" in item_type:
            raise LeakageError(f"web search tool used: {item_type}")
        if item_type == "command_execution":
            command = str(item.get("command", ""))
            if forbidden.search(command):
                raise LeakageError(f"forbidden analyst/evaluator command: {command}")
            commands.append({key: item.get(key) for key in ("command", "exit_code", "status")})
    return commands


async def preflight_adapter(repo: Path) -> CodexRuntimeAdapter:
    adapter = CodexRuntimeAdapter(
        model_map={"codex": MODEL},
        verdict_path=repo / "scripts/eval/state/codex_isolation_verdict.json",
    )
    await adapter.preflight("codex", EFFORT)
    return adapter


def run_codex(
    *, adapter: CodexRuntimeAdapter, package: Path, schema: Path, prompt: str, label: str, artifacts: Path,
) -> dict[str, Any]:
    request = RuntimeRequest(prompt, package, schema, "codex", EFFORT, 900)
    argv = adapter.build_argv(request)
    started = time.monotonic()
    process = subprocess.run(
        argv, cwd=package, input=prompt, capture_output=True, text=True, timeout=900, check=False,
    )
    duration = time.monotonic() - started
    (artifacts / "raw").mkdir(parents=True, exist_ok=True)
    (artifacts / "raw" / f"{label}.jsonl").write_text(process.stdout)
    (artifacts / "raw" / f"{label}.stderr.txt").write_text(process.stderr)
    if process.returncode:
        raise RuntimeError(f"{label} failed with exit {process.returncode}: {process.stderr[-1000:]}")
    output, usage, events = parse_events(process.stdout)
    validate_json(output, json.loads(schema.read_text()))
    commands = validate_tool_trace(events)
    dump_json(artifacts / "outputs" / f"{label}.json", output)
    meta = {"model": MODEL, "effort": EFFORT, "duration_seconds": round(duration, 3), "usage": usage, "commands": commands}
    dump_json(artifacts / "outputs" / f"{label}.meta.json", meta)
    return {"output": output, "meta": meta}


def build_judge_package(artifacts: Path, answer: dict[str, Any], results: dict[str, dict[str, Any]]) -> tuple[Path, dict[str, str]]:
    root = artifacts / "judge_package"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    seed = int(hashlib.sha256(b"wiki-assisted-pilot-blind-mapping").hexdigest()[:8], 16)
    ids = ["candidate_kestrel", "candidate_oriole"]
    arms = ["arm_a", "arm_b"]
    random.Random(seed).shuffle(arms)
    mapping = dict(zip(ids, arms, strict=True))
    for candidate_id, arm in mapping.items():
        dump_json(root / f"{candidate_id}.json", results[arm]["output"])
    hidden = {
        "ground_truth": answer["ground_truth"],
        "expert_structure": answer.get("expert_structure", "not_stated"),
        "expert_phase": answer.get("expert_phase", "not_stated"),
        "expert_event": answer.get("expert_event", "not_stated"),
        "expert_scenario": answer.get("expert_scenario", "not_stated"),
        "expert_trigger": answer.get("expert_trigger", "not_stated"),
        "expert_invalidation": answer.get("expert_invalidation", "not_stated"),
        "decisive": answer["decisive"],
    }
    dump_json(root / "expert_ground_truth.json", hidden)
    schema = judge_schema(ids)
    dump_json(root / "judge_output.schema.json", schema)
    (root / "prompt.txt").write_text(JUDGE_PROMPT)
    dump_json(artifacts / "private_arm_mapping.json", mapping)
    return root, mapping


def replay(candidate: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    scenario = candidate["leading_scenario"]
    direction = scenario["direction"]
    trigger = scenario["trigger_level"]
    invalidation = scenario["invalidation_level"]
    realized = answer["realized_direction"]
    direction_correct = direction == realized
    outcome = "unscorable"
    bars = None
    trigger_bar = None
    invalidation_bar = None
    if direction in {"up", "down"} and isinstance(trigger, (int, float)) and isinstance(invalidation, (int, float)):
        for index, candle in enumerate(answer["post_t_candles"], start=1):
            high, low = float(candle["high"]), float(candle["low"])
            invalidated = low <= invalidation if direction == "up" else high >= invalidation
            triggered = high >= trigger if direction == "up" else low <= trigger
            if invalidated and invalidation_bar is None:
                invalidation_bar = index
            if triggered and trigger_bar is None:
                trigger_bar = index
        if invalidation_bar is not None and (trigger_bar is None or invalidation_bar <= trigger_bar):
            outcome, bars = "invalidation_first", invalidation_bar
        elif trigger_bar is not None:
            outcome, bars = "trigger_first", trigger_bar
        else:
            outcome = "open"
    trigger_hit = outcome == "trigger_first"
    invalidation_respected = outcome != "invalidation_first"
    components = {
        "direction_correct": 1.0 if direction_correct else 0.0,
        "trigger_activated_before_invalidation": 1.0 if trigger_hit else 0.0,
        "invalidation_respected_until_trigger": 1.0 if invalidation_respected else 0.0,
    }
    return {
        "outcome": outcome,
        "bars_to_resolution": bars,
        "trigger_ever_activated": trigger_bar is not None,
        "trigger_first_bar": trigger_bar,
        "invalidation_ever_hit": invalidation_bar is not None,
        "invalidation_first_bar": invalidation_bar,
        "components": components,
        "realized_outcome_utility": sum(components.values()) / len(components),
    }


def score_results(
    artifacts: Path, answer: dict[str, Any], results: dict[str, dict[str, Any]], judge: dict[str, Any], mapping: dict[str, str],
) -> dict[str, Any]:
    by_id = {item["candidate_id"]: item for item in judge["candidates"]}
    if set(by_id) != set(mapping):
        raise RuntimeError("judge did not return both blinded candidate ids")
    scorecard: dict[str, Any] = {"arms": {}}
    for candidate_id, arm in mapping.items():
        semantic = by_id[candidate_id]
        scores = {dimension: semantic["scores"][dimension]["score"] for dimension in ALIGNMENT_DIMENSIONS}
        alignment = sum(scores.values()) / (4 * len(scores))
        outcome = replay(results[arm]["output"], answer)
        scorecard["arms"][arm] = {
            "blind_candidate_id": candidate_id,
            "expert_alignment": alignment,
            "alignment_scores_0_to_4": scores,
            "alignment_rationales": {dimension: semantic["scores"][dimension]["rationale"] for dimension in ALIGNMENT_DIMENSIONS},
            "judge_overall_comment": semantic["overall_comment"],
            "realized_outcome": outcome,
        }
    a = scorecard["arms"]["arm_a"]
    b = scorecard["arms"]["arm_b"]
    scorecard["delta_b_minus_a"] = {
        "expert_alignment": b["expert_alignment"] - a["expert_alignment"],
        "realized_outcome_utility": b["realized_outcome"]["realized_outcome_utility"] - a["realized_outcome"]["realized_outcome_utility"],
    }
    delta_align = scorecard["delta_b_minus_a"]["expert_alignment"]
    delta_outcome = scorecard["delta_b_minus_a"]["realized_outcome_utility"]
    if delta_align >= 0.10 and delta_outcome >= 0:
        verdict = "PROVEN"
    elif delta_align > 0 or (delta_align >= 0.10 and delta_outcome < 0):
        verdict = "CONDITIONAL"
    else:
        verdict = "DISPROVEN"
    scorecard["precommitted_verdict"] = verdict
    dump_json(artifacts / "scorecard.json", scorecard)
    return scorecard


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--judge-only", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    counts = build_packages(repo, args.source_root.resolve(), artifacts)
    if args.build_only:
        print(json.dumps({
            "status": "built",
            "counts": {
                arm: {
                    "methodology_files": data["methodology_files"],
                    "expert_example_files": data["expert_example_files"],
                    "total_files": data["manifest"]["count"],
                    "total_bytes": data["manifest"]["total_bytes"],
                }
                for arm, data in counts.items()
            },
        }, indent=2))
        return 0

    answer = load_master_answer(args.source_root / "data/eval/_answers/ground_truth_answers.json")
    angle_answer = json.loads(
        (args.source_root / "data/eval/benchmark/_answers" / f"{CASE_ID}.answer.json").read_text()
    )
    answer["post_t_candles"] = angle_answer["post_t_candles"]
    if args.judge_only:
        results = {
            arm: {
                "output": json.loads((artifacts / "outputs" / f"{arm}.json").read_text()),
                "meta": json.loads((artifacts / "outputs" / f"{arm}.meta.json").read_text()),
            }
            for arm in ("arm_a", "arm_b")
        }
        judge_root, mapping = build_judge_package(artifacts, answer, results)
        adapter = asyncio.run(preflight_adapter(repo))
        judge_result = run_codex(
            adapter=adapter,
            package=judge_root,
            schema=judge_root / "judge_output.schema.json",
            prompt=JUDGE_PROMPT,
            label="blind_judge_v2_scale_corrected",
            artifacts=artifacts,
        )
        scorecard = score_results(artifacts, answer, results, judge_result["output"], mapping)
        dump_json(artifacts / "run_summary.json", {
            "status": "complete",
            "model": MODEL,
            "effort": EFFORT,
            "duration_seconds": None,
            "packages": counts,
            "usage": {
                "arm_a": results["arm_a"]["meta"]["usage"],
                "arm_b": results["arm_b"]["meta"]["usage"],
                "blind_judge_v1": json.loads((artifacts / "outputs/blind_judge.meta.json").read_text())["usage"],
                "blind_judge_v2_scale_corrected": judge_result["meta"]["usage"],
            },
            "verdict": scorecard["precommitted_verdict"],
            "resumed_from_saved_outputs": True,
            "authoritative_judge": "blind_judge_v2_scale_corrected",
        })
        print(json.dumps({"status": "complete", "scorecard": scorecard}, indent=2))
        return 0
    if args.score_only:
        results = {
            arm: {
                "output": json.loads((artifacts / "outputs" / f"{arm}.json").read_text()),
                "meta": json.loads((artifacts / "outputs" / f"{arm}.meta.json").read_text()),
            }
            for arm in ("arm_a", "arm_b")
        }
        judge_result = {
            "output": json.loads((artifacts / "outputs/blind_judge.json").read_text()),
            "meta": json.loads((artifacts / "outputs/blind_judge.meta.json").read_text()),
        }
        mapping = json.loads((artifacts / "private_arm_mapping.json").read_text())
        scorecard = score_results(artifacts, answer, results, judge_result["output"], mapping)
        dump_json(artifacts / "run_summary.json", {
            "status": "complete",
            "model": MODEL,
            "effort": EFFORT,
            "duration_seconds": None,
            "packages": counts,
            "usage": {
                "arm_a": results["arm_a"]["meta"]["usage"],
                "arm_b": results["arm_b"]["meta"]["usage"],
                "blind_judge": judge_result["meta"]["usage"],
            },
            "verdict": scorecard["precommitted_verdict"],
            "resumed_from_saved_outputs": True,
        })
        print(json.dumps({"status": "complete", "scorecard": scorecard}, indent=2))
        return 0
    adapter = asyncio.run(preflight_adapter(repo))
    arms = ["arm_a", "arm_b"]
    random.Random(101).shuffle(arms)
    dump_json(artifacts / "run_order.json", {"order": arms, "seed": 101, "model": MODEL, "effort": EFFORT})
    results: dict[str, dict[str, Any]] = {}
    for arm in arms:
        package = artifacts / "packages" / arm
        results[arm] = run_codex(
            adapter=adapter,
            package=package,
            schema=package / "analysis_output.schema.json",
            prompt=ANALYST_PROMPT,
            label=arm,
            artifacts=artifacts,
        )

    judge_root, mapping = build_judge_package(artifacts, answer, results)
    judge_result = run_codex(
        adapter=adapter,
        package=judge_root,
        schema=judge_root / "judge_output.schema.json",
        prompt=JUDGE_PROMPT,
        label="blind_judge",
        artifacts=artifacts,
    )
    scorecard = score_results(artifacts, answer, results, judge_result["output"], mapping)
    dump_json(artifacts / "run_summary.json", {
        "status": "complete",
        "model": MODEL,
        "effort": EFFORT,
        "duration_seconds": round(time.monotonic() - started, 3),
        "packages": counts,
        "usage": {
            "arm_a": results["arm_a"]["meta"]["usage"],
            "arm_b": results["arm_b"]["meta"]["usage"],
            "blind_judge": judge_result["meta"]["usage"],
        },
        "verdict": scorecard["precommitted_verdict"],
    })
    print(json.dumps({"status": "complete", "scorecard": scorecard}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
