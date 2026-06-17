"""MCP server modules for Wyckoff AI.

Server modules are loaded lazily so optional MCP extras do not become required
for unrelated store and server tests.
"""

from __future__ import annotations

import importlib
from types import ModuleType


__all__ = [
    "backtest_server",
    "chart_renderer",
    "market_data_client",
    "market_data_server",
    "portfolio_server",
    "portfolio_store",
    "scanner_server",
    "signal_logger_server",
    "spread_chart_server",
]


def __getattr__(name: str) -> ModuleType:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module
