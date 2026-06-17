"""Tests for the Phase 3 ground-truth eval set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval import build_eval_set
from scripts.eval.ground_truth_cases import (
    ANSWER_REQUIRED_FIELDS,
    EVENT_QUOTA,
    GROUND_TRUTH_CASES,
    REQUIRED_FIELDS,
    load_answer_key,
    make_placeholder_answers,
    validate_event_coverage,
)


def test_case_count_and_quota() -> None:
    assert len(GROUND_TRUTH_CASES) == sum(EVENT_QUOTA.values())
    validate_event_coverage()


def test_all_cases_have_required_fields() -> None:
    for case in GROUND_TRUTH_CASES:
        assert REQUIRED_FIELDS <= case.keys()
        assert not ANSWER_REQUIRED_FIELDS.intersection(case.keys())
        for field in REQUIRED_FIELDS:
            assert case[field]


def test_case_ids_unique() -> None:
    case_ids = [case["case_id"] for case in GROUND_TRUTH_CASES]
    assert len(case_ids) == len(set(case_ids))


def test_at_least_two_post_cutoff() -> None:
    post_cutoff = [
        case for case in GROUND_TRUTH_CASES if str(case["cutoff"]) >= "2026-01-01"
    ]
    assert len(post_cutoff) >= 2


def test_validate_rejects_bad_quota() -> None:
    bad_answers = make_placeholder_answers()
    bad_answers["case_01"]["event_type"] = "failed_signal"

    with pytest.raises(ValueError, match="Event quota mismatch"):
        validate_event_coverage(answers=bad_answers)


def test_validate_rejects_missing_answer() -> None:
    answers = make_placeholder_answers()
    answers.pop("case_01")

    with pytest.raises(ValueError, match="case_01 missing answer key entry"):
        validate_event_coverage(answers=answers)


def test_load_answer_key_from_private_json(tmp_path: Path) -> None:
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_01",
                        "event_type": "spring",
                        "realized_direction": "up",
                        "decisive": True,
                        "ground_truth": "Private answer text",
                    }
                ]
            }
        )
        + "\n"
    )

    answers = load_answer_key(answers_path)

    assert answers["case_01"]["ground_truth"] == "Private answer text"


def test_build_eval_set_dry_run_generates_all(tmp_path: Path) -> None:
    build_eval_set.run(dry_run=True, base_dir=tmp_path)

    answers_dir = tmp_path / "_answers"
    assert answers_dir.exists()

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    manifest_text = manifest_path.read_text()
    assert "ground_truth" not in manifest_text
    assert "realized_direction" not in manifest_text
    manifest = json.loads(manifest_text)
    assert len(manifest["cases"]) == len(GROUND_TRUTH_CASES)

    for case in GROUND_TRUTH_CASES:
        case_dir = tmp_path / case["case_id"]
        assert case_dir.exists()
        assert (case_dir / "candles.json").exists()
        assert (case_dir / "chart.png").exists()

        answer_path = answers_dir / f"{case['case_id']}.answer.json"
        assert answer_path.exists()
        assert not answer_path.is_relative_to(case_dir)
        answer = json.loads(answer_path.read_text())
        assert answer["event_type"]
        assert answer["realized_direction"] in {"up", "down", "none"}
        assert isinstance(answer["decisive"], bool)
        assert "not the real eval ground truth" in answer["ground_truth"]
        assert len(answer["post_t_candles"]) == 21


def test_build_eval_set_real_run_requires_private_answers(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Answer key file not found"):
        build_eval_set.run(dry_run=False, base_dir=tmp_path, answers_path=tmp_path / "missing.json")
