from __future__ import annotations

from pathlib import Path

import pytest

from scripts.mcp import chart_renderer, spread_chart_server


def sample_candles(symbol_offset: float = 0.0, count: int = 5) -> list[dict]:
    candles: list[dict] = []
    for index in range(count):
        close = 100.0 + symbol_offset + index
        candles.append(
            {
                "open_time": index * 86_400_000,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000.0 + index,
                "close_time": index * 86_400_000 + 86_399_999,
            }
        )
    return candles


def test_spread_result_types_are_json_serializable_shape() -> None:
    result = spread_chart_server.calculate_spread_ohlcv(
        sample_candles(100),
        sample_candles(0),
    )

    assert set(result[0]) == {
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "base_close",
        "quote_close",
    }


@pytest.mark.parametrize(
    ("base", "quote", "expected"),
    [
        ("ETH", "BTC", ("ETH", "BTC", "ETHUSDT", "BTCUSDT")),
        ("ETHUSDT", "BTCUSDT", ("ETH", "BTC", "ETHUSDT", "BTCUSDT")),
        ("LINK/BTC", "SOL/USDT", ("LINK", "SOL", "LINKBTC", "SOLUSDT")),
    ],
)
def test_normalize_spread_pair(base: str, quote: str, expected: tuple[str, str, str, str]) -> None:
    pair = spread_chart_server.normalize_spread_pair(base, quote)

    assert (
        pair.base_symbol,
        pair.quote_symbol,
        pair.base_fetch_symbol,
        pair.quote_fetch_symbol,
    ) == expected


def test_normalize_spread_pair_rejects_identical_symbols() -> None:
    with pytest.raises(ValueError, match="must be different"):
        spread_chart_server.normalize_spread_pair("ETH", "ETHUSDT")


def test_calculate_spread_ohlcv_aligns_and_computes_ratios() -> None:
    base = sample_candles(100, count=3)
    quote = sample_candles(0, count=3)

    result = spread_chart_server.calculate_spread_ohlcv(base, quote)

    assert len(result) == 3
    assert result[0]["close"] == pytest.approx(200 / 100)
    assert result[1]["open"] == pytest.approx(result[0]["close"])
    assert result[1]["close"] == pytest.approx(201 / 101)
    assert result[1]["high"] == max(result[1]["open"], result[1]["close"])
    assert result[1]["low"] == min(result[1]["open"], result[1]["close"])
    assert result[1]["volume"] == base[1]["volume"]
    assert result[1]["base_close"] == base[1]["close"]
    assert result[1]["quote_close"] == quote[1]["close"]


def test_calculate_spread_ohlcv_drops_unmatched_timestamps() -> None:
    base = sample_candles(100, count=3)
    quote = sample_candles(0, count=3)
    quote.pop(1)

    result = spread_chart_server.calculate_spread_ohlcv(base, quote)

    assert [candle["open_time"] for candle in result] == [base[0]["open_time"], base[2]["open_time"]]


def test_calculate_spread_ohlcv_rejects_zero_quote_close() -> None:
    base = sample_candles(100, count=1)
    quote = sample_candles(0, count=1)
    quote[0]["close"] = 0

    with pytest.raises(ValueError, match="quote close must be positive"):
        spread_chart_server.calculate_spread_ohlcv(base, quote)


class FakeMarketDataClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        self.calls.append((symbol, timeframe, limit))
        if symbol.startswith("ETH"):
            return sample_candles(100, limit)
        if symbol.startswith("LINK"):
            return sample_candles(10, limit)
        if symbol.startswith("SOL"):
            return sample_candles(20, limit)
        return sample_candles(0, limit)


def test_get_spread_data_fetches_and_caches_identical_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(spread_chart_server, "market_data_client", fake)
    spread_chart_server._spread_cache.clear()

    first = spread_chart_server.get_spread_data("ETH", "BTC", "1d", 3)
    first["ohlcv"][0]["close"] = 999
    second = spread_chart_server.get_spread_data("ETHUSDT", "BTCUSDT", "1D", 3)

    assert fake.calls == [("ETHUSDT", "1d", 3), ("BTCUSDT", "1d", 3)]
    assert second["base_symbol"] == "ETH"
    assert second["quote_symbol"] == "BTC"
    assert second["candle_count"] == 3
    assert second["ohlcv"][0]["close"] != 999


def test_get_spread_wrapper_returns_spread_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(spread_chart_server, "market_data_client", fake)
    spread_chart_server._spread_cache.clear()

    result = spread_chart_server.get_spread("LINK", "BTC", "1d", 2)

    assert result["base_symbol"] == "LINK"
    assert result["quote_symbol"] == "BTC"
    assert result["candle_count"] == 2
    assert fake.calls == [("LINKUSDT", "1d", 2), ("BTCUSDT", "1d", 2)]


@pytest.mark.parametrize(("base", "quote"), [("ETH", "BTC"), ("LINK", "BTC"), ("SOL", "BTC")])
def test_default_spread_pairs_work_with_fake_client(
    base: str,
    quote: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(spread_chart_server, "market_data_client", fake)
    spread_chart_server._spread_cache.clear()

    result = spread_chart_server.get_spread(base, quote, "1d", 2)

    assert result["base_symbol"] == base
    assert result["quote_symbol"] == quote
    assert result["ohlcv"][-1]["close"] == pytest.approx(
        result["ohlcv"][-1]["base_close"] / result["ohlcv"][-1]["quote_close"]
    )


def test_render_spread_chart_creates_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(spread_chart_server, "market_data_client", fake)
    monkeypatch.setattr(chart_renderer, "RENDER_CACHE_DIR", tmp_path)
    spread_chart_server._spread_cache.clear()
    chart_renderer._render_cache.clear()

    result = spread_chart_server.render_spread_chart("ETH", "BTC", "1d", 80)

    assert result["title"] == "ETH/BTC spread 1d"
    assert result["base_symbol"] == "ETH"
    assert result["quote_symbol"] == "BTC"
    assert result["ratio_candle_count"] == 80
    assert result["width"] == 1200
    assert result["height"] == 600
    assert Path(result["path"]).exists()
