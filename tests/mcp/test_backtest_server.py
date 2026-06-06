"""Tests for the backtest runner MCP server.

Covers the issue #24 invariants — determinism (identical input → identical
stats), walk-forward execution (no future leakage) — plus the three
refinements: signal trades exit on their own stop/target, stats carry a
per-tactical-quality / per-phase breakdown, and Sharpe is computed over
daily returns. Dependencies (market data client + signal store) are
duck-typed fakes so the suite is offline and deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.mcp import backtest_server


# --------------------------------------------------------------------------
# Synthetic fixtures.
# --------------------------------------------------------------------------


def _ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _candle(iso, o, h, l, c, v=1000.0):
    return {
        "open_time": _ms(iso),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "close_time": _ms(iso) + 1,
        "quote_volume": v * c,
        "trades": 1,
    }


# A steadily rising daily series: a long generally reaches its target.
_RISING = [
    _candle("2024-01-01T00:00:00Z", 100.0, 105.0, 99.0, 100.0),
    _candle("2024-01-02T00:00:00Z", 200.0, 206.0, 101.0, 101.0),  # signal day
    _candle("2024-01-03T00:00:00Z", 110.0, 120.0, 109.0, 115.0),  # entry day
    _candle("2024-01-04T00:00:00Z", 116.0, 130.0, 115.0, 125.0),
    _candle("2024-01-05T00:00:00Z", 126.0, 140.0, 125.0, 135.0),
    _candle("2024-01-06T00:00:00Z", 136.0, 150.0, 135.0, 145.0),
    _candle("2024-01-07T00:00:00Z", 146.0, 160.0, 145.0, 155.0),
]

# A steadily falling daily series.
_FALLING = [
    _candle("2024-01-01T00:00:00Z", 100.0, 101.0, 90.0, 95.0),
    _candle("2024-01-02T00:00:00Z", 95.0, 96.0, 80.0, 90.0),  # signal day
    _candle("2024-01-03T00:00:00Z", 90.0, 91.0, 70.0, 75.0),  # entry day
    _candle("2024-01-04T00:00:00Z", 75.0, 76.0, 60.0, 65.0),
    _candle("2024-01-05T00:00:00Z", 65.0, 66.0, 50.0, 55.0),
]


class _FakeMarketClient:
    """Duck-typed stand-in for BinanceMarketDataClient."""

    def __init__(self, candles):
        self._candles = candles

    def get_ohlcv(self, symbol, timeframe, limit):
        return list(self._candles)


class _FakeSignalStore:
    """Duck-typed stand-in for SignalStore with the list_signals shape we use."""

    def __init__(self, signals):
        self._signals = signals

    def list_signals(self, *, symbol=None, start=None, end=None, signal_type=None):
        out = list(self._signals)
        if symbol is not None:
            out = [s for s in out if s.get("symbol") == symbol]
        if signal_type is not None:
            out = [s for s in out if s.get("signal_type") == signal_type]
        if start is not None:
            out = [s for s in out if s.get("logged_at", "") >= start]
        if end is not None:
            out = [s for s in out if s.get("logged_at", "") <= end]
        out.sort(key=lambda s: s.get("logged_at", ""))
        return out


def _signal(
    signal_id,
    symbol,
    signal_type,
    logged_at,
    *,
    invalidation=None,
    target_zone=None,
    tactical_quality=None,
    phase=None,
    timeframe="1d",
):
    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "signal_type": signal_type,
        "logged_at": logged_at,
        "timeframe": timeframe,
        "invalidation": invalidation,
        "target_zone": target_zone or [],
        "tactical_quality": tactical_quality,
        "phase_identified": phase,
    }


@pytest.fixture
def reset_state():
    """Reset module globals before and after each test."""
    backtest_server._market_client = None
    backtest_server._signal_store = None
    backtest_server._backtests = {}
    yield
    backtest_server._market_client = None
    backtest_server._signal_store = None
    backtest_server._backtests = {}


# --------------------------------------------------------------------------
# backtest_signals: stop/target exit from the logged signal.
# --------------------------------------------------------------------------


def test_backtest_signals_hits_target(reset_state):
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
                invalidation=105.0, target_zone=[130.0],
            )
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_RISING)

    result = backtest_server.backtest_signals(
        signal_filter={"symbol": "BTCUSDT"},
        start_date="2024-01-01T00:00:00Z",
        end_date="2024-01-31T00:00:00Z",
        fill_rule="next_bar_open",
    )

    summary = result["summary"]
    assert summary["total_trades"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["gross_pnl"] > 0

    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]
    # Enter at next-bar open (110), exit at the target (130) once touched.
    assert trade["entry_price"] == 110.0
    assert trade["exit_price"] == 130.0
    assert trade["outcome"] == "hit_tp"

    stats = backtest_server.get_stats(result["backtest_id"])
    assert stats == summary


def test_backtest_signals_hits_stop(reset_state):
    # Long signal on a falling series → stop is hit, a losing trade.
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
                invalidation=85.0, target_zone=[200.0],
            )
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_FALLING)

    result = backtest_server.backtest_signals()
    summary = result["summary"]
    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]

    # Enter at 90 (entry-day open), stopped out at 85.
    assert trade["entry_price"] == 90.0
    assert trade["exit_price"] == 85.0
    assert trade["outcome"] == "hit_sl"
    assert summary["win_rate"] == 0.0
    assert summary["gross_pnl"] < 0


def test_backtest_signals_short_hits_target(reset_state):
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "ETHUSDT", "short_utad", "2024-01-02T12:00:00Z",
                invalidation=96.0, target_zone=[70.0],
            )
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_FALLING)

    result = backtest_server.backtest_signals()
    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]
    # Short enters at 90, target 70 reached.
    assert trade["entry_price"] == 90.0
    assert trade["exit_price"] == 70.0
    assert trade["outcome"] == "hit_tp"
    assert result["summary"]["win_rate"] == 1.0


def test_max_holding_bars_timeout(reset_state):
    # Target never reached within the timeout → exit at the close of the
    # candle `max_holding_bars` after entry.
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
                invalidation=50.0, target_zone=[9999.0],
            )
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_RISING)

    result = backtest_server.backtest_signals(max_holding_bars=1)
    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]
    # Entry day = 2024-01-03 (open 110); one bar later = 2024-01-04 close 125.
    assert trade["entry_price"] == 110.0
    assert trade["exit_price"] == 125.0
    assert trade["outcome"] == "timeout"


# --------------------------------------------------------------------------
# Walk-forward: no future leakage.
# --------------------------------------------------------------------------


def test_walk_forward_entry_is_after_signal(reset_state):
    """Entry must fill on the first candle strictly after the signal.

    The signal lands during 2024-01-02 (which opens at 200); the prior
    candle opens at 100. The entry must use neither — only the next
    candle's open (110).
    """
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
                invalidation=105.0, target_zone=[130.0],
            )
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_RISING)

    result = backtest_server.backtest_signals()
    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]

    assert trade["entry_price"] == 110.0
    assert trade["entry_time"] == _ms("2024-01-03T00:00:00Z")
    assert trade["exit_time"] > trade["entry_time"]


def test_no_trade_when_signal_after_last_candle(reset_state):
    """A signal with no candle after it produces no trade (no future to fill)."""
    backtest_server._signal_store = _FakeSignalStore(
        [_signal("s1", "BTCUSDT", "long_spring", "2024-12-31T00:00:00Z")]
    )
    backtest_server._market_client = _FakeMarketClient(_RISING)

    result = backtest_server.backtest_signals()
    assert result["summary"]["total_trades"] == 0


# --------------------------------------------------------------------------
# Per-tactical-quality / per-phase breakdown.
# --------------------------------------------------------------------------


def test_breakdown_by_quality_and_phase(reset_state):
    backtest_server._signal_store = _FakeSignalStore(
        [
            _signal(
                "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
                invalidation=105.0, target_zone=[130.0],
                tactical_quality="phase_c_aggressive", phase="C",
            ),
            _signal(
                "s2", "BTCUSDT", "long_sos", "2024-01-03T12:00:00Z",
                invalidation=110.0, target_zone=[150.0],
                tactical_quality="phase_d_confirmation", phase="D",
            ),
        ]
    )
    backtest_server._market_client = _FakeMarketClient(_RISING)

    summary = backtest_server.backtest_signals()["summary"]

    assert summary["total_trades"] == 2

    by_q = summary["by_tactical_quality"]
    assert set(by_q) == {"phase_c_aggressive", "phase_d_confirmation"}
    assert by_q["phase_c_aggressive"]["total_trades"] == 1
    assert by_q["phase_d_confirmation"]["total_trades"] == 1
    assert sum(g["total_trades"] for g in by_q.values()) == summary["total_trades"]

    by_phase = summary["by_phase"]
    assert set(by_phase) == {"C", "D"}
    assert by_phase["C"]["total_trades"] == 1
    assert by_phase["D"]["total_trades"] == 1


# --------------------------------------------------------------------------
# backtest_rule with synthetic OHLCV (fixed-holding exit).
# --------------------------------------------------------------------------

_BREAKOUT = [
    _candle("2024-01-01T00:00:00Z", 100.0, 105.0, 99.0, 100.0),
    _candle("2024-01-02T00:00:00Z", 101.0, 106.0, 100.0, 101.0),
    _candle("2024-01-03T00:00:00Z", 102.0, 107.0, 101.0, 200.0),  # breakout close
    _candle("2024-01-04T00:00:00Z", 210.0, 230.0, 205.0, 220.0),  # entry day
    _candle("2024-01-05T00:00:00Z", 221.0, 260.0, 220.0, 250.0),  # exit day
    _candle("2024-01-06T00:00:00Z", 251.0, 270.0, 250.0, 260.0),
]


def test_backtest_rule_breakout(reset_state):
    backtest_server._market_client = _FakeMarketClient(_BREAKOUT)

    result = backtest_server.backtest_rule(
        rule_definition={
            "side": "long",
            "entry": "breakout",
            "lookback": 2,
            "holding_bars": 1,
        },
        symbols=["BTCUSDT"],
        timeframe="1d",
        start="2024-01-01T00:00:00Z",
        end="2024-01-31T00:00:00Z",
        fill_rule="next_bar_open",
    )

    trades = backtest_server._backtests[result["backtest_id"]]["trades"]
    assert len(trades) == 1
    trade = trades[0]
    # Decision on the breakout close (idx 2), fill on next open (210), exit
    # one candle later at close (250).
    assert trade["entry_price"] == 210.0
    assert trade["exit_price"] == 250.0
    assert result["summary"]["win_rate"] == 1.0
    # Rule trades carry no Wyckoff metadata → empty breakdowns.
    assert result["summary"]["by_tactical_quality"] == {}
    assert result["summary"]["by_phase"] == {}


def test_backtest_rule_slippage_raises_entry(reset_state):
    backtest_server._market_client = _FakeMarketClient(_BREAKOUT)

    result = backtest_server.backtest_rule(
        rule_definition={"side": "long", "lookback": 2, "holding_bars": 1},
        symbols=["BTCUSDT"],
        timeframe="1d",
        fill_rule="fixed_slippage_0.1pct",
    )
    trade = backtest_server._backtests[result["backtest_id"]]["trades"][0]
    # Long pays 0.1% more than the clean 210 open.
    assert trade["entry_price"] == pytest.approx(210.0 * 1.001)


def test_backtest_rule_rejects_unknown_entry(reset_state):
    backtest_server._market_client = _FakeMarketClient(_BREAKOUT)
    with pytest.raises(ValueError):
        backtest_server.backtest_rule(
            rule_definition={"entry": "rsi_cross"},
            symbols=["BTCUSDT"],
            timeframe="1d",
        )


def test_invalid_fill_rule_raises(reset_state):
    backtest_server._signal_store = _FakeSignalStore([])
    backtest_server._market_client = _FakeMarketClient(_RISING)
    with pytest.raises(ValueError):
        backtest_server.backtest_signals(fill_rule="market_order")


def test_max_holding_bars_validation_raises(reset_state):
    backtest_server._signal_store = _FakeSignalStore([])
    backtest_server._market_client = _FakeMarketClient(_RISING)
    with pytest.raises(ValueError):
        backtest_server.backtest_signals(max_holding_bars=0)


# --------------------------------------------------------------------------
# Sharpe over daily returns.
# --------------------------------------------------------------------------


def test_sharpe_daily_buckets_by_exit_day():
    # Two trades that exit on the same UTC day collapse into one daily
    # return (their sum), so the series here is identical to two distinct
    # daily returns of 0.10 and (-0.05 + 0.15).
    combined = backtest_server._sharpe_daily(
        [
            {"exit_time": _ms("2024-01-01T00:00:00Z"), "pnl_pct": 0.10},
            {"exit_time": _ms("2024-01-02T00:00:00Z"), "pnl_pct": -0.05},
            {"exit_time": _ms("2024-01-02T06:00:00Z"), "pnl_pct": 0.15},
        ]
    )
    expected = backtest_server._sharpe_daily(
        [
            {"exit_time": _ms("2024-01-01T00:00:00Z"), "pnl_pct": 0.10},
            {"exit_time": _ms("2024-01-02T00:00:00Z"), "pnl_pct": -0.05 + 0.15},
        ]
    )
    assert combined == pytest.approx(expected)


def test_sharpe_daily_two_distinct_days():
    trades = [
        {"exit_time": _ms("2024-01-01T00:00:00Z"), "pnl_pct": 0.10},
        {"exit_time": _ms("2024-01-02T00:00:00Z"), "pnl_pct": 0.20},
    ]
    mean = 0.15
    std = (((0.10 - mean) ** 2 + (0.20 - mean) ** 2) / 1) ** 0.5
    assert backtest_server._sharpe_daily(trades) == pytest.approx(mean / std)
    # A single active day has no dispersion → Sharpe 0.
    assert backtest_server._sharpe_daily(trades[:1]) == 0.0


# --------------------------------------------------------------------------
# Determinism: identical input → identical stats across runs.
# --------------------------------------------------------------------------


def test_determinism_signals(reset_state):
    signals = [
        _signal(
            "s1", "BTCUSDT", "long_spring", "2024-01-02T12:00:00Z",
            invalidation=105.0, target_zone=[130.0],
            tactical_quality="phase_c_aggressive", phase="C",
        ),
        _signal(
            "s2", "BTCUSDT", "long_sos", "2024-01-03T12:00:00Z",
            invalidation=110.0, target_zone=[150.0],
            tactical_quality="phase_d_confirmation", phase="D",
        ),
    ]

    runs = []
    for _ in range(3):
        backtest_server._signal_store = _FakeSignalStore(signals)
        backtest_server._market_client = _FakeMarketClient(_RISING)
        result = backtest_server.backtest_signals()
        runs.append(backtest_server.get_stats(result["backtest_id"]))

    assert runs[0] == runs[1] == runs[2]
    assert runs[0]["total_trades"] == 2


def test_determinism_rule(reset_state):
    runs = []
    for _ in range(3):
        backtest_server._market_client = _FakeMarketClient(_BREAKOUT)
        result = backtest_server.backtest_rule(
            rule_definition={"side": "long", "lookback": 2, "holding_bars": 1},
            symbols=["BTCUSDT"],
            timeframe="1d",
        )
        runs.append(backtest_server.get_stats(result["backtest_id"]))

    assert runs[0] == runs[1] == runs[2]


def test_get_stats_unknown_id_raises(reset_state):
    with pytest.raises(KeyError):
        backtest_server.get_stats("does-not-exist")
