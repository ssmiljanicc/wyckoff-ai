# Feature: Chart Renderer MCP Server

## Summary

Implement issue #10: a Python MCP server that converts OHLCV candles into Vision-readable PNG candlestick charts with volume. The server exposes:

- `render_chart(ohlcv_data, title, annotations)` -> PNG file path by default, optional base64 if explicitly requested in the implementation.
- `render_chart_for_symbol(symbol, timeframe, limit)` -> fetches OHLCV through the market data MCP/client from issue #9 / PR #33 and renders the same chart.

This plan is for implementation only. Do not implement spread charts, skill integration, paper trading, signal generation, or ML classification here.

## User Story

As a Wyckoff crypto analyst,
I want the agent to render clean OHLCV candlestick + volume charts from live or supplied data,
So that Vision can identify range structure, volume events, springs, tests, and phase context without manual chart prep.

## Problem Statement

The repo currently has the methodology skill and corpus, but no chart renderer in main. The PRD states that live analysis needs three inputs: structured OHLCV numbers, rendered chart images, and wiki methodology context. Without the renderer, the agent can fetch or receive OHLCV but cannot perform the visual bar-by-bar reading Wyckoff depends on.

Issue #10 requires a renderer that outputs at least 1200x600 PNGs with candlesticks, volume below price, clean background, minimal UI chrome, and optional annotation overlays. It depends on issue #9, whose PR #33 is open but not merged into main as of 2026-05-25.

## Solution Statement

Add a new `scripts/mcp/chart_renderer.py` module with:

- Pure rendering functions that validate OHLCV dictionaries, convert them into an `mplfinance`-compatible `pandas.DataFrame`, apply a `wyckoff_style` preset, render a 1200x600+ PNG, and return structured metadata.
- Optional annotation support for horizontal key levels and phase labels.
- A FastMCP server exposing `render_chart` and `render_chart_for_symbol`.
- A small per-process LRU cache keyed by input hash, render options, and annotation payload to avoid repeated identical PNG renders.
- Tests using deterministic mock OHLCV, no live network by default.

If PR #33 is merged before implementation, import `scripts.mcp.market_data_client.BinanceMarketDataClient`, `Candle`, and `DEFAULT_LIMIT`. If it is not merged, keep `render_chart` fully testable with local mock OHLCV and gate `render_chart_for_symbol` behind an import fallback that raises an actionable dependency error instead of failing import-time.

## Metadata

| Field | Value |
| --- | --- |
| Feature type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Primary issue | https://github.com/ssmiljanicc/wyckoff-ai/issues/10 |
| Parent PRD | `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md` |
| Depends on | issue #9 / PR #33: `get_ohlcv(symbol, timeframe, limit)` |
| Target plan path | `PRPs/plans/10-chart-renderer-mcp.plan.md` |
| Worktree while planning | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/chart-renderer-mcp` |
| Branch while planning | `kild/chart-renderer-mcp` |

## UX Design

Current operator/API flow:

```text
User asks "Analyze BTC 1d"
  -> agent may have methodology skill
  -> no local chart image tool in main
  -> user must supply chart image or textual chart description
```

Future operator/API flow:

```text
User asks "Analyze BTC 1d"
  -> render_chart_for_symbol("BTC", "1d", 200)
  -> market data client get_ohlcv("BTC", "1d", 200)
  -> mplfinance renders clean PNG with price + volume
  -> Vision reads image
  -> skill composes Wyckoff scenario using image + OHLCV + wiki
```

Data flow:

```text
Supplied OHLCV list ---------------+
                                   |
                                   v
                             chart_renderer
                                   |
Symbol/timeframe/limit -> #9 get_ohlcv()
                                   |
                                   v
                           validated DataFrame
                                   |
                                   v
                         mplfinance + annotations
                                   |
                                   v
                       PNG path + metadata for Vision
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| `scripts/mcp/` | No MCP renderer in main | `chart_renderer.py` exposes chart tools | Agent can create chart images on demand |
| MCP tool layer | #9 only exists in open PR #33 | `render_chart_for_symbol` composes with #9 when available | Common "symbol timeframe" request becomes one tool call |
| Vision workflow | User provides external chart | Server emits local PNG with known dimensions/style | Repeatable visual analysis |

## Mandatory Reading

- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:75-90` for required capabilities and explicit scope boundaries.
- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:120-138` for `mplfinance`, 1200x600 minimum, and technical risks.
- `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:159-162` for phase 2 success signal.
- `pyproject.toml:12-15` in main for existing `[mcp]` optional extra containing `mplfinance>=0.12` and `matplotlib>=3.9`.
- PR #33 `scripts/mcp/market_data_client.py:32-42` for the planned `Candle` shape.
- PR #33 `scripts/mcp/market_data_client.py:136-161` for `BinanceMarketDataClient.get_ohlcv(symbol, timeframe, limit)`.
- PR #33 `scripts/mcp/market_data_server.py:16-23` for FastMCP module-level server/client/tool registration style.
- PR #33 `tests/test_market_data_server.py:37-44` for monkeypatching module-level clients in server wrapper tests.
- mplfinance README: https://github.com/matplotlib/mplfinance/blob/master/README.md
- MCP Python SDK README: https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md
- Matplotlib `savefig` docs: https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| TYPES | PR #33 `scripts/mcp/market_data_client.py:32-42` | OHLCV candles are `TypedDict` rows with millisecond times and numeric OHLCV fields. | `class Candle(TypedDict): open_time: int ... volume: float ... trades: int` |
| FLOW | PR #33 `scripts/mcp/market_data_client.py:136-161` | Normalize inputs, validate limit, cache results, fetch or compute, return copies. | `cache_key = _CacheKey(...); if cache_key in self._ohlcv_cache: ... return list(...)` |
| MCP | PR #33 `scripts/mcp/market_data_server.py:16-23` | Module-level `FastMCP`, module-level shared client, thin decorated wrappers. | `mcp = FastMCP("wyckoff-market-data")` and `@mcp.tool()` |
| TESTS | PR #33 `tests/test_market_data_server.py:37-44` | Wrapper tests monkeypatch module-level client and assert call forwarding. | `monkeypatch.setattr(market_data_server, "client", fake)` |
| DEPENDENCIES | `pyproject.toml:12-15` | Existing `[mcp]` extra already names render dependencies. | `mcp = ["mplfinance>=0.12", "matplotlib>=3.9"]` |
| SCRIPT STYLE | `scripts/scrape_crypto_archive.py:9-23` | Scripts use `from __future__ import annotations`, stdlib imports first, typed helpers, explicit paths. | `from dataclasses import dataclass` and `from pathlib import Path` |
| ARCHITECTURE | `docs/edukacija/02-koncepti-arhitekture.md:80-83` | Phase 2 combines `get_ohlcv()` numbers with `render_chart()` images and wiki citations. | ``- `get_ohlcv()` -> brojevi`` and ``- `render_chart()` -> slika za Vision`` |

## Files to Change

- `pyproject.toml`
  - Add `pandas>=2.2` to `[project.optional-dependencies].mcp` unless PR #33 or another merged change already adds it. `mplfinance` consumes Pandas DataFrames; make this dependency explicit.
  - If PR #33 is merged, preserve its `httpx>=0.28` and `mcp[cli]>=1.0` project dependencies.

- `scripts/__init__.py`
  - Add only if PR #33 has not landed and tests need `scripts` as a package.

- `scripts/mcp/__init__.py`
  - Add only if PR #33 has not landed and tests need `scripts.mcp` as a package.

- `scripts/mcp/chart_renderer.py`
  - New module containing data validation, DataFrame conversion, `wyckoff_style`, annotation rendering, LRU cache, FastMCP tools, and `main()`.

- `tests/conftest.py`
  - Add only if PR #33 has not landed and tests need repo root on `sys.path`.

- `tests/test_chart_renderer.py`
  - New unit tests for DataFrame conversion, validation errors, chart file creation, image dimensions, annotations, cache behavior, and dependency fallback.

- `uv.lock`
  - Refresh if dependencies change.

Do not update `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md` in this issue unless the implementation task explicitly asks to move phase status. This planning request only asks to commit and push the plan file.

## NOT Building

- No spread chart server. That is issue #11.
- No live exchange client implementation. That is issue #9 / PR #33.
- No skill prompt/SKILL.md integration. That is phase 4.
- No Vision API caller inside the MCP server. Acceptance can be validated manually by showing the PNG to Vision.
- No browser UI, dashboard, or web frontend.
- No authenticated trading, portfolio, alerts, streaming, scanner, or ML classification.
- No heavy annotation grammar in v1. Accept a small dict schema for horizontal levels and phase labels.

## Step-by-Step Tasks

