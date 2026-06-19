"""Tests for scripts/eval/benchmark.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.eval import benchmark, scoring


# --- builders ---------------------------------------------------------------


def _answer_key(
    case_id: str = "case_01",
    event_type: str = "spring",
    realized: str = "up",
    decisive: bool = True,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "event_type": event_type,
        "realized_direction": realized,
        "decisive": decisive,
        "ground_truth": "Accumulation spring followed by markup.",
        "post_t_candles": [
            {"open_time": 1, "high": 101.0, "low": 96.0, "close": 100.0},
            {"open_time": 2, "high": 112.0, "low": 101.0, "close": 111.0},
        ],
    }


def _judge_verdict(score: float = 0.8) -> dict[str, Any]:
    return {
        name: {"score": score, "rationale": ""}
        for name in scoring.JUDGE_DIMENSION_NAMES
    }


def _run_result(
    direction: str = "up",
    trigger: float = 110.0,
    invalidation: float = 95.0,
    confidence: float = 0.7,
    input_tokens: int = 1000,
    output_tokens: int = 2000,
    judge_score: float = 0.8,
) -> benchmark.RunResult:
    return {
        "analysis_output": {
            "direction": direction,
            "trigger": trigger,
            "invalidation": invalidation,
            "confidence": confidence,
            "structure": "accumulation",
            "phase": "C",
            "event": "spring",
        },
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "judge_verdict": _judge_verdict(judge_score),
    }


def _make_spec(
    case_id: str,
    time_mode: str,
    anon_mode: str,
    model: str,
    effort: str,
    base_dir: Path,
) -> benchmark.RunSpec:
    base = Path(base_dir)
    return {
        "run_id": f"{case_id}__{time_mode}__{anon_mode}__{model}__{effort}",
        "case_id": case_id,
        "time_mode": time_mode,
        "anon_mode": anon_mode,
        "control": "baseline",
        "model": model,
        "effort": effort,
        "snapshot_dir": str(base / case_id),
        "answer_key_path": str(base / "_answers" / f"{case_id}.answer.json"),
        "instruction": None,
        "missing_snapshot": False,
    }


def _row(
    case_id: str,
    time_mode: str,
    anon_mode: str,
    aggregate: float,
    *,
    model: str = "claude-opus-4-8",
    effort: str = "high",
    event_type: str = "spring",
    total_tokens: int = 3000,
    cost_usd: float | None = 0.05,
) -> benchmark.BenchmarkRow:
    roi, roi_basis = benchmark._compute_roi(aggregate, cost_usd, total_tokens)
    return {
        "run_id": f"{case_id}__{time_mode}__{anon_mode}__{model}__{effort}",
        "case_id": case_id,
        "model": model,
        "effort": effort,
        "time_mode": time_mode,
        "anon_mode": anon_mode,
        "event_type": event_type,
        "aggregate": aggregate,
        "dimensions": {"direction": 1.0, "structure": aggregate},
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "roi": roi,
        "roi_basis": roi_basis,
        "wait_case": False,
    }


# --- 1. matrix --------------------------------------------------------------


def test_build_run_matrix_shape(tmp_path: Path) -> None:
    # Give case_01 a future_visible snapshot dir with an instruction file.
    fv_dir = tmp_path / "case_01__fv"
    fv_dir.mkdir()
    (fv_dir / "instruction.txt").write_text("as-of T instruction\n")

    specs = benchmark.build_run_matrix(["case_01", "case_02"], base_dir=tmp_path)

    # baseline + 2 controls = exactly 3 angles
    angles = {(s["time_mode"], s["anon_mode"]) for s in specs}
    assert angles == {
        ("blind", "anon"),
        ("blind", "revealed"),
        ("future_visible", "anon"),
    }

    # stable + unique run_ids
    run_ids = [s["run_id"] for s in specs]
    assert len(run_ids) == len(set(run_ids))
    n_model_effort = sum(len(e) for e in benchmark.BENCHMARK_MATRIX.values())
    assert len(specs) == 2 * 3 * n_model_effort

    sample = next(
        s
        for s in specs
        if s["case_id"] == "case_01"
        and s["time_mode"] == "blind"
        and s["anon_mode"] == "anon"
        and s["model"] == "claude-opus-4-8"
        and s["effort"] == "high"
    )
    assert sample["run_id"] == "case_01__blind__anon__claude-opus-4-8__high"
    assert sample["snapshot_dir"].endswith("case_01")
    assert sample["answer_key_path"].endswith("_answers/case_01.answer.json")

    # FV runs carry the instruction read from disk.
    fv_specs = [
        s for s in specs if s["case_id"] == "case_01" and s["time_mode"] == "future_visible"
    ]
    assert fv_specs and all(s["instruction"] == "as-of T instruction" for s in fv_specs)

    # revealed runs map to the __revealed dir + separate answer key.
    rev = next(s for s in specs if s["anon_mode"] == "revealed" and s["case_id"] == "case_02")
    assert rev["snapshot_dir"].endswith("case_02__revealed")
    assert rev["answer_key_path"].endswith("_answers/case_02__revealed.answer.json")


# --- 2. cost ----------------------------------------------------------------


def test_compute_cost() -> None:
    cost = benchmark.compute_cost(
        {"input_tokens": 1000, "output_tokens": 2000}, "claude-opus-4-8"
    )
    assert cost == (1000 * 5.0 + 2000 * 25.0) / 1e6

    # Codex pricing is None → cost is None (tokens-only ROI downstream).
    assert (
        benchmark.compute_cost({"input_tokens": 1000, "output_tokens": 2000}, "codex")
        is None
    )


# --- 3. score_run reuses scoring -------------------------------------------


def test_score_run_uses_scoring(tmp_path: Path) -> None:
    spec = _make_spec("case_01", "blind", "anon", "claude-opus-4-8", "high", tmp_path)
    answer = _answer_key()
    result = _run_result()

    row = benchmark.score_run(spec, result, answer)

    deterministic = scoring.score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=answer,
        confidence=0.7,
    )
    expected = scoring.combine_scores(deterministic, _judge_verdict(0.8))

    assert row["aggregate"] == expected["aggregate"]
    assert row["event_type"] == "spring"
    assert row["total_tokens"] == 3000
    assert row["cost_usd"] == (1000 * 5.0 + 2000 * 25.0) / 1e6
    assert row["roi_basis"] == "usd"
    assert row["roi"] == round(expected["aggregate"] / row["cost_usd"], 4)


# --- 4. Δleakage ------------------------------------------------------------


def test_aggregate_delta_leakage() -> None:
    rows = [
        _row("case_01", "blind", "anon", 0.5),
        _row("case_02", "blind", "anon", 0.6),
        _row("case_01", "blind", "revealed", 0.8),
        _row("case_02", "blind", "revealed", 0.9),
    ]
    report = benchmark.aggregate_report(rows)
    leak = {(d["model"], d["effort"]): d for d in report["delta_leakage"]}
    d = leak[("claude-opus-4-8", "high")]
    # mean((0.8-0.5),(0.9-0.6)) = 0.3 > 0
    assert d["delta"] == pytest.approx(0.3)
    assert d["n"] == 2


# --- 5. Δlookahead over common cases only -----------------------------------


def test_aggregate_delta_lookahead() -> None:
    rows = [
        _row("case_01", "blind", "anon", 0.5),
        _row("case_02", "blind", "anon", 0.6),
        # only case_01 has a future_visible counterpart
        _row("case_01", "future_visible", "anon", 0.52),
    ]
    report = benchmark.aggregate_report(rows)
    look = {(d["model"], d["effort"]): d for d in report["delta_lookahead"]}
    d = look[("claude-opus-4-8", "high")]
    # case_02 fv missing → excluded, not treated as 0
    assert d["n"] == 1
    assert d["delta"] == pytest.approx(0.02)


# --- 6. tokens-basis ROI when cost is None ----------------------------------


def test_roi_tokens_basis_when_cost_none(tmp_path: Path) -> None:
    spec = _make_spec("case_01", "blind", "anon", "codex", "high", tmp_path)
    row = benchmark.score_run(spec, _run_result(), _answer_key())

    assert row["cost_usd"] is None
    assert row["roi_basis"] == "tokens"
    assert row["roi"] == round(row["aggregate"] / (3000 / 1000), 4)


# --- 7. event-type breakdown ------------------------------------------------


def test_event_type_breakdown() -> None:
    rows = [
        _row("case_01", "blind", "anon", 0.4, event_type="spring"),
        _row("case_02", "blind", "anon", 0.8, event_type="upthrust"),
    ]
    report = benchmark.aggregate_report(rows)
    group = report["groups"][0]
    assert group["event_types"]["spring"] == pytest.approx(0.4)
    assert group["event_types"]["upthrust"] == pytest.approx(0.8)


# --- 8. report has both deltas + ROI rank -----------------------------------


def test_render_report_has_both_deltas() -> None:
    rows = [
        _row("case_01", "blind", "anon", 0.5),
        _row("case_01", "blind", "revealed", 0.8),
        _row("case_01", "future_visible", "anon", 0.5),
    ]
    report = benchmark.aggregate_report(rows)
    md = benchmark.render_report_markdown(report)

    assert "Δleakage" in md
    assert "Δlookahead" in md
    assert "Rank by ROI" in md
    # n column present in the baseline table
    assert "| n |" in md


# --- 9. dry-run builds the manifest without network -------------------------


def test_dry_run_builds_manifest(tmp_path: Path) -> None:
    path = benchmark.build_matrix_manifest(["case_01", "case_02"], base_dir=tmp_path)

    assert path.exists()
    assert path.name == "benchmark_runs.json"
    data = json.loads(path.read_text())

    assert data["runs"]
    # empty result slots — code does not call the model
    assert all(r["analysis_output"] is None for r in data["runs"])
    assert all(r["usage"] is None for r in data["runs"])
    assert all(r["judge_verdict"] is None for r in data["runs"])
    assert "_instructions" in data


# --- bonus: ingest round-trips results into a report ------------------------


def test_ingest_round_trip(tmp_path: Path) -> None:
    answers_dir = tmp_path / "_answers"
    answers_dir.mkdir()
    (answers_dir / "case_01.answer.json").write_text(json.dumps(_answer_key()))

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    run_id = "case_01__blind__anon__claude-opus-4-8__high"
    (results_dir / f"{run_id}.json").write_text(
        json.dumps(
            {
                "analysis_output": _run_result()["analysis_output"],
                "usage": {"input_tokens": 1000, "output_tokens": 2000},
                "judge_verdict": _judge_verdict(0.8),
            }
        )
    )

    report = benchmark.ingest(results_dir, base_dir=tmp_path)

    assert report["n_rows"] == 1
    assert report["groups"][0]["model"] == "claude-opus-4-8"
    assert (tmp_path / "_benchmark" / "report.md").exists()
    assert (tmp_path / "_benchmark" / "report.json").exists()
