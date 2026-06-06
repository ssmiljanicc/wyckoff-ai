"""Backtest runner MCP server.

Replay a stream of logged Wyckoff signals, or a declarative rule, against
historical OHLCV candles and produce a reproducible P&L plus summary
statistics. This closes the loop between the Signal Logger (#21) and the
Market Data client (#9): it answers whether a Wyckoff setup actually works
— win-rate, average gain/loss, drawdown, Sharpe.

Design invariants:
    - Walk-forward, no future leakage. A trade's entry always fills on a
      candle that opens strictly *after* the decision candle (the signal's
      timestamp, or the candle whose close triggered a rule). An entry
      decision never reads a price from a candle before the entry candle.
    - Faithful to the logged signal. A ``backtest_signals`` trade exits on
      the signal's own ``invalidation`` (stop) or ``target_zone`` (target),
      walking the candles forward bar by bar with the same conservative
      stop-before-target tie-break the Signal Logger's ``replay_signal``
      uses. ``max_holding_bars`` is an optional timeout, not the exit model.
    - Reproducible. There is no randomness in the P&L path: identical input
      yields identical statistics across any number of runs. (The
      ``backtest_id`` itself is a random uuid4 — it labels the run, it is
      not part of the computed result.)
    - In-memory storage. Completed backtests live in a process-local dict
      keyed by ``backtest_id``; they do not survive a restart.

Tools exposed:
    - backtest_signals: replay logged signals as trades
    - backtest_rule: replay a declarative breakout rule as trades
    - get_stats: fetch the summary statistics for a completed backtest

Run as a standalone MCP server over stdio:
    uv run python -m scripts.mcp.backtest_server
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from mcp.server.fastmcp import FastMCP

from scripts.mcp.market_data_client import Candle

# Fill rules (MVP). A fill rule maps a decision into an executed entry price.
FILL_NEXT_BAR_OPEN = "next_bar_open"
FILL_FIXED_SLIPPAGE = "fixed_slippage_0.1pct"
_VALID_FILL_RULES = {FILL_NEXT_BAR_OPEN, FILL_FIXED_SLIPPAGE}
_SLIPPAGE_PCT = 0.001  # 0.1%

# Default holding period (in bars) for the declarative rule engine.
_DEFAULT_HOLDING_BARS = 5

# How many candles to pull per (symbol, timeframe). The Binance client is
# limit-based (most recent N), so we ask for the maximum and filter by date.
_DEFAULT_CANDLE_LIMIT = 1000


# --------------------------------------------------------------------------
# Duck-typed dependencies (overridable in tests).
# --------------------------------------------------------------------------


class _MarketClient(Protocol):
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        ...


class _SignalStore(Protocol):
    def list_signals(
        self,
        *,
        symbol: str | None = ...,
        start: Any = ...,
        end: Any = ...,
        signal_type: str | None = ...,
    ) -> list[dict[str, Any]]:
        ...


_market_client: _MarketClient | None = None
_signal_store: _SignalStore | None = None
_backtests: dict[str, dict[str, Any]] = {}


def _get_market_client() -> _MarketClient:
    global _market_client
    if _market_client is None:
        from scripts.mcp.market_data_client import BinanceMarketDataClient

        _market_client = BinanceMarketDataClient()
    return _market_client


def _get_signal_store() -> _SignalStore:
    global _signal_store
    if _signal_store is None:
        from scripts.mcp.signal_logger_server import store

        _signal_store = store
    return _signal_store


# --------------------------------------------------------------------------
# Time helpers. Candles carry ``open_time`` as epoch milliseconds; signals
# carry ``logged_at`` as an ISO-8601 string. Everything is compared in ms.
# --------------------------------------------------------------------------


def _iso_to_ms(value: str | None) -> int | None:
    """Parse an ISO-8601 timestamp into epoch milliseconds (UTC)."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ms_to_day(time_ms: int) -> str:
    """Render an epoch-ms timestamp as a UTC calendar day (``YYYY-MM-DD``)."""
    return datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# Core simulation (pure, deterministic).
# --------------------------------------------------------------------------


def _side_for_signal(signal: dict[str, Any]) -> str:
    """Resolve the trade side for a logged signal.

    The signal store's ``signal_type`` is prefixed ``long_`` / ``short_``
    (e.g. ``long_spring``). An explicit ``side`` field wins if present;
    otherwise the prefix decides, defaulting to long.
    """
    side = signal.get("side")
    if side in ("long", "short"):
        return side
    signal_type = str(signal.get("signal_type", "")).lower()
    if signal_type.startswith("short"):
        return "short"
    return "long"


