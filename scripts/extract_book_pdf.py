#!/usr/bin/env python3
"""Extract clean page Markdown and page figures from the Villahermosa book PDF."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[1]
BOOK_ROOT = ROOT / "raw" / "book"
PDF_PATH = BOOK_ROOT / "wyckoff_methodology_in_depth.pdf"
PAGES_DIR = BOOK_ROOT / "pages"
IMAGES_DIR = BOOK_ROOT / "images"
FULL_TEXT_PATH = BOOK_ROOT / "full_text.md"
IMAGE_MANIFEST_PATH = BOOK_ROOT / "image_manifest.json"

EXPECTED_PAGES = 248
MIN_IMAGE_SIZE = 50
OCR_ARTIFACT_PATTERNS = ("gre ater", "selle rs", "tra ding", "wycko ff")


@dataclass
class Stats:
    pages_written: int = 0
    figures_written: int = 0
    figures_skipped: int = 0
    image_bytes: int = 0


@dataclass
class PageItem:
    kind: str
    bbox: tuple[float, float, float, float]
    block_no: int
    value: str


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text


def text_block_to_markdown(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        text = "".join(span.get("text", "") for span in line.get("spans", []))
        text = clean_text(text)
        if text:
            lines.append(text)

    if not lines:
        return ""

    return "\n".join(lines)


def ensure_dirs(pages_dir: Path, images_dir: Path) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)


def clean_outputs(output_root: Path, pages_dir: Path, images_dir: Path) -> None:
    for path in pages_dir.glob("page_*.md"):
        path.unlink()
    for path in images_dir.glob("page_*_fig_*.png"):
        path.unlink()

    for path in (output_root / "full_text.md", output_root / "image_manifest.json"):
        if path.exists():
            path.unlink()


def round_bbox(bbox: tuple[float, float, float, float]) -> dict[str, float]:
    left, top, right, bottom = bbox
    return {
        "top": round(top, 2),
        "left": round(left, 2),
        "right": round(right, 2),
        "bottom": round(bottom, 2),
    }


def image_filename(page_number: int, figure_index: int) -> str:
    return f"page_{page_number:03d}_fig_{figure_index}.png"


def render_figure(
    page: fitz.Page,
    bbox: tuple[float, float, float, float],
    output_path: Path,
    scale: float,
) -> tuple[int, int, int]:
    clip = fitz.Rect(bbox)
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        clip=clip,
        alpha=False,
    )
    pixmap.save(output_path)
    return output_path.stat().st_size, pixmap.width, pixmap.height


def manifest_entry(
    image_path: Path,
    page_number: int,
    figure_index: int,
    bbox: tuple[float, float, float, float],
    size_bytes: int,
    width_px: int,
    height_px: int,
) -> dict[str, Any]:
    return {
        "image_path": str(image_path.relative_to(ROOT)),
        "page_number": page_number,
        "figure_index": figure_index,
        "position_in_page": round_bbox(bbox),
        "format": "png",
        "size_bytes": size_bytes,
        "width_px": width_px,
        "height_px": height_px,
    }


def item_sort_key(item: PageItem) -> tuple[int, float, int]:
    left, top, _right, _bottom = item.bbox
    return (round(top), left, item.block_no)


def write_page(path: Path, items: list[PageItem]) -> str:
    blocks = [item.value for item in sorted(items, key=item_sort_key) if item.value.strip()]
    markdown = "\n\n".join(blocks).rstrip() + "\n"
    path.write_text(markdown, encoding="utf-8")
    return markdown


def write_manifest(path: Path, entries: list[dict[str, Any]]) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def write_full_text(path: Path, page_markdown: list[tuple[int, str]]) -> None:
    blocks = []
    for page_number, markdown in page_markdown:
        blocks.append(f"<!-- page_{page_number:03d} -->\n\n{markdown.rstrip()}")
    path.write_text("\n\n---\n\n".join(blocks).rstrip() + "\n", encoding="utf-8")


def artifact_matches(paths: list[Path]) -> list[tuple[Path, str]]:
    matches: list[tuple[Path, str]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for pattern in OCR_ARTIFACT_PATTERNS:
            if pattern in lowered:
                matches.append((path, pattern))
    return matches


def validate_pdf(pdf_path: Path) -> fitz.Document:
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Missing source PDF: {pdf_path}. This commercial source is gitignored; "
            "place it locally before running extraction."
        )

    doc = fitz.open(pdf_path)
    if doc.is_encrypted and not doc.authenticate(""):
        doc.close()
        raise RuntimeError(f"Cannot extract encrypted PDF: {pdf_path}")

    if len(doc) != EXPECTED_PAGES:
        page_count = len(doc)
        doc.close()
        raise RuntimeError(
            f"Expected {EXPECTED_PAGES} pages in {pdf_path}, found {page_count}"
        )

    return doc


def extract_book(
    pdf_path: Path,
    output_root: Path,
    min_image_size: int,
    scale: float,
    clean: bool,
) -> Stats:
    pages_dir = output_root / "pages"
    images_dir = output_root / "images"
    full_text_path = output_root / "full_text.md"
    manifest_path = output_root / "image_manifest.json"

    ensure_dirs(pages_dir, images_dir)
    if clean:
        clean_outputs(output_root, pages_dir, images_dir)

    stats = Stats()
    manifest: list[dict[str, Any]] = []
    page_markdown: list[tuple[int, str]] = []

    doc = validate_pdf(pdf_path)
    try:
        for page_index, page in enumerate(doc, start=1):
            items: list[PageItem] = []
            figure_index = 0
            page_dict = page.get_text("dict", sort=True)

            for block_no, block in enumerate(page_dict.get("blocks", [])):
                bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
                block_type = block.get("type")

                if block_type == 0:
                    text = text_block_to_markdown(block)
                    if text:
                        items.append(PageItem("text", bbox, block_no, text))
                    continue

                if block_type != 1:
                    continue

                width = int(block.get("width", 0) or 0)
                height = int(block.get("height", 0) or 0)
                if width < min_image_size or height < min_image_size:
                    stats.figures_skipped += 1
                    continue

                figure_index += 1
                filename = image_filename(page_index, figure_index)
                image_path = images_dir / filename
                size_bytes, width_px, height_px = render_figure(
                    page, bbox, image_path, scale
                )
                stats.figures_written += 1
                stats.image_bytes += size_bytes

                manifest.append(
                    manifest_entry(
                        image_path=image_path,
                        page_number=page_index,
                        figure_index=figure_index,
                        bbox=bbox,
                        size_bytes=size_bytes,
                        width_px=width_px,
                        height_px=height_px,
                    )
                )
                items.append(
                    PageItem(
                        "image",
                        bbox,
                        block_no,
                        f"![](images/{filename})",
                    )
                )

            page_path = pages_dir / f"page_{page_index:03d}.md"
            markdown = write_page(page_path, items)
            page_markdown.append((page_index, markdown))
            stats.pages_written += 1

    finally:
        doc.close()

    manifest.sort(key=lambda entry: (entry["page_number"], entry["figure_index"]))
    write_manifest(manifest_path, manifest)
    write_full_text(full_text_path, page_markdown)

    matches = artifact_matches(
        sorted(pages_dir.glob("page_*.md")) + [full_text_path]
    )
    if matches:
        for path, pattern in matches:
            print(f"OCR artifact found: {pattern!r} in {path}", file=sys.stderr)
        raise RuntimeError("Generated output contains known OCR artifact patterns")

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=PDF_PATH)
    parser.add_argument("--output-root", type=Path, default=BOOK_ROOT)
    parser.add_argument("--min-image-size", type=int, default=MIN_IMAGE_SIZE)
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove previously generated extraction outputs before writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        stats = extract_book(
            pdf_path=args.pdf,
            output_root=args.output_root,
            min_image_size=args.min_image_size,
            scale=args.scale,
            clean=not args.no_clean,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    manifest_path = args.output_root / "image_manifest.json"
    print(f"pages written: {stats.pages_written}")
    print(f"figures written: {stats.figures_written}")
    print(f"figures skipped: {stats.figures_skipped}")
    print(f"image bytes: {stats.image_bytes}")
    print(f"manifest: {manifest_path.relative_to(ROOT)}")
    print("artifact check: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
