#!/usr/bin/env python3
"""Fail-closed Codex launcher used only by expert-ingest Spona runs.

Spona v0.1.0 exposes ``--codex-bin`` and ``--codex-sandbox`` but cannot pass
Codex's ``--ignore-user-config``/``--ephemeral``, disable browser/app/plugin/web
capabilities, or lock reasoning effort. This shim keeps Spona's normal argv
contract while injecting the least-write Codex policy that still permits wiki
workspace edits and fixes gpt-5.6-sol reasoning to medium.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def build_safe_argv(real_codex: str, supplied: list[str]) -> list[str]:
    if not supplied or supplied[0] != "exec":
        raise ValueError("safe expert-ingest launcher podržava samo `codex exec`")
    models: list[str] = []
    for index, arg in enumerate(supplied):
        if arg in {"-m", "--model"}:
            if index + 1 >= len(supplied):
                raise ValueError(f"{arg} nema vrednost")
            models.append(supplied[index + 1])
        elif arg.startswith("--model="):
            models.append(arg.split("=", 1)[1])
        if arg in {"-c", "--config"} and index + 1 < len(supplied):
            config_value = supplied[index + 1]
        elif arg.startswith("--config=") or arg.startswith("-c="):
            config_value = arg.split("=", 1)[1]
        else:
            continue
        if config_value.split("=", 1)[0].strip() == "model_reasoning_effort":
            raise ValueError("model_reasoning_effort override nije dozvoljen")
    if models != ["gpt-5.6-sol"]:
        raise ValueError(
            "safe expert-ingest launcher zahteva tačno jedan gpt-5.6-sol model"
        )
    return [
        real_codex,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--disable",
        "browser_use",
        "--disable",
        "apps",
        "--disable",
        "plugins",
        "-c",
        'web_search="disabled"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        'model_reasoning_effort="medium"',
        *supplied[1:],
    ]


def main(argv: list[str] | None = None) -> int:
    supplied = list(sys.argv[1:] if argv is None else argv)
    real_codex = shutil.which("codex")
    if real_codex is None or Path(real_codex).resolve() == Path(__file__).resolve():
        print(
            "safe expert-ingest launcher: pravi `codex` nije pronađen", file=sys.stderr
        )
        return 127
    try:
        command = build_safe_argv(real_codex, supplied)
    except ValueError as exc:
        print(f"safe expert-ingest launcher: {exc}", file=sys.stderr)
        return 2
    os.execv(real_codex, command)
    raise AssertionError("os.execv se neočekivano vratio")


if __name__ == "__main__":
    raise SystemExit(main())
