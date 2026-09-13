#!/usr/bin/env python3
"""KB ingest wrapper — jedina tačka poziva Spona `spona-ingest` runnera (ADR 0006,
mirror aerodrom#142/#144 `~/projekti/aerodrom/scripts/kb_ingest.py`).

Poziv, ne import: čita `config/kb_ingest.yaml` i pokrene pinovan Spona
`spona-ingest` console script (`uv run spona-ingest`, project dependency,
`spona@v0.1.0`, ADR 0011 §D2 red 7) kao subprocess sa
`--kb-root`/`--validator-script` za izabrani KB. Svi ostali argumenti se
prosleđuju runneru netaknuti (`--dry-run`, `--skip-git`, `--max-batches`, ...).

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
`--no-pr` je project-wrapper režim za orkestrirane lokalne ingest prolaze: posle
obaveznog post-validatora ostavlja izmene u worktree-u bez grane, commita, push-a
ili GitHub poziva. Wrapper ga ne prosleđuje Spona runneru. Codex pozive vodi kroz
project-owned safe launcher (`gpt-5.6-sol`, reasoning `medium`, `workspace-write`,
bez user config/browser/apps/plugins/web/direktne mreže) i posle agenta potvrđuje da symbolic HEAD, HEAD OID, refs i index
nisu promenjeni. Udaljeni side effect ne može naknadno dokazano da se rollbackuje;
zato launcher preventivno uklanja mrežne alate, a batch prompt zabranjuje git/gh.
`--retry-gate B13 --no-pr` je uži oporavak: posle dokazanog exact blocked
boundary-ja pokreće samo domenski semantic gate u read-only Codex sandboxu,
čuva novi artifact/run-log i tek na jednoznačan PASS atomarno menja runner-owned
statusna polja. Nikada ne poziva content ingest prompt niti PR tok.
`--recover-batch B15 --no-pr` je još uži oporavak standardnog batch-a koji je
već stigao do tačnog boundary-ja, ali ga je wrapper blokirao samo zbog očekivane
status/ledger veze. Ne poziva ni content agent ni semantic gate; promocija je
dozvoljena tek kada su redosled, sva tri source boundary-ja i jedini validator
nalaz dokazani, pa se posle upisa ponavlja pun validator i git-state guard.

Tvrdi zahtev: pokretati iz korena wyckoff-ai repoa — runner sidri repo_root, git
provere i rezoluciju `sources:` putanja na cwd.

Pokretanje (iz korena wyckoff-ai repoa):
    uv run python scripts/kb_ingest.py --kb expert-analyses -- --dry-run --skip-git
    uv run python scripts/kb_ingest.py --kb expert-analyses --no-pr -- --max-batches 1
    uv run python scripts/kb_ingest.py --kb expert-analyses --retry-gate B13 --no-pr -- --backend codex --model gpt-5.6-sol --skip-git
    uv run python scripts/kb_ingest.py --kb expert-analyses --recover-batch B15 --no-pr -- --skip-git
    uv run python scripts/kb_ingest.py --kb expert-analyses -- --max-batches 1
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from spona.validated_ingest.adapters import artifacts as spona_artifacts
from spona.validated_ingest.api import AgentResult

# Spona validated-ingest, project dependency (pyproject.toml + uv.lock, ADR 0011 §D2 red 6).
# Module-alias oblik — sve postojeće core.X kvalifikovane reference ostaju nepromenjene
# (ADR 0012 §Šta ovaj ADR ne odlučuje: tačan oblik importa je izvršni detalj Faze 4).
from spona.validated_ingest.core import validator as core
from spona.validated_ingest.core import runner as runner_core

KONFIG_REL = Path("config") / "kb_ingest.yaml"

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
SAFE_CODEX_BIN_REL = Path("scripts") / "codex_ingest_safe.py"


def ucitaj_konfig(repo_root: Path) -> dict:
    konfig_put = repo_root / KONFIG_REL
    with konfig_put.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Pokreni Spona spona-ingest runner nad wyckoff-ai KB-om (poziv, ne import) + PR-tok.",
        epilog="Svi nepoznati argumenti se prosleđuju runneru netaknuti (npr. --dry-run --skip-git --max-batches 1).",
    )
    parser.add_argument(
        "--kb", default="expert-analyses", help="ključ KB-a iz config/kb_ingest.yaml"
    )
    parser.add_argument(
        "--issue",
        default=DEFAULT_ISSUE_NUMBER,
        help=f"issue broj za PR title template (default: {DEFAULT_ISSUE_NUMBER})",
    )
    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="ostavi uspešan ingest kao lokalne izmene; bez grane, commita, push-a i PR-a",
    )
    parser.add_argument(
        "--retry-gate",
        metavar="BATCH_ID",
        help="ponovi samo deklarisanu semantic gate kapiju nad već završenim blocked boundary-jem",
    )
    parser.add_argument(
        "--recover-batch",
        metavar="BATCH_ID",
        help="promoviši standardni blocked batch samo posle dokazanog exact boundary-ja i čistog post-validatora",
    )
    return parser.parse_known_args(argv)


def _load_validator_module(validator_script: Path):
    """Dinamički učitaj validator wrapper — mirror
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
        raise RuntimeError(
            f"validator modul {validator_script} nije učitljiv: {exc}"
        ) from exc
    return module


def _load_profile(validator_script: Path):
    module = _load_validator_module(validator_script)
    profile = getattr(module, "PROFILE", None)
    if profile is None:
        raise RuntimeError(f"{validator_script} ne izlaže PROFILE (CorpusProfile)")
    # `core.CorpusProfile` referencira ISTU klasu kao `spona.validated_ingest.api.CorpusProfile`
    # (jer `spona.validated_ingest.core.validator` je uvozi u sopstveni namespace) — isinstance je
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


