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

---

## [2026-05-25] ingest | Knjiga, Batch 2 — poglavlja 14–25 (events i phases)

- Issue: [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- Branch: `kild/wiki-ingest-batch2`
- Izvori: `raw/book/pages/page_093.md` do `page_190.md` (Part 5 — sedam događaja metodologije; Part 6 — pet faza). Dodatno citirano: `page_037.md`–`page_045.md` (Chapter 6 schematics) i `page_072.md`–`page_088.md` (Chapter 10–13 narrative) za strukturne stranice — ove sekcije već su bile delimično obrađene u Batch 1 kao source summaries, ali konkretne wiki stranice akumulacija/distribucija/reakumulacija/redistribucija prvi put se kreiraju ovde.

### Pages created (36)

`events/` (20 — kompletan event vocabulary):
- Phase A: `preliminary-support.md`, `selling-climax.md`, `buying-climax.md`, `automatic-rally.md`, `automatic-reaction.md`, `secondary-test.md`, `st-as-msos.md`, `st-as-msow.md`
- Phase C: `spring.md`, `upthrust-after-distribution.md`, `upthrust.md`, `no-shake-phase-c.md`
- Phase D/E: `sign-of-strength.md`, `sign-of-weakness.md`, `jump-across-the-creek.md`, `back-up-to-the-edge-of-the-creek.md`, `fall-through-the-ice.md`, `last-point-of-support.md`, `last-point-of-supply.md`, `failed-signal.md`

`concepts/` (8 — phases + methodology discipline):
- `phase-a.md` do `phase-e.md`
- `action-test-confirmation.md`, `labeling-is-last-step.md`, `creek-and-ice.md`

`structures/` (4 — sve glavne šeme):
- `accumulation.md`, `distribution.md`, `reaccumulation.md`, `redistribution.md`

`sources/book/` (12 — source summaries za ch 14–25):
- `book-chapter-14.md` do `book-chapter-25.md`

### Pages updated

- `knowledge/wiki/index.md` — listane sve 36 novih stranica; Pending sekcije ažurirane za Batch 3 i kasnije
- `knowledge/wiki/log.md` — ovaj zapis

### Pages not yet ingested

- Knjiga: poglavlja 26–27 (Batch 3 — Primary Positions, Decision-Making; Part 7 trading)
- Sva crypto archive grupacija (Batches 4–5)
- Sva Bruce Fraser arhiva (Batches 6–9)

### Commit-evi u ovom batch-u

- Batch 2.1: Phase A events (8 stranica — PS/PSY, SC, BC, AR akumulacija/distribucija, ST, ST kao mSOS/mSOW)
- Batch 2.2: Phase C events (4 stranice — spring, UTAD, UT, no-shake)
- Batch 2.3: Phase D/E events (8 stranica — SOS/SOW, JAC/FTI, BUEC, LPS/LPSY, failed-signal)
- Batch 2.4: methodology concept stranice (3 stranice — action-test-confirmation, labeling-is-last-step, creek-and-ice)
- Batch 2.5: Phase A–E concept stranice (5 stranica)
- Batch 2.6: strukture (4 stranice — accumulation, distribution, reaccumulation, redistribution)
- Batch 2.7: source summaries za ch 14–25 (12 stranica)

### Notes

- Sve stranice imaju `sources:` frontmatter sa specifičnim raw stranama i inline citacije u tekstu (po `/CLAUDE.md` §5). 36 stranica × prosečno ~6 raw-strana citata = preko 200 distinct citation links — provenance pokriva 100% Batch 2 sadržaja iz knjige.
- Cross-references preko `[[name]]` formirale su mrežu kroz Batch 1 i Batch 2 — events linkuju ka structures, phases, methodology concepts; structures linkuju ka events; source summaries linkuju ka odgovarajućim wiki stranicama.
- Nema WIKI_GAP markera — sve što je labeled u knjizi je pokriveno.
- `principle-in-the-principle` koncept se odlaže — nije eksplicitno u knjizi ch 14–25; pojaviće se u Fraser arhivi.
- UA-vs-UT, ST-as-SOW-vs-mSOW pages dokumentuju kako se ista akcija labelira drugačije u zavisnosti od structure read-a — primer za `labeling-is-last-step` disciplinu.

### Open follow-ups for Batch 3

- Stvoriti `sources/book/book-chapter-26.md` i `book-chapter-27.md`
- Stvoriti `concepts/three-stages-of-uptrend.md`, `concepts/stride-of-trend.md`, `concepts/point-and-figure-counting.md` ako su pokriveni u ch 26–27 (verovatno P&F u ch 27)
- Razmisliti o `scenarios/primary-positions.md` (mapiranje književnih primary trade lokacija) — može i da sačeka PRD-02 / [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8)
- Posle Batch 3 može da se pokrene prvi lint pass — sve required pages iz CLAUDE.md §3 vezane za knjigu trebale bi da postoje

---

## [2026-05-26] spot-fix | Batch 2 citation parity

- Issue: [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- Scope: Batch 2 semantic-review cleanup before Batch 3.

### Pages updated

- `events/spring.md` — added missing `raw/book/pages/page_140.md` to frontmatter `sources:` because the page body cites `[book p.139–140]`. This brings the page into runbook §3.6 range-citation parity: both pages in the range are now listed in `sources:`.

### Notes

- The direct quote under "Labeling Discipline" already cites `page_142.md`, where the quote appears verbatim.
- `structures/accumulation.md` and `structures/distribution.md` already contain explicit `> **Synthesis:**` markers for the former "Common Trading Mistakes" concern, so no further text change was needed there.

---

## [2026-05-26] ingest | Knjiga, Batch 3 — poglavlja 26–27 (primary positions i decision-making)

- Issue: [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- Branch: `wiki-ingest-batch3`
- Izvori: `raw/book/pages/page_198.md` do `page_226.md` (Chapter 26 — Primary Positions; Chapter 27 — Decision-Making). Chapter 27 source summary staje na `page_226.md`; `page_227.md` počinje Part 8 case studies.

### Pages created (3)

`concepts/`:
- `point-and-figure-counting.md` — classical horizontal count method, structure-specific count boundaries, projection grades, and modern-market subjectivity warning.

`sources/book/`:
- `book-chapter-26.md` — source summary for primary trade locations across Phase C, Phase D, and Phase E.
- `book-chapter-27.md` — source summary for significant bar, reversal of movement, order placement, stop logic, and take-profit evidence.

### Pages updated

- `knowledge/wiki/index.md` — Batch 3 pages added; book source summaries now complete at 27/27.
- `knowledge/wiki/sources/book/book-chapter-08.md` — `point-and-figure-counting` reference updated from planned seed to active primary rules page.
- `knowledge/wiki/log.md` — this entry.

### Notes

- `significant-bar.md` and `reversal-of-movement.md` already existed from Batch 1 because they were foundational for earlier pages; Chapter 27 now has its source summary instead of redefining those concepts.
- Text search did not find source support in the book for `three-stages-of-uptrend` or `stride-of-trend`; these remain pending for Fraser/archive or later confirmed sources rather than being filled from training data.
- No WIKI_GAP markers introduced.

### Open follow-ups

- Run mandatory semantic spot-check for Batch 3 before merge (per `operations/semantic-spot-check.md`).
- After Batch 3 merge, first lint pass can verify all book-sourced required pages and distinguish remaining Fraser/archive-sourced required pages.

---

## [2026-05-27] ingest | Crypto archive, Batch 4 — Vol 14–28 (2020 post-crash repair, margin behavior)

- Issue: [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)
- Branch: `wiki-ingest-batch4`
- Izvori: `raw/crypto_archive/html/wyckoff-crypto-report-vol-14.html` do `wyckoff-crypto-report-vol-28.html`; Vol 27 koristi `wyckoff-crypto-report-vol-27-flash-update.html`.

### Pages created (24)

`sources/crypto_archive/` (15 — jedna stranica po volumenu):
- `crypto-report-vol-14.md` do `crypto-report-vol-25.md`
- `crypto-report-vol-26.md` — WIKI_GAP; raw capture nema article body
- `crypto-report-vol-27.md`
- `crypto-report-vol-28.md`

`crypto/` (9 — crypto-specific applied concepts):
- `bitcoin-as-source-of-funding.md`
- `comparative-strength.md`
- `halving-and-catalysts.md`
- `historical-analogs.md`
- `intermarket-gate.md`
- `rotation-hierarchy.md`
- `spread-charts.md`
- `thematic-indexes.md`
- `three-stages-of-uptrend-in-crypto.md`

### Pages updated

- `knowledge/wiki/index.md` — dodate Batch 4 crypto i source-summary stranice.
- `knowledge/wiki/log.md` — ovaj zapis.

### Commit-evi u ovom batch-u

- `7c6b2cf` — source summaries Vol 14–20
- `0126c31` — source summaries Vol 21–28, uključujući Vol 26 WIKI_GAP
- `b18b390` — crypto applied concept stranice

### Notes

- Batch 1–3 book vocabulary nije redefinisan; archive stranice linkuju ka postojećim `concepts/`, `events/`, i `structures/` stranicama.
- Svaki inline `[vol N]` link ima paritetan `sources:` entry; svaka frontmatter crypto archive putanja se pojavljuje inline.
- Vol 26 je jedini WIKI_GAP u ovom batch-u: lokalni HTML fajl postoji, ali ne sadrži report body.
- `low-liquidity-tolerance`, `risk-off-refuge-hierarchy`, i `bitcoin-leader-vs-funding-source` ostaju pending dok ih Batch 5 ili kasniji izvori ne podrže direktnije.

### Open follow-ups

- Obavezan semantic spot-check pre merge-a: Batch 4 uvodi novi izvor tipa (`crypto archive`), trigger #1 iz `semantic-spot-check.md`.
- Batch 5: Crypto Archive Vol 29–59 (2020–2021: DeFi, rotation, terminal Bitcoin).

[2026-05-27] spot-check Batch 4 — 6 stranica, 24 PASS / 0 CONCERN / 0 FAIL — akcija: merge
