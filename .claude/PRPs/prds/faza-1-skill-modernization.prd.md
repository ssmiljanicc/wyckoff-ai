# Faza 1 — Skill Modernization (Upstream Contribution)

## Problem Statement

The existing `skills/wyckoff-trader-skill/` (forked from `naiemk/wyckoff-ai`) was hand-distilled from raw sources without provenance, has OCR-damaged book text, and is missing all chart images that Wyckoff methodology depends on. Every claim in SKILL.md and the 5 distilled reference files is unsourced, so the skill cannot be verified or mechanically updated as new sources arrive.

## Evidence

- **Book**: 248 page `.txt` files with confirmed OCR artifacts (`gre ater`, `selle rs`, `tra ding`, `wycko ff`); 0 images preserved from the PDF conversion. (`raw/INVENTORY.md`)
- **Crypto archive (Rutigliano)**: 46 `.md` posts text-only, 0 images, 10 posts confirmed paywalled (`raw/crypto_archive/manifest.json`).
- **Bruce Fraser**: 243 `.md` posts with 855 unique chart image URLs in HTML — none downloaded prior to issue #2.
- **Distilled refs** (book_foundations, crypto_adaptations, etc.) total ~5,800 words but reference files have no inline citations back to the raw corpus.
- Original skill applies its 9-section output contract to every query — even definitional queries like "what is a spring?" — which is broken UX for non-scenario questions.

## Proposed Solution

Rebuild the skill with provenance-tracked knowledge base (llm-wiki pattern), recovered chart images with Vision captions, clean book text re-extracted from PDF, and a mode-aware output contract that distinguishes scenario / concept / diagnostic queries. The skill remains tightly aligned with the original repo's vision (educational Wyckoff analyst) so the improvements can be contributed back upstream as a single PR.

## Key Hypothesis