@dataclass(frozen=True)
class GitControlState:
    symbolic_head: bytes
    head_oid: bytes
    refs: bytes
    index_entries: bytes


def _git_control_state(cwd: Path) -> GitControlState:
    """Snapshot lokalnog git control-plane-a; working-tree sadržaj je izuzet."""

    def checked_output(args: list[str]) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, check=True
        ).stdout

    symbolic = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "HEAD"],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if symbolic.returncode not in {0, 1}:
        raise RuntimeError(
            f"git symbolic-ref nije uspeo (rc={symbolic.returncode}): "
            + symbolic.stderr.decode(errors="replace").strip()
        )
    return GitControlState(
        symbolic_head=symbolic.stdout,
        head_oid=checked_output(["rev-parse", "--verify", "HEAD"]),
        refs=checked_output(
            ["for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)"]
        ),
        index_entries=checked_output(["ls-files", "--stage", "-z"]),
    )


def _snapshot_batch_statuses(kb_root: Path, validator_script: Path) -> dict[str, str]:
    """`{batch_id: status}` snapshot iz `batches.md` — koristi core `parse_batches`
    + KB-ov sopstveni PROFILE (dinamički učitan)."""
    profile = _load_profile(validator_script)
    batches = core.parse_batches(kb_root, profile)
    return {b.id: b.status for b in batches}


def _snapshot_coverage(kb_root: Path, validator_script: Path) -> dict:
    module = _load_validator_module(validator_script)
    reader = getattr(module, "read_progress_ledger", None)
    if reader is None:
        raise RuntimeError(f"{validator_script} ne izlaže read_progress_ledger")
    return reader(kb_root)


def _snapshot_extracts(kb_root: Path) -> set[str]:
    return {
        path.relative_to(kb_root).as_posix()
        for path in (kb_root / "wiki" / "extracts").glob("*.md")
    }


def _batch_log_cell(kb_root: Path, batch_id: str) -> str:
    header: list[str] | None = None
    log_index: int | None = None
    for line in (kb_root / "batches.md").read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None and any(cell.lower().startswith("batch") for cell in cells):
            header = cells
            log_index = next(
                (index for index, cell in enumerate(cells) if cell.lower() == "log"),
                None,
            )
            continue
        if header and cells and cells[0] == batch_id and log_index is not None:
            return cells[log_index] if log_index < len(cells) else ""
    return ""


def _max_batches_values(passthrough: list[str]) -> list[int]:
    """Vrati sve deklaracije, jer Spona/argparse prihvata poslednju pojavu.

    Wrapper namerno odbija duplikate umesto da dozvoli da bezbedni prvi
    ``--max-batches 1`` prikrije kasniji ``--max-batches 2``.
    """
    values: list[int] = []
    for index, arg in enumerate(passthrough):
        if arg.startswith("--max-batches="):
            values.append(int(arg.split("=", 1)[1]))
        elif arg == "--max-batches":
            if index + 1 >= len(passthrough):
                raise ValueError("--max-batches nema vrednost")
            values.append(int(passthrough[index + 1]))
    return values


