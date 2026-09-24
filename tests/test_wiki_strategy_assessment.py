from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from spikes import wiki_strategy_assessment as assessment


def _candles() -> list[dict]:
    return [
        {"open_time": 0, "open": 100, "high": 102, "low": 85, "close": 101, "volume": 90},
        {"open_time": 14_400_000, "open": 101, "high": 104, "low": 100, "close": 103, "volume": 110},
        {"open_time": 28_800_000, "open": 103, "high": 105, "low": 102, "close": 104, "volume": 95},
    ]


def _trade_plan() -> dict:
    return {
        "action": "wait_for_trigger", "direction": "long", "entry_type": "stop",
        "entry_level": 105, "stop_loss": 100, "take_profit": 120,
        "entry_expiry_bars": 8, "max_holding_bars": 20,
        "cancellation_condition": "Cancel at stop 100 or after 8 bars.",
    }


def _analyst() -> dict:
    return {
        "observations": ["Range", "Test", "Demand"],
        "structure": "A range with demand in control.",
        "phase": "Late Phase C into D.",
        "key_events": ["Spring", "Test"],
        "leading_scenario": {"direction": "up", "trigger_level": 105},
        "alternative_scenario": {"direction": "down", "trigger_level": 98},
        "confidence": 0.7,
        "uncertainties": ["No benchmark"],
        "trade_plan": _trade_plan(),
        "process_assessment": {"trading_area_readiness": "Ready after test."},
    }


def _evidence(direction: str = "long") -> list[dict]:
    entry, stop, target = (105, 100, 120) if direction == "long" else (100, 105, 85)
    if direction == "long":
        numeric = [
            ("entry", "trade_plan", "trade_plan.entry_level", None, entry),
            ("stop", "trade_plan", "trade_plan.stop_loss", None, stop),
            ("target", "trade_plan", "trade_plan.take_profit", None, target),
        ]
    else:
        numeric = [
            ("entry", "pre_t_bar", "candles[0].open", 0, entry),
            ("stop", "pre_t_bar", "candles[2].high", 2, stop),
            ("target", "pre_t_bar", "candles[0].low", 0, target),
        ]
    return [
        {"role": "setup", "source_field": "key_events", "field_path": "key_events[0]", "bar_index": None, "quote_or_fact": "Spring"},
        {"role": "readiness", "source_field": "process_assessment", "field_path": "process_assessment.trading_area_readiness", "bar_index": None, "quote_or_fact": "Ready after test."},
        *[
            {"role": role, "source_field": source, "field_path": path, "bar_index": bar, "quote_or_fact": str(value)}
            for role, source, path, bar, value in numeric
        ],
    ]


def _eligible(strategy_id: str, setup: str, direction: str) -> dict:
    if direction == "long":
        entry, stop, target = 105, 100, 120
    else:
        entry, stop, target = 100, 105, 85
    return {
        "strategy_id": strategy_id,
        "status": "eligible",
        "skip_reason": None,
        "setup": setup,
        "direction": direction,
        "readiness": "ready",
        "entry_action": "wait_for_trigger",
        "entry_type": "stop",
        "entry_level": entry,
        "stop_loss": stop,
        "take_profit": target,
        "entry_expiry_bars": 8,
        "max_holding_bars": 20,
        "evidence": _evidence(direction),
    }


