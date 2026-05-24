#!/usr/bin/env python3
"""Re-scrape Wyckoff Analytics crypto archive posts with images.

This intentionally does not authenticate or bypass paywalls. If the public
content is short or presents subscription UI, the post is saved as-is and marked
paywalled in the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = (
    ROOT
    / "skills"
    / "wyckoff-trader-skill"
    / "references"
    / "assets"
    / "crypto_archive"
    / "manifest.json"
)
OUTPUT_ROOT = ROOT / "raw" / "crypto_archive"
HTML_DIR = OUTPUT_ROOT / "html"
POSTS_DIR = OUTPUT_ROOT / "posts"
IMAGES_DIR = OUTPUT_ROOT / "images"
OUTPUT_MANIFEST = OUTPUT_ROOT / "manifest.json"

USER_AGENT = "wyckoff-ai-rebuild/0.1 (contact: ssmiljanic3@gmail.com)"
PAYWALL_RE = re.compile(
    r"(subscribe\s+to\s+read|sign\s+in\s+to\s+(?:read|continue)|"
    r"log\s+in\s+to\s+(?:read|continue)|members?\s+only|"
    r"premium\s+content|restricted\s+content)",
    re.I,
)
BLOCK_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "pre",
}
SKIP_TAGS = {"script", "style", "noscript", "svg", "form", "button"}


@dataclass
class Stats:
    downloaded_posts: int = 0
    skipped_posts: int = 0
    paywalled_posts: int = 0
    errors: int = 0
    total_images: int = 0
    total_bytes: int = 0


def is_complete(entry: dict, previous: dict[str, dict]) -> bool:
    slug = entry["slug"]
    return (
        (HTML_DIR / f"{slug}.html").exists()
        and (POSTS_DIR / f"{slug}.md").exists()
        and slug in previous
    )


def load_source_manifest() -> list[dict]:
    with SOURCE_MANIFEST.open() as f:
        data = json.load(f)
    if len(data) != 46:
        raise RuntimeError(f"Expected 46 source URLs, found {len(data)}")
    return data


def ensure_dirs() -> None:
    for path in (HTML_DIR, POSTS_DIR, IMAGES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def request_url(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=45)
    if response.status_code in {403, 429}:
        raise RuntimeError(f"Server returned {response.status_code} for {url}; stopping")
    response.raise_for_status()
    return response


def visible_text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def find_content(soup: BeautifulSoup) -> Tag:
    for selector in (
        ".post-single__content",
        "article .entry-content",
        ".entry-content",
        "article",
        "main",
    ):
        node = soup.select_one(selector)
        if node and len(visible_text(node)) > 50:
            return node

    candidates = [
        node
        for node in soup.find_all(["div", "section"])
        if len(visible_text(node)) > 500
    ]
    if not candidates:
        body = soup.body
        if body is None:
            raise RuntimeError("Could not locate page body")
        return body
    return max(candidates, key=lambda node: len(visible_text(node)))


def best_image_url(img: Tag, page_url: str) -> str | None:
    for attr in ("data-src", "data-lazy-src", "data-original", "src"):
        value = img.get(attr)
        if value and not value.startswith("data:"):
            return urljoin(page_url, value)

    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        candidates = []
        for part in srcset.split(","):
            pieces = part.strip().split()
            if not pieces:
                continue
            width = 0
            if len(pieces) > 1 and pieces[1].endswith("w"):
                try:
                    width = int(pieces[1][:-1])
                except ValueError:
                    width = 0
            candidates.append((width, pieces[0]))
        if candidates:
            return urljoin(page_url, max(candidates)[1])
    return None


def extension_from_response(url: str, response: requests.Response | None = None) -> str:
    content_type = ""
    if response is not None:
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
    by_type = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    if content_type in by_type:
        return by_type[content_type]

    suffix = Path(unquote(urlparse(url).path)).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".img"


def image_filename(index: int, url: str, response: requests.Response | None = None) -> str:
    parsed_name = Path(unquote(urlparse(url).path)).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", parsed_name).strip("-") or "image"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{index:02d}-{safe_stem}-{digest}{extension_from_response(url, response)}"


def download_images(
    session: requests.Session,
    content: Tag,
    page_url: str,
    slug: str,
    delay: float,
) -> tuple[dict[int, str], int, int]:
    image_dir = IMAGES_DIR / slug
    image_dir.mkdir(parents=True, exist_ok=True)
    refs: dict[int, str] = {}
    total_bytes = 0
    seen_urls: dict[str, str] = {}

    image_tags = content.find_all("img")
    for index, img in enumerate(image_tags, start=1):
        image_url = best_image_url(img, page_url)
        if not image_url:
            continue

        if image_url in seen_urls:
            refs[id(img)] = seen_urls[image_url]
            continue

        existing = sorted(image_dir.glob(f"{index:02d}-*"))
        if existing:
            filename = existing[0].name
            total_bytes += existing[0].stat().st_size
        else:
            time.sleep(delay)
            response = request_url(session, image_url)
            filename = image_filename(index, image_url, response)
            image_path = image_dir / filename
            image_path.write_bytes(response.content)
            total_bytes += len(response.content)

        rel_path = f"../images/{slug}/{filename}"
        seen_urls[image_url] = rel_path
        refs[id(img)] = rel_path

    return refs, len(image_tags), total_bytes


def direct_text(node: Tag) -> str:
    parts = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag) and child.name not in SKIP_TAGS and child.name != "img":
            parts.append(child.get_text(" ", strip=True))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def markdown_lines(content: Tag, image_refs: dict[int, str]) -> list[str]:
    lines: list[str] = []
    emitted_blocks: set[int] = set()

    def emit(line: str) -> None:
        line = line.strip()
        if line:
            lines.append(line)

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            return
        if node.name in SKIP_TAGS:
            return
        if node.name == "img":
            path = image_refs.get(id(node))
            if path:
                alt = re.sub(r"\s+", " ", node.get("alt", "")).strip()
                emit(f"![{alt}]({path})")
            return
        if node.name in BLOCK_TAGS:
            if id(node) in emitted_blocks:
                return
            emitted_blocks.add(id(node))
            if node.name.startswith("h") and len(node.name) == 2:
                level = min(int(node.name[1]) + 1, 6)
                emit(f"{'#' * level} {visible_text(node)}")
            elif node.name == "li":
                text = direct_text(node) or visible_text(node)
                emit(f"- {text}")
            elif node.name == "blockquote":
                for text_line in visible_text(node).splitlines():
                    emit(f"> {text_line}")
            else:
                text = direct_text(node) or visible_text(node)
                emit(text)
            for img in node.find_all("img"):
                walk(img)
            return
        for child in node.children:
            walk(child)

    for child in content.children:
        walk(child)
    return lines


def build_markdown(entry: dict, content: Tag, image_refs: dict[int, str]) -> str:
    title = entry.get("title") or entry["slug"]
    header = [
        f"# {title}",
        "",
        f"URL: {entry['url']}",
        f"Date: {entry.get('date', '')}",
        f"Author: {entry.get('author', '')}",
        "",
    ]
    body = markdown_lines(content, image_refs)
    return "\n".join(header + body).strip() + "\n"


def is_paywalled(text: str, soup: BeautifulSoup) -> bool:
    return len(text) < 1000 or bool(PAYWALL_RE.search(soup.get_text(" ", strip=True)))


def existing_manifest() -> dict[str, dict]:
    if not OUTPUT_MANIFEST.exists():
        return {}
    with OUTPUT_MANIFEST.open() as f:
        return {entry["slug"]: entry for entry in json.load(f)}


def process_entry(
    session: requests.Session,
    entry: dict,
    previous: dict[str, dict],
    delay: float,
    stats: Stats,
    rebuild_existing: bool = False,
) -> dict:
    slug = entry["slug"]
    html_path = HTML_DIR / f"{slug}.html"
    post_path = POSTS_DIR / f"{slug}.md"

    if html_path.exists() and post_path.exists() and slug in previous and not rebuild_existing:
        stats.skipped_posts += 1
        existing = previous[slug]
        stats.total_images += int(existing.get("image_count", 0))
        image_dir = IMAGES_DIR / slug
        if image_dir.exists():
            stats.total_bytes += sum(path.stat().st_size for path in image_dir.iterdir() if path.is_file())
        if existing.get("status") == "paywalled":
            stats.paywalled_posts += 1
        return existing

    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
    else:
        response = request_url(session, entry["url"])
        html = response.text
        html_path.write_text(html, encoding=response.encoding or "utf-8")
    soup = BeautifulSoup(html, "lxml")
    content = find_content(soup)
    text = visible_text(content)
    image_refs, image_count, image_bytes = download_images(
        session, content, entry["url"], slug, delay
    )
    markdown = build_markdown(entry, content, image_refs)
    post_path.write_text(markdown, encoding="utf-8")

    status = "paywalled" if is_paywalled(text, soup) else "ok"
    stats.downloaded_posts += 1
    stats.total_images += image_count
    stats.total_bytes += image_bytes
    if status == "paywalled":
        stats.paywalled_posts += 1

    return {
        "slug": slug,
        "url": entry["url"],
        "date": entry.get("date", ""),
        "char_count": len(text),
        "html_file": str(html_path.relative_to(OUTPUT_ROOT)),
        "image_count": image_count,
        "status": status,
    }


def write_manifest(entries: Iterable[dict]) -> None:
    tmp_path = OUTPUT_MANIFEST.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(list(entries), indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(OUTPUT_MANIFEST)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    parser.add_argument(
        "--rebuild-existing",
        action="store_true",
        help="Rebuild markdown and manifest from saved HTML when present",
    )
    args = parser.parse_args()

    ensure_dirs()
    source_entries = load_source_manifest()
    previous = existing_manifest()
    stats = Stats()
    output_entries: list[dict] = []

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        for index, entry in enumerate(source_entries, start=1):
            if index > 1 and not is_complete(entry, previous):
                time.sleep(args.delay)
            print(f"[{index:02d}/{len(source_entries)}] {entry['slug']}")
            result = process_entry(
                session,
                entry,
                previous,
                args.delay,
                stats,
                rebuild_existing=args.rebuild_existing,
            )
            output_entries.append(result)
            print(
                f"  status={result['status']} chars={result['char_count']} "
                f"images={result['image_count']}"
            )
    except Exception as exc:
        stats.errors += 1
        if output_entries:
            write_manifest(output_entries)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    write_manifest(output_entries)
    print()
    print(f"downloaded_posts={stats.downloaded_posts}")
    print(f"skipped_posts={stats.skipped_posts}")
    print(f"paywalled_posts={stats.paywalled_posts}")
    print(f"errors={stats.errors}")
    print(f"total_images={stats.total_images}")
    print(f"total_bytes={stats.total_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
