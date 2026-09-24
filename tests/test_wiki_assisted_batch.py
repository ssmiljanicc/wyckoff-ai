from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spikes import wiki_assisted_batch as batch


REPO = Path(__file__).resolve().parents[1]


def _source_registry() -> dict:
    candles = [
        {"open_time": 0, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 10.0},
        {"open_time": 1, "open": 1.0, "high": 1.2, "low": 0.95, "close": 1.1, "volume": 12.0},
    ]
    encoded = json.dumps(candles, indent=2, sort_keys=True).encode()
    cases = []
    for index in range(10):
        case_id = f"fixture_case_{index:02d}"
        cases.append({
            "case_id": case_id,
            "extract_path": f"research/expert-analyses/wiki/extracts/{case_id}.md",
            "source": {"path": f"raw/fixture/source-{index}.md"},
            "market": {"asset": f"FIX{index}/USDT", "symbol": f"FIX{index}USDT", "timeframe": "4h", "cutoff": "2020-03-20T00:00:00Z"},
            "candles": candles,
            "ohlcv_validation": {"input_sha256": hashlib.sha256(encoded).hexdigest(), "pre_t_count": 2},
            "verbatim_ground_truth": "Fixture says the market is in a trading range.",
            "expert_claims": [{"claim_id": f"{case_id}.c01", "category": "structure", "text": "The market is in a trading range."}],
            "expert_labels": {name: ("trading range" if name == "structure" else None) for name in batch.ALIGNMENT_DIMENSIONS},
            "applicable_alignment_dimensions": ["structure"],
            "exclusion_family": {"same_source_extracts": [], "derived_wiki_pages": [], "derived_indices": [], "near_duplicates": []},
        })
    return {"status": "frozen", "frozen": True, "validated": True, "validation_status": "passed", "cases": cases, "fixed_treatment_overlap_check": {"status": "passed"}}


def test_build_uses_only_27_book_summaries_six_temporal_examples_and_metadata(tmp_path: Path) -> None:
    registry = batch.evaluation_registry_v2(_source_registry(), "source-sha")
    summary = batch.build_packages(REPO, REPO, registry, tmp_path)

    treatment = json.loads((tmp_path / "treatment_corpus.json").read_text())
    assert treatment["count"] == 6
    assert treatment["selected"] == list(batch.FROZEN_TREATMENT_SHA256)
    assert treatment["sha256_by_file"] == batch.FROZEN_TREATMENT_SHA256
    leakage = json.loads((tmp_path / "leakage_control.json").read_text())
    assert leakage["status"] == "passed"
    assert leakage["canary_count"] == leakage["expected_canary_count"] == 10
    assert {test["case_id"] for test in leakage["tests"]} == {
        case["case_id"] for case in _source_registry()["cases"]
    }
    assert all(test["status"] == "passed" for test in leakage["tests"])
    for case_id, arms in summary.items():
        for arm in ("arm_a", "arm_b"):
            root = tmp_path / "packages" / case_id / arm
            theory = {path.name for path in (root / "knowledge/methodology").iterdir()}
            assert theory == set(batch.THEORY_BOOK_ALLOWLIST)
            metadata = json.loads((root / "input/metadata.json").read_text())
            assert metadata == {
                "timeframe": "4h", "bar_count": 2,
                "bar_duration": 14_400_000, "bar_duration_unit": "milliseconds",
                "final_bar_complete": True, "final_bar_elapsed_fraction": 1.0,
            }
            assert not ({"asset", "symbol", "date", "cutoff", "source"} & set(metadata))
            packaged = json.loads((root / "input/candles.json").read_text())
            assert [item["open_time"] for item in packaged] == [0, 14_400_000]
            assert packaged[0]["close"] == 100
            assert sorted(item["volume"] for item in packaged) == pytest.approx([10 / 11 * 100, 12 / 11 * 100])
            assert __import__("statistics").median(item["volume"] for item in packaged) == pytest.approx(100)
            assert arms[arm]["source_candles_sha256"] != arms[arm]["packaged_candles_sha256"]
            assert batch.sha256(root / "input/candles.json") == arms[arm]["packaged_candles_sha256"]
            assert not list(root.rglob("*transform*"))
        assert arms["arm_a"]["expert_example_files"] == 0
        assert arms["arm_b"]["expert_example_files"] == 6
        transform = json.loads((tmp_path / "_private/package_transforms" / f"{case_id}.json").read_text())
        assert transform["price_reference"] == 1.0
        assert transform["price_multiplier"] == 100
        # The same private multiplier preserves continuity from the final pre-T
        # close into a hypothetical first post-T close on the source scale.
        assert packaged[-1]["close"] == pytest.approx(1.1 * transform["price_multiplier"])
        assert 1.2 * transform["price_multiplier"] == pytest.approx(120)


