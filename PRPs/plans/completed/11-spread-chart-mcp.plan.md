# Feature: Spread Chart MCP Server

## Summary

Implement GitHub issue #11: a Python MCP server that computes crypto ratio OHLCV series and renders spread charts for rotation analysis through:

- `get_spread(base_symbol, quote_symbol, timeframe, limit)`
- `render_spread_chart(base, quote, timeframe, limit)`

This is Phase 3 of `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md`: "Spread chart MCP". It builds on the completed issue #9 market data client and mirrors the completed issue #10 chart renderer pattern.

## User Story

As a crypto Wyckoff practitioner,
I want the agent to compute and render BTC-denominated spread charts,
So that I can evaluate relative leadership such as ETH/BTC, LINK/BTC, and SOL/BTC without manually preparing ratio charts.

## Problem Statement

The skill can reason about crypto relative strength, but the repo currently exposes only raw OHLCV (`get_ohlcv`) and direct OHLCV chart rendering (`render_chart`). It cannot compute pair ratios or render spread charts, even though the PRD identifies spread charts as a primary crypto leadership tool.

## Solution Statement

Add a new `scripts/mcp/spread_chart_server.py` module with:

- ratio candle calculation using shared `BinanceMarketDataClient`
- deterministic validation and alignment of base and quote candles by `open_time`
- bounded per-process LRU cache for spread data and rendered spread metadata
- FastMCP tool wrappers for `get_spread` and `render_spread_chart`
- chart rendering that reuses the existing `chart_renderer.render_chart_image` and `wyckoff_style` conventions
- focused unit tests plus a live/manual sanity check command for `ETHBTC`

## Metadata

| Field | Value |
| --- | --- |
| Source issue | #11, Spread chart MCP server |
| PRD | `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md` Phase 3 |
| Feature type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Dependencies | Issue #9 complete; issue #10 complete |
| Primary files | `scripts/mcp/spread_chart_server.py`, `tests/test_spread_chart_server.py` |
| Default test pairs | `ETHBTC`, `LINKBTC`, `SOLBTC` |

## UX Design

Current operator/API flow:

```text
User/agent wants ETHBTC leadership read
  -> manually fetch ETH and BTC candles
  -> manually divide closes
  -> manually render chart
  -> provide image or description to skill
```

Future operator/API flow:

```text
User/agent wants ETHBTC leadership read
  -> MCP get_spread("ETH", "BTC", "1d", 200)
     -> BinanceMarketDataClient.get_ohlcv("ETHUSDT", "1d", 200)
     -> BinanceMarketDataClient.get_ohlcv("BTCUSDT", "1d", 200)
     -> align candles by open_time
     -> compute ratio OHLCV
  -> MCP render_spread_chart("ETH", "BTC", "1d", 200)
     -> return PNG metadata/path
  -> Vision/Wyckoff skill analyzes spread chart
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| MCP layer | Market data and normal chart tools only | Spread server exposes ratio data and rendered spread images | Agent can inspect crypto leadership autonomously |
| Data flow | Caller must manually compose two OHLCV series | Server fetches and aligns base/quote candles | Less manual data prep and fewer arithmetic mistakes |
| Chart output | `render_chart` accepts supplied OHLCV only | `render_spread_chart` returns a ready PNG path | Vision can read ETHBTC/LINKBTC/SOLBTC charts directly |

## Mandatory Reading

- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:164-167` - Phase 3 goal and success signal for `get_spread()` and `render_spread_chart()`.
- `scripts/mcp/market_data_client.py:75-94` - symbol normalization, including `ETHBTC` preservation and default `USDT` quote behavior.
- `scripts/mcp/market_data_client.py:110-161` - shared `BinanceMarketDataClient.get_ohlcv()` cache and fetch contract.
- `scripts/mcp/chart_renderer.py:189-245` - existing `render_chart_image()` behavior, output metadata, cache style, dimensions, and PNG path convention.
- `scripts/mcp/chart_renderer.py:248-267` - FastMCP tool wrapper style and market-data composition pattern.
- `tests/test_chart_renderer.py:134-176` - cache and fake-client tests to mirror.
- `tests/test_market_data_server.py:37-62` - thin MCP wrapper tests to mirror.

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| NAMING | `scripts/mcp/market_data_server.py:16-23` | Module-level `mcp`, module-level shared client, thin decorated wrapper. | `mcp = FastMCP("wyckoff-market-data")` / `@mcp.tool()` / `return client.get_ohlcv(...)` |
| TYPES | `scripts/mcp/market_data_client.py:32-42` | JSON-serializable `TypedDict` candle shape. | `class Candle(TypedDict): open_time: int ... close: float ... volume: float` |
| CACHE | `scripts/mcp/market_data_client.py:140-161` | Normalize inputs, check `OrderedDict` LRU, return copies, set cache only after successful computation. | `if cache_key in self._ohlcv_cache: self._ohlcv_cache.move_to_end(cache_key)` |
| RENDERING | `scripts/mcp/chart_renderer.py:189-245` | Pure render helper validates OHLCV, writes PNG under temp cache dir, returns metadata. | `render_chart_image(..., width=MIN_WIDTH, height=MIN_HEIGHT) -> RenderedChart` |
| ERRORS | `scripts/mcp/chart_renderer.py:100-145` | Validate input early with specific `ValueError` messages. | `raise ValueError("ohlcv_data must be a non-empty list of candles")` |
| TESTS | `tests/test_chart_renderer.py:164-176` | Monkeypatch module-level client and cache dir for deterministic wrapper tests. | `monkeypatch.setattr(chart_renderer, "market_data_client", fake)` |
| FLOW | `scripts/mcp/chart_renderer.py:258-267` | Convenience tool composes market client fetch with renderer and formats title. | `ohlcv_data = market_data_client.get_ohlcv(symbol, timeframe, limit)` |

