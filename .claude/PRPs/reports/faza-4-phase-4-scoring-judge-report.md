# Implementation Report

**Plan**: `.claude/PRPs/plans/faza-4-phase-4-scoring-judge.plan.md`
**Source Issue**: N/A
**Branch**: `kild/feature/66-scoring-judge`
**Worktree**: `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/feature-66-scoring-judge`
**Date**: 2026-06-17
**Status**: COMPLETE

## Summary

Implemented the Phase 4 eval scoring layer in `scripts/eval/scoring.py`: deterministic forecast replay, wait-case handling, isolated judge payload preparation, judge rubric prompt, weighted aggregation, and `_scores/<case_id>.score.json` persistence. Added focused tests covering replay behavior, SL-first tie-break, direction scoring, judge isolation, wait NA handling, aggregate NA skipping, score output location, strict judge verdict validation, old answer-key fallback behavior, and stronger leakage scrubbing.

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| --- | --- | --- | --- |
| Complexity | MEDIUM-HIGH | MEDIUM | The deterministic replay and persistence were straightforward; the main care was making NA dimensions explicit without treating them as zero. |
| Confidence | Not specified | High | Targeted scoring tests, review-regression probes, and full test suite pass. |

## Tasks Completed

| # | Task | File | Status |
| --- | --- | --- | --- |
| 1 | Rubric constants, dimension methods/weights, `DimensionScore`, `ScoreRecord` | `scripts/eval/scoring.py` | COMPLETE |
| 2 | Deterministic forecast replay for direction, trigger, invalidation | `scripts/eval/scoring.py` | COMPLETE |
| 3 | Wait rule with NA deterministic dimensions | `scripts/eval/scoring.py` | COMPLETE |
| 4 | Isolated judge input and `JUDGE_PROMPT_TEMPLATE` | `scripts/eval/scoring.py` | COMPLETE |
| 5 | Weighted score aggregation and `_scores/` persistence | `scripts/eval/scoring.py` | COMPLETE |
| 6 | Focused scoring and review-regression tests | `tests/test_scoring.py` | COMPLETE |
| 7 | `.gitignore` check | `.gitignore` | COMPLETE, no change needed because `data/eval/` is already ignored |

## Validation Results

| Check | Result | Details |
| --- | --- | --- |
| Import smoke | PASS | `uv run --extra mcp python -c "import scripts.eval.scoring as s; assert s.JUDGE_PROMPT_TEMPLATE and s.prepare_judge_input"` |
| Targeted deterministic tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -k deterministic -q` -> 3 passed |
| Targeted wait tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -k wait -q` -> 1 passed |
| Targeted isolation tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -k isolation -q` -> 1 passed |
| Targeted aggregate/persist tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -k "aggregate or persist" -q` -> 2 passed |
| Scoring tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -q` -> 11 passed |
| Review regression probes | PASS | Manual probes for old-key fallback, incomplete judge verdict rejection, and judge leakage scrubbing now behave as expected. |
| Full tests | PASS | `uv run --extra mcp pytest -q` -> 199 passed |

## Files Changed

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/scoring.py` | Added | Scoring rubric, deterministic replay, wait rule, stricter judge isolation, strict judge verdict validation, aggregation, and `_scores/` writer. |
| `tests/test_scoring.py` | Added | 11 tests for deterministic replay, SL-first tie-break, direction scoring, judge isolation, wait NA behavior, old-key fallback, incomplete judge verdict rejection, aggregation, and persistence. |
| `.gitignore` | Checked | No edit required; `data/eval/` already covers `_scores/`. |

## Deviations from Plan

- Task: `DimensionScore` schema
  - Plan said: `score: float 0..1`.
  - Actual: `score: float | None` plus `status: "scored" | "na"`.
  - Reason: Wait-rule NA dimensions must be serializable and must not be treated as zero in aggregation.
- Task: Source PRD update
  - Plan said: Update the source PRD phase when applicable.
  - Actual: No PRD update performed.
  - Reason: `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` is not present in this worktree.

## Issues Encountered

- The first `-k isolation` validation selected no tests because the test name did not include `isolation`; renamed it to match the plan command.
- The judge isolation test initially searched the whole returned object for the word `candles`, but the prompt intentionally tells the judge not to use candles. The test now checks the actual payload data (`output` and `answer_key`) for forbidden keys and paths.
- Independent PR review found three issues: incomplete judge verdicts were accepted, missing `decisive` could trigger wait NA behavior for old answer keys, and sanitizer coverage was too key-name dependent. Fixed by requiring all judge dimensions, distinguishing missing from explicit `decisive: false`, allowlisting analyst-output fields, and redacting path-like strings plus candle-shaped payloads.

## Tests Written

| Test File | Test Cases |
| --- | --- |
| `tests/test_scoring.py` | deterministic trigger hit, same-bar SL-first invalidation, direction correctness, invalidation before trigger, judge input isolation, value/path/candle scrubbing, wait rule NA, old-key fallback, aggregate skips NA, incomplete judge verdict rejection, score written outside case dir. |

## Next Steps

- Review implementation.
- Create PR with `$prp-pr`.
- Continue with the next PRD phase when applicable.
