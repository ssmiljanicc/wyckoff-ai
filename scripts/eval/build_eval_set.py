"""Generate the Phase 3 blind ground-truth eval set."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.eval.ground_truth_cases import (
    GROUND_TRUTH_CASES,
    load_answer_key,
    make_placeholder_answers,
    validate_event_coverage,
)
from scripts.eval.lookahead_probe import _DryRunClient
from scripts.eval.snapshot_builder import DEFAULT_BASE_DIR, build_snapshot

DEFAULT_ANSWERS_PATH = DEFAULT_BASE_DIR / "_answers" / "ground_truth_answers.json"


def run(
    dry_run: bool = False,
    base_dir: Path = DEFAULT_BASE_DIR,
    answers_path: Path | None = None,
) -> None:
    answers = (
        make_placeholder_answers()
        if dry_run
        else load_answer_key(answers_path or DEFAULT_ANSWERS_PATH)
    )
    validate_event_coverage(answers=answers)
    client: Any = _DryRunClient() if dry_run else None
    generated = 0

    for case in GROUND_TRUTH_CASES:
        case_id = case["case_id"]
        answer = answers[case_id]
        try:
            build_snapshot(
                symbol=case["symbol"],
                timeframe=case["timeframe"],
                cutoff=case["cutoff"],
                n_bars=case["n_bars"],
                mode="blind",
                case_id=case_id,
                client=client,
                ground_truth=answer["ground_truth"],
                answer_extra={
                    "event_type": answer["event_type"],
                    "realized_direction": answer["realized_direction"],
                    "decisive": answer["decisive"],
                },
                include_post_t_candles=True,
                base_dir=base_dir,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to build {case_id} ({case['symbol']} {case['cutoff']}): {exc}"
            ) from exc
        generated += 1

    coverage = Counter(answers[case["case_id"]]["event_type"] for case in GROUND_TRUTH_CASES)
    print(f"[eval-set] generated {generated} blind cases in {base_dir}")
    print("[eval-set] event coverage:")
    for event_type, count in sorted(coverage.items()):
        print(f"  - {event_type}: {count}")
    if dry_run:
        print("[eval-set] dry-run complete — stub client used, no network calls made")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 ground-truth eval set")
    parser.add_argument("--dry-run", action="store_true", help="Use stub client (no network)")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help="Output directory for eval cases",
    )
    parser.add_argument(
        "--answers-path",
        type=Path,
        default=None,
        help=(
            "Private answer-key JSON path. Defaults to "
            "data/eval/_answers/ground_truth_answers.json outside git."
        ),
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, base_dir=args.base_dir, answers_path=args.answers_path)


if __name__ == "__main__":
    main()
