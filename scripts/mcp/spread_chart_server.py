"""MCP server for computing and rendering crypto spread charts."""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only without the mcp extra.
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None:
            self.name = name

        def tool(self) -> Any:
            def decorator(func: Any) -> Any:
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError("FastMCP requires the mcp extra: uv run --extra mcp ...")

from scripts.mcp.chart_renderer import RenderedChart, render_chart_image
from scripts.mcp.market_data_client import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    SUPPORTED_QUOTE_ASSETS,
    BinanceMarketDataClient,
    normalize_symbol,
    normalize_timeframe,
)


DEFAULT_SPREAD_LIMIT = DEFAULT_LIMIT
SPREAD_CACHE_SIZE = 128


class SpreadCandle(TypedDict):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: NotRequired[int]
    base_close: float
    quote_close: float


class SpreadResult(TypedDict):
    base_symbol: str
    quote_symbol: str
    timeframe: str
    limit: int
    candle_count: int
    ohlcv: list[SpreadCandle]


class RenderedSpreadChart(RenderedChart):
    base_symbol: str
    quote_symbol: str
    timeframe: str
    ratio_candle_count: int


@dataclass(frozen=True)
class _SpreadPair:
    base_symbol: str
    quote_symbol: str
    base_fetch_symbol: str
    quote_fetch_symbol: str


@dataclass(frozen=True)
class _SpreadCacheKey:
    base_fetch_symbol: str
    quote_fetch_symbol: str
    timeframe: str
    limit: int


mcp = FastMCP("wyckoff-spread-chart")
market_data_client = BinanceMarketDataClient()
_spread_cache: OrderedDict[_SpreadCacheKey, SpreadResult] = OrderedDict()


def normalize_spread_pair(base_symbol: str, quote_symbol: str) -> _SpreadPair:
    base_fetch_symbol = normalize_symbol(base_symbol)
    quote_fetch_symbol = normalize_symbol(quote_symbol)
    base_display = _display_symbol(base_fetch_symbol)
    quote_display = _display_symbol(quote_fetch_symbol)
    if base_display == quote_display:
        raise ValueError("base_symbol and quote_symbol must be different")
    return _SpreadPair(
        base_symbol=base_display,
        quote_symbol=quote_display,
        base_fetch_symbol=base_fetch_symbol,
        quote_fetch_symbol=quote_fetch_symbol,
    )


def calculate_spread_ohlcv(
    base_candles: list[dict[str, Any]],
    quote_candles: list[dict[str, Any]],
) -> list[SpreadCandle]:
    if not base_candles:
        raise ValueError("base_candles must be non-empty")
    if not quote_candles:
        raise ValueError("quote_candles must be non-empty")

    quote_by_open_time = {
        _coerce_int(candle["open_time"], "quote open_time"): candle
        for candle in quote_candles
    }
    spread_candles: list[SpreadCandle] = []
    previous_close_ratio: float | None = None
    previous_open_time: int | None = None

    for base_candle in base_candles:
        open_time = _coerce_int(base_candle["open_time"], "base open_time")
        if previous_open_time is not None and open_time <= previous_open_time:
            raise ValueError("base candle open_time values must be strictly increasing")
        previous_open_time = open_time

        quote_candle = quote_by_open_time.get(open_time)
        if quote_candle is None:
            continue

        base_close = _coerce_positive_float(base_candle["close"], "base close")
        quote_close = _coerce_positive_float(quote_candle["close"], "quote close")
        close_ratio = base_close / quote_close
        open_ratio = previous_close_ratio if previous_close_ratio is not None else close_ratio
        high_ratio = max(open_ratio, close_ratio)
        low_ratio = min(open_ratio, close_ratio)

        spread_candle: SpreadCandle = {
            "open_time": open_time,
            "open": open_ratio,
            "high": high_ratio,
            "low": low_ratio,
            "close": close_ratio,
            "volume": _coerce_non_negative_float(base_candle["volume"], "base volume"),
            "base_close": base_close,
            "quote_close": quote_close,
        }
        if "close_time" in base_candle:
            spread_candle["close_time"] = _coerce_int(base_candle["close_time"], "base close_time")
        spread_candles.append(spread_candle)
        previous_close_ratio = close_ratio

    if not spread_candles:
        raise ValueError("No overlapping candles found for spread calculation")
    return spread_candles


