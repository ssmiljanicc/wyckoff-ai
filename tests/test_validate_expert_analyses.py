from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from spona.validated_ingest.core import runner

from scripts import validate_expert_analyses as v

ROOT = Path(__file__).resolve().parents[1]

VALID_FRONTMATTER = """---
source: raw/book/pages/page_014.md
page: 14
asset: unknown
timeframe: unknown
wyckoff_event: none
structure: accumulation
phase: unknown
image_path: raw/book/images/page_014_fig_1.png
type: schematic
status: candidate
---

## Verbatim pasus

> Kratak citat.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _extract(kb_root: Path, name: str, text: str) -> Path:
    _write(kb_root / "wiki" / "by-structure" / "accumulation.md", "")
    _write(kb_root / "wiki" / "by-event" / "spring.md", "")
    path = kb_root / "wiki" / "extracts" / name
    _write(path, text)
    return path


# --- check_extract_frontmatter ------------------------------------------------


def test_valid_extract_has_no_findings(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_valid.md", VALID_FRONTMATTER)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert findings == []


def test_missing_required_field_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("wyckoff_event: none\n", "")
    path = _extract(kb_root, "book_p014_missing_field.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    codes = [(f.severity, f.code) for f in findings]
    assert ("FAIL", "F-EXTRACT-FRONTMATTER") in codes
    assert any("wyckoff_event" in f.message for f in findings)


def test_invalid_type_enum_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("type: schematic", "type: not-a-real-type")
    path = _extract(kb_root, "book_p014_bad_type.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any(f.severity == "FAIL" and "type" in f.message for f in findings)


def test_invalid_status_enum_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("status: candidate", "status: not-a-real-status")
    path = _extract(kb_root, "book_p014_bad_status.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any(f.severity == "FAIL" and "status" in f.message for f in findings)


def test_missing_page_and_post_url_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("page: 14\n", "")
    path = _extract(kb_root, "book_p014_no_locator.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any("page/post_url" in f.message for f in findings)


def test_unknown_is_not_valid_event_or_structure_sentinel(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("wyckoff_event: none", "wyckoff_event: unknown")
    path = _extract(kb_root, "bad_event_sentinel.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any("wyckoff_event" in f.message for f in findings)


def test_event_and_structure_cannot_both_be_none(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("structure: accumulation", "structure: none")
    path = _extract(kb_root, "unindexable_schematic.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any("oba biti 'none'" in f.message for f in findings)


@pytest.mark.parametrize("field", ["asset", "timeframe"])
def test_asset_and_timeframe_reject_none_sentinel(tmp_path: Path, field: str) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(f"{field}: unknown", f"{field}: none")
    path = _extract(kb_root, f"bad_{field}_sentinel.md", text)

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any(
        field in finding.message and "'none'" in finding.message for finding in findings
    )


# --- check_extract_source_exists (PR #96 review nalaz) -------------------------


def test_nonexistent_source_path_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md",
        "source: raw/book/pages/page_does_not_exist.md",
    )
    path = _extract(kb_root, "book_p014_bad_source.md", text)

    findings = v.check_extract_source_exists(
        [path], repo_root=tmp_path, kb_root=kb_root
    )

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-SOURCE" for f in findings)


def test_existing_source_path_passes(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_good_source.md", VALID_FRONTMATTER)
    _write(tmp_path / "raw" / "book" / "pages" / "page_014.md", "sadržaj")

    findings = v.check_extract_source_exists(
        [path], repo_root=tmp_path, kb_root=kb_root
    )

    assert findings == []


def test_source_outside_expected_raw_trees_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "raw/book/pages/page_014.md", "raw/book/notes/page_014.md"
    )
    path = _extract(kb_root, "bad_tree.md", text)
    _write(tmp_path / "raw" / "book" / "notes" / "page_014.md", "Kratak citat.")

    findings = v.check_extract_source_exists([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-SOURCE" for f in findings)


def test_book_page_must_match_source_filename(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(
        kb_root, "wrong_page.md", VALID_FRONTMATTER.replace("page: 14", "page: 15")
    )
    _write(tmp_path / "raw" / "book" / "pages" / "page_014.md", "Kratak citat.")

    findings = v.check_extract_source_exists([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-PROVENANCE" for f in findings)


def test_post_url_must_match_source_header(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md\npage: 14",
        "source: raw/crypto_archive/posts/vol-14.md\npost_url: https://wrong.example/",
    ).replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: raw/crypto_archive/images/vol-14/chart.png",
    )
    path = _extract(kb_root, "wrong_url.md", text)
    _write(
        tmp_path / "raw" / "crypto_archive" / "posts" / "vol-14.md",
        "URL: https://right.example/\n\nKratak citat.\n",
    )

    findings = v.check_extract_source_exists([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-PROVENANCE" for f in findings)


# --- check_extract_image_path ---------------------------------------------------


def test_nonexistent_image_path_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_bad_image.md", VALID_FRONTMATTER)

    findings = v.check_extract_image_path([path], repo_root=tmp_path, kb_root=kb_root)

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-IMAGE" for f in findings)


def test_unmapped_remote_image_marker_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: (remote: https://example.com/x.jpg)",
    )
    path = _extract(kb_root, "book_p014_remote_image.md", text)

    findings = v.check_extract_image_path([path], repo_root=tmp_path, kb_root=kb_root)

    assert any(f.code == "F-EXTRACT-IMAGE-PROVENANCE" for f in findings)


def test_book_image_must_match_manifest_page(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_bad_mapping.md", VALID_FRONTMATTER)
    _write(tmp_path / "raw" / "book" / "images" / "page_014_fig_1.png", "png")
    _write(
        tmp_path / "raw" / "book" / "image_manifest.json",
        '[{"image_path":"raw/book/images/page_014_fig_1.png","page_number":13}]',
    )

    findings = v.check_extract_image_path([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-IMAGE-PROVENANCE" for f in findings)


def test_adjacent_page_range_allows_image_on_first_and_quote_on_second(
    tmp_path: Path,
) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("page: 14", "page: 14\npage_range: 14-15")
    path = _extract(kb_root, "book_adjacent.md", text)
    _write(
        tmp_path / "raw" / "book" / "pages" / "page_014.md",
        "Slika je na prethodnoj strani.\n",
    )
    _write(tmp_path / "raw" / "book" / "pages" / "page_015.md", "Kratak citat.\n")
    _write(tmp_path / "raw" / "book" / "images" / "page_014_fig_1.png", "png")
    _write(
        tmp_path / "raw" / "book" / "image_manifest.json",
        '[{"image_path":"raw/book/images/page_014_fig_1.png","page_number":14}]',
    )

    assert v.check_extract_image_path([path], tmp_path, kb_root) == []
    assert v.check_extract_verbatim([path], tmp_path, kb_root) == []


def test_adjacent_page_range_rejects_image_only_on_continuation_page(
    tmp_path: Path,
) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("page: 14", "page: 14\npage_range: 14-15").replace(
        "raw/book/images/page_014_fig_1.png",
        "raw/book/images/page_015_fig_1.png",
    )
    path = _extract(kb_root, "book_wrong_image_page.md", text)
    _write(tmp_path / "raw" / "book" / "images" / "page_015_fig_1.png", "png")
    _write(
        tmp_path / "raw" / "book" / "image_manifest.json",
        '[{"image_path":"raw/book/images/page_015_fig_1.png","page_number":15}]',
    )

    findings = v.check_extract_image_path([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-IMAGE-PROVENANCE" and "primary" in f.message
        for f in findings
    )


def test_non_adjacent_page_range_fails(tmp_path: Path) -> None:
    span, findings = v._book_page_span({"page": "14", "page_range": "14-16"}, "x.md")

    assert span is None
    assert any(f.code == "F-EXTRACT-PROVENANCE" for f in findings)


def test_crypto_image_must_be_linked_from_same_post(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md\npage: 14",
        "source: raw/crypto_archive/posts/vol-14.md\npost_url: https://example.com/14",
    ).replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: raw/crypto_archive/images/vol-14/chart.png",
    )
    path = _extract(kb_root, "crypto_mapping.md", text)
    _write(
        tmp_path / "raw" / "crypto_archive" / "posts" / "vol-14.md",
        "URL: https://example.com/14\n\n![](../images/other/chart.png)\nKratak citat.\n",
    )
    _write(
        tmp_path / "raw" / "crypto_archive" / "images" / "vol-14" / "chart.png", "png"
    )

    findings = v.check_extract_image_path([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-IMAGE-PROVENANCE" for f in findings)


def test_crypto_image_linked_from_same_post_passes(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md\npage: 14",
        "source: raw/crypto_archive/posts/vol-14.md\npost_url: https://example.com/14",
    ).replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: raw/crypto_archive/images/vol-14/chart.png",
    )
    path = _extract(kb_root, "crypto_mapping.md", text)
    _write(
        tmp_path / "raw" / "crypto_archive" / "posts" / "vol-14.md",
        "URL: https://example.com/14\n\n![](../images/vol-14/chart.png)\nKratak citat.\n",
    )
    _write(
        tmp_path / "raw" / "crypto_archive" / "images" / "vol-14" / "chart.png",
        "png",
    )

    assert v.check_extract_image_path([path], tmp_path, kb_root) == []


def test_fraser_image_must_be_mapped_to_same_post(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md\npage: 14",
        "source: raw/bruce_fraser/posts/article-a.md\npost_url: https://example.com/a",
    ).replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: raw/bruce_fraser/images/chart.jpg",
    )
    path = _extract(kb_root, "fraser_mapping.md", text)
    _write(
        tmp_path / "raw" / "bruce_fraser" / "posts" / "article-a.md",
        "URL: https://example.com/a\n\n![](../images/chart.jpg)\nKratak citat.\n",
    )
    _write(tmp_path / "raw" / "bruce_fraser" / "images" / "chart.jpg", "jpg")
    _write(
        tmp_path / "raw" / "bruce_fraser" / "images-manifest.json",
        '{"images":[{"path":"raw/bruce_fraser/images/chart.jpg","url":"https://cdn.example/chart.jpg","status":"available","references":[{"post":"raw/bruce_fraser/posts/article-b.md"}]}]}',
    )

    findings = v.check_extract_image_path([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-IMAGE-PROVENANCE" for f in findings)


# --- Ordered Markdown evidence + conservative contradiction checks ------------


def _crypto_evidence_extract(
    tmp_path: Path,
    *,
    source_body: str,
    declared_image: str = "raw/crypto_archive/images/vol-14/chart-a.png",
    asset: str = "BTC/USD",
    timeframe: str = "daily",
    context: str = "Daily BTC/USD chart je locating aid.",
) -> tuple[Path, Path, Path]:
    kb_root = tmp_path / "research" / "expert-analyses"
    source = "raw/crypto_archive/posts/vol-14.md"
    text = (
        VALID_FRONTMATTER.replace(
            "source: raw/book/pages/page_014.md\npage: 14",
            f"source: {source}\npost_url: https://example.com/14",
        )
        .replace("asset: unknown", f"asset: {asset}")
        .replace("timeframe: unknown", f"timeframe: {timeframe}")
        .replace(
            "image_path: raw/book/images/page_014_fig_1.png",
            f"image_path: {declared_image}",
        )
        + f"\n## Kontekst\n\n{context}\n"
    )
    path = _extract(kb_root, "crypto_evidence.md", text)
    source_path = tmp_path / source
    _write(
        source_path,
        "URL: https://example.com/14\n\n" + source_body,
    )
    return path, source_path, kb_root


def test_markdown_evidence_preserves_heading_and_image_order(tmp_path: Path) -> None:
    source = tmp_path / "raw" / "crypto_archive" / "posts" / "vol-14.md"
    _write(
        source,
        "### BTC/USD Daily chart\n"
        "![](../images/vol-14/chart-a.png)\n\n"
        "(click on chart for active version)\n\n"
        "Kratak citat.\n",
    )

    blocks = v._markdown_evidence_blocks(source, tmp_path)

    assert blocks == [
        v.MarkdownEvidenceBlock(
            heading="BTC/USD Daily chart",
            image_targets=("raw/crypto_archive/images/vol-14/chart-a.png",),
            body="(click on chart for active version)\n\nKratak citat.",
        )
    ]


def test_consecutive_images_before_shared_passage_remain_one_group(
    tmp_path: Path,
) -> None:
    source = tmp_path / "raw" / "bruce_fraser" / "posts" / "article.md"
    _write(
        source,
        "![](../images/a.png)\n\n"
        "(Click to view a live version)\n\n"
        "![](../images/b.png)\n\n"
        "(Click to view a live version)\n\n"
        "Shared passage.\n",
    )

    blocks = v._markdown_evidence_blocks(source, tmp_path)

    assert len(blocks) == 1
    assert blocks[0].image_targets == (
        "raw/bruce_fraser/images/a.png",
        "raw/bruce_fraser/images/b.png",
    )
    assert "Shared passage." in blocks[0].body


def test_repeated_verbatim_passage_is_unresolved_not_guessed(tmp_path: Path) -> None:
    path, source, _kb_root = _crypto_evidence_extract(
        tmp_path,
        source_body=(
            "### First\n![](../images/vol-14/chart-a.png)\nKratak citat.\n"
            "### Second\n![](../images/vol-14/chart-b.png)\nKratak citat.\n"
        ),
    )
    blocks = v._markdown_evidence_blocks(source, tmp_path)

    assert (
        v._unique_verbatim_block_match(path.read_text(encoding="utf-8"), blocks)
        is None
    )


def test_wrong_image_outside_unambiguous_passage_group_fails(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        declared_image="raw/crypto_archive/images/vol-14/chart-c.png",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n"
            "### Other\n![](../images/vol-14/chart-c.png)\nOther passage.\n"
        ),
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-IMAGE-ADJACENCY" for f in findings)


def test_following_image_in_same_section_is_ambiguous_and_allowed(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        declared_image="raw/crypto_archive/images/vol-14/chart-b.png",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\n"
            "Kratak citat.\n![](../images/vol-14/chart-b.png)\n"
        ),
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert not any(f.code == "F-EXTRACT-IMAGE-ADJACENCY" for f in findings)


def test_context_timeframe_contradiction_is_hard_failure(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="weekly",
        context="Daily BTC/USD chart je locating aid.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "Kontekst tokenu 'daily'" in f.message
        for f in findings
    )


def test_unknown_timeframe_with_one_explicit_context_token_fails(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="unknown",
        context="Daily BTC/USD chart je locating aid.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-METADATA-CONTRADICTION" for f in findings)


def test_context_asset_contradiction_is_hard_failure(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        asset="AAPL",
        context="Daily FXI chart je locating aid.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "Kontekst tokenu 'FXI'" in f.message
        for f in findings
    )


def test_book_context_metadata_contradiction_is_hard_failure(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = (
        VALID_FRONTMATTER.replace("timeframe: unknown", "timeframe: weekly")
        + "\n## Kontekst\n\nDaily AAPL chart je locating aid.\n"
    )
    path = _extract(kb_root, "book_context_contradiction.md", text)

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "Kontekst tokenu 'daily'" in f.message
        for f in findings
    )


def test_multiple_context_timeframes_are_ambiguous_and_skipped(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="unknown",
        context="Daily i weekly paneli su prikazani zajedno.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    assert v.check_extract_evidence_consistency([path], tmp_path, kb_root) == []


def test_point_and_figure_form_alone_does_not_claim_timeframe(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="unknown",
        context="Point-and-Figure chart ne navodi vremenski interval.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    assert v.check_extract_evidence_consistency([path], tmp_path, kb_root) == []


def test_current_chart_declaration_outranks_comparison_timeframes(
    tmp_path: Path,
) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="monthly",
        context="Monthly BTC/USD chart je locating aid.",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\n"
            "Kratak citat. Evaluating the monthly chart adds context to price "
            "behaviors seen on the daily and weekly charts. A later reaction "
            "appears as accumulation on the daily chart.\n"
        ),
    )

    assert v.check_extract_evidence_consistency([path], tmp_path, kb_root) == []


def test_current_chart_declaration_still_proves_real_contradiction(
    tmp_path: Path,
) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        timeframe="weekly",
        context="Weekly BTC/USD chart je locating aid.",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\n"
            "Kratak citat. Evaluating the monthly chart adds context to price "
            "behaviors seen on the daily and weekly charts.\n"
        ),
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        finding.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "raw chart tvrdnji 'monthly'" in finding.message
        for finding in findings
    )


def test_exact_raw_chart_asset_mismatch_fails_without_alias_guessing(
    tmp_path: Path,
) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        asset="AAPL",
        context="Daily AAPL chart je locating aid.",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\n"
            "Kratak citat. On the daily chart of FXI, weakness is visible.\n"
        ),
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "asset 'AAPL'" in f.message
        for f in findings
    )


def test_exact_raw_heading_asset_mismatch_is_detected(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        asset="AAPL",
        context="Locating aid bez metadata tvrdnje.",
        source_body=(
            "### FXI Daily chart\n"
            "![](../images/vol-14/chart-a.png)\nKratak citat.\n"
        ),
    )

    findings = v.check_extract_evidence_consistency([path], tmp_path, kb_root)

    assert any(
        f.code == "F-EXTRACT-METADATA-CONTRADICTION"
        and "raw chart tvrdnji 'FXI'" in f.message
        for f in findings
    )


def test_asset_alias_is_not_guessed(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        asset="BTC/USD",
        context="Daily Bitcoin chart je locating aid.",
        source_body="### Target\n![](../images/vol-14/chart-a.png)\nKratak citat.\n",
    )

    assert v.check_extract_evidence_consistency([path], tmp_path, kb_root) == []


def test_phase_tokens_do_not_create_semantic_findings(tmp_path: Path) -> None:
    path, _source, kb_root = _crypto_evidence_extract(
        tmp_path,
        context="Daily BTC/USD chart prolazi kroz Phase B i Phase D.",
        source_body=(
            "### Target\n![](../images/vol-14/chart-a.png)\n"
            "Kratak citat. Phase B prelazi u Phase D.\n"
        ),
    )

    assert v.check_extract_evidence_consistency([path], tmp_path, kb_root) == []


def test_extract_template_documents_conservative_evidence_contract() -> None:
    template = (
        ROOT / "research/expert-analyses/EXTRACT_TEMPLATE.md"
    ).read_text(encoding="utf-8")

    assert "deterministički dokaz" in template
    assert "P&F je forma grafikona" in template
    assert "event/structure/phase" in template
    assert "semantičku procenu" in template
    assert "--ocr-evidence" in template
    assert "validator bez tog flag-a ne pokreće OCR" in template
    assert "nečitljiv, dvosmislen, nestabilan, nedostajući ili zastareo dokaz" in template
    assert "ne popunjava metadata" in template


def test_evidence_consistency_is_composed_into_validator(monkeypatch) -> None:
    marker = v.core.Finding(
        "FAIL", "F-EXTRACT-METADATA-CONTRADICTION", "test marker", "test.md"
    )
    monkeypatch.setattr(
        v, "check_extract_evidence_consistency", lambda *_args: [marker]
    )

    findings = v.collect_findings(
        ROOT / "research/expert-analyses", ROOT, skip_git=True
    )

    assert marker in findings


def test_cli_fails_when_evidence_consistency_returns_failure(
    monkeypatch, capsys
) -> None:
    marker = v.core.Finding(
        "FAIL", "F-EXTRACT-METADATA-CONTRADICTION", "test marker", "test.md"
    )
    monkeypatch.setattr(v, "collect_findings", lambda *_args, **_kwargs: [marker])

    result = v.main(
        [
            "--kb-root",
            str(ROOT / "research/expert-analyses"),
            "--skip-git",
        ]
    )

    assert result == 1
    assert "F-EXTRACT-METADATA-CONTRADICTION" in capsys.readouterr().out


# --- Optional Fraser header OCR evidence --------------------------------------


OCR_FIXTURE = ROOT / "tests/fixtures/fraser_header_ocr_b17_v1.json"


def _fraser_ocr_extract(
    kb_root: Path,
    name: str,
    image_path: str,
    *,
    asset: str,
    timeframe: str,
) -> Path:
    text = (
        VALID_FRONTMATTER.replace(
            "source: raw/book/pages/page_014.md\npage: 14",
            "source: raw/bruce_fraser/posts/article.md\npost_url: https://example.com/article",
        )
        .replace("asset: unknown", f"asset: {asset}")
        .replace("timeframe: unknown", f"timeframe: {timeframe}")
        .replace("image_path: raw/book/images/page_014_fig_1.png", f"image_path: {image_path}")
    )
    return _extract(kb_root, name, text)


def _fixture_image_map(evidence: dict) -> dict[str, str]:
    return {
        Path(record["image_path"]).name: record["image_path"]
        for record in evidence["images"]
    }


def test_b17_historical_ocr_evidence_catches_eight_image_defects(
    tmp_path: Path,
) -> None:
    evidence = v.load_fraser_ocr_evidence(OCR_FIXTURE)
    images = _fixture_image_map(evidence)
    historical = (
        ("p003_img02", "14320745812221615332131.jpg", "AAPL", "weekly"),
        ("p004_img02", "1432686852895916959173.png", "JPM", "monthly"),
        ("p004_img03", "1432686867397868513327.png", "SBUX", "weekly"),
        ("p004_img04", "14326868785531869541943.png", "WAB", "weekly"),
        ("p004_img05", "14326868953111472110113.png", "V", "weekly"),
        ("p004_img06", "14326869071271044033839.png", "ADI", "weekly"),
        ("p005_img02", "14332827381361921633116.png", "SLB", "weekly"),
        ("p005_img03", "14332833268921091362512.png", "DOW", "weekly"),
        ("p006_img02", "14342293874161176365540.png", "CMG", "weekly"),
        ("p020_img03", "14413150039551001324999.png", "ISRG", "daily"),
    )
    kb_root = tmp_path / "research" / "expert-analyses"
    paths = [
        _fraser_ocr_extract(
            kb_root,
            f"{name}.md",
            images[filename],
            asset=asset,
            timeframe=timeframe,
        )
        for name, filename, asset, timeframe in historical
    ]

    findings = v.check_extract_ocr_evidence(paths, ROOT, kb_root, evidence)
    failures = [
        finding
        for finding in findings
        if finding.code == "F-EXTRACT-OCR-METADATA-CONTRADICTION"
    ]
    failed_cases = {Path(finding.location).stem for finding in failures}

    assert len(failures) == 12  # four two-field + four one-field contradictions
    assert len(failed_cases) == 8
    assert "p003_img02" not in failed_cases
    assert "p020_img03" not in failed_cases


def test_ocr_evidence_b17_pass_controls_have_no_mismatch(tmp_path: Path) -> None:
    evidence = v.load_fraser_ocr_evidence(OCR_FIXTURE)
    images = _fixture_image_map(evidence)
    controls = (
        ("1433284936955494306808.png", "UPS", "weekly"),
        ("1434227844229754672103.png", "DJIA", "weekly"),
        ("143500243259851525957.png", "KBH", "weekly"),
        ("1437104982965749267360.png", "GLW", "weekly"),
        ("1436477575284387740185.png", "CENX", "weekly"),
        ("14389630456271116338338.png", "DIS", "weekly"),
        ("1441314934537418192387.png", "AKAM", "daily"),
        ("1446232682289599151823.png", "ARMH", "weekly"),
        ("1454044162229867495322.jpg", "BIIB", "monthly"),
    )
    kb_root = tmp_path / "research" / "expert-analyses"
    paths = [
        _fraser_ocr_extract(
            kb_root,
            f"pass_{index}.md",
            images[filename],
            asset=asset,
            timeframe=timeframe,
        )
        for index, (filename, asset, timeframe) in enumerate(controls)
    ]

    findings = v.check_extract_ocr_evidence(paths, ROOT, kb_root, evidence)

    assert not any(
        finding.code == "F-EXTRACT-OCR-METADATA-CONTRADICTION"
        for finding in findings
    )


@pytest.mark.parametrize(
    ("declared", "observed", "expect_failure"),
    [
        ("$INDU", "DJIA", False),
        ("DJIA", "$INDU", False),
        ("$DJUSAR", "DJIA", True),
        ("$WTIC / XLE", "WTIC", False),
        ("$WTIC / XLE", "XOM", True),
        ("SHOP", "SHOP", False),
        ("SHOP", "HOP", True),
    ],
)
def test_ocr_evidence_matches_aliases_and_explicit_composite_members(
    tmp_path: Path, declared: str, observed: str, expect_failure: bool
) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    record = next(
        record for record in evidence["images"] if record["asset"]["value"] == "DJIA"
    )
    record["asset"]["value"] = observed
    record["asset"]["runs"] = [observed, observed]
    for run_evidence in record["asset"]["evidence"]:
        run_evidence[0]["text"] = observed
    evidence["images"] = [record]
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "alias.md",
        record["image_path"],
        asset=declared,
        timeframe="weekly",
    )

    findings = v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence)
    failures = [
        finding
        for finding in findings
        if finding.code == "F-EXTRACT-OCR-METADATA-CONTRADICTION"
    ]

    assert bool(failures) is expect_failure


@pytest.mark.parametrize(
    ("declared", "expect_failure"),
    [
        ("TRAN and INDU", False),
        ("TRAN and XLE", True),
        ("TRAN and INDU and XLE", True),
        ("TRAN", False),
    ],
)
def test_ocr_evidence_compares_stable_panel_members_for_multi_asset_declaration(
    tmp_path: Path, declared: str, expect_failure: bool
) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    record = next(
        record for record in evidence["images"] if record["asset"]["value"] == "DJIA"
    )
    record["asset"].update(
        {
            "value": "TRAN",
            "runs": ["TRAN", "TRAN"],
            "members": ["DJIA", "TRAN"],
            "members_decision_eligible": True,
            "member_runs": [["DJIA", "TRAN"], ["DJIA", "TRAN"]],
            "member_evidence": record["asset"]["evidence"],
        }
    )
    evidence["images"] = [record]
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "multi_panel.md",
        record["image_path"],
        asset=declared,
        timeframe="weekly",
    )

    findings = v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence)
    failures = [
        finding
        for finding in findings
        if finding.code == "F-EXTRACT-OCR-METADATA-CONTRADICTION"
    ]

    assert bool(failures) is expect_failure


def test_ocr_evidence_unstable_panel_members_are_safe_unknown(tmp_path: Path) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    record = next(
        record for record in evidence["images"] if record["asset"]["value"] == "DJIA"
    )
    record["asset"].update(
        {
            "value": "TRAN",
            "runs": ["TRAN", "TRAN"],
            "members": [],
            "members_decision_eligible": False,
            "member_runs": [["DJIA", "TRAN"], ["TRAN"]],
            "member_evidence": record["asset"]["evidence"],
        }
    )
    evidence["images"] = [record]
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "unstable_multi_panel.md",
        record["image_path"],
        asset="TRAN and INDU",
        timeframe="weekly",
    )

    findings = v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence)

    assert not any(finding.severity == "FAIL" for finding in findings)


def test_ocr_evidence_unknown_frontmatter_never_becomes_failure(tmp_path: Path) -> None:
    evidence = v.load_fraser_ocr_evidence(OCR_FIXTURE)
    images = _fixture_image_map(evidence)
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "unknown.md",
        images["1432686852895916959173.png"],
        asset="unknown",
        timeframe="unknown",
    )

    assert v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence) == []


def test_ocr_evidence_stale_hash_warns_but_never_hard_fails(tmp_path: Path) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    record = evidence["images"][0]
    record["sha256"] = "0" * 64
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "stale.md",
        record["image_path"],
        asset="WRONG",
        timeframe="monthly",
    )

    findings = v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence)

    assert [(finding.severity, finding.code) for finding in findings] == [
        ("WARN", "W-EXTRACT-OCR-EVIDENCE-SKIPPED")
    ]


def test_ocr_evidence_unstable_or_incomplete_field_never_hard_fails(
    tmp_path: Path,
) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    record = evidence["images"][1]
    record["asset"]["runs"] = ["FISV", "JPM"]
    record["timeframe"]["evidence"] = [
        [{"text": "Daily", "confidence": "not-a-number"}],
        [{"text": "Daily", "confidence": "not-a-number"}],
    ]
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _fraser_ocr_extract(
        kb_root,
        "unstable.md",
        record["image_path"],
        asset="JPM",
        timeframe="monthly",
    )

    findings = v.check_extract_ocr_evidence([path], ROOT, kb_root, evidence)

    assert not any(finding.severity == "FAIL" for finding in findings)


def test_ocr_evidence_loader_rejects_unknown_schema(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write(evidence_path, '{"schema":"unknown","generator":{},"images":[]}')

    with pytest.raises(v.core.ValidationError, match="schema"):
        v.load_fraser_ocr_evidence(evidence_path)


def test_ocr_evidence_loader_rejects_stale_parser_version(tmp_path: Path) -> None:
    evidence = json.loads(OCR_FIXTURE.read_text(encoding="utf-8"))
    evidence["generator"]["parser_version"] = 9
    evidence_path = tmp_path / "evidence.json"
    _write(evidence_path, json.dumps(evidence))

    with pytest.raises(v.core.ValidationError, match="generator contract"):
        v.load_fraser_ocr_evidence(evidence_path)


def test_default_cli_never_loads_ocr_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        v,
        "load_fraser_ocr_evidence",
        lambda *_args: pytest.fail("default CLI must not load OCR evidence"),
    )
    monkeypatch.setattr(v, "collect_findings", lambda *_args, **_kwargs: [])

    result = v.main(
        ["--kb-root", str(ROOT / "research/expert-analyses"), "--skip-git"]
    )

    assert result == 0


# --- check_extract_verbatim ----------------------------------------------------


def test_verbatim_quote_preserves_ocr_and_matches_exactly(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("Kratak citat.", "selle rs ostaju verbatim.")
    path = _extract(kb_root, "ocr.md", text)
    _write(
        tmp_path / "raw" / "book" / "pages" / "page_014.md",
        "selle rs ostaju verbatim.\n",
    )

    assert v.check_extract_verbatim([path], tmp_path, kb_root) == []


def test_corrected_ocr_quote_fails_exact_check(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("Kratak citat.", "sellers ostaju verbatim.")
    path = _extract(kb_root, "ocr_corrected.md", text)
    _write(
        tmp_path / "raw" / "book" / "pages" / "page_014.md",
        "selle rs ostaju verbatim.\n",
    )

    findings = v.check_extract_verbatim([path], tmp_path, kb_root)

    assert any(f.code == "F-EXTRACT-VERBATIM" for f in findings)


def test_verbatim_check_canonicalizes_markdown_line_wrapping_only(
    tmp_path: Path,
) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "> Kratak citat.", "> Kratak citat koji je\n> prelomljen drugačije."
    )
    path = _extract(kb_root, "reflowed.md", text)
    _write(
        tmp_path / "raw" / "book" / "pages" / "page_014.md",
        "Kratak citat koji je prelomljen drugačije.\n",
    )

    assert v.check_extract_verbatim([path], tmp_path, kb_root) == []


# --- check_extract_not_full_copy ------------------------------------------------


def test_oversized_extract_warns(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    long_body = VALID_FRONTMATTER + ("reč " * 500)
    path = _extract(kb_root, "book_p014_too_long.md", long_body)

    findings = v.check_extract_not_full_copy([path], kb_root)

    assert any(
        f.severity == "WARN" and f.code == "W-EXTRACT-FULL-COPY" for f in findings
    )


# --- UnicodeDecodeError postaje Finding, ne crash (PR #96 review nalaz) --------


def test_undecodable_extract_becomes_finding_not_crash(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = kb_root / "wiki" / "extracts" / "book_p014_bad_encoding.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00\x01 nije validan utf-8")

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any(
        f.severity == "FAIL" and f.code == "F-EXTRACT-ENCODING" for f in findings
    )


# --- Regresija: check_orphans namerno izostavljen (D7) -------------------------


def test_collect_findings_does_not_include_orphan_noise() -> None:
    """D7 (PR #96 review, mk-pregled-logike-solo): `check_orphans` bi trajno
    FAIL-ovao/WARN-ovao svih ~28 by-event/by-structure stranica jer primaju
    linkove SAMO iz `wiki/index.md` (isključen iz provere), nikad jedna od
    druge. Regresija nad STVARNIM repo stanjem — ako se `check_orphans` ikad
    vrati u kompoziciju bez adaptacije, ovaj test to hvata."""
    kb_root = ROOT / "research" / "expert-analyses"
    findings = v.collect_findings(kb_root, ROOT, skip_git=True)

    assert not any(f.code == "W-ORPHAN" for f in findings)


def _taxonomy_page(source: str, extract_stem: str) -> str:
    return (
        "---\n"
        "title: Test taxonomy\n"
        "description: Test taxonomy pointer.\n"
        "type: topic\n"
        "status: active\n"
        "updated: 2026-09-12\n"
        "sources:\n"
        f"  - path: {source}\n"
        "    note: test\n"
        "---\n\n"
        "## Primeri\n\n"
        f"- [[../extracts/{extract_stem}]]\n"
    )


def test_extensionless_wikilink_satisfies_extract_parity(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_valid.md", VALID_FRONTMATTER)
    _write(
        kb_root / "wiki" / "by-structure" / "accumulation.md",
        _taxonomy_page("raw/book/pages/page_014.md", "book_p014_valid"),
    )

    findings = v.check_extract_parity([path], kb_root)

    assert not any(f.code == "F-EXTRACT-PARITY" for f in findings)


def test_md_wikilink_also_satisfies_extract_parity(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_valid.md", VALID_FRONTMATTER)
    _write(
        kb_root / "wiki" / "by-structure" / "accumulation.md",
        _taxonomy_page("raw/book/pages/page_014.md", "book_p014_valid.md"),
    )

    findings = v.check_extract_parity([path], kb_root)

    assert not any(f.code == "F-EXTRACT-PARITY" for f in findings)


def test_missing_expected_taxonomy_pointer_is_hard_failure(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_valid.md", VALID_FRONTMATTER)

    findings = v.check_extract_parity([path], kb_root)

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-PARITY" for f in findings)


def test_expected_taxonomy_pointer_requires_extract_raw_source(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_valid.md", VALID_FRONTMATTER)
    _write(
        kb_root / "wiki" / "by-structure" / "accumulation.md",
        _taxonomy_page("raw/book/pages/page_999.md", "book_p014_valid"),
    )

    findings = v.check_extract_parity([path], kb_root)

    assert any(
        f.code == "F-EXTRACT-PARITY" and "nema raw source" in f.message
        for f in findings
    )


def test_unrelated_selling_climax_cannot_link_spring_extract(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace("wyckoff_event: none", "wyckoff_event: spring")
    path = _extract(kb_root, "book_p014_spring.md", text)
    for directory, name in (
        ("by-event", "spring"),
        ("by-structure", "accumulation"),
        ("by-event", "selling-climax"),
    ):
        _write(
            kb_root / "wiki" / directory / f"{name}.md",
            _taxonomy_page("raw/book/pages/page_014.md", "book_p014_spring"),
        )

    findings = v.check_extract_parity([path], kb_root)

    assert any(
        f.code == "F-EXTRACT-PARITY"
        and "nepovezani taxonomy" in f.message
        and f.location.endswith("selling-climax.md")
        for f in findings
    )


def test_declared_related_structures_allow_exact_multi_taxonomy_links(
    tmp_path: Path,
) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "structure: accumulation",
        "structure: accumulation\nrelated_structures: distribution,reaccumulation,redistribution",
    )
    path = _extract(kb_root, "book_p014_cycle.md", text)
    for structure in (
        "accumulation",
        "distribution",
        "reaccumulation",
        "redistribution",
    ):
        _write(
            kb_root / "wiki" / "by-structure" / f"{structure}.md",
            _taxonomy_page("raw/book/pages/page_014.md", "book_p014_cycle"),
        )

    frontmatter_findings = v.check_extract_frontmatter([path], kb_root)
    parity_findings = v.check_extract_parity([path], kb_root)

    assert not any(f.code == "F-EXTRACT-FRONTMATTER" for f in frontmatter_findings)
    assert parity_findings == []


# --- Regresija: batches.md parse-validnost (29 batch-eva) ----------------------


def test_real_batches_md_parses_to_29_batches() -> None:
    kb_root = ROOT / "research" / "expert-analyses"
    batches = v.core.parse_batches(kb_root, v.PROFILE)

    assert len(batches) == 29
    assert batches[0].id == "B01"
    assert batches[0].units == ("page_001-page_020",)


def _real_batch_prompts() -> tuple[str, dict[str, str]]:
    text = (ROOT / "research" / "expert-analyses" / "batches.md").read_text(
        encoding="utf-8"
    )
    prompts = {
        f"B{number:02d}": runner.extract_batch_prompt(text, f"B{number:02d}")
        for number in range(1, 30)
    }
    assert all(prompt is not None for prompt in prompts.values())
    return text, {
        batch_id: prompt for batch_id, prompt in prompts.items() if prompt is not None
    }


def test_real_batches_have_one_runner_extractable_prompt_each() -> None:
    text, prompts = _real_batch_prompts()
    prompt_area = text.split("## Copy/paste promptovi", 1)[1]

    assert "TODO — nije popunjen prompt" not in prompt_area
    assert list(prompts) == [f"B{number:02d}" for number in range(1, 30)]
    for batch_id, prompt in prompts.items():
        section_match = re.search(
            rf"^### {batch_id}\s*$\n(?P<body>.*?)(?=^### B\d|\Z)",
            prompt_area,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert section_match is not None, f"nedostaje prompt sekcija za {batch_id}"
        body = section_match.group("body")
        assert len(re.findall(r"^```text$", body, flags=re.MULTILINE)) == 1
        assert len(re.findall(r"^```$", body, flags=re.MULTILINE)) == 1
        assert prompt.startswith("Expert-analyses ")
        assert len(prompt.split()) >= 220, (
            f"{batch_id} prompt je verovatno skraćen ili malformed"
        )


def test_batch_prompts_preserve_exact_source_scopes() -> None:
    _, prompts = _real_batch_prompts()

    book_scopes = {
        f"B{number:02d}": ((number - 1) * 20 + 1, 248 if number == 13 else number * 20)
        for number in range(2, 14)
    }
    for batch_id, (start, end) in book_scopes.items():
        scope = (
            f"raw/book/pages/page_{start:03d}.md do raw/book/pages/page_{end:03d}.md"
        )
        assert scope in prompts[batch_id]
        assert "raw/book/image_manifest.json" in prompts[batch_id]
        assert "page_range" in prompts[batch_id]
        assert "page_range N+1 dozvoljava samo nastavak citata" in prompts[batch_id]
        assert "Speed dijagrama odbaci" in prompts[batch_id]
        assert "raw/crypto_archive/" not in prompts[batch_id]
        assert "raw/bruce_fraser/" not in prompts[batch_id]

    crypto_scopes = {"B14": (1, 16), "B15": (17, 31), "B16": (32, 46)}
    for batch_id, (start, end) in crypto_scopes.items():
        prompt = prompts[batch_id]
        assert f"pozicija {start}–{end}" in prompt
        assert "raw/crypto_archive/manifest.json" in prompt
        assert "raw/crypto_archive/posts/<slug>.md" in prompt
        assert "manifest redosled, a ne leksikografski" in prompt
        assert "raw/book/pages/" not in prompt
        assert "raw/bruce_fraser/" not in prompt

    for number in range(17, 30):
        batch_id = f"B{number:02d}"
        series = number - 16
        start = (series - 1) * 20 + 1
        end = 243 if number == 29 else series * 20
        prompt = prompts[batch_id]
        assert f"pozicija {start}–{end}" in prompt
        assert "raw/bruce_fraser/posts/*.md" in prompt
        assert "LC_ALL=C leksikografski red" in prompt
        assert "raw/bruce_fraser/images-manifest.json" in prompt
        assert "bez slike nije validan expert extract" in prompt
        assert "odnosno bez slike" not in prompt
        assert "raw/book/pages/" not in prompt
        assert "raw/crypto_archive/" not in prompt


def test_batch_prompts_keep_execution_contract_and_safe_prefix() -> None:
    _, prompts = _real_batch_prompts()
    required_fragments = (
        "research/expert-analyses/EXTRACT_TEMPLATE.md",
        "research/expert-analyses/_progress.md",
        "ceo research/expert-analyses/wiki/index.md",
        "poslednjih 50 linija research/expert-analyses/wiki/log.md",
        'sekciju "## Disciplina citiranja"',
        "research/expert-analyses/wiki/extracts/",
        "status: candidate",
        "wiki/by-event/*.md",
        "wiki/by-structure/*.md",
        'pod "## Primeri"',
        "corpus-count",
        "last_reviewed",
        "runner sme da proglasi batch complete",
        "bez delimičnog sadržajnog upisa",
        "poslednja 2-3 nova extract-a",
        "source locator, doslovni citat i image_path",
        "comma-separated related_events i/ili related_structures",
        "NE pozivaj ingest runner",
        "NE pokreći nijednu `git` ni `gh` komandu",
        "`git commit`",
        "`git branch`",
        "`git push`",
        "GitHub/PR pozive",
        "NE piši u research/expert-analyses/batches.md",
        "menja isključivo runner",
    )

    assert "Sentineli bez fabriciranja" in (
        ROOT / "research/expert-analyses/batches.md"
    ).read_text(encoding="utf-8")

    for batch_id, prompt in prompts.items():
        assert not re.match(r"^\$[\w-]+(?:\s|$)", prompt), batch_id
        if batch_id == "B01":
            continue  # B01 je istorijski, već izvršen i zadržan verbatim.
        assert "stani posle poslednjeg potpuno obrađenog" not in prompt
        for fragment in required_fragments:
            assert fragment in prompt, f"{batch_id} nema ugovorni fragment: {fragment}"

    for batch_id in ("B13", "B16", "B29"):
        assert "semantic-lint kapiju" in prompts[batch_id]


def test_crypto_and_fraser_prompts_preserve_image_and_resume_rules() -> None:
    _, prompts = _real_batch_prompts()

    for batch_id in ("B14", "B15", "B16"):
        prompt = prompts[batch_id]
        assert "status: paywalled" in prompt
        assert "research/expert-analyses/_gaps.md" in prompt
        assert "u ledgeru uvećaj reviewed i paywalled" in prompt
        assert "pripadajućom susednom Markdown slikom" in prompt
        assert "raw/crypto_archive/images/<report>/<file>" in prompt
        assert "post_url: doslovni URL iz headera posta" in prompt

    for batch_id in (f"B{number:02d}" for number in range(17, 30)):
        prompt = prompts[batch_id]
        assert "pripadajućom susednom Markdown slikom" in prompt
        assert "raw/bruce_fraser/images/<file>" in prompt
        assert "(remote: <url>) samo ako" in prompt
        assert "post_url: doslovni URL iz headera posta" in prompt


def test_future_fraser_prompts_require_visible_metadata_and_supported_taxonomy() -> None:
    _, prompts = _real_batch_prompts()
    hardening_fragments = (
        "`asset` i `timeframe` čitaj sa same slike samo kada su jasno vidljivi",
        "ako nisu proverljivi iz posta ili slike, koristi `unknown` i nikada ne nagađaj",
        "`wyckoff_event` mora biti eksplicitno podržan Fraserovim pasusom ili nedvosmislenim chart labelom",
        "`phase` postavi na A–E samo uz isti nivo podrške, inače koristi `unknown`",
        "Concept-only chart bez prirodnog mapiranja na dozvoljenu postojeću event/structure taksonomiju odbaci",
    )

    assert "Fraser metadata/taksonomija hardening" not in prompts["B17"]
    for batch_id in (f"B{number:02d}" for number in range(18, 30)):
        for fragment in hardening_fragments:
            assert fragment in prompts[batch_id], (
                f"{batch_id} nema Fraser hardening ugovorni fragment: {fragment}"
            )


def _assert_only_expected_blocked_gate_coupling(findings: list) -> None:
    """Prihvati čisto stanje ili jedini dokazivi blocked/status coupling."""
    kb_root = ROOT / "research" / "expert-analyses"
    fails = [finding for finding in findings if finding.severity == "FAIL"]
    blocked = [
        batch
        for batch in v.core.parse_batches(kb_root, v.PROFILE)
        if batch.status == "blocked"
    ]
    batches_text = (kb_root / "batches.md").read_text(encoding="utf-8")
    blocked_row = (
        next(
            (
                line
                for line in batches_text.splitlines()
                if blocked and line.startswith(f"| {blocked[0].id} |")
            ),
            "",
        )
        if blocked
        else ""
    )
    retryable = len(blocked) == 1 and (
        blocked[0].id in {"B13", "B16", "B29"}
        or re.search(r"\bvalidator\s+FAIL=1\s+WARN=0\b", blocked_row, re.I)
    )
    if retryable:
        assert len(fails) == 1
        assert fails[0].code == "F-BATCH-SCOPE-INCOMPLETE"
        assert fails[0].location == "_progress.md"
    else:
        assert fails == []


def test_real_kb_root_validates_or_is_ready_for_gate_retry() -> None:
    kb_root = ROOT / "research" / "expert-analyses"
    findings = v.collect_findings(kb_root, ROOT, skip_git=True)

    _assert_only_expected_blocked_gate_coupling(findings)


def test_real_kb_root_validates_or_is_ready_for_gate_retry_with_git_check() -> None:
    """Produkcioni put (skip_git=False) — zatečena svita ga NIKAD nije izvršavala (Faza 2
    lekcija: git-check grana ostaje netestirana bez ovog testa). Sveže klonirani worktree ima
    čist raw/, pa se očekuje isti rezultat kao skip_git=True."""
    kb_root = ROOT / "research" / "expert-analyses"
    findings = v.collect_findings(kb_root, ROOT, skip_git=False)

    _assert_only_expected_blocked_gate_coupling(findings)


# --- RAW_UNIT_RE (D6) — regresija za sva tri raw podstabla ----------------------


@pytest.mark.parametrize(
    ("raw_path", "expected_stem"),
    [
        ("raw/book/pages/page_001.md", "page_001"),
        (
            "raw/crypto_archive/posts/wyckoff-crypto-report-53.md",
            "wyckoff-crypto-report-53",
        ),
        ("raw/bruce_fraser/posts/some-fraser-article.md", "some-fraser-article"),
    ],
)
def test_raw_unit_re_matches_all_three_subtrees(
    raw_path: str, expected_stem: str
) -> None:
    m = v.RAW_UNIT_RE.search(raw_path)

    assert m is not None
    assert m.group(1) == expected_stem


def test_raw_unit_re_has_exactly_one_capture_group() -> None:
    # core.unit_identity radi m.group(1) bez provere broja grupa (D6 gotcha).
    assert v.RAW_UNIT_RE.groups == 1


# --- PROFILE runner-consumed ugovor (#218/#220) --------------------------------


def test_profile_is_corpus_profile_instance() -> None:
    assert isinstance(v.PROFILE, v.core.CorpusProfile)
    assert v.PROFILE.page_dirs == ("by-event", "by-structure")


def _batch(batch_id: str, status: str) -> v.Batch:
    return v.Batch(batch_id, (), status, None, "", "")


def _progress(kb_root: Path, *, book_reviewed: int, book_last: str) -> None:
    _write(
        kb_root / "_progress.md",
        "| source | total_files | reviewed | valid | rejected | paywalled | last_reviewed |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |\n"
        f"| book | 248 | {book_reviewed} | 2 | 18 | 0 | {book_last} |\n"
        "| crypto | 46 | 0 | 0 | 0 | 0 | — |\n"
        "| fraser | 243 | 0 | 0 | 0 | 0 | — |\n",
    )


def test_completed_batch_requires_ledger_at_canonical_boundary(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    _progress(kb_root, book_reviewed=20, book_last="raw/book/pages/page_020.md")

    findings = v.check_batch_scope_completion(
        kb_root, tmp_path, [_batch("B02", "complete")]
    )

    assert any(f.code == "F-BATCH-SCOPE-INCOMPLETE" for f in findings)


def test_pending_batch_rejects_early_stop_inside_fixed_scope(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    _progress(kb_root, book_reviewed=25, book_last="raw/book/pages/page_025.md")

    findings = v.check_batch_scope_completion(
        kb_root, tmp_path, [_batch("B02", "pending")]
    )

    assert any(f.code == "F-BATCH-SCOPE-INCOMPLETE" for f in findings)


def test_pending_batch_rejects_scope_overshoot(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    _progress(kb_root, book_reviewed=41, book_last="raw/book/pages/page_041.md")

    findings = v.check_batch_scope_completion(
        kb_root, tmp_path, [_batch("B01", "complete"), _batch("B02", "pending")]
    )

    assert any(f.code == "F-BATCH-SCOPE-INCOMPLETE" for f in findings)


def test_batch_scope_rejects_reviewed_locator_mismatch(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    _progress(kb_root, book_reviewed=40, book_last="raw/book/pages/page_039.md")

    findings = v.check_batch_scope_completion(
        kb_root, tmp_path, [_batch("B01", "complete"), _batch("B02", "pending")]
    )

    assert any(f.code == "F-BATCH-SCOPE-INCOMPLETE" for f in findings)


def test_pending_batch_accepts_previous_or_completed_boundary(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    for reviewed in (20, 40):
        _progress(
            kb_root,
            book_reviewed=reviewed,
            book_last=f"raw/book/pages/page_{reviewed:03d}.md",
        )
        assert (
            v.check_batch_scope_completion(
                kb_root,
                tmp_path,
                [_batch("B01", "complete"), _batch("B02", "pending")],
            )
            == []
        )


def test_batch_scope_rejects_out_of_order_complete_source(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    crypto_last = v._ordered_source_paths(ROOT, "crypto")[15]
    _write(
        kb_root / "_progress.md",
        "| source | total_files | reviewed | valid | rejected | paywalled | last_reviewed |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |\n"
        "| book | 248 | 20 | 2 | 18 | 0 | raw/book/pages/page_020.md |\n"
        f"| crypto | 46 | 16 | 1 | 15 | 0 | {crypto_last} |\n"
        "| fraser | 243 | 0 | 0 | 0 | 0 | — |\n",
    )

    findings = v.check_batch_scope_completion(
        kb_root,
        ROOT,
        [
            _batch("B01", "complete"),
            _batch("B02", "pending"),
            _batch("B14", "complete"),
        ],
    )

    assert any(f.code == "F-BATCH-ORDER" and "B14" in f.message for f in findings)


@pytest.mark.parametrize("batch_id", ["B13", "B16", "B29"])
def test_profile_uses_domain_specific_model_agnostic_gate_prompt(batch_id: str) -> None:
    prompt = runner.build_gate_prompt(
        batch_id,
        "semantic-lint (završni book batch)",
        ROOT / "research/expert-analyses",
        v.PROFILE,
    )

    assert "Expert-analyses semantic-lint" in prompt
    assert "issues-KB" in prompt
    assert "xhigh" not in prompt.lower()
    assert "astra" not in prompt.lower()
    assert "wiki/questions" not in prompt
    assert "GATE_OUTCOME: PASS" in prompt
    assert "GATE_OUTCOME: FAIL" in prompt
    assert "Poslednji neprazan red" in prompt


# --- kb_ingest.py: _load_profile end-to-end + sys.modules redosled lock-down --


def test_kb_ingest_load_profile_returns_real_profile() -> None:
    """End-to-end: `kb_ingest._load_profile` (dinamički loader, `sys.modules`
    gotcha) mora uspešno učitati PRAVI `scripts/validate_expert_analyses.py` i
    vratiti njegov `PROFILE` — isti kod-put koji `_snapshot_batch_statuses`
    koristi u produkciji."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    profile = kb_ingest._load_profile(ROOT / "scripts" / "validate_expert_analyses.py")

    assert isinstance(profile, v.core.CorpusProfile)
    assert profile.name == "expert-analyses"


def test_load_profile_registers_sys_modules_before_exec() -> None:
    """Lock-down (PR #96 review nalaz — poznata klasa gotcha-e, identična
    komentarisana u poligon `ingest_runner.py`): `sys.modules[spec.name] =
    module` MORA stajati PRE `spec.loader.exec_module(module)` u izvornom kodu
    `kb_ingest._load_profile`, inače dataclass anotacije (`CorpusProfile`
    frozen dataclass) ne mogu da se razreše preko `sys.modules[cls.__module__]`
    i budući refaktor koji zameni redosled linija tiho pada. Provera na nivou
    izvornog koda (ne runtime-reprodukcija) jer je runtime efekat osetljiv na
    Python verziju/dataclass internals — pozicija linija je stabilan signal."""
    source = (ROOT / "scripts" / "kb_ingest.py").read_text(encoding="utf-8")
    func_start = source.index("def _load_validator_module(")
    func_body = source[func_start : source.index("\ndef ", func_start + 1)]

    register_pos = func_body.index("sys.modules[spec.name] = module")
    exec_pos = func_body.index("spec.loader.exec_module(module)")

    assert register_pos < exec_pos, (
        "sys.modules[spec.name] = module mora biti PRE exec_module — "
        "vidi ingest_runner.py:_load_profile_from_validator_script gotcha"
    )


def test_kb_ingest_no_pr_is_wrapper_only_flag() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    args, passthrough = kb_ingest.parse_args(
        ["--kb", "expert-analyses", "--no-pr", "--", "--max-batches", "1"]
    )

    assert args.no_pr is True
    assert passthrough == ["--", "--max-batches", "1"]


def test_safe_codex_launcher_injects_least_write_capabilities() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import codex_ingest_safe

    command = codex_ingest_safe.build_safe_argv(
        "/usr/local/bin/codex",
        [
            "exec",
            "--json",
            "--model",
            "gpt-5.6-sol",
            "--sandbox",
            "workspace-write",
            "prompt",
        ],
    )

    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert 'web_search="disabled"' in command
    assert "sandbox_workspace_write.network_access=false" in command
    assert 'model_reasoning_effort="medium"' in command
    assert command.count('model_reasoning_effort="medium"') == 1
    assert command.count("--disable") == 3
    assert "browser_use" in command
    assert "apps" in command
    assert "plugins" in command
    assert command[-6:] == [
        "--json",
        "--model",
        "gpt-5.6-sol",
        "--sandbox",
        "workspace-write",
        "prompt",
    ]


@pytest.mark.parametrize(
    "supplied",
    [
        [
            "exec",
            "--model",
            "gpt-5.6-sol",
            "-c",
            'model_reasoning_effort="high"',
            "prompt",
        ],
        [
            "exec",
            "--model",
            "gpt-5.6-sol",
            '--config=model_reasoning_effort="low"',
            "prompt",
        ],
    ],
)
def test_safe_codex_launcher_rejects_reasoning_override(supplied: list[str]) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import codex_ingest_safe

    with pytest.raises(ValueError, match="reasoning"):
        codex_ingest_safe.build_safe_argv("/usr/local/bin/codex", supplied)


def test_wrapper_forces_safe_codex_launcher_and_workspace_sandbox() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    hardened = kb_ingest._harden_codex_passthrough(
        ["--backend", "codex", "--model", "gpt-5.6-sol"], ROOT
    )

    assert hardened[-4:-2] == [
        "--codex-bin",
        str((ROOT / "scripts" / "codex_ingest_safe.py").resolve()),
    ]
    assert hardened[-2:] == ["--codex-sandbox", "workspace-write"]


@pytest.mark.parametrize(
    "unsafe",
    [
        [
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--codex-sandbox",
            "danger-full-access",
        ],
        [
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--codex-bin",
            "/tmp/custom-codex",
        ],
        [
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--codex-profile",
            "unsafe",
        ],
        ["--backend", "codex"],
        ["--backend", "codex", "--model", "gpt-6-astra"],
        [
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--model",
            "gpt-6-astra",
        ],
    ],
)
def test_wrapper_rejects_codex_capability_overrides(unsafe: list[str]) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    with pytest.raises(ValueError):
        kb_ingest._harden_codex_passthrough(unsafe, ROOT)


def test_git_control_snapshot_allows_content_edits_but_detects_git_mutations(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init")
    _write(repo / "wiki.md", "initial\n")
    git("add", "wiki.md")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "initial",
    )
    baseline = kb_ingest._git_control_state(repo)

    _write(repo / "wiki.md", "workspace content edit\n")
    assert kb_ingest._git_control_state(repo) == baseline

    git("add", "wiki.md")
    staged = kb_ingest._git_control_state(repo)
    assert staged.index_entries != baseline.index_entries

    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "agent commit",
    )
    committed = kb_ingest._git_control_state(repo)
    assert committed.head_oid != baseline.head_oid
    assert committed.refs != baseline.refs

    git("switch", "-c", "agent-branch")
    switched = kb_ingest._git_control_state(repo)
    assert switched.symbolic_head != committed.symbolic_head


