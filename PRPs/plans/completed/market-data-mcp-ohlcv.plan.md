# Feature: Market Data MCP OHLCV

## Summary

Implement GitHub issue #9: a Python MCP server that exposes Binance public OHLCV data for Wyckoff analysis through `get_ohlcv(symbol, timeframe, limit)`, `get_supported_symbols()`, and `get_timeframes()`.

The feature is Phase 1 of `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md`: "Market data MCP". It is the shared data foundation for the later chart renderer and spread chart servers, so the implementation should create a reusable market data client instead of burying Binance calls inside one tool module.

## User Story

As a Wyckoff practitioner using the agent,
I want to provide only a symbol and timeframe,
So that the agent can pull current OHLCV data without manual chart export or pasted candles.

## Problem Statement

The current skill is methodologically rich but passive with respect to market data. PRD evidence says users must manually describe charts or provide OHLCV, and the agent cannot autonomously pull market data or render charts. Issue #9 is the first step: make reliable candle data available through MCP.

## Solution Statement

Add a small MCP package under `scripts/mcp/` with:

- `market_data_server.py`: FastMCP server registering the three public tools.
- `market_data_client.py`: shared Binance HTTP client, symbol/timeframe normalization, LRU caching, and rate limiting.
- `tests/`: focused tests for normalization, timeframes, response mapping, cache behavior, error surfacing, and MCP tool wrappers.

Use Binance public market data only. Do not add authentication, trading endpoints, WebSockets, multi-exchange fallback, chart rendering, or spread chart computation in this phase.

## Metadata

| Field | Value |
|---|---|
| Type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Source PRD | `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md` |
| Selected PRD phase | Phase 1, Market data MCP |
| GitHub issue | https://github.com/ssmiljanicc/wyckoff-ai/issues/9 |
| Related design note | https://github.com/ssmiljanicc/wyckoff-ai/issues/12 |
| Worktree | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/market-data-mcp` |
| Branch | `kild/market-data-mcp` |
| Canonical plan path | `PRPs/plans/market-data-mcp-ohlcv.plan.md` |

## UX Design

Current operator flow:

```text
User: "Analyze BTC 1d"
  -> agent asks for / depends on pasted chart or OHLCV
  -> user manually prepares data
  -> skill applies Wyckoff methodology
```

Future operator/API flow after this phase:

```text
User: "Analyze BTC 1d"
  -> agent calls get_ohlcv("BTC", "1d", 200)
  -> MCP normalizes BTC -> BTCUSDT
  -> MCP pulls Binance /api/v3/klines or returns session cache
  -> agent receives structured OHLCV JSON
  -> later phases render/analyze chart images
```

Data flow:

```text
MCP client
  -> market_data_server.py tool
  -> market_data_client.py normalize/cache/rate-limit/fetch
  -> Binance public market data endpoint
  -> normalized candle records
  -> structured MCP result
