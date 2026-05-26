# CLAUDE.md — Wyckoff AI Project Instructions and Wiki Schema

This file is **two things in one**:

1. **Project-level instructions** for Claude and other LLM agents working on this repo (communication style, language, review process — see §0 below)
2. **Domain schema** for the llm-wiki knowledge base at `knowledge/wiki/` (folder layout, vocabulary, provenance rules — see §1 onward)

Generic wiki mechanics (init, ingest, query, lint, image ingest) live in the universal llm-wiki runbook at `~/.agent-runbooks/llm-wiki.md`. This file does NOT duplicate those — it only encodes Wyckoff-specific decisions on top of the runbook.

**When in doubt:** read the runbook for *how to operate*, read this file for *what counts as right for Wyckoff*.

---

## 0. Project communication and process rules

### 0.1 Default language: Serbian

Sve odgovore korisniku, svi commit komentari koji se obraćaju ljudskom čitaocu, svi GitHub issue body-jevi i komentari, svi PRD-ovi i planski dokumenti se pišu na **srpskom jeziku** kao default.

**Kada se koristi engleski (izuzeci):**
- Tehnički termini bez prirodnog srpskog ekvivalenta (npr. `OHLCV`, `regression`, `embedding`)
- Imena fajlova, putanja, koda, varijabli, ID-eva
- Originalni naslovi izvora (knjige, članka)
- Kratke citacije iz koda ili dokumentacije
- Strukturirani identifikatori (issue brojevi, milestone imena tipa `M5: Trading Simulation MCP` — ovi se zadržavaju jer su key-evi u GitHub API-ju)

**Pravilo za engleske termine u srpskom tekstu:**

Kada se pojavi engleski tehnički termin prvi put u dokumentu/odgovoru, **napiši ga u zagradi sa srpskim prevodom i kratkim objašnjenjem**. Primer:

> "Koristićemo **embedding** (utiskivanje — vektorska predstava objekta u prostoru velike dimenzije) za similarity search."

Ne moraš opet objašnjavati taj termin u istom dokumentu jednom kad je uveden. Ali u novom dokumentu/sesiji, ponovi objašnjenje.

**Šta se zadržava na engleskom uvek:**
- Kod, file paths, configuration syntax
- Wiki content (`knowledge/wiki/`) — pošto su izvori (knjiga, Fraser, crypto arhiva) na engleskom, wiki ostaje na engleskom radi provenance konzistentnosti
- Pull request titles i body-jevi koji se čitaju od upstream maintainer-a (`naiemk/wyckoff-ai`)
- Skill-specific output contract (SKILL.md output strukture)

### 0.2 Code review pre merge-a

Pre nego što se PR merge-uje u main, sledeća disciplina je obavezna:

| PR scope | Review obavezan |
|---|---|
| Sirovi data scripts (extract, scrape, download) | Lagani — pregled koda + validacionih komandi |
| MCP serveri | Lagani — pregled tool definicija + testova |
| Skill (`SKILL.md`, wiki ingest output, agent runtime logic) | Duboki — `prp-review-agents` ili manuelni multi-aspect pregled |
| Schema (`/CLAUDE.md`, `/CLAUDE.md` §3) | Duboki — diskusija sa user-om |
| Edukativni dokumenti, PRD-ovi | Pregled jezika i strukture (po default-u srpski sa engleskim terminima) |

**Anti-pattern:** merge bez review-a jer se "deluje OK po opisu". Bar jedan sanity-check (pročitaj script body, proveri test rezultat) je obavezan.

### 0.3 GitHub issue convention

- **Naslov:** engleski (radi git/search kompatibilnosti i konzistentnosti)
- **Body:** srpski (per §0.1)
- **Labele:** uvek `phase:1/2/3`, `model:opus/sonnet`, plus content tipa (`skill`, `data`, `infrastructure`, `wiki`, `idea`)
- **Milestone:** uvek prikačen (M1–M6)

Kada se issue zatvara komentarom, srpski.

### 0.4 Kild i model selection

- **Kild + Codex YOLO:** za mehaničke skripte, MCP servere, scraping, ekstrakciju, ML feature engineering. Pattern već dokumentovan.
- **Claude Opus sesija (interaktivna):** za #7 wiki ingest, #8 SKILL.md rebuild, sva work koja zahteva domain nuance i syntheses preko izvora.
- **Claude Sonnet kild:** opciono za prelaz između (npr. validation skripti koje treba malu Wyckoff svesnost ali ne dubok rasudak)

