"""Shared stub OHLCV client for dry-run / offline eval workflows.

DryRunClient returns deterministic synthetic candles without any network calls,
so snapshot generation, the lookahead probe, the ground-truth set build, and the
benchmark matrix can all run offline (tests + --dry-run).
"""

from __future__ import annotations

from typing import Any


class DryRunClient:
    """Stub returning fixed candles without any network calls."""

    def __init__(self) -> None:
        self.call_log: list[dict] = []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: Any = None,
    ) -> list[dict]:
        self.call_log.append(
            {"symbol": symbol, "timeframe": timeframe, "limit": limit, "end_time": end_time}
        )
        price = 5000.0
        candles = []
        for i in range(limit):
            candles.append(
                {
                    "open_time": i * 86_400_000,
                    "open": price + i,
                    "high": price + i + 50,
                    "low": max(1.0, price + i - 50),
                    "close": price + i + 10,
                    "volume": 1000.0 + i * 5,
                    "close_time": (i + 1) * 86_400_000 - 1,
                    "quote_volume": (1000.0 + i * 5) * (price + i + 10),
                    "trades": 100,
                }
            )
        return candles
