from __future__ import annotations

import pytest

from scripts.mcp import scanner_server


DAY_MS = 86_400_000


def make_candles(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    start_time: int = 0,
    step: int = DAY_MS,
) -> list[dict]:
    """Build synthetic OHLCV candles from a list of closes."""
    n = len(closes)
    highs = highs if highs is not None else [c * 1.01 for c in closes]
    lows = lows if lows is not None else [c * 0.99 for c in closes]
    volumes = volumes if volumes is not None else [1_000.0] * n
    candles: list[dict] = []
    for i in range(n):
        open_time = start_time + i * step
        candles.append(
            {
                "open_time": open_time,
                "open": closes[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i],
                "close_time": open_time + step - 1,
                "quote_volume": volumes[i] * closes[i],
                "trades": 100,
            }
        )
    return candles


class FakeClient:
    """Stand-in for BinanceMarketDataClient keyed by the raw symbol string."""

    def __init__(self, data: dict[str, list[dict]]) -> None:
        self.data = data
        self.calls: list[tuple[str, str, int]] = []

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        self.calls.append((symbol, timeframe, limit))
        return list(self.data[symbol])


# ---------------------------------------------------------------------------
# Rule 1: range_duration_gt_4w
# ---------------------------------------------------------------------------

def test_range_duration_matches_tight_range() -> None:
    # 28 daily bars (4 weeks) oscillating within ±2% of midpoint 100.
    closes = [100 + (2 if i % 2 else -2) for i in range(28)]
    result = scanner_server._evaluate_range_duration(make_candles(closes), "1d")

    assert result["match"] is True
    assert "within ±5%" in result["reason"]
    assert result["score"] > 0


def test_range_duration_rejects_breakout() -> None:
    closes = [100.0] * 27 + [125.0]
    result = scanner_server._evaluate_range_duration(make_candles(closes), "1d")

    assert result["match"] is False
    assert "break" in result["reason"]


def test_range_duration_insufficient_data() -> None:
    result = scanner_server._evaluate_range_duration(make_candles([100.0] * 10), "1d")

    assert result["match"] is False
    assert "insufficient data" in result["reason"]


# ---------------------------------------------------------------------------
# Rule 2: volume_declining
# ---------------------------------------------------------------------------

def test_volume_declining_matches_falling_ma() -> None:
    closes = [100.0] * 20
    volumes = [float(2_000 - 90 * i) for i in range(20)]  # strictly declining
    result = scanner_server._evaluate_volume_declining(
        make_candles(closes, volumes=volumes), "1d"
    )

    assert result["match"] is True
    assert "declining" in result["reason"]
    assert result["score"] > 0


def test_volume_declining_rejects_rising_ma() -> None:
    closes = [100.0] * 20
    volumes = [float(100 + 90 * i) for i in range(20)]  # rising
    result = scanner_server._evaluate_volume_declining(
        make_candles(closes, volumes=volumes), "1d"
    )

    assert result["match"] is False
    assert "rising/flat" in result["reason"]


# ---------------------------------------------------------------------------
# Rule 3: range_after_drop
# ---------------------------------------------------------------------------

def test_range_after_drop_matches_large_drawdown() -> None:
    # 56 daily bars (8 weeks): peak at 100, trough 25% lower.
    highs = [100.0] * 30 + [90.0] * 26
    lows = [99.0] * 30 + [float(95 - i) for i in range(26)]  # dips to 70 → 30% drawdown
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    result = scanner_server._evaluate_range_after_drop(
        make_candles(closes, highs=highs, lows=lows), "1d"
    )

    assert result["match"] is True
    assert "drawdown" in result["reason"]
    assert result["score"] >= scanner_server.DROP_PCT


def test_range_after_drop_rejects_shallow_dip() -> None:
    highs = [100.0] * 56
    lows = [95.0] * 56  # only 5% drawdown
    closes = [97.0] * 56
    result = scanner_server._evaluate_range_after_drop(
        make_candles(closes, highs=highs, lows=lows), "1d"
    )

    assert result["match"] is False


# ---------------------------------------------------------------------------
# Rule 4: range_after_rally
# ---------------------------------------------------------------------------

def test_range_after_rally_matches_large_rally() -> None:
    lows = [100.0] * 30 + [110.0] * 26
    highs = [101.0] * 30 + [float(110 + i) for i in range(26)]  # rises to 135 → 35% rally
    closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    result = scanner_server._evaluate_range_after_rally(
        make_candles(closes, highs=highs, lows=lows), "1d"
    )

    assert result["match"] is True
    assert "rally" in result["reason"]
    assert result["score"] >= scanner_server.RALLY_PCT


def test_range_after_rally_rejects_small_move() -> None:
    lows = [100.0] * 56
    highs = [110.0] * 56  # only 10% rally
    closes = [105.0] * 56
    result = scanner_server._evaluate_range_after_rally(
        make_candles(closes, highs=highs, lows=lows), "1d"
    )

    assert result["match"] is False


# ---------------------------------------------------------------------------
# Rule 5: relative_strength_top_decile
# ---------------------------------------------------------------------------

