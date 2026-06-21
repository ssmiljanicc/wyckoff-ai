from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.eval import runtime_adapters as runtime


def request(tmp_path: Path, model: str = "claude-opus-4-8") -> runtime.RuntimeRequest:
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object","required":["direction"]}\n')
    return runtime.RuntimeRequest("private prompt", tmp_path, schema, model, "high", 1)


def test_claude_argv_is_toolless_and_non_persistent(tmp_path: Path) -> None:
    current = request(tmp_path)
    argv = runtime.ClaudeRuntimeAdapter().build_argv(current)
    assert argv[0:2] == ["claude", "-p"]
    assert "--bare" not in argv  # --bare breaks subprocess auth in non-TTY mode
    assert argv[argv.index("--json-schema") + 1] == '{"type":"object","required":["direction"]}'
    assert argv[argv.index("--json-schema") + 1] != str(current.schema_path)
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--strict-mcp-config" in argv
    assert "--disable-slash-commands" in argv
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


@pytest.mark.parametrize(
    "result",
    [
        '{"direction":"none"}',
        '```json\n{"direction":"none"}\n```',
        '```\n{"direction":"none"}\n```',
    ],
)
def test_claude_parser_extracts_json_string_results(monkeypatch, tmp_path: Path, result: str) -> None:
    async def fake_exec(*args, **kwargs):
        return json.dumps({"result": result}).encode(), b"", 0

    monkeypatch.setattr(runtime, "_exec", fake_exec)
    response = asyncio.run(runtime.ClaudeRuntimeAdapter().run(request(tmp_path)))
    assert response.output == {"direction": "none"}


@pytest.mark.parametrize(
    "stdout",
    [
        {"result": 'before {"direction":"none"}'},
        {"result": '```json\n{"direction":"none"}'},
        {"result": '["none"]'},
        {"result": "not json"},
        ["not", "an", "envelope"],
    ],
)
def test_claude_parser_rejects_invalid_structured_output(monkeypatch, tmp_path: Path, stdout) -> None:
    async def fake_exec(*args, **kwargs):
        return json.dumps(stdout).encode(), b"", 0

    monkeypatch.setattr(runtime, "_exec", fake_exec)
    with pytest.raises(runtime.RuntimeExecutionError, match="invalid Claude structured output"):
        asyncio.run(runtime.ClaudeRuntimeAdapter().run(request(tmp_path)))


def test_claude_argv_rejects_invalid_schema(tmp_path: Path) -> None:
    current = request(tmp_path)
    current.schema_path.write_text("not json")
    with pytest.raises(json.JSONDecodeError):
        runtime.ClaudeRuntimeAdapter().build_argv(current)


def test_claude_argv_rejects_missing_schema(tmp_path: Path) -> None:
    current = request(tmp_path)
    current.schema_path.unlink()
    with pytest.raises(FileNotFoundError):
        runtime.ClaudeRuntimeAdapter().build_argv(current)


def test_claude_preflight_probes_exact_isolation_profile(monkeypatch) -> None:
    calls: dict[str, object] = {}

    async def fake_capabilities(argv, required):
        calls["required"] = required

    async def fake_auth(argv):
        calls["auth_argv"] = argv

    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    monkeypatch.setattr(runtime, "_require_capabilities", fake_capabilities)
    monkeypatch.setattr(runtime, "_require_auth", fake_auth)
    asyncio.run(runtime.ClaudeRuntimeAdapter().preflight("claude-opus-4-8", "high"))

    assert "--mcp-config" in calls["required"]
    assert calls["auth_argv"] == ["claude", *runtime.CLAUDE_ISOLATION_ARGS, "auth", "status"]


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


def test_codex_preflight_fails_closed_after_isolation_canary(monkeypatch) -> None:
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    with pytest.raises(runtime.RuntimeUnavailable, match="isolation failed"):
        asyncio.run(runtime.CodexRuntimeAdapter().preflight("codex", "high"))


def test_stderr_redacts_token_lines() -> None:
    assert "secret" not in runtime._stderr_tail(b"ok\ntoken=secret\n").lower()
