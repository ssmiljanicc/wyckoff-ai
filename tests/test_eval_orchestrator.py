from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.eval import benchmark, orchestrator
from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES, make_placeholder_answers
from scripts.eval.runtime_adapters import RuntimeRequest, RuntimeResponse


def spec(tmp_path: Path, run_id: str = "case_01__blind__anon__claude-opus-4-8__high") -> benchmark.RunSpec:
    snapshot = tmp_path / "case_01"
    snapshot.mkdir(exist_ok=True)
    (snapshot / "candles.json").write_text("[]")
    return {
        "run_id": run_id, "case_id": "case_01", "time_mode": "blind", "anon_mode": "anon",
        "control": "baseline", "model": "claude-opus-4-8", "effort": "high",
        "snapshot_dir": str(snapshot), "answer_key_path": str(tmp_path / "answer.json"),
        "instruction": None, "missing_snapshot": False,
    }


def analysis() -> dict:
    return {"direction": "up", "trigger": 10.0, "invalidation": 8.0, "confidence": 0.7, "structure": "accumulation", "phase": "C", "event": "spring"}


def verdict() -> dict:
    return {name: {"score": 0.8, "rationale": "ok"} for name in ("structure", "phase", "event", "narrative_quality", "calibration")}


def test_state_reconciles_complete_and_partial_results(tmp_path: Path) -> None:
    first = spec(tmp_path)
    second = spec(tmp_path, "case_01__blind__anon__claude-opus-4-8__medium")
    results = tmp_path / "results"
    results.mkdir()
    (results / f'{first["run_id"]}.json').write_text(json.dumps({"analysis_output": analysis(), "usage": {}, "judge_verdict": verdict()}))
    (results / f'{second["run_id"]}.json').write_text(json.dumps({"analysis_output": analysis(), "usage": {}, "judge_verdict": None}))
    store = orchestrator.StateStore(tmp_path / "state.json", results)
    store.initialize([first, second])
    runs = store.read()["runs"]
    assert runs[first["run_id"]]["status"] == "succeeded"
    assert runs[second["run_id"]]["next_stage"] == "judge"


def test_state_rejects_manifest_fingerprint_change(tmp_path: Path) -> None:
    first = spec(tmp_path)
    store = orchestrator.StateStore(tmp_path / "state.json", tmp_path / "results")
    store.initialize([first])
    changed = dict(first)
    changed["effort"] = "medium"
    with pytest.raises(ValueError, match="fingerprint"):
        store.initialize([changed])


def test_analyst_root_rejects_symlink_and_never_copies_answer(tmp_path: Path) -> None:
    current = spec(tmp_path)
    secret = tmp_path / "answer.json"
    secret.write_text("private")
    (Path(current["snapshot_dir"]) / "escape").symlink_to(secret)
    with pytest.raises(ValueError, match="symlink"):
        with orchestrator.analyst_root(current):
            pass


class FakeAdapter:
    def __init__(self):
        self.requests: list[RuntimeRequest] = []
    async def preflight(self, model: str, effort: str) -> None:
        return None
    async def run(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        output = verdict() if request.model == orchestrator.JUDGE_MODEL and request.cwd.name.startswith("wyckoff-judge-") else analysis()
        return RuntimeResponse(output, {"input_tokens": 1, "output_tokens": 2})


def test_execute_run_checkpoints_and_isolates_judge(tmp_path: Path) -> None:
    current = spec(tmp_path)
    Path(current["answer_key_path"]).write_text(json.dumps({"ground_truth": "spring", "event_type": "spring", "realized_direction": "up", "decisive": True}))
    results = tmp_path / "results"
    results.mkdir()
    store = orchestrator.StateStore(tmp_path / "state.json", results)
    store.initialize([current])
    fake = FakeAdapter()
    asyncio.run(orchestrator.execute_run(current, store, results, adapters={current["model"]: fake, "__judge__": fake}, limiter=orchestrator.StartLimiter(0), timeout=1, max_attempts=2))
    raw = json.loads((results / f'{current["run_id"]}.json').read_text())
    assert raw["judge_verdict"] and raw["usage"] == {"input_tokens": 2, "output_tokens": 4}
    assert store.read()["runs"][current["run_id"]]["status"] == "succeeded"
    judge_payload = json.loads(fake.requests[1].prompt)
    assert "candles" not in judge_payload["answer_key"]
    assert "answer_key_path" not in judge_payload["output"]
    assert str(Path(current["snapshot_dir"])) not in fake.requests[1].prompt


def test_atomic_write_preserves_previous_file_when_replace_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    orchestrator.atomic_write_json(path, {"old": True})
    def fail(*args):
        raise OSError("simulated")
    monkeypatch.setattr(orchestrator.os, "replace", fail)
    with pytest.raises(OSError):
        orchestrator.atomic_write_json(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}


def test_dry_run_does_not_write_execution_state(tmp_path: Path) -> None:
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(make_placeholder_answers(GROUND_TRUTH_CASES)))
    base = tmp_path / "benchmark"
    args = orchestrator.build_parser().parse_args([
        "--answers-path", str(answers), "--base-dir", str(base), "--case", "case_01",
        "--model", "claude-opus-4-8", "--effort", "high", "--dry-run",
    ])
    fake = FakeAdapter()
    result = asyncio.run(orchestrator.orchestrate(args, injected_adapters={"claude-opus-4-8": fake, "__judge__": fake}))
    assert result == orchestrator.EXIT_OK
    assert not base.exists()
    assert not fake.requests