def test_v2_excludes_pnf_and_raw_target_from_primary_denominator() -> None:
    raw = _source_registry()
    raw["cases"][0]["case_id"] = "btc_vol43_2020_11"
    raw["cases"][0]["expert_claims"] = [{
        "claim_id": "btc_vol43_2020_11.c02", "category": "leading_scenario",
        "text": "The formation suggests upside continuation, with PnF room to $18,000.",
    }]
    value = batch.evaluation_registry_v2(raw, "source-sha")
    case = next(item for item in value["cases"] if item["case_id"] == "btc_vol43_2020_11")
    scored_text = " ".join(item["text"] for item in case["expert_claims"])
    assert "PnF" not in scored_text
    assert "$18,000" not in scored_text
    excluded = [item for item in case["expert_claim_applicability"] if item["status"] == "na"]
    assert any("point_and_figure" in (item["capability_reason"] or "") for item in excluded)
    assert case["primary_claim_denominator"] == 4 * len(case["expert_claims"])


def test_v2_prefers_registry_capability_fragments_over_legacy_override() -> None:
    raw = _source_registry()
    claim = raw["cases"][0]["expert_claims"][0]
    claim["capability_fragments"] = [
        {"status": "applicable", "text": "Observable range."},
        {
            "status": "na",
            "text": "The exact calendar event anchors the range.",
            "capability_reason": "calendar_identity_absent",
        },
    ]
    value = batch.evaluation_registry_v2(raw, "source-sha")
    case = value["cases"][0]
    assert case["expert_claims"] == [{
        "claim_id": "fixture_case_00.c01.f01",
        "source_claim_id": "fixture_case_00.c01",
        "category": "structure",
        "text": "Observable range.",
    }]
    assert case["expert_claim_applicability"][1]["status"] == "na"
    assert case["expert_claim_applicability"][1]["capability_reason"] == "calendar_identity_absent"


@pytest.mark.parametrize("fragment, message", [
    ({"status": "unknown", "text": "Claim."}, "invalid capability fragment status"),
    ({"status": "applicable", "text": ""}, "empty capability fragment text"),
    ({"status": "na", "text": "Unsupported."}, "requires capability_reason"),
])
def test_v2_rejects_invalid_registry_capability_fragments(fragment: dict, message: str) -> None:
    raw = _source_registry()
    raw["cases"][0]["expert_claims"][0]["capability_fragments"] = [fragment]
    with pytest.raises(RuntimeError, match=message):
        batch.evaluation_registry_v2(raw, "source-sha")


def test_one_hour_timeframe_is_supported() -> None:
    assert batch.BAR_DURATION_MS["1h"] == 3_600_000


def test_build_exposes_only_anonymous_partial_bar_metadata(tmp_path: Path) -> None:
    raw = _source_registry()
    for case in raw["cases"]:
        case["market"]["final_bar_complete"] = False
        case["market"]["final_bar_elapsed_fraction"] = 0.375
    registry = batch.evaluation_registry_v2(raw, "source-sha")
    batch.build_packages(REPO, REPO, registry, tmp_path)
    metadata = json.loads((
        tmp_path / "packages/fixture_case_00/arm_a/input/metadata.json"
    ).read_text())
    assert metadata["final_bar_complete"] is False
    assert metadata["final_bar_elapsed_fraction"] == 0.375
    assert not ({"asset", "symbol", "date", "cutoff", "source"} & set(metadata))


