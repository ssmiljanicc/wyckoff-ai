# Implementation Report

**Plan**: `.claude/PRPs/plans/faza-4-phase-3-ground-truth-set.plan.md`
**Source PRD**: `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 3 (nije prisutan u ovom worktree-u)
**Branch**: `kild/feature/66-ground-truth-set`
**Worktree**: `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/feature-66-ground-truth-set`
**Date**: 2026-06-17
**Status**: COMPLETE

## Summary

Implementiran je Phase 3 ground-truth eval set: 10 kuriranih crypto slučajeva, 4 post-cutoff slučaja posle 2026-01-01, multi-symbol pokrivenost (BTC, ETH, LINK, ADA), generator blind snapshot-a i answer-key proširenje sa `event_type`, `realized_direction`, `decisive` i `post_t_candles`. Posle review-a za PR #70, realni answer key je izmešten iz commitovanog koda u privatni JSON (`data/eval/_answers/ground_truth_answers.json` ili `--answers-path`), dok `--dry-run` koristi sintetičke placeholder odgovore.

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| --- | --- | --- | --- |
| Complexity | MEDIUM | MEDIUM | Kod je mali; najviše pažnje je otišlo na contract answer key-a i proveru da post-2026 slučajevi imaju dostupne buduće sveće. |
| Confidence | high | medium-high | Validacija i real-mode smoke check prolaze; domain etikete su kurirane iz OHLCV ishoda, ali bez eksternog analyst review-a. |

## Tasks Completed

| # | Task | File | Status |
| --- | --- | --- | --- |
| 1 | Case-lista metadata + kvota | `scripts/eval/ground_truth_cases.py` | DONE |
| 2 | Validator pokrivenosti | `scripts/eval/ground_truth_cases.py` | DONE |
| 3 | Generator sa privatnim answer source-om | `scripts/eval/build_eval_set.py` | DONE |
| 4 | Answer-key extra fields + `post_t_candles` | `scripts/eval/snapshot_builder.py` | DONE |
| 5 | Testovi | `tests/test_ground_truth_cases.py` | DONE |
| 6 | Stock WIKI_GAP/TODO | `scripts/eval/ground_truth_cases.py` | DONE |
| 7 | Review fixes: short-history fail-fast + answer leak removal | multiple | DONE |

## Validation Results

| Check | Result | Details |
| --- | --- | --- |
| Type check | N/A | Nema mypy/pyright komande u planu ili `pyproject.toml`. |
| Lint | N/A | Nema ruff/flake8 komande u planu ili `pyproject.toml`. |
| Import/count | PASS | `uv run --extra mcp python -c "from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES; print(len(GROUND_TRUTH_CASES))"` → `10` |
| Coverage validator | PASS | `uv run --extra mcp python -c "from scripts.eval.ground_truth_cases import validate_event_coverage; validate_event_coverage(); print('ok')"` → `ok` |
| Targeted tests | PASS | `uv run --extra mcp pytest tests/test_ground_truth_cases.py -q` → 9 passed |
| Snapshot regression tests | PASS | `uv run --extra mcp pytest tests/test_snapshot_builder.py -q` → 11 passed |
| Full tests | PASS | `uv run --extra mcp pytest -q` → 198 passed |
| Generator dry-run | PASS | `uv run --extra mcp python -m scripts.eval.build_eval_set --dry-run` → 10 cases generated with expected event coverage |
| Real-mode smoke check | PASS | `build_eval_set.run(dry_run=False, base_dir=<TemporaryDirectory>, answers_path=<TemporaryFile>)` fetched Binance OHLCV for all 10 cases and generated all outputs |

## Files Changed

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/ground_truth_cases.py` | create | Public case metadata, `EVENT_QUOTA`, private answer loading, placeholder answers, `validate_event_coverage()`, stock WIKI_GAP/TODO |
| `scripts/eval/build_eval_set.py` | create | CLI/run loop for blind eval set generation, `--dry-run`, private `--answers-path`, coverage summary |
| `scripts/eval/snapshot_builder.py` | edit | Added `answer_extra`, `include_post_t_candles`, coefficient reuse helper, and short-history fail-fast |
| `tests/test_ground_truth_cases.py` | create | 9 tests for quota, required fields, duplicate IDs, post-cutoff coverage, bad quota, missing answers, answer loading, dry-run output contract, and missing real answers |
| `tests/test_snapshot_builder.py` | edit | Added blind short-history regression test |

## Deviations from Plan

- Task: Files to change
  - Plan said: create `ground_truth_cases.py`, create `build_eval_set.py`, create `tests/test_ground_truth_cases.py`.
  - Actual: also edited `scripts/eval/snapshot_builder.py`.
  - Reason: Answer-key contract requires `post_t_candles` anonymized with the same `coef_meta` as the blind snapshot. Centralizing this in `build_snapshot()` avoids duplicating anonymization logic in the generator and keeps `_answers/` isolation in one place.

- Task: `GROUND_TRUTH_CASES` shape
  - Plan said: include full `ground_truth` text in committed `GROUND_TRUTH_CASES`.
  - Actual: committed `GROUND_TRUTH_CASES` now contains only case metadata; answer fields are loaded from a private JSON file.
  - Reason: PR review identified full ground-truth text in repository history as a blind-eval integrity risk.

- Task: PRD update
  - Plan said: update relevant implementation phase when complete.
  - Actual: no PRD update made.
  - Reason: `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` is referenced by the plan but is not present in this worktree.

## Issues Encountered

Nema blokera. `data/eval/` je ignorisan output; dry-run validation ga puni lokalno, ali implementacione promene su samo u kodu, testovima, reportu i arhiviranom planu.

## Tests Written

| Test File | Test Cases |
| --- | --- |
| `tests/test_ground_truth_cases.py` | `test_case_count_and_quota`, `test_all_cases_have_required_fields`, `test_case_ids_unique`, `test_at_least_two_post_cutoff`, `test_validate_rejects_bad_quota`, `test_build_eval_set_dry_run_generates_all` |

## Next Steps

- Uraditi code review pre merge-a.
- Kreirati PR: `$prp-pr`
- Phase 4 scoring može da koristi `data/eval/_answers/<case>.answer.json` contract sa `post_t_candles`.
