"""Shared helpers for the Spike #75 chart-image feasibility canaries.

Both canaries (Claude stream-json image input, Codex `-i` image input) prove two
things in ONE paid model call each:

1. capability — the model actually receives and reads the attached chart image
   (verified by an OCR-able token rendered inside the legitimate chart);
2. isolation — a sentinel placed OUTSIDE the case/`--cd` root does NOT leak into
   the model output.  The Codex canary additionally requires a recorded, failed
   command attempt; absence from the final answer alone is not proof.

Writing/holding these scripts is zero-cost. They invoke the model only with
``--confirm``; otherwise they run as a true dry-run (construct everything, print
the argv + stdin preview, make no call).
"""

from __future__ import annotations

import secrets
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def token(prefix: str) -> str:
    """Unique, OCR-friendly sentinel token, e.g. CHART-OK-3F9A2B."""
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def make_token_image(path: Path, line1: str, line2: str = "") -> None:
    """Render a PNG whose only content is large, readable text (for vision OCR)."""
    fig = plt.figure(figsize=(6, 3), dpi=100)
    fig.patch.set_facecolor("white")
    fig.text(0.5, 0.6 if line2 else 0.5, line1, ha="center", va="center", fontsize=30, weight="bold")
    if line2:
        fig.text(0.5, 0.28, line2, ha="center", va="center", fontsize=13)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), format="png")
    plt.close(fig)


@dataclass
class CliResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_cli(argv: list[str], *, cwd: Path, stdin: str, timeout: float) -> CliResult:
    """Run a CLI once, capturing output. The single paid model call lives here."""
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        input=stdin.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return CliResult(
        argv=argv,
        returncode=proc.returncode,
        stdout=proc.stdout.decode(errors="replace"),
        stderr=proc.stderr.decode(errors="replace"),
    )


def jsonl_events(raw: str) -> list[dict]:
    """Parse JSONL output, retaining only JSON objects."""
    events: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            events.append(value)
    return events


def extract_structured_output(events: list[dict]) -> dict | None:
    """Extract a structured final response from Claude or Codex JSONL."""
    for event in reversed(events):
        candidates = [event.get("structured_output"), event.get("result")]
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"}:
            candidates.append(item.get("text"))
        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate
            if isinstance(candidate, str):
                try:
                    decoded = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(decoded, dict):
                    return decoded
    return None


def failure_detail(events: list[dict]) -> str:
    """Summarize structured CLI failure events without assuming one schema."""
    for event in reversed(events):
        event_type = str(event.get("type", ""))
        if any(marker in event_type for marker in ("fail", "error")):
            return json.dumps(event, sort_keys=True)[:1000]
        if event.get("error"):
            return json.dumps(event, sort_keys=True)[:1000]
    return "no structured failure event found"


def command_attempt(events: list[dict], path: Path) -> tuple[bool, bool, str]:
    """Return whether Codex attempted and was blocked reading ``path``.

    Only command-execution items count.  A path echoed in a prompt or final
    answer is intentionally insufficient evidence.
    """
    needle = str(path)
    matches: list[dict] = []
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or "command" not in str(item.get("type", "")):
            continue
        rendered = json.dumps(item, sort_keys=True)
        if needle not in rendered:
            continue
        matches.append(item)
    if not matches:
        return False, False, "no command-execution item referenced the outside path"

    # Codex emits an in_progress item and later a terminal item with the same
    # command id.  Prefer the last terminal event; evaluating the first event
    # produces a false negative before the sandbox result exists.
    terminal = [
        item
        for item in matches
        if isinstance(item.get("exit_code"), int)
        or str(item.get("status", "")).lower() in {"completed", "failed", "error", "denied", "blocked"}
    ]
    item = terminal[-1] if terminal else matches[-1]
    rendered = json.dumps(item, sort_keys=True)
    exit_code = item.get("exit_code")
    status = str(item.get("status", "")).lower()
    output = str(item.get("aggregated_output", item.get("output", ""))).lower()
    blocked = (
        isinstance(exit_code, int) and exit_code != 0
    ) or status in {"failed", "error", "denied", "blocked"} or any(
        marker in output
        for marker in ("permission denied", "operation not permitted", "sandbox", "denied")
    )
    return True, blocked, rendered


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class Verdict:
    provider: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(name, passed, detail))

    @property
    def gate_pass(self) -> bool:
        return all(c.passed for c in self.checks)

    def render(self) -> str:
        lines = [f"\n=== Canary verdikt: {self.provider} ==="]
        for c in self.checks:
            mark = "PROŠAO" if c.passed else "PAO"
            lines.append(f"  [{mark}] {c.name} — {c.detail}")
        lines.append(f"  GEJT: {'PROŠAO ✅' if self.gate_pass else 'PAO ❌'}")
        return "\n".join(lines)


def print_dry_run(argv: list[str], cwd: Path, stdin_preview: str) -> None:
    print("=== DRY-RUN (bez model poziva) — dodaj --confirm za stvarni poziv ===")
    print(f"cwd: {cwd}")
    print("argv:")
    print("  " + " ".join(repr(a) if (a == "" or " " in a) else a for a in argv))
    print("stdin (preview, slika skraćena):")
    print(stdin_preview)
