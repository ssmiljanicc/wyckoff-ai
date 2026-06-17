"""Curated Phase 3 case metadata for blind Wyckoff evals.

The real answer key is intentionally loaded from an ignored local JSON file,
not committed in this module. Keeping full ground truth out of repo history
preserves the blind-eval workflow for analysts who receive the repository.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


EVENT_QUOTA = {
    "spring": 2,
    "upthrust": 2,
    "sos_sow": 2,
    "redistribution_as_accumulation": 1,
    "phase_b_noise": 1,
    "failed_signal": 2,
}

REQUIRED_FIELDS = {
    "case_id",
    "symbol",
    "timeframe",
    "cutoff",
    "n_bars",
}

ANSWER_REQUIRED_FIELDS = {
    "event_type",
    "realized_direction",
    "decisive",
    "ground_truth",
}

REALIZED_DIRECTIONS = {"up", "down", "none"}
POST_KNOWLEDGE_CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)


# WIKI_GAP: stock/equity case zahteva non-Binance adapter; v1 ostaje crypto-only.
# TODO: Add stock/equity diversity after a non-Binance OHLCV adapter exists.
GROUND_TRUTH_CASES: list[dict[str, Any]] = [
    {
        "case_id": "case_01",
        "symbol": "ETHUSDT",
        "timeframe": "1d",
        "cutoff": "2020-03-13",
        "n_bars": 180,
    },
    {
        "case_id": "case_02",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2026-03-29",
        "n_bars": 180,
    },
    {
        "case_id": "case_03",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2021-11-10",
        "n_bars": 180,
    },
    {
        "case_id": "case_04",
        "symbol": "ADAUSDT",
        "timeframe": "1d",
        "cutoff": "2024-03-13",
        "n_bars": 180,
    },
    {
        "case_id": "case_05",
        "symbol": "LINKUSDT",
        "timeframe": "1d",
        "cutoff": "2023-10-23",
        "n_bars": 180,
    },
    {
        "case_id": "case_06",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2022-06-13",
        "n_bars": 180,
    },
    {
        "case_id": "case_07",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2022-08-15",
        "n_bars": 180,
    },
    {
        "case_id": "case_08",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2026-04-27",
        "n_bars": 180,
    },
    {
        "case_id": "case_09",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2026-02-06",
        "n_bars": 180,
    },
    {
        "case_id": "case_10",
        "symbol": "ADAUSDT",
        "timeframe": "1d",
        "cutoff": "2026-05-10",
        "n_bars": 180,
    },
]


def make_placeholder_answers(
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return synthetic answers for dry-run and tests only.

    These preserve the output contract and event-quota shape without committing
    real eval answers.
    """
    selected = GROUND_TRUTH_CASES if cases is None else cases
    event_sequence = [
        event_type
        for event_type, count in EVENT_QUOTA.items()
        for _ in range(count)
    ]
    directions = {
        "spring": "up",
        "upthrust": "down",
        "sos_sow": "up",
        "redistribution_as_accumulation": "down",
        "phase_b_noise": "none",
        "failed_signal": "down",
    }
    return {
        str(case["case_id"]): {
            "event_type": event_type,
            "realized_direction": directions[event_type],
            "decisive": event_type != "phase_b_noise",
            "ground_truth": (
                f"Dry-run placeholder answer for {case['case_id']}; "
                "not the real eval ground truth."
            ),
        }
        for case, event_type in zip(selected, event_sequence, strict=True)
    }