def test_resolve_candles_rejects_path_outside_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    outside = tmp_path / "outside.json"
    batch.dump_json(outside, [])
    case = {"case_id": "escape", "input_candles_path": str(outside)}
    with pytest.raises(batch.LeakageError, match="escapes source_root"):
        batch.resolve_candles(case, source_root, tmp_path / "artifacts")


def test_resolve_candles_accepts_file_inside_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    candles_path = source_root / "inputs/candles.json"
    candles = [{"close": 1}]
    batch.dump_json(candles_path, candles)
    case = {"case_id": "inside", "input_candles_path": "inputs/candles.json"}
    resolved, loaded, digest = batch.resolve_candles(
        case, source_root, tmp_path / "artifacts",
    )
    assert resolved == str(candles_path.resolve())
    assert loaded == candles
    assert digest == batch.sha256(candles_path)


def test_judge_package_contains_frozen_process_rubric(tmp_path: Path) -> None:
    case = batch.evaluation_registry_v2(_source_registry(), "source-sha")["cases"][0]
    candidate = {"trade_plan": {"action": "no_trade"}}
    root, _, _ = batch.build_judge_package(case, tmp_path, {"arm_a": {"output": candidate}, "arm_b": {"output": candidate}})
    rubric = json.loads((root / "process_rubric.json").read_text())
    assert rubric["status"] == "frozen"
    assert rubric["documented_procedure"]["five_step"]
    assert rubric["documented_procedure"]["three_laws"] == ["supply_and_demand", "cause_and_effect", "effort_vs_result"]
    assert rubric["anchors"]["na"].startswith("Input capability")
    assert set(rubric["dimension_definitions"]) == set(batch.PROCESS_DIMENSIONS)
    assert "single-instrument" in rubric["dimension_definitions"]["market_context"]["definition"]
    assert "not proof" in rubric["dimension_definitions"]["target_reward_risk"]["evidence_bar"]
    assert "not an official school grading rubric" in rubric["warning"]


def test_no_trade_process_applicability_does_not_penalize_missing_execution_levels() -> None:
    case = _source_registry()["cases"][0]
    applicability = batch.process_applicability(case, "no_trade")
    assert applicability["trading_area_readiness"] is True
    assert applicability["confidence_uncertainty"] is True
    assert applicability["trigger"] is False
    assert applicability["invalidation_stop"] is False
    assert applicability["target_reward_risk"] is False


def test_resume_requires_exact_contract(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "payload.txt").write_text("same")
    schema = tmp_path / "schema.json"
    batch.dump_json(schema, {"type": "object", "additionalProperties": False, "properties": {}})
    batch.dump_json(tmp_path / "treatment_corpus.json", {"selected": []})
    verdict = tmp_path / "verdict.json"
    batch.dump_json(verdict, {"execution_identity": {"image_id": "img", "repo_digest": "repo", "cli_version": "cli"}, "profile_fingerprint": "profile"})

    class Adapter:
        verdict_path = verdict

    result = tmp_path / "result"
    result.mkdir()
    batch.dump_json(result / "output.json", {})
    meta = batch.call_contract(adapter=Adapter(), package=package, schema=schema, prompt="prompt", artifacts=tmp_path, run_id="run")
    batch.dump_json(result / "meta.json", meta)
    assert batch.load_saved_result(result, package, schema, False, Adapter(), "prompt", tmp_path, "run")
    with pytest.raises(RuntimeError, match="execution-contract mismatch"):
        batch.load_saved_result(result, package, schema, False, Adapter(), "changed", tmp_path, "run")