## External Documentation

- [mplfinance README](https://github.com/matplotlib/mplfinance/blob/master/README.md)
  - KEY_INSIGHT: `mpf.plot()` expects a Pandas DataFrame with Open, High, Low, Close and a Pandas `DatetimeIndex`; `type='candle'` and `volume=True` are documented use cases.
  - APPLIES_TO: `render_spread_chart()` via existing `chart_renderer.render_chart_image()`.
  - GOTCHA: Keep ratio candles in the same OHLCV shape and positive price domain so existing validation accepts them.
- [MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk)
  - KEY_INSIGHT: Official FastMCP examples use `from mcp.server.fastmcp import FastMCP`, `@mcp.tool()`, structured output from `TypedDict`, and `mcp.run()` for direct execution.
  - APPLIES_TO: `scripts/mcp/spread_chart_server.py`.
  - GOTCHA: Keep return values JSON-serializable and typed; do not return raw DataFrames or matplotlib objects.

## Files to Change

| File | Change |
| --- | --- |
| `scripts/mcp/spread_chart_server.py` | Add new spread MCP server, ratio calculation helpers, LRU caches, render wrapper, and `main()`. |
| `tests/test_spread_chart_server.py` | Add unit tests for symbol pair normalization, ratio calculation, alignment, cache behavior, fake-client rendering, and wrappers. |
| `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md` | Mark Phase 3 as `in-progress` and link this plan. |
| `PRPs/reports/11-spread-chart-mcp-report.md` | Created by `prp-implement` after implementation. |
| `PRPs/plans/completed/11-spread-chart-mcp.plan.md` | Created by `prp-implement` after successful implementation. |

## NOT Building

- No persistent disk cache for fetched ratio data.
- No custom ratio high/low reconstruction from intra-bar ticks.
- No multi-exchange fallback.
- No WebSocket or real-time streaming.
- No skill prompt/workflow update; that is PRD Phase 4.
- No trading signals or recommendations.
- No base64 image payloads unless a future MCP client requires them.

## Strategic Design

`APPROACH_CHOSEN`: create a dedicated spread MCP server that imports and reuses the shared `BinanceMarketDataClient` and the existing chart renderer.

`RATIONALE`: issue #9 already owns Binance normalization, HTTP, rate limiting, and OHLCV caching. Issue #10 already owns `mplfinance` rendering and PNG metadata. The spread server should only own pair composition and ratio semantics.

`ALTERNATIVES_REJECTED`:

- Fetch `ETHBTC` directly from Binance: it gives a market pair, but the requested ratio formula is `base_close / quote_close` and the shared client defaults `ETH` and `BTC` to USDT pairs. Fetching two normalized USD-denominated series keeps ratio behavior explicit and also works for pairs Binance may not list directly.
- Copy chart rendering code into the spread server: duplicates validation, styling, dimensions, cache semantics, and future maintenance.
- Use pandas joins as the core API: useful internally, but server contracts should stay list/dict JSON structures.

`NOT_BUILDING`: advanced high/low derivation. For MVP, compute a single ratio point per candle and set `open`, `high`, `low`, and `close` consistently from available close ratios. If implementing adjacent-close open is straightforward, set `open` to the previous close ratio; otherwise set `open == close`.

`FAILURE_MODES`:

- Base and quote series have mismatched timestamps: align by `open_time`; drop unmatched candles; fail if no aligned candles remain.
- Quote close is zero or non-positive: raise `ValueError` and do not render.
- Too few aligned candles for rendering: return data from `get_spread`, but rendering should rely on `chart_renderer` validation and fail clearly if input is invalid.
- Binance upstream errors: let `BinanceMarketDataClient` domain errors surface.

`PERFORMANCE`: two upstream OHLCV calls per uncached spread request. Use a spread-level LRU so repeated `get_spread` and `render_spread_chart` calls do not recompute ratios, while relying on issue #9 client cache to avoid duplicate HTTP calls.

`SECURITY`: public market data only; validate symbol strings through existing market client; do not use shell, filesystem paths from inputs, or authenticated APIs.

## Step-by-Step Tasks

1. Create the spread server module.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: add module docstring, imports, FastMCP fallback pattern matching `chart_renderer.py:17-31`, imports from `market_data_client`, imports `render_chart_image`, constants `DEFAULT_SPREAD_LIMIT = DEFAULT_LIMIT`, `SPREAD_CACHE_SIZE = 128`, `RENDER_CACHE_DIR` reuse through chart renderer.
   - Pattern to mirror: `scripts/mcp/chart_renderer.py:17-48`.
   - Gotcha: do not import matplotlib directly in this module; rendering is delegated.
   - Validation command: `uv run --extra mcp python -c "from scripts.mcp import spread_chart_server; print(spread_chart_server.mcp.name)"`

2. Define spread output types and cache keys.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: create `SpreadCandle(TypedDict)` with `open_time`, `open`, `high`, `low`, `close`, `volume`, optional `close_time`, `base_close`, `quote_close`; create `SpreadResult(TypedDict)` with `base_symbol`, `quote_symbol`, `timeframe`, `limit`, `candle_count`, `ohlcv`; create frozen dataclass `_SpreadCacheKey`.
   - Pattern to mirror: `scripts/mcp/market_data_client.py:32-42` and `_CacheKey` at `68-72`.
   - Gotcha: keep values JSON serializable; do not return dataclass instances from tools.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k types` after tests are added.

3. Implement symbol pair normalization for spread inputs.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: add `normalize_spread_pair(base_symbol, quote_symbol)` returning display symbols without separators and rejecting identical normalized symbols. Use `normalize_symbol()` from `market_data_client` only for validation/fetch targets where useful, but keep display symbols like `ETH` and `BTC` for title/result metadata.
   - Pattern to mirror: `market_data_client.normalize_symbol()` validation style.
   - Gotcha: `base_symbol="ETH"` and `quote_symbol="BTC"` should fetch `ETHUSDT` and `BTCUSDT`; `base_symbol="ETHUSDT"` should not lead to `ETHUSDTUSDT`.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k normalize`.

4. Implement ratio candle calculation.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: add `calculate_spread_ohlcv(base_candles, quote_candles)` that aligns candles by `open_time`, computes `close_ratio = base_close / quote_close`, uses numerator/base `volume`, and sets `high`/`low` as max/min of available ratio values for that output bar. For MVP, `open` may equal previous close ratio when available and current close for the first bar; `high=max(open_ratio, close_ratio)`, `low=min(open_ratio, close_ratio)`.
   - Pattern to mirror: `chart_renderer.validate_ohlcv_data()` positive numeric assumptions.
   - Gotcha: quote close must be positive; output `high >= open/close`, `low <= open/close`, prices positive, and `open_time` strictly increasing.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k calculate`.

5. Implement `get_spread_data()` pure helper with per-process LRU cache.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: create module-level `market_data_client = BinanceMarketDataClient()`, `_spread_cache: OrderedDict[_SpreadCacheKey, SpreadResult]`, `_get_cached_spread`, `_set_cached_spread`, and `get_spread_data(base_symbol, quote_symbol, timeframe, limit)` that fetches two OHLCV series, computes spread candles, returns copied JSON structures, and caches identical normalized requests.
   - Pattern to mirror: `market_data_client.py:140-161` and `chart_renderer.py:398-414`.
   - Gotcha: cache returned data must not be mutable shared internals; return shallow/deep-enough copies of candle dicts.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k cache`.

6. Implement `get_spread` MCP tool.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: instantiate `mcp = FastMCP("wyckoff-spread-chart")`; decorate `get_spread(base_symbol, quote_symbol, timeframe, limit=DEFAULT_LIMIT)` and return `get_spread_data(...)`.
   - Pattern to mirror: `market_data_server.py:20-23`.
   - Gotcha: tool name must be exactly `get_spread`.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k wrapper`.

7. Implement spread chart rendering.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: add `render_spread_chart(base, quote, timeframe, limit=DEFAULT_LIMIT)` as an MCP tool. It should call `get_spread_data`, pass returned `ohlcv` to `chart_renderer.render_chart_image`, title the chart like `"ETH/BTC spread 1d"`, and extend returned metadata with `base_symbol`, `quote_symbol`, `timeframe`, and `ratio_candle_count` if practical.
   - Pattern to mirror: `chart_renderer.render_chart_for_symbol()` at `258-267`.
   - Gotcha: chart renderer may return `cached=True` independently; preserve that field.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py -k render`.

8. Add direct execution entry point.
   - File: `scripts/mcp/spread_chart_server.py`.
   - Instruction: add `main()` calling `mcp.run()` and the standard `if __name__ == "__main__": main()` block.
   - Pattern to mirror: `market_data_server.py:38-43` and `chart_renderer.py:323-324,441-442`.
   - Gotcha: import-time side effects should be limited to module-level client/cache construction.
   - Validation command: `timeout 2 uv run --extra mcp python -m scripts.mcp.spread_chart_server || true` and confirm no immediate import traceback.

9. Add spread server tests.
   - File: `tests/test_spread_chart_server.py`.
   - Instruction: cover normalization, identical symbol rejection, aligned ratio calculation, unmatched timestamp dropping, zero quote close rejection, cache hit avoiding fake-client duplicate calls, `get_spread` wrapper, `render_spread_chart` producing a PNG with fake data and temp cache dir.
   - Pattern to mirror: `tests/test_chart_renderer.py` and `tests/test_market_data_server.py`.
   - Gotcha: monkeypatch both `spread_chart_server.market_data_client` and `chart_renderer.RENDER_CACHE_DIR` or pass through a patched rendering helper to keep tests deterministic.
   - Validation command: `uv run pytest -q tests/test_spread_chart_server.py`.

10. Run full validation and live/manual sanity checks.
    - Files: code and tests above.
    - Instruction: run all existing MCP tests plus live spread commands. For manual sanity, compute first/last ETH/BTC close ratio from returned spread and compare to `ETH close / BTC close` from the same candles.
    - Pattern to mirror: report style in `PRPs/reports/10-chart-renderer-mcp-report.md`.
    - Gotcha: if live Binance is unavailable or region-blocked, document the failure and keep fake-client tests passing.
    - Validation command: see "Validation Commands".

## Testing Strategy

- Unit tests: pure ratio helper, pair normalization, timestamp alignment, zero quote close errors.
- Cache tests: repeated identical requests with fake client should avoid duplicate fake fetches.
- Wrapper tests: `get_spread()` delegates to helper/client and returns JSON-serializable data.
- Render tests: fake market client plus temp chart cache dir should produce a 1200x600 PNG through `render_spread_chart()`.
- Regression tests: run existing market data and chart renderer suites to ensure imports and shared client behavior are unchanged.
- Live smoke: run ETH/BTC, LINK/BTC, and SOL/BTC small-limit requests if Binance is reachable.

## Validation Commands

```bash
uv run --extra mcp python -c "from scripts.mcp import spread_chart_server; print(spread_chart_server.mcp.name)"
uv run pytest -q tests/test_spread_chart_server.py
uv run pytest -q tests/test_market_data_client.py tests/test_market_data_server.py tests/test_chart_renderer.py tests/test_spread_chart_server.py
uv run --extra mcp python -c "from scripts.mcp.spread_chart_server import get_spread; r=get_spread('ETH','BTC','1d',5); print(r['base_symbol'], r['quote_symbol'], r['candle_count'], r['ohlcv'][-1]['close'])"
uv run --extra mcp python -c "from scripts.mcp.spread_chart_server import render_spread_chart; print(render_spread_chart('ETH','BTC','1d',80))"
uv run --extra mcp python -c "from scripts.mcp.spread_chart_server import get_spread; [print(pair, get_spread(pair[:-3], pair[-3:], '1d', 5)['ohlcv'][-1]['close']) for pair in ['ETHBTC','LINKBTC','SOLBTC']]"
```

## Acceptance Criteria

- `scripts/mcp/spread_chart_server.py` imports cleanly.
- MCP server name is `wyckoff-spread-chart`.
- `get_spread(base_symbol, quote_symbol, timeframe, limit)` returns JSON-serializable ratio OHLCV data.
- `render_spread_chart(base, quote, timeframe, limit)` returns chart metadata with a local PNG path.
- ETH/BTC spread render creates a meaningful 1200x600 chart using the existing Wyckoff chart style.
- Manual sanity check confirms at least one returned `close` ratio equals `base_close / quote_close` within normal floating-point rounding.
- Default pairs `ETHBTC`, `LINKBTC`, and `SOLBTC` work in fake-client tests and live smoke when Binance is reachable.
- Repeated identical spread requests use a bounded per-process LRU cache.
- Existing market data and chart renderer tests still pass.

## Completion Checklist

- [ ] `scripts/mcp/spread_chart_server.py` added.
- [ ] `tests/test_spread_chart_server.py` added.
- [ ] `get_spread` tool exposed.
- [ ] `render_spread_chart` tool exposed.
- [ ] Ratio OHLCV calculation validates positive quote close and aligned timestamps.
- [ ] Per-process spread LRU cache implemented and tested.
- [ ] ETHBTC manual sanity value checked or live-network limitation documented.
- [ ] Full MCP-related pytest suite passes.
- [ ] Implementation report written by `prp-implement`.
- [ ] Plan archived by `prp-implement`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Ambiguous base/quote input (`ETHBTC` vs `ETH`, `BTC`) | Wrong fetch targets or confusing metadata | Public tools accept separate base/quote args; tests cover default pairs; title uses slash form |
| Timestamp mismatch between base and quote candles | Incorrect ratio alignment | Align by `open_time`, drop unmatched candles, fail if no overlap |
| Quote close is zero or bad upstream row | Division error or invalid chart | Validate quote close > 0 and raise `ValueError` |
| Render validation rejects ratio candles | No chart output | Ensure output candles satisfy `high >= open/close`, `low <= open/close`, positive prices |
| Cache mutation leaks between calls | Flaky consumers/tests | Return copied dict/list structures from cache |
| Live Binance unavailable | Smoke validation blocked | Keep deterministic fake-client tests; document live failure in report |

## Notes

- The user specified the simplest high/low interpretation as max/min of `close_ratio` within the bar. With only OHLCV candles and no intra-bar sub-bars, the implementable MVP should use current and previous close ratios to produce valid candle bodies. If the implementation chooses `open == high == low == close == close_ratio`, document that as the strictest interpretation of "close_ratio within the bar".
- `volume` must be the numerator/base candle volume.
- Prefer reusing `chart_renderer.render_chart_image()` rather than exposing a second chart style surface.
