#!/usr/bin/env python3
"""Download Bruce Fraser article images and rebuild Markdown with inline refs."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "skills/wyckoff-trader-skill/references/assets/bruce_fraser_stockcharts"
HTML_ROOT = SOURCE_ROOT / "html"
MANIFEST_PATH = SOURCE_ROOT / "manifest.json"
OUTPUT_ROOT = REPO_ROOT / "raw/bruce_fraser"
IMAGE_ROOT = OUTPUT_ROOT / "images"
POST_ROOT = OUTPUT_ROOT / "posts"
ARTICLE_IMAGE_PREFIX = "https://d.stockcharts.com/img/articles/"
USER_AGENT = "wyckoff-ai-rebuild/0.1 (+https://github.com/ssmiljanicc/wyckoff-ai)"


@dataclass
class DownloadStats:
    downloaded: int = 0
    skipped: int = 0
    not_found: int = 0
    total_bytes: int = 0


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return url


def is_article_image(url: str) -> bool:
    return normalize_url(url).startswith(ARTICLE_IMAGE_PREFIX)


def image_filename(url: str) -> str:
    filename = Path(urlparse(url).path).name
    if not filename:
        raise ValueError(f"Image URL has no filename: {url}")
    return filename


def image_markdown(url: str) -> str:
    return f"![](../images/{image_filename(url)})"


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text


def inline_text(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if node.name == "br":
        return "\n"
    if node.name == "img":
        src = normalize_url(node.get("src", ""))
        if is_article_image(src):
            return f"\n\n{image_markdown(src)}\n\n"
        return ""
    return "".join(inline_text(child) for child in node.children)


def render_paragraph(node: Tag) -> list[str]:
    text = inline_text(node)
    parts = [clean_text(part) for part in re.split(r"\n{2,}", text) if clean_text(part)]
    return parts


def render_list(node: Tag, ordered: bool = False) -> list[str]:
    lines: list[str] = []
    for index, item in enumerate(node.find_all("li", recursive=False), start=1):
        prefix = f"{index}." if ordered else "-"
        text = clean_text(inline_text(item))
        if text:
            lines.append(f"{prefix} {text}")
    return ["\n".join(lines)] if lines else []


def render_heading(node: Tag) -> list[str]:
    try:
        level = int(node.name[1])
    except (TypeError, ValueError):
        level = 2
    level = min(max(level, 2), 6)
    text = clean_text(inline_text(node))
    return [f"{'#' * level} {text}"] if text else []


def render_block(node: Tag | NavigableString) -> list[str]:
    if isinstance(node, NavigableString):
        text = clean_text(str(node))
        return [text] if text else []

    if node.name in {"script", "style"}:
        return []
    if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return render_heading(node)
    if node.name == "p":
        return render_paragraph(node)
    if node.name == "ul":
        return render_list(node)
    if node.name == "ol":
        return render_list(node, ordered=True)
    if node.name == "hr":
        return ["---"]
    if node.name == "blockquote":
        lines = []
        for block in render_children(node):
            lines.extend(f"> {line}" if line else ">" for line in block.splitlines())
        return ["\n".join(lines)] if lines else []
    if node.name == "img":
        src = normalize_url(node.get("src", ""))
        if is_article_image(src):
            return [image_markdown(src)]
        return []
    if node.name == "figure":
        blocks: list[str] = []
        for img in node.find_all("img", recursive=True):
            src = normalize_url(img.get("src", ""))
            if is_article_image(src):
                blocks.append(image_markdown(src))
        caption = node.find("figcaption")
        if caption:
            text = clean_text(inline_text(caption))
            if text:
                blocks.append(text)
        return blocks

    return render_children(node)


def render_children(node: Tag) -> list[str]:
    blocks: list[str] = []
    for child in node.children:
        blocks.extend(render_block(child))
    return blocks


def content_image_urls(content: Tag) -> list[str]:
    urls: list[str] = []
    for img in content.find_all("img"):
        src = normalize_url(img.get("src", ""))
        if is_article_image(src):
            urls.append(src)
    return urls


def all_article_image_urls(html: str) -> list[str]:
    pattern = re.compile(r"https://d\.stockcharts\.com/img/articles/[^\"'<>\\s)]+")
    return pattern.findall(html)


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text())


def article_content(soup: BeautifulSoup, html_path: Path) -> Tag:
    content = soup.select_one(".gh-content") or soup.select_one(".post-content")
    if content is None:
        raise RuntimeError(f"No article content container found in {html_path}")
    return content


def rebuild_markdown(entry: dict, content: Tag) -> str:
    blocks = [
        "\n".join(
            [
                f"# {entry['title']}",
                "",
                f"URL: {entry['url']}",
                f"Date: {entry['date']}",
                "Author: Bruce Fraser",
            ]
        )
    ]
    blocks.extend(render_children(content))
    return "\n\n".join(block for block in blocks if block).rstrip() + "\n"


def write_posts(manifest: list[dict]) -> tuple[int, int, int]:
    POST_ROOT.mkdir(parents=True, exist_ok=True)
    inserted_refs = 0
    total_url_refs = 0
    unique_urls: set[str] = set()

    for entry in manifest:
        html_path = SOURCE_ROOT / entry["html_file"]
        html = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")
        content = article_content(soup, html_path)

        total_refs = all_article_image_urls(html)
        total_url_refs += len(total_refs)
        unique_urls.update(total_refs)

        inserted_refs += len(content_image_urls(content))
        output_path = POST_ROOT / f"{entry['slug']}.md"
        output_path.write_text(rebuild_markdown(entry, content), encoding="utf-8")

    return inserted_refs, total_url_refs, len(unique_urls)


def collect_unique_urls(manifest: list[dict]) -> list[str]:
    urls: set[str] = set()
    for entry in manifest:
        html_path = SOURCE_ROOT / entry["html_file"]
        urls.update(all_article_image_urls(html_path.read_text(encoding="utf-8")))
    return sorted(urls)


def download_images(urls: Iterable[str], delay: float) -> DownloadStats:
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    stats = DownloadStats()

    for url in urls:
        output_path = IMAGE_ROOT / image_filename(url)
        if output_path.exists() and output_path.stat().st_size > 0:
            stats.skipped += 1
            continue

        response = session.get(url, stream=True, timeout=60)
        if response.status_code in {403, 429}:
            raise RuntimeError(f"Stopping on HTTP {response.status_code}: {url}")
        if response.status_code == 404:
            stats.not_found += 1
            print(f"404: {url}", file=sys.stderr)
            time.sleep(delay)
            continue
        response.raise_for_status()

        bytes_written = 0
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with temp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue
                handle.write(chunk)
                bytes_written += len(chunk)
        temp_path.replace(output_path)
        stats.downloaded += 1
        stats.total_bytes += bytes_written
        time.sleep(delay)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    urls = collect_unique_urls(manifest)
    inserted_refs, total_url_refs, unique_url_count = write_posts(manifest)

    stats = DownloadStats()
    if not args.skip_download:
        stats = download_images(urls, args.delay)

    image_count = len([path for path in IMAGE_ROOT.glob("*") if path.is_file() and not path.name.endswith(".tmp")])
    image_bytes = sum(path.stat().st_size for path in IMAGE_ROOT.glob("*") if path.is_file())

    print(f"articles: {len(manifest)}")
    print(f"unique image URLs: {unique_url_count}")
    print(f"total URL references in HTML: {total_url_refs}")
    print(f"inline content image refs inserted: {inserted_refs}")
    print(f"images downloaded: {stats.downloaded}")
    print(f"images skipped: {stats.skipped}")
    print(f"404s: {stats.not_found}")
    print(f"bytes downloaded this run: {stats.total_bytes}")
    print(f"images on disk: {image_count}")
    print(f"image directory size: {image_bytes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
