# Feature: End-to-End Skill Validation

## Summary

Validate GitHub issue #13 after reconciling stale issue text with the current
post-#8 repo state. The goal is not to modify the Wyckoff skill or wiki, but to
prove that the rebuilt skill contract works end to end against the canonical
test harness and to preserve a reusable regression baseline.

## User Story

As a Wyckoff AI maintainer,
I want the rebuilt `wyckoff-trader-skill` validated against canonical prompts,
So that future skill/wiki changes can be checked against a known behavioral
baseline before shipping.

## Problem Statement

Issue #13 was written before #8 landed. Several instructions in the original
body are now stale:

- It references `uncommon_concepts` from the original skill, but that source
  was removed in #8.
- It describes five ad-hoc wiki-only prompts, while the canonical harness is
  now `knowledge/wiki/scenarios/test-set.md` with eight prompts.
- It treats MCP validation as a hard requirement, while the current issue
  state needs a best-effort check because live data depends on local runtime and
  upstream availability.

## Solution Statement

Run a reconciled validation pass:

- Use `knowledge/wiki/scenarios/test-set.md` as the Phase A source of truth.
- Remap the stale `uncommon_concepts` requirement to existing wiki concept
  pages and the eight canonical prompts.
- Follow `skills/wyckoff-trader-skill/SKILL.md`: preload
  `knowledge/wiki/index.md`, then JIT-read only required wiki pages.
- Produce full expected-mode answers for all eight prompts and evaluate them
  against prompt `Must:` criteria, mode contract, provenance traceback, and
  hallucination checks.
- Treat Phase B MCP as best-effort: if the local kild can start the servers,
  run at least one live-data prompt; otherwise document exact missing env.
- Save reusable prompt files under `tests/prompts/` and the validation report
  under `tests/skill_validation_2026-06-10.md`.

## Metadata

| Field | Value |
| --- | --- |
| Source issue | #13, End-to-end skill validation against test prompts |
| PRD | `.claude/PRPs/prds/faza-1-skill-modernization.prd.md` |
| Feature type | `VALIDATION` |
| Complexity | `MEDIUM` |
| Dependencies | #8 complete; #9/#10/#11 closed for best-effort MCP check |
| Primary files | `tests/skill_validation_2026-06-10.md`, `tests/prompts/` |
| Scope exclusions | Do not modify `SKILL.md` or `knowledge/wiki/` |

## Reconciliation Decisions

| Stale issue instruction | Current decision |
| --- | --- |
| Use `uncommon_concepts` from original skill | Do not use removed source; rely on canonical wiki pages such as `concepts/principle-in-the-principle.md`, `concepts/two-way-market.md`, and the existing `test-set.md` prompts. |
| Pick five ad-hoc wiki-only prompts | Use all eight prompts from `knowledge/wiki/scenarios/test-set.md`: 3 concept, 3 diagnostic, 2 scenario. |
| Phase B must run after M4 | #9/#10/#11 are closed; run local MCP smoke checks and one live prompt if servers start cleanly. |
| Block issue on MCP live data | Do not block Phase A. Document MCP availability or missing dependencies separately. |

## Mandatory Reading

- `CLAUDE.md` — project language, review, wiki provenance, and no-trade-call
  rules.
- `skills/wyckoff-trader-skill/SKILL.md` — runtime model and mode contracts.
- `knowledge/wiki/index.md` — preload catalog for JIT page selection.
- `knowledge/wiki/scenarios/test-set.md` — canonical eight-prompt validation
  harness.
- `knowledge/wiki/scenarios/output-contract.md` — concept / diagnostic /
  scenario response contracts.
- `knowledge/wiki/scenarios/playbook-master.md` — scenario routing.
- Prompt-specific wiki pages referenced by `test-set.md`.

## Files to Change

| File | Change |
| --- | --- |
| `PRPs/plans/completed/13-skill-validation.plan.md` | Save this reconciled investigation and execution plan. |
| `tests/skill_validation_2026-06-10.md` | Add pass/fail report, full responses, MCP live check, findings, and recommendations. |
| `tests/prompts/README.md` | Explain reusable prompt baseline. |
| `tests/prompts/phase_a_wiki_only.md` | Copy canonical deterministic prompt set into reusable regression form. |
| `tests/prompts/phase_b_mcp_live.md` | Preserve non-deterministic live MCP prompts as best-effort checks. |

## NOT Building

- No changes to `skills/wyckoff-trader-skill/SKILL.md`.
- No changes to `knowledge/wiki/`.
- No automated grader implementation in this PR.
- No self-merge.

## Step-by-Step Tasks

1. Read project instructions and skill contract.
2. Fetch issue #13 and confirm stale parts.
3. Post reconciled plan as a GitHub issue comment.
4. Read `test-set.md` and required wiki pages through the index-first flow.
5. Produce and evaluate all eight Phase A responses.
6. Probe MCP server availability with `uv run --extra mcp`.
7. If possible, call MCP tools through stdio and run one live BTC 1d prompt.
8. Write validation report and reusable prompt files.
9. Run relevant MCP regression tests.
10. Open PR against `main` with Serbian body and English title.

## Validation Checklist

- [x] Reconciled plan posted to #13.
- [x] Phase A uses `knowledge/wiki/scenarios/test-set.md`.
- [x] All eight prompts evaluated.
- [x] Contract target met: 8/8 pass, above required 6/8.
- [x] MCP best-effort live check completed.
- [x] `tests/prompts/` baseline added.
- [x] `tests/skill_validation_2026-06-10.md` added.
- [x] `SKILL.md` and `knowledge/wiki/` left unchanged.
- [x] Relevant tests pass.

## Verification Commands

```bash
uv run pytest -q tests/test_market_data_server.py tests/test_chart_renderer.py tests/test_spread_chart_server.py
```

Observed result:

```text
36 passed
```

MCP smoke checks:

```bash
uv run --extra mcp python -m scripts.mcp.market_data_server
uv run --extra mcp python -m scripts.mcp.chart_renderer
```

Executed through MCP stdio client during validation; tools listed and live BTC
OHLCV / chart render calls succeeded.

## Results

- Phase A deterministic validation: **8/8 pass**.
- Phase B best-effort MCP validation: **pass** for market data and chart
  renderer in this kild, no API keys required.
- Follow-up finding: `events/no-shake-phase-c.md` has inline citations to
  `raw/book/pages/page_075.md` and `raw/book/pages/page_083.md` that are not
  mirrored in frontmatter `sources:`; fix separately.