1. Prepare dependency and package baseline.
   - File: `pyproject.toml`, possibly `scripts/__init__.py`, `scripts/mcp/__init__.py`, `tests/conftest.py`.
   - Instruction: ensure `uv run --extra mcp` can import `mplfinance`, `matplotlib`, `pandas`, and `mcp.server.fastmcp.FastMCP`.
   - Pattern to mirror: PR #33 `pyproject.toml:10-17` if merged; otherwise main `pyproject.toml:12-15`.
   - Gotcha: do not remove existing scraping dependencies.
   - Validation command: `uv run --extra mcp python -c "import mplfinance, matplotlib, pandas; from mcp.server.fastmcp import FastMCP"`.

2. Define input and output types.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: define `ChartCandle`, `HorizontalLineAnnotation`, `PhaseLabelAnnotation`, `ChartAnnotations`, and `RenderedChart` with `TypedDict` or dataclasses. Accept PR #33 `Candle` shape as input: `open_time`, `open`, `high`, `low`, `close`, `volume`, plus optional metadata fields.
   - Pattern to mirror: PR #33 `Candle` `TypedDict`.
   - Gotcha: keep tool return JSON-serializable; return strings/numbers/lists/dicts, not `Path` objects.
   - Validation command: `uv run python -m compileall scripts`.

3. Add OHLCV validation.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: implement `validate_ohlcv_data(ohlcv_data)` to reject empty input, missing fields, non-numeric OHLCV, non-positive prices, `high < max(open, close)`, `low > min(open, close)`, negative volume, and duplicate/non-monotonic `open_time`.
   - Pattern to mirror: PR #33 `normalize_symbol`, `normalize_timeframe`, `_normalize_limit`, and `parse_kline` explicit `ValueError`/upstream error style.
   - Gotcha: allow zero volume for sparse candles, but reject negative volume.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k validation`.

4. Convert candles into an `mplfinance` DataFrame.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: implement `ohlcv_to_dataframe(ohlcv_data)` with a UTC `DatetimeIndex` derived from `open_time` milliseconds and columns exactly `Open`, `High`, `Low`, `Close`, `Volume`.
   - Pattern to mirror: mplfinance README requires a Pandas DataFrame containing OHLC data with a Pandas `DatetimeIndex`.
   - Imports/types: `import pandas as pd`.
   - Gotcha: sort by `open_time` only if validation can preserve deterministic ordering; prefer rejecting unsorted input so annotations align with visible sequence.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k dataframe`.

5. Implement `wyckoff_style`.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: create a `make_wyckoff_style()` helper using `mpf.make_marketcolors()` and `mpf.make_mpf_style()` with white/light facecolor, subdued grid, readable green/red candles, black/gray axis text, `y_on_right=False`, and no dark theme.
   - Pattern to mirror: PRD chart requirements at `.claude/PRPs/prds/faza-2-live-market-analysis.prd.md:127-128`.
   - Imports/types: `import mplfinance as mpf`.
   - Gotcha: avoid excessive grid and decorative styling because Vision should read bars, not chrome.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k style`.

6. Implement pure render function.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: implement `render_chart_image(ohlcv_data, title="", annotations=None, output_dir=None, width=1200, height=600)` that renders `type="candle"`, `volume=True`, `style=make_wyckoff_style()`, and writes a PNG into a temp/cache directory.
   - Pattern to mirror: PR #33 client methods are pure enough to unit test without running MCP transport.
   - Imports/types: `tempfile`, `hashlib`, `json`, `Path`, `matplotlib.pyplot as plt`.
   - Gotcha: Matplotlib dimensions are inches times DPI. Use a deterministic DPI such as 100 and `figsize=(12, 6)` for 1200x600. Close figures with `plt.close(fig)` after saving.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k render_creates_png`.

7. Add PNG dimension verification.
   - File: `tests/test_chart_renderer.py`.
   - Instruction: read the produced PNG dimensions with a lightweight method. Prefer Pillow only if it is already transitive/available; otherwise parse the PNG IHDR header in test helper to avoid a new dependency.
   - Pattern to mirror: deterministic unit tests in PR #33 avoid live network.
   - Gotcha: `bbox_inches="tight"` can shrink images below 1200x600. If using tight bounding boxes, assert final dimensions and tune `pad_inches`/savefig options.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k dimensions`.

8. Implement annotation overlay v1.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: support `annotations={"horizontal_lines":[{"price":..., "label":..., "color":...}], "phase_labels":[{"index":..., "label":...}]}`. Horizontal lines should draw across price axis; phase labels should appear on price panel near the top without obscuring candles.
   - Pattern to mirror: use `returnfig=True` from mplfinance so the implementation can access axes after plot creation.
   - Gotcha: keep annotation schema optional and forgiving for absent lists, but strict for malformed items when supplied.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k annotations`.

