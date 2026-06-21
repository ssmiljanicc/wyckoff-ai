# Implementation Report

**Plan**: `PRPs/plans/codex-filesystem-isolation-private-benchmark.plan.md`
**Source Issue**: #82
**Branch**: `feature/82-codex-filesystem-isolation`
**Worktree**: `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/feature-82-codex-filesystem-isolation`
**Date**: 2026-06-21
**Status**: PARTIAL

## Summary

Implementiran je Docker containment za Codex privatni benchmark. Pinovani image pokreće Codex CLI `0.141.0` kao non-root UID 10001; launcher mount-uje samo read-only case root i read-only auth fajl, koristi read-only root filesystem, `--cap-drop ALL` i `no-new-privileges`, prevodi samo proverene case putanje u `/workspace` i odbija escape/symlink/`--add-dir` pokušaje.

Canary, adapter, version/help/auth preflight i runtime koriste isti `CODEX_EXECUTION_PROFILE`. Persisted verdict je proširen live execution identity-jem: exact image ID/digest, container OS/arch i wrapped CLI verzija. Fingerprint koristi logički wrapper identitet i SHA-256 launcher izvora, pa je stabilan između worktree-jeva, ali svaka stvarna launcher izmena poništava PASS.

Offline testovi, Docker build, wrapped version/help/auth i fail-closed preflight prolaze. Status je `PARTIAL` isključivo zato što naplativi `canary_codex_image --confirm` i mali upareni Claude/Codex benchmark nisu autorizovani niti pokrenuti. Gate ostaje zatvoren i plan nije arhiviran.

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| --- | --- | --- | --- |
| Complexity | HIGH | HIGH | Container path translation, auth mount, portable fingerprint i live image identity morali su ostati konzistentni kroz canary/preflight/runtime |
| Confidence | 8/10 | 9/10 za kod; real isolation PASS pending | 324 offline testa i stvarni Docker smoke prolaze; model command-event dokaz još zahteva odobren plaćeni poziv |

## Tasks Completed

| # | Task | File | Status |
| --- | --- | --- | --- |
| 1 | Pinovani Codex eval image | `docker/codex-eval/Dockerfile` | COMPLETE |
| 2 | Hardened launcher i path translation | `scripts/eval/codex_container.py` | COMPLETE |
| 3 | Profile + execution identity verdict | `scripts/eval/isolation_state.py` | COMPLETE |
| 4 | Shared wrapper za run/version/help/auth | `scripts/eval/runtime_adapters.py`, `canary_common.py` | COMPLETE |
| 5 | Container-aware canary/verdict | `scripts/eval/canary_codex_image.py` | COMPLETE (real call pending) |
| 6 | Offline security regresije | `tests/test_codex_container.py` i postojeći testovi | COMPLETE |
| 7 | Operator runbook | `runbooks/faza-4-eval-orchestrator.md` | COMPLETE (status namerno `REAL CANARY PENDING`) |
| 8 | Real isolation canary | gitignored verdict | BLOCKED — zahteva eksplicitno odobrenje troška |
| 9 | Mali paired Claude/Codex canary | runtime artifacts | BLOCKED — zavisi od Task 8 i odobrenja troška |
| 10 | Sanity/security review | kompletan diff | COMPLETE za offline scope |

## Validation Results

| Check | Result | Details |
| --- | --- | --- |
| Type/compile | PASS | Python import/pytest collection uspešni |
| Lint | PASS | `git diff --check` |
| Ciljani testovi | PASS | 61 test, container/isolation/runtime/canary/orchestrator |
| Full tests | PASS | `uv run --extra mcp pytest -q` — 324 passed |
| Docker build | PASS | `linux/arm64`, digest-pinovan Node base, Codex `0.141.0` |
| Execution identity | PASS | Docker `linux/arm64`, exact image ID/digest i `codex-cli 0.141.0` dobijeni kroz launcher |
| Capability/auth smoke | PASS | Wrapped `--version`, `exec --help`, `login status` (`Logged in using ChatGPT`) |
| Canary dry-run | PASS | Bez model poziva; wrapper argv i outside sentinel odvojeni |
| Fail-closed smoke | PASS | Bez verdicta `CodexRuntimeAdapter.preflight` vraća `RuntimeUnavailable` |
| Real isolation canary | NOT RUN | Nije bilo eksplicitnog odobrenja naplativog poziva |
| Paired benchmark | NOT RUN | Zavisi od real isolation PASS-a |

