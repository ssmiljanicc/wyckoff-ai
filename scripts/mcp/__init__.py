"""MCP server modules for Wyckoff AI."""

from scripts.mcp import portfolio_server as portfolio_server  # noqa: F401  — register portfolio MCP server
from scripts.mcp import signal_logger_server as signal_logger_server  # noqa: F401  — register signal logger MCP server
from scripts.mcp import spread_chart_server as spread_chart_server  # noqa: F401  — register spread chart MCP server