def _sidecar() -> dict:
    return {
        "schema_version": assessment.ASSESSMENT_SCHEMA_VERSION,
        "assessments": [
            _eligible("phase_c_shake_direct", "spring_direct", "long"),
            _eligible("phase_c_test", "utad_test", "short"),
            _eligible("phase_d_break_test", "buec_lps", "long"),
            _eligible("phase_e_continuation", "phase_e_short_rally", "short"),
        ],
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    analyst = tmp_path / "analyst.json"
    candles = tmp_path / "candles.json"
    assessment.dump_json(analyst, _analyst())
    assessment.dump_json(candles, _candles())
    return analyst, candles


def _frozen_provenance() -> dict[str, str]:
    return {
        "packaged_candles_sha256": "a" * 64,
        "result_output_sha256": "b" * 64,
        "result_meta_sha256": "c" * 64,
    }


def _write_accepted_result(
    artifacts: Path, package_id: str, package_sha256: str, sidecar: dict,
) -> None:
    result_root = artifacts / "results" / package_id
    attempt_root = artifacts / "results" / f"{package_id}.attempts" / "attempt_01"
    usage = {
        "input_tokens": 100,
        "cached_input_tokens": 50,
        "output_tokens": 25,
    }
    raw = "\n".join([
        json.dumps({"item": {"type": "agent_message", "text": json.dumps(sidecar)}}),
        json.dumps({"usage": usage}),
    ])
    stderr = ""
    meta = {
        "run_id": "test-run",
        "stage": "strategy_assessment",
        "requested_model": assessment.MODEL,
        "resolved_model": assessment.MODEL,
        "effort": assessment.EFFORT,
        "timeout_seconds": assessment.TIMEOUT_SECONDS,
        "max_attempts": assessment.MAX_ATTEMPTS,
        "package_fingerprint": package_sha256,
        "prompt_sha256": assessment.sha256_bytes(assessment.ASSESSMENT_PROMPT.encode()),
        "schema_sha256": assessment.sha256_json(assessment.ASSESSMENT_SCHEMA),
        "rule_bundle_sha256": assessment.sha256_json(assessment.RULE_BUNDLE),
        "attempt": 1,
        "started_at": "2026-01-01T00:00:00+00:00",
        "duration_seconds": 1.0,
        "usage": usage,
        "stdout_sha256": assessment.sha256_bytes(raw.encode()),
        "stderr_sha256": assessment.sha256_bytes(stderr.encode()),
    }
    assessment.dump_json(result_root / "output.json", sidecar)
    assessment.dump_json(result_root / "meta.json", meta)
    assessment.dump_json(attempt_root / "parsed_output.json", sidecar)
    assessment.dump_json(attempt_root / "meta.json", meta)
    (attempt_root / "raw.jsonl").write_text(raw)
    (attempt_root / "stderr.txt").write_text(stderr)
    ledger = artifacts / "results" / "attempt_ledger.jsonl"
    ledger.write_text(assessment.canonical_json({**meta, "accepted": True}) + "\n")


def test_valid_assessment_covers_exact_four_strategies_and_both_directions() -> None:
    sidecar = _sidecar()
    assessment.validate_assessment(sidecar)
    plans = [assessment.build_strategy_plan(item) for item in sidecar["assessments"]]
    assert [item["strategy_id"] for item in plans] == list(assessment.STRATEGY_IDS)
    assert {item["trade_plan"]["direction"] for item in plans} == {"long", "short"}
    assert all(item["assessment_status"] == "eligible" for item in plans)
    assert all(item["reward_risk"] == pytest.approx(3.0) for item in plans)


def test_schema_rejects_unknown_fields_and_wrong_direction() -> None:
    sidecar = _sidecar()
    sidecar["unexpected"] = True
    with pytest.raises(ValidationError):
        assessment.validate_assessment(sidecar)

    sidecar = _sidecar()
    sidecar["assessments"][0]["direction"] = "short"
    with pytest.raises(ValueError, match="setup/direction contradiction"):
        assessment.validate_assessment(sidecar)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item["evidence"].pop(), "missing evidence roles"),
        (lambda item: item.update(stop_loss=110), "unordered eligible levels"),
        (lambda item: item.update(entry_expiry_bars=None), "requires entry expiry"),
    ],
)
def test_actionable_assessment_needs_complete_evidence_and_ordered_levels(mutation, message: str) -> None:
    sidecar = _sidecar()
    mutation(sidecar["assessments"][0])
    with pytest.raises(ValueError, match=message):
        assessment.validate_assessment(sidecar)


