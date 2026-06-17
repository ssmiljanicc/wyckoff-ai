from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from scripts.mcp import market_data_client
from scripts.mcp.market_data_client import (
    BinanceMarketDataClient,
    BinanceRateLimitError,
    BinanceUpstreamError,
    Candle,
    OHLCV_CACHE_SIZE,
    get_timeframes,
    normalize_symbol,
    normalize_timeframe,
    parse_kline,
)


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        params = kwargs.get("params")
        self.calls.append((url, params if isinstance(params, dict) else None))
        if not self.responses:
            raise AssertionError("No fake responses left")
        return self.responses.pop(0)


def response(status_code: int, payload: object, headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://data-api.binance.vision/test")
    return httpx.Response(status_code, json=payload, headers=headers, request=request)


def sample_kline(open_time: int = 1) -> list[object]:
    return [
        open_time,
        "100.0",
        "110.0",
        "90.0",
        "105.0",
        "123.45",
        open_time + 59_999,
        "12962.25",
        321,
        "1.0",
        "2.0",
        "0",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BTC", "BTCUSDT"),
        ("BTCUSDT", "BTCUSDT"),
        ("BTC/USDT", "BTCUSDT"),
        (" eth/usdt ", "ETHUSDT"),
        ("ETHBTC", "ETHBTC"),
    ],
)
def test_normalize_symbol(raw: str, expected: str) -> None:
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "BTC USDT", "BTC$USDT", "USDT"])
def test_normalize_symbol_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_symbol(raw)


def test_timeframes_are_supported_minimum_set() -> None:
    assert get_timeframes() == ["1h", "4h", "1d", "1w"]
    assert normalize_timeframe("1H") == "1h"
    with pytest.raises(ValueError):
        normalize_timeframe("15m")


def test_parse_kline_maps_binance_positional_row() -> None:
    assert parse_kline(sample_kline()) == {
        "open_time": 1,
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 123.45,
        "close_time": 60000,
        "quote_volume": 12962.25,
        "trades": 321,
    }


def test_get_ohlcv_fetches_and_caches_identical_request() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1), sample_kline(2)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    first = client.get_ohlcv("BTC", "1d", 2)
    second = client.get_ohlcv("BTC/USDT", "1d", 2)

    assert first == second
    assert len(first) == 2
    assert len(fake.calls) == 1
    assert fake.calls[0][1] == {"symbol": "BTCUSDT", "interval": "1d", "limit": 2}


def test_get_ohlcv_passes_end_time_to_binance() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("BTC", "1d", 1, end_time=1_554_076_800_000)

    assert fake.calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 1,
        "endTime": 1_554_076_800_000,
    }


def test_get_ohlcv_accepts_iso_end_time() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("BTC", "1d", 1, end_time="2019-04-01")

    assert fake.calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 1,
        "endTime": 1_554_076_800_000,
    }


def test_get_ohlcv_accepts_offset_iso_end_time() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("BTC", "1d", 1, end_time="2019-04-01T02:00:00+02:00")

    assert fake.calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 1,
        "endTime": 1_554_076_800_000,
    }


def test_get_ohlcv_accepts_datetime_end_time() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv(
        "BTC",
        "1d",
        1,
        end_time=datetime(2019, 4, 1, tzinfo=timezone.utc),
    )

    assert fake.calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 1,
        "endTime": 1_554_076_800_000,
    }


def test_get_ohlcv_treats_naive_datetime_end_time_as_utc() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("BTC", "1d", 1, end_time=datetime(2019, 4, 1))

    assert fake.calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 1,
        "endTime": 1_554_076_800_000,
    }


def test_get_ohlcv_without_end_time_omits_param() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("BTC", "1d", 1, end_time=None)

    assert fake.calls[0][1] == {"symbol": "BTCUSDT", "interval": "1d", "limit": 1}


def test_end_time_cache_does_not_collide() -> None:
    fake = FakeHttpClient(
        [
            response(200, [sample_kline(1)]),
            response(200, [sample_kline(2)]),
        ]
    )
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    first = client.get_ohlcv("BTC", "1d", 1, end_time=1_554_076_800_000)
    second = client.get_ohlcv("BTC", "1d", 1, end_time=1_554_163_200_000)
    cached_first = client.get_ohlcv("BTC", "1d", 1, end_time=1_554_076_800_000)

    assert first == cached_first
    assert first != second
    assert len(fake.calls) == 2


def test_get_ohlcv_reuses_cache_for_equivalent_end_time_representations() -> None:
    fake = FakeHttpClient([response(200, [sample_kline(1)])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    first = client.get_ohlcv("BTC", "1d", 1, end_time=1_554_076_800_000)
    iso_cached = client.get_ohlcv("BTC", "1d", 1, end_time="2019-04-01T02:00:00+02:00")
    datetime_cached = client.get_ohlcv(
        "BTC",
        "1d",
        1,
        end_time=datetime(2019, 4, 1, tzinfo=timezone.utc),
    )

    assert first == iso_cached == datetime_cached
    assert len(fake.calls) == 1


def test_get_ohlcv_rejects_invalid_end_time() -> None:
    client = BinanceMarketDataClient(http_client=FakeHttpClient([]), rate_limit_delay=0)

    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time=-1)
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time=True)
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time="1970-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time="1969-12-31T23:59:59Z")
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time=datetime(1969, 12, 31, 23, 59, 59))
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time="not-a-date")
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1, end_time=1.5)  # type: ignore[arg-type]


