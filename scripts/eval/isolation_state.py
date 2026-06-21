"""Persisted Codex isolation-canary verdict — the gate's only source of truth.

The Codex private-benchmark gate must NOT depend on a hand-edited boolean.
Authorization is granted only when the sentinel canary has *programmatically*
recorded a PASS for the current Codex CLI version and platform.  A missing,
failed, stale (different CLI version), or cross-platform record fails closed.

`canary_codex_image.py` writes this record on a real (`--confirm`) run;
`runtime_adapters.CodexRuntimeAdapter.preflight` reads it.  Re-enabling Codex
therefore requires actually running the canary to a genuine pass — there is no
constant to flip.

The verdict file lives under ``scripts/eval/state/`` (gitignored): a fresh
checkout has no file, so the default is fail-closed.  This is not tamper-proof
against an operator with repo write access — it raises the bar from an
innocuous one-character edit to deliberately forging a named security artifact
whose CLI/platform fingerprint must also match the live runtime.
"""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_VERDICT_PATH = Path(__file__).resolve().parent / "state" / "codex_isolation_verdict.json"

_REQUIRED_FIELDS = ("provider", "passed", "canary", "cli_version", "system", "platform", "recorded_at")


@dataclass(frozen=True)
class IsolationVerdict:
    provider: str
    passed: bool
    canary: str
    cli_version: str
    system: str
    platform: str
    recorded_at: str
    detail: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def record_verdict(
    *,
    provider: str,
    passed: bool,
    canary: str,
    cli_version: str,
    detail: str = "",
    path: Path = DEFAULT_VERDICT_PATH,
) -> IsolationVerdict:
    """Persist a canary verdict.  Called only after a real (paid) canary run."""
    verdict = IsolationVerdict(
        provider=provider,
        passed=passed,
        canary=canary,
        cli_version=cli_version,
        system=platform.system(),
        platform=platform.platform(),
        recorded_at=datetime.now(timezone.utc).isoformat(),
        detail=detail,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict.to_json())
    return verdict


def load_verdict(path: Path = DEFAULT_VERDICT_PATH) -> IsolationVerdict | None:
    """Load a recorded verdict, or None if absent/unreadable/malformed."""
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or any(field not in data for field in _REQUIRED_FIELDS):
        return None
    return IsolationVerdict(
        provider=str(data["provider"]),
        passed=bool(data["passed"]),
        canary=str(data["canary"]),
        cli_version=str(data["cli_version"]),
        system=str(data["system"]),
        platform=str(data["platform"]),
        recorded_at=str(data["recorded_at"]),
        detail=str(data.get("detail", "")),
    )


def isolation_block_reason(
    *,
    provider: str,
    cli_version: str | None,
    path: Path = DEFAULT_VERDICT_PATH,
) -> str | None:
    """Return None if isolation is currently proven for ``provider``; else a fail-closed reason.

    A proven verdict must exist, be a PASS, be for this provider, match the
    current platform, and match ``cli_version`` (when known).  Anything else —
    including an unknown current CLI version — is treated as not-proven.
    """
    verdict = load_verdict(path)
    if verdict is None:
        return "no sentinel-canary verdict recorded (fail-closed default)"
    if verdict.provider != provider:
        return f"recorded verdict is for provider {verdict.provider!r}, not {provider!r}"
    if not verdict.passed:
        suffix = f": {verdict.detail}" if verdict.detail else ""
        return f"sentinel-canary recorded a FAILED isolation verdict{suffix}"
    if verdict.system != platform.system():
        return (
            f"recorded verdict was proven on {verdict.system!r}; current platform is "
            f"{platform.system()!r} (Codex sandbox read behavior is platform-specific)"
        )
    if cli_version is None:
        return "current Codex CLI version could not be determined to validate the verdict"
    if verdict.cli_version != cli_version:
        return (
            f"recorded verdict is stale: proven on CLI {verdict.cli_version!r}, "
            f"current CLI {cli_version!r}"
        )
    return None