## Files Changed

| File | Action | Notes |
| --- | --- | --- |
| `docker/codex-eval/Dockerfile` | Add | Pinovani image, exact Codex CLI, non-root user |
| `scripts/eval/codex_container.py` | Add | Docker boundary, mount allowlist, path translation, identity probe |
| `scripts/eval/isolation_state.py` | Modify | Docker profile, portable source-bound fingerprint, execution identity verdict |
| `scripts/eval/runtime_adapters.py` | Modify | Svi Codex putevi kroz shared wrapper |
| `scripts/eval/canary_codex_image.py` | Modify | Wrapped CLI + live identity u verdictu |
| `scripts/eval/canary_common.py` | Modify | CLI version helper prima kompletan argv |
| `tests/test_codex_container.py` | Add | Mount, hardening, escape i identity testovi |
| `tests/test_isolation_state.py` | Modify | Identity mismatch i portable wrapper fingerprint |
| `tests/test_runtime_adapters.py` | Modify | Wrapped argv/preflight i identity fixtures |
| `runbooks/faza-4-eval-orchestrator.md` | Modify | Build/smoke/canary/gate procedura |
| `PRPs/plans/codex-filesystem-isolation-private-benchmark.plan.md` | Add | Canonical plan kopiran u izolovani worktree |

## Deviations from Plan

- Task 1:
  - Plan said: entrypoint kopira auth secret u writable `CODEX_HOME`, zatim pokreće non-root Codex.
  - Actual: Docker Desktop mapira read-only host auth bind na container UID 10001, pa se auth mount-uje direktno u efemerni `CODEX_HOME`; image od prvog procesa radi kao non-root.
  - Reason: `--cap-drop ALL` ispravno sprečava root entrypoint da naknadno menja UID/ownership. Direktan non-root start je jednostavniji i uži security profil.
- Task 6:
  - Plan said: izmeniti `tests/test_eval_orchestrator.py` za dodatni injected-adapter dokaz.
  - Actual: fajl nije menjan; postojeći orchestrator testovi i `_safe_copy` ugovor već dokazuju da analyst root ne sadrži answer key, dok novi launcher testovi dokazuju jedine host mount-ove.
  - Reason: dodatni test bi duplirao postojeću odgovornost bez nove regresione vrednosti.
- Tasks 8–9 nisu izvršeni zbog potrebnog novog odobrenja troška; bezbedni fail-closed state je očuvan.

## Issues Encountered

- Prvi entrypoint dizajn nije mogao da radi sa `--cap-drop ALL`: capability-less root nije mogao da upiše/chown-uje UID 10001 tmpfs niti da pozove `setresuid`. Rešenje je direktan `USER codex` image i read-only auth bind koji Docker Desktop mapira na container UID.
- Apsolutni KILD worktree path u `wrapper_argv` bi dao različit fingerprint posle merge-a. Rešeno je logičkim `wrapper_id` plus SHA-256 sadržaja launchera.

## Tests Written

| Test File | Test Cases |
| --- | --- |
| `tests/test_codex_container.py` | Tačno dva host bind mount-a, read-only/hardening flagovi, path translation, outside/symlink/`--add-dir`/missing-auth reject, immutable image identity |
| `tests/test_isolation_state.py` | Image identity mismatch, missing identity, logical wrapper portability |
| `tests/test_runtime_adapters.py` | Wrapper-prefixed runtime argv i identity-bound verdict fixtures |

## Next Steps

1. Operator odobrava tačno jedan naplativi poziv.
2. Pokrenuti `uv run python -m scripts.eval.canary_codex_image --confirm --model gpt-5.4 --effort low`.
3. Ako PASS: upisati dokazanu host/container platformu i exact image identity u runbook/report, zatim pokrenuti mali isti-case Claude/Codex canary uz zasebno odobrenje.
4. Posle oba PASS-a promeniti report na `COMPLETE` i arhivirati plan u `PRPs/plans/completed/`.