9. Add per-process LRU render cache.
   - File: `scripts/mcp/chart_renderer.py`.
   - Instruction: cache rendered outputs by stable hash of normalized candle data, title, annotations, width, height, style version, and output format. Use a bounded `OrderedDict` similar to PR #33 `OHLCV_CACHE_SIZE` pattern.
   - Pattern to mirror: PR #33 `scripts/mcp/market_data_client.py:68-73` and `:248-252`.
   - Gotcha: if cache returns an existing path, verify the file still exists before returning it; evict stale entries.
   - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k cache`.

10. Implement `render_chart` MCP tool wrapper.
    - File: `scripts/mcp/chart_renderer.py`.
    - Instruction: create `mcp = FastMCP("wyckoff-chart-renderer")`; decorate `render_chart(ohlcv_data, title="", annotations=None)` with `@mcp.tool()`; return `RenderedChart` metadata including `path`, `width`, `height`, `format`, `candle_count`, and `title`.
    - Pattern to mirror: PR #33 `scripts/mcp/market_data_server.py:16-23`.
    - Gotcha: do not return binary bytes by default. File path is the PRD decision and keeps tool payload small.
    - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k wrapper`.

11. Implement `render_chart_for_symbol` with dependency fallback.
    - File: `scripts/mcp/chart_renderer.py`.
    - Instruction: when PR #33 is available, instantiate or import a shared `BinanceMarketDataClient` and call `client.get_ohlcv(symbol, timeframe, limit)`, then pass data to `render_chart`. If import fails because #33 is not merged, raise `RuntimeError("render_chart_for_symbol requires issue #9 market data client; use render_chart with supplied OHLCV for local testing")`.
    - Pattern to mirror: PR #33 module-level shared client.
    - Gotcha: tests on main before PR #33 merge must still pass for `render_chart` and should assert the fallback error for `render_chart_for_symbol`.
    - Validation command: `uv run pytest -q tests/test_chart_renderer.py -k symbol`.

12. Add MCP server entry point.
    - File: `scripts/mcp/chart_renderer.py`.
    - Instruction: add `main() -> None: mcp.run()` and `if __name__ == "__main__": main()`.
    - Pattern to mirror: PR #33 `scripts/mcp/market_data_server.py:38-43`; MCP Python SDK direct execution docs.
    - Gotcha: keep import-time side effects minimal except for module-level clients/cache.
    - Validation command: `uv run --extra mcp python -m scripts.mcp.chart_renderer --help` if FastMCP supports it, otherwise `timeout 2 uv run --extra mcp python -m scripts.mcp.chart_renderer` and confirm no import error before timeout.

13. Add tests.
    - File: `tests/test_chart_renderer.py`.
    - Instruction: cover validation, DataFrame conversion, successful PNG render, minimum dimensions, annotation overlays not crashing, cache hit, FastMCP wrapper forwarding, and `render_chart_for_symbol` with fake client.
    - Pattern to mirror: PR #33 tests use fake clients and monkeypatch.
    - Gotcha: tests must not require Binance or live network.
    - Validation command: `uv run pytest -q`.

14. Add a local smoke command for implementers.
    - File: no new file required unless adding `scripts/mcp/sample_ohlcv.json` is preferred.
    - Instruction: document in implementation notes or tests how to call `render_chart` with generated mock OHLCV and verify the PNG manually.
    - Pattern to mirror: PR #33 PR body live smoke, but keep this issue's automated smoke offline.
    - Gotcha: acceptance includes Vision coherence, so leave a deterministic sample image path in test output or a documented one-liner for manual validation.
    - Validation command: `uv run --extra mcp python - <<'PY'\nfrom scripts.mcp.chart_renderer import render_chart\nprint(render_chart([{'open_time': i*86400000, 'open': 100+i, 'high': 103+i, 'low': 98+i, 'close': 101+i, 'volume': 1000+i} for i in range(60)], 'Mock BTC 1d', None)['path'])\nPY`

## Testing Strategy

- Unit tests: validate pure helpers without MCP transport or network.
- Render tests: generate synthetic 50-200 candle OHLCV arrays and assert PNG exists, is PNG format, has minimum dimensions, and contains non-trivial bytes.
- Annotation tests: render with at least two horizontal lines and two phase labels; assert no exception and output dimensions remain valid.
- Cache tests: call render twice with identical inputs and assert second call returns the same path or same cache metadata without rewriting unexpectedly.
- Symbol wrapper tests:
  - If PR #33 code is present, monkeypatch `chart_renderer.market_data_client` or equivalent fake client and assert forwarded args.
  - If PR #33 code is absent, assert actionable fallback error.
