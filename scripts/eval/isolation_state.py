"""Persisted Codex isolation-canary verdict — the gate's only source of truth.

The Codex private-benchmark gate must NOT depend on a hand-edited boolean.
Authorization is granted only when the sentinel canary has *programmatically*
recorded a PASS for the current Codex CLI version and platform.  A missing,
failed, stale (different CLI version), or cross-platform record fails closed.

`canary_codex_image.py` writes this record on a real (`--confirm`) run;
`runtime_adapters.CodexRuntimeAdapter.preflight` reads it.  Re-enabling Codex
therefore requires actually running the canary to a genuine pass — there is no
constant to flip.

A PASS is additionally bound to the fingerprint of the *execution profile*
(sandbox mode + containment wrapper) it was proven under, so a verdict earned
under containment can never authorize an uncontained run with the same OS/CLI.

The verdict file lives under ``scripts/eval/state/`` (gitignored): a fresh
checkout has no file, so the default is fail-closed.  This is not tamper-proof
against an operator with repo write access — it raises the bar from an
innocuous one-character edit to deliberately forging a named security artifact
whose canary id, CLI, platform, and execution-profile fingerprint must all match
the live runtime.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

from scripts.eval.codex_container import CONTAINER_WORKSPACE, DEFAULT_IMAGE

DEFAULT_VERDICT_PATH = Path(__file__).resolve().parent / "state" / "codex_isolation_verdict.json"
_CONTAINER_LAUNCHER = Path(__file__).with_name("codex_container.py")

# Single source of truth for the security-relevant Codex execution profile.
# BOTH the canary (which proves isolation) and the adapter (which runs the
# benchmark) launch codex through THIS profile, and a PASS authorizes a run only
# when the live profile fingerprint equals the recorded one.  When issue #82
# introduces real containment (separate uid, container, ...), set ``wrapper_argv``
# and ``containment`` here: the fingerprint changes, which invalidates any PASS
# proven under the old (uncontained) profile and forces the canary to be re-run
# under the new one.  This closes the hole where a PASS proven under containment
# could otherwise authorize an uncontained run with the same OS/CLI.
CODEX_EXECUTION_PROFILE: dict[str, object] = {
    "sandbox": "read-only",
    "wrapper_argv": [
        sys.executable,
        str(_CONTAINER_LAUNCHER),
        "--container-image",
        DEFAULT_IMAGE,
    ],
    "containment": "docker",
    "image": DEFAULT_IMAGE,
    "workspace": str(CONTAINER_WORKSPACE),
    # Logical argv + source hash keep the fingerprint stable across worktrees,
    # while any launcher implementation change still invalidates an old PASS.
    "wrapper_id": ["python", "scripts/eval/codex_container.py", "--container-image", DEFAULT_IMAGE],
    "launcher_sha256": hashlib.sha256(_CONTAINER_LAUNCHER.read_bytes()).hexdigest(),
}

_REQUIRED_FIELDS = (
    "provider", "passed", "canary", "cli_version",
    "system", "platform", "profile_fingerprint", "execution_identity", "recorded_at",
)


def codex_profile_fingerprint(profile: dict[str, object] | None = None) -> str:
    """Stable short hash of the security-relevant execution profile."""
    active = CODEX_EXECUTION_PROFILE if profile is None else profile
    fingerprinted = dict(active)
    if "wrapper_id" in fingerprinted:
        fingerprinted["wrapper_argv"] = fingerprinted["wrapper_id"]
    canonical = json.dumps(fingerprinted, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class IsolationVerdict:
    provider: str
    passed: bool
    canary: str
    cli_version: str
    system: str
    platform: str
    profile_fingerprint: str
    execution_identity: dict[str, str]
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
    execution_identity: dict[str, str],
    detail: str = "",
    path: Path = DEFAULT_VERDICT_PATH,
) -> IsolationVerdict:
    """Persist a canary verdict.  Called only after a real (paid) canary run.

    The verdict is stamped with the fingerprint of the *active* execution
    profile, so it can only authorize runs that launch codex the same way.
    """
    verdict = IsolationVerdict(
        provider=provider,
        passed=passed,
        canary=canary,
        cli_version=cli_version,
        system=platform.system(),
        platform=platform.platform(),
        profile_fingerprint=codex_profile_fingerprint(),
        execution_identity=dict(execution_identity),
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
    if (
        not isinstance(data, dict)
        or any(field not in data for field in _REQUIRED_FIELDS)
        or not isinstance(data.get("execution_identity"), dict)
    ):
        return None
    return IsolationVerdict(
        provider=str(data["provider"]),
        passed=bool(data["passed"]),
        canary=str(data["canary"]),
        cli_version=str(data["cli_version"]),
        system=str(data["system"]),
        platform=str(data["platform"]),
        profile_fingerprint=str(data["profile_fingerprint"]),
        execution_identity={str(key): str(value) for key, value in data["execution_identity"].items()},
        recorded_at=str(data["recorded_at"]),
        detail=str(data.get("detail", "")),
    )


def isolation_block_reason(
    *,
    provider: str,
    cli_version: str | None,
    execution_identity: dict[str, str] | None,
    expected_canary: str,
    path: Path = DEFAULT_VERDICT_PATH,
) -> str | None:
    """Return None if isolation is currently proven for ``provider``; else a fail-closed reason.

    A proven verdict must exist, be a PASS, come from ``expected_canary``, be for
    this provider, match the current platform string and CLI version (when
    known), and carry the fingerprint of the *active* execution profile.  Any
    mismatch — including an unknown current CLI version — is treated as
    not-proven.  The profile-fingerprint check is what binds the PASS to the
    containment under which it was proven: a verdict earned under one profile
    cannot authorize a run launched under a different one.
    """
    verdict = load_verdict(path)
    if verdict is None:
        return "no sentinel-canary verdict recorded (fail-closed default)"
    if verdict.provider != provider:
        return f"recorded verdict is for provider {verdict.provider!r}, not {provider!r}"
    if verdict.canary != expected_canary:
        return (
            f"recorded verdict is from canary {verdict.canary!r}, "
            f"not the expected {expected_canary!r}"
        )
    if not verdict.passed:
        suffix = f": {verdict.detail}" if verdict.detail else ""
        return f"sentinel-canary recorded a FAILED isolation verdict{suffix}"
    if verdict.system != platform.system():
        return (
            f"recorded verdict was proven on {verdict.system!r}; current platform is "
            f"{platform.system()!r} (Codex sandbox read behavior is platform-specific)"
        )
    if verdict.platform != platform.platform():
        return (
            f"recorded verdict was proven on {verdict.platform!r}; current platform is "
            f"{platform.platform()!r} (sandbox behavior can change across OS builds/arch)"
        )
    if cli_version is None:
        return "current Codex CLI version could not be determined to validate the verdict"
    if verdict.cli_version != cli_version:
        return (
            f"recorded verdict is stale: proven on CLI {verdict.cli_version!r}, "
            f"current CLI {cli_version!r}"
        )
    if execution_identity is None:
        return "current container execution identity could not be determined"
    if verdict.execution_identity != execution_identity:
        return (
            "recorded container execution identity does not match the live image/runtime "
            "(image id/digest, container platform, or wrapped CLI changed — re-run the canary)"
        )
    active_fingerprint = codex_profile_fingerprint()
    if verdict.profile_fingerprint != active_fingerprint:
        return (
            f"recorded verdict was proven under execution profile "
            f"{verdict.profile_fingerprint!r}; active profile is {active_fingerprint!r} "
            "(containment/sandbox profile changed — re-run the canary under it)"
        )
    return None
