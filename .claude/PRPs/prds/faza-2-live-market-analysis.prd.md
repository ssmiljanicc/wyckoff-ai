# Faza 2 — Live Market Analysis (MCP Layer)

## Problem Statement

After Faza 1, the modernized skill is still **read-only with respect to live markets** — the user must manually describe charts or paste OHLCV data for analysis. The agent cannot autonomously pull market data, render charts for Vision-based analysis, or compute spread charts for crypto rotation detection. This makes the skill cumbersome for routine use ("just analyze BTC 1d") and prevents the agent from operating as a self-sufficient Wyckoff analyst.

## Evidence

- Existing skill workflow assumes user provides chart description or pre-extracted data — verified by reading `skills/wyckoff-trader-skill/SKILL.md` §0 ("prefer local corpus") and §3 ("apply crypto overlays" — assumes user has the spread chart in front of them).
- Existing `agents/openai.yaml` default prompt: "Use $wyckoff-trader-skill to build a disciplined Wyckoff scenario for **this market**" — assumes the user already has a specific market open.
- Wyckoff is a fundamentally visual method (per book chapters 14–25 — event recognition is bar-by-bar spatial reading), but the agent has no way to obtain or render the charts it needs to analyze.
- Spread charts (ETHBTC, LINKBTC) are the primary tool for crypto leadership detection per `crypto_adaptations.md` §4 — currently the user must compute and render these manually.

## Proposed Solution

Build three MCP servers that give the agent **hands and eyes** for live market analysis:

1. **OHLCV server** — fetch open/high/low/close/volume data for any crypto symbol/timeframe from exchange APIs
2. **Chart renderer** — convert OHLCV into candlestick + volume chart images optimized for Vision analysis
3. **Spread chart server** — compute and render ratio charts (ETHBTC, etc.) for leadership detection

The skill from Faza 1 remains the methodology brain; MCP adds the data layer. With both, the agent can take a query like "Analyze BTC 1d" and autonomously: pull data → render chart → Vision-analyze → produce a 9-section scenario tree with provenance to wiki concepts.

## Key Hypothesis

We believe **autonomous chart pulling and rendering** will **transform the skill from a research tool into a real-time analyst** for **practitioners watching live crypto markets**. We'll know we're right when **a user can query "Analyze BTC 1d" with no chart input AND receive a contract-compliant scenario output AND the agent demonstrably used the MCP tools (verified via tool-call trace)**.

## What We're NOT Building

- **Paper trading, virtual portfolio, P&L tracking** — defers to Faza 3
- **Multi-symbol scanning** — defers to Faza 3
- **Signal generation, buy/sell recommendations** — defers to Faza 3
- **ML phase classification** — defers to Faza 3
- **Streaming / real-time push notifications** — agent is request/response; polling on demand is enough
- **Authenticated trading endpoints** — read-only public APIs only (Binance public, etc.)

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Symbol coverage | ≥ top 50 crypto pairs by volume (USD + perp) | MCP `get_supported_symbols()` returns ≥ 50 |
| Timeframe coverage | At minimum: 1h, 4h, 1d, 1w | Schema test |
| Render quality | Charts pass Vision recognizability check (5/5 randomly sampled charts correctly identify event/structure when prompted) | Manual review on validation set |
| End-to-end autonomous analysis | Agent produces a contract-compliant scenario for "BTC 1d" with no user input beyond the symbol | Validation transcript |
| Latency | MCP tool call returns in < 3s for typical OHLCV + render (200 candles, 1200×600px) | Benchmark log |

## Open Questions

