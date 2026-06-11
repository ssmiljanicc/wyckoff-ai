---
name: wyckoff-trader-skill
description: Use this skill to answer Wyckoff questions about markets (especially crypto) in one of three modes — scenario (a full forward-looking scenario tree), concept (definition of a term), or diagnostic (classify what a chart is showing). It reads from a provenance-tracked wiki so every claim traces back to a source. Use it for springs, upthrusts, SOS/SOW, LPS/LPSY, accumulation vs distribution, phase reading, intermarket gates, crypto rotation, and relative strength.
---

# Wyckoff Trader Skill

## Overview

This skill turns chart observations into disciplined Wyckoff analysis. It is
optimized for crypto but the core method is classical Wyckoff: context first,
then structure, then phase and event evidence, then — only for forward-looking
questions — a scenario tree instead of a single prediction. When a live market
query includes a clear symbol and timeframe, use available MCP market-data tools
as the primary observation source before relying on user-provided chart prose.

## Knowledge Base Architecture

The skill's knowledge lives in a **provenance-tracked wiki** at
`../../knowledge/wiki/` (relative to this file). Every substantive claim there
cites a raw source, so the skill's answers are traceable: answer → wiki page →
raw source.

**Runtime model (option B):** do **not** load the whole wiki. Always start by
reading the index, then read only the specific pages a query needs.

1. Read [`../../knowledge/wiki/index.md`](../../knowledge/wiki/index.md) — the
   navigation catalog. Every page is listed under its folder with a one-line
   description.
2. From the index, open the specific `concepts/`, `events/`, `structures/`,
   `crypto/`, or `scenarios/` pages the query requires.
3. Cite the wiki pages you used so the user can drill down to the raw source.

**Live-data precedence:** the wiki supplies method and vocabulary; MCP supplies
fresh observations. For a query such as "Analyze BTC 1d", first pull and render
the chart through MCP when those tools are available. Use the user's chart
description as supplemental context or as fallback only when MCP is unavailable
or the live fetch fails.

## Step 0 — Pick The Response Mode

Before answering, classify the query into **one** mode (full contract:
[`scenarios/output-contract.md`](../../knowledge/wiki/scenarios/output-contract.md)):

1. **Concept** — "what is X?", "explain Phase C", "spring vs upthrust?". No live
   data; the user wants knowledge.
2. **Diagnostic** — specific price/volume/structure observations supplied, asking
   "what is this?" / "what phase?". The user wants a classification.
3. **Scenario** — a forward-looking plan: scenario tree with trigger,
   invalidation, path ("build a scenario", "what's the setup?", "go/wait?").

Tie-breaks: forward path with trigger/invalidation → scenario; "what is this
right now" → diagnostic; symbol + timeframe with "analyze", "setup", "scenario",
"go/wait", or similar live-market intent → run the MCP workflow first, then pick
diagnostic or scenario from the user's requested output; general question →
concept.

## Mode Workflows

### Concept mode

Read the relevant `concepts/` or `events/` page via the index. Return: a 2–4
sentence definition in book vocabulary, 1–2 wiki citations, 2–3 related wiki
links, and one worked example (crypto preferred). Do **not** emit the
nine-section scenario contract.

### Diagnostic mode

Enforce [labeling-is-last-step](../../knowledge/wiki/concepts/labeling-is-last-step.md):
describe the price/volume behavior **before** naming a label. Return: what the
behavior shows, the candidate label(s) plus runner-up, the confidence and what
evidence would confirm or deny it, and an optional offer to escalate to scenario
mode.

### Scenario mode

Route through the master tree
([`scenarios/playbook-master.md`](../../knowledge/wiki/scenarios/playbook-master.md)),
then produce the full nine-section contract:

1. Context (market-cycle position; buying/selling/neutral)
2. Wyckoff story (supply/demand narrative so far)
3. Phase and event evidence (Phase A–E + events)
4. Crypto overlays (intermarket gate, BTC leadership, rotation, relative
   strength — run
   [`scenarios/crypto-rotation-watch.md`](../../knowledge/wiki/scenarios/crypto-rotation-watch.md))