- Integration smoke: once PR #33 is merged, render `BTC 1d 200` through `render_chart_for_symbol`.
- Manual acceptance: show the generated PNG to Vision and ask for a Wyckoff structure/event description; expected output should mention coherent candle/volume structure, not complain about unreadable chart.

## Validation Commands

Run these before marking implementation complete:

```bash
uv lock --check
uv run --extra mcp python -m compileall scripts tests
uv run --extra mcp pytest -q
uv run --extra mcp python -c "from scripts.mcp.chart_renderer import render_chart; print(render_chart([{'open_time': i*86400000, 'open': 100+i, 'high': 103+i, 'low': 98+i, 'close': 101+i, 'volume': 1000+i} for i in range(80)], 'Mock BTC 1d', None))"
```

After PR #33 is merged:

```bash
uv run --extra mcp python -c "from scripts.mcp.chart_renderer import render_chart_for_symbol; print(render_chart_for_symbol('BTC', '1d', 200))"
```

Manual Vision check:

```text
Prompt Vision with the generated PNG:
"Describe the Wyckoff-relevant structure in this chart. Identify any visible range, trend, volume events, tests, springs/upthrusts, or phase-like areas. Be explicit about uncertainty."
```

## Acceptance Criteria

- `render_chart(ohlcv_data, title, annotations)` returns a JSON-serializable result with a local PNG path.
- `render_chart_for_symbol(symbol, timeframe, limit)` fetches through issue #9 API when available and renders the same PNG format.
- PNG output is at least 1200x600 pixels.
- Chart uses candlesticks, not a line chart.
- Volume bars are below price and share the time axis.
- Background is clean/light with minimal grid and no excessive UI chrome.
- `wyckoff_style` preset exists and is used by default.
- Annotation dict supports horizontal key levels and phase labels in first-pass form.
- Identical render requests can be served from bounded per-process LRU cache.
- Automated tests pass without live network access.
- A sample rendered chart shown to Vision yields a coherent description with identifiable structure/events.

## Completion Checklist

- [ ] `scripts/mcp/chart_renderer.py` exists and imports cleanly.
- [ ] `render_chart` works with local mock OHLCV even if PR #33 is not merged.
- [ ] `render_chart_for_symbol` works with PR #33 code or raises an actionable dependency error when absent.
- [ ] Tests cover validation, rendering, dimensions, annotations, cache, and wrappers.
- [ ] `uv.lock` is refreshed if dependencies changed.
- [ ] Validation commands pass.
- [ ] Manual Vision check result is captured in implementation report or PR body.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| PR #33 not merged before implementation | `render_chart_for_symbol` cannot import market data client | Keep `render_chart` independent; test `render_chart_for_symbol` with local fake or actionable fallback |
| `bbox_inches="tight"` shrinks PNG below 1200x600 | Fails Vision readability requirement | Assert image dimensions in tests; avoid tight crop if it changes final pixels |
| Candles too compressed for 200 bars | Vision misses events | Default to 1200x600 minimum, reasonable candle width, and support limit control |
| Annotation labels obscure bars | Vision receives noisy chart | Place phase labels near top margin/axis, use small font and semi-transparent background |
| Matplotlib leaks figures in repeated tool calls | Server memory growth | Always close figures after save |
| Cache grows unbounded | Long-lived MCP process memory/disk growth | Use bounded `OrderedDict` LRU and verify file existence |
| MCP binary payload too large | Agent/tool latency and context bloat | Return file path by default; base64 only as later optional flag |

## Notes

External research:

- `mplfinance` official README states the new API works with Pandas DataFrames containing Open/High/Low/Close and a Pandas `DatetimeIndex`, supports `type='candle'`, and supports `volume=True`.
- MCP Python SDK README shows the FastMCP pattern with `from mcp.server.fastmcp import FastMCP`, `@mcp.tool()`, and `mcp.run()`.
- Matplotlib `savefig` docs confirm PNG saving options and show `dpi`, `bbox_inches`, `pad_inches`, and `facecolor` controls.

Confidence: 8/10. The dependency on PR #33 is the main uncertainty, but the renderer can be developed and tested independently with mock OHLCV until #33 lands.

Next recommended command after this plan is approved:

```bash
$prp-implement PRPs/plans/10-chart-renderer-mcp.plan.md
```
