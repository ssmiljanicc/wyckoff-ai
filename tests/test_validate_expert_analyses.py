from __future__ import annotations

import sys
from pathlib import Path

import pytest

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


# --- check_extract_source_exists (PR #96 review nalaz) -------------------------


def test_nonexistent_source_path_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "source: raw/book/pages/page_014.md", "source: raw/book/pages/page_does_not_exist.md"
    )
    path = _extract(kb_root, "book_p014_bad_source.md", text)

    findings = v.check_extract_source_exists([path], repo_root=tmp_path, kb_root=kb_root)

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-SOURCE" for f in findings)


def test_existing_source_path_passes(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_good_source.md", VALID_FRONTMATTER)
    _write(tmp_path / "raw" / "book" / "pages" / "page_014.md", "sadržaj")

    findings = v.check_extract_source_exists([path], repo_root=tmp_path, kb_root=kb_root)

    assert findings == []


# --- check_extract_image_path ---------------------------------------------------


def test_nonexistent_image_path_fails(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = _extract(kb_root, "book_p014_bad_image.md", VALID_FRONTMATTER)

    findings = v.check_extract_image_path([path], repo_root=tmp_path, kb_root=kb_root)

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-IMAGE" for f in findings)


def test_remote_image_marker_is_exempt(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    text = VALID_FRONTMATTER.replace(
        "image_path: raw/book/images/page_014_fig_1.png",
        "image_path: (remote: https://example.com/x.jpg)",
    )
    path = _extract(kb_root, "book_p014_remote_image.md", text)

    findings = v.check_extract_image_path([path], repo_root=tmp_path, kb_root=kb_root)

    assert findings == []


# --- check_extract_not_full_copy ------------------------------------------------


def test_oversized_extract_warns(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    long_body = VALID_FRONTMATTER + ("reč " * 500)
    path = _extract(kb_root, "book_p014_too_long.md", long_body)

    findings = v.check_extract_not_full_copy([path], kb_root)

    assert any(f.severity == "WARN" and f.code == "W-EXTRACT-FULL-COPY" for f in findings)


# --- UnicodeDecodeError postaje Finding, ne crash (PR #96 review nalaz) --------


def test_undecodable_extract_becomes_finding_not_crash(tmp_path: Path) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    path = kb_root / "wiki" / "extracts" / "book_p014_bad_encoding.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00\x01 nije validan utf-8")

    findings = v.check_extract_frontmatter([path], kb_root)

    assert any(f.severity == "FAIL" and f.code == "F-EXTRACT-ENCODING" for f in findings)


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


# --- Regresija: batches.md parse-validnost (29 batch-eva) ----------------------


def test_real_batches_md_parses_to_29_batches() -> None:
    kb_root = ROOT / "research" / "expert-analyses"
    batches = v.core.parse_batches(kb_root, v.PROFILE)

    assert len(batches) == 29
    assert batches[0].id == "B01"
    assert batches[0].units == ("page_001-page_020",)


def test_real_kb_root_validates_clean() -> None:
    """Prazna/pre-sweep skela (bez extract sadržaja iz B01) mora vratiti
    fail=0 — acceptance kriterijum plana (Zadatak 5 Validation)."""
    kb_root = ROOT / "research" / "expert-analyses"
    findings = v.collect_findings(kb_root, ROOT, skip_git=True)

    fails = [f for f in findings if f.severity == "FAIL"]
    assert fails == []


def test_real_kb_root_validates_clean_with_git_check() -> None:
    """Produkcioni put (skip_git=False) — zatečena svita ga NIKAD nije izvršavala (Faza 2
    lekcija: git-check grana ostaje netestirana bez ovog testa). Sveže klonirani worktree ima
    čist raw/, pa se očekuje isti rezultat kao skip_git=True."""
    kb_root = ROOT / "research" / "expert-analyses"
    findings = v.collect_findings(kb_root, ROOT, skip_git=False)

    fails = [f for f in findings if f.severity == "FAIL"]
    assert fails == []


# --- RAW_UNIT_RE (D6) — regresija za sva tri raw podstabla ----------------------


@pytest.mark.parametrize(
    ("raw_path", "expected_stem"),
    [
        ("raw/book/pages/page_001.md", "page_001"),
        ("raw/crypto_archive/posts/wyckoff-crypto-report-53.md", "wyckoff-crypto-report-53"),
        ("raw/bruce_fraser/posts/some-fraser-article.md", "some-fraser-article"),
    ],
)
def test_raw_unit_re_matches_all_three_subtrees(raw_path: str, expected_stem: str) -> None:
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
    func_start = source.index("def _load_profile(")
    func_body = source[func_start : source.index("\ndef ", func_start + 1)]

    register_pos = func_body.index("sys.modules[spec.name] = module")
    exec_pos = func_body.index("spec.loader.exec_module(module)")

    assert register_pos < exec_pos, (
        "sys.modules[spec.name] = module mora biti PRE exec_module — "
        "vidi ingest_runner.py:_load_profile_from_validator_script gotcha"
    )