def test_insufficient_evidence_becomes_no_trade_without_parsing_rationale() -> None:
    item = _eligible("phase_c_shake_direct", "spring_direct", "long")
    item.update(
        status="insufficient_evidence", skip_reason="insufficient_numeric_anchors",
        entry_action="none", entry_type="none", entry_level=None, stop_loss=None,
        take_profit=None, entry_expiry_bars=None, max_holding_bars=None,
    )
    item["evidence"] = [{
        "role": "target", "source_field": "leading_scenario",
        "field_path": "leading_scenario.expected_path", "bar_index": None,
        "quote_or_fact": "Narrative says much higher, but supplies no number 120.",
    }]
    sidecar = _sidecar()
    sidecar["assessments"][0] = item
    assessment.validate_assessment(sidecar)
    plan = assessment.build_strategy_plan(item)
    assert plan["skip_reason"] == "insufficient_numeric_anchors"
    assert plan["trade_plan"]["action"] == "no_trade"
    assert plan["trade_plan"]["take_profit"] is None


def test_three_r_boundary_passes_and_below_boundary_is_ineligible() -> None:
    exact = _eligible("phase_c_shake_direct", "spring_direct", "long")
    assert assessment.build_strategy_plan(exact)["assessment_status"] == "eligible"
    below = copy.deepcopy(exact)
    below["take_profit"] = 119.99
    result = assessment.build_strategy_plan(below)
    assert result["assessment_status"] == "ineligible"
    assert result["skip_reason"] == "below_3r"
    assert result["trade_plan"]["action"] == "no_trade"


def test_contextual_validation_rejects_numeric_anchor_not_at_cited_field() -> None:
    sidecar = _sidecar()
    sidecar["assessments"][0]["take_profit"] = 121
    with pytest.raises(ValueError, match="target anchor is not directly supported"):
        assessment.validate_assessment(
            sidecar, analyst_output=_analyst(), pre_t_candles=_candles(),
        )


def test_uncertainty_evidence_uses_matching_source_root() -> None:
    sidecar = _sidecar()
    sidecar["assessments"][0]["evidence"].append({
        "role": "contradiction",
        "source_field": "uncertainties",
        "field_path": "uncertainties[0]",
        "bar_index": None,
        "quote_or_fact": "No benchmark",
    })
    assessment.validate_assessment(
        sidecar, analyst_output=_analyst(), pre_t_candles=_candles(),
    )

    sidecar["assessments"][0]["evidence"][-1]["source_field"] = "process_assessment"
    with pytest.raises(ValueError, match="must start with process_assessment"):
        assessment.validate_assessment(
            sidecar, analyst_output=_analyst(), pre_t_candles=_candles(),
        )


@pytest.mark.parametrize(
    ("role", "source", "path"),
    [
        ("setup", "key_events", "key_events"),
        ("readiness", "process_assessment", "process_assessment"),
    ],
)
def test_contextual_evidence_rejects_parent_containers(
    role: str, source: str, path: str,
) -> None:
    sidecar = _sidecar()
    evidence = sidecar["assessments"][0]["evidence"]
    target = next(item for item in evidence if item["role"] == role)
    target.update(
        source_field=source,
        field_path=path,
        quote_or_fact="invented support",
    )
    with pytest.raises(ValueError, match="must resolve to a string or number"):
        assessment.validate_assessment(
            sidecar, analyst_output=_analyst(), pre_t_candles=_candles(),
        )


def test_defensive_builder_maps_invalid_ordering_to_stable_skip_reason() -> None:
    item = _eligible("phase_c_shake_direct", "spring_direct", "long")
    item["stop_loss"] = 106
    result = assessment.build_strategy_plan(item)
    assert result["skip_reason"] == "invalid_ordering"
    assert result["trade_plan"]["action"] == "no_trade"