def test_stage_model_and_effort_change_stable_run_namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verdict = tmp_path / "verdict.json"
    batch.dump_json(verdict, {"execution_identity": {"image_id": "img", "repo_digest": "repo", "cli_version": "cli"}, "profile_fingerprint": "profile"})
    batch.dump_json(tmp_path / "package_summary.json", {"packages": "same"})
    batch.dump_json(tmp_path / "treatment_corpus.json", {"treatment": "same"})
    batch.dump_json(tmp_path / "rubric_spec.json", {"rubric": "same"})
    batch.dump_json(
        tmp_path / "evaluation_registry_v2.json",
        batch.evaluation_registry_v2(_source_registry(), "source-sha"),
    )

    class Adapter:
        verdict_path = verdict

        def __init__(self, model: str):
            self.model_map = {model: model}

    monkeypatch.setattr(batch, "TIMEOUT_SECONDS", 900)
    monkeypatch.setattr(batch, "MAX_ATTEMPTS", 2)
    sol = Adapter("gpt-5.6-sol")
    luna = Adapter("gpt-6-luna")
    baseline, baseline_spec = batch.stable_run_id(sol, tmp_path, "registry")
    analyst_model_changed, _ = batch.stable_run_id(
        luna, tmp_path, "registry", analyst_model="gpt-6-luna",
        judge_adapter=sol,
    )
    analyst_effort_changed, _ = batch.stable_run_id(
        sol, tmp_path, "registry", analyst_effort="xhigh", judge_adapter=sol,
    )
    judge_model_changed, changed_spec = batch.stable_run_id(
        sol, tmp_path, "registry", judge_adapter=luna, judge_model="gpt-6-luna",
    )
    judge_effort_changed, _ = batch.stable_run_id(
        sol, tmp_path, "registry", judge_adapter=sol, judge_effort="xhigh",
    )
    batch.dump_json(tmp_path / "rubric_spec.json", {"rubric": "changed"})
    rubric_changed, _ = batch.stable_run_id(sol, tmp_path, "registry")
    batch.dump_json(tmp_path / "rubric_spec.json", {"rubric": "same"})
    evaluation_registry = json.loads((tmp_path / "evaluation_registry_v2.json").read_text())
    evaluation_registry["cases"][0]["expert_claims"].append({
        "claim_id": "fixture_case_00.extra", "category": "phase", "text": "Extra claim.",
    })
    batch.dump_json(tmp_path / "evaluation_registry_v2.json", evaluation_registry)
    judge_schema_changed, _ = batch.stable_run_id(sol, tmp_path, "registry")
    assert len({
        baseline, analyst_model_changed, analyst_effort_changed,
        judge_model_changed, judge_effort_changed, rubric_changed,
        judge_schema_changed,
    }) == 7
    assert baseline_spec["stages"]["analyst"] == baseline_spec["stages"]["judge"]
    assert baseline_spec["stages"]["analyst"] == {
        "requested_model": "gpt-5.6-sol", "resolved_model": "gpt-5.6-sol",
        "effort": "high", "runtime_image_id": "img", "runtime_repo_digest": "repo",
        "runtime_cli_version": "cli", "runtime_profile_fingerprint": "profile",
    }
    assert changed_spec["stages"]["judge"]["resolved_model"] == "gpt-6-luna"


@pytest.mark.parametrize("model", ["../gpt-6-luna", "gpt 6 luna", "", "x" * 129])
def test_runtime_model_must_be_a_bounded_path_safe_token(model: str) -> None:
    with pytest.raises(RuntimeError, match="path-safe model token"):
        batch.validate_runtime_choice(model, "high", "analyst")


def test_runtime_effort_must_be_allowlisted() -> None:
    with pytest.raises(RuntimeError, match="must be one of"):
        batch.validate_runtime_choice("gpt-6-luna", "ultra", "analyst")


def test_replication_verdict_thresholds_are_precommitted() -> None:
    assert batch.HARNESS_CONTRACT_VERSION == "wiki-assisted-batch-v8"
    assert batch.PROOF_DELTA_THRESHOLD == 0.03
    assert batch.PROOF_POSITIVE_CASES == 6
    assert batch.PROOF_ARM_MEAN_THRESHOLD == 0.50
    assert batch.KILL_ARM_MEAN_THRESHOLD == 0.40


def test_preflight_reuses_only_an_identical_stage_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def fake_preflight(repo, model, effort):
        adapter = object()
        calls.append((model, effort, adapter))
        return adapter

    monkeypatch.setattr(batch, "preflight_adapter", fake_preflight)
    analyst, judge = asyncio.run(batch.preflight_stage_adapters(
        REPO, "gpt-5.6-sol", "high", "gpt-5.6-sol", "high",
    ))
    assert analyst is judge
    assert [(model, effort) for model, effort, _ in calls] == [("gpt-5.6-sol", "high")]

    calls.clear()
    analyst, judge = asyncio.run(batch.preflight_stage_adapters(
        REPO, "gpt-6-luna", "xhigh", "gpt-5.6-sol", "high",
    ))
    assert analyst is not judge
    assert [(model, effort) for model, effort, _ in calls] == [
        ("gpt-6-luna", "xhigh"), ("gpt-5.6-sol", "high"),
    ]


