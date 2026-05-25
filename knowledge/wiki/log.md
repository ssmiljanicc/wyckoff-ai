# Wiki Log

Chronological, append-only operations log. Every init, ingest, query filing, lint pass, or update appends here.

---

## [2026-05-24] init | Knowledge base initialized

- Knowledge root: `/Users/ssmiljanic/projekti/wyckoff-ai/knowledge`
- Wiki root: `knowledge/wiki/`
- Schema: `/CLAUDE.md` at repo root (Wyckoff-specific domain conventions)
- Issue: [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6)

### Raw source paths (current/target — see [`raw/INVENTORY.md`](../../raw/INVENTORY.md))

| Source | Current location (pre-rebuild) | Target location (post-rebuild) | Status |
|---|---|---|---|
| Book (Villahermosa) | `skills/wyckoff-trader-skill/references/assets/book/` | `raw/book/` | Issue [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) blocked on PDF |
| Crypto Archive | `skills/wyckoff-trader-skill/references/assets/crypto_archive/` | `raw/crypto_archive/` | Issue [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) in flight (kild `crypto-rescrape`) |
| Bruce Fraser | `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/` | `raw/bruce_fraser/` | Issue [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) in flight (kild `fraser-images`) |

### Estimated corpus size

- ~350 sources total (248 book pages + 46 crypto archive posts + 243 Fraser articles)
- ~247k words ≈ ~329k tokens
- **Exceeds single context window** — ingest must be batched (planned in [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7), 9 batches)

### Notes

- Schema (`/CLAUDE.md`) defines 6 domain folders: `concepts/`, `events/`, `structures/`, `crypto/`, `scenarios/`, `sources/` (plus `questions/`, `health/` per runbook)
- Required-pages list in schema §3: ~70 pages expected once ingest is complete
- Ingest priority: book first (canonical taxonomy) → crypto archive → Bruce Fraser
- Vision captions ([#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5)) should land before ingest, else re-ingest needed once captions exist
- Schema may revise after PRD-02 (trading use) lands — `scenarios/` and `crypto/` structure could refine based on real query patterns

### Remaining sources not yet ingested

All of them. Ingest begins with [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) after raw data is ready (kilds for #2 and #3 in flight; #4 awaits PDF).

### Open follow-ups

- Wait for `fraser-images` kild (#2) and `crypto-rescrape` kild (#3) to complete
- PDF must be located before #4 can run (re-extract book with figures)
- PRD-02 must land before [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8); may also revise this schema's `scenarios/` section

---

## [2026-05-25] ingest | Knjiga, Batch 1 — poglavlja 1–13 (core framework)

- Issue: [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- Branch: `kild/wiki-ingest-batch1`
- Izvori: `raw/book/pages/page_012.md` do `page_088.md` (Part 1 — kako se tržišta kreću; Part 2 — Wyckoff metoda, šeme; Part 3 — tri zakona; Part 4 — procesi akumulacije i distribucije, narativno). Dodatno citirano: `page_208.md`–`page_212.md` (significant bar i reversal of movement iz Chapter 27 — koncepti foundational za Batch 1, sama glava ide u Batch 3).

### Pages created (25)

`concepts/` (12):
- `three-laws.md`, `supply-and-demand.md`, `cause-and-effect.md`, `effort-and-result.md`
- `market-cycle.md`, `buying-selling-neutral-position.md`
- `waves-and-fractals.md`, `trend-assessment.md`
- `significant-bar.md`, `reversal-of-movement.md`
- `random-vs-purposeful-range.md`, `path-of-least-resistance.md`

`structures/` (1):
- `trading-range.md` (generička šema; konkretne šeme akumulacije/distribucije dolaze u Batch 2)

`sources/book/` (13):
- `book-chapter-01.md` do `book-chapter-13.md`, jedna stranica po poglavlju, sa per-poglavljem listom raw strana i wiki stranica koje je generisalo.

### Pages updated

- `knowledge/wiki/index.md` — listane sve 25 novih stranica, pending sekcije ažurirane
- `knowledge/wiki/log.md` — ovaj zapis

### Pages not yet ingested

- Knjiga: poglavlja 14–25 (events, phases — Batch 2), 26–27 (trading, decision-making — Batch 3, iako ch 27 koncepti significant-bar / reversal-of-movement već citirani u Batch 1)
- Sva crypto archive grupacija (Batches 4–5)
- Sva Bruce Fraser arhiva (Batches 6–9)

### Commit-evi u ovom batch-u

- Batch 1.1: `three-laws` umbrella + supply-and-demand + cause-and-effect + effort-and-result
- Batch 1.2: market-cycle + buying-selling-neutral-position + waves-and-fractals + trend-assessment + significant-bar + reversal-of-movement
- Batch 1.3: random-vs-purposeful-range + path-of-least-resistance + structures/trading-range
- Batch 1.4: 13 source summaries za poglavlja 1–13

### Notes

- Sve concept stranice imaju `sources:` frontmatter sa konkretnim raw strana iz knjige i inline citacije u tekstu (po `/CLAUDE.md` §5).
- Cross-references preko `[[name]]` ka srodnim stranicama — mnoge još ne postoje (events, structures, phase pages), što je markeri za naredne batch-eve. Lint pass nakon Batch 2/3 će validirati da su backlinks ispunjeni.
- Stranice `significant-bar` i `reversal-of-movement` izlaze iz strogo "ch 1–13" opsega, ali su listed u `/CLAUDE.md` §3 i prompt za Batch 1 ih eksplicitno traži; frontmatter jasno citira ch 27 strane (208–212).
- Nema WIKI_GAP markera — svaki claim ima izvor iz knjige.

### Open follow-ups for Batch 2

- Stvoriti `concepts/phase-a.md` do `phase-e.md` (poglavlja 21–25)
- Stvoriti sve `events/*` stranice (poglavlja 14–20)
- Stvoriti `structures/accumulation.md`, `distribution.md`, `reaccumulation.md`, `redistribution.md`
- Stvoriti `concepts/action-test-confirmation.md`, `labeling-is-last-step.md`, `creek-and-ice.md`
