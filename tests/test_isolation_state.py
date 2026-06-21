from __future__ import annotations

import platform
from pathlib import Path

from scripts.eval import isolation_state

CANARY = "canary_codex_image"


def _record(tmp_path: Path, **overrides) -> Path:
    path = tmp_path / "verdict.json"
    defaults = dict(
        provider="codex",
        passed=True,
        canary=CANARY,
        cli_version="codex-cli 0.141.0",
        detail="all checks passed",
        path=path,
    )
    defaults.update(overrides)
    isolation_state.record_verdict(**defaults)
    return path


def _reason(path: Path, *, cli_version: str | None = "codex-cli 0.141.0") -> str | None:
    return isolation_state.isolation_block_reason(
        provider="codex", cli_version=cli_version, expected_canary=CANARY, path=path
    )


def test_missing_verdict_is_blocked(tmp_path: Path) -> None:
    reason = _reason(tmp_path / "nope.json")
    assert reason and "no sentinel-canary verdict" in reason


def test_fresh_passing_verdict_is_allowed(tmp_path: Path) -> None:
    assert _reason(_record(tmp_path)) is None


def test_failed_verdict_is_blocked(tmp_path: Path) -> None:
    reason = _reason(_record(tmp_path, passed=False, detail="outside read blocked"))
    assert reason and "FAILED isolation verdict" in reason


def test_provider_mismatch_is_blocked(tmp_path: Path) -> None:
    reason = _reason(_record(tmp_path, provider="claude"))
    assert reason and "provider" in reason


def test_canary_mismatch_is_blocked(tmp_path: Path) -> None:
    reason = _reason(_record(tmp_path, canary="some_other_canary"))
    assert reason and "canary" in reason


def test_stale_cli_version_is_blocked(tmp_path: Path) -> None:
    reason = _reason(_record(tmp_path, cli_version="codex-cli 0.140.0"))
    assert reason and "stale" in reason


def test_unknown_current_version_is_blocked(tmp_path: Path) -> None:
    reason = _reason(_record(tmp_path), cli_version=None)
    assert reason and "could not be determined" in reason


def test_system_mismatch_is_blocked(tmp_path: Path, monkeypatch) -> None:
    path = _record(tmp_path)  # records under the real current platform
    other = "Linux" if platform.system() != "Linux" else "Darwin"
    monkeypatch.setattr(isolation_state.platform, "system", lambda: other)
    reason = _reason(path)
    assert reason and "platform-specific" in reason


def test_full_platform_mismatch_is_blocked(tmp_path: Path, monkeypatch) -> None:
    path = _record(tmp_path)  # records under the real current platform string
    # Same OS name, different build/arch string -> still fail-closed.
    monkeypatch.setattr(isolation_state.platform, "platform", lambda: "Some-Other-Build-9.9")
    reason = _reason(path)
    assert reason and "OS builds/arch" in reason


def test_profile_fingerprint_mismatch_is_blocked(tmp_path: Path, monkeypatch) -> None:
    path = _record(tmp_path)  # fingerprint of the default (uncontained) profile
    # A different active execution profile (e.g. future containment wrapper) must
    # not be authorized by a verdict proven under the old profile.
    monkeypatch.setattr(
        isolation_state,
        "CODEX_EXECUTION_PROFILE",
        {"sandbox": "read-only", "wrapper_argv": ["sudo", "-u", "codexrunner"], "containment": "uid"},
    )
    reason = _reason(path)
    assert reason and "execution profile" in reason


def test_malformed_verdict_file_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text("{not valid json")
    assert isolation_state.load_verdict(path) is None
    reason = _reason(path)
    assert reason and "no sentinel-canary verdict" in reason


def test_incomplete_verdict_file_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text('{"provider": "codex", "passed": true}')  # missing required fields
    assert isolation_state.load_verdict(path) is None


def test_profile_fingerprint_is_stable_and_sensitive() -> None:
    base = {"sandbox": "read-only", "wrapper_argv": [], "containment": "none"}
    assert isolation_state.codex_profile_fingerprint(base) == isolation_state.codex_profile_fingerprint(base)
    changed = {"sandbox": "read-only", "wrapper_argv": ["x"], "containment": "uid"}
    assert isolation_state.codex_profile_fingerprint(base) != isolation_state.codex_profile_fingerprint(changed)
