# Handoff — Wyckoff AI Rebuild

**Session date:** 2026-05-24  
**Repo:** https://github.com/ssmiljanicc/wyckoff-ai (fork of naiemk/wyckoff-ai)  
**Local path:** `/Users/ssmiljanic/projekti/wyckoff-ai`

---

## What this repo is

A Claude Code skill (`skills/wyckoff-trader-skill/`) that turns an AI agent into a Wyckoff methodology analyst, specialized for crypto markets. The skill contains:
- `SKILL.md` — workflow and output contract
- `references/` — 5 hand-distilled markdown files (book_foundations, crypto_adaptations, uncommon_concepts, scenario_playbook, bruce_fraser_stockcharts)
- `references/assets/` — offline raw corpus: 248 book pages (.txt), 46 crypto archive posts (.md), 243 Bruce Fraser articles (.md + .html)

The skill is designed for use with OpenAI Agents SDK (`agents/openai.yaml`) but the knowledge base is format-agnostic.

---

## What we decided to do

**Rebuild the skill from scratch** using the llm-wiki method (Karpathy pattern). The current skill was hand-distilled without provenance tracking and is missing all chart images. The rebuild will:

1. Complete the raw data layer (download missing images, re-extract book from PDF)
2. Add Vision-generated captions for all chart images
3. Build a proper llm-wiki knowledge base with provenance
4. Reconstruct SKILL.md from the wiki
5. Add MCP servers for live market data so the agent can analyze charts autonomously

---

## Key decisions made

- **llm-wiki** as the KB method: raw sources immutable, wiki layer LLM-maintained, schema in CLAUDE.md
- **No Pre-Write Snapshot Cross-Check** in llm-wiki runbook — removed as Codex-specific overhead irrelevant for trading knowledge
- **Runbook updated** at `~/.agent-runbooks/llm-wiki.md`: added three-layer architecture, scale guidance (~100 sources = index.md sufficient), 10–15 pages per ingest pass, image ingest operation
- **Fork** (not copy): `ssmiljanicc/wyckoff-ai` is a proper fork of `naiemk/wyckoff-ai` — improvements may be contributed back via PR
- **PDF needed**: the book (Ruben Villahermosa Chaves, 248 pages) must be located to re-extract clean text + images. Do not commit PDF to repo.

---

## All open issues

### M1: Raw Data Ready
| # | Title | Status |
|---|---|---|
| [#1](https://github.com/ssmiljanicc/wyckoff-ai/issues/1) | Raw data inventory and gap analysis | open |
| [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2) | Download Bruce Fraser images + rebuild MD files | open |
| [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3) | Re-scrape crypto archive posts with images | open |
| [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) | Re-extract book from PDF: clean text + images | open |
| [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) | Claude Vision caption pass for all chart images | open |

### M2: Knowledge Base Built
| # | Title | Status |
|---|---|---|
| [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6) | Initialize llm-wiki + Wyckoff schema (CLAUDE.md) | open |
| [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) | Ingest all raw sources into wiki (batched) | open |

### M3: Skill Reconstructed
| # | Title | Status |
|---|---|---|
| [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) | Rebuild SKILL.md and scenario_playbook from wiki | open |
| [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9) | Market data MCP server (OHLCV) | open |
| [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10) | Chart renderer MCP (OHLCV → chart image) | open |
| [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11) | Spread chart MCP (ratio charts) | open |
| [#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12) | MCP integration tracking issue | open |

---

## Where to start in a new session

**If the PDF has been found:** start with #4 (re-extract book), then #1 (inventory).  
**If no PDF yet:** start with #1 (inventory) and #2 (Fraser images) — both are unblocked.  
**#2 is the highest-value unblocked task:** 243 HTML files are already local, 854 images just need downloading and a script to rebuild the MD files.

---

## Raw corpus summary

| Source | Files | Words | Images |
|---|---|---|---|
| Book (Villahermosa) | 248 .txt pages | ~38,400 | lost (need PDF) |
| Crypto Archive (Rutigliano) | 46 .md posts | ~24,000 | missing (need re-scrape) |
| Bruce Fraser (StockCharts) | 243 .md + 243 .html | ~185,000 | 854 URLs in HTML, not downloaded |
| **Total** | | **~247,000** | |

---

## Key files

| File | Purpose |
|---|---|
| `skills/wyckoff-trader-skill/SKILL.md` | Current skill (to be rebuilt in #8) |
| `references/assets/bruce_fraser_stockcharts/html/` | 243 HTML files with image URLs |
| `references/assets/crypto_archive/manifest.json` | 46 post URLs for re-scraping |
| `~/.agent-runbooks/llm-wiki.md` | Updated llm-wiki runbook |

---

## Context for Opus review

If opening with Opus to review issues: the goal is a complete rebuild, not incremental improvement. Every issue should be evaluated for: correctness of scope, correct milestone assignment, missing prerequisites, and anything that might block downstream work. Issues #2 and #9 are the most technically concrete and easiest to start with.