Vidi `model:opus` / `model:sonnet` labelu na svakom issue-u.

---

## 1. Three-Layer Architecture (Wyckoff instantiation)

```
Raw Sources          ← raw/ (book pages, Fraser articles+images, crypto archive posts+images)
     ↓
The Wiki             ← knowledge/wiki/ (LLM-maintained markdown — this is where ingest writes)
     ↓
Schema (this file)   ← CLAUDE.md (domain conventions, vocabulary, priorities)
```

**Raw sources are immutable.** Once `raw/bruce_fraser/`, `raw/crypto_archive/`, and `raw/book/` are populated by issues [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2), [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4), and image captions are added by [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5), the LLM never modifies them.

**The wiki compounds.** Every ingest, query answer, and reusable scenario can become a wiki page that future passes link to.

---

## 2. Wiki folder layout (Wyckoff-specific — overrides runbook default)

```
knowledge/wiki/
  README.md         ← project-specific wiki rules (short)
  index.md          ← navigation: every page listed under its folder
  log.md            ← chronological append-only operations log

  concepts/         ← Wyckoff laws, principles, methodology, phase semantics
  events/           ← named events (PS, SC, AR, ST, spring, upthrust, SOS, SOW, JAC, BUEC, FTI, LPS, LPSY...)
  structures/       ← full structure templates (accumulation, distribution, re-accumulation, redistribution) and schematics
  crypto/           ← crypto-specific adaptations (rotation, intermarket, BTC roles, spread charts, low-liquidity behavior)
  scenarios/        ← scenario templates, playbook entries, output contracts
  sources/          ← one page per source: book chapter, Fraser article, crypto archive volume
  questions/        ← filed query answers — the compounding layer (created during query operations)
  health/           ← lint reports (created during lint operations)
```

**Do not create new top-level folders without updating this schema first.** If a concept doesn't fit, file it under the closest folder and flag the question in `log.md`.

---

## 3. Required pages (domain vocabulary)

These pages **must exist** in the finished wiki. Treat their absence as a lint failure. Each must cite at least one raw source.

### concepts/ (laws and methodology)

- `concepts/three-laws.md` (supply-demand, cause-effect, effort-result — plus links to each)
- `concepts/supply-and-demand.md`
- `concepts/cause-and-effect.md`
- `concepts/effort-and-result.md`
- `concepts/market-cycle.md` (accumulation → markup → distribution → markdown)
- `concepts/buying-selling-neutral-position.md`
- `concepts/waves-and-fractals.md`
- `concepts/trend-assessment.md` (speed, projection, depth, channels)
- `concepts/significant-bar.md`
- `concepts/reversal-of-movement.md`
- `concepts/action-test-confirmation.md`
- `concepts/labeling-is-last-step.md`
- `concepts/random-vs-purposeful-range.md`
- `concepts/path-of-least-resistance.md`
- `concepts/principle-in-the-principle.md`
- `concepts/phase-a.md`, `concepts/phase-b.md`, `concepts/phase-c.md`, `concepts/phase-d.md`, `concepts/phase-e.md`
- `concepts/three-stages-of-uptrend.md` (value/absorption/speculation)
- `concepts/stride-of-trend.md`
- `concepts/creek-and-ice.md`
- `concepts/point-and-figure-counting.md`

### events/ (named events — each on own page)

Stop events (Phase A):
- `events/preliminary-support.md` (PS / PSY)
- `events/selling-climax.md` (SC) and `events/buying-climax.md` (BC)
- `events/automatic-rally.md` (AR) and `events/automatic-reaction.md`
- `events/secondary-test.md` (ST)
- `events/st-as-msos.md` and `events/st-as-msow.md`

Test events (Phase C):
- `events/spring.md`
- `events/upthrust-after-distribution.md` (UTAD)
- `events/upthrust.md` (UT)
- `events/no-shake-phase-c.md`

Trend events (Phase D / E):
- `events/sign-of-strength.md` (SOS)
- `events/sign-of-weakness.md` (SOW)
- `events/jump-across-the-creek.md` (JAC)
- `events/back-up-to-the-edge-of-the-creek.md` (BUEC)
- `events/fall-through-the-ice.md` (FTI)
- `events/last-point-of-support.md` (LPS)
- `events/last-point-of-supply.md` (LPSY)
- `events/failed-signal.md` (covers failed spring, failed upthrust, failed short trigger)

