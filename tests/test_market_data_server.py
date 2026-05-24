from __future__ import annotations

from scripts.mcp import market_data_server


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        self.calls.append((symbol, timeframe, limit))
        return [
            {
                "open_time": 1,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 10.0,
                "close_time": 2,
                "quote_volume": 1000.0,
                "trades": 5,
            }
        ]

    def get_supported_symbols(self) -> list[dict]:
        return [
            {
                "symbol": "BTCUSDT",
                "base_asset": "BTC",
                "quote_asset": "USDT",
                "quote_volume": 1_000_000.0,
            }
        ]


def test_get_ohlcv_wrapper_uses_shared_client(monkeypatch) -> None:
    fake = FakeClient()
    monkeypatch.setattr(market_data_server, "client", fake)

    result = market_data_server.get_ohlcv("BTC", "1d", 200)

    assert fake.calls == [("BTC", "1d", 200)]
    assert result[0]["close"] == 105.0


def test_get_supported_symbols_wrapper_uses_shared_client(monkeypatch) -> None:
    fake = FakeClient()
    monkeypatch.setattr(market_data_server, "client", fake)

    assert market_data_server.get_supported_symbols() == [
        {
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "quote_volume": 1_000_000.0,
        }
    ]


def test_get_timeframes_wrapper_returns_minimum_set() -> None:
    assert market_data_server.get_timeframes() == ["1h", "4h", "1d", "1w"]