5. Leading scenario (thesis, trigger, invalidation, path, intermarket
   dependency, evidence quality)
6. Alternate scenario(s) — at least one credible alternate
7. Trigger, invalidation, target path (comparative, not absolute)
8. What would change the read
9. Trade / wait / no-trade conclusion

Pick the matching entry template from the tree:
[accumulation-phase-c-entry](../../knowledge/wiki/scenarios/accumulation-phase-c-entry.md),
[distribution-phase-c-entry](../../knowledge/wiki/scenarios/distribution-phase-c-entry.md),
[phase-d-breakout-test](../../knowledge/wiki/scenarios/phase-d-breakout-test.md),
or [no-shake-foothold](../../knowledge/wiki/scenarios/no-shake-foothold.md).

## Step 3.5 — MCP-Driven Live Workflow

Use this workflow when the query contains enough market identity to fetch live
data: at minimum a symbol and timeframe, with an analysis, diagnostic, or
scenario intent.

1. Normalize the symbol and timeframe without changing the user's intent
   (`BTC 1d` → `BTCUSDT`, `1d` unless the user specified another quote asset).
2. Pull candles with `get_ohlcv(symbol, timeframe, limit)`. Use enough candles
   to see the current structure; default to about 200 bars when the user does
   not specify a lookback.
3. Render a Vision-readable chart from those candles with `render_chart`. If the
   runtime exposes only the shortcut renderer, `render_chart_for_symbol` is
   acceptable, but the answer must still state the fetched symbol, timeframe,
   lookback, and candle count.
4. Inspect the rendered chart before naming Wyckoff labels. Preserve the normal
   label-last discipline: describe range boundaries, swing quality, volume/effort
   behavior, tests, and relative position first.
5. For crypto overlay checks, use spread tools when the question needs relative
   strength or rotation evidence: `get_spread` and `render_spread_chart` for
   pairs such as `ETH/BTC`. Do not require spread calls for a simple BTC-only
   diagnostic unless the scenario conclusion depends on rotation.
6. Include a brief **MCP trace** in the answer before the mode-specific output:
   tools called, symbol/timeframe, lookback, rendered chart path if available,
   and any fetch/render failure.
7. Then produce the selected mode output. Scenario mode still uses the full
   nine-section contract, and section 1 (Context) must be grounded in the MCP
   candles/chart when the live workflow succeeded.

Fallback discipline:

- If MCP tools are not available, say so explicitly and ask for chart
  observations or an image before making a live-current claim.
- If `get_ohlcv` fails or the symbol/timeframe is unsupported, report the
  failure and either ask for corrected inputs or proceed only on user-supplied
  observations.
- Never fabricate live price, phase, volume, spread, or chart state when the MCP
  pull/render did not succeed.

## Core Rules

- **Label last.** Read price/volume behavior first; assign structure labels only
  after the story is coherent.
- **Context outranks pattern.** A spring in the wrong background is noise.
- **Scenarios, not certainties.** Every forward read carries an explicit
  invalidation.
- **Path of least resistance**, not the most dramatic narrative.
- **Crypto:** always check the intermarket gate and internal rotation before a
  directional view.
- **Mixed evidence → no-trade / wait**, not a forced thesis.
- **No trade calls** (`/CLAUDE.md` §9): describe what *would* count as evidence;
  never emit a bare "buy here".
- **Cite the wiki.** Every concept/diagnostic claim names the wiki page it came
  from.
- **MCP trace for live queries.** When live data is used, show the tool-call
  trace and distinguish tool observations from Wyckoff interpretation.

## References

- Navigation: [`../../knowledge/wiki/index.md`](../../knowledge/wiki/index.md)
- Response contract: [`scenarios/output-contract.md`](../../knowledge/wiki/scenarios/output-contract.md)
- Scenario tree: [`scenarios/playbook-master.md`](../../knowledge/wiki/scenarios/playbook-master.md)
- Updating the skill / wiki: [`runbooks/wyckoff-wiki-ingest.md`](../../runbooks/wyckoff-wiki-ingest.md)
- Domain schema: [`/CLAUDE.md`](../../CLAUDE.md)
