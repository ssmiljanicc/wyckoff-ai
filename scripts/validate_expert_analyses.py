#!/usr/bin/env python3
"""Deterministički validator `research/expert-analyses/` KB-a: mehanička kapija
(FAIL) + semantički rizici (WARN), za konzumaciju Spona `spona-ingest` runner-a.

Ovaj wrapper JE core-parametrizovan (pinovan Spona paket,
`spona.validated_ingest.core.validator`, Spona PR #51 — read-only semantic gate
isolation, corrective commit `afa63eb`,
project dependency)
ALI, za razliku od `validate_issues_kb.py`/`validate_skills_kb.py`, NE delegira na
`core.run_cli()`/`core.collect_findings()` monolitno. Dva strukturna razloga
(otkrivena čitanjem core/runner koda tokom planiranja, `PRPs/plans/wyckoff-onboarding-runner.plan.md`):

1. **Nebijektivan sadržajni model (D4).** `core.check_complete_coverage` očekuje
   TAČNO JEDNU content-stranicu po raw-jedinici iz batch-a (issues-KB: 1 issue =
   1 stranica; skills-KB: 1 skill = 1 stranica). Ovaj KB je istraživačka kuracija:
   N raw dokumenata (book/crypto/Fraser) → 0..M FILTRIRANIH extract kartica —
   većina Fraser postova se odbacuje. Poziv `check_complete_coverage` bi lažno
   FAIL-ovao svaki batch koji sadrži bar jedan odbačen dokument (očekivano,
   ne izuzetak). Pokrivenost umesto toga prati `_progress.md` ledger, a
   `check_progress_ledger_sane` izvodi njegove brojače iz kanonskih inventara,
   extract kartica i paywall statusa za već pregledani prefiks.
2. **Domenski frontmatter sukob (D3).** `wiki/extracts/*.md` nose NAMERNO
   domenski frontmatter šablon (`research/expert-analyses/EXTRACT_TEMPLATE.md`)
   sa poljima `type: forward|retrospective|schematic` i
   `status: candidate|validated|eval-used` — vrednosti koje se KOSE sa core-ovim
   TVRDO KODIRANIM `VALID_TYPES`/`VALID_STATUSES` (llm-wiki lifecycle vokabular:
   `type: topic|system|...`, `status: draft|active|needs-review`). Zato
   `extracts/` NIJE u `PAGE_DIRS` — core `load_pages`/`check_frontmatter` ih
   nikad ne učitava/ne vidi. Umesto toga dobijaju SOPSTVENE domenske provere
   (`check_extract_*` ispod), direktan port `PRPs/plans/research-expert-analyses-index.plan.md`
   Validation #3/#5/#6/#7 u `Finding`-producing Python.

`wiki/by-event/*.md` i `wiki/by-structure/*.md` OSTAJU pun llm-wiki šablon —
core `check_frontmatter`/`check_index_complete`/`check_index_descriptions`/
`check_local_links`/`check_orphans`/`check_dup_title`/`check_anchors`/
`check_wiki_gap`/`check_stale_reingest` rade nad njima NEPROMENJENI (reuse, ne
duplikat). Ovo NIJE gubitak core reuse-a — samo se ne poziva kroz JEDAN
monolitni `collect_findings()` poziv nego kroz eksplicitnu kompoziciju funkcija
(`collect_findings` ispod) plus domenske dopune.

`raw/` (book/crypto_archive/bruce_fraser) živi na REPO-ROOT nivou, ne pod
`kb_root` (namerna devijacija D2 — `research/expert-analyses/raw` ne postoji;
raw je deljen sa ostatkom wyckoff-ai repoa, npr. eval pipeline-om). Zato
`core.check_raw_integrity(kb_root, ...)` ne bi ništa proveravao (kb_root/raw
ne postoji → git status na nepostojećoj putanji je trivijalno prazan).
`check_raw_integrity_multi` ispod proverava sve TRI stvarne raw putanje.

Modul-level `PROFILE` je runner-consumed ugovor (#218/#220 poligon konvencija,
poreklo pre G2 migracije): Spona `spona-ingest --delta` mod dinamički učitava
ovaj modul i čita `PROFILE` da razreši layout parametre (raw regex, identitet,
content dir) bez uvoza koda.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Spona validated-ingest, project dependency (pyproject.toml + uv.lock, ADR 0011 §D2 red 6).
# Module-alias oblik — sve postojeće core.X kvalifikovane reference ostaju nepromenjene
# (ADR 0012 §Šta ovaj ADR ne odlučuje: tačan oblik importa je izvršni detalj Faze 4).
from spona.validated_ingest.core import validator as core

try:
    from scripts import fraser_header_ocr
except ModuleNotFoundError:  # direct `python scripts/validate_expert_analyses.py`
    import fraser_header_ocr


PAGE_DIRS = ("by-event", "by-structure")
CONTENT_DIR = "by-event"

# Jedna capture grupa preko alternacije triju raw podstabala (D6) — core radi
# `m.group(1)` bez provere broja grupa, pa regex SA odvojenom grupom po grani
# bi pukao na crypto/fraser granama.
RAW_UNIT_RE = re.compile(
    r"raw/(?:book/pages|crypto_archive/posts|bruce_fraser/posts)/([^/]+)\.md"
)

# Repo-root-relativni raw pod-koreni (D2 — NE pod kb_root).
RAW_SUBTREES = ("raw/book", "raw/crypto_archive", "raw/bruce_fraser")

# Domenski frontmatter ugovor extract kartica (EXTRACT_TEMPLATE.md) — SVOJI
# enumi, namerno drugačiji od core VALID_TYPES/VALID_STATUSES (vidi docstring).
EXTRACT_REQUIRED_FIELDS = (
    "source",
    "asset",
    "timeframe",
    "wyckoff_event",
    "structure",
    "phase",
    "image_path",
    "type",
    "status",
)
EXTRACT_VALID_TYPES = {"forward", "retrospective", "schematic"}
EXTRACT_VALID_STATUSES = {"candidate", "validated", "eval-used"}
EXTRACT_WORD_LIMIT = 400
OCR_EVIDENCE_SCHEMA = "fraser-header-ocr/v1"
OCR_EVIDENCE_PARSER_VERSION = 10
OCR_EVIDENCE_MIN_CONFIDENCE = 0.85
OCR_EVIDENCE_RUNS = 2
OCR_EVIDENCE_ENGINE = "Apple Vision VNRecognizeTextRequest accurate"

SOURCE_PATTERNS = {
    "book": re.compile(r"^raw/book/pages/page_(\d{3})\.md$"),
    "crypto": re.compile(r"^raw/crypto_archive/posts/([^/]+)\.md$"),
    "fraser": re.compile(r"^raw/bruce_fraser/posts/([^/]+)\.md$"),
}
PAGE_RANGE_RE = re.compile(r"^(\d{1,3})-(\d{1,3})$")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

# Evidence recognition is intentionally narrower than the open-ended timeframe
# schema.  Unknown forms are ignored rather than rejected: these patterns only
# prove a contradiction when both sides are explicit and reproducible.
_TIMEFRAME_TOKEN_RE = re.compile(
    r"(?<![\w-])(?:"
    r"daily|weekly|monthly|yearly|intraday|"
    r"\d{1,3}(?:[- ]?(?:minute|min|hour|hr|day))"
    r")(?![\w-])",
    re.IGNORECASE,
)
_DIRECT_CHART_TIMEFRAME_RE = re.compile(
    r"\bon\s+(?:this|the)\s+(?P<timeframe>"
    r"daily|weekly|monthly|yearly|intraday|"
    r"\d{1,3}(?:[- ]?(?:minute|min|hour|hr|day))"
    r")\s+chart\b",
    re.IGNORECASE,
)
_CURRENT_CHART_TIMEFRAME_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:evaluating|reviewing|examining|studying)\s+"
    r"(?:this|the|a)\s+(?P<timeframe>"
    r"daily|weekly|monthly|yearly|intraday|"
    r"\d{1,3}(?:[- ]?(?:minute|min|hour|hr|day))"
    r")\s+chart\b",
    re.IGNORECASE | re.MULTILINE,
)
_DIRECT_CHART_ASSET_PATTERNS = (
    re.compile(
        r"(?<![\w-])(?i:daily|weekly|monthly|yearly|intraday|"
        r"\d{1,3}(?:[- ]?(?:minute|min|hour|hr|day)))\s+"
        r"(?P<asset>\$?[A-Z][A-Z0-9./&-]{0,19})"
        r"(?:\s+\d{4}(?:[-–]\d{2,4})?)?\s+chart\b"
    ),
    re.compile(
        r"(?<![\w-])(?P<asset>\$?[A-Z][A-Z0-9./&-]{0,19})\s+"
        r"(?i:daily|weekly|monthly|yearly|intraday|"
        r"\d{1,3}(?:[- ]?(?:minute|min|hour|hr|day)))\s+chart\b"
    ),
    re.compile(r"\bchart\s+of\s+(?P<asset>\$?[A-Z][A-Z0-9./&-]{0,19})\b"),
)
_NON_ASSET_CHART_TOKENS = {"HR", "MIN", "P&F", "PNF"}
_ASSET_ALIASES = {"INDU": "DJIA"}
_CLICK_FURNITURE_RE = re.compile(
    r"^\s*\((?:click|tap)\b[^)]*(?:chart|version)[^)]*\)\s*$", re.IGNORECASE
)
_SEPARATOR_RE = re.compile(r"^\s*(?:-{3,}|_{3,})\s*$")

# Kanonski batch krajevi. Vrednosti su kumulativni broj pregledanih raw
# jedinica po izvoru, ne broj extract kartica (jedan dokument može dati više
# extract-a ili nijedan).
BATCH_COMPLETION_COUNTS = {
    **{
        f"B{number:02d}": ("book", 248 if number == 13 else number * 20)
        for number in range(1, 14)
    },
    "B14": ("crypto", 16),
    "B15": ("crypto", 31),
    "B16": ("crypto", 46),
    **{
        f"B{number:02d}": ("fraser", 243 if number == 29 else (number - 16) * 20)
        for number in range(17, 30)
    },
}

_PROGRESS_ROW_RE = re.compile(
    r"^\|\s*(book|crypto|fraser)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
    r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*$"
)


@dataclass(frozen=True)
class Batch:
    id: str
    units: tuple  # tuple[str, ...] — opisni tekst za crypto/fraser, opseg za book
    status: str
    pages: int | None
    remaining: str
    location: str


@dataclass(frozen=True)
class MarkdownEvidenceBlock:
    """Ordered raw-Markdown evidence around one unambiguous image group."""

    heading: str
    image_targets: tuple[str, ...]
    body: str


def _make_batch(*, id, units, status, pages, remaining, location) -> Batch:
    return Batch(
        id=id,
        units=units,
        status=status,
        pages=pages,
        remaining=remaining,
        location=location,
    )


def build_expert_gate_prompt(batch_id: str, gate_type: str, kb_root: Path) -> str:
    """Domenski semantic-lint prompt; model/effort ostaju runner parametri."""
    source_by_batch = {"B13": "book", "B16": "crypto", "B29": "fraser"}
    source = source_by_batch.get(batch_id)
    if source is None or "semantic-lint" not in gate_type:
        raise core.ValidationError(
            f"nepodržana expert-ingest kapija: {batch_id} / {gate_type}"
        )
    return (
        f"Expert-analyses semantic-lint posle {batch_id} za izvor '{source}'. "
        "TI LIČNO radiš read-only proveru u ovoj sesiji: ne pokreći drugi agent, "
        "ne menjaj raw/, batches.md, _progress.md niti wiki sadržaj. Pročitaj "
        f"{kb_root}/EXTRACT_TEMPLATE.md, {kb_root}/_progress.md, ceo "
        f"{kb_root}/wiki/index.md i sve extract kartice čiji source pripada ovom izvoru. "
        "Za svaki rizičan uzorak proveri doslovni Verbatim pasus u raw source-u, "
        "source/page ili source/post_url identitet, image_path vezu sa istim dokumentom, "
        "event/structure/phase bez fabriciranja i pointere iz odgovarajućih by-event/"
        "by-structure stranica. Proveri da je coverage ledger stigao do završnog boundary-ja "
        "iz batches.md. Vrati strukturiran tekstualni izveštaj sa konkretnim putanjama i "
        "nalazima. Poslednji neprazan red MORA biti tačno `GATE_OUTCOME: PASS` samo ako nema "
        "nijednog nalaza, odnosno `GATE_OUTCOME: FAIL` ako postoji makar jedan nalaz. Marker "
        "navedi tačno jednom; missing ili dvosmislen marker blokira batch. Runner čuva stdout "
        "kao gate artefakt. Ne koristi generički "
        "issues-KB query/questions/health workflow i ne biraj model u promptu."
    )


PROFILE = core.CorpusProfile(
    name="expert-analyses",
    unit_word="event",
    page_dirs=PAGE_DIRS,
    content_dir=CONTENT_DIR,
    raw_unit_re=RAW_UNIT_RE,
    file_unit_re=None,
    identity_key="unit",
    identity_mode="stem",
    batch_column_prefix="jedinic",
    make_batch=_make_batch,
    batch_units=lambda b: b.units,
    gate_prompt_builder=build_expert_gate_prompt,
)


# --- Domenska ekstenzija: raw integritet preko tri repo-root podstabla (D2) ---


def check_raw_integrity_multi(repo_root: Path, skip_git: bool) -> list:
    """Proveri git-integritet SVA TRI raw podstabla (D2 — `raw/` je na
    repo-root nivou, ne pod `kb_root`, pa `core.check_raw_integrity(kb_root, ...)`
    ne bi ništa proverio). Reimplementacija umesto reuse-a jer core-ova funkcija
    fiksira `raw_dir = kb_root / "raw"` internalno — signatura ne odgovara."""
    if skip_git:
        return []
    findings: list = []
    for subtree in RAW_SUBTREES:
        raw_dir = repo_root / subtree
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--", str(raw_dir)],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
        except FileNotFoundError as exc:
            raise core.ValidationError("komanda 'git' nije pronađena") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or str(exc)).strip()
            raise core.ValidationError(f"git status nije uspeo: {detail}") from exc
        if result.stdout.strip():
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-RAW-INTEGRITY",
                    f"raw/ je izmenjen (git status nije prazan) — raw mora biti read-only: {subtree}",
                    subtree,
                )
            )
    return findings


# --- Domenske ekstenzije: extract kartice (EXTRACT_TEMPLATE.md ugovor) --------


def _extract_paths(kb_root: Path) -> list[Path]:
    extracts_dir = kb_root / "wiki" / "extracts"
    if not extracts_dir.is_dir():
        return []
    return sorted(extracts_dir.glob("*.md"))


def _read_text_safe(path: Path, rel: str) -> tuple[str | None, list]:
    """Pročitaj fajl hvatajući `UnicodeDecodeError` kao `Finding` umesto da
    probije `collect_findings` i sruši `main()` sirovim tracebackom (PR #96
    review nalaz — `UnicodeDecodeError` NIJE podklasa `OSError`/`ValidationError`,
    pa bi inače pobegla iz `main()`-ovog `except (core.ValidationError, OSError)`)."""
    try:
        return path.read_text(encoding="utf-8"), []
    except UnicodeDecodeError as exc:
        return None, [
            core.Finding(
                "FAIL", "F-EXTRACT-ENCODING", f"fajl nije validan UTF-8: {exc}", rel
            )
        ]


def check_extract_frontmatter(extract_paths: list[Path], kb_root: Path) -> list:
    findings: list = []
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        for field in EXTRACT_REQUIRED_FIELDS:
            if field not in fm or not str(fm[field]).strip():
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-FRONTMATTER",
                        f"nedostaje obavezno polje: {field}",
                        rel,
                    )
                )
        if (
            not str(fm.get("page", "")).strip()
            and not str(fm.get("post_url", "")).strip()
        ):
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    "nedostaje page/post_url (either/or, bar jedno obavezno)",
                    rel,
                )
            )
        etype = fm.get("type")
        if etype is not None and etype not in EXTRACT_VALID_TYPES:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    f"nevažeći type: {etype} (očekivano: {'|'.join(sorted(EXTRACT_VALID_TYPES))})",
                    rel,
                )
            )
        status = fm.get("status")
        if status is not None and status not in EXTRACT_VALID_STATUSES:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    f"nevažeći status: {status} (očekivano: {'|'.join(sorted(EXTRACT_VALID_STATUSES))})",
                    rel,
                )
            )
        event = str(fm.get("wyckoff_event", "")).strip()
        structure = str(fm.get("structure", "")).strip()
        phase = str(fm.get("phase", "")).strip()
        for metadata_field in ("asset", "timeframe"):
            if str(fm.get(metadata_field, "")).strip().lower() == "none":
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-FRONTMATTER",
                        f"{metadata_field} koristi sentinel 'unknown'; 'none' nije dozvoljen",
                        rel,
                    )
                )
        valid_events = {
            item.stem for item in (kb_root / "wiki" / "by-event").glob("*.md")
        }
        valid_structures = {
            item.stem for item in (kb_root / "wiki" / "by-structure").glob("*.md")
        }
        if event and event not in valid_events | {"none"}:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    "wyckoff_event mora biti postojeći by-event slug ili sentinel 'none'",
                    rel,
                )
            )
        if structure and structure not in valid_structures | {"none"}:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    "structure mora biti postojeći by-structure slug ili sentinel 'none'",
                    rel,
                )
            )
        for related_field, primary, valid_slugs in (
            ("related_events", event, valid_events),
            ("related_structures", structure, valid_structures),
        ):
            if related_field not in fm:
                continue
            raw_related = str(fm[related_field]).strip()
            related = [item.strip() for item in raw_related.split(",")]
            if not raw_related or any(not item for item in related):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-FRONTMATTER",
                        f"{related_field} mora biti neprazna comma-separated lista postojećih slugova",
                        rel,
                    )
                )
                continue
            if (
                primary == "none"
                or primary in related
                or len(related) != len(set(related))
                or any(item not in valid_slugs for item in related)
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-FRONTMATTER",
                        f"{related_field} sme sadržati samo jedinstvene dodatne postojeće slugove uz primary polje",
                        rel,
                    )
                )
        if event == "none" and structure == "none":
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    "wyckoff_event i structure ne smeju oba biti 'none'",
                    rel,
                )
            )
        if phase and phase not in {"A", "B", "C", "D", "E", "unknown"}:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-FRONTMATTER",
                    "phase mora biti A|B|C|D|E ili sentinel 'unknown'",
                    rel,
                )
            )
    return findings


def check_extract_source_exists(
    extract_paths: list[Path], repo_root: Path, kb_root: Path
) -> list:
    """`source:` mora pokazivati na postojeći raw fajl (`EXTRACT_TEMPLATE.md:3`
    — "putanja do raw fajla (mora postojati)"). Pre ovog nalaza (PR #96 review)
    `check_extract_frontmatter` je proveravao SAMO prisustvo polja, ne postojanje
    putanje — typo u `source` je prolazio deterministički gate, iako je
    §Disciplina citiranja u `batches.md` pogrešnu atribuciju tretira kao
    najskuplju grešku ove KB discipline. Mirror `check_extract_image_path`."""
    findings: list = []
    repo_resolved = repo_root.resolve()
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        source = str(fm.get("source", "")).strip()
        if not source:
            continue  # nedostajuće polje već FAIL-uje u check_extract_frontmatter
        candidate = Path(source)
        if candidate.is_absolute():
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-SOURCE",
                    f"apsolutna source putanja nije dozvoljena: {source}",
                    rel,
                )
            )
            continue
        resolved = (repo_resolved / candidate).resolve()
        source_kind = next(
            (
                kind
                for kind, pattern in SOURCE_PATTERNS.items()
                if pattern.fullmatch(source)
            ),
            None,
        )
        if source_kind is None:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-SOURCE",
                    "source mora biti .md fajl direktno iz očekivanog raw podstabla",
                    rel,
                )
            )
            continue
        if not resolved.is_relative_to(repo_resolved) or not resolved.is_file():
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-SOURCE",
                    f"source ne pokazuje na postojeći raw fajl: {source}",
                    rel,
                )
            )
            continue
        if source_kind == "book":
            source_match = SOURCE_PATTERNS["book"].fullmatch(source)
            assert source_match is not None
            source_page = int(source_match.group(1))
            page_raw = str(fm.get("page", "")).strip()
            if not page_raw.isdigit() or int(page_raw) != source_page:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-PROVENANCE",
                        f"book page mora odgovarati source filename-u ({source_page})",
                        rel,
                    )
                )
            if "post_url" in fm:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-PROVENANCE",
                        "book extract koristi page/page_range, ne post_url",
                        rel,
                    )
                )
        else:
            if "page" in fm or "page_range" in fm:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-PROVENANCE",
                        "crypto/Fraser extract koristi post_url, ne page/page_range",
                        rel,
                    )
                )
            declared_url = str(fm.get("post_url", "")).strip()
            source_url = re.search(
                r"^URL:\s*(\S+)\s*$",
                resolved.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if not source_url or declared_url != source_url.group(1):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-PROVENANCE",
                        "post_url mora doslovno odgovarati URL headeru navedenog raw posta",
                        rel,
                    )
                )
    return findings


def _book_page_span(fm: dict, rel: str) -> tuple[range | None, list]:
    findings: list = []
    page_raw = str(fm.get("page", "")).strip()
    if not page_raw.isdigit():
        return None, findings
    start = int(page_raw)
    page_range_raw = str(fm.get("page_range", "")).strip()
    if not page_range_raw:
        return range(start, start + 1), findings
    match = PAGE_RANGE_RE.fullmatch(page_range_raw)
    if not match:
        findings.append(
            core.Finding(
                "FAIL",
                "F-EXTRACT-PROVENANCE",
                "page_range mora biti oblika NNN-NNN",
                rel,
            )
        )
        return None, findings
    range_start, range_end = int(match.group(1)), int(match.group(2))
    if range_start != start or range_end != start + 1:
        findings.append(
            core.Finding(
                "FAIL",
                "F-EXTRACT-PROVENANCE",
                "page_range je dozvoljen samo za source stranicu i neposredno sledeću stranicu",
                rel,
            )
        )
        return None, findings
    return range(range_start, range_end + 1), findings


def _source_kind(source: str) -> str | None:
    return next(
        (
            kind
            for kind, pattern in SOURCE_PATTERNS.items()
            if pattern.fullmatch(source)
        ),
        None,
    )


def _normalize_markdown_image_target(
    target: str, source_path: Path, repo_root: Path
) -> str | None:
    target = target.strip().split(maxsplit=1)[0].strip("<>")
    if re.match(r"^https?://", target):
        return f"(remote: {target})"
    repo_resolved = repo_root.resolve()
    resolved = (source_path.parent / target).resolve()
    if not resolved.is_relative_to(repo_resolved):
        return None
    return resolved.relative_to(repo_resolved).as_posix()


def _is_image_group_furniture(line: str) -> bool:
    return not line.strip() or bool(
        _CLICK_FURNITURE_RE.fullmatch(line) or _SEPARATOR_RE.fullmatch(line)
    )


def _markdown_evidence_blocks(
    source_path: Path, repo_root: Path
) -> list[MarkdownEvidenceBlock]:
    """Preserve image/text order without guessing across ambiguous groups.

    Consecutive images separated only by blank/click-through furniture belong
    to one candidate group.  A heading or substantive prose closes the prior
    group before a later image begins.
    """

    blocks: list[MarkdownEvidenceBlock] = []
    current_images: list[str] = []
    current_body: list[str] = []
    current_heading = ""
    latest_heading = ""

    def flush() -> None:
        nonlocal current_images, current_body, current_heading
        if current_images:
            blocks.append(
                MarkdownEvidenceBlock(
                    heading=current_heading,
                    image_targets=tuple(current_images),
                    body="\n".join(current_body).strip(),
                )
            )
        current_images = []
        current_body = []
        current_heading = ""

    for line in source_path.read_text(encoding="utf-8").splitlines():
        heading_match = re.match(r"^#{1,6}\s+(?P<heading>.+?)\s*$", line)
        if heading_match:
            flush()
            latest_heading = heading_match.group("heading")
            continue

        image_targets = MARKDOWN_IMAGE_RE.findall(line)
        if image_targets:
            normalized = [
                value
                for target in image_targets
                if (
                    value := _normalize_markdown_image_target(
                        target, source_path, repo_root
                    )
                )
                is not None
            ]
            if current_images and not all(
                _is_image_group_furniture(item) for item in current_body
            ):
                flush()
            if not current_images:
                current_heading = latest_heading
                current_body = []
            else:
                current_body = []
            current_images.extend(normalized)
            continue

        if current_images:
            current_body.append(line)

    flush()
    return blocks


def _markdown_image_paths(source_path: Path, repo_root: Path) -> set[str]:
    return {
        target
        for block in _markdown_evidence_blocks(source_path, repo_root)
        for target in block.image_targets
        if not target.lower().startswith("(remote:")
    }


def _fraser_image_map(
    repo_root: Path,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    manifest_path = repo_root / "raw" / "bruce_fraser" / "images-manifest.json"
    if not manifest_path.is_file():
        return {}, {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    local: dict[str, set[str]] = {}
    remote: dict[str, set[str]] = {}
    for image in payload.get("images", []):
        posts = {ref.get("post", "") for ref in image.get("references", [])}
        local_path = str(image.get("path", ""))
        local.setdefault(local_path, set()).update(posts)
        if image.get("status") != "available" or not (repo_root / local_path).is_file():
            remote.setdefault(str(image.get("url", "")), set()).update(posts)
    return local, remote


def check_extract_image_path(
    extract_paths: list[Path], repo_root: Path, kb_root: Path
) -> list:
    findings: list = []
    repo_resolved = repo_root.resolve()
    book_manifest_path = repo_root / "raw" / "book" / "image_manifest.json"
    book_manifest = (
        {
            item["image_path"]: int(item["page_number"])
            for item in json.loads(book_manifest_path.read_text(encoding="utf-8"))
        }
        if book_manifest_path.is_file()
        else {}
    )
    fraser_local, fraser_remote = _fraser_image_map(repo_root)
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        image_path = str(fm.get("image_path", "")).strip()
        if not image_path:
            continue
        source = str(fm.get("source", "")).strip()
        source_kind = _source_kind(source)
        lowered = image_path.lower()
        if lowered == "bez slike":
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-IMAGE",
                    "expert extract mora imati source-verifiable sliku; 'bez slike' nije dozvoljeno",
                    rel,
                )
            )
            continue
        if lowered.startswith("(remote"):
            remote_match = re.fullmatch(r"\(remote:\s*(https?://[^)]+)\)", image_path)
            remote_url = remote_match.group(1).strip() if remote_match else ""
            if source_kind != "fraser" or source not in fraser_remote.get(
                remote_url, set()
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-IMAGE-PROVENANCE",
                        "remote image je dozvoljen samo za Fraser URL mapiran na isti post u images-manifest.json",
                        rel,
                    )
                )
            continue
        candidate = Path(image_path)
        if candidate.is_absolute():
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-IMAGE",
                    f"apsolutna image_path putanja nije dozvoljena: {image_path}",
                    rel,
                )
            )
            continue
        resolved = (repo_resolved / candidate).resolve()
        if not resolved.is_relative_to(repo_resolved) or not resolved.is_file():
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-IMAGE",
                    f"image_path ne pokazuje na postojeći fajl: {image_path}",
                    rel,
                )
            )
            continue

        if source_kind == "book":
            span, span_findings = _book_page_span(fm, rel)
            findings += span_findings
            manifest_page = book_manifest.get(image_path)
            primary_page = str(fm.get("page", "")).strip()
            if (
                manifest_page is None
                or span is None
                or not primary_page.isdigit()
                or manifest_page != int(primary_page)
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-IMAGE-PROVENANCE",
                        "book image_path mora biti u image_manifest.json i pripadati primary source/page strani; page_range N+1 važi samo za nastavak citata",
                        rel,
                    )
                )
        elif source_kind == "crypto":
            source_path = repo_root / source
            if image_path not in _markdown_image_paths(source_path, repo_root):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-IMAGE-PROVENANCE",
                        "crypto image_path mora biti Markdown slika iz istog raw posta",
                        rel,
                    )
                )
        elif source_kind == "fraser" and source not in fraser_local.get(
            image_path, set()
        ):
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-IMAGE-PROVENANCE",
                    "Fraser image_path mora biti mapiran na isti post u images-manifest.json",
                    rel,
                )
            )
    return findings


def _section_body(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match else ""


def _normalize_timeframe(value: str) -> str | None:
    compact = re.sub(r"\s+", " ", value.strip().lower())
    compact = compact.replace("point & figure", "point and figure")
    compact = re.sub(
        r"\s+(?:point[- ]and[- ]figure|p&f|pnf)$", "", compact
    ).strip()
    if compact in {"daily", "weekly", "monthly", "yearly", "intraday"}:
        return compact
    if compact in {"point-and-figure", "point and figure", "p&f", "pnf"}:
        return None  # chart form alone does not identify a time interval
    match = re.fullmatch(
        r"(?P<number>\d{1,3})[- ]?(?P<unit>minute|min|hour|hr|day)", compact
    )
    if not match:
        return None
    unit = {"min": "minute", "hr": "hour"}.get(match.group("unit"), match.group("unit"))
    return f"{int(match.group('number'))}-{unit}"


def _timeframe_tokens(text: str, *, direct_chart_only: bool = False) -> set[str]:
    matches = (
        (
            match.group("timeframe")
            for match in _DIRECT_CHART_TIMEFRAME_RE.finditer(text)
        )
        if direct_chart_only
        else (match.group(0) for match in _TIMEFRAME_TOKEN_RE.finditer(text))
    )
    return {
        normalized
        for value in matches
        if (normalized := _normalize_timeframe(value)) is not None
    }


def _current_chart_timeframe_tokens(text: str) -> set[str]:
    """Return explicit declarations of the chart currently being evaluated.

    These declarations outrank later references to comparison charts in the
    same evidence block. Multiple declarations remain ambiguous and therefore
    cannot support a hard failure.
    """

    return {
        normalized
        for match in _CURRENT_CHART_TIMEFRAME_RE.finditer(text)
        if (normalized := _normalize_timeframe(match.group("timeframe"))) is not None
    }


def _timeframes_conflict(declared: str | None, explicit: str) -> bool:
    if declared is None or declared == explicit:
        return False
    intraday_units = ("-minute", "-hour")
    if declared == "intraday" and explicit.endswith(intraday_units):
        return False
    if explicit == "intraday" and declared.endswith(intraday_units):
        return False
    return True


def _normalize_asset(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    return _ASSET_ALIASES.get(normalized, normalized)


def _declared_asset_components(declared: str) -> set[str]:
    return {
        _normalize_asset(component)
        for component in re.split(r"\s+(?:/|&|and)\s+|,\s*", declared, flags=re.I)
        if component.strip()
    }


def _ocr_asset_matches(
    declared: str, observed: str, observed_members: set[str] | None = None
) -> bool:
    """Preserve scalar matching; compare multi-asset declarations as exact sets."""

    observed_normalized = _normalize_asset(observed)
    declared_components = _declared_asset_components(declared)
    if len(declared_components) <= 1:
        return bool(observed_normalized) and declared_components == {observed_normalized}
    if observed_members is None:
        return bool(observed_normalized) and observed_normalized in declared_components
    return declared_components == observed_members


def _direct_chart_asset_tokens(text: str) -> set[str]:
    assets: set[str] = set()
    for pattern in _DIRECT_CHART_ASSET_PATTERNS:
        for match in pattern.finditer(text):
            asset = match.group("asset")
            if asset not in _NON_ASSET_CHART_TOKENS:
                assets.add(_normalize_asset(asset))
    return {asset for asset in assets if asset}


def _unique_verbatim_block_match(
    text: str, blocks: list[MarkdownEvidenceBlock]
) -> tuple[int, MarkdownEvidenceBlock] | None:
    paragraphs = _verbatim_paragraphs(text)
    if not paragraphs:
        return None
    matching = [
        (index, block)
        for index, block in enumerate(blocks)
        if all(
            _canonical_verbatim(paragraph) in _canonical_verbatim(block.body)
            for paragraph in paragraphs
        )
    ]
    return matching[0] if len(matching) == 1 else None


def _verbatim_image_candidates(
    match: tuple[int, MarkdownEvidenceBlock], blocks: list[MarkdownEvidenceBlock]
) -> tuple[str, ...]:
    index, block = match
    candidates = list(block.image_targets)
    # Crypto/Fraser sources sometimes explain the following chart immediately
    # before its Markdown image.  Without pixel semantics both neighboring
    # groups are legitimate; a heading boundary is the only safe separator.
    if index + 1 < len(blocks) and blocks[index + 1].heading == block.heading:
        candidates.extend(blocks[index + 1].image_targets)
    return tuple(dict.fromkeys(candidates))


def check_extract_evidence_consistency(
    extract_paths: list[Path], repo_root: Path, kb_root: Path
) -> list:
    """Fail only on positive, reproducible metadata or adjacency conflicts."""

    findings: list = []
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        context = _section_body(text, "Kontekst")
        declared_timeframe = str(fm.get("timeframe", "")).strip()
        normalized_declared_timeframe = _normalize_timeframe(declared_timeframe)
        context_timeframes = _timeframe_tokens(context)
        if len(context_timeframes) == 1:
            explicit_timeframe = next(iter(context_timeframes))
            if declared_timeframe.lower() == "unknown" or (
                _timeframes_conflict(normalized_declared_timeframe, explicit_timeframe)
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-METADATA-CONTRADICTION",
                        f"timeframe '{declared_timeframe}' protivreči jednoznačnom "
                        f"Kontekst tokenu '{explicit_timeframe}'",
                        rel,
                    )
                )

        declared_asset = str(fm.get("asset", "")).strip()
        normalized_declared_asset = _normalize_asset(declared_asset)
        context_assets = _direct_chart_asset_tokens(context)
        if len(context_assets) == 1:
            explicit_asset = next(iter(context_assets))
            if declared_asset.lower() == "unknown" or (
                normalized_declared_asset
                and normalized_declared_asset != explicit_asset
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-METADATA-CONTRADICTION",
                        f"asset '{declared_asset}' protivreči jednoznačnom "
                        f"Kontekst tokenu '{explicit_asset}'",
                        rel,
                    )
                )

        source = str(fm.get("source", "")).strip()
        source_kind = _source_kind(source)
        source_path = repo_root / source
        image_path = str(fm.get("image_path", "")).strip()
        if (
            source_kind not in {"crypto", "fraser"}
            or not source_path.is_file()
            or not image_path
        ):
            continue

        blocks = _markdown_evidence_blocks(source_path, repo_root)
        evidence_match = _unique_verbatim_block_match(text, blocks)
        image_candidates = (
            _verbatim_image_candidates(evidence_match, blocks)
            if evidence_match is not None
            else ()
        )
        if image_candidates and image_path not in image_candidates:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-IMAGE-ADJACENCY",
                    "verbatim pasus je ograničen na susedne Markdown slike "
                    f"{', '.join(image_candidates)}, ne na deklarisanu sliku {image_path}",
                    rel,
                )
            )

        if evidence_match is None:
            continue
        evidence_index, evidence_block = evidence_match
        source_timeframes = _timeframe_tokens(evidence_block.heading)
        # A body-level statement is safe only when there is no same-section
        # following image to which it could refer (for example "chart below").
        body_timeframes = _current_chart_timeframe_tokens(evidence_block.body)
        if not body_timeframes and not (
            evidence_index + 1 < len(blocks)
            and blocks[evidence_index + 1].heading == evidence_block.heading
        ):
            body_timeframes = _timeframe_tokens(
                evidence_block.body, direct_chart_only=True
            )
        source_timeframes |= body_timeframes
        if len(source_timeframes) == 1:
            explicit_timeframe = next(iter(source_timeframes))
            if declared_timeframe.lower() == "unknown" or (
                _timeframes_conflict(normalized_declared_timeframe, explicit_timeframe)
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-METADATA-CONTRADICTION",
                        f"timeframe '{declared_timeframe}' protivreči jednoznačnoj "
                        f"raw chart tvrdnji '{explicit_timeframe}'",
                        rel,
                    )
                )

        source_assets = _direct_chart_asset_tokens(evidence_block.heading)
        if not (
            evidence_index + 1 < len(blocks)
            and blocks[evidence_index + 1].heading == evidence_block.heading
        ):
            source_assets |= _direct_chart_asset_tokens(evidence_block.body)
        if len(source_assets) == 1:
            explicit_asset = next(iter(source_assets))
            if declared_asset.lower() == "unknown" or (
                normalized_declared_asset and normalized_declared_asset != explicit_asset
            ):
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-METADATA-CONTRADICTION",
                        f"asset '{declared_asset}' protivreči jednoznačnoj raw chart "
                        f"tvrdnji '{explicit_asset}'",
                        rel,
                    )
                )
    return findings


def load_fraser_ocr_evidence(path: Path) -> dict:
    """Load the explicit versioned OCR artifact or reject the whole input."""

    if not path.is_file():
        raise core.ValidationError(f"OCR evidence fajl ne postoji: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise core.ValidationError(f"OCR evidence nije validan JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != OCR_EVIDENCE_SCHEMA:
        raise core.ValidationError(
            f"OCR evidence schema mora biti {OCR_EVIDENCE_SCHEMA}"
        )
    generator = payload.get("generator")
    if not isinstance(generator, dict) or (
        generator.get("parser_version") != OCR_EVIDENCE_PARSER_VERSION
        or generator.get("minimum_confidence") != OCR_EVIDENCE_MIN_CONFIDENCE
        or generator.get("runs_per_image") != OCR_EVIDENCE_RUNS
        or generator.get("engine") != OCR_EVIDENCE_ENGINE
        or generator.get("recognition_language") != "en-US"
        or generator.get("uses_language_correction") is not False
        or not isinstance(generator.get("toolchain"), dict)
    ):
        raise core.ValidationError("OCR evidence generator contract nije podržan")
    images = payload.get("images")
    if not isinstance(images, list):
        raise core.ValidationError("OCR evidence images mora biti lista")
    seen: set[str] = set()
    for record in images:
        image_path = record.get("image_path") if isinstance(record, dict) else None
        if not isinstance(image_path, str) or not image_path or image_path in seen:
            raise core.ValidationError(
                "OCR evidence image record mora imati jedinstven image_path"
            )
        seen.add(image_path)
    return payload


def _eligible_ocr_value(record: dict, field: str) -> str | None:
    value = record.get(field)
    if not isinstance(value, dict) or value.get("decision_eligible") is not True:
        return None
    observed = value.get("value")
    runs = value.get("runs")
    evidence = value.get("evidence")
    if (
        not isinstance(observed, str)
        or not observed
        or observed.lower() == "unknown"
        or runs != [observed] * OCR_EVIDENCE_RUNS
        or not isinstance(evidence, list)
        or len(evidence) != OCR_EVIDENCE_RUNS
    ):
        return None
    normalize = _normalize_asset if field == "asset" else _normalize_timeframe
    expected = normalize(observed)
    if not expected:
        return None
    for run_value, run_evidence in zip(runs, evidence, strict=True):
        if not isinstance(run_evidence, list):
            return None
        try:
            parsed = fraser_header_ocr.parse_header(run_evidence)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        parsed_field = parsed.get(field)
        supported = (
            parsed_field.get("value") if isinstance(parsed_field, dict) else None
        )
        if (
            normalize(str(run_value)) != expected
            or normalize(str(supported)) != expected
        ):
            return None
    return observed


def _eligible_ocr_asset_members(record: dict) -> set[str] | None:
    asset = record.get("asset")
    if not isinstance(asset, dict) or asset.get("members_decision_eligible") is not True:
        return None
    members = asset.get("members")
    runs = asset.get("member_runs")
    evidence = asset.get("member_evidence")
    if (
        not isinstance(members, list)
        or not members
        or not all(
            isinstance(member, str) and _normalize_asset(member)
            for member in members
        )
        or len({_normalize_asset(member) for member in members}) != len(members)
        or runs != [members] * OCR_EVIDENCE_RUNS
        or not isinstance(evidence, list)
        or len(evidence) != OCR_EVIDENCE_RUNS
    ):
        return None
    expected_members = {_normalize_asset(member) for member in members}
    for run_members, run_evidence in zip(runs, evidence, strict=True):
        if not isinstance(run_evidence, list):
            return None
        try:
            parsed = fraser_header_ocr.parse_header(run_evidence)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        parsed_members = {
            _normalize_asset(member)
            for member in parsed.get("asset", {}).get("members", [])
        }
        stored_members = {
            _normalize_asset(member)
            for member in run_members
            if isinstance(member, str)
        }
        if stored_members != expected_members or parsed_members != expected_members:
            return None
    return expected_members


def _file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check_extract_ocr_evidence(
    extract_paths: list[Path],
    repo_root: Path,
    kb_root: Path,
    evidence: dict | None,
) -> list:
    """Fail only on explicit, stable mismatches from a supplied OCR artifact."""

    if evidence is None:
        return []
    records = {record["image_path"]: record for record in evidence["images"]}
    findings: list = []
    warned_images: set[str] = set()
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        source = str(fm.get("source", "")).strip()
        image_path = str(fm.get("image_path", "")).strip()
        if _source_kind(source) != "fraser" or image_path.startswith("(remote:"):
            continue
        record = records.get(image_path)
        if record is None:
            continue
        resolved = (repo_root / image_path).resolve()
        image_root = (repo_root / "raw" / "bruce_fraser" / "images").resolve()
        if not resolved.is_relative_to(image_root) or not resolved.is_file():
            continue  # existing image/provenance checks own this failure
        expected_hash = record.get("sha256")
        actual_hash = _file_sha256(resolved)
        if (
            not isinstance(expected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or expected_hash != actual_hash
        ):
            if image_path not in warned_images:
                findings.append(
                    core.Finding(
                        "WARN",
                        "W-EXTRACT-OCR-EVIDENCE-SKIPPED",
                        f"OCR evidence SHA-256 ne odgovara slici {image_path}; regeneriši artefakt",
                        rel,
                    )
                )
                warned_images.add(image_path)
            continue

        for field in ("asset", "timeframe"):
            observed = _eligible_ocr_value(record, field)
            declared = str(fm.get(field, "")).strip()
            if observed is None or not declared or declared.lower() == "unknown":
                continue
            if field == "asset":
                declared_normalized = _normalize_asset(declared)
                observed_normalized = _normalize_asset(observed)
                declared_components = _declared_asset_components(declared)
                observed_members = _eligible_ocr_asset_members(record)
                if len(declared_components) > 1 and "members" in record.get("asset", {}):
                    if observed_members is None:
                        continue
                    values_match = _ocr_asset_matches(
                        declared, observed, observed_members
                    )
                else:
                    values_match = _ocr_asset_matches(declared, observed)
            else:
                declared_normalized = _normalize_timeframe(declared)
                observed_normalized = _normalize_timeframe(observed)
                values_match = declared_normalized == observed_normalized
            if (
                not declared_normalized
                or not observed_normalized
                or values_match
            ):
                continue
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-OCR-METADATA-CONTRADICTION",
                    f"{field} '{declared}' protivreči stabilnom OCR dokazu "
                    f"'{observed}' za {image_path} (sha256:{actual_hash})",
                    rel,
                )
            )
    return findings


def _verbatim_paragraphs(text: str) -> list[str]:
    """Vrati blockquote pasuse ispod tačno naslovljene Verbatim sekcije.

    Skidaju se samo Markdown `>` markeri. Poređenje kasnije kanonizuje razmake
    i prelome reda, ali ne menja nijedan token niti OCR artefakt.
    """
    body = _section_body(text, "Verbatim pasus")
    if not body:
        return []
    paragraphs: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        quote = re.match(r"^> ?(.*)$", line)
        if quote:
            content = quote.group(1)
            if content:
                current.append(content)
            elif current:
                paragraphs.append("\n".join(current))
                current = []
        elif current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def _canonical_verbatim(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_extract_verbatim(
    extract_paths: list[Path], repo_root: Path, kb_root: Path
) -> list:
    findings: list = []
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        fm = core.parse_frontmatter(text)
        source = str(fm.get("source", "")).strip()
        source_kind = _source_kind(source)
        source_path = repo_root / source
        if source_kind is None or not source_path.is_file():
            continue  # source provera već daje tvrdi nalaz
        source_texts = [source_path.read_text(encoding="utf-8")]
        if source_kind == "book" and fm.get("page_range"):
            span, span_findings = _book_page_span(fm, rel)
            findings += span_findings
            if span is None:
                continue
            source_texts = []
            for page_number in span:
                range_path = repo_root / f"raw/book/pages/page_{page_number:03d}.md"
                if not range_path.is_file():
                    findings.append(
                        core.Finding(
                            "FAIL",
                            "F-EXTRACT-PROVENANCE",
                            f"page_range source ne postoji: {range_path.relative_to(repo_root)}",
                            rel,
                        )
                    )
                    source_texts = []
                    break
                source_texts.append(range_path.read_text(encoding="utf-8"))
        paragraphs = _verbatim_paragraphs(text)
        if not paragraphs:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-VERBATIM",
                    "nedostaje neprazan blockquote u sekciji '## Verbatim pasus'",
                    rel,
                )
            )
            continue
        combined_source = _canonical_verbatim("\n".join(source_texts))
        for paragraph in paragraphs:
            if _canonical_verbatim(paragraph) not in combined_source:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-VERBATIM",
                        "verbatim blockquote nije doslovno prisutan u source/page_range tekstu",
                        rel,
                    )
                )
                break
    return findings


def check_extract_not_full_copy(extract_paths: list[Path], kb_root: Path) -> list:
    findings: list = []
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        if text is None:
            findings += decode_findings
            continue
        word_count = len(text.split())
        if word_count > EXTRACT_WORD_LIMIT:
            findings.append(
                core.Finding(
                    "WARN",
                    "W-EXTRACT-FULL-COPY",
                    f"extract ima {word_count} reči (>{EXTRACT_WORD_LIMIT}) — moguća kopija celog dokumenta umesto pointer+citat",
                    rel,
                )
            )
    return findings


def check_extract_parity(extract_paths: list[Path], kb_root: Path) -> list:
    findings: list = []
    by_event_dir = kb_root / "wiki" / "by-event"
    by_structure_dir = kb_root / "wiki" / "by-structure"

    def taxonomy_contract(index_path: Path) -> tuple[set[str], set[str]]:
        text, decode_findings = _read_text_safe(
            index_path, str(index_path.relative_to(kb_root))
        )
        findings.extend(decode_findings)
        if text is None:
            return set(), set()
        references: set[str] = set()
        for target in WIKILINK_RE.findall(text):
            target_path = Path(target.strip())
            if "extracts" in target_path.parts:
                references.add(target_path.stem)
        for file_part, _anchor in core.extract_links(text):
            target_path = Path(file_part)
            if "extracts" in target_path.parts:
                references.add(target_path.stem)
        sources: set[str] = set()
        raw_sources = core.parse_frontmatter(text).get("sources", [])
        if isinstance(raw_sources, list):
            for item in raw_sources:
                if isinstance(item, dict) and item.get("path"):
                    sources.add(str(item["path"]).strip())
                elif isinstance(item, str):
                    sources.add(item.strip())
        return references, sources

    taxonomy_paths = sorted(by_event_dir.glob("*.md")) + sorted(
        by_structure_dir.glob("*.md")
    )
    contracts = {path: taxonomy_contract(path) for path in taxonomy_paths}
    expected_by_extract: dict[str, set[Path]] = {}

    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        text, decode_findings = _read_text_safe(path, rel)
        findings += decode_findings
        if text is None:
            continue
        fm = core.parse_frontmatter(text)
        expected_indexes: list[Path] = []
        event = str(fm.get("wyckoff_event", "")).strip()
        structure = str(fm.get("structure", "")).strip()
        if event and event != "none":
            expected_indexes.append(by_event_dir / f"{event}.md")
        related_events = str(fm.get("related_events", "")).strip()
        if related_events:
            expected_indexes.extend(
                by_event_dir / f"{item.strip()}.md"
                for item in related_events.split(",")
                if item.strip()
            )
        if structure and structure != "none":
            expected_indexes.append(by_structure_dir / f"{structure}.md")
        related_structures = str(fm.get("related_structures", "")).strip()
        if related_structures:
            expected_indexes.extend(
                by_structure_dir / f"{item.strip()}.md"
                for item in related_structures.split(",")
                if item.strip()
            )
        expected = set(expected_indexes)
        expected_by_extract[path.stem] = expected
        missing_links: list[str] = []
        missing_sources: list[str] = []
        source = str(fm.get("source", "")).strip()
        for item in expected_indexes:
            contract = contracts.get(item)
            if contract is None or path.stem not in contract[0]:
                missing_links.append(item.relative_to(kb_root).as_posix())
            if contract is None or source not in contract[1]:
                missing_sources.append(item.relative_to(kb_root).as_posix())
        if missing_links:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-PARITY",
                    "extract nije referenciran extensionless ili .md linkom iz očekivanih indeksa: "
                    + ", ".join(missing_links),
                    rel,
                )
            )
        if missing_sources:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-EXTRACT-PARITY",
                    "očekivani taxonomy indeks nema raw source extracta u frontmatter sources: "
                    + ", ".join(missing_sources),
                    rel,
                )
            )

    for taxonomy_path, (references, _sources) in contracts.items():
        for extract_stem in references:
            expected = expected_by_extract.get(extract_stem)
            if expected is not None and taxonomy_path not in expected:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-PARITY",
                        f"nepovezani taxonomy indeks linkuje extract {extract_stem}",
                        taxonomy_path.relative_to(kb_root).as_posix(),
                    )
                )
    return findings


# --- Domenska ekstenzija: _progress.md ledger strukturna sanost ---------------


def check_progress_ledger_sane(
    kb_root: Path, repo_root: Path, extract_paths: list[Path]
) -> list:
    """Derive every ledger counter from canonical inventories and extracts."""
    findings: list = []
    progress_path = kb_root / "_progress.md"
    if not progress_path.is_file():
        return [
            core.Finding(
                "FAIL",
                "F-PROGRESS-LEDGER",
                "_progress.md ne postoji",
                "_progress.md",
            )
        ]
    text, decode_findings = _read_text_safe(progress_path, "_progress.md")
    if text is None:
        return decode_findings
    rows: dict[str, tuple[int, dict[str, int | str]]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _PROGRESS_ROW_RE.match(line.strip())
        if not m:
            continue
        rows[m.group(1)] = (
            lineno,
            {
                "total": int(m.group(2)),
                "reviewed": int(m.group(3)),
                "valid": int(m.group(4)),
                "rejected": int(m.group(5)),
                "paywalled": int(m.group(6)),
                "last_reviewed": m.group(7).strip(),
            },
        )

    extract_counts = {"book": 0, "crypto": 0, "fraser": 0}
    represented = {"book": set(), "crypto": set(), "fraser": set()}
    for path in extract_paths:
        text_value, _decode_findings = _read_text_safe(
            path, str(path.relative_to(kb_root))
        )
        if text_value is None:
            continue
        source_path = str(core.parse_frontmatter(text_value).get("source", "")).strip()
        source_kind = _source_kind(source_path)
        if source_kind is None:
            continue
        extract_counts[source_kind] += 1
        represented[source_kind].add(Path(source_path).as_posix())

    for source in ("book", "crypto", "fraser"):
        if source not in rows:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"nedostaje red za izvor: {source}",
                    "_progress.md",
                )
            )
            continue

        lineno, row = rows[source]
        inventory = _ordered_source_paths(repo_root, source)
        reviewed = int(row["reviewed"])
        if reviewed > len(inventory):
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"{source}: reviewed ({reviewed}) > canonical total ({len(inventory)})",
                    f"_progress.md:{lineno}",
                )
            )
        reviewed_prefix = set(inventory[:reviewed])
        outside_prefix = sorted(represented[source] - reviewed_prefix)
        if outside_prefix:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"{source}: extract source je van reviewed prefiksa: "
                    + ", ".join(outside_prefix),
                    f"_progress.md:{lineno}",
                )
            )

        paywalled = len(_paywalled_source_paths(repo_root, source) & reviewed_prefix)
        represented_reviewed = len(represented[source] & reviewed_prefix)
        rejected = reviewed - represented_reviewed - paywalled
        expected = {
            "total": len(inventory),
            "valid": extract_counts[source],
            "paywalled": paywalled,
            "rejected": rejected,
        }
        if rejected < 0:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"{source}: izvedeni rejected je negativan ({rejected}); "
                    "represented/paywalled skupovi se preklapaju ili prelaze reviewed",
                    f"_progress.md:{lineno}",
                )
            )
        for field, expected_value in expected.items():
            actual = int(row[field])
            if actual != expected_value:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-PROGRESS-LEDGER",
                        f"{source}: {field} mora biti izvedeno {expected_value}, "
                        f"dobijeno {actual}",
                        f"_progress.md:{lineno}",
                    )
                )
    return findings


def read_progress_ledger(kb_root: Path) -> dict[str, dict[str, int | str]]:
    rows: dict[str, dict[str, int | str]] = {}
    text = (kb_root / "_progress.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        match = _PROGRESS_ROW_RE.match(line.strip())
        if not match:
            continue
        rows[match.group(1)] = {
            "total": int(match.group(2)),
            "reviewed": int(match.group(3)),
            "valid": int(match.group(4)),
            "rejected": int(match.group(5)),
            "paywalled": int(match.group(6)),
            "last_reviewed": match.group(7).strip(),
        }
    return rows


def _ordered_source_paths(repo_root: Path, source: str) -> list[str]:
    if source == "book":
        return [f"raw/book/pages/page_{number:03d}.md" for number in range(1, 249)]
    if source == "crypto":
        manifest = json.loads(
            (repo_root / "raw/crypto_archive/manifest.json").read_text(encoding="utf-8")
        )
        return [f"raw/crypto_archive/posts/{item['slug']}.md" for item in manifest]
    return [
        path.relative_to(repo_root).as_posix()
        for path in sorted(
            (repo_root / "raw/bruce_fraser/posts").glob("*.md"), key=lambda p: p.name
        )
    ]


def _paywalled_source_paths(repo_root: Path, source: str) -> set[str]:
    if source != "crypto":
        return set()
    manifest = json.loads(
        (repo_root / "raw/crypto_archive/manifest.json").read_text(encoding="utf-8")
    )
    return {
        f"raw/crypto_archive/posts/{item['slug']}.md"
        for item in manifest
        if item.get("status") == "paywalled"
    }


def expected_batch_boundary(repo_root: Path, batch_id: str) -> tuple[str, int, str]:
    source, reviewed = BATCH_COMPLETION_COUNTS[batch_id]
    paths = _ordered_source_paths(repo_root, source)
    if reviewed < 1 or reviewed > len(paths):
        raise core.ValidationError(
            f"{batch_id}: kanonski kraj {reviewed} je van {source} manifesta ({len(paths)})"
        )
    return source, reviewed, paths[reviewed - 1]


def check_batch_scope_completion(
    kb_root: Path, repo_root: Path, batches: list[Batch]
) -> list:
    """Fail-closed veza Spona statusa i coverage ledgera.

    Spona meri samo `pages_delta`, pa bi agent koji obradi deo scope-a mogao da
    dobije `complete`. Ova provera veže svaki završen batch za njegov kanonski
    kumulativni boundary i hvata i delimično pomeren pending/partial batch.
    """
    findings: list = []
    first_noncomplete: Batch | None = None
    for batch in batches:
        if batch.status != "complete":
            first_noncomplete = first_noncomplete or batch
        elif first_noncomplete is not None:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-BATCH-ORDER",
                    f"{batch.id} je complete posle nezavršenog {first_noncomplete.id}; "
                    "batch-evi moraju završavati kanonskim redom",
                    "batches.md",
                )
            )

    rows = read_progress_ledger(kb_root)
    active = next(
        (batch for batch in batches if batch.status in {"pending", "partial"}), None
    )
    completed_boundary = {"book": 0, "crypto": 0, "fraser": 0}
    for batch in batches:
        if batch.status == "complete" and batch.id in BATCH_COMPLETION_COUNTS:
            source, reviewed = BATCH_COMPLETION_COUNTS[batch.id]
            completed_boundary[source] = max(completed_boundary[source], reviewed)

    for source, row in rows.items():
        reviewed = int(row["reviewed"])
        last_reviewed = str(row["last_reviewed"])
        allowed = {completed_boundary[source]}
        if active and active.id in BATCH_COMPLETION_COUNTS:
            active_source, active_boundary = BATCH_COMPLETION_COUNTS[active.id]
            if active_source == source:
                # Pre statusnog upisa validator vidi ili netaknut prethodni
                # boundary, ili TAČNO završen tekući scope. Sve između i svaki
                # overshoot su greška.
                allowed.add(active_boundary)
        if allowed == {0}:
            last_position = 0 if last_reviewed in {"—", "-", ""} else -1
        else:
            ordered_paths = _ordered_source_paths(repo_root, source)
            last_position = (
                ordered_paths.index(last_reviewed) + 1
                if last_reviewed in ordered_paths
                else 0
            )
        if reviewed not in allowed or last_position != reviewed:
            allowed_text = "/".join(str(item) for item in sorted(allowed))
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-BATCH-SCOPE-INCOMPLETE",
                    f"{source} ledger reviewed/last_reviewed mora biti na kanonskom boundary-ju {allowed_text}; dobijeno {reviewed}/{last_position}",
                    "_progress.md",
                )
            )
    return findings


# --- Agregacija -----------------------------------------------------------------


def collect_findings(
    kb_root: Path,
    repo_root: Path,
    skip_git: bool,
    ocr_evidence: dict | None = None,
) -> list:
    """SOPSTVENA kompozicija (NE `core.collect_findings`) — vidi modul docstring
    D3/D4 za zašto. Reuse core provera koje se primenjuju na `wiki/by-event`+
    `wiki/by-structure`+`wiki/index.md` stranice (`page_dirs`), PLUS domenske
    ekstenzije za `wiki/extracts/` i `_progress.md` ledger."""
    pages = core.load_pages(kb_root, PROFILE)
    batches = core.parse_batches(kb_root, PROFILE)
    extract_paths = _extract_paths(kb_root)

    findings: list = []
    # Core provere nad llm-wiki-šablonskim stranicama (by-event/by-structure/index)
    findings += core.check_sources_exist(pages, repo_root)
    findings += core.check_frontmatter(pages)
    findings += core.check_local_links(pages)
    findings += core.check_index_complete(pages, kb_root, PROFILE)
    findings += core.check_index_descriptions(pages, kb_root, PROFILE)
    findings += core.check_dup_identity(pages, PROFILE)
    findings += core.check_batch_status(batches)
    # NAMERNO IZOSTAVLJENO: core.check_complete_coverage (D4 — bijekcija ne važi)
    findings += check_raw_integrity_multi(repo_root, skip_git)
    # NAMERNO IZOSTAVLJENO: core.check_orphans (D7, PR #96 review nalaz — mk-pregled-logike-solo).
    # `check_orphans` pretpostavlja da sadržajne stranice primaju ulazne veze
    # JEDNA OD DRUGE; u ovoj topologiji `by-event`/`by-structure` stranice
    # primaju linkove ISKLJUČIVO iz `wiki/index.md` (isključen iz provere) i
    # pokazuju NA extract kartice (koje nisu `Page`-ovi core-a) — nikad jedna
    # od druge. Svih ~28 taksonomijskih stranica bi zato bilo TRAJNO "orphan"
    # kroz ceo život korpusa (empirijski potvrđeno: B01 E2E warn=30, od čega
    # ~28 ovaj šum), zasićujući WARN kanal u kome operator treba da primeti
    # STVARNE signale (W-STALE-REINGEST, W-BATCH-SUSPECT, W-EXTRACT-*). Isti
    # kriterijum kao D4: core provera čija premisa ne važi za ovu topologiju.
    findings += core.check_dup_title(pages)
    findings += core.check_anchors(pages)
    findings += core.check_wiki_gap(pages)
    findings += core.check_batch_suspect(batches)
    findings += core.check_stale_reingest(pages, repo_root, PROFILE)

    # Domenske ekstenzije nad extract karticama + ledger
    findings += check_extract_frontmatter(extract_paths, kb_root)
    findings += check_extract_source_exists(extract_paths, repo_root, kb_root)
    findings += check_extract_image_path(extract_paths, repo_root, kb_root)
    findings += check_extract_verbatim(extract_paths, repo_root, kb_root)
    findings += check_extract_evidence_consistency(extract_paths, repo_root, kb_root)
    findings += check_extract_ocr_evidence(
        extract_paths, repo_root, kb_root, ocr_evidence
    )
    findings += check_extract_not_full_copy(extract_paths, kb_root)
    findings += check_extract_parity(extract_paths, kb_root)
    findings += check_progress_ledger_sane(kb_root, repo_root, extract_paths)
    findings += check_batch_scope_completion(kb_root, repo_root, batches)

    return findings


# --- CLI -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """SOPSTVENI CLI loop (NE `core.run_cli`) — jer `run_cli` interno poziva
    `core.collect_findings` bezuslovno (nema hook za zamenu). Flagovi/JSON
    šema/exit semantika su IDENTIČNI `core.run_cli` ugovoru (parser je REUSE
    `core.build_parser`) tako da `--delta` mod i runner subprocess pozivi rade
    nepromenjeno."""
    parser = core.build_parser(
        default_kb_root=Path("research/expert-analyses"),
        description=__doc__,
        require_kb_root=False,
    )
    parser.add_argument(
        "--ocr-evidence",
        type=Path,
        help="opt-in fraser-header-ocr/v1 JSON; bez ovog flag-a OCR se ne koristi",
    )
    args = parser.parse_args(argv)
    try:
        ocr_evidence = (
            load_fraser_ocr_evidence(args.ocr_evidence)
            if args.ocr_evidence is not None
            else None
        )
        findings = collect_findings(
            args.kb_root, Path.cwd(), args.skip_git, ocr_evidence=ocr_evidence
        )
    except (core.ValidationError, OSError) as exc:
        print(f"greška: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(core.format_json(findings))
    else:
        print(core.format_report(findings))
    return 1 if any(f.severity == "FAIL" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
