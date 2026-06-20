"""Tests for the source-anchored ground-truth eval set (issue #76)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.eval import build_eval_set
from scripts.eval.ground_truth_cases import (
    ANSWER_REQUIRED_FIELDS,
    GROUND_TRUTH_CASES,
    PLACEHOLDER_MARKER,
    PROVENANCE_REQUIRED_FIELDS,
    REQUIRED_FIELDS,
    angle_answer_metadata,
    load_answer_key,
    make_placeholder_answers,
    validate_event_coverage,
)


# --- fixtures: a self-contained repo-like raw tree under tmp_path ------------


def _make_raw_tree(
    tmp_path: Path,
    *,
    md_lines: list[str] | None = None,
    image_disk: str = "raw/crypto_archive/images/vol/img.png",
    extra_images: list[str] | None = None,
) -> Path:
    """Create raw/crypto_archive/posts/post.md + image(s) under tmp_path."""
    md_lines = md_lines or [
        "Expert analysis of the chart right edge.",
        "![](../images/vol/img.png)",
    ]
    posts = tmp_path / "raw/crypto_archive/posts"
    posts.mkdir(parents=True, exist_ok=True)
    (posts / "post.md").write_text("\n".join(md_lines) + "\n")
    for rel in [image_disk, *(extra_images or [])]:
        img = tmp_path / rel
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"\x89PNG fake")
    return tmp_path


def _case(**overrides: Any) -> dict[str, Any]:
    case = {
        "case_id": "c1",
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "cutoff": "2020-11-13",
        "n_bars": 120,
    }
    case.update(overrides)
    return case


def _answer(**overrides: Any) -> dict[str, Any]:
    answer = {
        "event_type": "spring",
        "realized_direction": "up",
        "decisive": True,
        "analysis_mode": "forward_looking",
        "ground_truth": "Faithful summary of the cited excerpt.",
        "expert_author": "Alessio Rutigliano",
        "source_path": "raw/crypto_archive/posts/post.md",
        "source_url": "https://example.com/post",
        "source_image_path": "raw/crypto_archive/images/vol/img.png",
        "source_excerpt_location": {"start_line": 1, "end_line": 2},
        "expert_structure": "not_stated",
        "expert_phase": "not_stated",
        "expert_event": "spring",
        "expert_scenario": "not_stated",
        "expert_trigger": "not_stated",
        "expert_invalidation": "not_stated",
        "reconstruction_notes": "Symbol/timeframe/cutoff confirmed from the chart title.",
    }
    answer.update(overrides)
    return answer


def _validate_one(tmp_path: Path, case: dict, answer: dict) -> None:
    validate_event_coverage(
        cases=[case], answers={case["case_id"]: answer}, raw_root=tmp_path
    )


# --- registry shape ----------------------------------------------------------


def test_registry_is_non_empty_and_variable_count() -> None:
    # No hard-coded count, no event quota — just a non-empty source-anchored set.
    assert len(GROUND_TRUTH_CASES) >= 1


def test_all_cases_have_required_fields_and_no_answer_leakage() -> None:
    for case in GROUND_TRUTH_CASES:
        assert REQUIRED_FIELDS <= case.keys()
        # Evaluation/answer fields must never live in the public case registry.
        assert not ANSWER_REQUIRED_FIELDS.intersection(case.keys())
        assert not PROVENANCE_REQUIRED_FIELDS.intersection(case.keys())
        for field in REQUIRED_FIELDS:
            assert case[field]


def test_case_ids_unique() -> None:
    case_ids = [case["case_id"] for case in GROUND_TRUTH_CASES]
    assert len(case_ids) == len(set(case_ids))


# --- happy paths -------------------------------------------------------------


def test_valid_forward_case_passes(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    _validate_one(tmp_path, _case(), _answer())


def test_valid_retrospective_case_passes(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    _validate_one(
        tmp_path,
        _case(),
        _answer(analysis_mode="retrospective", realized_direction="not_applicable"),
    )


# --- answer field validation -------------------------------------------------


def test_rejects_missing_answer(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="missing answer key entry"):
        validate_event_coverage(cases=[_case()], answers={}, raw_root=tmp_path)


def test_rejects_empty_event_type(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="event_type must be non-empty"):
        _validate_one(tmp_path, _case(), _answer(event_type="  "))


def test_rejects_unknown_analysis_mode(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="analysis_mode must be one of"):
        _validate_one(tmp_path, _case(), _answer(analysis_mode="sideways"))


def test_rejects_forward_bad_realized_direction(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="forward realized_direction"):
        _validate_one(tmp_path, _case(), _answer(realized_direction="not_applicable"))


def test_rejects_retrospective_with_directional_realized(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="retrospective realized_direction"):
        _validate_one(
            tmp_path, _case(), _answer(analysis_mode="retrospective", realized_direction="up")
        )


# --- provenance / source-anchor validation -----------------------------------


def test_rejects_missing_provenance_fields(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    answer = _answer()
    del answer["source_image_path"]
    with pytest.raises(ValueError, match="missing provenance fields"):
        _validate_one(tmp_path, _case(), answer)


def test_rejects_empty_not_stated_sentinel(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="must be a non-empty value or 'not_stated'"):
        _validate_one(tmp_path, _case(), _answer(expert_scenario="   "))


def test_rejects_absolute_source_path(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="must be repo-relative"):
        _validate_one(tmp_path, _case(), _answer(source_path="/etc/passwd"))


def test_rejects_path_escape(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="must resolve inside"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_path="raw/crypto_archive/../../secret.md"),
        )


def test_rejects_missing_source_image(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="source_image_path does not exist"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_image_path="raw/crypto_archive/images/vol/missing.png"),
        )


def test_rejects_source_image_not_referenced_in_excerpt(tmp_path: Path) -> None:
    # other.png exists on disk but the excerpt references img.png, not other.png.
    _make_raw_tree(
        tmp_path, extra_images=["raw/crypto_archive/images/vol/other.png"]
    )
    with pytest.raises(ValueError, match="not referenced by the Markdown"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_image_path="raw/crypto_archive/images/vol/other.png"),
        )


def test_rejects_image_ref_outside_excerpt_range(tmp_path: Path) -> None:
    # Image IS referenced in the file, but on line 3 — outside the cited 1–2
    # excerpt. The boundary slice lines[start-1:end] must not see it.
    _make_raw_tree(
        tmp_path,
        md_lines=[
            "Expert analysis paragraph.",
            "More commentary, no image here.",
            "![](../images/vol/img.png)",
        ],
    )
    with pytest.raises(ValueError, match="not referenced by the Markdown"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_excerpt_location={"start_line": 1, "end_line": 2}),
        )


def test_rejects_excerpt_beyond_file_length(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="exceeds file length"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_excerpt_location={"start_line": 1, "end_line": 999}),
        )


def test_rejects_invalid_excerpt_bounds(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    with pytest.raises(ValueError, match="1 <= start_line <= end_line"):
        _validate_one(
            tmp_path,
            _case(),
            _answer(source_excerpt_location={"start_line": 0, "end_line": 2}),
        )


# --- set-level rules ---------------------------------------------------------


def test_rejects_empty_case_set() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_event_coverage(cases=[], answers={})


def test_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    _make_raw_tree(tmp_path)
    a = _answer()
    with pytest.raises(ValueError, match="Duplicate case_id"):
        validate_event_coverage(
            cases=[_case(), _case()], answers={"c1": a}, raw_root=tmp_path
        )


# --- placeholders are dry-run only -------------------------------------------


def test_placeholders_rejected_in_real_run() -> None:
    placeholders = make_placeholder_answers()
    assert all(PLACEHOLDER_MARKER in a for a in placeholders.values())
    with pytest.raises(ValueError, match="placeholder"):
        validate_event_coverage(answers=placeholders, allow_placeholders=False)


def test_placeholders_accepted_when_allowed() -> None:
    placeholders = make_placeholder_answers()
    # No raw_root / provenance needed: placeholders skip the source-anchor gate.
    validate_event_coverage(answers=placeholders, allow_placeholders=True)


# --- angle metadata propagation allowlist ------------------------------------


def test_angle_answer_metadata_carries_analysis_mode_not_provenance(tmp_path: Path) -> None:
    metadata = angle_answer_metadata(_answer())
    assert metadata == {
        "event_type": "spring",
        "realized_direction": "up",
        "decisive": True,
        "analysis_mode": "forward_looking",
    }
    # Provenance and reconstruction never propagate.
    for field in PROVENANCE_REQUIRED_FIELDS:
        assert field not in metadata


# --- build + load ------------------------------------------------------------


def test_load_answer_key_from_private_json(tmp_path: Path) -> None:
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "c1",
                        "event_type": "spring",
                        "realized_direction": "up",
                        "decisive": True,
                        "analysis_mode": "forward_looking",
                        "ground_truth": "Private answer text",
                    }
                ]
            }
        )
        + "\n"
    )
    answers = load_answer_key(answers_path)
    assert answers["c1"]["ground_truth"] == "Private answer text"
    assert answers["c1"]["analysis_mode"] == "forward_looking"


def test_load_answer_key_from_bare_list(tmp_path: Path) -> None:
    # The top-level bare-list shape (not wrapped in {"cases": ...}).
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "c1",
                    "event_type": "spring",
                    "realized_direction": "up",
                    "decisive": True,
                    "analysis_mode": "forward_looking",
                    "ground_truth": "List-shape answer text",
                }
            ]
        )
    )
    answers = load_answer_key(answers_path)
    assert answers["c1"]["ground_truth"] == "List-shape answer text"
    assert "case_id" not in answers["c1"]  # popped into the dict key


def test_build_eval_set_dry_run_generates_all(tmp_path: Path) -> None:
    build_eval_set.run(dry_run=True, base_dir=tmp_path)

    answers_dir = tmp_path / "_answers"
    assert answers_dir.exists()

    manifest_path = tmp_path / "manifest.json"
    manifest_text = manifest_path.read_text()
    # No truth or answer labels leak into the public manifest.
    assert "ground_truth" not in manifest_text
    assert "realized_direction" not in manifest_text
    manifest = json.loads(manifest_text)
    assert len(manifest["cases"]) == len(GROUND_TRUTH_CASES)

    for case in GROUND_TRUTH_CASES:
        case_dir = tmp_path / case["case_id"]
        assert (case_dir / "candles.json").exists()
        assert (case_dir / "chart.png").exists()

        answer_path = answers_dir / f"{case['case_id']}.answer.json"
        assert answer_path.exists()
        assert not answer_path.is_relative_to(case_dir)
        answer = json.loads(answer_path.read_text())
        assert answer["event_type"]
        assert answer["realized_direction"] in {"up", "down", "none", "not_applicable"}
        assert answer["analysis_mode"] in {"forward_looking", "retrospective"}
        assert isinstance(answer["decisive"], bool)
        assert "not the real eval ground truth" in answer["ground_truth"]
        assert len(answer["post_t_candles"]) == 21
        # Provenance never reaches the angle answer key.
        for field in PROVENANCE_REQUIRED_FIELDS:
            assert field not in answer


def test_build_eval_set_real_run_requires_private_answers(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Answer key file not found"):
        build_eval_set.run(
            dry_run=False, base_dir=tmp_path, answers_path=tmp_path / "missing.json"
        )
