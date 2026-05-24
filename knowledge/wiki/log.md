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
