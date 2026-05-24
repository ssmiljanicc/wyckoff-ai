# Raw Data Inventory

**Generated:** 2026-05-24
**Issue:** [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1)
**Source paths (current, pre-rebuild):** `skills/wyckoff-trader-skill/references/assets/`
**Target paths (post-rebuild):** `raw/` — sources will be relocated as #2/#3/#4 produce clean output

> **Status:** the source files still live under the legacy `references/assets/` path. Rebuild issues ([#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2), [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4)) will produce new output under `raw/{book,bruce_fraser,crypto_archive}/` with images alongside text. This file describes the current state and what needs to happen.

---

## Top-level summary

| Source | Files | Words | Chars | Images | Status |
|---|---:|---:|---:|---:|---|
| **Book** (Villahermosa, *The Wyckoff Methodology in Depth*) | 248 page .txt + 1 full_text.txt | 38,417 | — | 0 of ~unknown (lost) | OCR artifacts present; figures lost in PDF→text |
| **Crypto Archive** (Rutigliano, wyckoffanalytics.com) | 46 .md posts | 23,929 | 150,220 | 0 of unknown (lost) | HTML not saved; 12 posts likely paywalled |
| **Bruce Fraser** (StockCharts) | 243 .md + 243 .html + 7 archive_pages | 184,833 | 1,065,072 | 0 of 855 unique URLs | HTML local; 855 image URLs identified but not downloaded |
| **Total raw** | | **247,179** | | **0 of ~855+ known** | |

**Token estimate (rough, 1 word ≈ 1.33 tokens):** ~329k tokens — exceeds a single context window; ingest must be batched (planned in [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7)).

### Already-distilled reference files (not raw — to be replaced)

These are the **hand-distilled** outputs from the previous build. They're NOT raw sources and will be replaced or repointed by [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8).

| File | Words | Notes |
|---|---:|---|
| `references/book_foundations.md` | 970 | Distilled from book |
| `references/bruce_fraser_stockcharts.md` | 1,023 | Distilled from Fraser |
| `references/crypto_adaptations.md` | 1,006 | Distilled from crypto archive |
| `references/scenario_playbook.md` | 506 | Scenario tree |
| `references/source_index.md` | 1,342 | Source pointers |
| `references/uncommon_concepts.md` | 1,004 | Edge-case Wyckoff concepts |
| **Total distilled** | **5,851** | ~8k tokens — all to be regenerated from wiki |

---

## Source 1 — Book: *The Wyckoff Methodology in Depth* (Ruben Villahermosa Chaves)

### Current state

| Item | Value |
|---|---|
| Format | Plain text (`.txt`) from PDF→text conversion |
| File count | 248 page-level files (`page_001.txt` … `page_248.txt`) + 1 concatenated `full_text.txt` |
| Word count (full_text) | 38,417 |
| Image count | **0** — all figures lost in PDF→text conversion |
| Text quality | **Damaged** — OCR-style artifacts present (`gre ater`, `selle rs`, `tra ding`, `wycko ff`); 4+ instances confirmed in a 4-pattern spot check |
| Current path | `skills/wyckoff-trader-skill/references/assets/book/` |

### Gaps

- **No images** — schematics, accumulation/distribution diagrams, P&F examples, all gone
- **OCR artifacts in text** — invisible spaces broke words; ingest of this text will leak artifacts into the wiki

### Action

[#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) — Re-extract from PDF via PyMuPDF. **Hard prerequisite:** user must locate the original PDF (commercial book, not in repo). Path: `raw/book/wyckoff_methodology_in_depth.pdf` (gitignored).

### Estimated post-fix size

Book figures: ~150–300 figures expected (estimate based on a typical Wyckoff text — phase schematics, P&F examples, candle bar examples, accumulation/distribution diagrams across 27 chapters).

---

## Source 2 — Crypto Archive (Alessio Rutigliano, wyckoffanalytics.com)

### Current state

| Item | Value |
|---|---|
| Format | Plain text Markdown (`.md`) |
| File count | 46 posts (`wyckoff-crypto-report-vol-14` through `wyckoff-crypto-report-59`) |
| Word count | 23,929 |
| Char count (from manifest) | 150,220 |
| Image count | **0** — HTML not saved during original scrape |
| Date range | 2020-03-20 to 2021-03-26 (vol 14 → vol 59) |
| Current path | `skills/wyckoff-trader-skill/references/assets/crypto_archive/posts/` |
| Manifest | `references/assets/crypto_archive/manifest.json` — has slug, URL, date, char_count per post |

### Suspicious posts (likely paywalled — text-only scrape returned almost nothing)

12 posts have char_count < 1500, much lower than the average ~3,300 chars/post:

| Slug | Chars | Date | Likely cause |
|---|---:|---|---|
| wyckoff-crypto-report-58 | 204 | 2021-03-19 | Paywall |
| wyckoff-crypto-report-57 | 239 | 2021-03-12 | Paywall |
| wyckoff-crypto-report-vol-52 | 291 | 2021-01-29 | Paywall |
| wyckoff-crypto-report-vol-26 | 483 | 2020-06-19 | Paywall (unexpectedly early) |
| wyckoff-crypto-report-54 | 503 | 2021-02-19 | Paywall |
| wyckoff-crypto-report-55 | 503 | 2021-02-26 | Paywall |
| wyckoff-crypto-report-vol-56 | 526 | 2021-03-05 | Paywall |
| wyckoff-crypto-report-53 | 562 | 2021-02-05 | Paywall |
| wyckoff-crypto-report-59 | 729 | 2021-03-26 | Paywall |
| wyckoff-crypto-report-vol-50 | 827 | 2021-01-15 | Paywall |
| _2 more_ | _<1500_ | | |

The handoff guessed vol 49–59 were paywalled; **actual gap is wider** — vol 26 is also affected, suggesting the paywall was inconsistent over time, not strictly date-based.

### Gaps

- **No images** — chart screenshots central to these reports are gone
- **No HTML** — can't even recover image URLs without re-fetching
- **12 paywalled posts** — re-scrape won't fix; need policy decision (skip, mark `WIKI_GAP`, or find alternate sources)

### Action

[#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) — Re-scrape all 46 URLs with HTML saved, images downloaded, paywall-aware (no bypass, mark `WIKI_GAP`).

---

## Source 3 — Bruce Fraser (StockCharts.com)

### Current state

| Item | Value |
|---|---|
| Format | Markdown (text-only) + HTML (full source) |
| File count | 243 `.md` posts + 243 `.html` files + 7 archive index `.html` |
| Word count (md) | 184,833 |
| Char count | 1,065,072 |
| Image URLs in HTML | **1,565 references** → **855 unique** (many images reused across multiple articles, top 5 each used in 4 articles) |
| Image files on disk | **0** — URLs identified but never downloaded |
| Date range | 2015-05 to 2026-03 (10+ years of weekly articles) |
| Current path | `skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts/` |
| Manifest | `manifest.json` — has slug, URL, date, html_file, char_count per article |

### Year distribution

| Year | Articles |
|---:|---:|
| 2015 | 29 |
| 2016 | 49 |
| 2017 | 46 |
| 2018 | 45 |
| 2019 | 24 |
| 2020 | 13 |
| 2021 | 9 |
| 2022 | 9 |
| 2023 | 5 |
| 2024 | 12 |
| 2025 | 1 |
| 2026 | 1 |
| **Total** | **243** |

The corpus is heavily front-loaded (2015–2018 = 169 of 243 = 70%) — the foundational pedagogical content sits in the early years, more current commentary in recent years.

### Important note on image count

The handoff said **854 images**; actual measurement is **855 unique URLs** (off-by-one is fine — handoff was approximate). However, the **total image references is 1,565** because images are reused across articles. The downloader script only needs to fetch 855 files but must insert 1,565 reference lines into the .md outputs.

### Only 1 short article

`articles-stocktalk-2024-02-swing-trading-strategies-tips-487` is 888 chars — much shorter than the average 4,400 chars/article. Worth investigating during re-build; everything else looks reasonable.

### Gaps

- **No images on disk** — 855 unique chart images sitting at `https://d.stockcharts.com/img/articles/...`
- **No inline image refs in .md** — text was extracted but image positions were lost

### Action

[#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) — Download 855 unique images, rebuild .md files with inline image refs at correct positions (1,565 reference lines across 243 articles).

---

## Summary of gaps (mapped to issues)

| Gap | Affected issue(s) | Severity |
|---|---|---|
| Book figures lost in PDF→text | [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) | Critical — half the Wyckoff method is visual |
| Book PDF not in repo | [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) prerequisite | Blocks #4 — user must source |
| OCR artifacts in book text | [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) | High — propagates to wiki if ingested as-is |
| Crypto archive images lost | [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) | High — chart screenshots central to scenario reports |
| 12 crypto posts likely paywalled (broader than handoff stated) | [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) | Medium — policy decision needed |
| 855 Fraser images not downloaded | [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) | High — chart-driven articles |
| No Vision captions on any image | [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) | Resolved by #5 once #2/#3/#4 produce images |

## Discrepancies with HANDOFF.md

The handoff was a reasonable approximation. Notable corrections:

| Handoff said | Actual | Note |
|---|---|---|
| 854 Fraser images | 855 unique URLs (1,565 references) | Off by one; the 1,565 number is more useful for the .md rebuild |
| "later posts (vol 49–59)" paywalled | 12 posts < 1500 chars, including unexpectedly vol 26 | Wider gap than expected |
| 2016-04 to 2026-03 (Fraser) | 2015-05 to 2026-03 | One earlier year |
| ~247k words total | 247,179 words exactly | Confirmed |

---

## Next-step recommendation

**Highest-value unblocked task:** [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) — Fraser image download. 855 images, 243 articles, HTML already local, no dependencies.

**Second:** [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) — crypto archive re-scrape; can run in parallel with #2.

**Blocked:** [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) — needs PDF located by user first.

**Wait until #2/#3/#4 produce images:** [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) — Vision captions.
