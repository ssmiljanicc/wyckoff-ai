#!/usr/bin/env python3
"""Deterministički validator `research/expert-analyses/` KB-a: mehanička kapija
(FAIL) + semantički rizici (WARN), za konzumaciju poligon `ingest_runner.py`.

Ovaj wrapper JE core-parametrizovan (`~/projekti/poligon/scripts/validate_kb_core.py`)
ALI, za razliku od `validate_issues_kb.py`/`validate_skills_kb.py`, NE delegira na
`core.run_cli()`/`core.collect_findings()` monolitno. Dva strukturna razloga
(otkrivena čitanjem core/runner koda tokom planiranja, `PRPs/plans/wyckoff-onboarding-runner.plan.md`):

1. **Nebijektivan sadržajni model (D4).** `core.check_complete_coverage` očekuje
   TAČNO JEDNU content-stranicu po raw-jedinici iz batch-a (issues-KB: 1 issue =
   1 stranica; skills-KB: 1 skill = 1 stranica). Ovaj KB je istraživačka kuracija:
   N raw dokumenata (book/crypto/Fraser) → 0..M FILTRIRANIH extract kartica —
   većina Fraser postova se odbacuje. Poziv `check_complete_coverage` bi lažno
   FAIL-ovao svaki batch koji sadrži bar jedan odbačen dokument (očekivano,
   ne izuzetak). Pokrivenost umesto toga prati `_progress.md` ledger
   (`check_progress_ledger_sane` ispod) — strukturna sanost, ne potpuna
   pokrivenost (ta ostaje ručna/LLM procena, van dosega determinističkog gate-a).
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

Modul-level `PROFILE` je runner-consumed ugovor (#218/#220 poligon konvencija):
`ingest_runner.py --delta` mod dinamički učitava ovaj modul i čita `PROFILE`
da razreši layout parametre (raw regex, identitet, content dir) bez uvoza koda.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# scripts/ nije paket; poligon je DRUGI repo — apsolutna putanja, ne
# Path(__file__).parent (isti obrazac kao ingest_runner.py:69, prilagođen
# cross-repo pozivu). Env override za premestivost/testiranje.
_POLIGON_SCRIPTS_DIR = Path(
    os.environ.get("POLIGON_SCRIPTS_DIR", str(Path.home() / "projekti" / "poligon" / "scripts"))
)
sys.path.insert(0, str(_POLIGON_SCRIPTS_DIR))
import validate_kb_core as core  # noqa: E402


PAGE_DIRS = ("by-event", "by-structure")
CONTENT_DIR = "by-event"

# Jedna capture grupa preko alternacije triju raw podstabala (D6) — core radi
# `m.group(1)` bez provere broja grupa, pa regex SA odvojenom grupom po grani
# bi pukao na crypto/fraser granama.
RAW_UNIT_RE = re.compile(r"raw/(?:book/pages|crypto_archive/posts|bruce_fraser/posts)/([^/]+)\.md")

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

_PROGRESS_ROW_RE = re.compile(
    r"^\|\s*(book|crypto|fraser)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
)


@dataclass(frozen=True)
class Batch:
    id: str
    units: tuple  # tuple[str, ...] — opisni tekst za crypto/fraser, opseg za book
    status: str
    pages: int | None
    remaining: str
    location: str


def _make_batch(*, id, units, status, pages, remaining, location) -> Batch:
    return Batch(id=id, units=units, status=status, pages=pages, remaining=remaining, location=location)


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
            core.Finding("FAIL", "F-EXTRACT-ENCODING", f"fajl nije validan UTF-8: {exc}", rel)
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
            if field not in fm:
                findings.append(
                    core.Finding(
                        "FAIL",
                        "F-EXTRACT-FRONTMATTER",
                        f"nedostaje obavezno polje: {field}",
                        rel,
                    )
                )
        if "page" not in fm and "post_url" not in fm:
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
    return findings


def check_extract_source_exists(extract_paths: list[Path], repo_root: Path, kb_root: Path) -> list:
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
                    "FAIL", "F-EXTRACT-SOURCE", f"apsolutna source putanja nije dozvoljena: {source}", rel
                )
            )
            continue
        resolved = (repo_resolved / candidate).resolve()
        if not resolved.is_relative_to(repo_resolved) or not resolved.is_file():
            findings.append(
                core.Finding(
                    "FAIL", "F-EXTRACT-SOURCE", f"source ne pokazuje na postojeći raw fajl: {source}", rel
                )
            )
    return findings


def check_extract_image_path(extract_paths: list[Path], repo_root: Path, kb_root: Path) -> list:
    findings: list = []
    repo_resolved = repo_root.resolve()
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
        lowered = image_path.lower()
        if lowered.startswith("(remote") or lowered == "bez slike":
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
    haystacks: list[str] = []
    for d in (by_event_dir, by_structure_dir):
        if d.is_dir():
            for f in d.glob("*.md"):
                text, decode_findings = _read_text_safe(f, str(f.relative_to(kb_root)))
                findings += decode_findings
                if text is not None:
                    haystacks.append(text)
    combined = "\n".join(haystacks)
    for path in extract_paths:
        rel = str(path.relative_to(kb_root))
        if path.name not in combined:
            findings.append(
                core.Finding(
                    "WARN",
                    "W-EXTRACT-ORPHAN",
                    "extract nije referenciran ni u jednom wiki/by-event ili wiki/by-structure fajlu",
                    rel,
                )
            )
    return findings


# --- Domenska ekstenzija: _progress.md ledger strukturna sanost ---------------


def check_progress_ledger_sane(kb_root: Path) -> list:
    """Strukturna sanost `_progress.md` ledgera (izvor istine za pokrivenost,
    NE broj extract fajlova). NE proverava potpunu pokrivenost (reviewed ==
    total_files) — ta ostaje ručna/LLM procena (stari plan Validation #10),
    van dosega determinističkog gate-a. Ovde se proverava samo da red postoji
    za sva tri izvora i da su brojevi konzistentni (reviewed <= total_files,
    non-negativni)."""
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
    found_sources: set[str] = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _PROGRESS_ROW_RE.match(line.strip())
        if not m:
            continue
        source, total_str, reviewed_str = m.group(1), m.group(2), m.group(3)
        found_sources.add(source)
        total_files, reviewed = int(total_str), int(reviewed_str)
        if reviewed > total_files:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"{source}: reviewed ({reviewed}) > total_files ({total_files})",
                    f"_progress.md:{lineno}",
                )
            )
    for source in ("book", "crypto", "fraser"):
        if source not in found_sources:
            findings.append(
                core.Finding(
                    "FAIL",
                    "F-PROGRESS-LEDGER",
                    f"nedostaje red za izvor: {source}",
                    "_progress.md",
                )
            )
    return findings


# --- Agregacija -----------------------------------------------------------------


def collect_findings(kb_root: Path, repo_root: Path, skip_git: bool) -> list:
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
    findings += core.check_index_complete(pages, kb_root)
    findings += core.check_index_descriptions(pages, kb_root)
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
    findings += check_extract_not_full_copy(extract_paths, kb_root)
    findings += check_extract_parity(extract_paths, kb_root)
    findings += check_progress_ledger_sane(kb_root)

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
    args = parser.parse_args(argv)
    try:
        findings = collect_findings(args.kb_root, Path.cwd(), args.skip_git)
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