def test_package_is_deterministic_and_contains_only_allowlisted_pre_t_files(tmp_path: Path) -> None:
    analyst, candles = _write_inputs(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    one = assessment.build_package(
        analyst_output=analyst, pre_t_candles=candles, destination=first,
        forbidden_markers=["secret-case", "BTCUSDT"],
    )
    two = assessment.build_package(
        analyst_output=analyst, pre_t_candles=candles, destination=second,
        forbidden_markers=["secret-case", "BTCUSDT"],
    )
    assert one == two
    assert assessment.file_manifest(first) == assessment.file_manifest(second)
    assessment.validate_package(first, forbidden_markers=["secret-case", "BTCUSDT"])
    names = {path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file()}
    assert names == {
        "input/analysis.json", "input/candles.json", "strategy_rules.json",
        "prompt.txt", "strategy_assessment.schema.json", "allowlist_manifest.json",
    }


@pytest.mark.parametrize(
    "kind", ["post_t", "identity", "annotation", "marker", "symlink"],
)
def test_package_boundary_rejects_future_identity_markers_and_symlinks(tmp_path: Path, kind: str) -> None:
    analyst, candles = _write_inputs(tmp_path)
    package = tmp_path / "package"
    assessment.build_package(
        analyst_output=analyst, pre_t_candles=candles, destination=package,
        forbidden_markers=["secret-case"],
    )
    if kind == "post_t":
        assessment.dump_json(package / "post_t.json", [])
    elif kind == "identity":
        value = json.loads((package / "input/analysis.json").read_text())
        value["asset"] = "BTC"
        assessment.dump_json(package / "input/analysis.json", value)
    elif kind == "annotation":
        value = json.loads((package / "input/candles.json").read_text())
        value[0]["wyckoff_phase"] = "Phase D"
        assessment.dump_json(package / "input/candles.json", value)
    elif kind == "marker":
        (package / "prompt.txt").write_text(assessment.ASSESSMENT_PROMPT + "secret-case")
    else:
        (package / "leak").symlink_to(analyst)
    with pytest.raises(assessment.LeakageError):
        assessment.validate_package(package, forbidden_markers=["secret-case"])


def test_build_rejects_calendar_open_times_and_provenance_keys(tmp_path: Path) -> None:
    analyst, candles = _write_inputs(tmp_path)
    values = json.loads(candles.read_text())
    values[0]["open_time"] = 1_700_000_000_000
    assessment.dump_json(candles, values)
    with pytest.raises(assessment.LeakageError, match="starting at zero"):
        assessment.build_package(
            analyst_output=analyst, pre_t_candles=candles,
            destination=tmp_path / "package",
        )
    value = _analyst()
    value["source"] = "private/file"
    assessment.dump_json(analyst, value)
    assessment.dump_json(candles, _candles())
    with pytest.raises(assessment.LeakageError, match="forbidden identity"):
        assessment.build_package(
            analyst_output=analyst, pre_t_candles=candles,
            destination=tmp_path / "other",
        )


def test_extended_partial_candle_schema_is_strict_but_supported() -> None:
    candles = _candles()
    for candle in candles:
        candle.update(is_complete=True, elapsed_fraction=1.0)
    candles[-1].update(is_complete=False, elapsed_fraction=0.5)
    assessment._validate_anonymous_candles(candles)

    candles[0]["elapsed_fraction"] = 0.5
    with pytest.raises(assessment.LeakageError, match="inconsistent completion"):
        assessment._validate_anonymous_candles(candles)


def test_run_contract_is_luna_xhigh_900_seconds_and_resume_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst, candles = _write_inputs(tmp_path)
    package = tmp_path / "package"
    assessment.build_package(
        analyst_output=analyst, pre_t_candles=candles, destination=package,
    )
    sidecar = _sidecar()
    stdout = "\n".join([
        json.dumps({"item": {"type": "agent_message", "text": json.dumps(sidecar)}}),
        json.dumps({"usage": {"input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 40}}),
    ])

    class Adapter:
        model_map = {assessment.MODEL: assessment.MODEL}

        def build_argv(self, request):
            assert request.model == "gpt-5.6-luna"
            assert request.effort == "xhigh"
            assert request.timeout == 900
            assert request.cwd == package
            return ["fake-codex"]

    calls = []

    def fake_run(argv, *, cwd, prompt):
        calls.append((argv, cwd, prompt))
        return __import__("subprocess").CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(assessment, "_run_process", fake_run)
    result_dir = tmp_path / "results/result"
    result = assessment.run_package(
        adapter=Adapter(), package=package, result_dir=result_dir,
        run_id="run-1", resume=False,
    )
    assert result["meta"]["timeout_seconds"] == 900
    assert result["meta"]["usage"] == {
        "input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 40,
    }
    resumed = assessment.run_package(
        adapter=Adapter(), package=package, result_dir=result_dir,
        run_id="run-1", resume=True,
    )
    assert resumed["resumed"] is True
    assert len(calls) == 1
    with pytest.raises(RuntimeError, match="contract mismatch"):
        assessment.run_package(
            adapter=Adapter(), package=package, result_dir=result_dir,
            run_id="changed", resume=True,
        )


def test_resume_recovers_accepted_attempt_after_interrupted_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst, candles = _write_inputs(tmp_path)
    package = tmp_path / "package"
    assessment.build_package(
        analyst_output=analyst, pre_t_candles=candles, destination=package,
    )
    class Adapter:
        model_map = {assessment.MODEL: assessment.MODEL}

        def build_argv(self, request):
            return ["fake-codex"]

    result_dir = tmp_path / "results" / "result"
    attempt_root = tmp_path / "results" / "result.attempts" / "attempt_01"
    package_fingerprint = json.loads(
        (package / "allowlist_manifest.json").read_text()
    )["content_fingerprint"]
    meta = {
        "run_id": "run-1",
        "stage": "strategy_assessment",
        "requested_model": assessment.MODEL,
        "resolved_model": assessment.MODEL,
        "effort": assessment.EFFORT,
        "timeout_seconds": assessment.TIMEOUT_SECONDS,
        "max_attempts": assessment.MAX_ATTEMPTS,
        "package_fingerprint": package_fingerprint,
        "prompt_sha256": assessment.sha256_bytes(assessment.ASSESSMENT_PROMPT.encode()),
        "schema_sha256": assessment.sha256_json(assessment.ASSESSMENT_SCHEMA),
        "rule_bundle_sha256": assessment.sha256_json(assessment.RULE_BUNDLE),
        "attempt": 1,
        "started_at": "2026-01-01T00:00:00+00:00",
        "duration_seconds": 1.0,
        "usage": {
            "input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 40,
        },
        "stdout_sha256": "",
        "stderr_sha256": assessment.sha256_bytes(b""),
    }
    raw = "\n".join([
        json.dumps({"item": {
            "type": "agent_message", "text": json.dumps(_sidecar()),
        }}),
        json.dumps({"usage": meta["usage"]}),
    ])
    meta["stdout_sha256"] = assessment.sha256_bytes(raw.encode())
    assessment.dump_json(attempt_root / "parsed_output.json", _sidecar())
    assessment.dump_json(attempt_root / "meta.json", meta)
    (attempt_root / "raw.jsonl").write_text(raw)
    (attempt_root / "stderr.txt").write_text("")
    monkeypatch.setattr(
        assessment,
        "_run_process",
        lambda *args, **kwargs: pytest.fail("resume must not issue another model call"),
    )
    result = assessment.run_package(
        adapter=Adapter(), package=package, result_dir=result_dir,
        run_id="run-1", resume=True,
    )
    assert result["meta"]["attempt"] == 1
    assert result["resumed"] is True
    assert (result_dir / "output.json").is_file()
    ledger = (tmp_path / "results" / "attempt_ledger.jsonl").read_text().splitlines()
    assert len(ledger) == 1


def test_frozen_bundle_is_byte_stable_auditable_and_tamper_evident(tmp_path: Path) -> None:
    sidecar = _sidecar()
    record = assessment.freeze_case_record(
        case_id="hidden-case", arm="arm_a", analyst_output=_analyst(),
        pre_t_candles=_candles(), sidecar=sidecar, **_frozen_provenance(),
    )
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = assessment.freeze_plan_bundle([record], first)
    second_manifest = assessment.freeze_plan_bundle([record], second)
    assert assessment.file_manifest(first) == assessment.file_manifest(second)
    assert first_manifest["content_fingerprint"] == second_manifest["content_fingerprint"]
    bundle = json.loads((first / "frozen_plans.json").read_text())
    assert bundle["strategy_ids"] == list(assessment.STRATEGY_IDS)
    assert bundle["cases"][0]["baseline"]["origin"] == "analyst_trade_plan"
    assert len(bundle["cases"][0]["strategies"]) == 4
    assert all(entry["reward_risk"] == pytest.approx(3.0) for entry in bundle["cases"][0]["strategies"])

    aggregate = first / "frozen_plans.json"
    aggregate.write_text(aggregate.read_text() + " ")
    with pytest.raises(RuntimeError, match="file manifest mismatch"):
        assessment.verify_frozen_bundle(first)


def test_changed_analysis_changes_frozen_input_hash() -> None:
    first = assessment.freeze_case_record(
        case_id="one", arm="arm_a", analyst_output=_analyst(),
        pre_t_candles=_candles(), sidecar=_sidecar(), **_frozen_provenance(),
    )
    changed = _analyst()
    changed["confidence"] = 0.5
    second = assessment.freeze_case_record(
        case_id="one", arm="arm_a", analyst_output=changed,
        pre_t_candles=_candles(), sidecar=_sidecar(), **_frozen_provenance(),
    )
    assert first["analyst_input_sha256"] != second["analyst_input_sha256"]


def test_registry_build_keeps_identity_only_in_private_index(tmp_path: Path) -> None:
    analyst, candles = _write_inputs(tmp_path)
    registry = tmp_path / "registry.json"
    assessment.dump_json(registry, {"cases": [{
        "case_id": "secret-case", "arm": "arm_a",
        "analyst_output": str(analyst), "pre_t_candles": str(candles),
        "forbidden_markers": ["BTCUSDT"],
    }]})
    artifacts = tmp_path / "artifacts"
    index = assessment.build_from_registry(registry, artifacts)
    package_id = index["packages"][0]["package_id"]
    package = artifacts / "packages" / package_id
    assert "secret-case" not in str(package.relative_to(artifacts))
    assert "secret-case" not in "".join(
        path.read_text(errors="ignore") for path in package.rglob("*") if path.is_file()
    )
    assessment.verify_packages(artifacts)


def test_verify_from_artifacts_regenerates_identical_frozen_tree(tmp_path: Path) -> None:
    analyst, candles = _write_inputs(tmp_path)
    registry = tmp_path / "registry.json"
    assessment.dump_json(registry, {"cases": [{
        "case_id": "case-01", "arm": "arm_a",
        "analyst_output": str(analyst), "pre_t_candles": str(candles),
    }]})
    artifacts = tmp_path / "artifacts"
    index = assessment.build_from_registry(registry, artifacts)
    package_id = index["packages"][0]["package_id"]
    _write_accepted_result(
        artifacts, package_id, index["packages"][0]["package_sha256"], _sidecar(),
    )
    frozen = tmp_path / "frozen"
    assessment.freeze_from_artifacts(artifacts, frozen)
    verified = assessment.verify_from_artifacts(artifacts, frozen)
    assert verified["schema_version"] == assessment.MANIFEST_SCHEMA_VERSION


def test_freeze_rejects_unbound_sidecar_without_accepted_meta(tmp_path: Path) -> None:
    analyst, candles = _write_inputs(tmp_path)
    registry = tmp_path / "registry.json"
    assessment.dump_json(registry, {"cases": [{
        "case_id": "case-01", "arm": "arm_a",
        "analyst_output": str(analyst), "pre_t_candles": str(candles),
    }]})
    artifacts = tmp_path / "artifacts"
    index = assessment.build_from_registry(registry, artifacts)
    package_id = index["packages"][0]["package_id"]
    assessment.dump_json(artifacts / "results" / package_id / "output.json", _sidecar())
    with pytest.raises(RuntimeError, match="requires output and meta"):
        assessment.freeze_from_artifacts(artifacts, tmp_path / "frozen")
