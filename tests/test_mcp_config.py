from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mcp_config_registers_analysis_journal_server() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    server = config["mcpServers"]["wyckoff-analysis-journal"]
    assert server == {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "python", "-m", "scripts.mcp.analysis_journal_server"],
        "cwd": ".",
    }


def test_chart_servers_use_mcp_extra_dependencies() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    assert config["mcpServers"]["wyckoff-chart-renderer"]["args"][:3] == [
        "run",
        "--extra",
        "mcp",
    ]
    assert config["mcpServers"]["wyckoff-spread-chart"]["args"][:3] == [
        "run",
        "--extra",
        "mcp",
    ]
