"""Hardened Docker launcher for Codex private-benchmark processes.

The container receives only the resolved case root and the Codex auth file.
Every host file argument is translated beneath ``/workspace`` before launch.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


DEFAULT_IMAGE = "wyckoff-codex-eval:0.141.0"
CONTAINER_WORKSPACE = Path("/workspace")
CONTAINER_AUTH = "/home/codex/.codex/auth.json"
CODEX_UID = 10001


class ContainerProfileError(ValueError):
    """The requested launch cannot satisfy the containment contract."""


def auth_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return Path(os.environ.get("WYCKOFF_CODEX_AUTH_PATH", codex_home / "auth.json")).expanduser()


def _existing_real_file(path: Path, *, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ContainerProfileError(f"{label} must be an existing non-symlink file: {path}")
    return path.resolve()


def _inside_file(raw: str, root: Path, *, label: str) -> str:
    path = _existing_real_file(Path(raw), label=label)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ContainerProfileError(f"{label} escapes case root: {path}") from exc
    return str(CONTAINER_WORKSPACE / relative)


def translate_codex_argv(inner_argv: Sequence[str]) -> tuple[list[str], Path | None]:
    """Validate and translate Codex host paths, returning argv and case root."""
    if not inner_argv or inner_argv[0] != "codex":
        raise ContainerProfileError("wrapper accepts only commands beginning with 'codex'")
    if "--add-dir" in inner_argv:
        raise ContainerProfileError("--add-dir is forbidden by the containment profile")

    args = list(inner_argv)
    case_root: Path | None = None
    if "--cd" in args:
        index = args.index("--cd")
        try:
            raw_root = Path(args[index + 1])
        except IndexError as exc:
            raise ContainerProfileError("--cd requires a case root") from exc
        if raw_root.is_symlink() or not raw_root.is_dir():
            raise ContainerProfileError(f"case root must be an existing non-symlink directory: {raw_root}")
        case_root = raw_root.resolve()
        args[index + 1] = str(CONTAINER_WORKSPACE)

    for flag in ("--output-schema", "--image", "-i"):
        start = 0
        while flag in args[start:]:
            index = args.index(flag, start)
            if case_root is None:
                raise ContainerProfileError(f"{flag} requires --cd")
            try:
                args[index + 1] = _inside_file(args[index + 1], case_root, label=flag)
            except IndexError as exc:
                raise ContainerProfileError(f"{flag} requires a file") from exc
            start = index + 2

    # The external Docker boundary is the sandbox.  Do not claim that Seatbelt
    # inside the Linux container is providing the filesystem guarantee.
    if "--sandbox" in args:
        index = args.index("--sandbox")
        if index + 1 >= len(args):
            raise ContainerProfileError("--sandbox requires a value")
        del args[index:index + 2]
    if "--dangerously-bypass-approvals-and-sandbox" not in args and "exec" in args:
        args.insert(args.index("exec") + 1, "--dangerously-bypass-approvals-and-sandbox")
    return args, case_root


def docker_argv(
    inner_argv: Sequence[str],
    *,
    image: str = DEFAULT_IMAGE,
    auth: Path | None = None,
) -> list[str]:
    translated, case_root = translate_codex_argv(inner_argv)
    command = [
        "docker", "run", "--rm", "-i", "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges=true",
        "--tmpfs", f"/home/codex/.codex:rw,noexec,nosuid,nodev,mode=0700,uid={CODEX_UID},gid={CODEX_UID}",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev",
    ]
    if case_root is not None:
        command.extend(["--mount", f"type=bind,src={case_root},dst={CONTAINER_WORKSPACE},readonly"])
    selected_auth = auth or auth_path()
    if selected_auth.exists():
        selected_auth = _existing_real_file(selected_auth, label="Codex auth")
        command.extend(["--mount", f"type=bind,src={selected_auth},dst={CONTAINER_AUTH},readonly"])
    elif "login" in translated or "exec" in translated:
        raise ContainerProfileError(f"Codex auth file is unavailable: {selected_auth}")
    command.extend([image, *translated])
    return command


def execution_identity(*, image: str = DEFAULT_IMAGE) -> dict[str, str]:
    if shutil.which("docker") is None:
        raise ContainerProfileError("docker binary is unavailable")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .}}"],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(inspect.stdout)
    version = subprocess.run(
        docker_argv(["codex", "--version"], image=image),
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "image": image,
        "image_id": str(data["Id"]),
        "repo_digest": str((data.get("RepoDigests") or [""])[0]),
        "container_os": str(data["Os"]),
        "container_arch": str(data["Architecture"]),
        "cli_version": version,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-identity", action="store_true")
    parser.add_argument("--container-image", dest="image", default=DEFAULT_IMAGE)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.execution_identity:
            print(json.dumps(execution_identity(image=args.image), sort_keys=True))
            return 0
        if not args.command:
            raise ContainerProfileError("a Codex command is required")
        return subprocess.run(docker_argv(args.command, image=args.image)).returncode
    except (ContainerProfileError, FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"codex container unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
