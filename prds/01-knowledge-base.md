# PRD-01: Knowledge Base & Skill Rebuild

**Status:** Active
**Created:** 2026-05-24
**Covers issues:** [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1), [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2), [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4), [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5), [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6), [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7), [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8), [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13)
**Milestones:** M1, M2, M3
**Related PRDs:** PRD-02 (trading use) — must land before [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) starts

---

## Problem

The current `skills/wyckoff-trader-skill` was hand-distilled from raw sources without provenance tracking:

- SKILL.md and the 5 reference `.md` files contain unsourced assertions — no way to trace a claim to a passage in the book or a Bruce Fraser article
- All chart images are missing — PDF→text discarded book figures, scraping discarded crypto archive HTML, Fraser image URLs are present in HTML but never downloaded (854 of them)
- The book text has OCR artifacts (`gre ater`, `selle rs`) from the lossy PDF→text conversion
- The skill cannot be updated mechanically — adding a new source means re-distilling by hand

Wyckoff is a visual method. Without charts and without provenance, the skill is a guessing machine on top of damaged sources.

## Why now

- Knowledge will be queried for years — the foundation compounds, so bad input today costs forever
- This repo is a fork of `naiemk/wyckoff-ai`; clean provenance is a precondition for contributing improvements upstream
- The `llm-wiki` method (Karpathy pattern) is mature enough to use as the KB backbone, with a runbook already at `~/.agent-runbooks/llm-wiki.md`

## Goals

1. **Complete the raw data layer** — recover all chart images, re-extract clean book text
2. **Build a provenance-tracked llm-wiki** — every wiki page cites its source(s); every source has at least one wiki page
3. **Reconstruct SKILL.md from the wiki** — every assertion in the skill traces back to a wiki page, which traces back to a raw source
4. **Make the skill mechanically updatable** — adding a new source = ingest into wiki = wiki entry available to skill

## Non-goals

