# Feature: Virtual Portfolio MCP Server

## Summary

Implement GitHub issue [#20](https://github.com/ssmiljanicc/wyckoff-ai/issues/20): a Python MCP server that tracks **virtual (paper) trading positions across sessions**. It exposes five tools — `open_position`, `close_position`, `list_positions`, `get_portfolio_state`, `reset_portfolio` — backed by file-based JSON state in `data/portfolios/<name>.json` with **atomic writes** and a **file lock** so state survives MCP restarts and concurrent access without corruption.

This is **Phase 1 of M5** in `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md`. It is the foundation for all later M5 trading-simulation work (signal logger, scanner, backtest runner) — without a persistent portfolio there is nowhere for signals to land. It has **no dependency** on other M5/M6 work; it optionally consumes Faza-2 OHLCV (#9) for mark-to-market equity, but that coupling is kept out of MVP scope.

## User Story

As a Wyckoff practitioner running the agent in research/signal mode,
I want the agent to record, close, and report virtual positions in a named portfolio that persists to disk,
So that I can measure scenario quality with concrete P&L across multiple sessions instead of subjective recall.

## Problem Statement

The skill is currently a single-shot analysis tool: it can analyze a chart but cannot remember that it called a long here and a short there, nor compute what those calls earned. The Faza-3 PRD names "Virtual portfolio P&L tracking" as the first Must-have capability and the literal foundation ("bez portfolio-a, signali i scanning nemaju gde da idu"). The risk explicitly called out is *"Virtual portfolio state corruption across MCP restarts"*, mitigated by *"JSON state with file lock; atomic writes"*. There is no portfolio server today.

## Solution Statement

Add two modules under `scripts/mcp/`, mirroring the existing `market_data_client.py` (logic) + `market_data_server.py` (thin FastMCP wrapper) split:

- **`scripts/mcp/portfolio_store.py`** — all logic: data shapes (`Position`, `PortfolioState`), atomic JSON persistence, `fcntl` file lock, P&L computation, and a `PortfolioStore` class with the five operations. No MCP import, fully unit-testable.
- **`scripts/mcp/portfolio_server.py`** — thin `FastMCP("wyckoff-portfolio")` wrapper exposing the five tools, mirroring `market_data_server.py` and reusing the `chart_renderer.py` FastMCP import-fallback so the module imports cleanly without the `mcp` extra.
- **`scripts/mcp/__init__.py`** — append one registration line (do not touch the existing docstring).
- **`tests/test_portfolio_server.py`** — covers the three success signals from the issue (restart persistence, 5-position P&L vs. manual, interrupted-write does not corrupt).

Keep MVP scope tight: no exchange auth, no order placement, no live price feed inside open/close, no SQLite, no WebSocket.

## Metadata

| Field | Value |
|---|---|
| Type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Source PRD | `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md` |
| Selected PRD phase | Phase 1 (M5), "Virtual portfolio MCP" |
| GitHub issue | https://github.com/ssmiljanicc/wyckoff-ai/issues/20 |
| Milestone | M5: Trading Simulation MCP |
| Worktree | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/trading-portfolio-mcp` |
| Branch | `kild/trading-portfolio-mcp` (base `main`) |
| Canonical plan path | `PRPs/plans/trading-portfolio-mcp.plan.md` |

## UX Design

This is a backend/MCP feature; the "UX" is the agent/operator tool workflow.

Before (today):

```text
User: "Long BTC here on the spring, stop 40k, target 50k"
  -> agent analyzes, states a call in prose
  -> nothing recorded; next session the call is gone
  -> no P&L, no track record
```

After this phase:

```text
User: "Long BTC here on the spring, stop 40k, target 50k"
  -> agent calls open_position("main", "BTC/USDT", "long", 0.1, entry_price=42000, sl=40000, tp=50000)
  -> portfolio_store writes data/portfolios/main.json atomically (under file lock)
  -> later / after MCP restart: list_positions("main", "open") still returns it
  -> on exit: close_position("main", pos_id, exit_price=48000, reason="target hit")
       -> realized_pnl = (48000-42000)*0.1 = 600.0, added to cash
  -> get_portfolio_state("main") -> {cash, realized_pnl, total_equity, open positions}
```

Data flow:

```text
MCP tool call
  -> portfolio_server.py tool wrapper
  -> module-level PortfolioStore (data/portfolios/)
  -> acquire fcntl lock on <name>.json.lock
  -> read current JSON (or seed default) -> mutate -> atomic write (temp + fsync + os.replace)
  -> release lock
  -> structured dict result back to agent
```

| Location | Before | After | User Impact |
|---|---|---|---|
| MCP layer | No portfolio server | `open/close/list/get_state/reset` tools | Agent can track paper trades across sessions |
| `data/portfolios/` | Does not exist | One JSON file per named portfolio | Debuggable, portable, restart-safe state |
| `scripts/mcp/__init__.py` | Docstring only | + one registration line | Server discoverable alongside others |
| `skills/.../SKILL.md` | n/a | No change in this issue | Signal-mode integration is Phase 4 (#?) |

## Mandatory Reading

Read before implementing — these set the patterns to copy exactly:

- `scripts/mcp/market_data_server.py` — the thin FastMCP server shape (`mcp = FastMCP(name)`, `@mcp.tool()` wrappers delegating to a module-level client, `main()`/`mcp.run()`).
- `scripts/mcp/market_data_client.py` — logic-module conventions: `from __future__ import annotations`, `TypedDict` data shapes, typed exceptions subclassing a base `RuntimeError`, `ValueError` for input validation.
- `scripts/mcp/chart_renderer.py:1-49` — the `try/except ImportError` FastMCP fallback and atomic-temp-file usage under `tempfile`; mirror the FastMCP fallback verbatim.
- `tests/test_market_data_server.py` + `tests/conftest.py` — test style: `from scripts.mcp import <module>`, `monkeypatch` of module-level singletons, plain `assert`, no fixtures framework beyond pytest builtins; `conftest.py` puts repo root on `sys.path`.
- This file's CLAUDE.md §0 (Serbian commit/PR body, English titles) and `pyproject.toml` (`pytest` lives in the `[mcp]` optional extra → tests run via `uv run --extra mcp pytest`).

## Patterns to Mirror

| Category | File:Lines | Pattern | Snippet |
|---|---|---|---|
| SERVER | `scripts/mcp/market_data_server.py:16-39` | FastMCP singleton + `@mcp.tool()` + `main()` | `mcp = FastMCP("wyckoff-market-data")` … `def main() -> None: mcp.run()` |
| IMPORT-FALLBACK | `scripts/mcp/chart_renderer.py:17-31` | FastMCP shim when `mcp` extra absent | `try: from mcp.server.fastmcp import FastMCP / except ImportError: class FastMCP: ...` |
| TYPES | `scripts/mcp/market_data_client.py:32-49` | `TypedDict` record shapes | `class Candle(TypedDict): open_time: int ...` |
| ERRORS | `scripts/mcp/market_data_client.py:51-61` | typed exception hierarchy | `class BinanceMarketDataError(RuntimeError): ...` |
| VALIDATION | `scripts/mcp/market_data_client.py:75-94` | `ValueError` on bad input, `.strip().upper()` normalize | `if not raw: raise ValueError("Symbol is required")` |
| ATOMIC-FILE | `scripts/mcp/chart_renderer.py:8,48` + new | temp file in target dir then replace | `tempfile` import; write temp under `RENDER_CACHE_DIR` |
| TESTS | `tests/test_market_data_server.py:37-44` | `monkeypatch.setattr(module, "client", fake)` | `monkeypatch.setattr(market_data_server, "client", fake)` |
| SYSPATH | `tests/conftest.py:7-9` | repo root on `sys.path` | `ROOT = Path(__file__).resolve().parents[1]` |

## Files to Change

| File | Action | Why |
|---|---|---|
| `scripts/mcp/portfolio_store.py` | **Create** | Persistence + lock + P&L + `PortfolioStore` (all logic) |
| `scripts/mcp/portfolio_server.py` | **Create** | Thin FastMCP wrapper, five `@mcp.tool()` functions |
| `scripts/mcp/__init__.py` | **Edit (append one line)** | Register the new server; do not modify the existing docstring |
| `tests/test_portfolio_server.py` | **Create** | The three issue success signals + edge cases |
| `.gitignore` | **Edit** | Ignore runtime `data/portfolios/*.json`, keep dir via `.gitkeep` |
| `data/portfolios/.gitkeep` | **Create** | Ensure storage dir exists in a fresh checkout |

## Design Decisions (decide-and-document, per "procitaj i odluci")

1. **`entry_price` added to `open_position`.** The issue's minimum interface omits an entry price, but P&L is undefined without one, and the "P&L matches manual calc" test must be deterministic and network-free. Decision: `open_position(portfolio, symbol, side, size, entry_price, sl=None, tp=None, note="")` — `entry_price` is **required**. This is a deliberate, documented extension of the listed signature, not a deviation from intent (the issue's own success signal shows price-bearing fields sl/tp). Live mark-to-market entry via Faza-2 OHLCV is explicitly **NOT** built here.
2. **P&L formula.** `long: (exit_price - entry_price) * size`; `short: (entry_price - exit_price) * size`. Fees/slippage = 0 at MVP (PRD decision log: "Simple bar-close fill, no slippage at MVP").
3. **Cash/equity model = realized-only.** `cash = starting_cash + Σ realized_pnl(closed)`. Opening a position does **not** lock cash in MVP (keeps the model deterministic and avoids margin accounting). `total_equity = cash + Σ unrealized_pnl(open)`; unrealized requires mark prices, so `get_portfolio_state` accepts an optional `marks: dict[symbol→price]` — absent ⇒ unrealized = 0 ⇒ `total_equity == cash`. Fully deterministic for tests.
4. **Position id = per-portfolio monotonic integer** stored as `next_id` in the file (`"1"`, `"2"`, …). Friendlier than UUID for the agent to reference; survives restarts.
5. **Module split** (store vs server) mirrors market-data, even though the issue names only `portfolio_server.py` — required by "prati `market_data_server.py` za strukturu" and keeps logic testable without MCP.
6. **Lock mechanism = `fcntl.flock(LOCK_EX)` on a sidecar `<name>.json.lock`.** POSIX/darwin-native, no new dependency. Each operation = lock → read → mutate → atomic write → unlock.

## NOT Building

- Real-money / exchange integration, order placement, auth (hard PRD non-goal).
- Live price feed inside `open_position`/`close_position` (entry/exit are explicit args).
- Mark-to-market via Faza-2 OHLCV inside the server (only an optional `marks` arg; no network).
- Margin/leverage, fees, slippage, partial fills, position averaging/scaling.
- SQLite / database backend (PRD chose file-based JSON).
- Cross-process advisory beyond a single-host `fcntl` lock (no distributed locking).
- Any change to `knowledge/wiki/`, SKILL.md, or other MCP servers.

## Step-by-Step Tasks

### Task 1 — Create `scripts/mcp/portfolio_store.py` data shapes & errors
- **Action:** Create the module with `from __future__ import annotations`; imports `json, os, tempfile, fcntl, time, uuid?`(no — use int ids), `from pathlib import Path`, `from typing import Literal, TypedDict`.
- **Define:** `Side = Literal["long", "short"]`; `PositionStatus = Literal["open", "closed"]`.
  - `class Position(TypedDict)`: `id:str, symbol:str, side:str, size:float, entry_price:float, sl:float|None, tp:float|None, note:str, status:str, opened_at:str, closed_at:str|None, exit_price:float|None, reason:str|None, realized_pnl:float|None`.
  - `class PortfolioState(TypedDict)`: `name:str, starting_cash:float, cash:float, next_id:int, positions:list[Position], created_at:str, updated_at:str`.
- **Errors:** `class PortfolioError(RuntimeError)`; `class PortfolioNotFound(PortfolioError)`; `class PositionNotFound(PortfolioError)`; `class InvalidPositionState(PortfolioError)` (e.g. closing an already-closed position).
- **Constants:** `DEFAULT_STARTING_CASH = 100_000.0`; `PORTFOLIO_DIR_ENV = "WYCKOFF_PORTFOLIO_DIR"`; `DEFAULT_PORTFOLIO_DIR = Path("data/portfolios")`.
- **Pattern:** `market_data_client.py:32-61`.
- **Gotcha:** ISO timestamps via `datetime.now(timezone.utc).isoformat()` — store as strings so JSON round-trips losslessly.
- **Validation:** `uv run --extra mcp python -c "from scripts.mcp import portfolio_store"`

### Task 2 — Implement atomic write + file lock helpers in `portfolio_store.py`
- **Action:** Add private helpers:
  - `_atomic_write_json(path: Path, data: dict) -> None`: create a `NamedTemporaryFile(dir=path.parent, delete=False)` (same filesystem as target → `os.replace` is atomic), `json.dump`, `f.flush()`, `os.fsync(f.fileno())`, close, then `os.replace(tmp, path)`. On any exception, remove the temp file and re-raise (never leave a half temp around; never touch the real file until replace).
  - `_locked(path: Path)` contextmanager: open `<path>.lock` (`os.open(..., O_CREAT|O_RDWR)`), `fcntl.flock(fd, LOCK_EX)`, `yield`, `finally: flock(LOCK_UN); os.close(fd)`.
- **Pattern:** `chart_renderer.py:8,48` for tempfile use; atomic-replace is new but standard.
- **Gotcha:** Use `os.replace` (not `os.rename`) for cross-platform atomic overwrite semantics. fsync before replace guarantees durability so an interrupted write cannot corrupt the existing file — the old inode stays intact until replace swaps it.
- **Validation:** covered by Task 7 atomic-write test.

### Task 3 — Implement `PortfolioStore` class in `portfolio_store.py`
- **Action:** `class PortfolioStore` with `__init__(self, base_dir: Path | None = None)` resolving dir from arg → `WYCKOFF_PORTFOLIO_DIR` env → `DEFAULT_PORTFOLIO_DIR`; `self.base_dir.mkdir(parents=True, exist_ok=True)`.
  - `_path(name) -> Path` (validate `name`: non-empty, no path separators / `..` → `ValueError`).
  - `_load(name) -> PortfolioState` (raise `PortfolioNotFound` if file missing).
  - `_seed(name, starting_cash) -> PortfolioState` (fresh default).
  - Public ops each wrap `with _locked(path):` then read-modify-`_atomic_write_json`:
    - `open_position(portfolio, symbol, side, size, entry_price, sl=None, tp=None, note="")` — auto-seed portfolio if absent (so the agent never has to pre-create); validate `side in {long,short}`, `size>0`, `entry_price>0`; assign `id=str(state["next_id"])`, increment `next_id`; append open position; `updated_at` bumped; return the new `Position`.
    - `close_position(portfolio, position_id, exit_price, reason="")` — find open position (else `PositionNotFound`/`InvalidPositionState`); compute `realized_pnl` (Task 4); set status/closed_at/exit_price/reason/realized_pnl; `cash += realized_pnl`; return closed `Position`.
    - `list_positions(portfolio, status="all")` — `status in {open,closed,all}`; return filtered list (empty list if portfolio absent? No — raise `PortfolioNotFound` for unknown name to surface typos; document).
    - `get_portfolio_state(portfolio, marks=None)` — return `{name, starting_cash, cash, realized_pnl, unrealized_pnl, total_equity, open_positions:[...], closed_count:int}`; unrealized from `marks` per Decision 3.
    - `reset_portfolio(portfolio, starting_cash=DEFAULT_STARTING_CASH)` — overwrite with a fresh seeded state; return it.
- **Pattern:** `BinanceMarketDataClient` class shape (`market_data_client.py:110-168`).
- **Gotcha:** Do all mutation on an in-memory copy then single atomic write — never partial writes mid-operation. Re-`_load` inside the lock (not cached) so a restarted process always sees on-disk truth.
- **Validation:** `uv run --extra mcp python -c "from scripts.mcp.portfolio_store import PortfolioStore"`

### Task 4 — P&L computation function in `portfolio_store.py`
- **Action:** `def compute_pnl(side: str, entry_price: float, exit_price: float, size: float) -> float:` — `long → (exit-entry)*size`, `short → (entry-exit)*size`, else `ValueError`. Pure function (easy to unit-test against manual numbers).
- **Validation:** `uv run --extra mcp python -c "from scripts.mcp.portfolio_store import compute_pnl; assert compute_pnl('long',100,110,2)==20; assert compute_pnl('short',100,90,2)==20"`

### Task 5 — Create `scripts/mcp/portfolio_server.py` (thin FastMCP wrapper)
- **Action:** Mirror `market_data_server.py`. Copy the `chart_renderer.py:17-31` FastMCP import fallback. Create `mcp = FastMCP("wyckoff-portfolio")` and a module-level `store = PortfolioStore()`. Define five `@mcp.tool()` functions delegating to `store`, with full docstrings (the agent reads these):
  - `open_position(portfolio, symbol, side, size, entry_price, sl=None, tp=None, note="")`
  - `close_position(portfolio, position_id, exit_price, reason="")`
  - `list_positions(portfolio, status="all")`
  - `get_portfolio_state(portfolio)`  *(no `marks` arg on the tool surface — keep MVP tool signature simple; `marks` stays an internal/optional store capability)*
  - `reset_portfolio(portfolio, starting_cash=100000.0)`
  - `def main() -> None: mcp.run()` + `if __name__ == "__main__": main()`.
- **Gotcha:** Keep wrappers one-liners delegating to `store` so they stay `monkeypatch`-able exactly like `market_data_server` tests do.
- **Validation:** `uv run --extra mcp python -c "from scripts.mcp import portfolio_server; print(portfolio_server.mcp.name)"`

### Task 6 — Register in `scripts/mcp/__init__.py`
- **Action:** Append exactly one line after the existing docstring (leave the docstring untouched, per the prompt): `from scripts.mcp import portfolio_server as portfolio_server  # noqa: F401  — register portfolio MCP server`.
- **Gotcha:** Eager import is safe because the FastMCP fallback means importing the package never requires the `mcp` extra. Verify other modules' tests still import fine.
- **Validation:** `uv run --extra mcp python -c "import scripts.mcp; import scripts.mcp.portfolio_server"`

### Task 7 — Create `tests/test_portfolio_server.py`
- **Action:** Use `tmp_path` to isolate storage: construct `PortfolioStore(base_dir=tmp_path)` (preferred) or set `WYCKOFF_PORTFOLIO_DIR`. Tests:
  1. **`test_open_position_persists_across_restart`** (issue success signal #1): `store1 = PortfolioStore(tmp_path)`; `open_position("main","BTC/USDT","long",0.1, entry_price=42000, sl=40000, tp=50000)`. Create a **new** `store2 = PortfolioStore(tmp_path)` (simulated restart, same files) → `list_positions("main","open")` returns the BTC long with matching fields. Assert the on-disk JSON file exists.
  2. **`test_pnl_matches_manual_five_positions`** (signal #2): open 5 positions (mix long/short) with known entry/size, close each at a known exit, assert each `realized_pnl` equals a hand-computed constant, and that `get_portfolio_state` `cash == starting_cash + Σ pnl` and `realized_pnl` matches the manual sum. Include at least one losing trade and one short.
  3. **`test_interrupted_write_does_not_corrupt`** (signal #3): seed + open a position so a valid file exists; `monkeypatch` `json.dump` (or the temp-write step) inside `_atomic_write_json` to raise mid-write on the *next* operation; attempt `open_position`, assert it raised; then a fresh `PortfolioStore(tmp_path)` still loads the **previous** valid state (original positions intact, JSON parses) and no stray `*.tmp` file remains in the dir.
  4. `test_close_unknown_position_raises` (`PositionNotFound`).
  5. `test_close_already_closed_raises` (`InvalidPositionState`).
  6. `test_reset_portfolio_clears_positions_and_sets_cash`.
  7. `test_list_positions_status_filter` (open/closed/all).
  8. `test_open_position_validates_side_and_size` (`ValueError`).
  9. `test_compute_pnl_long_and_short` (pure-function table).
- **Pattern:** `tests/test_market_data_server.py` (monkeypatch, plain asserts); `conftest.py` already handles `sys.path`.
- **Gotcha:** Do not write under the repo's real `data/portfolios/` in tests — always `tmp_path`. For the corruption test, assert against the directory listing to prove no temp leak.
- **Validation:** `uv run --extra mcp pytest tests/test_portfolio_server.py -v` → all pass.

### Task 8 — `.gitignore` + storage dir
- **Action:** Add under the "Runtime data" section of `.gitignore`: `data/portfolios/*.json` and `data/portfolios/*.lock` (runtime state is not committed). Create `data/portfolios/.gitkeep` and add a negate rule `!data/portfolios/.gitkeep` so the dir exists on fresh checkout but runtime files stay ignored.
- **Validation:** `git status --short` shows only the `.gitkeep`, not any `*.json`/`*.lock` after running tests.

### Task 9 — Full validation + commit + PR
- **Action:** Run the full test suite to confirm no regressions, then commit (Serbian message, per CLAUDE.md §0.1) and open a PR to `main` (English title, Serbian body, links #20).
- **Validation:** see Validation Commands below.

## Testing Strategy

- **Unit-level on `portfolio_store`** is the core — the MCP wrappers are one-liners, so most behavior is tested through `PortfolioStore` directly (deterministic, no network, no `mcp` runtime needed beyond the import).
- **The three issue success signals are first-class named tests** (restart persistence, manual P&L parity on a 5-position long/short scenario, interrupted-write safety).
- **Isolation via `tmp_path`** so tests never touch real `data/portfolios/`.
- **Determinism:** entry/exit prices are explicit args; no clock-dependent assertions (timestamps only checked for presence/type, not value).

## Validation Commands

```bash
# Module imports (no mcp extra needed thanks to fallback, but pytest needs the extra)
uv run --extra mcp python -c "from scripts.mcp import portfolio_store, portfolio_server"

# P&L pure-function sanity
uv run --extra mcp python -c "from scripts.mcp.portfolio_store import compute_pnl; assert compute_pnl('long',100,110,2)==20.0; assert compute_pnl('short',100,90,2)==20.0; print('pnl ok')"

# Feature tests (the command the issue asks for; note the --extra mcp — pytest lives in the [mcp] optional group)
uv run --extra mcp pytest tests/test_portfolio_server.py -v

# Full suite — no regressions to existing MCP tests
uv run --extra mcp pytest -q

# No runtime portfolio files leaked into git
git status --short
```

> **Note on the issue's command.** The issue/prompt says `uv run pytest …`, but `pytest` is declared only in the `[project.optional-dependencies].mcp` group (`pyproject.toml`), so the reliable invocation is `uv run --extra mcp pytest …`. The completed market-data work uses the same extra. Use `--extra mcp`.

## Acceptance Criteria

- [ ] `open_position` for a BTC long writes `data/portfolios/<name>.json`; a brand-new `PortfolioStore` over the same dir still returns that position (restart-safe).
- [ ] `close_position` computes P&L matching manual calc for both long and short across a 5-position scenario; `cash` reflects the realized sum.
- [ ] An interrupted/failed write leaves the prior valid portfolio intact and parseable, with no stray temp file.
- [ ] `list_positions` honors `status` ∈ {open, closed, all}; `get_portfolio_state` returns cash, realized P&L, total equity, and open positions; `reset_portfolio` produces a fresh state.
- [ ] Five `@mcp.tool()`s registered on `FastMCP("wyckoff-portfolio")`; module imports without the `mcp` extra.
- [ ] `scripts/mcp/__init__.py` gains exactly one registration line; existing docstring unchanged.
- [ ] `uv run --extra mcp pytest tests/test_portfolio_server.py -v` and the full suite pass; no runtime JSON committed.
- [ ] Commit message in Serbian; PR English title + Serbian body linking #20.

## Completion Checklist

- [ ] `portfolio_store.py`, `portfolio_server.py` created; `__init__.py` one-line edit; `.gitignore` + `.gitkeep` done.
- [ ] All Validation Commands pass.
- [ ] `knowledge/wiki/` untouched (`git status` confirms).
- [ ] Commit (Serbian) on `kild/trading-portfolio-mcp`; PR opened to `main` linking #20.
- [ ] (Optional) PRD Phase 1 row marked `in-progress` with plan link.

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Missing `entry_price` makes P&L undefined | High (design) | Added as required arg, documented as deliberate interface extension (Decision 1) |
| `os.rename` not atomic across edge cases | Low | Use `os.replace` + same-dir temp + `fsync` before replace (Task 2) |
| Temp file leak on crash | Low | `try/except` removes temp on failure; corruption test asserts no `*.tmp` remains |
| `fcntl` unavailable on non-POSIX | Low | Target is darwin/Linux; `fcntl` is stdlib there. Document POSIX assumption; revisit if Windows support is ever needed |
| Tests writing to real `data/portfolios/` | Medium | `tmp_path` / `base_dir` injection in every test |
| `pytest` not installed in base env | Medium (known) | Documented `--extra mcp` requirement |
| Scope creep into mark-to-market / signals | Medium | Explicit NOT-Building list; `marks` kept optional and out of tool surface |

## Notes

- Mirrors the established `*_client.py` (logic) + `*_server.py` (FastMCP) split even though the issue names only `portfolio_server.py`; this is required to satisfy "prati `market_data_server.py` za strukturu" and to keep logic testable.
- `WYCKOFF_PORTFOLIO_DIR` env override exists primarily for test isolation and future deployment flexibility; default stays `data/portfolios/`.
- Faza-2 OHLCV mark-to-market equity is intentionally deferred — the optional `marks` parameter on the store is the seam where it would later plug in without reopening this design.

## Next Step

```text
$prp-implement PRPs/plans/trading-portfolio-mcp.plan.md
```

(Or proceed with implementation in this worktree; `prp-implement` is available as `prp-core:prp-implement`.)
