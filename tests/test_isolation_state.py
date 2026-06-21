from __future__ import annotations

import platform
from pathlib import Path

from scripts.eval import isolation_state


def _record(tmp_path: Path, **overrides) -> Path:
    path = tmp_path / "verdict.json"
    defaults = dict(
        provider="codex",
        passed=True,
        canary="canary_codex_image",
        cli_version="codex-cli 0.141.0",
        detail="all checks passed",
        path=path,
    )
    defaults.update(overrides)
    isolation_state.record_verdict(**defaults)
    return path


def test_missing_verdict_is_blocked(tmp_path: Path) -> None:
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=tmp_path / "nope.json"
    )
    assert reason and "no sentinel-canary verdict" in reason


def test_fresh_passing_verdict_is_allowed(tmp_path: Path) -> None:
    path = _record(tmp_path)
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason is None


def test_failed_verdict_is_blocked(tmp_path: Path) -> None:
    path = _record(tmp_path, passed=False, detail="outside read blocked")
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason and "FAILED isolation verdict" in reason


def test_provider_mismatch_is_blocked(tmp_path: Path) -> None:
    path = _record(tmp_path, provider="claude")
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason and "provider" in reason


def test_stale_cli_version_is_blocked(tmp_path: Path) -> None:
    path = _record(tmp_path, cli_version="codex-cli 0.140.0")
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason and "stale" in reason


def test_unknown_current_version_is_blocked(tmp_path: Path) -> None:
    path = _record(tmp_path)
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version=None, path=path
    )
    assert reason and "could not be determined" in reason


def test_platform_mismatch_is_blocked(tmp_path: Path, monkeypatch) -> None:
    path = _record(tmp_path)  # records under the real current platform
    other = "Linux" if platform.system() != "Linux" else "Darwin"
    monkeypatch.setattr(isolation_state.platform, "system", lambda: other)
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason and "platform" in reason


def test_malformed_verdict_file_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text("{not valid json")
    assert isolation_state.load_verdict(path) is None
    reason = isolation_state.isolation_block_reason(
        provider="codex", cli_version="codex-cli 0.141.0", path=path
    )
    assert reason and "no sentinel-canary verdict" in reason


def test_incomplete_verdict_file_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text('{"provider": "codex", "passed": true}')  # missing required fields
    assert isolation_state.load_verdict(path) is None
