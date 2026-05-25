# Feature: Re-extract Book PDF with Clean Text and Page Images

## Summary

Implement GitHub issue [#4](https://github.com/ssmiljanicc/wyckoff-ai/issues/4): create and run a PyMuPDF-based extraction pipeline for `raw/book/wyckoff_methodology_in_depth.pdf` that produces clean per-page Markdown, extracted page figures, a concatenated `full_text.md`, and `image_manifest.json`.

This is Phase 1 raw-data work for `.claude/PRPs/prds/faza-1-skill-modernization.prd.md`. The book is the canonical taxonomy source for later wiki ingest, so the output must preserve page provenance and readable Wyckoff labels embedded directly in chart/schematic pixels.

## User Story

As a Wyckoff skill maintainer,
I want the Villahermosa book re-extracted from the source PDF with clean text and page images,
So that wiki ingest can cite page-level raw sources without OCR artifacts or missing chart schematics.

## Problem Statement

The current book corpus is a legacy PDF-to-text conversion under `skills/wyckoff-trader-skill/references/assets/book/`. It has 248 page `.txt` files and `full_text.txt`, but `raw/INVENTORY.md:45-49` records that images were lost and OCR artifacts such as `gre ater`, `selle rs`, `tra ding`, and `wycko ff` are present. The Phase 1 PRD also calls out the same defects at `.claude/PRPs/prds/faza-1-skill-modernization.prd.md:7-17`.

Wyckoff methodology is chart- and schematic-heavy. Issue #4 was updated on 2026-05-25 to state that book figures contain labels rendered directly into pixels, including examples like MSOS, JAC, BCLX, and mSOS. Those labels must remain readable because later issue #5 handles captioning/tagging; this issue only preserves raw page evidence.

## Solution Statement

Add `scripts/extract_book_pdf.py`, a deterministic CLI script that:

- validates the source PDF exists and has exactly 248 pages;
- extracts text from PyMuPDF text blocks instead of OCR;
- extracts/renders page image blocks and skips decorative images smaller than 50x50 px;
- writes `raw/book/pages/page_NNN.md` with inline `![](images/page_NNN_fig_M.png)` references ordered by page coordinates;
- writes `raw/book/images/page_NNN_fig_M.png`;
- writes `raw/book/full_text.md`;
- writes `raw/book/image_manifest.json` with page, figure, bbox, dimensions, format, and byte metadata;
- fails validation if the known OCR artifact patterns remain in generated text;
- is idempotent, so a second run produces no git diff.

## Metadata

| Field | Value |
| --- | --- |
| Feature type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Source issue | [#4 Re-extract book from PDF](https://github.com/ssmiljanicc/wyckoff-ai/issues/4) |
| PRD | `.claude/PRPs/prds/faza-1-skill-modernization.prd.md` |
| PRD phase | Phase 1: Raw data ready / M1 |
| Worktree | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/book-pdf-extract` |
| Branch | `kild/book-pdf-extract` |
| Primary dependency | `pymupdf>=1.24` from `[book]` extra |
| Source PDF | `raw/book/wyckoff_methodology_in_depth.pdf` |
| Plan output | `PRPs/plans/04-book-pdf-extract.plan.md` |

## UX Design

This is a backend/operator workflow, not an end-user UI.

Current flow:

```text
Legacy book .txt files
  -> OCR artifacts remain
  -> images are absent
  -> wiki ingest would cite damaged text and miss schematics
```

Future flow:

```text
raw/book/wyckoff_methodology_in_depth.pdf
  -> uv run --extra book python scripts/extract_book_pdf.py
  -> raw/book/pages/page_NNN.md + inline image refs
  -> raw/book/images/page_NNN_fig_M.png
  -> raw/book/full_text.md
  -> raw/book/image_manifest.json
  -> wiki ingest can cite clean page-level sources
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| `skills/wyckoff-trader-skill/references/assets/book/` | Legacy text-only book copy with artifacts | Left unchanged as historical input | Avoids churn in legacy references |
| `raw/book/` | PDF only, gitignored, or absent in fresh clone | Clean tracked raw extraction outputs beside gitignored PDF | Later ingest has canonical raw sources |
| Operator CLI | No book extraction script | `uv run --extra book python scripts/extract_book_pdf.py` | Reproducible extraction and validation |

## Mandatory Reading

- `.claude/PRPs/prds/faza-1-skill-modernization.prd.md:7-17` - Phase 1 evidence and proposed solution.
- `.claude/PRPs/prds/faza-1-skill-modernization.prd.md:31-39` - success metrics, especially chart image recovery.
- `.claude/PRPs/prds/faza-1-skill-modernization.prd.md:141-157` - Phase 1 status and raw-data success signal.
- `raw/INVENTORY.md:39-64` - current book state, OCR artifacts, missing images, expected figure count.
- `CLAUDE.md:11-21` - raw sources -> wiki -> schema architecture and immutability rule.
- `CLAUDE.md:148-165` - book ingest priority and why book extraction blocks later corpus quality.
- `CLAUDE.md:210-221` - image alt-text convention that issue #5 will apply after this raw extraction.
- `pyproject.toml:12-15` - `[book]` extra with `pymupdf>=1.24`.
- `scripts/download_fraser_images.py:20-29`, `scripts/download_fraser_images.py:266-294` - repo-root constants and simple CLI reporting pattern.
- `scripts/scrape_crypto_archive.py:26-40`, `scripts/scrape_crypto_archive.py:91-101`, `scripts/scrape_crypto_archive.py:366-424` - output path constants, directory setup, manifest temp-write, stats output.
- [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html) - `Page.get_text()`, image block metadata, `Page.get_image_info()`, `Page.get_image_rects()`, `Page.get_pixmap()`.

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| NAMING | `scripts/download_fraser_images.py:20-29` | Resolve repo root from script path and define output roots as constants. | `REPO_ROOT = Path(__file__).resolve().parents[1]` |
| CLI | `scripts/download_fraser_images.py:266-294` | Keep script as standalone `argparse` CLI and print final counters. | `parser = argparse.ArgumentParser()` / `print(f"images on disk: {image_count}")` |
| TYPES | `scripts/scrape_crypto_archive.py:64-72` | Use dataclass for extraction stats instead of loose counters. | `@dataclass class Stats:` |
| ERRORS | `scripts/scrape_crypto_archive.py:96-101` | Fail fast on unrecoverable source problems. | `response.raise_for_status()` |
| FLOW | `scripts/scrape_crypto_archive.py:91-93` | Ensure output directories before processing. | `path.mkdir(parents=True, exist_ok=True)` |
| MANIFEST | `scripts/scrape_crypto_archive.py:366-369` | Write manifests deterministically through a temp file, then replace. | `tmp_path.write_text(json.dumps(list(entries), indent=2) + "\n", encoding="utf-8")` |
| MARKDOWN | `scripts/scrape_crypto_archive.py:238-296` | Build Markdown as ordered lines/blocks and emit image refs in-place. | `emit(f"![{alt}]({path})")` |
| GITIGNORE | `.gitignore:158-160` | Keep commercial PDF untracked while allowing generated raw Markdown/images to be tracked. | `raw/book/*.pdf` |
| SOURCE STATE | `skills/wyckoff-trader-skill/references/assets/book/index.md:5-8` | Legacy book naming confirms 248 pages and page numbering pattern. | `page_001.txt ... page_248.txt` |

## Files to Change

| File | Change |
| --- | --- |
| `scripts/extract_book_pdf.py` | New PyMuPDF extraction CLI. |
| `raw/book/pages/page_001.md` ... `raw/book/pages/page_248.md` | Generated clean page Markdown with inline image refs. |
| `raw/book/images/page_NNN_fig_M.png` | Generated figure images, skipping <50x50 px decorative assets. |
| `raw/book/full_text.md` | Generated concatenation of all page Markdown. |
| `raw/book/image_manifest.json` | Generated image metadata manifest. |

Do not modify `skills/wyckoff-trader-skill/references/assets/book/`; issue #4 explicitly says the clean extraction output goes to `raw/book/`.

## NOT Building

- No Vision captioning or semantic image tags; deferred to issue #5 and issue #27.
- No ML labeling of Wyckoff concepts in figures.
- No wiki ingest or `knowledge/wiki/` updates; deferred to issue #7.
- No replacement of legacy `references/assets/book/` files.
- No committing `raw/book/wyckoff_methodology_in_depth.pdf`; `.gitignore:158-160` already protects it.
- No OCR engine. The plan uses PDF text extraction and layout reconstruction via PyMuPDF.

## Architecture

### APPROACH_CHOSEN

Use `page.get_text("dict", sort=True)` as the primary layout source because it returns text and image blocks with bounding boxes. Convert text spans into clean paragraphs, convert qualifying image blocks into figure files and manifest entries, then merge both block types in coordinate order to write page Markdown.

For image preservation, use image block bytes when available and readable, but normalize generated figure outputs to PNG. If a block lacks reliable embedded image bytes or readability is poor, render the page region at 2x scale with `page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(bbox), alpha=False)` so pixel-baked labels remain readable. Always record the final output dimensions.

### RATIONALE

The page-level raw source contract in `CLAUDE.md:169-195` expects citations to `raw/book/pages/page_NNN.md`. Inline image refs in the page Markdown preserve the text/image relationship for later captioning and wiki ingest. Using coordinate order mirrors existing scraper behavior of inserting images while traversing source content, but adapts it to PDF layout coordinates.

### ALTERNATIVES_REJECTED

- `pdftotext` or existing `.txt` files: rejected because the known OCR-like artifacts and missing images are the core defect.
- OCR: rejected because the PDF has extractable text and OCR can introduce new spacing artifacts.
- `Page.get_images()` alone: rejected because it finds embedded image resources but does not by itself provide a complete reading-order stream for inline Markdown placement.
- Single full-document Markdown only: rejected because wiki provenance requires page-level source links.

### Failure Modes

- PDF missing in a fresh clone: script exits with a clear message that `raw/book/wyckoff_methodology_in_depth.pdf` is required and intentionally gitignored.
- Page count not 248: script exits non-zero to avoid silently extracting the wrong edition.
- Image block missing bytes or xref: fallback to clipped page pixmap at 2x.
- Decorative bullets become figure files: filter anything with original block `width < 50` or `height < 50`.
- Coordinate ordering interleaves columns poorly: expose a helper that sorts by `(round(y0), x0, block_no)` and validate with random-page spot checks.
- Re-run leaves stale files: clean only `raw/book/pages/*.md`, `raw/book/images/page_*_fig_*.png`, `raw/book/full_text.md`, and `raw/book/image_manifest.json` before writing.

### Performance Concerns

248 pages and 150-300 expected figures are modest. 2x clipped pixmap rendering should be limited to image bboxes, not whole pages, to avoid excessive runtime and file size. JSON manifest writing should sort entries by `(page_number, figure_index)`.

### Security / Licensing Concerns

The source PDF is a commercial book and remains gitignored. Generated text/images are raw corpus artifacts already required by this repo's Phase 1 plan; do not add the PDF or paths outside `raw/book/`.

## Step-by-Step Tasks

1. Add the extraction script skeleton.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: create a standalone Python CLI with `#!/usr/bin/env python3`, `from __future__ import annotations`, `argparse`, `json`, `re`, `dataclasses`, `Path`, and `fitz`.
   - Pattern to mirror: `scripts/download_fraser_images.py:1-20` and `scripts/scrape_crypto_archive.py:26-40`.
   - Gotcha: PyMuPDF is installed only through the `[book]` extra; validation commands must use `uv run --extra book`.
   - Validation command: `uv run --extra book python scripts/extract_book_pdf.py --help`

2. Define constants, stats, and CLI options.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: define `ROOT`, `PDF_PATH`, `BOOK_ROOT`, `PAGES_DIR`, `IMAGES_DIR`, `FULL_TEXT_PATH`, `IMAGE_MANIFEST_PATH`, `EXPECTED_PAGES = 248`, `MIN_IMAGE_SIZE = 50`, and `OCR_ARTIFACT_PATTERNS = ("gre ater", "selle rs", "tra ding", "wycko ff")`.
   - Add `--pdf`, `--output-root`, `--min-image-size`, `--scale` defaulting to `2.0`, and optional `--no-clean` only if useful for debugging.
   - Pattern to mirror: constants in `scripts/scrape_crypto_archive.py:26-42` and dataclass stats in `scripts/scrape_crypto_archive.py:64-72`.
   - Gotcha: keep default paths exactly matching issue #4 output schema.
   - Validation command: `python -m py_compile scripts/extract_book_pdf.py`

3. Implement output preparation.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: ensure `raw/book/pages/` and `raw/book/images/` exist, then remove only generated files matching `page_*.md`, `page_*_fig_*.png`, `full_text.md`, and `image_manifest.json` unless `--no-clean` is used.
   - Pattern to mirror: `ensure_dirs()` from `scripts/scrape_crypto_archive.py:91-93`.
   - Gotcha: never delete `raw/book/wyckoff_methodology_in_depth.pdf`.
   - Validation command: `test -f raw/book/wyckoff_methodology_in_depth.pdf && uv run --extra book python scripts/extract_book_pdf.py --help`

4. Open and validate the PDF.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: use `fitz.open(pdf_path)` in a context manager or close explicitly; fail if missing, encrypted without permission, or `len(doc) != 248`.
   - Pattern to mirror: fail-fast style in `scripts/scrape_crypto_archive.py:96-101`.
   - Gotcha: the current worktree may not contain gitignored PDF after clone; the script should explain that the PDF is required locally.
   - Validation command: `uv run --extra book python - <<'PY'\nimport fitz\nfrom pathlib import Path\np=Path('raw/book/wyckoff_methodology_in_depth.pdf')\nprint(len(fitz.open(p)) if p.exists() else 'missing')\nPY`

5. Extract and normalize text blocks.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: for each page, read `page.get_text("dict", sort=True)["blocks"]`; for text blocks, collect line spans in order, normalize whitespace, fix punctuation spacing, preserve meaningful blank breaks, and omit empty blocks.
   - Pattern to mirror: `clean_text()` in `scripts/download_fraser_images.py:60-64` and Markdown line construction in `scripts/scrape_crypto_archive.py:238-296`.
   - Gotcha: do not over-normalize terms like `mSOS`, `BCLX`, `LPSY`, `JAC`, or chapter headings.
   - Validation command: `uv run --extra book python scripts/extract_book_pdf.py && test $(find raw/book/pages -name 'page_*.md' | wc -l | tr -d ' ') = 248`

6. Detect and export figure blocks.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: for each image block from the dict output, inspect `bbox`, `width`, and `height`; skip blocks where width or height is below the configured minimum; save output as `raw/book/images/page_NNN_fig_M.png`.
   - Pattern to mirror: deterministic image filenames from `scripts/scrape_crypto_archive.py:179-183`.
   - Gotcha: figure index must count only kept images, not skipped decorative images.
   - Validation command: `find raw/book/images -name 'page_*_fig_*.png' | wc -l`

7. Preserve label readability with 2x clipped rendering.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: prefer rendering the page bbox with `page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(bbox), alpha=False)` for each kept figure, because issue #4 requires pixel-baked labels to remain readable. Save PNG output and record final `width_px` and `height_px`.
   - Pattern to mirror: existing scripts save complete image bytes before Markdown references, as in `scripts/scrape_crypto_archive.py:186-225`.
   - Gotcha: PyMuPDF `clip` coordinates are page coordinates, and output dimensions will be scaled; manifest bbox should remain unscaled page coordinates.
   - Validation command: `uv run --extra book python - <<'PY'\nimport fitz\nfrom pathlib import Path\nimgs=sorted(Path('raw/book/images').glob('page_*_fig_*.png'))[:5]\nfor p in imgs:\n    pix=fitz.Pixmap(str(p))\n    print(p.name, pix.width, pix.height)\nPY`

8. Interleave Markdown blocks by position.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: build a list of page items shaped like `{kind, bbox, block_no, text_or_path}` and sort by top coordinate, then left coordinate, then original block number. Emit text blocks and image Markdown `![](images/page_NNN_fig_M.png)` into `page_NNN.md`.
   - Pattern to mirror: `markdown_lines()` in `scripts/scrape_crypto_archive.py:238-282`.
   - Gotcha: issue #4 requires image references at correct positions relative to surrounding text; do not append all figures at the bottom.
   - Validation command: `rg -n \"!\\[\\]\\(images/page_[0-9]{3}_fig_[0-9]+\\.png\\)\" raw/book/pages | head`

9. Write `full_text.md` deterministically.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: concatenate page Markdown in page-number order with a stable page separator such as `\n\n---\n\n` or a heading/comment that does not break downstream Markdown. Keep page file content unchanged inside the full text.
   - Pattern to mirror: sorted manifest/page iteration in existing scripts.
   - Gotcha: `full_text.md` must not include absolute local paths.
   - Validation command: `test -s raw/book/full_text.md && rg -n \"page_001|page_248|!\\[\\]\\(images/\" raw/book/full_text.md`

10. Write `image_manifest.json`.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: write a list of dicts exactly matching issue #4 schema: `image_path`, `page_number`, `figure_index`, `position_in_page` with `top/left/right/bottom`, `format`, `size_bytes`, `width_px`, and `height_px`. Use relative paths like `raw/book/images/page_152_fig_1.png`.
   - Pattern to mirror: temp-file manifest write in `scripts/scrape_crypto_archive.py:366-369`.
   - Gotcha: JSON order and indentation must be stable; include trailing newline.
   - Validation command: `uv run --extra book python -m json.tool raw/book/image_manifest.json >/tmp/book_manifest.json`

11. Add built-in quality validation.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: after writing, scan all generated page Markdown plus `full_text.md` for the four known artifact strings. If any are found, print offending path/pattern and exit non-zero.
   - Pattern to mirror: final summary counters in `scripts/download_fraser_images.py:283-294`.
   - Gotcha: match case-insensitively enough to catch exact issue examples, but do not invent broad word-joining rewrites.
   - Validation command: `! rg -n \"gre ater|selle rs|tra ding|wycko ff\" raw/book/pages raw/book/full_text.md`

12. Add final stats output.
   - File: `scripts/extract_book_pdf.py`
   - Instruction: print pages written, figures written, figures skipped, total image bytes, manifest path, and artifact check status.
   - Pattern to mirror: `scripts/scrape_crypto_archive.py:416-423`.
   - Gotcha: stats should be stable and useful for issue closeout.
   - Validation command: `uv run --extra book python scripts/extract_book_pdf.py`

13. Run extraction and inspect output shape.
   - Files: `raw/book/pages/`, `raw/book/images/`, `raw/book/full_text.md`, `raw/book/image_manifest.json`
   - Instruction: run the script once with defaults. Confirm 248 page files, expected image range about 150-300 figures, non-empty manifest, and no artifact patterns.
   - Pattern to mirror: issue #4 acceptance criteria.
   - Gotcha: if image count is outside expected range, inspect skipped-image threshold and PyMuPDF block detection before accepting.
   - Validation command: `test $(find raw/book/pages -name 'page_*.md' | wc -l | tr -d ' ') = 248 && python - <<'PY'\nimport json\nfrom pathlib import Path\nm=json.loads(Path('raw/book/image_manifest.json').read_text())\nprint(len(m))\nassert 150 <= len(m) <= 300, len(m)\nPY`

14. Spot-check five representative pages.
   - Files: generated page Markdown and images.
   - Instruction: inspect at least page 007 or first figure page, one middle event chapter page, one phase chapter page, one trading chapter page, and page 248 or last page. Check that text is clean and image refs are near relevant surrounding text.
   - Pattern to mirror: issue #4 random 5-page spot-check acceptance criterion.
   - Gotcha: document the exact page numbers and result in the implementation final response, not in a separate tracked artifact unless requested.
   - Validation command: `for p in 007 101 152 184 248; do printf '\\n--- page_%s ---\\n' \"$p\"; sed -n '1,80p' raw/book/pages/page_${p}.md; done`

15. Verify idempotency.
   - Files: all generated outputs.
   - Instruction: run the script a second time and verify `git diff -- raw/book scripts/extract_book_pdf.py` is empty after the second run relative to the first run's generated state.
   - Pattern to mirror: deterministic output and skip behavior in existing data scripts.
   - Gotcha: metadata must not include run timestamps.
   - Validation command: `uv run --extra book python scripts/extract_book_pdf.py && git diff --exit-code -- raw/book scripts/extract_book_pdf.py`

16. Final issue acceptance check.
   - Files: generated outputs and script.
   - Instruction: run all acceptance checks before commit.
   - Pattern to mirror: issue #4 acceptance section.
   - Gotcha: `raw/book/*.pdf` must remain untracked.
   - Validation command: `git status --short && git check-ignore -v raw/book/wyckoff_methodology_in_depth.pdf && ! git ls-files raw/book/wyckoff_methodology_in_depth.pdf --error-unmatch`

## Testing Strategy

Use script-level validation rather than a separate test suite because this repo currently has standalone data scripts and no test harness.

- Unit-like smoke checks: `python -m py_compile scripts/extract_book_pdf.py` and `uv run --extra book python scripts/extract_book_pdf.py --help`.
- Source validation: PDF exists, opens with PyMuPDF, and has 248 pages.
- Output shape validation: exactly 248 page Markdown files, `full_text.md` exists, JSON manifest parses.
- Image validation: count is approximately 150-300; every manifest path exists; every image is at least 50x50 final pixels and readable.
- Text validation: known artifact patterns absent from all generated page Markdown and full text.
- Placement validation: five page spot-checks confirm image refs appear near relevant text, not batched at page end.
- Idempotency validation: second run produces zero diff.

## Validation Commands

```bash
uv run --extra book python scripts/extract_book_pdf.py --help
python -m py_compile scripts/extract_book_pdf.py
uv run --extra book python scripts/extract_book_pdf.py
test "$(find raw/book/pages -name 'page_*.md' | wc -l | tr -d ' ')" = "248"
python -m json.tool raw/book/image_manifest.json >/tmp/book_image_manifest.json
python - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("raw/book/image_manifest.json").read_text())
print(f"images={len(manifest)}")
assert 150 <= len(manifest) <= 300
for entry in manifest:
    assert Path(entry["image_path"]).exists(), entry["image_path"]
    assert entry["width_px"] >= 50 and entry["height_px"] >= 50, entry
PY
! rg -n "gre ater|selle rs|tra ding|wycko ff" raw/book/pages raw/book/full_text.md
uv run --extra book python scripts/extract_book_pdf.py
git diff --exit-code -- raw/book scripts/extract_book_pdf.py
git check-ignore -v raw/book/wyckoff_methodology_in_depth.pdf
```

## Acceptance Criteria

- `scripts/extract_book_pdf.py` exists and runs with `uv run --extra book`.
- `raw/book/pages/` contains exactly 248 files named `page_001.md` through `page_248.md`.
- `raw/book/images/` contains extracted figure images named `page_NNN_fig_M.png`.
- Very small decorative images under 50x50 px are skipped.
- Figure labels rendered into pixels remain readable; clipped pixmaps use 2x scale where needed.
- `raw/book/full_text.md` concatenates all pages deterministically.
- `raw/book/image_manifest.json` lists every extracted image with page number, figure index, bbox, format, byte size, and dimensions.
- Generated text has no `gre ater`, `selle rs`, `tra ding`, or `wycko ff` patterns.
- Five random/representative pages are spot-checked for clean text and correct relative image placement.
- Re-running the script produces zero changes.
- `raw/book/wyckoff_methodology_in_depth.pdf` remains untracked and gitignored.

## Completion Checklist

- [ ] Read issue #4 body and confirm acceptance criteria are still current.
- [ ] Confirm local PDF exists at `raw/book/wyckoff_methodology_in_depth.pdf`.
- [ ] Add `scripts/extract_book_pdf.py`.
- [ ] Run extraction through `uv run --extra book`.
- [ ] Verify exactly 248 page Markdown files.
- [ ] Verify manifest JSON parses and every listed image exists.
- [ ] Verify image count is in the expected 150-300 range or investigate discrepancy.
- [ ] Verify no known OCR artifact patterns remain.
- [ ] Spot-check five pages and record page numbers in implementation final response.
- [ ] Run second extraction and verify zero diff.
- [ ] Confirm source PDF is ignored and not staged.
- [ ] Commit script and generated raw outputs, excluding the PDF.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Gitignored PDF is not present in implementer's worktree | Extraction cannot run | Script fails clearly; implementer must place PDF locally before running |
| PyMuPDF text block order differs from human reading order | Inline image refs may be misplaced | Sort blocks by coordinates and spot-check five pages; adjust ordering helper if needed |
| Embedded images are low resolution or labels unreadable | Later Vision captioning and wiki ingest lose canonical labels | Use 2x clipped `get_pixmap()` rendering for figure blocks |
| Decorative bullets inflate figure count | Noisy image corpus | Skip blocks with width or height below 50 px |
| Duplicate image resources appear multiple times | Manifest/image count confusing | Count figures by page occurrence; deterministic page/figure naming preserves page context |
| Stale output survives re-run | Idempotency failure | Clean only generated page/image/manifest/full-text outputs before writing |
| Text cleanup removes meaningful Wyckoff labels | Semantic damage | Limit cleanup to whitespace and punctuation spacing; do not rewrite domain terms |

## Notes

- External research used: official PyMuPDF documentation for `Page.get_text()`, image metadata, image rectangles, and `Page.get_pixmap()`: https://pymupdf.readthedocs.io/en/latest/page.html
- The source issue says "Preserve original image format where possible", but the requested output schema names `.png` files. The implementation should prioritize the schema and readability by writing PNG outputs; if original bytes are also preserved, that should be an explicit extension and not required for issue #4.
- Current local inspection did not find `raw/book/` in the tracked tree because the source PDF is gitignored. Issue #4 states the prerequisite was resolved on 2026-05-25 and the PDF is available locally at `raw/book/wyckoff_methodology_in_depth.pdf`; implementation must verify this before extraction.
- PRD status was not changed by this planning pass because the user requested committing and pushing the plan file only.