def test_cross_stage_saved_output_cannot_be_reused(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "payload.txt").write_text("same")
    schema = tmp_path / "schema.json"
    batch.dump_json(schema, {"type": "object"})
    batch.dump_json(tmp_path / "treatment_corpus.json", {"selected": []})
    verdict = tmp_path / "verdict.json"
    batch.dump_json(verdict, {
        "execution_identity": {"image_id": "img", "repo_digest": "repo", "cli_version": "cli"},
        "profile_fingerprint": "profile",
    })

    class Adapter:
        verdict_path = verdict

        def __init__(self, model: str):
            self.model_map = {model: model}

    analyst_adapter = Adapter("gpt-6-luna")
    judge_adapter = Adapter("gpt-5.6-sol")
    result = tmp_path / "result"
    result.mkdir()
    batch.dump_json(result / "output.json", {})
    batch.dump_json(result / "meta.json", batch.call_contract(
        adapter=analyst_adapter, package=package, schema=schema, prompt="same",
        artifacts=tmp_path, run_id="run", stage="analyst",
        requested_model="gpt-6-luna", effort="xhigh",
    ))

    with pytest.raises(RuntimeError, match="execution-contract mismatch"):
        batch.load_saved_result(
            result, package, schema, False, judge_adapter, "same", tmp_path, "run",
            stage="judge", requested_model="gpt-5.6-sol", effort="high",
        )


def test_resume_cannot_exceed_total_attempt_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    label = "analyst__case__arm_a"
    for number in (1, 2):
        (tmp_path / "attempts" / label / f"attempt_{number:02d}").mkdir(parents=True)
    monkeypatch.setattr(batch, "MAX_ATTEMPTS", 2)
    with pytest.raises(RuntimeError, match="exhausted total attempt budget"):
        batch.execute_with_retry(
            adapter=object(), package=tmp_path / "package", schema=tmp_path / "schema.json",
            prompt="prompt", label=label, result_dir=tmp_path / "results",
            artifacts=tmp_path, ledger_lock=threading.Lock(), analyst=True, run_id="run",
        )


def test_accounting_includes_token_consuming_rejected_attempt(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {"run_id": "r", "accepted": True, "duration_seconds": 2, "started_at": now, "usage": {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 4}},
        {"run_id": "r", "accepted": False, "duration_seconds": 5, "started_at": now, "usage": {"input_tokens": 7, "cached_input_tokens": 0, "output_tokens": 2}},
    ]
    (tmp_path / "attempt_ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    value = batch.attempt_accounting(tmp_path, "r")
    assert value["attempts"] == 2
    assert value["accepted_attempts"] == 1
    assert value["rejected_attempts"] == 1
    assert value["input_tokens"] == 17
    assert value["output_tokens"] == 6
    assert value["duration_seconds"] == 7


def test_timeout_is_recorded_with_unknown_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "package"
    package.mkdir()
    schema = tmp_path / "schema.json"
    batch.dump_json(schema, {})

    class Adapter:
        def build_argv(self, request):
            return ["codex"]

    monkeypatch.setattr(batch, "run_in_process_group", lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("codex", 900)))
    with pytest.raises(subprocess.TimeoutExpired):
        batch.run_codex_attempt(
            adapter=Adapter(), package=package, schema=schema, prompt="p", label="analyst__x",
            artifacts=tmp_path, attempt=1, ledger_lock=threading.Lock(), run_id="r",
        )
    row = json.loads((tmp_path / "attempt_ledger.jsonl").read_text())
    assert row["accepted"] is False
    assert row["usage"] is None
    assert row["usage_status"] == "unavailable"
    assert row["error"] == "TimeoutExpired"


