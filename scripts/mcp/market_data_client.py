"""Binance public market data client for Wyckoff MCP servers."""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

import httpx


BINANCE_BASE_URL = "https://data-api.binance.vision"
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
OHLCV_CACHE_SIZE = 256
RATE_LIMIT_DELAY_SECONDS = 0.05
USER_AGENT = "wyckoff-ai-market-data/0.1 (+https://github.com/ssmiljanicc/wyckoff-ai)"
SUPPORTED_TIMEFRAMES: dict[str, str] = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}
DEFAULT_QUOTE_ASSET = "USDT"
SUPPORTED_QUOTE_ASSETS = ("USDT", "USDC", "BTC", "ETH", "BNB")
LEVERAGED_TOKEN_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")
SYMBOL_RE = re.compile(r"^[A-Z0-9/._:-]+$")


class Candle(TypedDict):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int


class SymbolInfo(TypedDict):
    symbol: str
    base_asset: str
    quote_asset: str
    quote_volume: float


class BinanceMarketDataError(RuntimeError):
    """Base exception for market data failures."""


class BinanceRateLimitError(BinanceMarketDataError):
    """Raised when Binance rejects a request for rate-limit or legal reasons."""


class BinanceUpstreamError(BinanceMarketDataError):
    """Raised for non-rate-limit upstream failures."""


class _HttpClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        ...


@dataclass(frozen=True)
class _CacheKey:
    symbol: str
    timeframe: str
    limit: int


def normalize_symbol(symbol: str) -> str:
    """Normalize common crypto symbol spellings to Binance format."""
    raw = symbol.strip().upper()
    if not raw:
        raise ValueError("Symbol is required")
    if not SYMBOL_RE.fullmatch(raw):
        raise ValueError(f"Unsupported symbol format: {symbol!r}")

    normalized = re.sub(r"[/._:-]", "", raw)
    if not normalized:
        raise ValueError("Symbol is required")
    if normalized == DEFAULT_QUOTE_ASSET:
        raise ValueError(f"Symbol must include a base asset: {symbol!r}")

    if any(
        normalized.endswith(quote) and len(normalized) > len(quote)
        for quote in SUPPORTED_QUOTE_ASSETS
    ):
        return normalized
    return f"{normalized}{DEFAULT_QUOTE_ASSET}"


def normalize_timeframe(timeframe: str) -> str:
    normalized = timeframe.strip().lower()
    try:
        return SUPPORTED_TIMEFRAMES[normalized]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_TIMEFRAMES)
        raise ValueError(f"Unsupported timeframe {timeframe!r}; supported: {supported}") from exc


def get_timeframes() -> list[str]:
    return list(SUPPORTED_TIMEFRAMES)


