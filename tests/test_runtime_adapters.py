from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts.eval import runtime_adapters as runtime


IDENTITY = {
    "image": "test-image", "image_id": "sha256:test", "repo_digest": "",
    "container_os": "linux", "container_arch": "arm64", "cli_version": "codex-cli 9.9.9",
}


async def _async_value(value):
    return value


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
    assert argv[:len(runtime.isolation_state.CODEX_EXECUTION_PROFILE["wrapper_argv"])] == runtime.isolation_state.CODEX_EXECUTION_PROFILE["wrapper_argv"]
    inner_index = argv.index("codex")
    assert argv[inner_index:inner_index + 3] == ["codex", "exec", "-"]
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


def test_codex_preflight_fails_closed_when_no_verdict(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    missing = tmp_path / "codex_isolation_verdict.json"
    adapter = runtime.CodexRuntimeAdapter(verdict_path=missing)
    with pytest.raises(runtime.RuntimeUnavailable, match="isolation is not proven"):
        asyncio.run(adapter.preflight("codex", "high"))


def test_codex_preflight_fails_closed_on_failed_verdict(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    path = tmp_path / "codex_isolation_verdict.json"
    runtime.isolation_state.record_verdict(
        provider="codex", passed=False, canary="canary_codex_image",
        cli_version="codex-cli 0.141.0", execution_identity=IDENTITY,
        detail="outside read blocked", path=path,
    )
    adapter = runtime.CodexRuntimeAdapter(verdict_path=path)
    with pytest.raises(runtime.RuntimeUnavailable, match="FAILED isolation verdict"):
        asyncio.run(adapter.preflight("codex", "high"))


def test_codex_preflight_passes_gate_on_fresh_passing_verdict(monkeypatch, tmp_path: Path) -> None:
    # A recorded PASS matching the live CLI version + platform clears the gate;
    # downstream capability/auth checks are stubbed to isolate the gate.
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")

    async def _ok_version(argv):
        return "codex-cli 9.9.9"

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runtime, "_cli_version", _ok_version)
    monkeypatch.setattr(runtime, "_execution_identity", lambda argv: _async_value(IDENTITY))
    monkeypatch.setattr(runtime, "_require_capabilities", _noop)
    monkeypatch.setattr(runtime, "_require_auth", _noop)
    path = tmp_path / "codex_isolation_verdict.json"
    runtime.isolation_state.record_verdict(
        provider="codex", passed=True, canary="canary_codex_image",
        cli_version="codex-cli 9.9.9", execution_identity=IDENTITY,
        detail="all checks passed", path=path,
    )
    adapter = runtime.CodexRuntimeAdapter(verdict_path=path)
    asyncio.run(adapter.preflight("codex", "high"))  # must not raise


def test_codex_preflight_fails_closed_on_stale_verdict(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")

    async def _new_version(argv):
        return "codex-cli 9.9.9"

    monkeypatch.setattr(runtime, "_cli_version", _new_version)
    path = tmp_path / "codex_isolation_verdict.json"
    runtime.isolation_state.record_verdict(
        provider="codex", passed=True, canary="canary_codex_image",
        cli_version="codex-cli 0.141.0", execution_identity=IDENTITY,
        detail="all checks passed", path=path,
    )
    adapter = runtime.CodexRuntimeAdapter(verdict_path=path)
    with pytest.raises(runtime.RuntimeUnavailable, match="stale"):
        asyncio.run(adapter.preflight("codex", "high"))


def test_codex_preflight_fails_closed_when_profile_changed(monkeypatch, tmp_path: Path) -> None:
    # A PASS proven under one execution profile must not authorize a run launched
    # under a different (e.g. uncontained) profile with the same OS/CLI.
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: f"/usr/bin/{binary}")

    async def _ok_version(argv):
        return "codex-cli 9.9.9"

    monkeypatch.setattr(runtime, "_cli_version", _ok_version)
    monkeypatch.setattr(runtime, "_execution_identity", lambda argv: _async_value(IDENTITY))
    path = tmp_path / "codex_isolation_verdict.json"
    runtime.isolation_state.record_verdict(
        provider="codex", passed=True, canary="canary_codex_image",
        cli_version="codex-cli 9.9.9", execution_identity=IDENTITY,
        detail="all checks passed", path=path,
    )
    # The active profile now differs from the one the verdict was stamped under.
    monkeypatch.setattr(
        runtime.isolation_state,
        "CODEX_EXECUTION_PROFILE",
        {"sandbox": "read-only", "wrapper_argv": ["firejail"], "containment": "container"},
    )
    adapter = runtime.CodexRuntimeAdapter(verdict_path=path)
    with pytest.raises(runtime.RuntimeUnavailable, match="execution profile"):
        asyncio.run(adapter.preflight("codex", "high"))


def test_stderr_redacts_token_lines() -> None:
    assert "secret" not in runtime._stderr_tail(b"ok\ntoken=secret\n").lower()
