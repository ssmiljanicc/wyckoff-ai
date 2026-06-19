from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.eval import runtime_adapters as runtime


def request(tmp_path: Path, model: str = "claude-opus-4-8") -> runtime.RuntimeRequest:
    schema = tmp_path / "schema.json"
    schema.write_text("{}")
    return runtime.RuntimeRequest("private prompt", tmp_path, schema, model, "high", 1)


def test_claude_argv_is_bare_toolless_and_non_persistent(tmp_path: Path) -> None:
    argv = runtime.ClaudeRuntimeAdapter().build_argv(request(tmp_path))
    assert argv[0:2] == ["claude", "-p"]
    assert "--bare" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv
    assert "private prompt" not in argv


def test_codex_argv_is_ephemeral_read_only_and_uses_config_effort(tmp_path: Path) -> None:
    argv = runtime.CodexRuntimeAdapter().build_argv(request(tmp_path, "codex"))
    assert argv[:3] == ["codex", "exec", "-"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in argv and "--ignore-user-config" in argv
    assert 'model_reasoning_effort="high"' in argv


def test_claude_parser_extracts_structured_output_and_usage(monkeypatch, tmp_path: Path) -> None:
    async def fake_exec(*args, **kwargs):
        return json.dumps({"structured_output": {"direction": "none"}, "usage": {"input_tokens": 2, "output_tokens": 3}}).encode(), b"", 0

    monkeypatch.setattr(runtime, "_exec", fake_exec)
    response = asyncio.run(runtime.ClaudeRuntimeAdapter().run(request(tmp_path)))
    assert response.output == {"direction": "none"}
    assert response.usage == {"input_tokens": 2, "output_tokens": 3}


def test_codex_parser_reads_jsonl_agent_message(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"direction":"up"}'}},
        {"type": "turn.completed", "usage": {"input_tokens": 4, "output_tokens": 5}},
    ]
    async def fake_exec(*args, **kwargs):
        return ("\n".join(json.dumps(event) for event in events)).encode(), b"", 0

    monkeypatch.setattr(runtime, "_exec", fake_exec)
    response = asyncio.run(runtime.CodexRuntimeAdapter().run(request(tmp_path, "codex")))
    assert response.output["direction"] == "up"
    assert response.usage["output_tokens"] == 5


def test_stderr_redacts_token_lines() -> None:
    assert "secret" not in runtime._stderr_tail(b"ok\ntoken=secret\n").lower()
