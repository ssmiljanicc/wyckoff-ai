"""MCP server exposing Binance OHLCV market data."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from scripts.mcp.market_data_client import (
    DEFAULT_LIMIT,
    BinanceMarketDataClient,
    Candle,
    SymbolInfo,
    get_timeframes as client_get_timeframes,
)


mcp = FastMCP("wyckoff-market-data")
client = BinanceMarketDataClient()


@mcp.tool()
def get_ohlcv(symbol: str, timeframe: str, limit: int = DEFAULT_LIMIT) -> list[Candle]:
    """Fetch OHLCV candles from Binance public market data."""
    return client.get_ohlcv(symbol, timeframe, limit)


@mcp.tool()
def get_supported_symbols() -> list[SymbolInfo]:
    """Return the top 50 supported spot USDT symbols by 24h quote volume."""
    return client.get_supported_symbols()


@mcp.tool()
def get_timeframes() -> list[str]:
    """Return supported OHLCV timeframes."""
    return client_get_timeframes()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

