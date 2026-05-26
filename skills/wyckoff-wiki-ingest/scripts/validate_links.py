#!/usr/bin/env python3
"""Validate inline citation links in knowledge/wiki/ pages.

Checks that every `[text](relative/path)` link in a wiki .md file resolves
to a file that actually exists on disk, relative to the .md file's location.

Usage:
    uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
    uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py --pr 38
    uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py --json

Exit code:
    0 — all links resolve
    1 — at least one broken link (details printed)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = REPO_ROOT / "knowledge" / "wiki"

# Inline link with relative path (skips http(s), [[wiki-links]], and image refs handled separately)
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)\)")


def files_to_check(pr_number: int | None) -> list[Path]:
    if pr_number is None:
        return sorted(WIKI_DIR.rglob("*.md"))

    # PR mode: use git to diff against origin/main
    ref = f"origin/pr/{pr_number}"
    try:
        subprocess.run(
            ["git", "fetch", "origin", f"pull/{pr_number}/head:refs/remotes/{ref}"],
            check=True,
            capture_output=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError as e:
        print(f"git fetch failed: {e.stderr.decode()}", file=sys.stderr)
        sys.exit(2)

    diff = subprocess.run(
        ["git", "diff", "--name-only", f"origin/main...{ref}", "--", "knowledge/wiki"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return [REPO_ROOT / p for p in diff.stdout.splitlines() if p.endswith(".md")]


def validate_file(path: Path) -> list[tuple[int, str, str, Path]]:
    """Return list of (lineno, link_text, link_target, resolved_path) for broken links."""
    broken: list[tuple[int, str, str, Path]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return broken

    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in LINK_RE.finditer(line):
            target = m.group(2)
            # Skip absolute URLs and anchor-only links
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            # Strip trailing #anchor
            target_path_part = target.split("#", 1)[0]
            if not target_path_part:
                continue
            resolved = (path.parent / target_path_part).resolve()
            if not resolved.exists():
                broken.append((lineno, m.group(1), target, resolved))
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wiki citation links")
    parser.add_argument("--pr", type=int, help="Check only files in given PR")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    files = files_to_check(args.pr)
    if not files:
        print("No wiki .md files to check.")
        return 0

    all_broken: dict[str, list[tuple[int, str, str, str]]] = defaultdict(list)
    for f in files:
        if not f.exists() or "knowledge/wiki" not in str(f):
            continue
        broken = validate_file(f)
        if broken:
            rel = f.relative_to(REPO_ROOT)
            for lineno, link_text, target, resolved in broken:
                all_broken[str(rel)].append(
                    (lineno, link_text, target, str(resolved.relative_to(REPO_ROOT)) if resolved.is_relative_to(REPO_ROOT) else str(resolved))
                )

    total_broken = sum(len(v) for v in all_broken.values())

    if args.json:
        out = {
            "files_checked": len(files),
            "files_with_broken_links": len(all_broken),
            "total_broken_links": total_broken,
            "broken": {
                f: [{"lineno": ln, "text": t, "target": tg, "resolved": r} for ln, t, tg, r in v]
                for f, v in all_broken.items()
            },
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if total_broken == 0 else 1

    # Human-readable Serbian report
    print(f"Provereno fajlova: {len(files)}")
    print(f"Fajlovi sa broken linkovima: {len(all_broken)}")
    print(f"Ukupno broken linkova: {total_broken}")

    if total_broken == 0:
        print("\n✓ Svi inline linkovi razrešavaju.")
        return 0

    print()
    for f, broken in sorted(all_broken.items()):
        print(f"\n{f} ({len(broken)} broken)")
        for lineno, link_text, target, resolved in broken[:5]:
            print(f"  L{lineno}: [{link_text}]({target}) → {resolved} NE POSTOJI")
        if len(broken) > 5:
            print(f"  ... još {len(broken) - 5}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