def test_wrapper_fails_before_post_processing_when_agent_changes_git_control_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    before = kb_ingest.GitControlState(
        b"refs/heads/main\n", b"a\n", b"refs-a", b"index"
    )
    after = kb_ingest.GitControlState(
        b"refs/heads/agent\n", b"b\n", b"refs-b", b"index"
    )
    states = iter((before, after))
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(kb_ingest, "_current_branch", lambda _cwd: "main")
    monkeypatch.setattr(kb_ingest, "_git_control_state", lambda _cwd: next(states))
    monkeypatch.setattr(
        kb_ingest,
        "_snapshot_batch_statuses",
        lambda *_args: {"B01": "complete", "B02": "pending"},
    )
    monkeypatch.setattr(
        kb_ingest,
        "_snapshot_coverage",
        lambda *_args: {"book": {}, "crypto": {}, "fraser": {}},
    )
    monkeypatch.setattr(kb_ingest, "_snapshot_extracts", lambda *_args: set())
    monkeypatch.setattr(kb_ingest, "_run", lambda *_args: 0)

    rc = kb_ingest.main(
        [
            "--kb",
            "expert-analyses",
            "--no-pr",
            "--",
            "--max-batches",
            "1",
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--skip-git",
        ]
    )

    assert rc == 1


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--max-batches", "1"], [1]),
        (["--skip-git", "--max-batches=1"], [1]),
        (["--skip-git"], []),
        (["--max-batches", "1", "--max-batches", "2"], [1, 2]),
    ],
)
def test_real_ingest_batch_limit_parser(args: list[str], expected: list[int]) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    assert kb_ingest._max_batches_values(args) == expected


