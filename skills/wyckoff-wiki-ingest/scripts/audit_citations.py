#!/usr/bin/env python3
"""Audit wiki citations for likely source misattribution.

Layer-1 checks are deterministic and stdlib-only:
1. cited raw page is image-only
2. direct blockquote is not found verbatim in the cited raw page
3. cited raw book page looks like a section-boundary page
4. frontmatter sources and inline raw citations have parity
5. page-range citations are sane

Usage:
    uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py
    uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --pr 57
    uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json
    uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --self-check

Exit code:
    0 - no flags
    1 - at least one suspicious citation flag
    2 - execution/setup error
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = REPO_ROOT / "knowledge" / "wiki"

LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)\)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SOURCES_PATH_RE = re.compile(r"^\s*-\s*path:\s*(\S+)", re.MULTILINE)
BOOK_PAGE_RE = re.compile(r"raw/book/pages/page_(\d{3})\.md$")
PAGE_TOKEN_RE = re.compile(r"(?:p\.\s*)?(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?", re.IGNORECASE)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")
HARD_CODES = {
    "frontmatter_missing",
    "image_only",
    "missing_raw",
    "quote_not_found",
    "range_missing_frontmatter",
    "range_missing_raw",
    "range_target",
}
WARNING_CODES = {"inline_missing", "section_boundary"}


class AuditSetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class Citation:
    kind: str
    source: str
    path: Path
    raw_path: str
    lineno: int
    label: str
    target: str
    pages: tuple[int, ...]


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    file: str
    line: int
    citation: str
    raw_path: str
    detail: str


def run(cmd: list[str], check: bool = True) -> str:
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=check)
    return res.stdout


def files_to_check(pr_number: int | None) -> list[Path]:
    if pr_number is None:
        return [p for p in sorted(WIKI_DIR.rglob("*.md")) if is_auditable_wiki_file(p)]

    ref = f"origin/pr/{pr_number}"
    try:
        subprocess.run(
            ["git", "fetch", "origin", f"pull/{pr_number}/head:refs/remotes/{ref}"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError as e:
        raise AuditSetupError(f"git fetch failed: {e.stderr.strip()}") from e

    try:
        diff = subprocess.run(
            ["git", "diff", "--name-status", f"origin/main...{ref}", "--", "knowledge/wiki"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError as e:
        raise AuditSetupError(f"git diff failed: {e.stderr.strip()}") from e

    files: list[Path] = []
    missing: list[str] = []
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or parts[0].startswith("D") or not parts[1].endswith(".md"):
            continue
        path = REPO_ROOT / parts[1]
        if not is_auditable_wiki_file(path):
            continue
        if not path.exists():
            missing.append(parts[1])
            continue
        files.append(path)
    if missing:
        raise AuditSetupError(
            "PR diff contains wiki file(s) absent from the current worktree: "
            + ", ".join(missing)
            + ". Run gh pr checkout or audit the fetched ref explicitly."
        )
    return files


def is_auditable_wiki_file(path: Path) -> bool:
    try:
        rel_path = path.relative_to(WIKI_DIR)
    except ValueError:
        return False
    return not rel_path.parts or rel_path.parts[0] != "health"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def strip_markdown_noise(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = text.replace("\u2026", " ")
    return text


def normalize_text(text: str) -> str:
    text = strip_markdown_noise(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_tokens(text: str) -> list[str]:
    return normalize_text(text).split()


def distinctive_phrase(text: str, max_words: int = 12) -> str:
    words = WORD_RE.findall(strip_markdown_noise(text))
    return " ".join(words[:max_words])


def parse_book_pages(label: str) -> tuple[int, ...]:
    if "p." not in label.lower():
        return ()
    pages: list[int] = []
    for match in PAGE_TOKEN_RE.finditer(label):
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        if end < start:
            continue
        pages.extend(range(start, end + 1))
    return tuple(dict.fromkeys(pages))


def book_page_from_raw_path(raw_path: str) -> int | None:
    match = BOOK_PAGE_RE.search(raw_path)
    return int(match.group(1)) if match else None


def parse_frontmatter_sources(path: Path, text: str) -> list[Citation]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return []
    citations: list[Citation] = []
    for lineno, line in enumerate(text[: match.end(1)].splitlines(), start=1):
        source_match = re.match(r"^\s*-\s*path:\s*(\S+)", line)
        if not source_match:
            continue
        raw_path = source_match.group(1)
        page = book_page_from_raw_path(raw_path)
        pages = (page,) if page is not None else ()
        citations.append(
            Citation(
                kind="frontmatter",
                source=raw_path,
                path=path,
                raw_path=raw_path,
                lineno=lineno,
                label=raw_path,
                target=raw_path,
                pages=pages,
            )
        )
    return citations


def parse_inline_citations(path: Path, text: str) -> list[Citation]:
    citations: list[Citation] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in LINK_RE.finditer(line):
            label = match.group(1)
            target = match.group(2)
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            raw_path = rel(resolved)
            if not raw_path.startswith("raw/"):
                continue
            citations.append(
                Citation(
                    kind="inline",
                    source=line.strip(),
                    path=path,
                    raw_path=raw_path,
                    lineno=lineno,
                    label=label,
                    target=target,
                    pages=parse_book_pages(label),
                )
            )
    return citations


def read_raw(raw_path: str) -> str:
    path = REPO_ROOT / raw_path
    if not path.exists():
        raise FileNotFoundError(raw_path)
    return path.read_text(encoding="utf-8")


def is_image_only(raw_text: str) -> bool:
    meaningful: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = MARKDOWN_IMAGE_RE.sub("", stripped).strip()
        if stripped:
            meaningful.append(stripped)
    return bool(raw_text.strip()) and not meaningful


def uppercase_tail_heading(raw_text: str) -> str | None:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    tail = lines[-1]
    if MARKDOWN_IMAGE_RE.fullmatch(tail):
        return None
    if len(tail) < 8 or len(tail) > 80:
        return None
    letters = [ch for ch in tail if ch.isalpha()]
    if len(letters) < 6:
        return None
    uppercase_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
    words = WORD_RE.findall(tail)
    if uppercase_ratio >= 0.85 and len(words) <= 8:
        return tail
    return None


def severity_for_code(code: str) -> str:
    if code in WARNING_CODES:
        return "WARNING"
    if code in HARD_CODES or code.startswith("range_"):
        return "HARD"
    return "FLAG"


def issue_for(citation: Citation, code: str, detail: str, severity: str | None = None) -> Issue:
    return Issue(
        code=code,
        severity=severity or severity_for_code(code),
        file=rel(citation.path),
        line=citation.lineno,
        citation=citation.label if citation.kind == "inline" else citation.raw_path,
        raw_path=citation.raw_path,
        detail=detail,
    )


def check_raw_content(citations: list[Citation]) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[tuple[str, int, str]] = set()
    for citation in citations:
        if not citation.raw_path.startswith("raw/"):
            continue
        try:
            raw_text = read_raw(citation.raw_path)
        except FileNotFoundError:
            issues.append(
                issue_for(
                    citation,
                    "missing_raw",
                    "cited raw path does not exist",
                )
            )
            continue
        key = (citation.raw_path, citation.lineno, citation.kind)
        if is_image_only(raw_text) and key not in seen:
            seen.add(key)
            issues.append(
                issue_for(
                    citation,
                    "image_only",
                    "cited raw page contains only markdown image references and no prose",
                )
            )
        tail = uppercase_tail_heading(raw_text)
        if tail and key not in seen:
            if citation.kind == "inline" and citation.pages:
                cited_page = book_page_from_raw_path(citation.raw_path)
                if cited_page is not None and cited_page < max(citation.pages):
                    continue
            seen.add(key)
            issues.append(
                issue_for(
                    citation,
                    "section_boundary",
                    f"cited book page ends with uppercase heading only: {tail!r}; check next page for supporting prose",
                )
            )
    return issues


def frontmatter_inline_parity(
    path: Path, frontmatter: list[Citation], inline: list[Citation]
) -> list[Issue]:
    issues: list[Issue] = []
    fm_paths = {c.raw_path for c in frontmatter}
    inline_paths = {c.raw_path for c in inline}

    for citation in inline:
        expected_paths = range_paths_for_inline(citation)
        missing = sorted(p for p in expected_paths if p not in fm_paths)
        if missing:
            issues.append(
                issue_for(
                    citation,
                    "frontmatter_missing",
                    "inline citation has no matching frontmatter source(s): " + ", ".join(missing),
                )
            )

    for citation in frontmatter:
        if citation.raw_path not in inline_paths:
            issues.append(
                issue_for(
                    citation,
                    "inline_missing",
                    "frontmatter source is not cited inline on this page",
                )
            )
    return issues


def range_paths_for_inline(citation: Citation) -> tuple[str, ...]:
    if not citation.pages:
        return (citation.raw_path,)
    if not citation.raw_path.startswith("raw/book/pages/page_"):
        return (citation.raw_path,)
    return tuple(f"raw/book/pages/page_{page:03d}.md" for page in citation.pages)


def check_range_sanity(inline: list[Citation], frontmatter: list[Citation]) -> list[Issue]:
    issues: list[Issue] = []
    fm_paths = {c.raw_path for c in frontmatter}
    for citation in inline:
        if len(citation.pages) <= 1:
            continue
        expected = range_paths_for_inline(citation)
        if citation.raw_path != expected[0]:
            issues.append(
                issue_for(
                    citation,
                    "range_target",
                    f"range citation should link to first page {expected[0]}, got {citation.raw_path}",
                )
            )
        missing_files = [p for p in expected if not (REPO_ROOT / p).exists()]
        if missing_files:
            issues.append(
                issue_for(
                    citation,
                    "range_missing_raw",
                    "range citation points across missing raw page(s): " + ", ".join(missing_files),
                )
            )
        missing_fm = [p for p in expected if p not in fm_paths]
        if missing_fm:
            issues.append(
                issue_for(
                    citation,
                    "range_missing_frontmatter",
                    "range citation page(s) absent from frontmatter: " + ", ".join(missing_fm),
                )
            )
    return issues


def find_nearby_citation(block_start: int, block_end: int, lines: list[str], inline: list[Citation]) -> Citation | None:
    by_line: dict[int, list[Citation]] = defaultdict(list)
    for citation in inline:
        by_line[citation.lineno].append(citation)

    for lineno in range(block_start, block_end + 1):
        if by_line.get(lineno):
            return by_line[lineno][0]
    for lineno in range(block_start - 3, block_start):
        if lineno >= 1 and by_line.get(lineno):
            return by_line[lineno][0]
    for lineno in range(block_end + 1, min(len(lines), block_end + 3) + 1):
        if by_line.get(lineno):
            return by_line[lineno][0]
    return None


def is_attribution_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"\(?\s*\[[^\]]+\]\([^)]+\)\s*\)?", stripped))


def clean_quote_line(line: str) -> str:
    line = re.sub(r"\s+[—-]\s*\[[^\]]+\]\([^)]+\)\s*$", "", line)
    return line.strip()


def quote_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    start: int | None = None
    collected: list[str] = []
    skip_synthesis = False
    for idx, line in enumerate(lines, start=1):
        if line.startswith(">"):
            stripped = line.lstrip("> ").strip()
            if stripped.startswith("**Synthesis:**"):
                if start is not None:
                    blocks.append((start, idx - 1, " ".join(collected)))
                    start = None
                    collected = []
                skip_synthesis = True
                continue
            if skip_synthesis:
                continue
            if start is None:
                start = idx
            if not is_attribution_line(stripped):
                collected.append(clean_quote_line(stripped))
            continue
        skip_synthesis = False
        if start is not None:
            blocks.append((start, idx - 1, " ".join(collected)))
            start = None
            collected = []
    if start is not None:
        blocks.append((start, len(lines), " ".join(collected)))
    return blocks


def fuzzy_quote_found(quote: str, raw_text: str) -> bool:
    quote_tokens = normalized_tokens(quote)
    raw_tokens = normalized_tokens(raw_text)
    if len(quote_tokens) < 6 or len(raw_tokens) < 6:
        return False

    raw_norm = " ".join(raw_tokens)
    max_ngram = min(10, len(quote_tokens))
    for ngram_size in range(max_ngram, 5, -1):
        for idx in range(0, len(quote_tokens) - ngram_size + 1):
            if " ".join(quote_tokens[idx : idx + ngram_size]) in raw_norm:
                return True

    quote_joined = " ".join(quote_tokens)
    min_window = max(6, int(len(quote_tokens) * 0.75))
    max_window = min(len(raw_tokens), int(len(quote_tokens) * 1.6) + 6)
    for window_size in range(min_window, max_window + 1):
        for idx in range(0, len(raw_tokens) - window_size + 1):
            raw_window = " ".join(raw_tokens[idx : idx + window_size])
            if SequenceMatcher(None, quote_joined, raw_window).ratio() >= 0.82:
                return True
    return False


def check_quotes(path: Path, text: str, inline: list[Citation]) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()
    for start, end, quote in quote_blocks(lines):
        if "**Synthesis:**" in quote:
            continue
        citation = find_nearby_citation(start, end, lines, inline)
        if citation is None or not citation.raw_path.startswith("raw/"):
            continue
        clean_quote = normalize_text(quote)
        if len(clean_quote.split()) < 6:
            continue
        try:
            raw_text = read_raw(citation.raw_path)
        except FileNotFoundError:
            issues.append(
                Issue(
                    code="missing_raw",
                    severity=severity_for_code("missing_raw"),
                    file=rel(path),
                    line=start,
                    citation=citation.label,
                    raw_path=citation.raw_path,
                    detail="cited raw path does not exist",
                )
            )
            continue
        raw_norm = normalize_text(raw_text)
        phrase = distinctive_phrase(quote)
        phrase_norm = normalize_text(phrase)
        if clean_quote not in raw_norm and phrase_norm not in raw_norm and not fuzzy_quote_found(quote, raw_text):
            issues.append(
                Issue(
                    code="quote_not_found",
                    severity=severity_for_code("quote_not_found"),
                    file=rel(path),
                    line=start,
                    citation=citation.label,
                    raw_path=citation.raw_path,
                    detail=f"blockquote phrase not found in cited raw page: {phrase!r}",
                )
            )
    return issues


def audit_file(path: Path) -> list[Issue]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise AuditSetupError(f"wiki file disappeared before audit: {rel(path)}") from e
    return audit_text(path, text)


def audit_text(path: Path, text: str) -> list[Issue]:
    frontmatter = parse_frontmatter_sources(path, text)
    inline = parse_inline_citations(path, text)
    citations = frontmatter + inline
    issues: list[Issue] = []
    issues.extend(check_raw_content(citations))
    issues.extend(frontmatter_inline_parity(path, frontmatter, inline))
    issues.extend(check_range_sanity(inline, frontmatter))
    issues.extend(check_quotes(path, text, inline))
    return dedupe_issues(issues)


def report_payload(files: list[Path], issues: list[Issue]) -> dict[str, object]:
    hard_flags = [issue for issue in issues if issue.severity == "HARD"]
    warning_flags = [issue for issue in issues if issue.severity == "WARNING"]
    return {
        "files_checked": len(files),
        "files_with_flags": len({issue.file for issue in issues}),
        "total_flags": len(issues),
        "hard_flags": len(hard_flags),
        "warning_flags": len(warning_flags),
        "summary_by_code": dict(
            sorted((code, sum(1 for issue in issues if issue.code == code)) for code in {i.code for i in issues})
        ),
        "summary_by_severity": dict(
            sorted((severity, sum(1 for issue in issues if issue.severity == severity)) for severity in {i.severity for i in issues})
        ),
        "flags": [asdict(issue) for issue in issues],
    }


def self_check() -> tuple[list[Issue], list[str]]:
    """Run known issue #57 controls without mutating wiki content."""
    fixture_path = WIKI_DIR / "events" / "__citation_audit_self_check__.md"
    fixture = """---
title: "Citation Audit Self Check"
type: event
status: draft
sources:
  - path: raw/book/pages/page_141.md
    note: "intentional wrong page for spring quote control"
  - path: raw/book/pages/page_163.md
    note: "intentional image-only page control"
  - path: raw/book/pages/page_144.md
    note: "range boundary control"
  - path: raw/book/pages/page_145.md
    note: "range boundary control"
  - path: raw/book/pages/page_146.md
    note: "range boundary control"
  - path: raw/book/pages/page_147.md
    note: "range boundary control"
  - path: raw/book/pages/page_149.md
    note: "correct quote attribution control"
  - path: raw/book/pages/page_142.md
    note: "synthesis skip control"
---

# Citation Audit Self Check

The book is strict
([book p.141](../../../raw/book/pages/page_141.md)):

> "Spring must necessarily cause the range to break up. Anything other
> than this should not be labeled as Spring. It will simply be a test."

This direct quote is correctly attributed:

> "We must train ourselves to anticipate the possible outcome of the
> event and be prepared to take action on our behalf quickly and
> decisively." — [book p.149](../../../raw/book/pages/page_149.md)

This synthesis block should never be treated as a direct quote:

> **Synthesis:** Faza 1 PRD with the Wyckoff discipline that labels are
> provisional until structure resolves
> ([book p.142](../../../raw/book/pages/page_142.md)).

This range already includes the prose after the page-boundary heading
([book p.144–147](../../../raw/book/pages/page_144.md)).

This comma-separated citation must require both pages in frontmatter
([book p.108, p.111](../../../raw/book/pages/page_108.md)).

This missing raw citation should be explicit
([book p.999](../../../raw/book/pages/page_999.md)).
"""
    issues = audit_text(fixture_path, fixture)
    expected = {
        ("frontmatter_missing", "raw/book/pages/page_108.md"),
        ("frontmatter_missing", "raw/book/pages/page_999.md"),
        ("image_only", "raw/book/pages/page_163.md"),
        ("inline_missing", "raw/book/pages/page_145.md"),
        ("inline_missing", "raw/book/pages/page_146.md"),
        ("inline_missing", "raw/book/pages/page_147.md"),
        ("inline_missing", "raw/book/pages/page_163.md"),
        ("missing_raw", "raw/book/pages/page_999.md"),
        ("quote_not_found", "raw/book/pages/page_141.md"),
        ("range_missing_frontmatter", "raw/book/pages/page_108.md"),
        ("section_boundary", "raw/book/pages/page_144.md"),
    }
    actual = {(issue.code, issue.raw_path) for issue in issues}
    errors: list[str] = []
    if len(issues) != len(expected):
        errors.append(f"expected {len(expected)} self-check flags, got {len(issues)}")
    if actual != expected:
        errors.append(f"expected self-check flags {sorted(expected)}, got {sorted(actual)}")
    if any(issue.code == "quote_not_found" and issue.raw_path in {"raw/book/pages/page_142.md", "raw/book/pages/page_149.md"} for issue in issues):
        errors.append("correct p.142/p.149 quote controls produced quote_not_found")
    if any(issue.code == "section_boundary" and issue.citation == "book p.144–147" for issue in issues):
        errors.append("range citation p.144-147 produced section_boundary even though it includes the next page")
    comma_issue = next(
        (
            issue
            for issue in issues
            if issue.code == "range_missing_frontmatter"
            and issue.citation == "book p.108, p.111"
        ),
        None,
    )
    if comma_issue is None or "raw/book/pages/page_111.md" not in comma_issue.detail:
        errors.append("comma-separated page control did not include page_111.md")
    payload = report_payload([fixture_path], issues)
    required_keys = {
        "files_checked",
        "files_with_flags",
        "flags",
        "hard_flags",
        "summary_by_code",
        "summary_by_severity",
        "total_flags",
        "warning_flags",
    }
    if set(payload) != required_keys:
        errors.append(f"JSON schema keys changed: {sorted(payload)}")
    return issues, errors


def dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, str, int, str, str]] = set()
    deduped: list[Issue] = []
    for issue in issues:
        key = (issue.code, issue.file, issue.line, issue.raw_path, issue.detail)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def print_human(files: list[Path], issues: list[Issue]) -> None:
    by_code: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = defaultdict(int)
    by_file: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        by_code[issue.code] += 1
        by_severity[issue.severity] += 1
        by_file[issue.file].append(issue)

    print(f"Provereno fajlova: {len(files)}")
    print(f"Fajlovi sa citation flagovima: {len(by_file)}")
    print(f"Ukupno citation flagova: {len(issues)}")
    if by_code:
        print("Summary po severity:")
        for severity, count in sorted(by_severity.items()):
            print(f"  - {severity}: {count}")
        print("Summary po tipu:")
        for code, count in sorted(by_code.items()):
            print(f"  - {code}: {count}")

    if not issues:
        print("\nSvi audit checkovi prolaze.")
        return

    for file, file_issues in sorted(by_file.items()):
        print(f"\n{file} ({len(file_issues)} flagova)")
        for issue in sorted(file_issues, key=lambda item: (item.line, item.code)):
            print(
                f"  L{issue.line}: {issue.code} ({issue.severity}) [{issue.citation}] -> "
                f"{issue.raw_path} | {issue.detail}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit wiki citations for likely misattribution")
    parser.add_argument("--pr", type=int, help="Check only files changed in the given PR")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--self-check", action="store_true", help="Run built-in issue #57 control cases")
    args = parser.parse_args()

    files: list[Path]
    self_check_errors: list[str] = []
    try:
        if args.self_check:
            files = [WIKI_DIR / "events" / "__citation_audit_self_check__.md"]
            issues, self_check_errors = self_check()
        else:
            files = files_to_check(args.pr)
            issues: list[Issue] = []
            for path in files:
                issues.extend(audit_file(path))
        issues = dedupe_issues(issues)
    except AuditSetupError as e:
        if args.json:
            print(json.dumps({"error": str(e), "exit_code": 2}, indent=2, ensure_ascii=False))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.json:
        out = report_payload(files, issues)
        if args.self_check:
            out["self_check"] = {"ok": not self_check_errors, "errors": self_check_errors}
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print_human(files, issues)
        if args.self_check:
            if self_check_errors:
                print("\nSelf-check FAIL:")
                for error in self_check_errors:
                    print(f"  - {error}")
            else:
                print("\nSelf-check PASS: expected control flags and JSON schema matched.")

    if args.self_check:
        return 2 if self_check_errors else 0
    return 1 if any(issue.severity == "HARD" for issue in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
