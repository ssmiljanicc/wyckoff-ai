# Phase B MCP Live Prompt Set

These prompts are non-deterministic because they depend on current market data
and available MCP server configuration. They are retained as best-effort live
checks, not as blockers for Phase A wiki-only validation.

## B1

Prompt: "Pull BTC 1d for the last 200 days, render the chart, and identify the
current Wyckoff phase."

Required tools: `scripts.mcp.market_data_server:get_ohlcv`,
`scripts.mcp.chart_renderer:render_chart_for_symbol`.

## B2

Prompt: "Pull ETHBTC 4h, render the spread, and tell me whether altcoins are
leading."

Required tools: `scripts.mcp.spread_chart_server:get_spread`,
`scripts.mcp.spread_chart_server:render_spread_chart`.

## B3

Prompt: "Pull a thin-liquidity alt and scan for spring/upthrust setups."

Required tools: `scripts.mcp.market_data_server:get_ohlcv` plus a scanner or
manual Wyckoff diagnostic pass. If exchange support or symbol liquidity is
insufficient, document the missing dependency instead of failing Phase A.