Modifiers / archive-specific:
- `events/feather.md` (Fraser/archive-specific)
- `events/hinge.md`
- `events/flat-reaction.md`

### structures/

- `structures/accumulation.md` (schematic 1, schematic 2 — link from here)
- `structures/distribution.md` (schematic 1, schematic 2)
- `structures/reaccumulation.md`
- `structures/redistribution.md`
- `structures/trading-range.md` (general — boundaries, time, midpoint)

### crypto/

- `crypto/intermarket-gate.md` (S&P / Nasdaq dependency)
- `crypto/bitcoin-leader-vs-funding-source.md`
- `crypto/rotation-hierarchy.md` (BTC → large caps → mid → low → themes)
- `crypto/spread-charts.md` (ETHBTC, LINKBTC — detection only, execute on USD/perp)
- `crypto/comparative-strength.md` (in-gear ranking)
- `crypto/low-liquidity-tolerance.md`
- `crypto/bitcoin-as-source-of-funding.md`
- `crypto/risk-off-refuge-hierarchy.md` (Tether → BTC → alts ordering)
- `crypto/three-stages-of-uptrend-in-crypto.md`
- `crypto/halving-and-catalysts.md`
- `crypto/thematic-indexes.md` (DeFi, exchange tokens, etc.)
- `crypto/historical-analogs.md` (1987, 1998, 2017 China ban, etc.)

### scenarios/

- `scenarios/playbook-master.md` (top-level scenario tree)
- `scenarios/output-contract.md` (what an analysis answer looks like — to be aligned with PRD-02)
- `scenarios/accumulation-phase-c-entry.md`
- `scenarios/distribution-phase-c-entry.md`
- `scenarios/phase-d-breakout-test.md`
- `scenarios/no-shake-foothold.md`
- `scenarios/crypto-rotation-watch.md`

### sources/

One per logical source unit:
- `sources/book/` — one page per chapter (~27 entries expected)
- `sources/crypto_archive/` — one page per volume (46 entries, ~12 marked WIKI_GAP for paywall)
- `sources/bruce_fraser/` — grouped by theme (not 243 separate pages — group similar articles, ~30–50 pages total)

---

## 4. Ingest workflow

Active batch ingest for [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) is operated through the temporary skill [`skills/wyckoff-wiki-ingest/`](skills/wyckoff-wiki-ingest/SKILL.md). That skill contains:

- The batch priority order (book → crypto archive → Fraser) with concrete chapter/volume ranges
- The cross-batch awareness protocol (read existing wiki before redefining)
- Validation scripts (`validate_links.py`, `fix_inline_links.py`, `review_pr.py`)
- Per-batch output contract and PR template

The skill is deleted once #7 is complete (Batch 9 merged). This file then continues to govern ad-hoc wiki updates via §2, §3, §5–§9.

---

## 5. Provenance conventions

**Every substantive claim in a wiki page must cite a raw source** in the page's frontmatter `sources:` field. The format:

```yaml
---
title: "Spring"
type: event
status: active
updated: 2026-05-24
sources:
  - path: raw/book/pages/page_142.md
    note: "primary definition"
  - path: raw/book/pages/page_143.md
    note: "test sequence after spring"
  - path: raw/crypto_archive/posts/wyckoff-crypto-report-vol-27.md
    note: "crypto-specific example: BTC March 2020 spring"
---
```

**Within page body**, cite inline using markdown links for high-density claims. The link path is **relative from the page's actual depth in `knowledge/wiki/`** — not a fixed string. A page in `knowledge/wiki/events/` is 3 levels deep, so its links use `../../../raw/...`; a page in `knowledge/wiki/sources/book/` is 4 levels deep, so its links use `../../../../raw/...`.

```md
A spring is a downside shake that probes below trading-range support
([book p.142](../../../raw/book/pages/page_142.md)) and is followed by a
test that prints lower volume than the spring itself.
```

For the full depth table and an automated validator, see [`skills/wyckoff-wiki-ingest/SKILL.md`](skills/wyckoff-wiki-ingest/SKILL.md) §2 and run `uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py` before commit.

**Synthesis claims** (cross-source generalizations not stated verbatim in any one source) must be marked:

```md
> **Synthesis:** Across the book chapter on Phase C and crypto archive
> vol 27, springs in low-liquidity assets often print climactic tails
> that the book does not emphasize.
> Sources: [[book chapter 17]], [[crypto vol 27]], [[crypto vol 28]]
```

**Wiki-internal links** use Obsidian-style `[[event name]]` for backlinks between pages (the LLM and human reader both benefit).

---

## 6. Image alt-text convention

When [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) (Vision caption pass) writes alt text into raw source `.md` files, the format is:

```md
![Accumulation schematic showing SC, AR, and spring at support](images/page_047_fig_1.png)
```

When ingesting into the wiki:
- Copy the alt text verbatim into the wiki page's image reference
- If the source image is reused across multiple wiki pages, the alt text is the same
- If an image has no alt text yet (caption pass not run), add `<!-- TODO: Vision caption -->` next to the reference and log it in the wiki page's `## Open Questions` section

---

## 7. WIKI_GAP marker

When ingest cannot complete a page because of a missing source (paywalled crypto post, missing book figure, unclear concept), insert `WIKI_GAP` markers:

```md
## Spring in Low-Liquidity Markets

WIKI_GAP — `raw/crypto_archive/posts/wyckoff-crypto-report-vol-52.md` is
paywalled (`status: paywalled` in manifest). Only the introductory
sentence was scraped; the spring example referenced in the public excerpt
cannot be verified.

The book covers springs in general ([book ch.17](../../../raw/book/sources/book-ch17.md))
but does not specifically address low-liquidity tails.
```

The lint pass (operation: `lint`) reports all `WIKI_GAP` markers in `health/`.

**Do not silently leave a section incomplete.** If you can't fill it, mark it.

---

## 8. Cross-reference conventions (what links to what)

A well-formed event page (e.g. `events/spring.md`) should link:

- **Up:** to the containing structure (`structures/accumulation.md`) and phase (`concepts/phase-c.md`)
- **Sideways:** to related events (`events/upthrust.md` as the bearish counterpart, `events/secondary-test.md` for the test sequence)
- **Down:** to scenarios that hinge on it (`scenarios/accumulation-phase-c-entry.md`)
- **Crypto application:** if relevant, to a `crypto/` page (`crypto/low-liquidity-tolerance.md`)
- **Provenance:** to the raw source pages cited

A page with zero outbound links is suspicious — flag in lint.

---

## 9. Style and tone

- **Precise, not flowery.** Wyckoff vocabulary is technical; prefer the specific term over a metaphor.
- **Comparative, not absolute.** "Faster than the prior impulse" beats "fast." This is core Wyckoff methodology.
- **Distinguish source-stated from synthesis.** Mark synthesis explicitly per §5.
- **Avoid premature labels.** Per concept `labeling-is-last-step` — read price/volume first, label second.
- **No trade calls.** The wiki is knowledge, not a signal feed. Scenarios describe what *would* count as evidence; they don't say "buy here."

---

## 10. Out of scope for the wiki

Things the wiki does **not** contain:

- **Live market data** — that lives in MCP servers ([#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9)–[#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12))
- **The skill itself** — `skills/wyckoff-trader-skill/SKILL.md` is the runtime contract; the wiki is its knowledge base
- **Project planning** — that lives in `prds/` and GitHub issues
- **Trading rules** — the wiki describes Wyckoff phenomenology; it doesn't prescribe trades

If you find yourself writing something in one of these categories, file it in the right place (memory, an issue, the skill, the PRD).

---

## 11. Quick reference

| Want to... | Go to |
|---|---|
| Understand how ingest works (generic) | `~/.agent-runbooks/llm-wiki.md` |
| Run a #7 batch ingest or PR review | [`skills/wyckoff-wiki-ingest/SKILL.md`](skills/wyckoff-wiki-ingest/SKILL.md) |
| Decide where a new page goes | this file §2 + §3 |
| Cite a source correctly | this file §5 + skill §2 (path depth) |
| Mark a missing or paywalled source | this file §7 |
| Verify the wiki is healthy | runbook §"Operation: Lint" + this file §3 (required pages list) |

---

**Schema version:** 1.0 (2026-05-24, created with [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6))
**Next revision trigger:** PRD-02 (trading use) lands — may add/refine `scenarios/` and `crypto/` structure based on real query patterns.
