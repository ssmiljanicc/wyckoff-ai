"""Isolated CLI runtime adapters for Phase 4 analyst and judge calls."""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from scripts.eval import isolation_state


CLAUDE_ISOLATION_ARGS = [
    "--setting-sources", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--disable-slash-commands", "--tools", "", "--permission-mode", "dontAsk",
    "--no-session-persistence",
]


class RuntimeErrorBase(RuntimeError):
    """Base class for bounded, operator-safe runtime failures."""


class RuntimeUnavailable(RuntimeErrorBase):
    pass


class RuntimeExecutionError(RuntimeErrorBase):
    def __init__(self, message: str, *, exit_code: int | None = None, stderr_tail: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail


class RuntimeTimeout(RuntimeExecutionError):
    pass


@dataclass(frozen=True)
class RuntimeRequest:
    prompt: str
    cwd: Path
    schema_path: Path
    model: str
    effort: str
    timeout: float


@dataclass(frozen=True)
class RuntimeResponse:
    output: dict[str, Any]
    usage: dict[str, int]
    exit_code: int = 0


class RuntimeAdapter(Protocol):
    async def preflight(self, model: str, effort: str) -> None: ...
    async def run(self, request: RuntimeRequest) -> RuntimeResponse: ...


def _stderr_tail(raw: bytes, *, limit: int = 2000) -> str:
    text = raw.decode(errors="replace")[-limit:]
    # Prompts are never included; remove common credential-shaped lines as defense in depth.
    return "\n".join(
        "[REDACTED]" if any(k in line.lower() for k in ("api_key", "authorization", "token=")) else line
        for line in text.splitlines()
    )


def _usage(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": int(raw.get("input_tokens", raw.get("input", 0)) or 0),
        "output_tokens": int(raw.get("output_tokens", raw.get("output", 0)) or 0),
    }


async def _exec(argv: list[str], *, cwd: Path, stdin: str, timeout: float) -> tuple[bytes, bytes, int]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(stdin.encode()), timeout)
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeTimeout(f"runtime timed out after {timeout:g}s") from exc
    return stdout, stderr, int(process.returncode or 0)


async def _require_capabilities(argv: list[str], required: tuple[str, ...]) -> None:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    stdout, _ = await process.communicate()
    help_text = stdout.decode(errors="replace")
    missing = [flag for flag in required if flag not in help_text]
    if process.returncode or missing:
        detail = f"; missing flags: {', '.join(missing)}" if missing else ""
        raise RuntimeUnavailable(f"runtime capability check failed{detail}")


