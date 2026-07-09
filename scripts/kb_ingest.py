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
NEMA. PRE subprocess poziva pravi/prelazi na granu `wiki-ingest/<kb>-<timestamp>`
(batch-ID nije unapred poznat — runner sam bira sledeći pending/partial batch).
POSLE uspešnog poziva (rc==0) upoređuje batches.md status SNAPSHOT pre/posle da
utvrdi koji batch(evi) su upravo obrađeni, commit-uje promene, push-uje granu, i
otvara PR (`gh pr create --body-file`, NIKAD inline multi-line string).
`--dry-run` pozivi (nema pisanja u KB) NAMERNO preskaču ceo grana+PR tok — samo
subprocess poziv, bez git side-effect-a (sprečava trash grane iz test/validation
poziva).

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
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

KONFIG_REL = Path("config") / "kb_ingest.yaml"
POLIGON_SCRIPTS_DIR = Path(
    os.environ.get("POLIGON_SCRIPTS_DIR", str(Path.home() / "projekti" / "poligon" / "scripts"))
)

# Otvoreno pitanje (vidi PRPs/plans/wyckoff-onboarding-runner.plan.md §Notes):
# #89 je najbliži postojeći otvoreni wyckoff issue za research/expert-analyses/
# deliverable, ali NIJE doslovno "runner onboarding" issue. Lako izmenjiv posle
# operator odluke (ovde ILI preko --issue flaga).
DEFAULT_ISSUE_NUMBER = "89"


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
    return profile


def _snapshot_batch_statuses(kb_root: Path, validator_script: Path) -> dict[str, str]:
    """`{batch_id: status}` snapshot iz `batches.md` — koristi core `parse_batches`
    + KB-ov sopstveni PROFILE (dinamički učitan)."""
    sys.path.insert(0, str(POLIGON_SCRIPTS_DIR))
    import validate_kb_core as core  # noqa: E402

    profile = _load_profile(validator_script)
    batches = core.parse_batches(kb_root, profile)
    return {b.id: b.status for b in batches}


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"kb-ingest: {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def _open_pr_for_batches(
    *, cwd: Path, kb_root_rel: str, issue: str, changed: dict[str, tuple[str, str]]
) -> None:
    """Grana + commit + push + `gh pr create --body-file` za batch-eve koji su
    upravo promenili status (pre != posle). NIKAD inline multi-line `--body`
    string (poznata zamka)."""
    if not changed:
        print("kb-ingest: nijedan batch nije promenio status — preskačem grana/PR tok.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_ids = sorted(changed.keys())
    branch = f"wiki-ingest/expert-analyses-{timestamp}"
    scope = ", ".join(batch_ids)

    subprocess.run(["git", "checkout", "-b", branch], cwd=cwd, check=True)
    subprocess.run(["git", "add", kb_root_rel], cwd=cwd, check=True)
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=cwd, check=False
    )
    if status.returncode == 0:
        print("kb-ingest: nema staged izmena posle batch-a — preskačem commit/PR.")
        subprocess.run(["git", "checkout", "-"], cwd=cwd, check=False)
        subprocess.run(["git", "branch", "-D", branch], cwd=cwd, check=False)
        return

    commit_title = f"#{issue} Wiki ingest (research/expert-analyses, {scope})"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as commit_body_file:
        commit_body_file.write(commit_title + "\n\n")
        for bid in batch_ids:
            before, after = changed[bid]
            commit_body_file.write(f"- {bid}: {before} -> {after}\n")
        commit_body_path = commit_body_file.name
    subprocess.run(["git", "commit", "-F", commit_body_path], cwd=cwd, check=True)
    os.unlink(commit_body_path)

    subprocess.run(["git", "push", "-u", "origin", branch], cwd=cwd, check=True)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as pr_body_file:
        pr_body_file.write(f"## Summary\n\nRunner batch ingest: {scope} (`research/expert-analyses`).\n\n")
        pr_body_file.write("## Batch-evi\n\n")
        for bid in batch_ids:
            before, after = changed[bid]
            pr_body_file.write(f"- `{bid}`: `{before}` -> `{after}`\n")
        pr_body_file.write("\n🤖 Otvoreno preko `scripts/kb_ingest.py`.\n")
        pr_body_path = pr_body_file.name
    subprocess.run(
        [
            "gh", "pr", "create",
            "--title", commit_title,
            "--body-file", pr_body_path,
        ],
        cwd=cwd,
        check=True,
    )
    os.unlink(pr_body_path)


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

    try:
        pre_snapshot = _snapshot_batch_statuses(kb_root, validator)
    except RuntimeError as exc:
        print(f"greška: {exc}", file=sys.stderr)
        return 2

    rc = _run(cmd, cwd)
    if rc != 0:
        print(f"kb-ingest: runner rc={rc} — preskačem grana/PR tok.", file=sys.stderr)
        return rc

    post_snapshot = _snapshot_batch_statuses(kb_root, validator)
    changed = {
        bid: (pre_snapshot.get(bid, "?"), post_status)
        for bid, post_status in post_snapshot.items()
        if pre_snapshot.get(bid) != post_status
    }

    try:
        _open_pr_for_batches(
            cwd=cwd,
            kb_root_rel=kb_unos["kb_root"],
            issue=args.issue,
            changed=changed,
        )
    except subprocess.CalledProcessError as exc:
        print(f"greška u grana/PR toku: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