def _apply_entry_slippage(price: float, side: str, fill_rule: str) -> float:
    """Adjust an entry fill price for the fill rule.

    ``fixed_slippage_0.1pct`` moves the fill 0.1% against the trader: a
    long pays more, a short receives less. ``next_bar_open`` is a clean
    fill with no slippage.
    """
    if fill_rule != FILL_FIXED_SLIPPAGE:
        return price
    if side == "long":
        return price * (1.0 + _SLIPPAGE_PCT)
    return price * (1.0 - _SLIPPAGE_PCT)


def _trade_return(side: str, entry: float, exit_price: float) -> float:
    """Per-trade fractional return (e.g. 0.05 == +5%)."""
    if entry == 0:
        return 0.0
    if side == "long":
        return (exit_price - entry) / entry
    return (entry - exit_price) / entry


def _resolve_signal_exit(
    candles: list[Candle],
    entry_index: int,
    side: str,
    invalidation: float | None,
    target_zone: list[float] | None,
    max_holding_bars: int | None,
) -> tuple[int, float, str]:
    """Walk forward from the entry candle to the signal's stop/target exit.

    Returns ``(exit_index, exit_price, outcome)``. The stop (``invalidation``)
    is checked before the target on each candle, so a candle whose range
    spans both resolves conservatively to ``hit_sl`` — the intrabar path is
    unknown, mirroring ``signal_logger_server.replay_signal``.

    The first target reached is used: ``min(target_zone)`` for a long,
    ``max(target_zone)`` for a short. When the signal carries no usable
    stop/target, or neither is touched before the data (or
    ``max_holding_bars``) runs out, the trade exits at the last candle's
    close with outcome ``"timeout"``.
    """
    last = len(candles) - 1
    if max_holding_bars is not None:
        last = min(last, entry_index + max_holding_bars)

    has_levels = invalidation is not None and bool(target_zone)
    if has_levels:
        inval = float(invalidation)
        target = min(target_zone) if side == "long" else max(target_zone)
        for i in range(entry_index, last + 1):
            high = float(candles[i]["high"])
            low = float(candles[i]["low"])
            if side == "long":
                if low <= inval:
                    return i, inval, "hit_sl"
                if high >= target:
                    return i, target, "hit_tp"
            else:
                if high >= inval:
                    return i, inval, "hit_sl"
                if low <= target:
                    return i, target, "hit_tp"

    exit_candle = candles[last]
    return last, float(exit_candle["close"]), "timeout"


def _simulate_signal_trade(
    candles: list[Candle],
    entry_index: int,
    side: str,
    fill_rule: str,
    signal: dict[str, Any],
    max_holding_bars: int | None,
) -> dict[str, Any] | None:
    """Simulate one trade from a logged signal using its own stop/target.

    ``entry_index`` is the candle whose *open* fills the entry — it must lie
    strictly after the signal (no future leakage). The exit is resolved by
    :func:`_resolve_signal_exit` against the signal's ``invalidation`` and
    ``target_zone``.

    Returns ``None`` when there is no candle available to fill the entry.
    """
    if entry_index < 0 or entry_index >= len(candles):
        return None
    entry_candle = candles[entry_index]
    entry_price = _apply_entry_slippage(float(entry_candle["open"]), side, fill_rule)

    exit_index, exit_price, outcome = _resolve_signal_exit(
        candles,
        entry_index,
        side,
        signal.get("invalidation"),
        signal.get("target_zone"),
        max_holding_bars,
    )
    exit_candle = candles[exit_index]
    pnl_pct = _trade_return(side, entry_price, exit_price)
    return {
        "side": side,
        "entry_time": entry_candle["open_time"],
        "entry_price": entry_price,
        "exit_time": exit_candle["open_time"],
        "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "outcome": outcome,
    }


def _simulate_holding_trade(
    candles: list[Candle],
    entry_index: int,
    side: str,
    fill_rule: str,
    holding_bars: int,
) -> dict[str, Any] | None:
    """Simulate a fixed-holding trade (used by the rule engine).

    ``entry_index`` is the candle whose *open* fills the entry — it must lie
    strictly after the decision candle, which keeps the simulation free of
    future leakage. The trade exits at the close of the candle
    ``holding_bars`` later, clamped to the last available candle.

    Returns ``None`` when there is no candle available to fill the entry.
    """
    if entry_index < 0 or entry_index >= len(candles):
        return None
    entry_candle = candles[entry_index]
    entry_price = _apply_entry_slippage(float(entry_candle["open"]), side, fill_rule)

    exit_index = min(entry_index + holding_bars, len(candles) - 1)
    exit_candle = candles[exit_index]
    exit_price = float(exit_candle["close"])

    pnl_pct = _trade_return(side, entry_price, exit_price)
    return {
        "side": side,
        "entry_time": entry_candle["open_time"],
        "entry_price": entry_price,
        "exit_time": exit_candle["open_time"],
        "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "outcome": "timeout",
    }


