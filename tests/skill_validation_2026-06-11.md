# Skill Validation — 2026-06-11

## Context

Scope: issue #32, Phase B MCP-driven E2E validation after PR #64 merged the
MCP-aware updates to `skills/wyckoff-trader-skill/SKILL.md` and
`skills/wyckoff-trader-skill/agents/openai.yaml`.

Prompt source: `tests/prompts/phase_b_mcp_live.md`, with issue #32's concrete
SOL/USDT variant for B3.

Environment:

- Branch: `validation/issue-32-phase-b-mcp`
- Runtime: `uv run --extra mcp`
- Date/time of live data pull: 2026-06-11, Europe/Belgrade

Validation checks for each prompt:

1. MCP tool-call trace is present.
2. Vision (vizuelna analiza renderovanog chart-a) is performed on the rendered
   PNG before labels are assigned.
3. Output is contract-compliant (usklađen sa ugovorom odgovora) for the selected
   mode from `knowledge/wiki/scenarios/output-contract.md`.
4. Wiki citations are present where Wyckoff terminology is used.

## Phase B (MCP)

### B1 — BTC 1d Current Phase

Prompt:

> Pull BTC 1d for the last 200 days, render the chart, and identify the current
> Wyckoff phase.

MCP tool-call trace:

| Step | Tool | Arguments | Result |
| --- | --- | --- | --- |
| 1 | `get_ohlcv` | `symbol="BTC"`, `timeframe="1d"`, `limit=200` | 200 BTCUSDT candles returned |
| 2 | `render_chart` | `title="BTCUSDT 1d - 200 candles"` | PNG rendered, 1200x600, 200 candles |
| 3 | Vision | rendered PNG | Chart read before assigning labels |

Rendered chart:

`/var/folders/46/lj2d6ckx0fz82w5jtv5rrr7h0000gn/T/wyckoff-ai-chart-renderer/9a60cfbd02ab9f9b8ddb5304a28fc26b8b7bdbd58d327f4dac85fcdf981423e6.png`

Observed data:

- Latest close: `62842.01`
- 200-candle high/low: `97924.49` / `59130.91`
- Recent 40-candle high/low: `82850.00` / `59130.91`
- Latest close location in recent 40-candle range: `0.156` from low to high
- Average volume last 20 candles: `20925.48`
- Average volume prior 20 candles: `14120.68`

Vision read:

The chart shows a high area in January, a sharp markdown into early February,
a recovery/rally into the low 80k area by May, then a renewed decline into the
lower 60k area. Recent candles are near the lower end of the latest range with
elevated recent volume and only early stabilization. There is no clean spring
confirmation yet because the chart does not show a support sweep followed by a
successful test and sign of strength.

Mode selected: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** BTC 1d is near the lower end of the recent
   40-candle range after a persistent decline from the May rally high. Volume is
   higher than the prior 20-candle window, so the current zone is an active
   supply/demand test rather than a quiet completed base.
2. **Candidate label(s).** Leading read: late Phase B / unresolved testing range,
   not confirmed Phase C. Runner-up: early stopping action after markdown, but
   the chart still needs a higher-quality test before a stronger accumulation
   label is justified.
3. **Confidence and what is missing.** Confidence: medium-low. Per
   `knowledge/wiki/concepts/labeling-is-last-step.md`, labels are provisional
   until structure confirms them. A spring label would require the behavior
   described in `knowledge/wiki/events/spring.md`: false break, re-entry, test,
   and later strength. That confirmation is not visible in this chart.
4. **Optional escalation.** Scenario mode would require a forward plan with
   trigger/invalidation; from this chart alone the proper conclusion is
   watch/diagnose, not a trade call.

Evaluation:

- MCP trace: PASS.
- Vision on rendered chart: PASS.
- Mode contract: PASS, diagnostic four-part structure present.
- Wiki citations: PASS via `output-contract.md`, `labeling-is-last-step.md`,
  and `events/spring.md`.

### B2 — ETHBTC 4h Spread Leadership

Prompt:

> Pull ETHBTC 4h, render the spread, and tell me whether altcoins are leading.

MCP tool-call trace:

| Step | Tool | Arguments | Result |
| --- | --- | --- | --- |
| 1 | `get_spread` | `base_symbol="ETH"`, `quote_symbol="BTC"`, `timeframe="4h"`, `limit=200` | 200 ETH/BTC ratio candles returned |
| 2 | `render_spread_chart` | `base="ETH"`, `quote="BTC"`, `timeframe="4h"`, `limit=200` | PNG rendered, 1200x600, 200 ratio candles |
| 3 | Vision | rendered PNG | Spread chart read before rotation conclusion |

Rendered chart:

`/var/folders/46/lj2d6ckx0fz82w5jtv5rrr7h0000gn/T/wyckoff-ai-chart-renderer/cec970b30eb21f8119a2a52974ffcbed68d3134717316158ef6f2e072c92870c.png`

Observed data:

- Latest ETH/BTC ratio close: `0.02634925686642691`
- 200-candle high/low: `0.029047188511776404` / `0.02563841105631293`
- Recent 40-candle high/low: `0.027926407580900522` / `0.02563841105631293`
- Latest close location in recent 40-candle range: `0.311` from low to high
- Average ratio-volume proxy last 20 candles: `58407.54`
- Average ratio-volume proxy prior 20 candles: `120003.04`

Vision read:

The spread starts in a downtrend, attempts a sharp rally at the beginning of
June, then fails and breaks hard into a new lower area. The rebound from the
low is partial and stalls below the prior base. That does not support a current
altcoin-leadership read for ETH versus BTC.

Mode selected: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** ETH/BTC is not leading now. The spread
   failed after a short upside attempt, broke lower on a sharp move, and is only
   recovering weakly below the prior range.
2. **Candidate label(s).** Leading read: failed relative-strength attempt /
   weak spread. Runner-up: possible early repair attempt, but not yet confirmed
   leadership.
3. **Confidence and what is missing.** Confidence: medium. Crypto spread charts
   are used as leadership and rotation evidence, but the actual entry still
   belongs on the USD pair per `knowledge/wiki/crypto/spread-charts.md`. A
   leadership upgrade would require ETH/BTC to reclaim the failed range and
   show better comparative slope, consistent with
   `knowledge/wiki/crypto/comparative-strength.md` and
   `knowledge/wiki/crypto/rotation-hierarchy.md`.
4. **Optional escalation.** Scenario mode should add ETHUSDT and BTCUSDT context
   before making a forward path.

Evaluation:

- MCP trace: PASS.
- Vision on rendered chart: PASS.
- Mode contract: PASS, diagnostic four-part structure present.
- Wiki citations: PASS via `output-contract.md`, `crypto/spread-charts.md`,
  `crypto/comparative-strength.md`, and `crypto/rotation-hierarchy.md`.

### B3 — SOL/USDT 1d Spring / Upthrust Scan

Prompt:

> Pull SOL/USDT 1d for the last 60 days -- scan for spring or upthrust setups.

MCP tool-call trace:

| Step | Tool | Arguments | Result |
| --- | --- | --- | --- |
| 1 | `get_ohlcv` | `symbol="SOL"`, `timeframe="1d"`, `limit=60` | 60 SOLUSDT candles returned |
| 2 | `render_chart` | `title="SOLUSDT 1d - 60 candles"` | PNG rendered, 1200x600, 60 candles |
| 3 | Vision | rendered PNG | Chart scanned for spring/upthrust behavior |

Rendered chart:

`/var/folders/46/lj2d6ckx0fz82w5jtv5rrr7h0000gn/T/wyckoff-ai-chart-renderer/2710ed615ee74d3d45ed6489f9dfcbe21e9d3e19fd0e9d796ebe309d1fe5d998.png`

Observed data:

- Latest close: `65.44`
- 60-candle high/low: `98.41` / `60.13`
- Recent 40-candle high/low: `98.41` / `60.13`
- Latest close location in recent 40-candle range: `0.139` from low to high
- Average volume last 20 candles: `2791436.56`
- Average volume prior 20 candles: `2538788.90`

Vision read:

SOL 1d shows a May rally into the high 90s, then a controlled roll-over that
accelerates into early June. The latest bars sit near the lower end of the
60-day window after a high-volume downside leg. The chart does not show an
upthrust setup now because price is not testing the upper boundary. It also
does not yet show a confirmed spring because the move below/near support has
not been followed by a decisive re-entry, quiet test, and upward resolution.

Mode selected: diagnostic.

Contract-compliant output sample:

1. **What the price/volume shows.** SOL is testing the lower end of its 60-day
   range after a sharp markdown from the May high. Recent volume is slightly
   higher than the prior 20-candle window, so supply was active on the decline.
2. **Candidate label(s).** Leading read: lower-boundary test after markdown,
   not a confirmed spring. Runner-up: early spring candidate only if price
   re-enters the prior range and later holds a low-volume test. Upthrust is not
   supported because the chart is not near the upper boundary.
3. **Confidence and what is missing.** Confidence: medium. The spring criteria
   in `knowledge/wiki/events/spring.md` require false break/re-entry and a test;
   the upthrust criteria in `knowledge/wiki/events/upthrust.md` require an
   upper-boundary probe and re-entry. Per
   `knowledge/wiki/concepts/labeling-is-last-step.md`, this should remain a
   provisional lower-boundary test until follow-through resolves it.
4. **Optional escalation.** Scenario mode could define a trigger only after a
   reclaim/test sequence or a breakdown continuation becomes visible.

Evaluation:

- MCP trace: PASS.
- Vision on rendered chart: PASS.
- Mode contract: PASS, diagnostic four-part structure present.
- Wiki citations: PASS via `output-contract.md`, `events/spring.md`,
  `events/upthrust.md`, and `concepts/labeling-is-last-step.md`.

## Commands Run

```bash
uv run --extra mcp python - <<'PY'
# imported MCP tool wrappers and executed:
# get_ohlcv("BTC", "1d", 200) -> render_chart(...)
# get_spread("ETH", "BTC", "4h", 200) -> render_spread_chart(...)
# get_ohlcv("SOL", "1d", 60) -> render_chart(...)
PY
```

```bash
uv run pytest tests/test_market_data_server.py tests/test_chart_renderer.py tests/test_spread_chart_server.py
```

## Summary

All three Phase B prompts passed the acceptance signal:

- MCP tool-call trace: PASS for B1, B2, B3.
- Vision on rendered chart: PASS for B1, B2, B3.
- Contract-compliant output: PASS for B1, B2, B3.
- Wiki citations for Wyckoff terminology: PASS for B1, B2, B3.

Residual risk: this is a live-data validation, so exact prices and chart reads
are time-dependent. The important invariant is the workflow: pull data through
MCP, render a chart, inspect the rendered chart, then answer under the existing
mode contract with wiki citations.