def test_relative_strength_metric_positive_when_outperforming_btc() -> None:
    # 30 aligned bars; symbol grows, BTC flat → positive RS.
    sym = make_candles([100.0 + i for i in range(30)])
    btc = make_candles([100.0] * 30)

    metric = scanner_server.relative_strength_metric(sym, btc, "1d")

    assert metric is not None
    assert metric > 0


def test_relative_strength_metric_none_without_overlap() -> None:
    sym = make_candles([100.0] * 30, start_time=0)
    btc = make_candles([100.0] * 30, start_time=999 * DAY_MS)  # disjoint open_times

    assert scanner_server.relative_strength_metric(sym, btc, "1d") is None


def test_relative_strength_top_decile_selects_leader() -> None:
    metrics: dict[str, float | None] = {
        "A": 0.50,  # clear leader → top decile
        "B": 0.05,
        "C": 0.04,
        "D": 0.03,
        "E": 0.02,
        "F": 0.01,
        "G": 0.00,
        "H": -0.01,
        "I": -0.02,
        "J": -0.03,
    }
    results = scanner_server._evaluate_relative_strength(metrics)

    assert results["A"]["match"] is True
    assert results["J"]["match"] is False
    assert "top decile" in results["A"]["reason"]


def test_relative_strength_handles_missing_metric() -> None:
    results = scanner_server._evaluate_relative_strength({"A": 0.5, "B": None})

    assert results["A"]["match"] is True
    assert results["B"]["match"] is False
    assert "insufficient" in results["B"]["reason"]


# ---------------------------------------------------------------------------
# scan_universe: sorting + filtering + concurrency
# ---------------------------------------------------------------------------

def test_scan_universe_returns_sorted_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    # WEAK has a shallow drop (no match); STRONG and MID both match with
    # different drawdowns so we can assert ordering.
    def drop_candles(trough: float) -> list[dict]:
        highs = [100.0] * 30 + [95.0] * 26
        lows = [99.0] * 30 + [trough] * 26
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
        return make_candles(closes, highs=highs, lows=lows)

    data = {
        "STRONG": drop_candles(60.0),   # 40% drawdown
        "MID": drop_candles(75.0),      # 25% drawdown
        "WEAK": drop_candles(95.0),     # 5% drawdown → no match
    }
    fake = FakeClient(data)
    monkeypatch.setattr(scanner_server, "market_data_client", fake)

    results = scanner_server.scan_universe(
        ["STRONG", "MID", "WEAK"], "1d", "range_after_drop", max_results=5
    )

    assert [r["symbol"] for r in results] == ["STRONG", "MID"]
    assert results[0]["score"] > results[1]["score"]
    assert all(r["match"] for r in results)


def test_scan_universe_respects_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    def drop_candles(trough: float) -> list[dict]:
        highs = [100.0] * 30 + [95.0] * 26
        lows = [99.0] * 30 + [trough] * 26
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
        return make_candles(closes, highs=highs, lows=lows)

    data = {sym: drop_candles(60.0) for sym in ("A", "B", "C", "D")}
    fake = FakeClient(data)
    monkeypatch.setattr(scanner_server, "market_data_client", fake)

    results = scanner_server.scan_universe(
        ["A", "B", "C", "D"], "1d", "range_after_drop", max_results=2
    )

    assert len(results) == 2


def test_scan_universe_rejects_unknown_rule() -> None:
    with pytest.raises(scanner_server.UnknownRuleError):
        scanner_server.scan_universe(["BTC"], "1d", "no_such_rule")


def test_scan_universe_rejects_empty_symbols() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        scanner_server.scan_universe([], "1d", "volume_declining")


# ---------------------------------------------------------------------------
# get_universe
# ---------------------------------------------------------------------------

def test_get_universe_returns_expected_symbols() -> None:
    assert scanner_server.get_universe("top20_alts")[:3] == ["ETH", "BNB", "SOL"]
    assert len(scanner_server.get_universe("top20_alts")) == 20
    assert "UNI" in scanner_server.get_universe("defi_index")
    assert "GALA" in scanner_server.get_universe("low_caps")


def test_get_universe_returns_copy() -> None:
    first = scanner_server.get_universe("defi_index")
    first.append("MUTATED")
    assert "MUTATED" not in scanner_server.get_universe("defi_index")


def test_get_universe_unknown_raises() -> None:
    with pytest.raises(scanner_server.UnknownUniverseError):
        scanner_server.get_universe("does_not_exist")


# ---------------------------------------------------------------------------
# evaluate_rule (single symbol)
# ---------------------------------------------------------------------------

def test_evaluate_rule_single_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    closes = [100.0] * 20
    volumes = [float(2_000 - 90 * i) for i in range(20)]
    fake = FakeClient({"ETH": make_candles(closes, volumes=volumes)})
    monkeypatch.setattr(scanner_server, "market_data_client", fake)

    result = scanner_server.evaluate_rule("ETH", "1d", "volume_declining")

    assert result["match"] is True
    assert "declining" in result["reason"]
