# Wyckoff AI Wiki

This is an LLM-maintained knowledge base for Wyckoff methodology, specialized for crypto markets.

**Method:** `llm-wiki` (universal runbook in `~/.agent-runbooks/llm-wiki.md`) — Karpathy-pattern three-layer architecture (raw / wiki / schema). For the active #7 batch ingest, see [`skills/wyckoff-wiki-ingest/SKILL.md`](../../skills/wyckoff-wiki-ingest/SKILL.md).

## Layout

- `concepts/` — Wyckoff laws, principles, methodology, phase semantics
- `events/` — named events (PS, SC, AR, ST, spring, upthrust, SOS, SOW, JAC, BUEC, FTI, LPS, LPSY...)
- `structures/` — accumulation, distribution, re-accumulation, redistribution
- `crypto/` — crypto-specific adaptations (rotation, intermarket, BTC roles, spread charts)
- `scenarios/` — scenario templates, playbook entries, output contracts
- `sources/` — per-source summary pages (book chapters, Fraser articles, crypto archive volumes)
- `questions/` — filed query answers (compounding layer; appears during `query` operations)
- `health/` — lint reports (appears during `lint` operations)

## Operating principles

- **Provenance:** every claim cites a raw source in frontmatter (`sources:`)
- **Compounding:** reusable query answers become wiki pages
- **No live data:** market data, charts, trade calls live elsewhere (MCP, the skill)
- **Schema-driven:** all conventions in `/CLAUDE.md` at repo root

## Where to find...

| Need | Path |
|---|---|
| How to ingest a new source | `~/.agent-runbooks/llm-wiki.md` (universal runbook) |
| Wyckoff-specific conventions | `/CLAUDE.md` at repo root |
| What pages must exist | `/CLAUDE.md` §3 |
| Citation format | `/CLAUDE.md` §5 |
| Navigation across all wiki pages | [`index.md`](./index.md) |
| What has been ingested when | [`log.md`](./log.md) |

## Status

**Initialized:** 2026-05-24 (issue [#6](https://github.com/ssmiljanicc/wyckoff-ai/issues/6))
**Sources ingested:** 0 (waiting on [#2](https://github.com/ssmiljanicc/wyckoff-ai/issues/2), [#3](https://github.com/ssmiljanicc/wyckoff-ai/issues/3), [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4), [#5](https://github.com/ssmiljanicc/wyckoff-ai/issues/5) to complete raw data; then [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) begins batched ingest)
**Wiki pages:** 0 of ~70 expected (see `/CLAUDE.md` §3 for the required-pages list)
