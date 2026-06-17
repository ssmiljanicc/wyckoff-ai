# Implementation Report

**Plan**: `.claude/PRPs/plans/faza-4-phase-2-lookahead-probe-prep.plan.md`
**Source PRD**: `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 2
**Branch**: `kild/feature/66-lookahead-probe-prep`
**Date**: 2026-06-17
**Status**: COMPLETE

## Summary

Implementiran reproduciblian eval snapshot generator sa dual-mode podrškcom (`blind` / `future_visible`), deterministična anonimizacija bez curenja, lookahead probe scaffold sa 3 slučaja, i `vertical_lines` anotacija u rendereru. Pilot refaktorisan da koristi generator. Svi 187 testova zeleni.

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| --- | --- | --- | --- |
| Complexity | MEDIUM | MEDIUM | Tačna procena; najviše vremena na dizajn anonimizacije i layout answer-key/manifest |
| Confidence | high | high | Sve komponente robustne; nijedan gotcha nije iznenadio |

## Tasks Completed

| # | Task | File | Status |
| --- | --- | --- | --- |
| 1 | `vertical_lines` anotacija | `scripts/mcp/chart_renderer.py` | ✅ DONE |
| 2 | Anonimizator | `scripts/eval/snapshot_builder.py` | ✅ DONE |
| 3 | Neutralan eval render-stil + x-osa | `scripts/eval/snapshot_builder.py` | ✅ DONE |
| 4 | Dual-mode generator + snapshot layout | `scripts/eval/snapshot_builder.py` | ✅ DONE |
| 5 | Lookahead probe scaffold | `scripts/eval/lookahead_probe.py` | ✅ DONE |
| 6 | Refactor pilota | `scripts/eval/pilot_blind_slice.py` | ✅ DONE |
| 7 | gitignore | `.gitignore` | ✅ DONE |
| 8 | Testovi | `tests/test_snapshot_builder.py`, `tests/test_chart_renderer.py` | ✅ DONE |

## Validation Results

| Check | Result | Details |
| --- | --- | --- |
| Type check | N/A | Nema mypy u pyproject.toml extras |
| Lint | N/A | Nema ruff/flake8 u CI |
| Tests (targeted) | PASS | `pytest tests/test_snapshot_builder.py tests/test_chart_renderer.py -q` → 32 passed |
| Tests (full suite) | PASS | `pytest -q` → 187 passed |
| gitignore | PASS | `git check-ignore data/eval/x scripts/eval/pilot_out/x` → oba ignorisana |
| Probe dry-run | PASS | `python -m scripts.eval.lookahead_probe --dry-run` → 3 slučaja × 2 moda OK |

## Files Changed

| File | Action | Notes |
| --- | --- | --- |
| `scripts/mcp/chart_renderer.py` | edit | +`VerticalLineAnnotation` TypedDict, +`vertical_lines` u `ChartAnnotations`, `normalize_annotations`, `_apply_annotations` |
| `scripts/eval/snapshot_builder.py` | create | `anonymize`, `render_eval_chart`, `build_snapshot`, `SnapshotResult` |
| `scripts/eval/lookahead_probe.py` | create | 3 probe slučaja × 2 moda, `_DryRunClient`, `--dry-run` flag, `probe_result.json` šablon |
| `scripts/eval/pilot_blind_slice.py` | edit (refactor) | thin wrapper oko `build_snapshot`; uklonjen sirov httpx i curljive konstante |
| `.gitignore` | edit | +`data/eval/`, +`scripts/eval/pilot_out/` |
| `tests/test_snapshot_builder.py` | create | 8 testova (anonymize + build_snapshot + layout) |
| `tests/test_chart_renderer.py` | edit | +3 testa za `vertical_lines` |

## Deviations from Plan

Jedna manja devijacija:

- **Task 4 — limit u future_visible modu**: Plan kaže `end_time = cutoff + future_bars*tf_ms` ali ne specificira eksplicitno limit. Implementiran `limit = n_bars + future_bars` (umesto samo `n_bars`) da se dobije **isti `n_bars` sveća PRE T plus `future_bars` sveća POSLE T**. Ovo je logičniji dizajn (analitičar vidi isti blind prozor + vidljiva budućnost). `t_marker_index = n_bars - 1` (poslednja blind svećica).

## Issues Encountered

Nijedan bloker. Sve komponente bile čiste.

## Tests Written

| Test File | Test Cases |
| --- | --- |
| `tests/test_snapshot_builder.py` | `test_anonymize_pushes_to_unusual_range`, `test_anonymize_deterministic`, `test_anonymize_different_cases_different_coefs`, `test_x_axis_not_real_calendar`, `test_blind_mode_excludes_future`, `test_future_visible_extends_and_marks`, `test_answer_key_outside_case_dir`, `test_manifest_has_no_truth`, `test_snapshot_result_paths_exist` |
| `tests/test_chart_renderer.py` | `test_vertical_lines_annotation`, `test_vertical_lines_out_of_range_raises`, `test_normalize_annotations_vertical_lines_missing_index` |

## Next Steps

- Pokrenuti `git commit` i napraviti PR za ovaj branch
- Izvršiti probe runbook: pustiti slep subagent na `case_01`/`case_02`/`case_03` blind pa future_visible; popuniti `data/eval/_answers/probe_result.json`
- Na osnovu gate odluke: ako `delta≈0 && !fv_leaked` → Phase 3 koristi živi `end_time` + as-of instrukciju; inače → pun snapshot blinding
- Kreirati PR: `/prp-pr`
