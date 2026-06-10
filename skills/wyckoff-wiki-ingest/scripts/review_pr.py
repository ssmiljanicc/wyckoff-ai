#!/usr/bin/env python3
"""Mechanical pre-merge review for batch PR.

Runs 6 checks against the PR's diff:
1. Provenance frontmatter — every new wiki page has `sources:` with valid raw/ paths;
   if `primary_source:` is present it must match a raw/ folder name
2. Inline citation links — every `[text](path)` resolves from the page's actual depth
3. Cross-references — `[[name]]` links point to pages that exist (or are flagged future-batch)
4. Index/log update — knowledge/wiki/{index,log}.md have new batch entries
5. Style consistency — new pages have Summary + Key Points sections
6. WIKI_GAP markers — no unjustified gaps in wiki pages

Usage:
    uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py 38

Exit code:
    0 — all checks PASS
    1 — at least one FAIL (Serbian report printed)
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]\n|]+)(?:\|[^\]]+)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SOURCES_PATH_RE = re.compile(r"^\s*-\s*path:\s*(\S+)", re.MULTILINE)
PRIMARY_SOURCE_RE = re.compile(r"^\s*primary_source:\s*(\S+)", re.MULTILINE)


def is_generated_health_report(path: Path, wt: Path) -> bool:
    try:
        rel = path.relative_to(wt)
    except ValueError:
        return False
    return (
        len(rel.parts) == 4
        and rel.parts[:3] == ("knowledge", "wiki", "health")
        and rel.name.startswith("citation-audit-")
        and rel.suffix == ".md"
    )


def allowed_primary_sources(wt: Path) -> set[str]:
    """Allowed primary_source values = the raw/ subfolder names (derived, not hardcoded)."""
    raw = wt / "raw"
    if not raw.is_dir():
        return set()
    return {p.name for p in raw.iterdir() if p.is_dir()}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, check=check)
    return res.stdout


def setup_worktree(pr_number: int) -> Path:
    ref = f"refs/remotes/origin/pr/{pr_number}"
    subprocess.run(
        ["git", "fetch", "origin", f"pull/{pr_number}/head:{ref}"],
        check=True, capture_output=True, cwd=REPO_ROOT,
    )
    wt = Path(tempfile.mkdtemp(prefix=f"wyckoff-pr{pr_number}-"))
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt), ref],
        check=True, capture_output=True, cwd=REPO_ROOT,
    )
    return wt


def cleanup_worktree(wt: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO_ROOT, capture_output=True)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)


def files_in_pr(wt: Path, pr_number: int) -> tuple[list[Path], list[Path]]:
    """Return (added_files, modified_files) for wiki .md files in the PR."""
    diff = subprocess.run(
        ["git", "diff", "--name-status", f"origin/main...refs/remotes/origin/pr/{pr_number}", "--", "knowledge/wiki"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    added, modified = [], []
    for line in diff.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].endswith(".md"):
            p = wt / parts[1]
            if parts[0] == "A":
                added.append(p)
            elif parts[0] == "M":
                modified.append(p)
    return added, modified


def check_frontmatter(files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    issues = []
    allowed_ps = allowed_primary_sources(wt)
    for f in files:
        rel = f.relative_to(wt)
        if is_generated_health_report(f, wt):
            continue
        if rel.name in ("index.md", "log.md", "README.md"):
            continue
        text = f.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            issues.append(f"{rel}: nema frontmatter-a")
            continue
        fm = m.group(1)
        sources = SOURCES_PATH_RE.findall(fm)
        if not sources:
            issues.append(f"{rel}: prazan ili nepostojeći `sources:` blok")
            continue
        for src in sources:
            if not (wt / src).exists():
                issues.append(f"{rel}: sources path `{src}` ne postoji u repo-u")
        # primary_source (optional): if present, value must match a raw/ folder name
        ps_match = PRIMARY_SOURCE_RE.search(fm)
        if ps_match and allowed_ps:
            ps_val = ps_match.group(1)
            if ps_val not in allowed_ps:
                issues.append(
                    f"{rel}: primary_source `{ps_val}` nije validan "
                    f"(dozvoljeno: {', '.join(sorted(allowed_ps))})"
                )
    return len(issues) == 0, issues


def check_inline_links(files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    issues = []
    for f in files:
        rel = f.relative_to(wt)
        if is_generated_health_report(f, wt):
            continue
        if rel.name in ("index.md", "log.md", "README.md"):
            continue
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in LINK_RE.finditer(line):
                target = m.group(2)
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                resolved = (f.parent / target_path).resolve()
                if not resolved.exists():
                    issues.append(f"{rel}:L{lineno}: [{m.group(1)}]({target}) ne razrešava")
    return len(issues) == 0, issues


def check_cross_references(files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    wiki_root = wt / "knowledge" / "wiki"
    # Build lookup accepting both [[spring]] and [[events/spring]] forms
    all_slugs: set[str] = set()
    for p in wiki_root.rglob("*.md"):
        all_slugs.add(p.stem)
        try:
            folder_slug = "/".join(p.relative_to(wiki_root).with_suffix("").parts)
            all_slugs.add(folder_slug)
        except ValueError:
            pass

    issues = []
    for f in files:
        rel = f.relative_to(wt)
        if is_generated_health_report(f, wt):
            continue
        if rel.name in ("index.md", "log.md", "README.md"):
            continue
        text = f.read_text(encoding="utf-8")
        for m in WIKILINK_RE.finditer(text):
            target_slug = m.group(1).strip().replace(" ", "-").lower()
            if target_slug not in all_slugs:
                issues.append(f"{rel}: [[{m.group(1)}]] → stranica ne postoji")
    return len(issues) == 0, issues


def check_index_log_update(added_files: list[Path], all_files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    # Only require index/log update when the PR adds NEW wiki content pages
    new_content = [
        f for f in added_files
        if f.name not in ("index.md", "log.md", "README.md")
        and "knowledge/wiki" in str(f)
        and not is_generated_health_report(f, wt)
    ]
    if not new_content:
        return True, []
    issues = []
    index_changed = any(f.name == "index.md" for f in all_files)
    log_changed = any(f.name == "log.md" for f in all_files)
    if not index_changed:
        issues.append("knowledge/wiki/index.md nije izmenjen u PR-u")
    if not log_changed:
        issues.append("knowledge/wiki/log.md nije izmenjen u PR-u")
    return len(issues) == 0, issues


def check_style(files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    issues = []
    for f in files:
        rel = f.relative_to(wt)
        if is_generated_health_report(f, wt):
            continue
        if rel.name in ("index.md", "log.md", "README.md"):
            continue
        # source summary pages have different format
        if "sources/" in str(rel):
            continue
        text = f.read_text(encoding="utf-8")
        if "## Summary" not in text:
            issues.append(f"{rel}: nedostaje `## Summary` sekcija")
        if "## Key Points" not in text and "## Key " not in text:
            issues.append(f"{rel}: nedostaje `## Key Points` sekcija")
    return len(issues) == 0, issues


def check_wiki_gap(files: list[Path], wt: Path) -> tuple[bool, list[str]]:
    issues = []
    for f in files:
        rel = f.relative_to(wt)
        if is_generated_health_report(f, wt):
            continue
        if rel.name == "log.md":
            continue
        text = f.read_text(encoding="utf-8")
        if "WIKI_GAP" in text:
            # OK if explicitly in a gap section; flag otherwise
            issues.append(f"{rel}: ima WIKI_GAP marker — proveri kontekst u log.md")
    # WIKI_GAP markers are not necessarily a fail; just info
    return True, issues


def print_section(name: str, passed: bool, issues: list[str]) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"\n## {name}: {status}")
    if issues:
        for i in issues[:10]:
            print(f"  - {i}")
        if len(issues) > 10:
            print(f"  - ... još {len(issues) - 10}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mechanical pre-merge PR review")
    parser.add_argument("pr_number", type=int, help="PR number")
    args = parser.parse_args()

    wt = setup_worktree(args.pr_number)
    try:
        added, modified = files_in_pr(wt, args.pr_number)
        all_files = added + modified
        if not all_files:
            print(f"PR #{args.pr_number}: nema izmenjenih .md fajlova u knowledge/wiki/")
            return 0

        print(f"PR #{args.pr_number}: {len(added)} novih + {len(modified)} izmenjenih fajlova\n")

        results = []
        # Frontmatter/style/gaps: samo novi fajlovi (dodati, ne modifikovani)
        fm_pass, fm_issues = check_frontmatter(added, wt)
        results.append(("Provenance frontmatter", fm_pass, fm_issues))

        # Inline links: i novi i modifikovani (fix mora biti tačan u oba)
        link_pass, link_issues = check_inline_links(all_files, wt)
        results.append(("Inline citation links", link_pass, link_issues))

        # Cross-references: samo novi fajlovi (forward-refs u postojećim su OK)
        xref_pass, xref_issues = check_cross_references(added, wt)
        results.append(("Cross-references [[name]]", xref_pass, xref_issues))

        # Index/log: obavezno samo ako postoje novi content fajlovi
        idx_pass, idx_issues = check_index_log_update(added, all_files, wt)
        results.append(("Index/log update", idx_pass, idx_issues))

        style_pass, style_issues = check_style(added, wt)
        results.append(("Style consistency", style_pass, style_issues))

        gap_pass, gap_issues = check_wiki_gap(all_files, wt)
        results.append(("WIKI_GAP markeri (info)", gap_pass, gap_issues))

        for name, p, issues in results:
            print_section(name, p, issues)

        all_passed = all(p for _, p, _ in results)
        print()
        print("=" * 50)
        if all_passed:
            print(f"✓ PR #{args.pr_number}: SVI MEHANIČKI CHECK-OVI PROLAZE")
            return 0
        else:
            failed = [n for n, p, _ in results if not p]
            print(f"✗ PR #{args.pr_number}: FAIL u sekcijama: {', '.join(failed)}")
            return 1
    finally:
        cleanup_worktree(wt)


if __name__ == "__main__":
    sys.exit(main())