def _first_index_after(candles: list[Candle], time_ms: int) -> int:
    """Index of the first candle whose open_time is strictly after ``time_ms``.

    Returns ``len(candles)`` when no such candle exists. Candles are
    assumed sorted chronologically (the market data client returns them in
    order).
    """
    for i, candle in enumerate(candles):
        if int(candle["open_time"]) > time_ms:
            return i
    return len(candles)


def _filter_range(
    candles: list[Candle],
    start_ms: int | None,
    end_ms: int | None,
) -> list[Candle]:
    """Keep only candles whose open_time falls within [start_ms, end_ms]."""
    out = candles
    if start_ms is not None:
        out = [c for c in out if int(c["open_time"]) >= start_ms]
    if end_ms is not None:
        out = [c for c in out if int(c["open_time"]) <= end_ms]
    return out


def _sharpe_daily(trades: list[dict[str, Any]]) -> float:
    """Simple Sharpe over daily returns (per the issue: daily returns / std).

    Each trade's return is bucketed into the UTC calendar day of its exit;
    days with no trade are not synthesised. Sharpe is the mean of the daily
    series over its sample standard deviation. Fewer than two active days,
    or zero dispersion, yields 0.0.
    """
    by_day: dict[str, float] = {}
    for t in trades:
        day = _ms_to_day(int(t["exit_time"]))
        by_day[day] = by_day.get(day, 0.0) + t["pnl_pct"]

    daily = [by_day[d] for d in sorted(by_day)]
    n = len(daily)
    if n < 2:
        return 0.0
    mean = sum(daily) / n
    variance = sum((r - mean) ** 2 for r in daily) / (n - 1)
    std = variance ** 0.5
    return mean / std if std > 0 else 0.0


def _base_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """The seven core metrics over a list of completed trades.

    All money figures are fractional returns so trades on symbols with
    different price scales aggregate sensibly. ``max_drawdown`` is taken
    from a compounding equity curve walked in entry-time order; ``sharpe``
    is the simple daily Sharpe (see :func:`_sharpe_daily`).
    """
    ordered = sorted(trades, key=lambda t: int(t.get("entry_time", 0)))
    returns = [t["pnl_pct"] for t in ordered]
    total = len(returns)
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]

    gross_pnl = sum(returns)
    win_rate = len(wins) / total if total else 0.0
    avg_gain = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for r in returns:
        equity *= 1.0 + r
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "gross_pnl": gross_pnl,
        "avg_gain": avg_gain,
        "avg_loss": avg_loss,
        "max_drawdown": max_drawdown,
        "sharpe": _sharpe_daily(ordered),
    }