- [ ] Exchange source: Binance public, Bybit, CoinGecko aggregate, or multi-source fallback? Currently issue #9 leans Binance — confirm before implementation
- [ ] Chart styling: `mplfinance` defaults or custom Wyckoff-tailored style with phase-bar annotations?
- [ ] Spread chart calculation: simple `close_ratio` series or full OHLCV ratio with proper high/low derivation?
- [ ] Should there be a shared data client (per #12 design note) abstracted across the three servers, or separate dependencies per server?
- [ ] Cache policy: per-process LRU, on-disk, or none?

---

## Users & Context

**Primary User**
- **Who**: Same as Faza 1 — solo crypto trader / Wyckoff practitioner; now expects the agent to fetch data on its own
- **Current behavior** (post-Faza-1): manually describes chart OR pastes OHLCV before invoking the skill
- **Trigger**: Sees a symbol mentioned somewhere and wants quick Wyckoff read without leaving the conversation
- **Success state**: Says "Analyze BTC 1d" and gets full scenario without further input

**Job to Be Done**

When **I want a Wyckoff read on a specific symbol**, I want to **provide just the symbol + timeframe** so I can **get a complete analysis without manual data prep**.

**Non-Users**
- Users who only ever use the skill for offline education / concept lookup (concept mode from Faza 1 doesn't need MCP)
- Anyone needing tick-level / microstructure analysis (MCP is candle-level only)

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | `get_ohlcv(symbol, timeframe, limit)` | Foundational — every other capability depends on data |
| Must | `render_chart(ohlcv, title, annotations)` returning PNG | Wyckoff needs visual; Vision needs an image |
| Must | `render_chart_for_symbol(symbol, tf, limit)` convenience wrapper | Most common call pattern |
| Must | `get_spread(base, quote, tf, limit)` + `render_spread_chart(...)` | Crypto Wyckoff rotation analysis requires spread charts |
| Should | `get_supported_symbols()`, `get_timeframes()` | Discoverability for the agent |
| Should | Shared data client across all three servers | Avoid duplicate API calls per session (per #12 note) |
| Could | Annotation layer (horizontal lines for SC/AR/spring levels passed by agent) | Useful for re-rendering with agent-identified levels |
| Could | Multi-exchange fallback (Binance → Bybit → CoinGecko) | Resilience but adds complexity |
| Won't | Authenticated endpoints / order placement | Out of scope |
| Won't | Real-time streaming via WebSocket | Polling is sufficient for analysis |

### MVP Scope

Minimum to validate hypothesis:

1. OHLCV server with Binance public API, supports BTC/USDT + ETH/USDT + top 20 alts on 1h/4h/1d/1w (#9)
2. Chart renderer using `mplfinance` with `wyckoff_style` preset (#10)
3. Spread chart server for BTC-denominated pairs (#11)
4. Skill update: `agents/openai.yaml` and SKILL.md mention MCP-enabled flow
5. Validation: 3 of 8 canonical Faza-1 prompts run end-to-end with MCP

### User Flow

```
User → "Analyze BTC 1d"
       ↓
Skill recognizes scenario mode + needs market data
       ↓
Agent calls get_ohlcv("BTC/USDT", "1d", 200) via MCP
       ↓
Agent calls render_chart_for_symbol(...) → PNG
       ↓
Vision analyzes PNG → identifies structure, phase, events
       ↓
Wiki citations + OHLCV-derived facts (e.g., volume comparison) compose 9-section output
```

---

## Technical Approach

**Feasibility**: HIGH

**Architecture Notes**
- Three MCP servers, one Python package (`scripts/mcp/`) or three separate packages — TBD in #12 design
- Shared data client recommended in #12 — defer decision until first server prototype
- `mplfinance` is the prime candidate for rendering — well-supported, candlestick + volume out of the box
- Chart resolution: 1200×600px minimum (per #10 spec) for Vision to resolve individual bars

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Binance API rate limits hit during heavy use | Medium | Implement session cache; consider CoinGecko fallback for popular symbols |
| `mplfinance` styling produces charts Vision struggles with | Low | Pilot 10 charts with Vision before standardizing |
| Spread chart calculation edge cases (zero volume, gaps) | Medium | Use closing-price ratio as default; OHLC derivation as optional |
| Symbol naming inconsistency across exchanges (BTCUSDT vs BTC/USDT vs BTCUSD) | Medium | Normalize internally to one canonical form |
| MCP protocol changes break server | Low | Pin MCP SDK version |

---

## Implementation Phases

| # | Phase | Milestone | Description | Status | Plan |
|---|-------|-----------|-------------|--------|------|
| 1 | Market data MCP | M4 | OHLCV server with Binance public API | complete | [PRPs/plans/completed/market-data-mcp-ohlcv.plan.md](../../../PRPs/plans/completed/market-data-mcp-ohlcv.plan.md) |
| 2 | Chart renderer MCP | M4 | OHLCV → PNG via `mplfinance` | complete | [PRPs/plans/completed/10-chart-renderer-mcp.plan.md](../../../PRPs/plans/completed/10-chart-renderer-mcp.plan.md) |
| 3 | Spread chart MCP | M4 | Ratio OHLCV + spread chart render | in-progress (depends on #1; parallel with #2) | [PRPs/plans/11-spread-chart-mcp.plan.md](../../../PRPs/plans/11-spread-chart-mcp.plan.md) |
| 4 | Skill integration | M4 | Update SKILL.md + agents/openai.yaml to use MCP | pending (depends on #1, #2, #3) | |
| 5 | E2E validation Phase B | M4 (or #13 Phase B) | 3 MCP-driven prompts validated | pending (depends on #4) | |

### Phase Details

**Phase 1: Market data MCP**
- **Goal**: `get_ohlcv()`, `get_supported_symbols()`, `get_timeframes()` working against Binance public API
- **Issues**: [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9)
- **Success signal**: MCP tool call returns 200-candle BTC/USDT 1d data in JSON

**Phase 2: Chart renderer MCP**
- **Goal**: `render_chart(ohlcv)` returns PNG path or base64 suitable for Vision
- **Issues**: [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10)
- **Success signal**: Sample chart shown to Vision returns coherent description with structure/event identification

**Phase 3: Spread chart MCP**
- **Goal**: `get_spread()` and `render_spread_chart()` for default pairs (ETHBTC, LINKBTC, etc.)
- **Issues**: [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11)
- **Success signal**: ETHBTC spread chart renders and matches manually-computed values within rounding

**Phase 4: Skill integration**
- **Goal**: Skill description and workflow reflect MCP availability; user can invoke skill with just a symbol
- **Issues**: Update [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) (Faza-1 work touches this) + new issue for MCP-aware SKILL.md additions
- **Success signal**: `agents/openai.yaml` references MCP tools; SKILL.md §0 includes "if MCP is available, prefer pulling fresh data over user-provided"

**Phase 5: E2E validation Phase B**
- **Goal**: 3 MCP-driven prompts in [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) Phase B run successfully end-to-end
- **Issues**: extends [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13)
- **Success signal**: validation report shows MCP tool-call traces + contract-compliant outputs

### Parallelism Notes

- Phase 2 (chart renderer) and Phase 3 (spread chart) can run in parallel — both depend on Phase 1 (OHLCV) but not on each other
- Phase 4 (skill integration) is sequential after 1+2+3; can begin as soon as all three MCP servers expose a stable interface, even before validation

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Exchange source | Binance public API (default), CoinGecko fallback | Bybit, Kraken, multi-exchange aggregator | Best free symbol coverage, no auth required |
| Chart library | `mplfinance` | `plotly`, custom matplotlib | Candlestick + volume built-in, simplest path |
| Tool registration | Three separate MCP servers (one per concern) | One server with all tools | Cleaner failure isolation; allows independent versioning |
| Output format from renderer | PNG file path | base64 inline | Smaller agent context; file persists for re-use |
| Caching layer | Per-process LRU (in shared data client) | Disk cache, no cache | Avoid duplicate API calls in single session |

---

## Research Summary

**Market Context**
- Binance, Bybit, CoinGecko all expose public OHLCV without auth — choice is convenience, not access
- `mplfinance` is the de-facto Python library for OHLCV chart rendering; alternatives (`plotly.graph_objects`) have steeper learning curve
- MCP ecosystem is growing; existing reference servers (filesystem, brave-search) document the protocol patterns

**Technical Context**
- `uv` package layout already set up in repo root for Python scripts
- No existing MCP infrastructure in repo — Faza 2 is a new directory tree (`scripts/mcp/` or similar)
- Vision recognizability is the key gating factor — must pilot before standardizing chart style

---

## Linked GitHub Issues

| Issue | Title | Status |
|---|---|---|
| [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9) | Market data MCP server (OHLCV) | Open |
| [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10) | Chart renderer MCP server | Open |
| [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11) | Spread chart MCP server | Open |
| [#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12) | MCP server integration tracking | Open |
| NEW | Skill: integrate MCP into SKILL.md + openai.yaml | To be created |
| NEW | E2E validation Phase B (MCP-driven prompts) | To be created (extends #13) |

---

*Generated: 2026-05-24*
*Status: PLANNED — depends on Faza-1 completion*