```

| Location | Before | After | User Impact |
|---|---|---|---|
| `skills/wyckoff-trader-skill/SKILL.md` | Workflow starts from raw chart observations | No change in this issue | Skill integration waits for phases #10/#11 |
| MCP layer | No market data server exists | `get_ohlcv`, `get_supported_symbols`, `get_timeframes` available | Agent can fetch candles without user prep |
| Future chart renderer | No shared data source | Can import shared client from `scripts/mcp/market_data_client.py` | Avoids duplicate API/session logic |

## Mandatory Reading

- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:37-45` for success metrics: top 50 symbols, 1h/4h/1d/1w, and `<3s` latency target.
- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:77-90` for required and explicitly out-of-scope capabilities.
- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:120-138` for architecture notes and risks.
- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:142-157` for Phase 1 definition and success signal.
- GitHub issue #9 body for minimum interface, Binance-first data source, chart-renderer-compatible output, and in-session caching.
- GitHub issue #12 body for sequencing and shared data client design note.
- Binance Spot API docs:
  - https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
  - https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- MCP Python SDK docs:
  - https://modelcontextprotocol.io/docs/sdk
  - https://github.com/modelcontextprotocol/python-sdk

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
|---|---|---|---|
| DEPENDENCIES | `pyproject.toml:1-18` | Project is a non-package `uv` Python repo with dependencies in `pyproject.toml` and optional extras. | `dependencies = [...]`; `[project.optional-dependencies]`; `[tool.uv] package = false` |
| HTTP | `scripts/scrape_crypto_archive.py:96-101` | HTTP helpers fail fast on rate/protection errors and call `raise_for_status()`. | `if response.status_code in {403, 429}: raise RuntimeError(...)` |
| HTTP | `scripts/download_fraser_images.py:228-263` | Existing scripts create a session, set `User-Agent`, sleep between remote requests, and stop on 403/429. | `session = requests.Session()`; `time.sleep(delay)` |
| CLI | `scripts/scrape_crypto_archive.py:372-420` | Existing Python scripts have `main()`, argparse, printed progress, and integer exit codes. | `def main() -> int:`; `parser = argparse.ArgumentParser()` |
| ARCHITECTURE | `docs/edukacija/02-koncepti-arhitekture.md:339-351` | MCP adds capabilities through external tool processes; `get_ohlcv` is the canonical example. | ``get_ohlcv(symbol, timeframe)`` |
| ARCHITECTURE | `docs/edukacija/02-koncepti-arhitekture.md:365-393` | Design expects multiple MCP servers with a market data server separate from chart/spread servers. | `market_data_server.py -> OHLCV` |
| ARCHITECTURE | `docs/edukacija/02-koncepti-arhitekture.md:420-485` | MCP server exposes tools over JSON-RPC, with Python pseudocode for `get_ohlcv`. | `@server.tool()` and `server.run()` |
| SCOPE | `CLAUDE.md:271-280` | Live market data belongs in MCP servers, not the wiki. | `Live market data — that lives in MCP servers` |
| SKILL | `skills/wyckoff-trader-skill/SKILL.md:35-42` | Skill currently prefers local corpus and is not responsible for live data. | `Use the local bundled assets before browsing...` |
| SKILL | `skills/wyckoff-trader-skill/SKILL.md:57-63` | Crypto workflow expects spread/relative charts but assumes they already exist. | `Use spread charts for leadership detection...` |
| PROMPT | `skills/wyckoff-trader-skill/agents/openai.yaml:1-7` | Existing agent prompt assumes "this market" is already available. | `default_prompt: "...scenario for this market."` |

## External Research

- [Binance Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
  - KEY_INSIGHT: Public market data endpoints such as `/api/v3/exchangeInfo`, `/api/v3/klines`, `/api/v3/ticker/24hr`, and `/api/v3/time` are available without authentication via `https://data-api.binance.vision`.
  - APPLIES_TO: `scripts/mcp/market_data_client.py`.
  - GOTCHA: Do not introduce API keys or signed endpoints for this issue.