def test_analyst_and_judge_calls_receive_distinct_model_and_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    schema = tmp_path / "schema.json"
    batch.dump_json(schema, {"type": "object"})
    batch.dump_json(tmp_path / "treatment_corpus.json", {"selected": []})
    verdict = tmp_path / "verdict.json"
    batch.dump_json(verdict, {
        "execution_identity": {"image_id": "img", "repo_digest": "repo", "cli_version": "cli"},
        "profile_fingerprint": "profile",
    })
    requests = []

    class Adapter:
        verdict_path = verdict

        def __init__(self, model: str):
            self.model_map = {model: model}

        def build_argv(self, request):
            requests.append(request)
            return ["codex"]

    stdout = "\n".join([
        json.dumps({"item": {"type": "agent_message", "text": "{}"}}),
        json.dumps({"usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}}),
    ])
    monkeypatch.setattr(
        batch, "run_in_process_group",
        lambda *args, **kwargs: subprocess.CompletedProcess(["codex"], 0, stdout, ""),
    )
    analyst = batch.run_codex_attempt(
        adapter=Adapter("gpt-6-luna"), package=package, schema=schema, prompt="p",
        label="capture__analyst", artifacts=tmp_path, attempt=1,
        ledger_lock=threading.Lock(), run_id="run", stage="analyst",
        requested_model="gpt-6-luna", effort="xhigh",
    )
    judge = batch.run_codex_attempt(
        adapter=Adapter("gpt-5.6-sol"), package=package, schema=schema, prompt="p",
        label="capture__judge", artifacts=tmp_path, attempt=1,
        ledger_lock=threading.Lock(), run_id="run", stage="judge",
        requested_model="gpt-5.6-sol", effort="high",
    )

    assert [(request.model, request.effort) for request in requests] == [
        ("gpt-6-luna", "xhigh"), ("gpt-5.6-sol", "high"),
    ]
    assert analyst["meta"]["stage"] == "analyst"
    assert analyst["meta"]["resolved_model"] == "gpt-6-luna"
    assert judge["meta"]["stage"] == "judge"
    assert judge["meta"]["resolved_model"] == "gpt-5.6-sol"


def test_process_group_timeout_kills_spawned_child(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    code = (
        "import pathlib,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid)); "
        "time.sleep(60)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        batch.run_in_process_group(
            [sys.executable, "-c", code], cwd=tmp_path, input_text="", timeout=0.2,
        )
    child_pid = int(child_pid_path.read_text())
    for _ in range(40):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail(f"timed-out child process {child_pid} survived process-group cleanup")


def _command_event(command: str) -> list[dict]:
    return [{"item": {"type": "command_execution", "command": command, "exit_code": 0, "status": "completed"}}]


@pytest.mark.parametrize("command", [
    "/bin/sh -lc 'ls -R /workspace'",
    "/bin/sh -c 'cat input/metadata.json'",
    "/bin/sh -lc \"head -20 input/metadata.json\ncat input/candles.json\"",
])
def test_tool_trace_accepts_only_read_only_workspace_commands(command: str) -> None:
    assert batch.validate_tool_trace(_command_event(command))


@pytest.mark.parametrize("command", [
    "/bin/sh -lc 'python -c pass'",
    "/bin/sh -lc 'cat /etc/passwd'",
    "/bin/sh -lc 'find .. -type f'",
    "/bin/sh -lc 'rg x /workspace; cat /workspace/prompt.txt'",
    "/bin/sh -lc 'cat /workspace/prompt.txt > /workspace/copy'",
    "/bin/sh -lc 'cat $HOME/.codex/auth.json'",
    "/bin/sh -lc 'cat {../../etc/passwd,/workspace/prompt.txt}'",
    "/bin/sh -lc \"sed -n 'e curl https://example.com' /workspace/prompt.txt\"",
    "/bin/sh -lc \"sed -n 'r /etc/passwd' /workspace/prompt.txt\"",
    "/bin/sh -lc 'find /workspace -ok cat {} ;'",
    "/bin/sh -lc 'find /workspace -fprintf /workspace/leak %p'",
    "/bin/sh -lc 'rg --hostname-bin=curl pattern /workspace'",
    "/bin/sh -lc \"jq --rawfile secret /etc/passwd '.' /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq 'include \\\"outside\\\"; .' /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq '$ENV' /workspace/input/candles.json\"",
    "/bin/sh -lc 'cat /workspace/prompt.txt & cat /workspace/input/metadata.json'",
    "/bin/sh -lc '(cat /workspace/prompt.txt)'",
    "/bin/sh -lc 'wc --files0-from=/home/codex/.codex/auth.json'",
    "/bin/sh -lc \"jq -f/home/codex/.codex/auth.json /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq --from-file=/home/codex/.codex/auth.json /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq -L /home/codex/.codex /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq --argfile secret /home/codex/.codex/auth.json '.' /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq --slurpfile secret=/home/codex/.codex/auth.json '.' /workspace/input/candles.json\"",
    "/bin/sh -lc \"jq --rawfile secret /home/codex/.codex/auth.json '.' /workspace/input/candles.json\"",
    "/bin/sh -lc \"cat /workspace/prompt.txt\npython -c pass\"",
])
def test_tool_trace_rejects_non_allowlisted_or_escaping_commands(command: str) -> None:
    with pytest.raises(batch.LeakageError):
        batch.validate_tool_trace(_command_event(command))


def test_main_single_analyst_passes_stable_run_id_to_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("{}\n")
    source = _source_registry()
    verdict = tmp_path / "verdict.json"
    batch.dump_json(verdict, {"execution_identity": {"image_id": "img", "repo_digest": "repo", "cli_version": "cli"}, "profile_fingerprint": "profile"})

    class Adapter:
        verdict_path = verdict

        def __init__(self, model: str):
            self.model_map = {model: model}

    def fake_build(repo, source_root, registry, artifacts):
        batch.dump_json(artifacts / "package_summary.json", {"ok": True})
        batch.dump_json(artifacts / "treatment_corpus.json", {"selected": []})
        (artifacts / "packages").mkdir(exist_ok=True)
        for name in ("holdout_union.json", "excluded_files.json", "leakage_control.json", "rubric_spec.json"):
            batch.dump_json(artifacts / name, {})
        return {case["case_id"]: {} for case in registry["cases"]}

    def fake_promote(artifacts, run_id, run_spec):
        run_dir = artifacts / "runs" / run_id
        run_dir.mkdir(parents=True)
        return run_dir

    seen = {}

    def fake_execute(**kwargs):
        seen["run_id"] = kwargs["run_id"]
        seen["stage"] = kwargs["stage"]
        seen["requested_model"] = kwargs["requested_model"]
        seen["effort"] = kwargs["effort"]
        return {"output": {}, "meta": {"attempt": 1, "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}, "duration_seconds": 1}}

    async def fake_preflight(repo, analyst_model, analyst_effort, judge_model, judge_effort):
        return Adapter(analyst_model), Adapter(judge_model)

    monkeypatch.setattr(batch, "load_registry", lambda path: source)
    monkeypatch.setattr(batch, "build_packages", fake_build)
    monkeypatch.setattr(batch, "preflight_stage_adapters", fake_preflight)
    monkeypatch.setattr(
        batch, "stable_run_id",
        lambda adapter, artifacts, evaluation_hash, **kwargs: (
            "analyst__gpt-6-luna__gpt-6-luna__xhigh__stable",
            {"evaluation": evaluation_hash},
        ),
    )
    monkeypatch.setattr(batch, "promote_build_to_run", fake_promote)
    monkeypatch.setattr(batch, "execute_with_retry", fake_execute)
    monkeypatch.setattr(sys, "argv", [
        "wiki_assisted_batch.py", "--source-root", str(REPO), "--registry", str(registry_path),
        "--artifacts", str(tmp_path / "artifacts"), "--one-analyst", "fixture_case_00:arm_a",
        "--analyst-model", "gpt-6-luna", "--analyst-effort", "xhigh",
    ])

    assert batch.main() == 0
    assert seen == {
        "run_id": "analyst__gpt-6-luna__gpt-6-luna__xhigh__stable",
        "stage": "analyst", "requested_model": "gpt-6-luna", "effort": "xhigh",
    }