async def _cli_version(argv: list[str]) -> str | None:
    """Best-effort CLI version string (e.g. ``codex-cli 0.141.0``); None on failure.

    Captured identically to ``canary_common.cli_version`` so the recorded and the
    live version strings compare equal.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
    except OSError:
        return None
    stdout, _ = await process.communicate()
    if process.returncode:
        return None
    return stdout.decode(errors="replace").strip() or None


async def _require_auth(argv: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()
    if process.returncode:
        raise RuntimeUnavailable("runtime authentication is unavailable")


class ClaudeRuntimeAdapter:
    binary = "claude"

    def build_argv(self, request: RuntimeRequest) -> list[str]:
        schema = request.schema_path.read_text().strip()
        json.loads(schema)
        return [
            self.binary, "-p", "--model", request.model, "--effort", request.effort,
            "--json-schema", schema, "--output-format", "json",
            *CLAUDE_ISOLATION_ARGS,
        ]

    async def preflight(self, model: str, effort: str) -> None:
        if shutil.which(self.binary) is None:
            raise RuntimeUnavailable("claude binary is unavailable")
        if model == "claude-fable-5":
            raise RuntimeUnavailable("claude-fable-5 is not available in the v1 runtime map")
        if not model.startswith("claude-"):
            raise RuntimeUnavailable(f"unsupported Claude model: {model}")
        await _require_capabilities(
            [self.binary, "--help"],
            (
                "--model", "--effort", "--json-schema", "--no-session-persistence",
                "--setting-sources", "--strict-mcp-config", "--mcp-config",
                "--disable-slash-commands", "--tools",
            ),
        )
        # `auth status` is free and rejects invalid global args, so this also
        # verifies that the installed CLI parses the exact isolation profile.
        await _require_auth([self.binary, *CLAUDE_ISOLATION_ARGS, "auth", "status"])

    async def run(self, request: RuntimeRequest) -> RuntimeResponse:
        stdout, stderr, code = await _exec(
            self.build_argv(request), cwd=request.cwd, stdin=request.prompt, timeout=request.timeout
        )
        if code:
            raise RuntimeExecutionError("claude runtime failed", exit_code=code, stderr_tail=_stderr_tail(stderr))
        try:
            envelope = json.loads(stdout)
            if not isinstance(envelope, dict):
                raise ValueError("Claude output envelope is not an object")
            output = envelope.get("structured_output")
            if output is None:
                output = envelope.get("result", envelope)
            if isinstance(output, str):
                stripped = output.strip()
                lines = stripped.splitlines()
                if lines and lines[0].strip() in {"```", "```json"}:
                    if len(lines) < 3 or lines[-1].strip() != "```":
                        raise ValueError("Claude structured output has an incomplete code fence")
                    stripped = "\n".join(lines[1:-1]).strip()
                output = json.loads(stripped)
            if not isinstance(output, dict):
                raise ValueError("structured output is not an object")
            return RuntimeResponse(output, _usage(envelope.get("usage")))
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise RuntimeExecutionError("invalid Claude structured output", stderr_tail=_stderr_tail(stderr)) from exc


class CodexRuntimeAdapter:
    binary = "codex"

    def __init__(
        self,
        *,
        model_map: dict[str, str] | None = None,
        verdict_path: Path | None = None,
    ):
        self.model_map = model_map or {"codex": "gpt-5.4"}
        self.verdict_path = verdict_path or isolation_state.DEFAULT_VERDICT_PATH

    def build_argv(self, request: RuntimeRequest) -> list[str]:
        model = self.model_map.get(request.model, request.model)
        # Launch through the shared execution profile so the run is contained the
        # same way the canary proved (wrapper + sandbox feed the gate fingerprint).
        profile = isolation_state.CODEX_EXECUTION_PROFILE
        return [
            *profile["wrapper_argv"],
            self.binary, "exec", "-", "--model", model, "--cd", str(request.cwd),
            "--sandbox", str(profile["sandbox"]), "--ephemeral", "--ignore-user-config",
            "--output-schema", str(request.schema_path), "--json",
            "-c", f'model_reasoning_effort="{request.effort}"',
        ]

    async def preflight(self, model: str, effort: str) -> None:
        if shutil.which(self.binary) is None:
            raise RuntimeUnavailable("codex binary is unavailable")
        if model not in self.model_map:
            raise RuntimeUnavailable(f"unmapped Codex matrix model: {model}")
        # Authorization is gated on a programmatically recorded sentinel-canary
        # PASS for the live CLI/platform — never a hand-edited constant (issue #75).
        cli_version = await _cli_version([self.binary, "--version"])
        block_reason = isolation_state.isolation_block_reason(
            provider="codex",
            cli_version=cli_version,
            expected_canary="canary_codex_image",
            path=self.verdict_path,
        )
        if block_reason is not None:
            raise RuntimeUnavailable(
                f"Codex private-benchmark isolation is not proven: {block_reason}. "
                "Run `uv run python -m scripts.eval.canary_codex_image --confirm` to "
                "record a passing sentinel verdict (issue #75)."
            )
        await _require_capabilities(
            [self.binary, "exec", "--help"],
            ("--model", "--cd", "--sandbox", "--output-schema", "--ephemeral", "--ignore-user-config"),
        )
        await _require_auth([self.binary, "login", "status"])

    async def run(self, request: RuntimeRequest) -> RuntimeResponse:
        stdout, stderr, code = await _exec(
            self.build_argv(request), cwd=request.cwd, stdin=request.prompt, timeout=request.timeout
        )
        if code:
            raise RuntimeExecutionError("codex runtime failed", exit_code=code, stderr_tail=_stderr_tail(stderr))
        try:
            events = [json.loads(line) for line in stdout.decode().splitlines() if line.strip()]
            output: Any = None
            usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
            for event in events:
                if isinstance(event.get("usage"), dict):
                    usage = _usage(event["usage"])
                item = event.get("item", {})
                candidate = item.get("text") if isinstance(item, dict) else None
                if candidate and item.get("type") in {"agent_message", "message"}:
                    output = json.loads(candidate) if isinstance(candidate, str) else candidate
            if not isinstance(output, dict):
                raise ValueError("no structured agent message")
            return RuntimeResponse(output, usage)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise RuntimeExecutionError("invalid Codex structured output", stderr_tail=_stderr_tail(stderr)) from exc


def adapter_for_model(model: str) -> RuntimeAdapter:
    return CodexRuntimeAdapter() if model == "codex" else ClaudeRuntimeAdapter()