def load_answer_key(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load private answer metadata from a local JSON file.

    Supported shapes:
    - {"case_01": {"event_type": ..., ...}, ...}
    - {"cases": [{"case_id": "case_01", "event_type": ..., ...}, ...]}
    """
    answer_path = Path(path)
    if not answer_path.exists():
        raise FileNotFoundError(
            f"Answer key file not found: {answer_path}. "
            "Create it outside git, e.g. data/eval/_answers/ground_truth_answers.json, "
            "or run with --dry-run for placeholder answers."
        )
    raw = json.loads(answer_path.read_text())
    if isinstance(raw, dict) and isinstance(raw.get("cases"), list):
        return _answers_from_list(raw["cases"])
    if isinstance(raw, list):
        return _answers_from_list(raw)
    if isinstance(raw, dict):
        return {str(case_id): dict(answer) for case_id, answer in raw.items()}
    raise ValueError(f"Unsupported answer key shape in {answer_path}")


def validate_event_coverage(
    cases: list[dict[str, Any]] | None = None,
    answers: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Validate required fields, event quotas, uniqueness, and post-cutoff coverage."""
    selected = GROUND_TRUTH_CASES if cases is None else cases
    selected_answers = make_placeholder_answers(selected) if answers is None else answers
    expected_count = sum(EVENT_QUOTA.values())
    if len(selected) != expected_count:
        raise ValueError(f"Expected {expected_count} cases, got {len(selected)}")

    case_ids: list[str] = []
    event_counts: Counter[str] = Counter()
    post_cutoff_count = 0

    for index, case in enumerate(selected, start=1):
        missing = REQUIRED_FIELDS - case.keys()
        case_id = str(case.get("case_id", f"<case #{index}>"))
        if missing:
            raise ValueError(f"{case_id} missing required fields: {sorted(missing)}")

        case_ids.append(case_id)
        answer = selected_answers.get(case_id)
        if answer is None:
            raise ValueError(f"{case_id} missing answer key entry")
        missing_answer_fields = ANSWER_REQUIRED_FIELDS - answer.keys()
        if missing_answer_fields:
            raise ValueError(
                f"{case_id} answer missing required fields: {sorted(missing_answer_fields)}"
            )

        event_type = str(answer["event_type"])
        event_counts[event_type] += 1
        if event_type not in EVENT_QUOTA:
            raise ValueError(f"{case_id} has unknown event_type: {event_type!r}")

        if answer["realized_direction"] not in REALIZED_DIRECTIONS:
            raise ValueError(
                f"{case_id} realized_direction must be one of {sorted(REALIZED_DIRECTIONS)}"
            )
        if not isinstance(answer["decisive"], bool):
            raise ValueError(f"{case_id} decisive must be bool")
        if not str(answer["ground_truth"]).strip():
            raise ValueError(f"{case_id} ground_truth must be non-empty")
        if not str(case["symbol"]).strip():
            raise ValueError(f"{case_id} symbol must be non-empty")
        if not str(case["timeframe"]).strip():
            raise ValueError(f"{case_id} timeframe must be non-empty")
        if int(case["n_bars"]) <= 0:
            raise ValueError(f"{case_id} n_bars must be positive")

        cutoff = _parse_cutoff(case["cutoff"], case_id=case_id)
        if cutoff >= POST_KNOWLEDGE_CUTOFF:
            post_cutoff_count += 1

    duplicate_ids = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"Duplicate case_id values: {duplicate_ids}")

    if dict(event_counts) != EVENT_QUOTA:
        raise ValueError(f"Event quota mismatch: expected {EVENT_QUOTA}, got {dict(event_counts)}")

    if post_cutoff_count < 2:
        raise ValueError(f"Expected at least 2 post-cutoff cases, got {post_cutoff_count}")


def _answers_from_list(raw_answers: list[Any]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    for index, raw_answer in enumerate(raw_answers, start=1):
        if not isinstance(raw_answer, dict):
            raise ValueError(f"Answer #{index} must be an object")
        if "case_id" not in raw_answer:
            raise ValueError(f"Answer #{index} missing case_id")
        answer = dict(raw_answer)
        case_id = str(answer.pop("case_id"))
        answers[case_id] = answer
    return answers


def _parse_cutoff(value: Any, *, case_id: str) -> datetime:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{case_id} cutoff must be a positive millisecond epoch")
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

    raw = str(value)
    if "T" not in raw and " " not in raw:
        raw = raw + "T00:00:00"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{case_id} has invalid cutoff: {value!r}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