We believe **a provenance-tracked, image-complete, mode-aware Wyckoff skill** will **measurably improve scenario quality and skill maintainability** for **Wyckoff practitioners and learners**. We'll know we're right when **the E2E validation (#13) passes on all 8 canonical prompts AND a PR is opened against `naiemk/wyckoff-ai` with a clean diff**.

## What We're NOT Building

- **Live market data integration** — defers to Faza 2 (MCP layer)
- **Paper trading, scanning, signal generation** — defers to Faza 3
- **ML classifiers, embeddings, similarity search** — defers to Faza 3
- **Backwards-compatibility shims** for the old `references/` layout — the wiki replaces it
- **Multi-asset/multi-market beyond crypto** — out of scope (original repo was crypto-focused)

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Wiki pages with full provenance | 100% of ~70 required pages (per `/CLAUDE.md` §3) | `llm-wiki lint` returns no `WIKI_GAP` for required pages |
| Chart images recovered | ≥ 1,200 (Fraser 855 + Crypto 190 + Book ~200) | Filesystem inventory after #2/#3/#4/#5 |
| Vision captions written | ≥ 95% of images have non-empty alt text | grep over raw/ for empty `![](` |
| E2E validation passes | All 8 canonical prompts in `scenarios/test-set.md` produce contract-compliant output | Manual review documented in `tests/skill_validation_<date>.md` |
| Upstream PR opened | 1 PR to `naiemk/wyckoff-ai` | GitHub PR link |

## Open Questions

- [ ] Should the wiki ship bundled in the skill bundle (option A/B in #8) or fetched on demand? → decide in #8
- [ ] After the upstream PR is opened, do we maintain the fork relationship or detach (`git remote remove upstream` + GitHub "unfork" via support)?
- [ ] Are paywalled crypto archive posts (10 of 46) a material gap or acceptable loss?
- [ ] Does the mode discriminator (scenario / concept / diagnostic) survive user-testing, or does it need refinement?

---

## Users & Context

**Primary User**
- **Who**: Solo trader / Wyckoff practitioner watching crypto charts, intermediate-to-advanced Wyckoff vocabulary
- **Current behavior**: Reads charts manually, consults the book + Fraser articles for setup confirmation, sometimes uses ChatGPT for second opinions
- **Trigger**: Sees a chart structure that "looks like accumulation" and wants disciplined confirmation before committing
- **Success state**: Receives a 9-section scenario tree with explicit trigger + invalidation + alternate — feels equipped to decide

**Secondary User**
- **Who**: Wyckoff student at intermediate level
- **Current behavior**: Studies the book + watches Fraser videos; struggles to apply concepts to live structures
- **Trigger**: Encounters an unfamiliar event term ("what's a no-shake Phase C?")
- **Success state**: Gets concise concept-mode answer with wiki citations + 1 worked example

**Job to Be Done**

When **I'm analyzing a crypto chart structure**, I want to **get a disciplined Wyckoff scenario** so I can **make an informed go/wait/no-trade decision without curve-fitting**.

**Non-Users**
- Bot / algo signal-feed consumers (no automated buy/sell)
- Complete Wyckoff beginners (skill assumes vocabulary; they should read the book first)
- Non-crypto traders (corpus is crypto-focused, though methodology transfers)

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Provenance-tracked wiki (llm-wiki pattern) | Every claim traces to source → maintainability |
| Must | Recovered chart images with Vision captions | Wyckoff is visual; captions enable semantic comparison |
| Must | Clean book text (PDF re-extract) | OCR artifacts must not propagate into wiki |
| Must | Three-mode output contract (scenario / concept / diagnostic) | One-size-fits-all is broken UX |
| Must | E2E validation against 8 canonical prompts | Without test set, claim of "improvement" is unverifiable |
| Should | Vision caption pass on book figures | Adds visual semantic layer the original lacked |
| Should | Updated `agents/openai.yaml` to reflect new modes | Existing integration point should stay current |
| Could | Hybrid Opus/Sonnet ingest cost optimization | Quality vs. budget tradeoff documented |
| Won't | Live data integration | Defers to Faza 2 — out of scope for upstream contribution |
| Won't | Paper trading / signals | Defers to Faza 3 — never was in original repo vision |

### MVP Scope

Minimum to validate hypothesis and open upstream PR:

1. Raw data complete: Fraser images (#2 ✓), crypto rescrape (#3 ✓), book PDF re-extract (#4 — blocked on PDF)
2. Vision captions on at least Fraser + crypto images (#5)
3. Wiki initialized + at least book chapters 1–13 ingested (subset of #7)
4. SKILL.md rewritten with three modes and wiki references (#8)
5. E2E validation passes on at least 6 of 8 prompts (#13)

### User Flow

Critical path for scenario-mode query:

```
User → "Build a Wyckoff scenario for BTC 1d at $42k after 6-week range"
       ↓
Skill loads wiki index → identifies relevant concept/event/structure pages
       ↓
Agent reads pages with citations → builds 9-section output
       ↓
Output cites wiki pages → user can drill down to source
```

For concept mode: User asks "what is X?" → skill identifies concept-mode → returns short definition + 1–2 wiki citations + related concepts.

---

## Technical Approach

**Feasibility**: HIGH

**Architecture Notes**
- Three-layer pattern: raw sources (immutable) → wiki (LLM-maintained markdown) → skill (procedural prompt). Documented in `/CLAUDE.md`.
- Runtime architecture choice (A/B/C) deferred to #8 — recommendation in PRD-01a is option B (ship wiki + preload `index.md`).
- All wiki conventions in `/CLAUDE.md` schema, generic llm-wiki mechanics in `~/.agent-runbooks/llm-wiki.md`.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| PDF cannot be located | Medium | User must source; book images still missing if unsolved |
| Vision captions vague on Wyckoff structures | Medium | 20-image pilot in #5 before full pass; escalate to Opus if needed |
| Wiki schema wrong for downstream queries | Low | Schema in `/CLAUDE.md` matches existing distilled refs taxonomy — already validated |
| Cost overrun on #7 batched ingest | Medium | Hybrid Opus/Sonnet split documented; Batch 1 pilot decides full strategy |
| Upstream maintainer rejects PR | Low | Improvements are additive (wiki + modes), original skill structure preserved |

---

## Implementation Phases

<!-- STATUS legend: pending / in-progress / complete -->

| # | Phase | Milestone | Description | Status |
|---|-------|-----------|-------------|--------|
| 1 | Raw data ready | M1 | Inventory, scrape Fraser, rescrape crypto, re-extract book, Vision captions | in-progress (3 of 5 done) |
| 2 | Knowledge base built | M2 | Init wiki + schema (`/CLAUDE.md`), batched ingest of all sources | in-progress (init done, ingest pending) |
| 3 | Skill reconstructed | M3 | Rewrite SKILL.md with modes, regenerate scenario playbook, E2E validation | pending |
| 4 | Upstream contribution | NEW | Open PR to `naiemk/wyckoff-ai`, address review feedback, merge, unfork | pending |

### Phase Details

**Phase 1: Raw data ready (M1)**
- **Goal**: All chart images recovered, book text clean, Vision captions on every image
- **Issues**: [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1) ✓, [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) ✓, [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) ✓, [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) (blocked on PDF), [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5)
- **Success signal**: `raw/INVENTORY.md` shows 100% completeness across all sources

**Phase 2: Knowledge base built (M2)**
- **Goal**: All raw sources ingested into wiki with provenance; ~70 required pages exist per `/CLAUDE.md` §3
- **Issues**: [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) ✓, [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- **Success signal**: `llm-wiki lint` passes with no critical gaps; `knowledge/wiki/log.md` lists all batches

**Phase 3: Skill reconstructed (M3)**
- **Goal**: SKILL.md and scenario_playbook regenerated from wiki; mode discriminator implemented; E2E validation passes
- **Issues**: [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8), [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13), trading-use methodology decisions (mode contracts, boundaries)
- **Success signal**: Validation report committed; 6+ of 8 prompts produce contract-compliant output

**Phase 4: Upstream contribution (new milestone)**
- **Goal**: PR opened to `naiemk/wyckoff-ai` with the improvements; merge resolution; decide on fork relationship
- **New issues** (created with this PRD): "Open upstream PR", "Decide on fork detach"
- **Success signal**: PR link recorded; if merged, decide on detach; if not, document why and continue as detached fork

### Parallelism Notes

- Phase 1 sub-tasks (#2, #3, #4) are independent and can run in parallel kilds (proven during 2026-05-24 session — #2 and #3 completed in parallel kild sessions)
- Phase 2 ingest (#7) batches can run in parallel if dispatched to multiple agents with non-overlapping source paths
- Phase 3 is sequential after Phase 2

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| KB method | llm-wiki (Karpathy pattern) | Vector embeddings, ad-hoc references | Provenance built-in, no embedding infra, scales to ~350 sources |
| Wiki folder layout | Wyckoff-specific (concepts/, events/, structures/, crypto/, scenarios/, sources/) | llm-wiki default (topics/systems/comparisons) | Domain-fit aids both ingest and skill navigation |
| Mode discriminator | Three modes (scenario/concept/diagnostic) | Single 9-section contract for all | Existing skill applies 9 sections to "what is X?" — broken UX |
| Ingest model strategy | Hybrid Opus (conceptual batches) + Sonnet (mechanical batches) | All-Opus, all-Sonnet | Quality where it compounds, cost savings where mechanical |
| Image bundling threshold | <100MB commit, ≥100MB gitignore | All commit, all gitignore | Reproducibility for small sets, repo health for large sets |
| Paywall handling | No bypass; mark `WIKI_GAP` | Try alt sources, manual scraping | Respect source; gaps surface during lint |

---

## Research Summary

**Market Context**
- The original `naiemk/wyckoff-ai` skill is a public fork target for Wyckoff-aware AI assistance; few public Wyckoff skills exist
- Karpathy's llm-wiki pattern is mature, used in similar provenance-critical domains (research notes, codebase wikis)
- Bruce Fraser's StockCharts archive is one of the largest applied Wyckoff corpora available publicly

**Technical Context**
- Repo is a fork of `naiemk/wyckoff-ai`; clean provenance is a precondition for upstream PR
- Existing skill content (~5,800 distilled words) is high-quality and largely preserves correctly with mechanical migration
- 6 of 8 system prompts in #13 should pass even without #4 book re-extraction (vocabulary is already captured in distilled refs)

---

## Linked GitHub Issues

| Issue | Title | Status |
|---|---|---|
| [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1) | Raw data inventory and gap analysis | ✓ Closed |
| [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) | Download Bruce Fraser chart images | ✓ Closed |
| [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) | Re-scrape crypto archive posts | ✓ Closed |
| [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) | Re-extract book from PDF | Open (blocked on PDF) |
| [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) | Vision caption pass | Open |
| [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) | Initialize llm-wiki + schema | ✓ Closed |
| [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) | Batched ingest of all sources | Open |
| [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) | Rebuild SKILL.md + scenario_playbook | Open |
| [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) | E2E skill validation | Open |
| NEW | Open upstream PR to naiemk/wyckoff-ai | To be created with this PRD |
| NEW | Decide fork detach after upstream merge | To be created with this PRD |

---

*Generated: 2026-05-24*
*Status: ACTIVE — Phase 1 in progress, see `Implementation Phases` table*