def test_get_ohlcv_empty_cutoff_response_includes_request_context() -> None:
    fake = FakeHttpClient([response(200, [])])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    with pytest.raises(BinanceUpstreamError) as exc_info:
        client.get_ohlcv("BTC", "1d", 1, end_time="2019-04-01")

    message = str(exc_info.value)
    assert "BTCUSDT 1d" in message
    assert "limit=1" in message
    assert "end_time=1554076800000" in message


def test_ohlcv_cache_evicts_least_recently_used_entry() -> None:
    responses = [
        response(200, [sample_kline(index)])
        for index in range(OHLCV_CACHE_SIZE + 2)
    ]
    fake = FakeHttpClient(responses)
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    client.get_ohlcv("ASSET0", "1d", 1)
    for index in range(1, OHLCV_CACHE_SIZE + 1):
        client.get_ohlcv(f"ASSET{index}", "1d", 1)
    client.get_ohlcv("ASSET0", "1d", 1)

    assert len(fake.calls) == OHLCV_CACHE_SIZE + 2


def test_rate_limit_delay_between_real_upstream_requests(monkeypatch) -> None:
    fake = FakeHttpClient(
        [
            response(200, [sample_kline(1)]),
            response(200, [sample_kline(2)]),
        ]
    )
    monotonic_values = iter([100.0, 100.0, 100.01, 100.06])
    sleeps: list[float] = []
    monkeypatch.setattr(market_data_client.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(market_data_client.time, "sleep", sleeps.append)
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0.05)

    client.get_ohlcv("BTC", "1d", 1)
    client.get_ohlcv("ETH", "1d", 1)

    assert sleeps == pytest.approx([0.04])


def test_get_ohlcv_rejects_invalid_limit() -> None:
    client = BinanceMarketDataClient(http_client=FakeHttpClient([]), rate_limit_delay=0)
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 0)
    with pytest.raises(ValueError):
        client.get_ohlcv("BTC", "1d", 1001)


@pytest.mark.parametrize("status_code", [429, 451])
def test_get_ohlcv_surfaces_rate_limit_and_legal_errors(status_code: int) -> None:
    fake = FakeHttpClient([response(status_code, {"msg": "blocked"}, {"Retry-After": "2"})])
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    with pytest.raises(BinanceRateLimitError) as exc_info:
        client.get_ohlcv("BTC", "1h", 1)

    assert f"HTTP {status_code}" in str(exc_info.value)
    assert "Retry-After=2" in str(exc_info.value)


def test_get_supported_symbols_returns_top_50_usdt_spot_symbols_by_quote_volume() -> None:
    exchange_symbols = [
        {
            "symbol": f"ASSET{i}USDT",
            "baseAsset": f"ASSET{i}",
            "quoteAsset": "USDT",
            "status": "TRADING",
            "isSpotTradingAllowed": True,
        }
        for i in range(60)
    ]
    exchange_symbols.extend(
        [
            {
                "symbol": "BTCDOWNUSDT",
                "baseAsset": "BTCDOWN",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
            },
            {
                "symbol": "ETHBTC",
                "baseAsset": "ETH",
                "quoteAsset": "BTC",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
            },
            {
                "symbol": "OLDUSDT",
                "baseAsset": "OLD",
                "quoteAsset": "USDT",
                "status": "BREAK",
                "isSpotTradingAllowed": True,
            },
        ]
    )
    tickers = [
        {"symbol": f"ASSET{i}USDT", "quoteVolume": str(i)}
        for i in range(60)
    ]
    tickers.extend(
        [
            {"symbol": "BTCDOWNUSDT", "quoteVolume": "999999"},
            {"symbol": "ETHBTC", "quoteVolume": "999999"},
            {"symbol": "OLDUSDT", "quoteVolume": "999999"},
        ]
    )
    fake = FakeHttpClient(
        [
            response(200, {"symbols": exchange_symbols}),
            response(200, tickers),
        ]
    )
    client = BinanceMarketDataClient(http_client=fake, rate_limit_delay=0)

    symbols = client.get_supported_symbols()
    cached_symbols = client.get_supported_symbols()

    assert len(symbols) == 50
    assert symbols == cached_symbols
    assert len(fake.calls) == 2
    assert symbols[0]["symbol"] == "ASSET59USDT"
    assert symbols[-1]["symbol"] == "ASSET10USDT"
    assert all(item["quote_asset"] == "USDT" for item in symbols)
    assert "BTCDOWNUSDT" not in {item["symbol"] for item in symbols}


def test_get_supported_symbols_rejects_invalid_limit() -> None:
    client = BinanceMarketDataClient(http_client=FakeHttpClient([]), rate_limit_delay=0)
    with pytest.raises(ValueError):
        client.get_supported_symbols(0)


def test_candle_type_is_json_serializable_shape() -> None:
    candle: Candle = parse_kline(sample_kline())
    assert set(candle) == {
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
    }
