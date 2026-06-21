from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts.eval import codex_container as container


def _case(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "case"
    root.mkdir()
    schema = root / "schema.json"
    image = root / "chart.png"
    auth = tmp_path / "auth.json"
    schema.write_text("{}")
    image.write_bytes(b"png")
    auth.write_text("{}")
    return root, schema, image, auth


def test_docker_argv_has_only_read_only_case_and_auth_mounts(tmp_path: Path) -> None:
    root, schema, image, auth = _case(tmp_path)
    argv = container.docker_argv(
        [
            "codex", "exec", "-", "--cd", str(root), "--sandbox", "read-only",
            "--output-schema", str(schema), "--image", str(image),
        ],
        image="test-image", auth=auth,
    )
    mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]
    assert mounts == [
        f"type=bind,src={root.resolve()},dst=/workspace,readonly",
        f"type=bind,src={auth.resolve()},dst=/home/codex/.codex/auth.json,readonly",
    ]
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges=true"
    assert "--privileged" not in argv
    assert not any("docker.sock" in value for value in argv)
    assert "--sandbox" not in argv
    inner = argv[argv.index("test-image") + 1:]
    assert "--dangerously-bypass-approvals-and-sandbox" in inner
    assert inner[inner.index("--cd") + 1] == "/workspace"
    assert inner[inner.index("--output-schema") + 1] == "/workspace/schema.json"
    assert inner[inner.index("--image") + 1] == "/workspace/chart.png"


@pytest.mark.parametrize("flag", ["--output-schema", "--image"])
def test_file_argument_outside_case_is_rejected(tmp_path: Path, flag: str) -> None:
    root, _, _, _ = _case(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("secret")
    with pytest.raises(container.ContainerProfileError, match="escapes case root"):
        container.translate_codex_argv(["codex", "exec", "-", "--cd", str(root), flag, str(outside)])


def test_symlink_file_is_rejected(tmp_path: Path) -> None:
    root, schema, _, _ = _case(tmp_path)
    link = root / "link.json"
    link.symlink_to(schema)
    with pytest.raises(container.ContainerProfileError, match="non-symlink"):
        container.translate_codex_argv(
            ["codex", "exec", "-", "--cd", str(root), "--output-schema", str(link)]
        )


def test_add_dir_is_rejected(tmp_path: Path) -> None:
    root, _, _, _ = _case(tmp_path)
    with pytest.raises(container.ContainerProfileError, match="forbidden"):
        container.translate_codex_argv(["codex", "exec", "-", "--cd", str(root), "--add-dir", str(tmp_path)])


def test_missing_auth_blocks_exec(tmp_path: Path) -> None:
    root, schema, _, _ = _case(tmp_path)
    with pytest.raises(container.ContainerProfileError, match="auth file is unavailable"):
        container.docker_argv(
            ["codex", "exec", "-", "--cd", str(root), "--output-schema", str(schema)],
            auth=tmp_path / "missing-auth.json",
        )


def test_execution_identity_uses_inspected_image_id(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ["docker", "image", "inspect"]:
            payload = {
                "Id": "sha256:immutable", "RepoDigests": ["test@sha256:digest"],
                "Os": "linux", "Architecture": "arm64",
            }
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        return subprocess.CompletedProcess(argv, 0, "codex-cli 0.141.0\n", "")

    monkeypatch.setattr(container.shutil, "which", lambda binary: "/usr/bin/docker")
    monkeypatch.setattr(container.subprocess, "run", fake_run)
    identity = container.execution_identity(image="test-image")
    assert identity["image_id"] == "sha256:immutable"
    assert identity["cli_version"] == "codex-cli 0.141.0"
    assert calls[0][:4] == ["docker", "image", "inspect", "test-image"]