def _group_stats(trades: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Per-group base stats, grouped by ``trade[key]`` (None values skipped).

    Keys are sorted so the breakdown is deterministic. Trades that lack the
    attribute (e.g. rule trades have no ``tactical_quality``) are omitted,
    yielding an empty mapping rather than a spurious ``None`` group.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        value = t.get(key)
        if value is None:
            continue
        groups.setdefault(str(value), []).append(t)
    return {k: _base_stats(groups[k]) for k in sorted(groups)}


def _compute_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats plus per-tactical-quality and per-phase breakdowns."""
    stats = _base_stats(trades)
    stats["by_tactical_quality"] = _group_stats(trades, "tactical_quality")
    stats["by_phase"] = _group_stats(trades, "phase")
    return stats


def _store_backtest(
    kind: str,
    params: dict[str, Any],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a completed backtest in-memory and return its record."""
    backtest_id = str(uuid.uuid4())
    stats = _compute_stats(trades)
    record = {
        "backtest_id": backtest_id,
        "kind": kind,
        "params": params,
        "trades": trades,
        "stats": stats,
    }
    _backtests[backtest_id] = record
    return record


# --------------------------------------------------------------------------
# Declarative rule engine (MVP: breakout).
# --------------------------------------------------------------------------


def _breakout_trigger_indices(
    candles: list[Candle],
    side: str,
    lookback: int,
    holding_bars: int,
) -> list[int]:
    """Decision-candle indices for a breakout rule, non-overlapping.

    A long triggers on the first candle whose close exceeds the highest
    high of the prior ``lookback`` candles; a short triggers on a close
    below the lowest low. After a trigger we skip ahead past the resulting
    trade's holding window so trades never overlap (no pyramiding) — this
    keeps the result deterministic regardless of position sizing.

    Returned indices are *decision* candles; the actual entry fills on the
    following candle (handled by the caller), preserving walk-forward order.
    """
    triggers: list[int] = []
    i = lookback
    while i < len(candles):
        window = candles[i - lookback:i]
        close = float(candles[i]["close"])
        if side == "long":
            hit = close > max(float(c["high"]) for c in window)
        else:
            hit = close < min(float(c["low"]) for c in window)
        if hit:
            triggers.append(i)
            # Skip past the entry candle (i+1) and its holding window.
            i = i + 1 + holding_bars + 1
        else:
            i += 1
    return triggers


# --------------------------------------------------------------------------
# MCP server + tools.
# --------------------------------------------------------------------------

mcp = FastMCP("wyckoff-backtest")


@mcp.tool()
def backtest_signals(
    signal_filter: dict[str, Any] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fill_rule: str = FILL_NEXT_BAR_OPEN,
    max_holding_bars: int | None = None,
    candle_limit: int = _DEFAULT_CANDLE_LIMIT,
) -> dict[str, Any]:
    """Backtest a stream of logged Wyckoff signals.

    Each matching signal becomes one trade: it enters on the candle that
    opens after the signal's ``logged_at`` (per ``fill_rule``), then exits
    on the signal's own ``invalidation`` (stop) or ``target_zone`` (target),
    walking the candles forward bar by bar — stop checked before target.
    Signals are processed in chronological order, so the run is walk-forward
    by construction.

    The signal's own ``timeframe`` field selects which OHLCV series the
    fills are resolved against. ``signal_filter`` accepts ``symbol`` and
    ``signal_type`` keys (passed through to the signal store).

    Args:
        signal_filter: Optional ``{symbol, signal_type}`` filter.
        start_date: ISO-8601 inclusive lower bound on signal timestamps.
        end_date: ISO-8601 inclusive upper bound on signal timestamps.
        fill_rule: ``"next_bar_open"`` or ``"fixed_slippage_0.1pct"``.
        max_holding_bars: Optional timeout — exit at the candle's close this
            many bars after entry if neither stop nor target is hit. When
            ``None`` (default) the trade runs until stop/target or the end
            of the available candles.
        candle_limit: How many candles to pull per (symbol, timeframe).

    Returns:
        ``{"backtest_id": ..., "summary": {...stats...}}``. The summary
        carries the seven core metrics plus ``by_tactical_quality`` and
        ``by_phase`` breakdowns.
    """
    if fill_rule not in _VALID_FILL_RULES:
        raise ValueError(
            f"unknown fill_rule {fill_rule!r}; "
            f"expected one of {sorted(_VALID_FILL_RULES)}"
        )
    if max_holding_bars is not None and max_holding_bars < 1:
        raise ValueError("max_holding_bars must be >= 1 when set")

    flt = signal_filter or {}
    signals = _get_signal_store().list_signals(
        symbol=flt.get("symbol"),
        signal_type=flt.get("signal_type"),
        start=start_date,
        end=end_date,
    )
    # list_signals() already sorts by logged_at; re-sort defensively.
    signals = sorted(signals, key=lambda s: s.get("logged_at", ""))

    client = _get_market_client()
    # Fetch OHLCV once per (symbol, timeframe) — avoid refetching in the loop.
    candle_cache: dict[tuple[str, str], list[Candle]] = {}
    trades: list[dict[str, Any]] = []
    for signal in signals:
        symbol = signal.get("symbol")
        timeframe = signal.get("timeframe")
        if not symbol or not timeframe:
            continue
        key = (symbol, timeframe)
        if key not in candle_cache:
            candle_cache[key] = client.get_ohlcv(symbol, timeframe, candle_limit)
        candles = candle_cache[key]

        signal_ms = _iso_to_ms(signal.get("logged_at"))
        if signal_ms is None:
            continue
        entry_index = _first_index_after(candles, signal_ms)
        side = _side_for_signal(signal)
        trade = _simulate_signal_trade(
            candles, entry_index, side, fill_rule, signal, max_holding_bars
        )
        if trade is not None:
            trade["signal_id"] = signal.get("signal_id")
            trade["symbol"] = symbol
            trade["tactical_quality"] = signal.get("tactical_quality")
            trade["phase"] = signal.get("phase_identified")
            trades.append(trade)

    record = _store_backtest(
        "signals",
        {
            "signal_filter": flt,
            "start_date": start_date,
            "end_date": end_date,
            "fill_rule": fill_rule,
            "max_holding_bars": max_holding_bars,
        },
        trades,
    )
    return {"backtest_id": record["backtest_id"], "summary": record["stats"]}


@mcp.tool()
def backtest_rule(
    rule_definition: dict[str, Any],
    symbols: list[str],
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    fill_rule: str = FILL_NEXT_BAR_OPEN,
    candle_limit: int = _DEFAULT_CANDLE_LIMIT,
) -> dict[str, Any]:
    """Backtest a declarative breakout rule across symbols.

    ``rule_definition`` (MVP) supports a single breakout entry::

        {
            "side": "long" | "short",   # default "long"
            "entry": "breakout",         # only supported entry type
            "lookback": 3,                # breakout window in candles
            "holding_bars": 5             # candles to hold each trade
        }

    A long enters when a candle's close exceeds the highest high of the
    prior ``lookback`` candles; a short enters on a close below the lowest
    low. The entry fills on the *next* candle's open (per ``fill_rule``), so
    no future data influences the entry decision. A rule has no stop/target,
    so each trade exits at the close ``holding_bars`` candles after entry.
    Trades are non-overlapping.

    Args:
        rule_definition: The breakout rule, as above.
        symbols: Symbols to scan.
        timeframe: OHLCV timeframe, e.g. ``"1d"``.
        start: Optional ISO-8601 inclusive lower bound for candles.
        end: Optional ISO-8601 inclusive upper bound for candles.
        fill_rule: ``"next_bar_open"`` or ``"fixed_slippage_0.1pct"``.
        candle_limit: How many candles to pull per symbol.

    Returns:
        ``{"backtest_id": ..., "summary": {...stats...}}``.
    """
    if fill_rule not in _VALID_FILL_RULES:
        raise ValueError(
            f"unknown fill_rule {fill_rule!r}; "
            f"expected one of {sorted(_VALID_FILL_RULES)}"
        )

    entry_type = rule_definition.get("entry", "breakout")
    if entry_type != "breakout":
        raise ValueError(
            f"unsupported entry type {entry_type!r}; only 'breakout' is "
            "supported in the MVP"
        )

    side = rule_definition.get("side", "long")
    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    lookback = int(rule_definition.get("lookback", 3))
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    holding_bars = int(rule_definition.get("holding_bars", _DEFAULT_HOLDING_BARS))
    if holding_bars < 1:
        raise ValueError("holding_bars must be >= 1")

    start_ms = _iso_to_ms(start)
    end_ms = _iso_to_ms(end)

    client = _get_market_client()
    trades: list[dict[str, Any]] = []
    # Symbols processed in stable order for reproducibility.
    for symbol in symbols:
        candles = _filter_range(
            client.get_ohlcv(symbol, timeframe, candle_limit), start_ms, end_ms
        )
        triggers = _breakout_trigger_indices(candles, side, lookback, holding_bars)
        for decision_index in triggers:
            # Decision on the trigger candle's close; fill on the next candle.
            entry_index = decision_index + 1
            trade = _simulate_holding_trade(
                candles, entry_index, side, fill_rule, holding_bars
            )
            if trade is not None:
                trade["symbol"] = symbol
                trades.append(trade)

    record = _store_backtest(
        "rule",
        {
            "rule_definition": rule_definition,
            "symbols": symbols,
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "fill_rule": fill_rule,
        },
        trades,
    )
    return {"backtest_id": record["backtest_id"], "summary": record["stats"]}


@mcp.tool()
def get_stats(backtest_id: str) -> dict[str, Any]:
    """Return the summary statistics for a completed backtest.

    Args:
        backtest_id: The id returned by ``backtest_signals`` or
            ``backtest_rule``.

    Returns:
        ``{win_rate, total_trades, gross_pnl, avg_gain, avg_loss,
        max_drawdown, sharpe, by_tactical_quality, by_phase}``. The two
        breakdowns map each tactical-quality / phase value to the same
        seven core metrics over that subset of trades.

    Raises:
        KeyError: If ``backtest_id`` is unknown.
    """
    record = _backtests.get(backtest_id)
    if record is None:
        raise KeyError(f"unknown backtest_id: {backtest_id}")
    return record["stats"]


def main() -> None:
    """Entry point for running as a standalone MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