- Live market analysis, OHLCV pulling, chart rendering — see [PRD-02](./02-trading-use.md) and M4 ([#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9), [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10), [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11), [#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12))
- New Wyckoff content or original research
- Multi-asset support beyond what existing sources cover (crypto + general equities references)
- Backwards-compatibility shims for the old reference file layout — the rebuild replaces it

## Success criteria

- Every assertion in `SKILL.md` carries a provenance link to a wiki page (form to be decided in [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8))
- `knowledge/wiki/log.md` lists all ~350 sources as ingested
- `knowledge/wiki/index.md` has entries in all domain folders defined by [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) schema
- `llm-wiki lint` passes with no critical gaps
- E2E validation ([#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13)) passes on 5 canonical prompts — no hallucinated phases, events, or schematics
- Re-extraction scripts ([#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2), [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4)) are idempotent — re-running reproduces identical output

## Scope (mapped to GitHub issues)

### M1 — Raw Data Ready

| Issue | Task | Model | Notes |
|---|---|---|---|
| [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1) | Raw data inventory + gap analysis | Sonnet | Mostly drafted in `.claude/HANDOFF.md`; formalize as `raw/INVENTORY.md` |
| [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) | Download Bruce Fraser images, rebuild MDs | Sonnet | 854 images across 243 articles, HTML already local |
| [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) | Re-scrape crypto archive with images | Sonnet | 46 posts; paywall-aware (no bypass) |
| [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) | Re-extract book from PDF (clean text + images) | Sonnet | **Hard prereq:** user locates PDF; gitignored |
| [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) | Vision caption pass for all images | Sonnet (orchestrator) | Caption model configurable; pilot 20 images before full pass |

### M2 — Knowledge Base Built

| Issue | Task | Model | Notes |
|---|---|---|---|
| [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) | Initialize llm-wiki + Wyckoff schema (CLAUDE.md) | Opus | Schema decisions propagate to entire wiki — high-leverage |
| [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) | Batched ingest of all sources (9 batches) | Hybrid | Opus on batches 1–3, 6 (conceptual); Sonnet on 4, 5, 7, 8, 9 (mechanical) |

### M3 — Skill Reconstructed

| Issue | Task | Model | Notes |
|---|---|---|---|
| [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) | Rebuild SKILL.md + scenario_playbook | Opus | **Blocked by PRD-02** — output contract depends on trading flow |
| [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) | End-to-end validation against test prompts | Opus | Phase A (wiki-only) is in PRD-01 scope; Phase B (MCP) is PRD-02 scope |

## Dependencies / sequencing

```
#1 (inventory) ─┐
                ├─ mostly parallel
#2 (Fraser)  ─┐ │
              ├─┤
#3 (crypto) ─┘ │
               │
#4 (book PDF) ─┘   ← blocked on user locating PDF
       │
       ▼
#5 (Vision captions) ← waits for #2, #3, #4 (full pass)
       │
       ▼
#6 (wiki schema)      ← Opus, defines taxonomy
       │
       ▼
#7 (batched ingest)   ← 9 batches, hybrid Opus/Sonnet
       │
       ▼
   ┌── PAUSE: PRD-02 must land here ──┐
       │
       ▼
#8 (rebuild SKILL.md) ← Opus, depends on PRD-02 decisions
       │
       ▼
#13 (E2E validation)  ← Opus, Phase A
```

## Key risks

| Risk | Mitigation |
|---|---|
| PDF cannot be located | [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) blocked; [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1)–[#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) proceed without it; book figures stay missing until resolved |
| Vision captions vague on Wyckoff structures (spring, upthrust, phase markers) | 20-image Sonnet pilot in [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5); escalate to Opus only if quality is materially worse |
| Wiki schema ([#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6)) organized around book taxonomy instead of query patterns | PRD-02 should land before [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8); if PRD-02 reveals schema mismatch, schema can be adjusted before ingest is too deep |
| Cost overrun on [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) | Hybrid Opus/Sonnet split per batch; start with Batch 1 as pilot — if Sonnet output is indistinguishable, fall back |
| Skill runtime architecture wrong (wiki shipped vs. distilled) | Three options A/B/C documented in [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8); decision deferred until wiki exists and PRD-02 lands |
| Paywall on crypto archive posts (vol 49–59) | No bypass; mark `WIKI_GAP` in [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3); decide on alternative sources only if gap is material |

## Open questions

1. **Skill bundle size:** if wiki ships with skill (option B in [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8)), how big is acceptable? Need to measure after [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7).
2. **Paywall scope:** are missing crypto archive vol 49–59 essential, or is the early-rotation/leadership material in vol 14–48 sufficient? Decide after [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) runs.
3. **Bruce Fraser thematic selection:** [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) currently ingests all 243 articles (batches 6–9). If quality drop is severe on Sonnet batches, may need to trim batch 9.
4. **Provenance format:** inline citations? footnotes? a separate provenance index? Decided in [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8).

## Cross-PRD relationship

| | PRD-01 (this) | PRD-02 (trading use) |
|---|---|---|
| Concerned with | What knowledge exists, how it's organized, how the skill cites it | How a trader interacts with the skill — questions, output format, scenario walkthroughs |
| Independence | Through M2 — schema in [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) is generic enough that trading-use decisions don't change ingest | N/A |
| Dependency | Provides the knowledge layer PRD-02 builds on | Defines the output contract [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) must implement |
| Natural pause point | After [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) completes, before [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) starts | PRD-02 lands during this pause |

## Out of scope (handled elsewhere)

- **Live market analysis** — MCP servers [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9), [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10), [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11), [#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12) under M4; design philosophy in PRD-02
- **E2E validation Phase B (with MCP)** — [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) Phase B; PRD-02 scope
- **Output format for live chart analysis** — PRD-02
- **Agent's trade-walkthrough flow** — PRD-02

## Change log

| Date | Change | Why |
|---|---|---|
| 2026-05-24 | Initial PRD | Formalize the rebuild plan after issue review |

---

**Maintenance note:** if an issue body changes materially (scope, dependency, milestone), update this PRD's relevant section. If this PRD changes (new risk, scope cut, new success criterion), update the affected issues. The two artifacts should stay in sync — issues are the executable unit, PRD is the why/how-they-fit-together view.