class BinanceMarketDataClient:
    """Small shared client for public Binance OHLCV data."""

    def __init__(
        self,
        *,
        base_url: str = BINANCE_BASE_URL,
        timeout: float = 10.0,
        rate_limit_delay: float = RATE_LIMIT_DELAY_SECONDS,
        http_client: _HttpClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self._last_request_at = 0.0
        self._ohlcv_cache: OrderedDict[_CacheKey, list[Candle]] = OrderedDict()
        self._supported_symbols_cache: list[SymbolInfo] | None = None
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )

    def close(self) -> None:
        if self._owns_http_client and hasattr(self._http_client, "close"):
            self._http_client.close()

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = DEFAULT_LIMIT) -> list[Candle]:
        normalized_symbol = normalize_symbol(symbol)
        normalized_timeframe = normalize_timeframe(timeframe)
        normalized_limit = self._normalize_limit(limit)
        cache_key = _CacheKey(normalized_symbol, normalized_timeframe, normalized_limit)
        if cache_key in self._ohlcv_cache:
            self._ohlcv_cache.move_to_end(cache_key)
            return list(self._ohlcv_cache[cache_key])

        data = self._request_json(
            "/api/v3/klines",
            {
                "symbol": normalized_symbol,
                "interval": normalized_timeframe,
                "limit": normalized_limit,
            },
        )
        if not isinstance(data, list):
            raise BinanceUpstreamError("Unexpected Binance klines response")
        candles = [parse_kline(row) for row in data]
        if not candles:
            raise BinanceUpstreamError(
                f"Binance returned no candles for {normalized_symbol} {normalized_timeframe}"
            )
        self._set_ohlcv_cache(cache_key, candles)
        return list(candles)

    def get_supported_symbols(self, limit: int = 50) -> list[SymbolInfo]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if self._supported_symbols_cache is None:
            self._supported_symbols_cache = self._fetch_supported_symbols()
        return list(self._supported_symbols_cache[:limit])

    def _fetch_supported_symbols(self) -> list[SymbolInfo]:
        exchange_info = self._request_json("/api/v3/exchangeInfo")
        ticker_24hr = self._request_json("/api/v3/ticker/24hr")
        if not isinstance(exchange_info, dict) or not isinstance(ticker_24hr, list):
            raise BinanceUpstreamError("Unexpected Binance supported-symbols response")

        active_symbols: dict[str, tuple[str, str]] = {}
        for item in exchange_info.get("symbols", []):
            if not isinstance(item, dict):
                continue
            if item.get("status") != "TRADING":
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            symbol = str(item.get("symbol", ""))
            quote_asset = str(item.get("quoteAsset", ""))
            base_asset = str(item.get("baseAsset", ""))
            if quote_asset != DEFAULT_QUOTE_ASSET:
                continue
            if _is_leveraged_token(base_asset):
                continue
            active_symbols[symbol] = (base_asset, quote_asset)

        symbols: list[SymbolInfo] = []
        for item in ticker_24hr:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", ""))
            if symbol not in active_symbols:
                continue
            base_asset, quote_asset = active_symbols[symbol]
            try:
                quote_volume = float(item.get("quoteVolume", 0))
            except (TypeError, ValueError):
                quote_volume = 0.0
            symbols.append(
                {
                    "symbol": symbol,
                    "base_asset": base_asset,
                    "quote_asset": quote_asset,
                    "quote_volume": quote_volume,
                }
            )

        symbols.sort(key=lambda item: (-item["quote_volume"], item["symbol"]))
        return symbols

    def _request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._sleep_for_rate_limit()
        url = f"{self.base_url}{path}"
        try:
            response = self._http_client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise BinanceUpstreamError(f"Binance request failed: {exc}") from exc

        if response.status_code in {429, 451}:
            retry_after = response.headers.get("Retry-After")
            suffix = f"; Retry-After={retry_after}" if retry_after else ""
            raise BinanceRateLimitError(
                f"Binance returned HTTP {response.status_code} for {path}{suffix}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BinanceUpstreamError(
                f"Binance returned HTTP {response.status_code} for {path}"
            ) from exc
        return response.json()

    def _sleep_for_rate_limit(self) -> None:
        if self.rate_limit_delay <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_at = time.monotonic()

    def _set_ohlcv_cache(self, cache_key: _CacheKey, candles: list[Candle]) -> None:
        self._ohlcv_cache[cache_key] = candles
        self._ohlcv_cache.move_to_end(cache_key)
        if len(self._ohlcv_cache) > OHLCV_CACHE_SIZE:
            self._ohlcv_cache.popitem(last=False)

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if limit > MAX_LIMIT:
            raise ValueError(f"limit must be <= {MAX_LIMIT}")
        return limit


def parse_kline(row: Any) -> Candle:
    if not isinstance(row, list) or len(row) < 9:
        raise BinanceUpstreamError("Unexpected Binance kline row")
    return {
        "open_time": int(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
        "close_time": int(row[6]),
        "quote_volume": float(row[7]),
        "trades": int(row[8]),
    }


def _is_leveraged_token(base_asset: str) -> bool:
    return base_asset.endswith(LEVERAGED_TOKEN_SUFFIXES)
