from __future__ import annotations

import importlib
import sys


def test_scripts_mcp_package_does_not_eager_import_optional_servers() -> None:
    for name in ["scripts.mcp", "scripts.mcp.chart_renderer", "scripts.mcp.spread_chart_server"]:
        sys.modules.pop(name, None)

    package = importlib.import_module("scripts.mcp")

    assert "scripts.mcp.chart_renderer" not in sys.modules
    assert "scripts.mcp.spread_chart_server" not in sys.modules
    assert package.__name__ == "scripts.mcp"


def test_scripts_mcp_package_lazily_exposes_existing_server_modules() -> None:
    package = importlib.import_module("scripts.mcp")

    signal_logger = package.signal_logger_server
    portfolio_store = package.portfolio_store

    assert signal_logger.__name__ == "scripts.mcp.signal_logger_server"
    assert portfolio_store.__name__ == "scripts.mcp.portfolio_store"