def get_spread_data(
    base_symbol: str,
    quote_symbol: str,
    timeframe: str,
    limit: int = DEFAULT_SPREAD_LIMIT,
) -> SpreadResult:
    pair = normalize_spread_pair(base_symbol, quote_symbol)
    normalized_timeframe = normalize_timeframe(timeframe)
    normalized_limit = _normalize_limit(limit)
    cache_key = _SpreadCacheKey(
        pair.base_fetch_symbol,
        pair.quote_fetch_symbol,
        normalized_timeframe,
        normalized_limit,
    )
    cached = _get_cached_spread(cache_key)
    if cached is not None:
        return cached

    base_candles = market_data_client.get_ohlcv(
        pair.base_fetch_symbol,
        normalized_timeframe,
        normalized_limit,
    )
    quote_candles = market_data_client.get_ohlcv(
        pair.quote_fetch_symbol,
        normalized_timeframe,
        normalized_limit,
    )
    spread_ohlcv = calculate_spread_ohlcv(base_candles, quote_candles)
    result: SpreadResult = {
        "base_symbol": pair.base_symbol,
        "quote_symbol": pair.quote_symbol,
        "timeframe": normalized_timeframe,
        "limit": normalized_limit,
        "candle_count": len(spread_ohlcv),
        "ohlcv": spread_ohlcv,
    }
    _set_cached_spread(cache_key, result)
    return _copy_spread_result(result)


@mcp.tool()
def get_spread(
    base_symbol: str,
    quote_symbol: str,
    timeframe: str,
    limit: int = DEFAULT_SPREAD_LIMIT,
) -> SpreadResult:
    """Compute ratio OHLCV candles for base_symbol / quote_symbol."""
    return get_spread_data(base_symbol, quote_symbol, timeframe, limit)


@mcp.tool()
def render_spread_chart(
    base: str,
    quote: str,
    timeframe: str,
    limit: int = DEFAULT_SPREAD_LIMIT,
) -> RenderedSpreadChart:
    """Render a ratio spread chart for base / quote as a PNG image."""
    spread = get_spread_data(base, quote, timeframe, limit)
    title = f"{spread['base_symbol']}/{spread['quote_symbol']} spread {spread['timeframe']}"
    rendered = render_chart_image(spread["ohlcv"], title, None)
    result: RenderedSpreadChart = {
        **rendered,
        "base_symbol": spread["base_symbol"],
        "quote_symbol": spread["quote_symbol"],
        "timeframe": spread["timeframe"],
        "ratio_candle_count": spread["candle_count"],
    }
    return result


def main() -> None:
    mcp.run()


def _display_symbol(fetch_symbol: str) -> str:
    for quote_asset in SUPPORTED_QUOTE_ASSETS:
        if fetch_symbol.endswith(quote_asset) and len(fetch_symbol) > len(quote_asset):
            return fetch_symbol[: -len(quote_asset)]
    return fetch_symbol


def _get_cached_spread(cache_key: _SpreadCacheKey) -> SpreadResult | None:
    result = _spread_cache.get(cache_key)
    if result is None:
        return None
    _spread_cache.move_to_end(cache_key)
    return _copy_spread_result(result)


def _set_cached_spread(cache_key: _SpreadCacheKey, result: SpreadResult) -> None:
    _spread_cache[cache_key] = _copy_spread_result(result)
    _spread_cache.move_to_end(cache_key)
    if len(_spread_cache) > SPREAD_CACHE_SIZE:
        _spread_cache.popitem(last=False)


def _copy_spread_result(result: SpreadResult) -> SpreadResult:
    return {
        "base_symbol": result["base_symbol"],
        "quote_symbol": result["quote_symbol"],
        "timeframe": result["timeframe"],
        "limit": result["limit"],
        "candle_count": result["candle_count"],
        "ohlcv": [dict(candle) for candle in result["ohlcv"]],
    }


def _normalize_limit(limit: int) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if limit > MAX_LIMIT:
        raise ValueError(f"limit must be <= {MAX_LIMIT}")
    return limit


def _coerce_positive_float(value: Any, field_name: str) -> float:
    coerced = _coerce_float(value, field_name)
    if coerced <= 0:
        raise ValueError(f"{field_name} must be positive")
    return coerced


def _coerce_non_negative_float(value: Any, field_name: str) -> float:
    coerced = _coerce_float(value, field_name)
    if coerced < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return coerced


def _coerce_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        coerced = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(coerced):
        raise ValueError(f"{field_name} must be finite")
    return coerced


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field_name} must be an integer")
    return coerced


if __name__ == "__main__":
    main()
