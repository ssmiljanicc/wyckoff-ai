#!/usr/bin/env python3
"""KB ingest wrapper — jedina tačka poziva poligon runnera (ADR 0006, mirror
aerodrom#142/#144 `~/projekti/aerodrom/scripts/kb_ingest.py`).

Poziv, ne import: čita `config/kb_ingest.yaml`, razreši putanju do poligon
`ingest_runner.py` (env `WYCKOFF_INGEST_RUNNER` ima prednost) i pokrene ga kao
subprocess sa `--kb-root`/`--validator-script` za izabrani KB. Svi ostali
argumenti se prosleđuju runneru netaknuti (`--dry-run`, `--skip-git`,
`--max-batches`, ...).

**Razlika od aerodrom exemplara (issue #219 nalaz 2 — "PR-tok = wrapper oko
poziva, ne izmena runnera")**: ovaj wrapper DODAJE grana+PR korak koji aerodrom
NEMA. Redosled (batch-ID nije unapred poznat pre poziva — runner sam bira
sledeći pending/partial batch, pa se grana pravi TEK POSLE): subprocess poziv
runneru na TEKUĆOJ (polaznoj) grani → upoređivanje batches.md status SNAPSHOT
pre/posle da se utvrdi koji batch(evi) su upravo obrađeni → `git checkout -b
wiki-ingest/<kb>-<timestamp>` → commit + push te grane → `gh pr create
--body-file` (NIKAD inline multi-line string) → **povratak na polaznu granu**
(uhvaćenu PRE poziva runneru) u svakom ishodu, da sledeći poziv ne nasledi
nemergovanu granu (PR #96 review, KRITIČan nalaz — ispravljeno).
`--dry-run` pozivi (nema pisanja u KB) NAMERNO preskaču ceo grana+PR tok — samo
subprocess poziv, bez git side-effect-a (sprečava trash grane iz test/validation
poziva). Ne-dry pozivi ODBIJAJU pokretanje ako je tekuća grana već
`wiki-ingest/*` (guard protiv lančanja na nemergovan PR).

Tvrdi zahtev: pokretati iz korena wyckoff-ai repoa — runner sidri repo_root, git
provere i rezoluciju `sources:` putanja na cwd.

Pokretanje (iz korena wyckoff-ai repoa):
    uv run python scripts/kb_ingest.py --kb expert-analyses -- --dry-run --skip-git
    uv run python scripts/kb_ingest.py --kb expert-analyses -- --max-batches 1
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

KONFIG_REL = Path("config") / "kb_ingest.yaml"
POLIGON_SCRIPTS_DIR = Path(
    os.environ.get("POLIGON_SCRIPTS_DIR", str(Path.home() / "projekti" / "poligon" / "scripts"))
)
# Jedan izvor istine za poligon core import — modul-nivo (ADR 0006, poziv ne
# import za RUNNER; core je Python modul pa se ovde legitimno importuje).
sys.path.insert(0, str(POLIGON_SCRIPTS_DIR))
import validate_kb_core as core  # noqa: E402

# Otvoreno pitanje (vidi PRPs/plans/wyckoff-onboarding-runner.plan.md §Notes):
# #89 je najbliži postojeći otvoreni wyckoff issue za research/expert-analyses/
# deliverable, ali NIJE doslovno "runner onboarding" issue. Lako izmenjiv posle
# operator odluke (ovde ILI preko --issue flaga).
DEFAULT_ISSUE_NUMBER = "89"

# Grane koje ovaj wrapper sam pravi (_open_pr_for_batches) — guard protiv
# pokretanja SA takve grane (PR #96 review nalaz, KRITIČNO): ako se prethodni
# poziv nije vratio na polaznu granu (bug ispravljen ovde), sledeći poziv bi se
# inače granao OD nemergovanog PR-a i lančano ga nosio u sledeći diff.
INGEST_BRANCH_RE = re.compile(r"^wiki-ingest/")


def ucitaj_konfig(repo_root: Path) -> dict:
    konfig_put = repo_root / KONFIG_REL
    with konfig_put.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def razresi_runner(konfig: dict) -> Path:
    """Putanja do poligon runnera; env WYCKOFF_INGEST_RUNNER ima prednost nad YAML-om."""
    iz_env = os.environ.get("WYCKOFF_INGEST_RUNNER", "").strip()
    if iz_env:
        return Path(iz_env)
    iz_yaml = (konfig.get("runner") or {}).get("putanja", "")
    return Path(iz_yaml)


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Pokreni poligon ingest runner nad wyckoff-ai KB-om (poziv, ne import) + PR-tok.",
        epilog="Svi nepoznati argumenti se prosleđuju runneru netaknuti (npr. --dry-run --skip-git --max-batches 1).",
    )
    parser.add_argument("--kb", default="expert-analyses", help="ključ KB-a iz config/kb_ingest.yaml")
    parser.add_argument(
        "--issue",
        default=DEFAULT_ISSUE_NUMBER,
        help=f"issue broj za PR title template (default: {DEFAULT_ISSUE_NUMBER})",
    )
    return parser.parse_known_args(argv)


def _load_profile(validator_script: Path):
    """Dinamički učitaj `PROFILE` iz validator wrappera — mirror
    `ingest_runner.py:_load_profile_from_validator_script` (isti `sys.modules`
    gotcha: registracija PRE `exec_module`, jer dataclass anotacije razrešavaju
    preko `sys.modules[cls.__module__]`)."""
    spec = importlib.util.spec_from_file_location(
        f"_kb_ingest_profile_{validator_script.stem}", validator_script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"ne mogu učitati validator modul: {validator_script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(spec.name, None)
        raise RuntimeError(f"validator modul {validator_script} nije učitljiv: {exc}") from exc
    profile = getattr(module, "PROFILE", None)
    if profile is None:
        raise RuntimeError(f"{validator_script} ne izlaže PROFILE (CorpusProfile)")
    # `sys.modules[spec.name] = module` gore garantuje da je ovo ISTI keširan
    # `validate_kb_core` modul kao `core` (modul-nivo import) — isinstance je
    # zato pouzdan i jeftin (PR #96 review nalaz).
    if not isinstance(profile, core.CorpusProfile):
        raise RuntimeError(
            f"{validator_script}.PROFILE nije core.CorpusProfile instanca "
            f"(dobijeno: {type(profile).__name__})"
        )
    return profile


def _current_branch(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _snapshot_batch_statuses(kb_root: Path, validator_script: Path) -> dict[str, str]:
    """`{batch_id: status}` snapshot iz `batches.md` — koristi core `parse_batches`
    + KB-ov sopstveni PROFILE (dinamički učitan)."""
    profile = _load_profile(validator_script)
    batches = core.parse_batches(kb_root, profile)
    return {b.id: b.status for b in batches}


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"kb-ingest: {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def _checkout(cwd: Path, branch: str) -> bool:
    return subprocess.run(["git", "checkout", branch], cwd=cwd, check=False).returncode == 0


def _open_pr_for_batches(
    *,
    cwd: Path,
    kb_root_rel: str,
    issue: str,
    changed: dict[str, tuple[str, str]],
    original_branch: str,
) -> int:
    """Grana + commit + push + `gh pr create --body-file` za batch-eve koji su
    upravo promenili status (pre != posle). NIKAD inline multi-line `--body`
    string (poznata zamka).

    Vraća repo na `original_branch` u SVAKOM ishodu (uspeh, prazan diff,
    obešena udaljena grana posle neuspelog `gh pr create`) — PR #96 review
    KRITIČAN nalaz: prethodna verzija je posle uspešnog `gh pr create` ostajala
    na novoj grani, pa se sledeći poziv granao OD nemergovanog PR-a i lančano
    ga nosio u sledeći diff.

    Vraća 0 na uspeh/no-op, 1 na grešku (repo ostaje na `branch` radi ručne
    inspekcije SAMO ako i povratak na `original_branch` ne uspe)."""
    if not changed:
        print("kb-ingest: nijedan batch nije promenio status — preskačem grana/PR tok.")
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_ids = sorted(changed.keys())
    branch = f"wiki-ingest/expert-analyses-{timestamp}"
    scope = ", ".join(batch_ids)

    subprocess.run(["git", "checkout", "-b", branch], cwd=cwd, check=True)
    subprocess.run(["git", "add", kb_root_rel], cwd=cwd, check=True)
    status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd, check=False)

    # rc 0 = nema staged izmena, rc 1 = ima staged izmena — SVAKI drugi rc je
    # git greška (npr. oštećen index) i NE sme se tumačiti kao "ima izmena".
    if status.returncode not in (0, 1):
        print(
            f"kb-ingest GREŠKA: 'git diff --cached --quiet' vratio neočekivan rc={status.returncode} "
            f"(git greška, ne staged-diff signal) — repo ostaje na '{branch}' radi inspekcije.",
            file=sys.stderr,
        )
        return 1

    if status.returncode == 0:
        print("kb-ingest: nema staged izmena posle batch-a — preskačem commit/PR.")
        if not _checkout(cwd, original_branch):
            print(
                f"kb-ingest UPOZORENJE: povratak na '{original_branch}' nije uspeo — "
                f"repo ostaje na '{branch}'.",
                file=sys.stderr,
            )
            return 1
        if subprocess.run(["git", "branch", "-D", branch], cwd=cwd, check=False).returncode != 0:
            print(
                f"kb-ingest UPOZORENJE: brisanje prazne grane '{branch}' nije uspelo — obriši ručno.",
                file=sys.stderr,
            )
        return 0

    commit_title = f"#{issue} Wiki ingest (research/expert-analyses, {scope})"
    commit_body_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as commit_body_file:
            commit_body_file.write(commit_title + "\n\n")
            for bid in batch_ids:
                before, after = changed[bid]
                commit_body_file.write(f"- {bid}: {before} -> {after}\n")
            commit_body_path = commit_body_file.name
        subprocess.run(["git", "commit", "-F", commit_body_path], cwd=cwd, check=True)
    finally:
        if commit_body_path:
            os.unlink(commit_body_path)

    subprocess.run(["git", "push", "-u", "origin", branch], cwd=cwd, check=True)

    pr_body_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as pr_body_file:
            pr_body_file.write(f"## Sažetak\n\nRunner batch ingest: {scope} (`research/expert-analyses`).\n\n")
            pr_body_file.write("## Batch-evi\n\n")
            for bid in batch_ids:
                before, after = changed[bid]
                pr_body_file.write(f"- `{bid}`: `{before}` -> `{after}`\n")
            pr_body_file.write("\n🤖 Otvoreno preko `scripts/kb_ingest.py`.\n")
            pr_body_path = pr_body_file.name
        gh_result = subprocess.run(
            ["gh", "pr", "create", "--title", commit_title, "--body-file", pr_body_path],
            cwd=cwd,
            check=False,
        )
    finally:
        if pr_body_path:
            os.unlink(pr_body_path)

    if gh_result.returncode != 0:
        print(
            f"kb-ingest GREŠKA: 'gh pr create' nije uspeo (rc={gh_result.returncode}), ali grana "
            f"'{branch}' JE push-ovana na origin sa commit-om ({scope}) — obešena udaljena grana. "
            f"Otvori PR ručno (gh pr create --title \"{commit_title}\" --base {original_branch} "
            f"--head {branch}) ili obriši granu (git push origin --delete {branch}) ako je greškom.",
            file=sys.stderr,
        )
        _checkout(cwd, original_branch)  # best-effort povratak, ne guta gornju grešku
        return 1

    if not _checkout(cwd, original_branch):
        print(
            f"kb-ingest UPOZORENJE: PR otvoren, ali povratak na '{original_branch}' nije uspeo — "
            f"repo je ostao na '{branch}'. Pre sledećeg poziva: git checkout {original_branch}.",
            file=sys.stderr,
        )
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    args, runner_args = parse_args(argv)
    cwd = Path.cwd()

    # Tvrda cwd provera PRE subprocess-a: runner sidri repo/git/sources na cwd.
    if not (cwd / KONFIG_REL).is_file():
        print(
            f"greška: pokreni iz korena wyckoff-ai repoa (nema {KONFIG_REL} u {cwd})",
            file=sys.stderr,
        )
        return 2

    konfig = ucitaj_konfig(cwd)

    transport = (konfig.get("runner") or {}).get("transport", "subprocess")
    if transport != "subprocess":
        print(
            f"greška: transport '{transport}' nije implementiran — v1 podržava samo"
            " 'subprocess' (remote/MCP transport čeka poligon#87 okidač)",
            file=sys.stderr,
        )
        return 2

    kb_unos = (konfig.get("kb") or {}).get(args.kb)
    if not kb_unos:
        poznati = ", ".join(sorted((konfig.get("kb") or {}).keys())) or "nijedan"
        print(f"greška: nepoznat KB '{args.kb}' (poznati: {poznati})", file=sys.stderr)
        return 2

    kb_root = cwd / kb_unos["kb_root"]
    validator = cwd / kb_unos["validator_script"]
    if not kb_root.is_dir():
        print(f"greška: kb_root ne postoji: {kb_root}", file=sys.stderr)
        return 2
    if not validator.is_file():
        print(f"greška: validator ne postoji: {validator}", file=sys.stderr)
        return 2

    runner = razresi_runner(konfig)
    if not runner.is_file():
        print(
            f"greška: poligon runner nije na putanji: {runner}\n"
            "  - proveri config/kb_ingest.yaml (runner.putanja), ili\n"
            "  - postavi env WYCKOFF_INGEST_RUNNER na putanju do ingest_runner.py",
            file=sys.stderr,
        )
        return 2

    passthrough = list(runner_args)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    is_dry_run = "--dry-run" in passthrough

    cmd = [
        sys.executable,
        str(runner),
        "--kb-root",
        str(kb_root),
        "--validator-script",
        str(validator),
        *passthrough,
    ]

    if is_dry_run:
        # Dry-run ne piše ništa u KB — nema šta da se commit-uje/PR-uje, i
        # namerno se ne pravi grana (sprečava trash grane iz test/validation
        # poziva, npr. Validation Commands u wyckoff-onboarding-runner.plan.md).
        return _run(cmd, cwd)

    original_branch = _current_branch(cwd)
    if INGEST_BRANCH_RE.match(original_branch):
        print(
            f"greška: tekuća grana '{original_branch}' izgleda kao granu koju je ovaj wrapper "
            "sam napravio (nemergovan prethodni poziv) — pređi na nameravanu baznu granu pre "
            f"ponovnog pokretanja (npr. 'git checkout wyckoff-onboarding-runner' ili 'main').",
            file=sys.stderr,
        )
        return 2

    try:
        pre_snapshot = _snapshot_batch_statuses(kb_root, validator)
    except RuntimeError as exc:
        print(f"greška: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 2

    rc = _run(cmd, cwd)
    if rc != 0:
        print(f"kb-ingest: runner rc={rc} — preskačem grana/PR tok.", file=sys.stderr)
        return rc

    try:
        post_snapshot = _snapshot_batch_statuses(kb_root, validator)
    except RuntimeError as exc:
        print(
            f"greška: ingest je USPEO (rc=0), ali post-snapshot za grana/PR tok nije uspeo: {exc}\n"
            f"{traceback.format_exc()}",
            file=sys.stderr,
        )
        return 2

    changed = {
        bid: (pre_snapshot.get(bid, "?"), post_status)
        for bid, post_status in post_snapshot.items()
        if pre_snapshot.get(bid) != post_status
    }

    try:
        return _open_pr_for_batches(
            cwd=cwd,
            kb_root_rel=kb_unos["kb_root"],
            issue=args.issue,
            changed=changed,
            original_branch=original_branch,
        )
    except subprocess.CalledProcessError as exc:
        print(f"greška u grana/PR toku: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
