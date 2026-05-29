# Feature: Signal Logger MCP Server

## Summary

Implement GitHub issue [#21](https://github.com/ssmiljanicc/wyckoff-ai/issues/21): an MCP server that logs every trading signal the agent generates (with full Wyckoff metadata) to append-only monthly JSONL files, and supports deterministic replay against historical price/OHLCV to compute would-have outcomes (hit TP / hit SL / open).

This is Phase 2 (M5) of `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md`. Without a signal log there is no feedback loop — and per the crypto archive, failed signals are the most informative in Wyckoff, so they must be captured and replayable.

The work is one new module `scripts/mcp/signal_logger_server.py` (store logic + thin MCP tool wrappers, mirroring `scripts/mcp/market_data_server.py`), a one-line registration in `scripts/mcp/__init__.py`, and a test file `tests/test_signal_logger_server.py`. No changes to `knowledge/wiki/`.

## User Story

As a Wyckoff crypto practitioner running the skill in signal/research mode,
I want every signal the agent emits recorded with its full evidence and Wyckoff metadata, and replayable against later price action,
So that I can measure the quality of the agent's (and my own) reasoning over time and backtest "would buying on spring + retest have paid off?".

## Problem Statement

Post-Faza-2 the skill is a single-shot analyzer with no memory of what it called. There is no path to:

- record a signal (entry zone, invalidation, target, evidence, phase, cited wiki pages) in a durable, queryable form;
- query past signals by symbol / date range / type;
- replay a recorded signal against subsequent price to get a deterministic outcome.

The PRD names this as a **Must** capability (`Solution Detail → Core Capabilities`): "Signal logger MCP (record agent calls with metadata) — Without log, no learning loop." Phase 5 (backtest runner) explicitly depends on this phase.

There is currently no `data/signals/` directory, no signal schema in code, and no MCP server for it. `scripts/mcp/` contains only the market-data and chart-renderer servers.

## Solution Statement

Add `scripts/mcp/signal_logger_server.py` containing:

- A stable `Signal` record shape (TypedDict) matching the schema in issue #21.
- A `SignalStore` class constructed with a base directory (default `data/signals/`), holding all I/O:
  - `log_signal(...)` — build a full record (generate `signal_id` uuid4, set `logged_at`), append one JSON line to `data/signals/<YYYY-MM>.jsonl` keyed off the signal timestamp, return the record (incl. `signal_id`).
  - `list_signals(symbol=None, start=None, end=None, signal_type=None)` — scan only the month files overlapping the date range, filter, return records.
  - `get_signal(signal_id)` — locate and return the full record (or `None`).
  - `replay_signal(signal_id, current_price_or_ohlcv)` — deterministically compute `hit_tp` / `hit_sl` / `open` given a scalar price or a chronological OHLCV list.
- A module-level `store = SignalStore()` and thin `@mcp.tool()` wrappers delegating to it — mirroring how `market_data_server.py` keeps a module-level `client` and thin tools, so tests can swap the store via `monkeypatch` or construct `SignalStore(tmp_path)` directly.

Direction (long/short) is inferred from the `signal_type` prefix (`long_*` / `short_*`); replay tie-breaks are documented and deterministic (SL-before-TP when a single bar's range spans both — conservative).

## Metadata

| Field | Value |
| --- | --- |
| Feature type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Source issue | [#21 Trading MCP — signal logger](https://github.com/ssmiljanicc/wyckoff-ai/issues/21) |
| PRD | `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md` |
| PRD phase | Phase 2: Signal logger MCP / M5 |
| Worktree | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/trading-signal-logger` |
| Branch | `kild/trading-signal-logger` |
| New runtime deps | none (stdlib `json`, `uuid`, `datetime`, `pathlib`; `mcp[cli]` already present) |
| Plan output | `PRPs/plans/signal-logger-mcp.plan.md` |

## UX Design

Operator / API workflow (no UI). Before vs after:

```text
BEFORE
  Agent analyzes a chart in signal mode
    -> emits "long spring retest, entry 42000-42500, SL 40500, TP 48000-52000"
    -> output is text only; nothing is stored
    -> no way to query it later, no way to replay it

AFTER
  Agent calls log_signal(...) on the MCP server
    -> a full record + signal_id is appended to data/signals/2026-05.jsonl
    -> list_signals(symbol="BTC/USDT", start=..., end=...) returns it
    -> get_signal(signal_id) returns the full record
    -> replay_signal(signal_id, ohlcv) -> {"outcome": "hit_tp"|"hit_sl"|"open", ...}
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| MCP layer | only market-data + chart tools | + signal log/list/get/replay tools | agent can persist & replay signals |
| `data/signals/` | does not exist | monthly append-only JSONL | durable, inspectable signal history |

## Mandatory Reading

Before implementing, read:

- `scripts/mcp/market_data_server.py` — the thin-server pattern to mirror (module-level shared object + `@mcp.tool()` wrappers + `main()`).
- `scripts/mcp/market_data_client.py:32-49` — TypedDict record style (`Candle`, `SymbolInfo`); `:51-61` exception class style; `:75-103` input-normalization/validation style.
- `tests/test_market_data_server.py` — the test style: import the server module, `monkeypatch.setattr(module, "shared_obj", fake)`, assert on tool return values.
- `tests/conftest.py` — repo-root is put on `sys.path`; tests import via `from scripts.mcp import ...`.
- Issue #21 schema block (reproduced under *Step-by-Step Tasks* below).
- `CLAUDE.md` §0.1 (commit/PR language: Serbian body, English title) and §0.2 (light review for MCP servers).

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| SERVER | `scripts/mcp/market_data_server.py:16-39` | FastMCP instance + module-level shared obj + thin `@mcp.tool()` wrappers + `main()`/`__main__` | `mcp = FastMCP("wyckoff-market-data")` / `client = BinanceMarketDataClient()` / `@mcp.tool()` def get_ohlcv(...) -> ...: return client.get_ohlcv(...)` / `def main() -> None: mcp.run()` |
| TYPES | `scripts/mcp/market_data_client.py:32-49` | TypedDict for stable record shapes | `class Candle(TypedDict): open_time: int; open: float; ...` |
| ERRORS | `scripts/mcp/market_data_client.py:51-61` | Domain exception hierarchy on `RuntimeError` | `class BinanceMarketDataError(RuntimeError): ...` / `class BinanceUpstreamError(BinanceMarketDataError): ...` |
| VALIDATION | `scripts/mcp/market_data_client.py:75-103` | Validate/normalize inputs, raise `ValueError` with helpful message | `if not raw: raise ValueError("Symbol is required")` |
| CONFIG INJECTION | `scripts/mcp/market_data_client.py:113-130` | Constructor takes overridable config (`base_url=...`) so tests inject; `client` built at module load | `def __init__(self, *, base_url: str = BINANCE_BASE_URL, ...)` |
| TESTS | `tests/test_market_data_server.py:37-44` | monkeypatch the shared module object with a fake, assert on tool output | `monkeypatch.setattr(market_data_server, "client", fake)` |
| HEADER | `scripts/mcp/market_data_client.py:1-3` | module docstring + `from __future__ import annotations` | `"""..."""` then `from __future__ import annotations` |

## Files to Change

| File | Change | Notes |
| --- | --- | --- |
| `scripts/mcp/signal_logger_server.py` | **new** | store logic (`Signal` TypedDict, `SignalStore`, errors) + FastMCP server + tool wrappers + `main()` |
| `scripts/mcp/__init__.py` | **add one line** | register the new server per issue instruction; do not touch existing content |
| `tests/test_signal_logger_server.py` | **new** | covers the three success signals from the issue |
| `.claude/PRPs/prds/faza-3-trading-and-ml.prd.md` | status update | mark Phase 2 `in-progress`, link this plan (done by planning step) |

`data/signals/` is created at runtime by the store (`mkdir(parents=True, exist_ok=True)`) — not committed. `data/` is **not** currently in `.gitignore`; tests must write to a `tmp_path`, never to the repo's `data/`. (See Risks for the gitignore decision.)

## NOT Building

- Virtual portfolio / `open_position` (Phase 1, separate issue) — only note that `signal_id` is the join key.
- Backtest runner stats engine (Phase 5) — replay computes a single signal's outcome, not portfolio P&L.
- Scanner, skill signal-mode contract, ML (Phases 3,4,6–9).
- Slippage/spread/fees modeling — bar-close/touch fills only (PRD decision: simple at MVP).
- Editing or deleting signals — the log is append-only.
- Any change to `knowledge/wiki/`.

## Step-by-Step Tasks

Canonical record schema (from issue #21) — implement exactly these keys:

```json
{
  "signal_id": "uuid",
  "logged_at": "2026-05-24T15:00:00Z",
  "symbol": "BTC/USDT",
  "timeframe": "1d",
  "signal_type": "long_spring_retest",
  "entry_zone": [42000, 42500],
  "invalidation": 40500,
  "target_zone": [48000, 52000],
  "tactical_quality": "Phase C aggressive",
  "evidence": ["climactic low at $30k", "AR to $38k", "tested $30k 3x", "spring printed"],
  "phase_identified": "C",
  "wiki_pages_cited": ["events/spring.md", "structures/accumulation.md"]
}
```

### Task 1 — Module skeleton, types, errors

- **Action:** create `scripts/mcp/signal_logger_server.py`.
- **Implementation:** module docstring `"""MCP server for logging and replaying Wyckoff trading signals."""`; then `from __future__ import annotations`; imports `json`, `uuid`, `os` (only if needed for atomic write), `from dataclasses import` not needed, `from datetime import datetime, timezone, date`, `from pathlib import Path`, `from typing import Iterable, Literal, TypedDict`, `from mcp.server.fastmcp import FastMCP`.
  - Define `DEFAULT_SIGNALS_DIR = Path("data/signals")`.
  - Define `class Signal(TypedDict)` with the 12 keys above (`entry_zone: list[float]`, `target_zone: list[float]`, `invalidation: float`, `evidence: list[str]`, `wiki_pages_cited: list[str]`, rest `str`).
  - Define `class SignalLoggerError(RuntimeError)` and `class SignalNotFoundError(SignalLoggerError)`.
  - Define `Outcome = Literal["hit_tp", "hit_sl", "open"]`.
- **Pattern to mirror:** header `market_data_client.py:1-9`; TypedDict `:32-49`; errors `:51-61`.
- **Gotchas:** use `from __future__ import annotations` so `list[float]` annotations work on 3.11; the venv runs 3.13 but `requires-python = ">=3.11"`.
- **Validation:** `uv run python -c "from scripts.mcp import signal_logger_server as s; print(s.Signal.__annotations__.keys())"`

### Task 2 — `SignalStore` with `log_signal`

- **Action:** add `class SignalStore` to the same file.
- **Implementation:**
  - `def __init__(self, base_dir: Path | str = DEFAULT_SIGNALS_DIR) -> None: self.base_dir = Path(base_dir)`.
  - Helper `def _month_file(self, when: datetime) -> Path: return self.base_dir / f"{when:%Y-%m}.jsonl"`.
  - Helper `_now() -> datetime` returning `datetime.now(timezone.utc)` (module-level function so tests can monkeypatch).
  - Helper `_parse_iso(ts: str) -> datetime` accepting trailing `Z` (normalize `Z`→`+00:00` before `datetime.fromisoformat`).
  - `def log_signal(self, *, symbol, timeframe, signal_type, entry_zone, invalidation, target_zone, tactical_quality, evidence, phase_identified, wiki_pages_cited, timestamp=None) -> Signal:`
    - Validate: `symbol` non-empty; `entry_zone`/`target_zone` are 2-element numeric lists; `signal_type` starts with `long_`/`short_` (raise `ValueError` listing accepted prefixes); raise `ValueError` otherwise.
    - `logged_at` = `timestamp` if provided else `_now()`; accept either a `datetime` or an ISO string for `timestamp`; the **month file is chosen by `logged_at`**.
    - Build record: `signal_id = str(uuid.uuid4())`, `logged_at` serialized as `...isoformat()` normalized to `Z` (e.g. `.replace("+00:00","Z")`).
    - `self.base_dir.mkdir(parents=True, exist_ok=True)`; append `json.dumps(record) + "\n"` to the month file opened in `"a"` mode with `encoding="utf-8"`.
    - Return the record.
  - **Note on the issue's tool signature** `log_signal(symbol, timeframe, signal_type, entry, sl, tp, evidence, phase, tactical_quality, timestamp)`: map `entry→entry_zone`, `sl→invalidation`, `tp→target_zone`, `phase→phase_identified`. Keep the **stored** schema exactly as the issue's schema block. Decide at implementation: store-level method uses schema names; the MCP tool wrapper (Task 6) exposes the issue's argument names and translates. Document this mapping in a comment.
- **Gotchas:** open in append mode per call (cheap, durable); do **not** hold the file open. One JSON object per line, no pretty-print (JSONL).
- **Validation:** covered by Task 7 roll-over + list tests.

### Task 3 — `list_signals` with filters

- **Action:** add `list_signals` to `SignalStore`.
- **Implementation:** `def list_signals(self, *, symbol=None, start=None, end=None, signal_type=None) -> list[Signal]:`
  - Accept `start`/`end` as `datetime | str | None`; parse strings via `_parse_iso`.
  - Determine candidate month files: if both bounds present, iterate only `YYYY-MM` files in `[start, end]` month range; else `sorted(self.base_dir.glob("*.jsonl"))`. If dir missing, return `[]`.
  - Read each file line-by-line, `json.loads`, skip blank lines; filter by `symbol` (exact), `signal_type` (exact), and `start <= logged_at <= end`.
  - Return in chronological order (sort by `logged_at`).
- **Gotchas:** date-range filter is on `logged_at`; tolerate naive vs aware by normalizing both to aware UTC. Be robust to a missing base dir (return `[]`, do not raise) — `list_signals` on a fresh install is a valid empty query.
- **Validation:** Task 7 list + roll-over tests.

### Task 4 — `get_signal`

- **Action:** add `get_signal`.
- **Implementation:** `def get_signal(self, signal_id: str) -> Signal | None:` scan month files (newest first is fine), return first record whose `signal_id` matches, else `None`. (MCP wrapper may raise `SignalNotFoundError`; store returns `None` to stay composable — decide and document.)
- **Validation:** `get_signal(logged_id)` returns the record; `get_signal("nope")` returns `None`.

### Task 5 — `replay_signal` (deterministic outcome)

- **Action:** add `replay_signal`.
- **Implementation:** `def replay_signal(self, signal_id, current_price_or_ohlcv) -> dict:`
  - Fetch the record (raise/return-None handling consistent with Task 4 decision; for replay, raise `SignalNotFoundError` if absent).
  - Infer `side`: `"long"` if `signal_type.startswith("long")`, `"short"` if `startswith("short")`, else raise `ValueError`.
  - Define levels: long → TP touched when price/high `>= min(target_zone)`, SL touched when price/low `<= invalidation`. Short → TP when price/low `<= max(target_zone)`, SL when price/high `>= invalidation`. (Document the exact comparison chosen.)
  - **Scalar input** (`int`/`float`): TP-touch and SL-touch both checked; if both true (impossible for a scalar unless levels cross) tie-break SL. Return outcome.
  - **OHLCV input** (`list` of dicts with `high`/`low`, like `Candle`): iterate **in chronological order**; for each bar, if both SL and TP are touched within the same bar, resolve **SL first** (conservative — we cannot know intrabar path); return on first resolved bar. If no bar resolves, `"open"`.
  - Return `{"signal_id": ..., "side": side, "outcome": "hit_tp"|"hit_sl"|"open", "resolved_at": <bar index or open_time or None>}`.
- **Pattern to mirror:** `Candle` keys (`high`, `low`, `open_time`) from `market_data_client.py:32-42`.
- **Gotchas:** determinism is the success criterion — same inputs always same outcome. Document the intrabar SL-first rule in a comment and the test. Handle empty OHLCV list → `"open"`.
- **Validation:** Task 7 replay test (hit_tp / hit_sl / open).

### Task 6 — FastMCP server + tool wrappers + `main()`

- **Action:** add the server instance and tools below the store class.
- **Implementation:** `mcp = FastMCP("wyckoff-signal-logger")`; `store = SignalStore()`; four `@mcp.tool()` functions delegating to `store`:
  - `log_signal(symbol, timeframe, signal_type, entry, sl, tp, evidence, phase, tactical_quality, timestamp=None)` — translate arg names to schema (Task 2 note), return the record.
  - `list_signals(symbol=None, start=None, end=None, signal_type=None)`.
  - `get_signal(signal_id)`.
  - `replay_signal(signal_id, current_price_or_ohlcv)`.
  - `def main() -> None: mcp.run()` and `if __name__ == "__main__": main()`.
- **Pattern to mirror:** `market_data_server.py:16-43` exactly.
- **Gotchas:** keep tool bodies one-liners delegating to `store`, so tests can `monkeypatch.setattr(signal_logger_server, "store", SignalStore(tmp_path))`.
- **Validation:** `uv run python -c "from scripts.mcp import signal_logger_server as s; print(s.mcp.name)"`

### Task 7 — Tests

- **Action:** create `tests/test_signal_logger_server.py`.
- **Implementation:** mirror `tests/test_market_data_server.py` import style. Use the `tmp_path` pytest fixture and construct `SignalStore(tmp_path)` (or monkeypatch `signal_logger_server.store`). Cover the issue's three success signals:
  1. **list filter works:** log several signals (varied `symbol`, `signal_type`, recent timestamps) → `list_signals(symbol=..., start=now-Ndays, end=now)` returns exactly the matching ones; assert a non-matching symbol/type is excluded.
  2. **deterministic replay:** log a `long_*` signal (e.g. entry [42000,42500], invalidation 40500, target [48000,52000]); replay against three crafted OHLCV series → one that hits TP returns `hit_tp`, one that hits SL returns `hit_sl`, one that stays in range returns `open`. Add a same-bar-spans-both case asserting `hit_sl` (tie-break). Optionally a `short_*` case. Assert running replay twice gives identical output.
  3. **JSONL roll-over:** log one signal with `timestamp` in month A and one in month B → assert two files exist (`A.jsonl`, `B.jsonl`), each with exactly one line, and `list_signals()` returns both.
  - Add a small unit test for the `long_/short_` prefix `ValueError` and for `get_signal` miss → `None`.
- **Gotchas:** never write to repo `data/` — always `tmp_path`. If monkeypatching `_now`, restore via the fixture.
- **Validation:** `uv run pytest tests/test_signal_logger_server.py -v` — all pass.

### Task 8 — Register server in `scripts/mcp/__init__.py`

- **Action:** add one line to `scripts/mcp/__init__.py`, per the issue ("samo dodaj svoju liniju — ne diraj postojeće").
- **Implementation:** the existing `__init__.py` is only a docstring and does **not** import `market_data_server`, so there is no existing import line to mirror. Add a single import that makes the server importable as a package attribute:
  ```python
  from scripts.mcp import signal_logger_server  # noqa: F401
  ```
  This satisfies "register your server" without touching the docstring or any existing line. (See Risks — if a different registration convention is expected, this is the one ambiguous spot; flag in the PR.)
- **Gotchas:** do not reorder or modify the docstring; append below it.
- **Validation:** `uv run python -c "import scripts.mcp; from scripts.mcp import signal_logger_server"`

### Task 9 — Full validation + commit + PR

- **Action:** run the full suite, lint-check imports, then commit (Serbian message) and open a PR to `main`.
- **Validation:** see Validation Commands. PR: English title, Serbian body, links #21.

## Testing Strategy

- Pure-stdlib, filesystem-backed; no network, no MCP transport needed — call the `SignalStore` methods (and/or the thin tool wrappers) directly, exactly as `test_market_data_server.py` calls `market_data_server.get_ohlcv` after swapping the shared object.
- Determinism is asserted explicitly (replay twice → equal) because it is a PRD success metric.
- `tmp_path` isolates all writes; no fixture writes into the repo tree.

## Validation Commands

```bash
# from repo root: /Users/ssmiljanic/.kild/worktrees/wyckoff-ai/trading-signal-logger
uv run pytest tests/test_signal_logger_server.py -v        # all pass — primary gate
uv run pytest -q                                            # full suite still green
uv run python -c "import scripts.mcp; from scripts.mcp import signal_logger_server as s; print(s.mcp.name)"
uv run python -c "from scripts.mcp.signal_logger_server import SignalStore; print('store ok')"
git status --short                                          # only the 3 intended files (+ PRD) changed
```

## Acceptance Criteria

- `scripts/mcp/signal_logger_server.py` exists with `Signal` TypedDict matching issue #21's 12-key schema, a `SignalStore`, and four MCP tools.
- `log_signal` appends one JSONL line and returns a record with a uuid `signal_id` and `logged_at`.
- `list_signals` filters by symbol, date range, and signal_type.
- `get_signal` returns the full record by id (or None / not-found per documented choice).
- `replay_signal` returns a deterministic `hit_tp` / `hit_sl` / `open` for scalar and OHLCV inputs.
- Signals from two different months land in two different `data/signals/<YYYY-MM>.jsonl` files.
- `scripts/mcp/__init__.py` gains exactly one line; existing content untouched.
- `uv run pytest tests/test_signal_logger_server.py -v` passes; full suite stays green.
- `knowledge/wiki/` untouched.
- Commit message Serbian; PR English title + Serbian body linking #21.

## Completion Checklist

- [ ] `signal_logger_server.py` created (types, errors, store, server, main)
- [ ] `__init__.py` one-line registration added
- [ ] `tests/test_signal_logger_server.py` covers list-filter, deterministic replay (TP/SL/open + tie-break), month roll-over, prefix validation, get-miss
- [ ] `uv run pytest tests/test_signal_logger_server.py -v` green
- [ ] full `uv run pytest -q` green
- [ ] `git status` shows only intended files
- [ ] decision on `.gitignore` for `data/signals/` resolved (see Risks)
- [ ] commit (Serbian) + PR (English title, Serbian body, links #21)

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Tests pollute repo `data/signals/` | Medium | Always use `tmp_path`; never default-dir in tests |
| `data/signals/*.jsonl` accidentally committed | Medium | `data/` is **not** in `.gitignore`. Decide: add `data/signals/` (or `data/`) to `.gitignore` so runtime signals aren't committed. Flag in PR; default recommendation = ignore `data/signals/`. |
| `__init__.py` registration convention differs from expectation | Low | Existing file imports nothing; chose minimal `from scripts.mcp import signal_logger_server`. Called out in PR for reviewer confirmation per CLAUDE.md §0.2 light review. |
| Intrabar SL/TP ambiguity breaks determinism | Medium | Fixed rule: same-bar both-touched → SL first; documented in code + asserted in test |
| Timezone naive/aware mismatch in date filter | Medium | Normalize all timestamps to aware UTC; `Z`↔`+00:00` handling in `_parse_iso` |
| `signal_type` without long/short prefix can't infer side | Low | Validate prefix at `log_signal`; raise `ValueError` early so bad signals never persist |

## Notes

- Replay deliberately assumes the signal *was taken* (entry filled) and only resolves TP/SL/open — entry-fill modeling and P&L belong to the Phase 5 backtest runner.
- `signal_id` is the documented join key for the Phase 1 portfolio MCP (`open_position` may reference it); no coupling is built here.
- Keeping store + server in one file matches the issue's "Novi fajl: signal_logger_server.py" while still isolating I/O in `SignalStore` for testability — the only deviation from the two-file market-data layout (`client` + `server`), justified by the issue's explicit single-file instruction.
- Confidence: **8/10**. Schema and success signals are concrete; the only genuine ambiguities are the `__init__.py` registration convention and the `.gitignore` decision, both flagged for the reviewer.