- [Binance Spot REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
  - KEY_INSIGHT: Responses are JSON, timestamps are milliseconds by default, data is chronological unless noted, and calls without `startTime`/`endTime` return recent items up to `limit`.
  - APPLIES_TO: Candle parsing and `get_ohlcv` response order.
  - GOTCHA: HTTP 429 means rate limit exceeded; repeated violations can escalate to 418. Surface 429 to the caller and do not fallback.
- [MCP SDKs](https://modelcontextprotocol.io/docs/sdk)
  - KEY_INSIGHT: Python is a Tier 1 official SDK and supports servers exposing tools, resources, prompts, local/remote transports, and type safety.
  - APPLIES_TO: Dependency choice: add `mcp[cli]`.
  - GOTCHA: Use official SDK, not third-party FastMCP packages.
- [MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk)
  - KEY_INSIGHT: Current stable README documents SDK v1.x; `FastMCP` registers tools with `@mcp.tool()` and supports structured output from Pydantic models, TypedDicts, dataclasses, dicts, lists, and primitives.
  - APPLIES_TO: `scripts/mcp/market_data_server.py` tool definitions and return types.
  - GOTCHA: Return JSON-serializable structured data; avoid raw `httpx.Response` objects or Decimal instances.

## Files to Change

| File | Change |
|---|---|
| `pyproject.toml` | Add `httpx` and `mcp[cli]` to the MCP optional dependencies or main dependencies, following repo convention. Because the user explicitly asked "Dodaj mcp[cli] + httpx u pyproject.toml", prefer adding them to `[project.optional-dependencies].mcp` alongside `mplfinance` and `matplotlib`. |
| `uv.lock` | Update through `uv lock` after editing `pyproject.toml`. |
| `scripts/mcp/__init__.py` | New package marker for shared MCP modules. |
| `scripts/mcp/market_data_client.py` | New shared client with Binance base URL, symbol normalization, timeframe validation, per-process LRU cache, 50ms inter-request delay, top-50 symbol discovery, and 429/451 surfacing. |
| `scripts/mcp/market_data_server.py` | New FastMCP server exposing `get_ohlcv`, `get_supported_symbols`, and `get_timeframes`. |
| `tests/test_market_data_client.py` | New unit tests for normalization, timeframe validation, kline parsing, cache key behavior, 429/451 handling, and top-50 filtering/sorting. |
| `tests/test_market_data_server.py` | New lightweight tests for tool wrappers and structured return shape. |
| Optional `README` or docs | Only add if the repo already has MCP server docs by implementation time. Current repo has no MCP docs; avoid extra docs unless needed for validation. |

## NOT Building

- No chart rendering or `mplfinance` work. That is issue #10.
- No spread chart computation. That is issue #11.
- No SKILL.md or `agents/openai.yaml` runtime integration. PRD phase 4 depends on issues #9, #10, and #11.
- No authenticated Binance API calls.
- No trading/order endpoints.
- No WebSockets or streaming.
- No multi-exchange fallback. Specifically, 429 and 451 must be surfaced as errors.
- No persistent/on-disk cache.
- No scanner beyond `get_supported_symbols()` returning top 50 by volume.

## Strategic Design

### APPROACH_CHOSEN

Create a shared `BinanceMarketDataClient` module and a thin FastMCP wrapper. The client owns HTTP, normalization, caching, rate limiting, and Binance response mapping. The MCP server owns tool registration and tool-friendly validation boundaries.

### RATIONALE

Issue #12 says all three MCP servers should share a common data client so requests are not duplicated in the same session. PRD lines 124-126 also call out a shared client recommendation. Keeping the Binance logic out of the server allows chart and spread servers to import the same client later.

### ALTERNATIVES_REJECTED

- Put all logic in `market_data_server.py`: fastest for issue #9, but forces duplication when #10/#11 need candles.
- Use `requests`: existing scripts use it, but user explicitly requested `httpx` and async support fits MCP tool implementations.
- Use a disk cache: more durable, but out of scope and risks stale market data semantics.
- Use fallback sources on errors: PRD mentions fallback as a possible future capability, but user explicitly says 429/451 should surface errors and not fallback.

### FAILURE MODES

- Invalid symbol: normalize first, then return a clear tool error if Binance returns invalid symbol or symbol is not present in `exchangeInfo`.
- Unsupported timeframe: reject before HTTP call; supported minimum set is `1h`, `4h`, `1d`, `1w`.
- Binance 429/451: raise a domain-specific exception and surface it through MCP without fallback.
- Binance 5xx/network timeout: raise a clear transient upstream error; do not return partial candles.
- Empty kline result: return an error for invalid/unavailable data rather than an empty "successful" analysis input.

### PERFORMANCE

- Use a module-level client or lifespan client so HTTP connection pooling and cache persist for the process.
- Cache `get_ohlcv(symbol, timeframe, limit)` results by normalized symbol/timeframe/limit for the process.
- Cache `get_supported_symbols()` because it likely calls `/api/v3/ticker/24hr` and/or `/api/v3/exchangeInfo`.
- Enforce roughly 50ms between actual upstream requests; cache hits should not sleep.
- Validate single `get_ohlcv("BTC", "1d", 200)` call completes under 3 seconds.

### SECURITY

- No credentials, no environment variables, no signed endpoints.
- No shell execution from MCP tool inputs.
- Normalize symbols through a conservative regex and whitelist quote assets (`USDT`, maybe `USDC` only if implementation chooses to include them in supported symbols).

### MAINTAINABILITY

- Use typed data structures (`TypedDict`, dataclass, or Pydantic model) for candle output.
- Keep Binance raw-array parsing in one function with tests because Binance klines are positional arrays.
- Keep supported timeframe mapping explicit: `{"1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"}`.

## Step-by-Step Tasks

1. **Add MCP dependencies**
   - File: `pyproject.toml`
   - Action: Add `mcp[cli]` and `httpx` to `[project.optional-dependencies].mcp`, preserving existing `mplfinance` and `matplotlib`.
   - Pattern to mirror: `pyproject.toml:12-18`.
   - Gotcha: Do not remove current dependencies; phase #10 still needs chart packages.
   - Validation: `uv lock --check` should fail before lock update if dependencies changed; after lock update, run `uv lock --check`.

2. **Refresh lockfile**
   - File: `uv.lock`
   - Action: Run `uv lock` after editing `pyproject.toml`.
   - Pattern to mirror: existing `uv.lock` includes resolved extras under package metadata.
   - Gotcha: Use `uv`, not pip.
   - Validation: `uv lock --check`.

3. **Create MCP package directory**
   - File: `scripts/mcp/__init__.py`
   - Action: Add package marker and keep it minimal.
   - Pattern to mirror: existing repo places operational Python code under `scripts/`.
   - Gotcha: Do not restructure existing scripts.
   - Validation: `test -f scripts/mcp/__init__.py`.

4. **Define data types and constants**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Add constants for Binance public market data base URL, supported timeframes, default limit, max allowed limit, and user agent. Define candle output fields: `open_time`, `open`, `high`, `low`, `close`, `volume`, `close_time`, `quote_volume`, `trades`.
   - Pattern to mirror: `scripts/scrape_crypto_archive.py:26-42` constants near the top.
   - Imports/types: `from __future__ import annotations`, `time`, `re`, `dataclasses`, `typing`, `httpx`.
   - Gotcha: Output must be JSON serializable; floats are acceptable for agent analysis, strings may preserve precision. Choose one and test it consistently.
   - Validation: `uv run python -m compileall scripts/mcp/market_data_client.py`.

5. **Implement symbol normalization**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Implement `normalize_symbol(symbol: str) -> str` with these examples: `"BTC" -> "BTCUSDT"`, `"BTCUSDT" -> "BTCUSDT"`, `"BTC/USDT" -> "BTCUSDT"`.
   - Pattern to mirror: `scripts/download_fraser_images.py:39-42` small pure normalization helper.
   - Gotcha: Uppercase, strip whitespace, remove `/`, reject empty or unsafe symbols. Do not turn `"ETHBTC"` into `"ETHBTCUSDT"`.
   - Validation: `uv run pytest tests/test_market_data_client.py -q -k normalize`.

6. **Implement timeframe validation**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Implement `get_timeframes()` and internal `normalize_timeframe()` supporting at least `1h`, `4h`, `1d`, `1w`.
   - Pattern to mirror: explicit constants in `scripts/scrape_crypto_archive.py:49-61`.
   - Gotcha: Keep Binance interval strings identical for these supported values.
   - Validation: `uv run pytest tests/test_market_data_client.py -q -k timeframe`.

7. **Implement Binance HTTP request helper**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Use `httpx.AsyncClient` or `httpx.Client` consistently. Add `_request_json(path, params)` that applies rate delay before upstream requests and handles status codes.
   - Pattern to mirror: `scripts/scrape_crypto_archive.py:96-101` and `scripts/download_fraser_images.py:240-249`.
   - Gotcha: 429 and 451 must raise a domain-specific upstream error and must not fallback. Include `Retry-After` in the error message if present.
   - Validation: `uv run pytest tests/test_market_data_client.py -q -k "rate_limit or upstream_error"`.

8. **Implement kline parsing**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Call `/api/v3/klines` with `symbol`, `interval`, and `limit`; map Binance positional arrays into candle dictionaries.
   - Pattern to mirror: `docs/edukacija/02-koncepti-arhitekture.md:438-459` expected tool call/result concept.
   - Gotcha: Binance returns timestamps in milliseconds and recent rows up to `limit`; keep chronological order.
   - Validation: `uv run pytest tests/test_market_data_client.py -q -k kline`.

9. **Implement per-process LRU cache**
   - File: `scripts/mcp/market_data_client.py`
   - Action: Cache `get_ohlcv(normalized_symbol, timeframe, limit)` and `get_supported_symbols()` results within the process.
   - Pattern to mirror: issue #12 shared-session design note; no existing cache implementation exists.
   - Imports/types: `functools.lru_cache` if implementation is synchronous, or a small dict/OrderedDict cache if async.
   - Gotcha: Cache hits should avoid both HTTP calls and 50ms sleep. If using async, do not put coroutine objects inside `lru_cache`.
   - Validation: `uv run pytest tests/test_market_data_client.py -q -k cache`.

10. **Implement supported symbols**
    - File: `scripts/mcp/market_data_client.py`
    - Action: Fetch active symbols and 24h ticker data, filter to spot USDT pairs, sort by quote volume descending, return top 50 normalized symbols.
    - Pattern to mirror: PRD success metric `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:39-42`.
    - Gotcha: Exclude leveraged/down/up tokens if Binance returns them and tests cover the intended filter. Keep the output deterministic.
    - Validation: `uv run pytest tests/test_market_data_client.py -q -k supported_symbols`.

11. **Create FastMCP server wrapper**
    - File: `scripts/mcp/market_data_server.py`
    - Action: Instantiate `FastMCP("wyckoff-market-data")`, register `get_ohlcv`, `get_supported_symbols`, and `get_timeframes` with `@mcp.tool()`, and call `mcp.run()` in `main()`.
    - Pattern to mirror: official MCP Python SDK uses `from mcp.server.fastmcp import FastMCP`, `mcp = FastMCP(name="Tool Example")`, and `@mcp.tool()`.
    - Imports/types: import shared client from `scripts.mcp.market_data_client`.
    - Gotcha: Return structured JSON-compatible data, not raw text blobs.
    - Validation: `uv run python -m compileall scripts/mcp/market_data_server.py`.

12. **Add unit tests for tool wrappers**
    - File: `tests/test_market_data_server.py`
    - Action: Test wrapper functions by monkeypatching the shared client, not by hitting Binance.
    - Pattern to mirror: no existing tests; keep tests focused and deterministic.
    - Gotcha: Do not require a running MCP transport for basic wrapper behavior.
    - Validation: `uv run pytest tests/test_market_data_server.py -q`.

13. **Add live smoke validation command**
    - File: no source change required unless adding docs.
    - Action: Validate one real public call manually after unit tests: `uv run python - <<'PY' ... get_ohlcv("BTC", "1d", 200) ... PY`.
    - Pattern to mirror: PRD Phase 1 success signal `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:154-157`.
    - Gotcha: If Binance returns 451 from the current region, that is a surfaced upstream error and should be reported, not hidden by fallback.
    - Validation: Single call should complete in `<3s` when Binance is reachable.

14. **Run full validation**
    - Files: all changed files.
    - Action: Run formatting/linting if the repo has a configured formatter by implementation time; otherwise run compile and tests.
    - Validation commands:
      - `uv lock --check`
      - `uv run python -m compileall scripts tests`
      - `uv run pytest -q`
      - `uv run python -m scripts.mcp.market_data_server --help` only if the implemented server exposes a CLI help path; otherwise skip and use MCP inspector manually.

## Testing Strategy

- Unit tests should mock `httpx` responses and never depend on Binance for normal CI.
- Include live smoke validation as a manual/operator check because acceptance requires actual Binance public API behavior.
- Test normalization examples from the user prompt exactly:
  - `"BTC" -> "BTCUSDT"`
  - `"BTCUSDT" -> "BTCUSDT"`
  - `"BTC/USDT" -> "BTCUSDT"`
- Test unsupported timeframe rejection.
- Test 429 and 451 status propagation.
- Test top-50 symbols are sorted by quote volume and length is at least 50 when fixture data has enough pairs.
- Test cache avoids duplicate upstream calls for identical `(symbol, timeframe, limit)` in the same process.

## Validation Commands

```bash
uv lock --check
uv run python -m compileall scripts tests
uv run pytest -q
uv run pytest tests/test_market_data_client.py -q
uv run pytest tests/test_market_data_server.py -q
```

Manual live smoke after implementation:

```bash
uv run python - <<'PY'
from scripts.mcp.market_data_client import BinanceMarketDataClient

client = BinanceMarketDataClient()
candles = client.get_ohlcv("BTC", "1d", 200)
print(len(candles), candles[0]["open_time"], candles[-1]["close"])
PY
```

If the implementation is async, adapt the smoke command with `asyncio.run(...)`.

## Acceptance Criteria

- `get_ohlcv(symbol, timeframe, limit)` works for `"BTC"`, `"BTCUSDT"`, and `"BTC/USDT"` by normalizing to `"BTCUSDT"`.
- `get_ohlcv("BTC", "1d", 200)` returns 200 chronological candles when Binance is reachable.
- Each candle contains open, high, low, close, and volume fields suitable for chart rendering.
- `get_supported_symbols()` returns at least 50 top-volume supported symbols.
- `get_timeframes()` returns at least `["1h", "4h", "1d", "1w"]`.
- Repeated identical `get_ohlcv` calls in one process use the cache.
- Real upstream requests have roughly 50ms delay between calls.
- HTTP 429 and 451 are surfaced as errors without fallback.
- No API keys or authenticated endpoints are used.
- A typical single OHLCV call returns in under 3 seconds when Binance is reachable.
- `pyproject.toml` contains `mcp[cli]` and `httpx`, and `uv.lock` is updated.

## Completion Checklist

- [ ] Dependencies added and lockfile refreshed with `uv`.
- [ ] Shared Binance client implemented under `scripts/mcp/`.
- [ ] FastMCP server exposes exactly the three issue #9 tools.
- [ ] Symbol normalization examples pass.
- [ ] Timeframe list includes `1h`, `4h`, `1d`, `1w`.
- [ ] Top-50 symbol discovery returns at least 50 symbols from fixture/live data.
- [ ] Per-process cache verified by tests.
- [ ] 429/451 behavior verified by tests.
- [ ] Unit tests pass.
- [ ] Manual live smoke documented in implementation notes.
- [ ] No chart/spread/skill integration work slipped into this phase.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Binance blocks the operator region with 451 | Surface the error as required; do not fallback. Unit tests should still pass with mocked responses. |
| Async caching is implemented incorrectly | Use a simple explicit dict cache around awaited results, or implement the client synchronously if simpler. |
| `get_supported_symbols()` returns unstable symbols | Filter to `TRADING` spot USDT pairs and sort by numeric `quoteVolume`. |
| Raw Binance kline arrays are mapped incorrectly | Centralize parser and test every positional field used by chart renderer. |
| MCP server returns unstructured text | Use JSON-compatible lists/dicts or typed models so clients can consume the data deterministically. |
| Extra scope creeps into chart/spread work | Keep all rendering and ratio computation out of this issue; later phases import the client. |

## Notes

- The PRD currently mentions "Binance public API (default), CoinGecko fallback" in the decisions log, but the user clarified for this plan that 429/451 must surface errors and not fallback. Treat the user clarification as binding for issue #9.
- The plan intentionally does not update `skills/wyckoff-trader-skill/SKILL.md` or `skills/wyckoff-trader-skill/agents/openai.yaml`; PRD phase 4 handles integration after data, chart, and spread MCP servers stabilize.
- `uv.lock` already contains transitive `httpx` entries from existing resolution, but issue #9 still requires explicit `httpx` in `pyproject.toml`.