def test_real_ingest_rejects_duplicate_max_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    monkeypatch.chdir(ROOT)
    rc = kb_ingest.main(
        [
            "--kb",
            "expert-analyses",
            "--no-pr",
            "--",
            "--max-batches",
            "1",
            "--max-batches",
            "2",
        ]
    )

    assert rc == 2


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("Sve provere su čiste.\nGATE_OUTCOME: PASS\n", "PASS"),
        ("Nađen je problem.\nGATE_OUTCOME: FAIL\n", "FAIL"),
        ("Nađen je problem: FAIL", None),
        ("GATE_OUTCOME: PASS\nGATE_OUTCOME: FAIL\n", None),
        (
            '{"type":"result","result":"čisto\\nGATE_OUTCOME: PASS"}',
            "PASS",
        ),
        (
            '{"type":"thread.started"}\n'
            '{"type":"item.completed","item":{"type":"agent_message",'
            '"text":"nalaz\\nGATE_OUTCOME: FAIL"}}\n',
            "FAIL",
        ),
    ],
)
def test_gate_content_outcome_contract(stdout: str, expected: str | None) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    assert kb_ingest._gate_content_outcome(stdout) == expected


@pytest.mark.parametrize(
    ("stdout", "should_fail"),
    [
        ("Izveštaj je čist.\nGATE_OUTCOME: PASS\n", False),
        ("Nalaz.\nGATE_OUTCOME: FAIL\n", True),
        ("Nalaz bez ugovornog markera.", True),
        ("GATE_OUTCOME: PASS\nGATE_OUTCOME: FAIL\n", True),
    ],
)
def test_required_gate_uses_content_not_only_zero_rc(
    tmp_path: Path, stdout: str, should_fail: bool
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _write(
        kb_root / "batches.md",
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B13 | page_241-page_248 | semantic-lint | complete | 2026-01-01 | 1 | nema | ok |\n",
    )
    _write(
        kb_root / "run-log.md",
        "| B13 | gate | codex | sol | 0 | 0 | 0 | 0 | 0 | 0 |\n",
    )
    _write(kb_root / "logs" / "B13-gate-codex.json", stdout)

    failed = kb_ingest._failed_required_gates(
        kb_root, {"B13": ("pending", "complete")}, ""
    )

    assert ("B13" in failed) is should_fail


def test_post_validator_failure_reverts_new_complete_status_to_blocked(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches = (
        "| Batch | Jedinice | Status | Wiki stranice | Preostali izvori | Datum | Log |\n"
        "| --- | --- | --- | ---: | --- | --- | --- |\n"
        "| B02 | page_021-page_040 | complete | 1 | nema | 2026-09-12 | ok |\n"
    )
    _write(kb_root / "batches.md", batches)
    validator = tmp_path / "validator.py"
    _write(
        validator,
        "from scripts.validate_expert_analyses import PROFILE\n",
    )

    kb_ingest._mark_completed_transitions_blocked(
        kb_root,
        validator,
        {"B02": ("pending", "complete")},
        reason="post-validator FAIL=1",
    )

    updated = (kb_root / "batches.md").read_text(encoding="utf-8")
    assert "| B02 | page_021-page_040 | blocked |" in updated
    assert "post-validator FAIL=1" in updated


def _write_progress_adapter(batches_path: Path, batch_id: str, **values) -> None:
    text = batches_path.read_text(encoding="utf-8")
    batches_path.write_text(
        runner.render_batch_progress_update(text, batch_id, **values), encoding="utf-8"
    )


def test_fake_agent_all_rejected_batch_uses_safe_zero_page_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _progress(kb_root, book_reviewed=20, book_last="raw/book/pages/page_020.md")
    batches_path = kb_root / "batches.md"
    _write(
        batches_path,
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B01 | page_001-page_020 | standardna | complete | 2026-01-01 | 2 | nema | ok |\n"
        "| B02 | page_021-page_040 | standardna | pending | | | nema | |\n\n"
        "### B02\n\n```text\nObradi B02.\n```\n",
    )
    _write(kb_root / "wiki" / "log.md", "# Log\n")

    class AllRejectedAgent:
        def execute(self, _prompt: str, *, timeout: int):
            del timeout
            _progress(
                kb_root,
                book_reviewed=40,
                book_last="raw/book/pages/page_040.md",
            )
            progress = (kb_root / "_progress.md").read_text(encoding="utf-8")
            (kb_root / "_progress.md").write_text(
                progress.replace("| 2 | 18 | 0 |", "| 2 | 38 | 0 |"),
                encoding="utf-8",
            )
            return runner.AgentResult(0, "", "")

    pre_statuses = {"B01": "complete", "B02": "pending"}
    pre_coverage = v.read_progress_ledger(kb_root)
    pre_extracts: set[str] = set()
    rc = runner.run_full_mode(
        kb_root,
        batches_path,
        batches_path,
        kb_root / "wiki" / "log.md",
        v.PROFILE,
        max_batches=1,
        skip_git=True,
        timeout=1,
        agent=AllRejectedAgent(),
        validator_gate=lambda *_: (0, {"summary": {"fail": 0, "warn": 0}}),
        write_progress=_write_progress_adapter,
        append_log=lambda *_: None,
        save_stdout=lambda *_: None,
        append_run_log=lambda *args, **kwargs: None,
        autofix=lambda *_: False,
    )

    assert rc == 1
    assert (
        "| B02 | page_021-page_040 | standardna | blocked |"
        in batches_path.read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        kb_ingest,
        "_post_validate",
        lambda *args, **kwargs: (0, {"summary": {"fail": 0, "warn": 0}}),
    )
    recovered = kb_ingest._recover_verified_zero_page_completion(
        cwd=tmp_path,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        pre_statuses=pre_statuses,
        post_statuses={"B01": "complete", "B02": "blocked"},
        pre_coverage=pre_coverage,
        post_coverage=v.read_progress_ledger(kb_root),
        pre_extracts=pre_extracts,
        post_extracts=set(),
        skip_git=True,
    )

    assert recovered is True
    assert (
        "| B02 | page_021-page_040 | standardna | complete |"
        in batches_path.read_text(encoding="utf-8")
    )


def test_zero_page_recovery_rejects_other_batch_and_source_progress(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _write(
        kb_root / "batches.md",
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B01 | page_001-page_020 | standardna | complete | 2026-01-01 | 2 | nema | ok |\n"
        "| B02 | page_021-page_040 | standardna | blocked | 2026-01-01 | 0 | svi | pages_delta=0 |\n"
        "| B14 | crypto 1-16 | standardna | complete | 2026-01-01 | 1 | nema | lažni napredak |\n",
    )
    pre_coverage = {
        "book": {
            "total": 248,
            "reviewed": 20,
            "valid": 2,
            "rejected": 18,
            "paywalled": 0,
            "last_reviewed": "raw/book/pages/page_020.md",
        },
        "crypto": {
            "total": 46,
            "reviewed": 0,
            "valid": 0,
            "rejected": 0,
            "paywalled": 0,
            "last_reviewed": "—",
        },
        "fraser": {
            "total": 243,
            "reviewed": 0,
            "valid": 0,
            "rejected": 0,
            "paywalled": 0,
            "last_reviewed": "—",
        },
    }
    post_coverage = {
        **pre_coverage,
        "book": {
            **pre_coverage["book"],
            "reviewed": 40,
            "rejected": 38,
            "last_reviewed": "raw/book/pages/page_040.md",
        },
        "crypto": {
            **pre_coverage["crypto"],
            "reviewed": 16,
            "valid": 1,
            "rejected": 15,
            "last_reviewed": v._ordered_source_paths(ROOT, "crypto")[15],
        },
    }

    recovered = kb_ingest._recover_verified_zero_page_completion(
        cwd=ROOT,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        pre_statuses={"B01": "complete", "B02": "pending", "B14": "pending"},
        post_statuses={"B01": "complete", "B02": "blocked", "B14": "complete"},
        pre_coverage=pre_coverage,
        post_coverage=post_coverage,
        pre_extracts=set(),
        post_extracts=set(),
        skip_git=True,
    )

    assert recovered is False
    assert "| B02 | page_021-page_040 | standardna | blocked |" in (
        kb_root / "batches.md"
    ).read_text(encoding="utf-8")


def test_fake_gate_rc_one_is_detected_and_blocks_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches_path = kb_root / "batches.md"
    _write(
        batches_path,
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B13 | page_241-page_248 | semantic-lint | pending | | | nema | |\n\n"
        "### B13\n\n```text\nObradi B13.\n```\n",
    )
    _write(kb_root / "wiki" / "log.md", "# Log\n")
    run_log = kb_root / "run-log.md"

    class GateFailAgent:
        calls = 0

        def execute(self, _prompt: str, *, timeout: int):
            del timeout
            self.calls += 1
            if self.calls == 1:
                _write(kb_root / "wiki" / "by-event" / "spring.md", "ingest change")
                return runner.AgentResult(0, "", "")
            return runner.AgentResult(1, "gate fail", "")

    def append_run_log(
        _kb_root: Path, *, batch_id: str, kind: str, result, **_kwargs
    ) -> None:
        with run_log.open("a", encoding="utf-8") as handle:
            handle.write(
                f"| {batch_id} | {kind} | codex | sol | 0 | 0 | 0 | 0 | 0 | {result.returncode} |\n"
            )

    monkeypatch.setattr(runner, "RETRY_BACKOFF_SECONDS", 0)
    rc = runner.run_full_mode(
        kb_root,
        batches_path,
        batches_path,
        kb_root / "wiki" / "log.md",
        v.PROFILE,
        max_batches=1,
        skip_git=True,
        timeout=1,
        agent=GateFailAgent(),
        validator_gate=lambda *_: (0, {"summary": {"fail": 0, "warn": 0}}),
        write_progress=_write_progress_adapter,
        append_log=lambda *_: None,
        save_stdout=lambda *_: None,
        append_run_log=append_run_log,
        autofix=lambda *_: False,
    )

    assert rc == 0  # zatečeno Spona ponašanje koje wrapper mora pooštriti
    changed = {"B13": ("pending", "complete")}
    failed = kb_ingest._failed_required_gates(kb_root, changed, "")
    assert failed == {"B13"}
    kb_ingest._mark_completed_transitions_blocked(
        kb_root,
        ROOT / "scripts" / "validate_expert_analyses.py",
        changed,
        reason="gate rc=1",
    )
    assert (
        "| B13 | page_241-page_248 | semantic-lint | blocked |"
        in batches_path.read_text(encoding="utf-8")
    )


def _blocked_gate_retry_fixture(kb_root: Path, batch_id: str = "B13") -> Path:
    batches_path = kb_root / "batches.md"
    _write(
        batches_path,
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        f"| {batch_id} | page_241-page_248 | semantic-lint | blocked | 2026-01-01 | 7 | nema | gate fail |\n",
    )
    return batches_path


def test_retry_gate_cli_dispatches_without_content_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    captured: dict = {}
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(kb_ingest, "_current_branch", lambda _cwd: "main")
    monkeypatch.setattr(
        kb_ingest,
        "_run",
        lambda *_args: pytest.fail("content spona-ingest runner ne sme biti pozvan"),
    )

    def fake_retry(**kwargs) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(kb_ingest, "_run_required_gate_retry", fake_retry)

    rc = kb_ingest.main(
        [
            "--kb",
            "expert-analyses",
            "--retry-gate",
            "B13",
            "--no-pr",
            "--",
            "--backend",
            "codex",
            "--model",
            "gpt-5.6-sol",
            "--skip-git",
            "--timeout",
            "17",
        ]
    )

    assert rc == 0
    assert captured["batch_id"] == "B13"
    assert captured["skip_git"] is True
    assert captured["timeout"] == 17


@pytest.mark.parametrize(
    ("stdout", "expected_rc", "expected_status"),
    [
        ("Nalazi su čisti.\nGATE_OUTCOME: PASS\n", 0, "complete"),
        ("Postoji nalaz.\nGATE_OUTCOME: FAIL\n", 1, "blocked"),
        ("Nedostaje marker.\n", 1, "blocked"),
    ],
)
def test_gate_only_retry_fake_outcomes_do_not_rerun_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    expected_rc: int,
    expected_status: str,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches_path = _blocked_gate_retry_fixture(kb_root)
    state = kb_ingest.GitControlState(b"head", b"oid", b"refs", b"index")
    coverage = {"book": {}, "crypto": {}, "fraser": {}}
    invoke_calls: list[str] = []
    monkeypatch.setattr(
        kb_ingest,
        "_required_gate_retry_preflight",
        lambda **_kwargs: kb_ingest.RetryGateContext(
            batch_id="B13", prompt="DOMAIN GATE PROMPT", pages=7
        ),
    )
    monkeypatch.setattr(kb_ingest, "_git_control_state", lambda _cwd: state)
    monkeypatch.setattr(
        kb_ingest,
        "_snapshot_batch_statuses",
        lambda *_args: {
            "B13": "complete"
            if "| B13 | page_241-page_248 | semantic-lint | complete |"
            in batches_path.read_text(encoding="utf-8")
            else "blocked"
        },
    )
    monkeypatch.setattr(kb_ingest, "_snapshot_coverage", lambda *_args: coverage)
    monkeypatch.setattr(kb_ingest, "_snapshot_extracts", lambda *_args: {"existing.md"})

    def fake_invoke(*, cwd: Path, prompt: str, timeout: int):
        del cwd, timeout
        invoke_calls.append(prompt)
        return runner.AgentResult(0, stdout, "")

    monkeypatch.setattr(kb_ingest, "_invoke_safe_retry_gate", fake_invoke)
    monkeypatch.setattr(
        kb_ingest,
        "_post_validate",
        lambda *_args, **_kwargs: (0, {"summary": {"fail": 0, "warn": 0}}),
    )

    rc = kb_ingest._run_required_gate_retry(
        cwd=ROOT,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        batch_id="B13",
        skip_git=True,
        timeout=1,
    )

    assert rc == expected_rc
    assert invoke_calls == ["DOMAIN GATE PROMPT"]
    assert f"| B13 | page_241-page_248 | semantic-lint | {expected_status} |" in (
        batches_path.read_text(encoding="utf-8")
    )
    assert "| B13 | gate-retry-" in (kb_root / "run-log.md").read_text(encoding="utf-8")
    artifacts = list((kb_root / "logs").glob("B13-gate-retry-*-codex.json"))
    assert len(artifacts) == 1
    assert artifacts[0].read_text(encoding="utf-8") == stdout


def test_gate_retry_preflight_rejects_non_semantic_batch(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _write(
        kb_root / "batches.md",
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B12 | page_221-page_240 | standardna | blocked | 2026-01-01 | 7 | nema | fail |\n",
    )

    with pytest.raises(RuntimeError, match="semantic-lint"):
        kb_ingest._required_gate_retry_preflight(
            cwd=ROOT,
            kb_root=kb_root,
            validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
            batch_id="B12",
            skip_git=True,
        )


def test_gate_retry_preflight_rejects_later_batch_progress(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _write(
        kb_root / "batches.md",
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |\n"
        "| --- | --- | --- | --- | --- | ---: | --- | --- |\n"
        "| B13 | page_241-page_248 | semantic-lint | blocked | 2026-01-01 | 7 | nema | gate fail |\n"
        "| B14 | crypto 1-16 | standardna | complete | 2026-01-01 | 2 | nema | out of order |\n",
    )

    with pytest.raises(RuntimeError, match="kasniji batch/source"):
        kb_ingest._required_gate_retry_preflight(
            cwd=ROOT,
            kb_root=kb_root,
            validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
            batch_id="B13",
            skip_git=True,
        )


def test_gate_retry_preflight_accepts_only_exact_blocked_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    rows = [
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for number in range(1, 30):
        batch_id = f"B{number:02d}"
        status = (
            "complete" if number < 13 else ("blocked" if number == 13 else "pending")
        )
        gate = "semantic-lint" if number in {13, 16, 29} else "standardna"
        rows.append(
            f"| {batch_id} | scope | {gate} | {status} | 2026-01-01 | 7 | nema | test |"
        )
    _write(kb_root / "batches.md", "\n".join(rows) + "\n")
    _write(
        kb_root / "_progress.md",
        "| source | total_files | reviewed | valid | rejected | paywalled | last_reviewed |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |\n"
        "| book | 248 | 248 | 2 | 246 | 0 | raw/book/pages/page_248.md |\n"
        "| crypto | 46 | 0 | 0 | 0 | 0 | — |\n"
        "| fraser | 243 | 0 | 0 | 0 | 0 | — |\n",
    )
    monkeypatch.setattr(
        kb_ingest,
        "_post_validate",
        lambda *_args, **_kwargs: (
            1,
            {
                "summary": {"fail": 1, "warn": 0},
                "findings": [
                    {
                        "code": "F-BATCH-SCOPE-INCOMPLETE",
                        "location": "_progress.md",
                        "message": "book blocked status coupling",
                    }
                ],
            },
        ),
    )

    context = kb_ingest._required_gate_retry_preflight(
        cwd=ROOT,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        batch_id="B13",
        skip_git=True,
    )

    assert context.batch_id == "B13"
    assert context.pages == 7
    assert "Expert-analyses semantic-lint" in context.prompt


def _blocked_standard_recovery_fixture(
    kb_root: Path,
    *,
    crypto_reviewed: int = 31,
    later_status: str = "pending",
    target_log: str = "validator FAIL=1 WARN=0",
) -> Path:
    rows = [
        "| Batch | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for number in range(1, 30):
        batch_id = f"B{number:02d}"
        if number < 15:
            status = "complete"
        elif number == 15:
            status = "blocked"
        elif number == 16:
            status = later_status
        else:
            status = "pending"
        gate = "semantic-lint" if number in {13, 16, 29} else "standardna"
        log = target_log if number == 15 else "test"
        rows.append(
            f"| {batch_id} | scope | {gate} | {status} | 2026-01-01 | 39 | nema | {log} |"
        )
    batches_path = kb_root / "batches.md"
    _write(batches_path, "\n".join(rows) + "\n")
    crypto_paths = v._ordered_source_paths(ROOT, "crypto")
    crypto_last = "—" if crypto_reviewed == 0 else crypto_paths[crypto_reviewed - 1]
    _write(
        kb_root / "_progress.md",
        "| source | total_files | reviewed | valid | rejected | paywalled | last_reviewed |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |\n"
        "| book | 248 | 248 | 77 | 171 | 0 | raw/book/pages/page_248.md |\n"
        f"| crypto | 46 | {crypto_reviewed} | 30 | 0 | 1 | {crypto_last} |\n"
        "| fraser | 243 | 0 | 0 | 0 | 0 | — |\n",
    )
    return batches_path


def _expected_standard_recovery_coupling(*_args, **_kwargs) -> tuple[int, dict]:
    return (
        1,
        {
            "summary": {"fail": 1, "warn": 0},
            "findings": [
                {
                    "severity": "FAIL",
                    "code": "F-BATCH-SCOPE-INCOMPLETE",
                    "location": "_progress.md",
                    "message": "crypto ledger blocked status coupling",
                }
            ],
        },
    )


def test_standard_blocked_recovery_cli_dispatches_without_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    captured: dict = {}
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(kb_ingest, "_current_branch", lambda _cwd: "main")
    monkeypatch.setattr(
        kb_ingest,
        "_run",
        lambda *_args: pytest.fail("content runner ne sme biti pozvan"),
    )
    monkeypatch.setattr(
        kb_ingest,
        "_invoke_safe_retry_gate",
        lambda **_kwargs: pytest.fail("semantic/model gate ne sme biti pozvan"),
    )

    def fake_recovery(**kwargs) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(kb_ingest, "_run_standard_blocked_recovery", fake_recovery)

    rc = kb_ingest.main(
        [
            "--kb",
            "expert-analyses",
            "--recover-batch",
            "B15",
            "--no-pr",
            "--",
            "--skip-git",
        ]
    )

    assert rc == 0
    assert captured["batch_id"] == "B15"
    assert captured["skip_git"] is True


@pytest.mark.parametrize(
    "args",
    [
        ["--recover-batch", "B15", "--", "--skip-git"],
        [
            "--recover-batch",
            "B15",
            "--retry-gate",
            "B16",
            "--no-pr",
            "--",
            "--skip-git",
        ],
    ],
)
def test_standard_blocked_recovery_requires_no_pr_and_exclusive_mode(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(
        kb_ingest,
        "_run_standard_blocked_recovery",
        lambda **_kwargs: pytest.fail("nebezbedan recovery ne sme biti pokrenut"),
    )

    assert kb_ingest.main(["--kb", "expert-analyses", *args]) == 2


@pytest.mark.parametrize(
    "passthrough",
    [
        ["--backend", "codex"],
        ["--skip-git", "--skip-git"],
        ["--max-batches", "1"],
    ],
)
def test_standard_blocked_recovery_rejects_agent_or_runner_arguments(
    passthrough: list[str],
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    with pytest.raises(ValueError, match="samo opciono --skip-git"):
        kb_ingest._recover_batch_passthrough(passthrough)


def test_standard_blocked_recovery_promotes_exact_boundary_without_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches_path = _blocked_standard_recovery_fixture(kb_root)
    state = kb_ingest.GitControlState(b"head", b"oid", b"refs", b"index")
    validations = iter(
        [
            _expected_standard_recovery_coupling(),
            (0, {"summary": {"fail": 0, "warn": 0}, "findings": []}),
        ]
    )
    monkeypatch.setattr(kb_ingest, "_git_control_state", lambda _cwd: state)
    monkeypatch.setattr(
        kb_ingest, "_post_validate", lambda *_a, **_k: next(validations)
    )
    monkeypatch.setattr(
        kb_ingest,
        "_invoke_safe_retry_gate",
        lambda **_kwargs: pytest.fail("recovery ne sme pozvati model"),
    )

    rc = kb_ingest._run_standard_blocked_recovery(
        cwd=ROOT,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        batch_id="B15",
        skip_git=True,
    )

    assert rc == 0
    assert "| B15 | scope | standardna | complete |" in batches_path.read_text(
        encoding="utf-8"
    )
    assert "| B16 | scope | semantic-lint | pending |" in batches_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("reviewed", [30, 32])
def test_standard_blocked_recovery_rejects_partial_and_overshoot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reviewed: int
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _blocked_standard_recovery_fixture(kb_root, crypto_reviewed=reviewed)
    monkeypatch.setattr(
        kb_ingest, "_post_validate", _expected_standard_recovery_coupling
    )

    with pytest.raises(RuntimeError, match="crypto ledger nije na tačnom"):
        kb_ingest._standard_blocked_recovery_preflight(
            cwd=ROOT,
            kb_root=kb_root,
            validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
            batch_id="B15",
            skip_git=True,
        )


def test_standard_blocked_recovery_rejects_out_of_order_progress(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    _blocked_standard_recovery_fixture(kb_root, later_status="complete")

    with pytest.raises(RuntimeError, match="kasniji batch/source"):
        kb_ingest._standard_blocked_recovery_preflight(
            cwd=ROOT,
            kb_root=kb_root,
            validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
            batch_id="B15",
            skip_git=True,
        )


def test_standard_blocked_recovery_rejects_semantic_gate(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches_path = _blocked_standard_recovery_fixture(kb_root)
    batches_path.write_text(
        batches_path.read_text(encoding="utf-8").replace(
            "| B15 | scope | standardna |", "| B15 | scope | semantic-lint |"
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="--retry-gate"):
        kb_ingest._standard_blocked_recovery_preflight(
            cwd=ROOT,
            kb_root=kb_root,
            validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
            batch_id="B15",
            skip_git=True,
        )


def test_standard_blocked_recovery_restores_blocked_row_on_post_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import kb_ingest

    kb_root = tmp_path / "research" / "expert-analyses"
    batches_path = _blocked_standard_recovery_fixture(kb_root)
    original = batches_path.read_text(encoding="utf-8")
    state = kb_ingest.GitControlState(b"head", b"oid", b"refs", b"index")
    validations = iter(
        [
            _expected_standard_recovery_coupling(),
            (1, {"summary": {"fail": 1, "warn": 0}, "findings": []}),
        ]
    )
    monkeypatch.setattr(kb_ingest, "_git_control_state", lambda _cwd: state)
    monkeypatch.setattr(
        kb_ingest, "_post_validate", lambda *_a, **_k: next(validations)
    )

    rc = kb_ingest._run_standard_blocked_recovery(
        cwd=ROOT,
        kb_root=kb_root,
        validator_script=ROOT / "scripts" / "validate_expert_analyses.py",
        batch_id="B15",
        skip_git=True,
    )

    assert rc == 1
    assert batches_path.read_text(encoding="utf-8") == original
