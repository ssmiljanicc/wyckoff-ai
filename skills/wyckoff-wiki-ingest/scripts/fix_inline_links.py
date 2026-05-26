#!/usr/bin/env python3
"""Fix inline citation link depth bug in knowledge/wiki/ pages.

The bug: Opus copied the example from CLAUDE.md §5 verbatim (`../../raw/...`),
which only resolves for pages 2 levels deep. All real wiki pages are 3 or
4 levels deep.

This script:
1. Walks every .md file under knowledge/wiki/
2. Finds inline links that point into `raw/` but don't resolve from the
   page's actual depth
3. Adjusts the `../` prefix to the correct depth so the link resolves
4. Idempotent — links that already resolve are not touched

Usage:
    uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py --dry-run
    uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = REPO_ROOT / "knowledge" / "wiki"

# Match `[text](relative/path/that/includes/raw/...)`
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(((?:\.\./)+raw/[^)\s]+)\)")


def correct_depth_for(page: Path) -> int:
    """How many `../` segments are needed to reach repo root from `page`."""
    rel = page.relative_to(REPO_ROOT)
    # rel.parts excludes the file name only if parent is included; use parents count
    return len(rel.parts) - 1  # number of directories above the file


def fix_link(page: Path, link_target: str) -> str | None:
    """Return corrected link target if needed, else None."""
    # Count current `../` prefix
    m = re.match(r"^((?:\.\./)+)(raw/.+)$", link_target)
    if not m:
        return None
    prefix, tail = m.group(1), m.group(2)
    current_depth = prefix.count("../")
    needed = correct_depth_for(page)

    # Verify needed by resolving:
    candidate = (page.parent / link_target).resolve()
    if candidate.exists():
        return None  # already correct

    # Try corrected depth
    new_prefix = "../" * needed
    new_target = new_prefix + tail
    new_resolved = (page.parent / new_target).resolve()
    if new_resolved.exists():
        return new_target

    return None  # couldn't auto-fix; leave for manual review


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    """Return (fixed_count, unfixable_count) for the file."""
    text = path.read_text(encoding="utf-8")
    fixed = 0
    unfixable = 0
    new_text = text

    # Process all matches; do it via regex sub with callback
    def replace(m: re.Match[str]) -> str:
        nonlocal fixed, unfixable
        link_text = m.group(1)
        target = m.group(2)
        corrected = fix_link(path, target)
        if corrected is None:
            # Check if it already resolves
            if (path.parent / target).resolve().exists():
                return m.group(0)  # no change needed
            unfixable += 1
            return m.group(0)
        fixed += 1
        return f"[{link_text}]({corrected})"

    new_text = LINK_RE.sub(replace, text)

    if new_text != text and not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return fixed, unfixable


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix inline citation link depth")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    args = parser.parse_args()

    total_fixed = 0
    total_unfixable = 0
    files_changed: list[tuple[Path, int]] = []

    for f in sorted(WIKI_DIR.rglob("*.md")):
        fixed, unfixable = process_file(f, args.dry_run)
        if fixed:
            files_changed.append((f.relative_to(REPO_ROOT), fixed))
        total_fixed += fixed
        total_unfixable += unfixable

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] Fajlovi promenjeni: {len(files_changed)}")
    print(f"[{mode}] Linkovi popravljeni: {total_fixed}")
    print(f"[{mode}] Linkovi koji se ne mogu auto-fix-ovati: {total_unfixable}")
    if files_changed:
        print()
        for f, count in files_changed:
            print(f"  {f} ({count} fix)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
