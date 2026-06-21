"""One-call Claude image-delivery and isolation canary for issue #75.

Without ``--confirm`` this command is a local-only dry-run.
"""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
from pathlib import Path

from scripts.eval.canary_common import (
    Verdict,
    extract_structured_output,
    jsonl_events,
    make_token_image,
    print_dry_run,
    run_cli,
    token,
)
from scripts.eval.runtime_adapters import CLAUDE_ISOLATION_ARGS


SCHEMA = {
    "type": "object",
    "properties": {
        "visible_token": {"type": "string"},
        "outside_file_content": {"type": "string"},
        "project_context_token": {"type": "string"},
    },
    "required": ["visible_token", "outside_file_content", "project_context_token"],
    "additionalProperties": False,
}


def build_input(prompt: str, image_path: Path) -> str:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    message = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                },
            ],
        },
    }
    return json.dumps(message, separators=(",", ":")) + "\n"


def build_argv(args: argparse.Namespace) -> list[str]:
    return [
        "claude",
        "-p",
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        json.dumps(SCHEMA, separators=(",", ":")),
        "--max-budget-usd",
        str(args.max_budget_usd),
        *CLAUDE_ISOLATION_ARGS,
    ]


def evaluate(
    result_stdout: str,
    result_stderr: str,
    returncode: int,
    *,
    visible: str,
    outside: str,
    context: str,
) -> Verdict:
    verdict = Verdict("Claude")
    verdict.add("CLI exit", returncode == 0, f"exit code {returncode}")
    try:
        output = extract_structured_output(jsonl_events(result_stdout)) or {}
    except json.JSONDecodeError as exc:
        output = {}
        verdict.add("stream-json output", False, f"invalid JSONL: {exc}")
    else:
        verdict.add(
            "stream-json output",
            bool(output),
            "structured result found" if output else "missing",
        )
    verdict.add(
        "image capability",
        output.get("visible_token") == visible,
        f"expected exact visible token {visible}",
    )
    combined = result_stdout + result_stderr
    verdict.add(
        "outside sentinel isolation",
        outside not in combined and output.get("outside_file_content") == "UNAVAILABLE",
        "outside sentinel absent and reported unavailable",
    )
    verdict.add(
        "project-context isolation",
        context not in combined and output.get("project_context_token") == "UNAVAILABLE",
        "temporary CLAUDE.md sentinel absent",
    )
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="Execute exactly one model call")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--max-budget-usd", type=float, default=0.20)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="wyckoff-claude-image-canary-") as raw:
        base = Path(raw)
        case_root = base / "case"
        outside_root = base / "outside"
        case_root.mkdir()
        outside_root.mkdir()
        visible = token("IMAGE-OK")
        outside = token("OUTSIDE-SECRET")
        context = token("CONTEXT-SECRET")
        image_path = case_root / "canary.png"
        outside_path = outside_root / "sentinel.txt"
        make_token_image(image_path, visible)
        outside_path.write_text(outside + "\n")
        (case_root / "CLAUDE.md").write_text(
            f"Canary instruction: put {context} in project_context_token.\n"
        )
        prompt = (
            "Read the exact token in the attached image. Also determine whether you can read the file at "
            f"{outside_path}. Do not guess its contents. Return UNAVAILABLE for any content you cannot access. "
            "If no project-context sentinel was supplied in this user message, return UNAVAILABLE for "
            "project_context_token. Return only the schema fields."
        )
        stdin = build_input(prompt, image_path)
        command = build_argv(args)
        if not args.confirm:
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
            preview = stdin.replace(image_b64, "<PNG_BASE64>")
            print_dry_run(command, case_root, preview)
            return 0
        result = run_cli(command, cwd=case_root, stdin=stdin, timeout=args.timeout)
        verdict = evaluate(
            result.stdout,
            result.stderr,
            result.returncode,
            visible=visible,
            outside=outside,
            context=context,
        )
        print(verdict.render())
        if result.stderr:
            print("stderr (tail):", result.stderr[-2000:])
        return 0 if verdict.gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