def _option_values(passthrough: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, arg in enumerate(passthrough):
        if arg.startswith(option + "="):
            values.append(arg.split("=", 1)[1])
        elif arg == option:
            if index + 1 >= len(passthrough):
                raise ValueError(f"{option} nema vrednost")
            values.append(passthrough[index + 1])
    return values


def _harden_codex_passthrough(passthrough: list[str], cwd: Path) -> list[str]:
    """Nametni project-owned Codex containment kada je aktivni backend Codex."""
    backends = _option_values(passthrough, "--backend")
    if not backends or backends[-1] != "codex":
        return passthrough
    if _option_values(passthrough, "--codex-bin"):
        raise ValueError("--codex-bin override nije dozvoljen za expert ingest")
    if _option_values(passthrough, "--codex-profile"):
        raise ValueError("--codex-profile nije dozvoljen za expert ingest")
    models = _option_values(passthrough, "--model")
    if models != ["gpt-5.6-sol"]:
        raise ValueError(
            "Codex expert ingest zahteva jednu --model gpt-5.6-sol deklaraciju"
        )
    if any("model_reasoning_effort" in arg for arg in passthrough):
        raise ValueError(
            "model_reasoning_effort određuje safe launcher; override nije dozvoljen"
        )
    sandboxes = _option_values(passthrough, "--codex-sandbox")
    if any(value != "workspace-write" for value in sandboxes):
        raise ValueError("Codex sandbox mora biti workspace-write")
    safe_bin = (cwd / SAFE_CODEX_BIN_REL).resolve()
    if not safe_bin.is_file() or not os.access(safe_bin, os.X_OK):
        raise ValueError(f"safe Codex launcher nije izvršan fajl: {safe_bin}")
    return [
        *passthrough,
        "--codex-bin",
        str(safe_bin),
        "--codex-sandbox",
        "workspace-write",
    ]


def _new_gate_attempts(
    run_log_before: str, run_log_after: str
) -> dict[str, tuple[str, str, int]]:
    """Poslednji novi gate pokušaj po batch-u: ``kind, backend, rc``."""
    if run_log_after.startswith(run_log_before):
        new_text = run_log_after[len(run_log_before) :]
    else:
        before_lines = len(run_log_before.splitlines())
        new_text = "\n".join(run_log_after.splitlines()[before_lines:])
    attempts: dict[str, tuple[str, str, int]] = {}
    for line in new_text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 10 or not cells[1].startswith("gate"):
            continue
        try:
            attempts[cells[0]] = (cells[1], cells[2], int(cells[-1]))
        except ValueError:
            continue
    return attempts


GATE_OUTCOME_RE = re.compile(r"(?m)^[ \t]*GATE_OUTCOME:[ \t]*(PASS|FAIL)[ \t]*$")


def _structured_gate_messages(value: object) -> list[str]:
    """Izdvoji samo finalne poruke iz podržanih Claude/Codex JSON formata.

    Ne pretražujemo proizvoljan JSON jer event stream može sadržati originalni
    prompt sa oba tokena. Claude ``--output-format json`` nosi final u
    ``type=result/result``; Codex ``exec --json`` u ``item=agent_message/text``.
    """
    if not isinstance(value, dict):
        return []
    messages: list[str] = []
    if value.get("type") == "result" and isinstance(value.get("result"), str):
        messages.append(value["result"])
    item = value.get("item")
    if (
        isinstance(item, dict)
        and item.get("type") == "agent_message"
        and isinstance(item.get("text"), str)
    ):
        messages.append(item["text"])
    return messages


def _gate_content_outcome(stdout: str) -> str | None:
    """Parsira strogi gate contract; missing/ambiguous izlaz vraća ``None``.

    Finalna poruka mora sadržati tačno jedan marker kao poslednji neprazan red:
    ``GATE_OUTCOME: PASS`` ili ``GATE_OUTCOME: FAIL``. Podržani su plain text,
    Claude JSON objekat i Codex JSONL event stream.
    """
    stripped = stdout.strip()
    if not stripped:
        return None
    messages: list[str] = []
    try:
        messages = _structured_gate_messages(json.loads(stripped))
    except json.JSONDecodeError:
        parsed_jsonl = False
        jsonl_messages: list[str] = []
        for line in stripped.splitlines():
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            parsed_jsonl = True
            jsonl_messages.extend(_structured_gate_messages(parsed))
        messages = jsonl_messages if parsed_jsonl else [stripped]

    matches: list[str] = []
    for message in messages:
        found = list(GATE_OUTCOME_RE.finditer(message))
        if len(found) != 1:
            if found:
                return None
            continue
        if message[found[0].end() :].strip():
            return None
        matches.append(found[0].group(1))
    return matches[0] if len(matches) == 1 else None


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"kb-ingest: {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def _checkout(cwd: Path, branch: str) -> bool:
    return (
        subprocess.run(["git", "checkout", branch], cwd=cwd, check=False).returncode
        == 0
    )


def _post_validate(
    validator: Path, kb_root: Path, cwd: Path, *, skip_git: bool
) -> tuple[int, dict]:
    cmd = [
        "uv",
        "run",
        "python",
        str(validator),
        "--kb-root",
        str(kb_root),
        "--json",
    ]
    if skip_git:
        cmd.append("--skip-git")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "summary": {"fail": 1, "warn": 0},
            "findings": [
                {
                    "severity": "FAIL",
                    "code": "F-POST-VALIDATOR",
                    "message": result.stderr.strip() or "validator nije vratio JSON",
                }
            ],
        }
    return result.returncode, payload


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomarno zameni tekstualni fajl u istom direktorijumu."""
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)


def _write_transition_status(
    kb_root: Path,
    validator_script: Path,
    changed: dict[str, tuple[str, str]],
    *,
    target_status: str,
    reason: str,
) -> None:
    """Kontrolisana statusna korekcija posle wrapper provera.

    Koristi se fail-closed za vraćanje nevalidnog `complete` u `blocked`, kao i
    za jedini bezbedan N→0 izuzetak: promociju Spona `pages_delta=0` blokade tek
    nakon tačnog boundary-ja i čistog post-validatora. Menja samo runner-owned
    progress ćelije ciljnih redova.
    """
    batches_path = kb_root / "batches.md"
    text = batches_path.read_text(encoding="utf-8")
    current = {
        batch.id: batch
        for batch in core.parse_batches(kb_root, _load_profile(validator_script))
    }
    for batch_id, (_before, after) in changed.items():
        if batch_id not in current:
            continue
        batch = current[batch_id]
        text = runner_core.render_batch_progress_update(
            text,
            batch_id,
            status=target_status,
            date_str=datetime.now(timezone.utc).date().isoformat(),
            pages=str(batch.pages or 0),
            remaining="nema"
            if target_status == "complete"
            else (batch.remaining or "scope nije potvrđen"),
            log_note=reason,
        )
    _atomic_write_text(batches_path, text)


def _mark_completed_transitions_blocked(
    kb_root: Path,
    validator_script: Path,
    changed: dict[str, tuple[str, str]],
    *,
    reason: str,
) -> None:
    completed = {
        bid: values for bid, values in changed.items() if values[1] == "complete"
    }
    _write_transition_status(
        kb_root,
        validator_script,
        completed,
        target_status="blocked",
        reason=reason,
    )


def _recover_verified_zero_page_completion(
    *,
    cwd: Path,
    kb_root: Path,
    validator_script: Path,
    pre_statuses: dict[str, str],
    post_statuses: dict[str, str],
    pre_coverage: dict,
    post_coverage: dict,
    pre_extracts: set[str],
    post_extracts: set[str],
    skip_git: bool,
) -> bool:
    """Promoviši Spona `pages_delta=0` blokadu samo za dokazani N→0 batch."""
    batch_id = next(
        (
            bid
            for bid, status in pre_statuses.items()
            if status in {"pending", "partial"}
        ),
        None,
    )
    if batch_id is None or post_statuses.get(batch_id) != "blocked":
        return False
    status_changes = {
        bid
        for bid in set(pre_statuses) | set(post_statuses)
        if pre_statuses.get(bid) != post_statuses.get(bid)
    }
    if status_changes != {batch_id}:
        return False
    ordered_statuses = list(pre_statuses.items())
    first_noncomplete = next(
        (
            index
            for index, (_bid, status) in enumerate(ordered_statuses)
            if status != "complete"
        ),
        len(ordered_statuses),
    )
    if (
        first_noncomplete >= len(ordered_statuses)
        or ordered_statuses[first_noncomplete][0] != batch_id
        or any(
            status == "complete"
            for _bid, status in ordered_statuses[first_noncomplete + 1 :]
        )
    ):
        return False
    if "pages_delta=0" not in _batch_log_cell(kb_root, batch_id):
        return False

    module = _load_validator_module(validator_script)
    boundary = getattr(module, "expected_batch_boundary", None)
    if boundary is None:
        return False
    source, expected_reviewed, expected_last = boundary(cwd, batch_id)
    before = pre_coverage.get(source)
    after = post_coverage.get(source)
    if before is None or after is None:
        return False
    if set(pre_coverage) != set(post_coverage) or any(
        pre_coverage[name] != post_coverage[name]
        for name in pre_coverage
        if name != source
    ):
        return False
    if any(
        before.get(field) != after.get(field)
        for field in set(before) | set(after)
        if field not in {"reviewed", "valid", "rejected", "paywalled", "last_reviewed"}
    ):
        return False
    reviewed_delta = int(after["reviewed"]) - int(before["reviewed"])
    rejected_delta = int(after["rejected"]) - int(before["rejected"])
    paywalled_delta = int(after["paywalled"]) - int(before["paywalled"])
    valid_delta = int(after["valid"]) - int(before["valid"])
    if not (
        reviewed_delta > 0
        and int(after["reviewed"]) == expected_reviewed
        and str(after["last_reviewed"]) == expected_last
        and valid_delta == 0
        and rejected_delta >= 0
        and paywalled_delta >= 0
        and rejected_delta + paywalled_delta == reviewed_delta
        and pre_extracts == post_extracts
    ):
        return False

    transition = {batch_id: (pre_statuses[batch_id], "blocked")}
    _write_transition_status(
        kb_root,
        validator_script,
        transition,
        target_status="complete",
        reason="verified N→0 batch: svi dokumenti rejected/paywalled; validator post-gate",
    )
    post_rc, payload = _post_validate(validator_script, kb_root, cwd, skip_git=skip_git)
    if post_rc == 0 and int((payload.get("summary") or {}).get("fail", 0)) == 0:
        return True

    _write_transition_status(
        kb_root,
        validator_script,
        {batch_id: (pre_statuses[batch_id], "complete")},
        target_status="blocked",
        reason="N→0 recovery post-validator nije prošao",
    )
    return False


def _failed_required_gates(
    kb_root: Path,
    changed: dict[str, tuple[str, str]],
    run_log_before: str,
) -> set[str]:
    batches_text = (kb_root / "batches.md").read_text(encoding="utf-8")
    run_log_path = kb_root / "run-log.md"
    run_log_after = (
        run_log_path.read_text(encoding="utf-8") if run_log_path.exists() else ""
    )
    attempts = _new_gate_attempts(run_log_before, run_log_after)
    failed: set[str] = set()
    for batch_id, (_before, after) in changed.items():
        if after != "complete":
            continue
        gate = runner_core.resolve_gate_type(
            runner_core.extract_batch_gate(batches_text, batch_id)
        )
        if not gate:
            continue
        attempt = attempts.get(batch_id)
        if attempt is None:
            failed.add(batch_id)
            continue
        kind, backend, rc = attempt
        if rc != 0 or not re.fullmatch(r"[A-Za-z0-9_.-]+", kind + backend):
            failed.add(batch_id)
            continue
        artifact = kb_root / "logs" / f"{batch_id}-{kind}-{backend}.json"
        try:
            stdout = artifact.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            failed.add(batch_id)
            continue
        if _gate_content_outcome(stdout) != "PASS":
            failed.add(batch_id)
    return failed


@dataclass(frozen=True)
class RetryGateContext:
    batch_id: str
    prompt: str
    pages: int


@dataclass(frozen=True)
class RecoverBatchContext:
    batch_id: str
    pages: int


def _recover_batch_passthrough(passthrough: list[str]) -> bool:
    """Recovery bez agenta prihvata samo jednu opcionu `--skip-git` deklaraciju."""
    if not passthrough:
        return False
    if passthrough == ["--skip-git"]:
        return True
    raise ValueError("batch recovery prihvata samo opciono --skip-git")


def _standard_blocked_recovery_preflight(
    *,
    cwd: Path,
    kb_root: Path,
    validator_script: Path,
    batch_id: str,
    skip_git: bool,
) -> RecoverBatchContext:
    """Dokaži da je standardni batch blokiran samo status/ledger coupling-om."""
    module = _load_validator_module(validator_script)
    profile = _load_profile(validator_script)
    batches = core.parse_batches(kb_root, profile)
    positions = {batch.id: index for index, batch in enumerate(batches)}
    if batch_id not in positions:
        raise RuntimeError(f"nepoznat batch za recovery: {batch_id}")
    target_index = positions[batch_id]
    target = batches[target_index]
    batches_text = (kb_root / "batches.md").read_text(encoding="utf-8")
    gate_type = runner_core.resolve_gate_type(
        runner_core.extract_batch_gate(batches_text, batch_id)
    )
    if gate_type:
        raise RuntimeError(
            f"{batch_id} ima deklarisanu posebnu kapiju; koristi --retry-gate"
        )
    if target.status != "blocked":
        raise RuntimeError(f"{batch_id} mora biti blocked za batch recovery")
    if target.pages is None or target.pages <= 0:
        raise RuntimeError(
            f"{batch_id}: standardni recovery zahteva sadržajne wiki stranice"
        )
    if not re.search(
        r"\bvalidator\s+FAIL=1\s+WARN=0\b", _batch_log_cell(kb_root, batch_id), re.I
    ):
        raise RuntimeError(
            f"{batch_id}: log ne dokazuje jedinu validator FAIL=1/WARN=0 blokadu"
        )
    if any(batch.status != "complete" for batch in batches[:target_index]):
        raise RuntimeError(f"{batch_id}: svi raniji batch-evi moraju biti complete")
    if any(batch.status != "pending" for batch in batches[target_index + 1 :]):
        raise RuntimeError(f"{batch_id}: kasniji batch/source napredak nije dozvoljen")

    boundary = getattr(module, "expected_batch_boundary", None)
    counts = getattr(module, "BATCH_COMPLETION_COUNTS", None)
    ordered_paths = getattr(module, "_ordered_source_paths", None)
    if boundary is None or not isinstance(counts, dict) or ordered_paths is None:
        raise RuntimeError("validator ne izlaže deterministic batch boundary ugovor")
    if any(batch.id not in counts for batch in batches[: target_index + 1]):
        raise RuntimeError("batch schedule sadrži red bez kanonskog boundary ugovora")
    target_source, target_reviewed, target_last = boundary(cwd, batch_id)
    expected_by_source = {"book": 0, "crypto": 0, "fraser": 0}
    for batch in batches[:target_index]:
        source, reviewed = counts[batch.id]
        expected_by_source[source] = max(expected_by_source[source], reviewed)
    expected_by_source[target_source] = target_reviewed

    coverage = _snapshot_coverage(kb_root, validator_script)
    if set(coverage) != set(expected_by_source):
        raise RuntimeError("coverage ledger nema tačno book/crypto/fraser redove")
    for source, expected_reviewed in expected_by_source.items():
        row = coverage[source]
        expected_last = (
            "—"
            if expected_reviewed == 0
            else ordered_paths(cwd, source)[expected_reviewed - 1]
        )
        if source == target_source:
            expected_last = target_last
        if (
            int(row["reviewed"]) != expected_reviewed
            or str(row["last_reviewed"]) != expected_last
        ):
            raise RuntimeError(
                f"{batch_id}: {source} ledger nije na tačnom dozvoljenom boundary-ju"
            )

    val_rc, payload = _post_validate(validator_script, kb_root, cwd, skip_git=skip_git)
    findings = payload.get("findings") or []
    summary = payload.get("summary") or {}
    expected_coupling = (
        val_rc != 0
        and int(summary.get("fail", 0)) == 1
        and int(summary.get("warn", 0)) == 0
        and len(findings) == 1
        and findings[0].get("severity") in {None, "FAIL"}
        and findings[0].get("code") == "F-BATCH-SCOPE-INCOMPLETE"
        and str(findings[0].get("location", "")).startswith("_progress.md")
        and target_source in str(findings[0].get("message", ""))
    )
    if not expected_coupling:
        raise RuntimeError(
            f"{batch_id}: validator ima nalaze van očekivanog blocked/status scope coupling-a"
        )
    return RecoverBatchContext(batch_id=batch_id, pages=target.pages)


def _run_standard_blocked_recovery(
    *,
    cwd: Path,
    kb_root: Path,
    validator_script: Path,
    batch_id: str,
    skip_git: bool,
) -> int:
    """Promoviši već validiran standardni boundary bez content/model poziva."""
    try:
        _standard_blocked_recovery_preflight(
            cwd=cwd,
            kb_root=kb_root,
            validator_script=validator_script,
            batch_id=batch_id,
            skip_git=skip_git,
        )
        git_before = _git_control_state(cwd)
        statuses_before = _snapshot_batch_statuses(kb_root, validator_script)
        coverage_before = _snapshot_coverage(kb_root, validator_script)
        extracts_before = _snapshot_extracts(kb_root)
        batches_path = kb_root / "batches.md"
        batches_before = batches_path.read_text(encoding="utf-8")
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        print(f"kb-ingest batch recovery preflight: {exc}", file=sys.stderr)
        return 2

    transition = {batch_id: ("blocked", "blocked")}
    _write_transition_status(
        kb_root,
        validator_script,
        transition,
        target_status="complete",
        reason="verified standard blocked boundary recovery",
    )
    batches_after_owned = batches_path.read_text(encoding="utf-8")
    try:
        post_rc, payload = _post_validate(
            validator_script, kb_root, cwd, skip_git=skip_git
        )
        post_fail = int((payload.get("summary") or {}).get("fail", 0))
        statuses_after = _snapshot_batch_statuses(kb_root, validator_script)
        expected_statuses = {**statuses_before, batch_id: "complete"}
        unchanged = (
            post_rc == 0
            and post_fail == 0
            and _git_control_state(cwd) == git_before
            and statuses_after == expected_statuses
            and _snapshot_coverage(kb_root, validator_script) == coverage_before
            and _snapshot_extracts(kb_root) == extracts_before
            and batches_path.read_text(encoding="utf-8") == batches_after_owned
        )
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError):
        unchanged = False
    if not unchanged:
        if batches_path.read_text(encoding="utf-8") == batches_after_owned:
            _atomic_write_text(batches_path, batches_before)
        else:
            _write_transition_status(
                kb_root,
                validator_script,
                {batch_id: ("blocked", "complete")},
                target_status="blocked",
                reason="standard recovery post-validator/state guard nije prošao",
            )
        print(
            f"kb-ingest batch recovery {batch_id}: post-validator/state guard FAIL; batch je blocked.",
            file=sys.stderr,
        )
        return 1
    print(
        f"kb-ingest batch recovery {batch_id}: PASS; batch je complete, bez model/PR toka."
    )
    return 0


def _retry_gate_passthrough(passthrough: list[str]) -> tuple[bool, int]:
    """Dozvoli samo Codex/model/timeout/skip-git opcije za gate-only put."""
    allowed_with_value = {"--backend", "--model", "--timeout"}
    skip_git = False
    timeout = 3600
    index = 0
    while index < len(passthrough):
        arg = passthrough[index]
        if arg == "--skip-git":
            if skip_git:
                raise ValueError("--skip-git duplikat nije dozvoljen")
            skip_git = True
            index += 1
            continue
        matched = next(
            (option for option in allowed_with_value if arg.startswith(option + "=")),
            None,
        )
        if matched:
            value = arg.split("=", 1)[1]
            if matched == "--timeout":
                timeout = int(value)
            index += 1
            continue
        if arg in allowed_with_value:
            if index + 1 >= len(passthrough):
                raise ValueError(f"{arg} nema vrednost")
            if arg == "--timeout":
                timeout = int(passthrough[index + 1])
            index += 2
            continue
        raise ValueError(f"gate-only retry ne prihvata argument: {arg}")
    if timeout <= 0:
        raise ValueError("--timeout mora biti pozitivan")
    if _option_values(passthrough, "--backend") != ["codex"]:
        raise ValueError("gate-only retry zahteva jednu --backend codex deklaraciju")
    if _option_values(passthrough, "--model") != ["gpt-5.6-sol"]:
        raise ValueError(
            "gate-only retry zahteva jednu --model gpt-5.6-sol deklaraciju"
        )
    if len(_option_values(passthrough, "--timeout")) > 1:
        raise ValueError("--timeout duplikat nije dozvoljen")
    return skip_git, timeout


def _required_gate_retry_preflight(
    *,
    cwd: Path,
    kb_root: Path,
    validator_script: Path,
    batch_id: str,
    skip_git: bool,
) -> RetryGateContext:
    """Dokaži da je jedina blokada targetova već završena semantic kapija."""
    module = _load_validator_module(validator_script)
    profile = _load_profile(validator_script)
    batches = core.parse_batches(kb_root, profile)
    positions = {batch.id: index for index, batch in enumerate(batches)}
    if batch_id not in positions:
        raise RuntimeError(f"nepoznat batch za gate retry: {batch_id}")
    target_index = positions[batch_id]
    target = batches[target_index]
    batches_text = (kb_root / "batches.md").read_text(encoding="utf-8")
    gate_type = runner_core.resolve_gate_type(
        runner_core.extract_batch_gate(batches_text, batch_id)
    )
    if not gate_type or "semantic-lint" not in gate_type:
        raise RuntimeError(f"{batch_id} nema deklarisanu semantic-lint kapiju")
    if target.status != "blocked":
        raise RuntimeError(f"{batch_id} mora biti blocked za gate-only retry")
    if any(batch.status != "complete" for batch in batches[:target_index]):
        raise RuntimeError(f"{batch_id}: svi raniji batch-evi moraju biti complete")
    if any(batch.status != "pending" for batch in batches[target_index + 1 :]):
        raise RuntimeError(f"{batch_id}: kasniji batch/source napredak nije dozvoljen")

    boundary = getattr(module, "expected_batch_boundary", None)
    counts = getattr(module, "BATCH_COMPLETION_COUNTS", None)
    ordered_paths = getattr(module, "_ordered_source_paths", None)
    if boundary is None or not isinstance(counts, dict) or ordered_paths is None:
        raise RuntimeError("validator ne izlaže deterministic batch boundary ugovor")
    target_source, target_reviewed, target_last = boundary(cwd, batch_id)
    expected_by_source = {"book": 0, "crypto": 0, "fraser": 0}
    for batch in batches[:target_index]:
        if batch.id in counts:
            source, reviewed = counts[batch.id]
            expected_by_source[source] = max(expected_by_source[source], reviewed)
    expected_by_source[target_source] = target_reviewed

    coverage = _snapshot_coverage(kb_root, validator_script)
    if set(coverage) != set(expected_by_source):
        raise RuntimeError("coverage ledger nema tačno book/crypto/fraser redove")
    for source, expected_reviewed in expected_by_source.items():
        row = coverage[source]
        expected_last = (
            "—"
            if expected_reviewed == 0
            else ordered_paths(cwd, source)[expected_reviewed - 1]
        )
        if source == target_source:
            expected_last = target_last
        if (
            int(row["reviewed"]) != expected_reviewed
            or str(row["last_reviewed"]) != expected_last
        ):
            raise RuntimeError(
                f"{batch_id}: {source} ledger nije na tačnom dozvoljenom boundary-ju"
            )

    val_rc, payload = _post_validate(validator_script, kb_root, cwd, skip_git=skip_git)
    findings = payload.get("findings") or []
    summary = payload.get("summary") or {}
    expected_coupling = (
        val_rc != 0
        and int(summary.get("fail", 0)) == 1
        and int(summary.get("warn", 0)) == 0
        and len(findings) == 1
        and findings[0].get("code") == "F-BATCH-SCOPE-INCOMPLETE"
        and str(findings[0].get("location", "")).startswith("_progress.md")
        and target_source in str(findings[0].get("message", ""))
    )
    if not expected_coupling:
        raise RuntimeError(
            f"{batch_id}: validator ima nalaze van očekivanog blocked/status scope coupling-a"
        )
    prompt = runner_core.build_gate_prompt(batch_id, gate_type, kb_root, profile)
    return RetryGateContext(batch_id=batch_id, prompt=prompt, pages=target.pages or 0)


def _invoke_safe_retry_gate(*, cwd: Path, prompt: str, timeout: int) -> AgentResult:
    safe_bin = (cwd / SAFE_CODEX_BIN_REL).resolve()
    command = [
        str(safe_bin),
        "exec",
        "--json",
        "-C",
        str(cwd),
        "--sandbox",
        "read-only",
        "--model",
        "gpt-5.6-sol",
        prompt,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return AgentResult(result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return AgentResult(124, stdout, stderr or "gate retry timeout")


def _run_required_gate_retry(
    *,
    cwd: Path,
    kb_root: Path,
    validator_script: Path,
    batch_id: str,
    skip_git: bool,
    timeout: int,
) -> int:
    try:
        context = _required_gate_retry_preflight(
            cwd=cwd,
            kb_root=kb_root,
            validator_script=validator_script,
            batch_id=batch_id,
            skip_git=skip_git,
        )
        git_before = _git_control_state(cwd)
        statuses_before = _snapshot_batch_statuses(kb_root, validator_script)
        coverage_before = _snapshot_coverage(kb_root, validator_script)
        extracts_before = _snapshot_extracts(kb_root)
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"kb-ingest gate retry preflight: {exc}", file=sys.stderr)
        return 2

    result = _invoke_safe_retry_gate(cwd=cwd, prompt=context.prompt, timeout=timeout)
    kind = "gate-retry-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    spona_artifacts.save_agent_stdout(kb_root, batch_id, kind, "codex", result.stdout)
    spona_artifacts.append_run_log(
        kb_root,
        batch_id=batch_id,
        kind=kind,
        backend="codex",
        model="gpt-5.6-sol",
        usage=runner_core.extract_usage(result.stdout, "codex"),
        wall_seconds=0,
        rc=result.returncode,
    )

    try:
        unchanged = (
            _git_control_state(cwd) == git_before
            and _snapshot_batch_statuses(kb_root, validator_script) == statuses_before
            and _snapshot_coverage(kb_root, validator_script) == coverage_before
            and _snapshot_extracts(kb_root) == extracts_before
        )
    except (OSError, subprocess.CalledProcessError, RuntimeError):
        unchanged = False
    outcome = _gate_content_outcome(result.stdout)
    if result.returncode != 0 or outcome != "PASS" or not unchanged:
        print(
            f"kb-ingest gate retry {batch_id}: FAIL/missing ili state mutation; batch ostaje blocked.",
            file=sys.stderr,
        )
        return 1

    transition = {batch_id: ("blocked", "blocked")}
    _write_transition_status(
        kb_root,
        validator_script,
        transition,
        target_status="complete",
        reason="semantic gate retry GATE_OUTCOME: PASS",
    )
    try:
        post_rc, payload = _post_validate(
            validator_script, kb_root, cwd, skip_git=skip_git
        )
        post_fail = int((payload.get("summary") or {}).get("fail", 0))
    except Exception as exc:  # status je promovisan; obavezno ga vrati u blocked
        post_rc, post_fail = 1, 1
        print(f"kb-ingest gate retry post-validator greška: {exc}", file=sys.stderr)
    try:
        git_unchanged = _git_control_state(cwd) == git_before
    except (OSError, subprocess.CalledProcessError, RuntimeError):
        git_unchanged = False
    if post_rc != 0 or post_fail or not git_unchanged:
        _write_transition_status(
            kb_root,
            validator_script,
            {batch_id: ("blocked", "complete")},
            target_status="blocked",
            reason="semantic gate retry post-validator/git guard nije prošao",
        )
        print(
            f"kb-ingest gate retry {batch_id}: post-validator/git guard FAIL; batch vraćen na blocked.",
            file=sys.stderr,
        )
        return 1
    print(f"kb-ingest gate retry {batch_id}: PASS; batch je complete, bez PR toka.")
    return 0


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
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=cwd, check=False
    )

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
        if (
            subprocess.run(
                ["git", "branch", "-D", branch], cwd=cwd, check=False
            ).returncode
            != 0
        ):
            print(
                f"kb-ingest UPOZORENJE: brisanje prazne grane '{branch}' nije uspelo — obriši ručno.",
                file=sys.stderr,
            )
        return 0

    commit_title = f"#{issue} Wiki ingest (research/expert-analyses, {scope})"
    commit_body_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False
        ) as commit_body_file:
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
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False
        ) as pr_body_file:
            pr_body_file.write(
                f"## Sažetak\n\nRunner batch ingest: {scope} (`research/expert-analyses`).\n\n"
            )
            pr_body_file.write("## Batch-evi\n\n")
            for bid in batch_ids:
                before, after = changed[bid]
                pr_body_file.write(f"- `{bid}`: `{before}` -> `{after}`\n")
            pr_body_file.write("\n🤖 Otvoreno preko `scripts/kb_ingest.py`.\n")
            pr_body_path = pr_body_file.name
        gh_result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                commit_title,
                "--body-file",
                pr_body_path,
            ],
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
            f'Otvori PR ručno (gh pr create --title "{commit_title}" --base {original_branch} '
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

    passthrough = list(runner_args)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    is_dry_run = "--dry-run" in passthrough
    is_gate_retry = args.retry_gate is not None
    is_batch_recovery = args.recover_batch is not None

    if is_gate_retry and is_batch_recovery:
        print(
            "greška: --retry-gate i --recover-batch su međusobno isključivi",
            file=sys.stderr,
        )
        return 2

    if not is_dry_run and not is_gate_retry and not is_batch_recovery:
        try:
            max_batches_values = _max_batches_values(passthrough)
        except ValueError as exc:
            print(f"greška: neispravan --max-batches: {exc}", file=sys.stderr)
            return 2
        if max_batches_values != [1]:
            print(
                "greška: realan expert ingest zahteva jednu jedinu deklaraciju "
                "'--max-batches 1' da bi wrapper proverio batch/gate pre prelaska "
                "na sledeći izvor; duplikati nisu dozvoljeni",
                file=sys.stderr,
            )
            return 2

    if is_batch_recovery:
        if is_dry_run:
            print("greška: --recover-batch nema dry-run režim", file=sys.stderr)
            return 2
        if not args.no_pr:
            print("greška: --recover-batch zahteva --no-pr", file=sys.stderr)
            return 2
        try:
            skip_git = _recover_batch_passthrough(passthrough)
            branch = _current_branch(cwd)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"greška: batch recovery argument/preflight: {exc}", file=sys.stderr)
            return 2
        if INGEST_BRANCH_RE.match(branch):
            print(
                f"greška: batch recovery nije dozvoljen sa wrapper-owned grane '{branch}'",
                file=sys.stderr,
            )
            return 2
        return _run_standard_blocked_recovery(
            cwd=cwd,
            kb_root=kb_root,
            validator_script=validator,
            batch_id=args.recover_batch,
            skip_git=skip_git,
        )

    try:
        hardened_passthrough = _harden_codex_passthrough(passthrough, cwd)
    except ValueError as exc:
        print(f"greška: nebezbedan Codex ingest poziv: {exc}", file=sys.stderr)
        return 2

    if is_gate_retry:
        if is_dry_run:
            print("greška: --retry-gate nema dry-run režim", file=sys.stderr)
            return 2
        if not args.no_pr:
            print("greška: --retry-gate zahteva --no-pr", file=sys.stderr)
            return 2
        try:
            skip_git, timeout = _retry_gate_passthrough(passthrough)
            branch = _current_branch(cwd)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"greška: gate retry argument/preflight: {exc}", file=sys.stderr)
            return 2
        if INGEST_BRANCH_RE.match(branch):
            print(
                f"greška: gate retry nije dozvoljen sa wrapper-owned grane '{branch}'",
                file=sys.stderr,
            )
            return 2
        return _run_required_gate_retry(
            cwd=cwd,
            kb_root=kb_root,
            validator_script=validator,
            batch_id=args.retry_gate,
            skip_git=skip_git,
            timeout=timeout,
        )

    passthrough = hardened_passthrough

    cmd = [
        "uv",
        "run",
        "spona-ingest",
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
        git_control_before = _git_control_state(cwd)
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"greška: ne mogu snimiti pre-run git stanje: {exc}", file=sys.stderr)
        return 2

    try:
        pre_snapshot = _snapshot_batch_statuses(kb_root, validator)
        blocked = [bid for bid, status in pre_snapshot.items() if status == "blocked"]
        if blocked:
            print(
                "greška: blocked batch zahteva disposition/reset pre novog autonomnog rada: "
                + ", ".join(blocked),
                file=sys.stderr,
            )
            return 2
        pre_coverage = _snapshot_coverage(kb_root, validator)
        pre_extracts = _snapshot_extracts(kb_root)
        run_log_path = kb_root / "run-log.md"
        run_log_before = (
            run_log_path.read_text(encoding="utf-8") if run_log_path.exists() else ""
        )
    except RuntimeError as exc:
        print(f"greška: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 2

    rc = _run(cmd, cwd)
    try:
        git_control_after = _git_control_state(cwd)
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"greška: ne mogu potvrditi post-run git stanje: {exc}", file=sys.stderr)
        return 1
    if git_control_after != git_control_before:
        print(
            "kb-ingest: agent je promenio lokalni git branch/HEAD/refs/index; "
            "run je fail-closed zaustavljen pre PR toka. Pregledaj i ručno vrati git stanje.",
            file=sys.stderr,
        )
        return 1
    try:
        post_snapshot = _snapshot_batch_statuses(kb_root, validator)
        post_coverage = _snapshot_coverage(kb_root, validator)
        post_extracts = _snapshot_extracts(kb_root)
    except RuntimeError as exc:
        print(
            f"greška: runner je završio sa rc={rc}, ali post-snapshot nije uspeo: {exc}\n"
            f"{traceback.format_exc()}",
            file=sys.stderr,
        )
        return 2

    if rc != 0:
        recovered = _recover_verified_zero_page_completion(
            cwd=cwd,
            kb_root=kb_root,
            validator_script=validator,
            pre_statuses=pre_snapshot,
            post_statuses=post_snapshot,
            pre_coverage=pre_coverage,
            post_coverage=post_coverage,
            pre_extracts=pre_extracts,
            post_extracts=post_extracts,
            skip_git="--skip-git" in passthrough,
        )
        if not recovered:
            print(
                f"kb-ingest: runner rc={rc}; N→0 safe-completion uslovi nisu dokazani — bez PR toka.",
                file=sys.stderr,
            )
            return rc
        post_snapshot = _snapshot_batch_statuses(kb_root, validator)
        print(
            "kb-ingest: verifikovan N→0 all-rejected/paywalled batch promovisan je u complete."
        )

    changed = {
        bid: (pre_snapshot.get(bid, "?"), post_status)
        for bid, post_status in post_snapshot.items()
        if pre_snapshot.get(bid) != post_status
    }

    failed_gates = _failed_required_gates(kb_root, changed, run_log_before)
    if failed_gates:
        failed_transitions = {bid: changed[bid] for bid in failed_gates}
        _mark_completed_transitions_blocked(
            kb_root,
            validator,
            failed_transitions,
            reason="semantic gate nema jednoznačan sadržajni PASS uz rc=0",
        )
        print(
            "kb-ingest: semantic gate FAIL/missing za "
            + ", ".join(sorted(failed_gates))
            + " — batch je blocked; sledeći izvor neće biti pokrenut.",
            file=sys.stderr,
        )
        return 1

    post_rc, post_payload = _post_validate(
        validator,
        kb_root,
        cwd,
        skip_git="--skip-git" in passthrough,
    )
    post_fail = int((post_payload.get("summary") or {}).get("fail", 0))
    if post_rc != 0 or post_fail:
        reason = f"post-validator FAIL={post_fail}; kanonski scope nije potvrđen"
        _mark_completed_transitions_blocked(
            kb_root,
            validator,
            changed,
            reason=reason,
        )
        print(
            f"kb-ingest: {reason} — promenjeni complete redovi vraćeni su na blocked; bez PR toka.",
            file=sys.stderr,
        )
        return 1

    if args.no_pr:
        print(
            "kb-ingest: --no-pr — validirane izmene ostaju lokalno, bez git/GitHub operacija."
        )
        return 0

    try:
        return _open_pr_for_batches(
            cwd=cwd,
            kb_root_rel=kb_unos["kb_root"],
            issue=args.issue,
            changed=changed,
            original_branch=original_branch,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"greška u grana/PR toku: {exc}\n{traceback.format_exc()}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
