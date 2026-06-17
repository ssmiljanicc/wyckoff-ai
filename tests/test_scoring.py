"""Tests for scripts/eval/scoring.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.scoring import (
    JUDGE_PROMPT_TEMPLATE,
    combine_scores,
    prepare_judge_input,
    score_deterministic,
    write_score,
)


def _answer_key(**overrides) -> dict:
    base = {
        "case_id": "case_01",
        "symbol": "BTCUSDT",
        "cutoff": "2020-01-01",
        "coef_meta": {"price_coef": 0.1},
        "ground_truth": "Accumulation spring followed by markup.",
        "event_type": "spring",
        "realized_direction": "up",
        "decisive": True,
        "post_t_candles": [
            {"open_time": 1, "high": 101.0, "low": 96.0, "close": 100.0},
            {"open_time": 2, "high": 112.0, "low": 101.0, "close": 111.0},
        ],
        "chart_path": "/tmp/data/eval/case_01/chart.png",
        "candles": [{"high": 100.0, "low": 90.0}],
    }
    base.update(overrides)
    return base


def _judge_verdict(**overrides) -> dict:
    verdict = {
        "structure": {"score": 1.0, "rationale": "Correct accumulation framing."},
        "phase": {"score": 0.8, "rationale": "Phase C/D boundary is acceptable."},
        "event": {"score": 1.0, "rationale": "Spring is semantically correct."},
        "narrative_quality": {"score": 0.6, "rationale": "Good but incomplete."},
        "calibration": {"score": 0.7, "rationale": "Confidence is plausible."},
    }
    verdict.update(overrides)
    return verdict


def test_deterministic_trigger_hit() -> None:
    result = score_deterministic(
        direction="long",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(),
    )

    assert result["direction_correct"] is True
    assert result["trigger_hit"] is True
    assert result["invalidation_hit"] is False
    assert result["outcome"] == "hit_tp"
    assert result["bars_to_resolution"] == 2
    assert result["dimensions"]["trigger"]["score"] == 1.0


def test_deterministic_same_bar_both_touched_resolves_invalidation() -> None:
    result = score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(
            post_t_candles=[
                {"open_time": 1, "high": 112.0, "low": 94.0, "close": 100.0},
            ]
        ),
    )

    assert result["trigger_hit"] is False
    assert result["invalidation_hit"] is True
    assert result["invalidation_respected"] is False
    assert result["outcome"] == "hit_sl"
    assert result["dimensions"]["invalidation"]["score"] == 0.0


def test_deterministic_direction_correct() -> None:
    correct = score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(realized_direction="up"),
    )
    wrong = score_deterministic(
        direction="down",
        trigger_level=90.0,
        invalidation_level=105.0,
        answer_key=_answer_key(realized_direction="up"),
    )

    assert correct["direction_correct"] is True
    assert correct["dimensions"]["direction"]["score"] == 1.0
    assert wrong["direction_correct"] is False
    assert wrong["dimensions"]["direction"]["score"] == 0.0


def test_invalidation_respected() -> None:
    result = score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(
            post_t_candles=[
                {"open_time": 1, "high": 102.0, "low": 94.0, "close": 96.0},
                {"open_time": 2, "high": 115.0, "low": 100.0, "close": 114.0},
            ]
        ),
    )

    assert result["trigger_hit"] is False
    assert result["invalidation_hit"] is True
    assert result["invalidation_respected"] is False


def test_judge_input_isolation_excludes_chart() -> None:
    payload = prepare_judge_input(
        {
            "analysis_id": "a1",
            "structure": "accumulation",
            "chart_path": "/tmp/data/eval/case_01/chart.png",
            "forecast": {"direction": "up", "trigger": 110.0, "invalidation": 95.0},
            "nested": {"candles_path": "/tmp/data/eval/case_01/candles.json"},
        },
        _answer_key(
            case_dir="/tmp/data/eval/case_01",
            post_t_candles=[{"high": 120.0, "low": 90.0}],
        ),
    )

    payload_text = json.dumps({"output": payload["output"], "answer_key": payload["answer_key"]})
    assert "chart_path" not in payload_text
    assert "candles" not in payload_text
    assert "case_dir" not in payload_text
    assert "/tmp/data/eval/case_01" not in payload_text
    assert payload["answer_key"]["ground_truth"]
    assert JUDGE_PROMPT_TEMPLATE in payload["prompt"]


def test_judge_input_isolation_scrubs_path_values_and_candle_shapes() -> None:
    payload = prepare_judge_input(
        {
            "notes": {"source": "/tmp/data/eval/case_01/chart.png"},
            "evidence": [{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
            "data": [{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        },
        _answer_key(),
    )

    payload_text = json.dumps({"output": payload["output"], "answer_key": payload["answer_key"]})
    assert "/tmp/data/eval/case_01/chart.png" not in payload_text
    assert "case_01" not in payload_text
    assert "chart.png" not in payload_text
    assert '"high"' not in payload_text
    assert payload["output"]["notes"]["source"] == "[REDACTED_PATH]"
    assert payload["output"]["evidence"] == "[REDACTED_CANDLES]"
    assert "data" not in payload["output"]


def test_wait_rule_not_penalized() -> None:
    result = score_deterministic(
        direction="wait",
        trigger_level=None,
        invalidation_level=None,
        confidence=0.2,
        answer_key=_answer_key(realized_direction="none", decisive=False, post_t_candles=[]),
    )

    assert result["wait_case"] is True
    assert result["direction_correct"] is None
    assert result["dimensions"]["direction"]["status"] == "na"
    assert result["dimensions"]["trigger"]["score"] is None
    assert result["dimensions"]["invalidation"]["score"] is None


def test_missing_decisive_wait_uses_old_key_fallback_not_wait_na() -> None:
    result = score_deterministic(
        direction="wait",
        confidence=0.2,
        answer_key={
            "case_id": "old_case",
            "future_visible": [{"open_time": 1, "high": 120.0, "low": 100.0}],
        },
    )

    assert result["wait_case"] is False
    assert result["used_fallback"] is True
    assert result["dimensions"]["direction"]["status"] == "scored"
    assert result["dimensions"]["trigger"]["status"] == "scored"
    assert result["dimensions"]["invalidation"]["status"] == "scored"


def test_aggregate_skips_na() -> None:
    deterministic = score_deterministic(
        direction="wait",
        confidence=0.2,
        answer_key=_answer_key(realized_direction="none", decisive=False, post_t_candles=[]),
    )
    record = combine_scores(
        deterministic,
        {
            "structure": {"score": 1.0, "rationale": "Correct."},
            "phase": {"score": 0.0, "rationale": "Wrong."},
            "event": {"score": 0.0, "rationale": "Wrong."},
            "narrative_quality": {"score": 0.0, "rationale": "Weak."},
            "calibration": {"score": 0.0, "rationale": "Wrong confidence."},
        },
    )

    assert record["wait_case"] is True
    assert record["aggregate"] == pytest.approx(0.2308)


def test_combine_scores_rejects_incomplete_judge_verdict() -> None:
    deterministic = score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(),
    )

    with pytest.raises(ValueError, match="missing required dimensions"):
        combine_scores(deterministic, {})

    with pytest.raises(ValueError, match="missing required dimensions"):
        combine_scores(deterministic, {"structure": {"score": 1.0, "rationale": "ok"}})


def test_persist_score_written_outside_case_dir(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_01"
    case_dir.mkdir()
    deterministic = score_deterministic(
        direction="up",
        trigger_level=110.0,
        invalidation_level=95.0,
        answer_key=_answer_key(),
    )
    record = combine_scores(deterministic, _judge_verdict(), analysis_id="analysis_01")

    path = write_score(record, tmp_path)

    assert path == tmp_path / "_scores" / "case_01.score.json"
    assert not path.is_relative_to(case_dir)
    data = json.loads(path.read_text())
    assert data["case_id"] == "case_01"
    assert data["analysis_id"] == "analysis_01"
