# Feature: Codex filesystem izolacija za privatni benchmark

## Summary

Issue [#82](https://github.com/ssmiljanicc/wyckoff-ai/issues/82) vraća Codex analyst u Faza 4 privatni benchmark tako što ga izvršava u namenskom, spolja ograničenom Docker kontejneru. Kontejner vidi samo kopiju case root-a i read-only (samo za čitanje) auth secret; privatni answer key, repo root i ostali host fajlovi nisu mount-ovani. I canary i pravi benchmark prolaze kroz isti `CODEX_EXECUTION_PROFILE`, a PASS verdict se vezuje za wrapper, Codex CLI verziju, host platformu i stvarni Docker image identitet.

Plan ne menja scoring, judge dimenzije niti `chart_image` ugovor. Posle offline testova traži se pregled dry-run izlaza, jedan operator-odobreni plaćeni isolation canary i tek zatim mali upareni Claude/Codex benchmark. Puna model × effort matrica ostaje van obima.

## User Story

Kao operator privatnog Wyckoff benchmark-a,
želim da Codex analyst radi u dokazanoj filesystem izolaciji,
kako bih dobio verodostojno Claude/Codex rangiranje bez mogućnosti čitanja answer key-a.

## Problem Statement

Codex CLI `0.141.0` na Darwin/Seatbelt platformi, pokrenut sa `--sandbox read-only --cd <case-root>`, uspešno je pročitao sentinel van case root-a. `--cd` bira radni direktorijum, ali nije granica čitanja. Zbog toga `CodexRuntimeAdapter.preflight` trenutno ispravno radi fail-closed (bezbedno zatvaranje — odbija izvršenje kada dokaz nedostaje), pa cross-provider rangiranje nije dostupno.

Postojeći PR #81 već daje dobru osnovu: canary i adapter dele profil, verdict je vezan za fingerprint profila, a verzija/platforma se proveravaju. Nedostaje stvarni containment i nekoliko pratećih detalja:

- slepo prepend-ovanje `wrapper_argv` ne može da prevede host putanje u kontejnerske putanje i napravi tačno određene mount-ove;
- preflight (`--version`, `exec --help`, `login status`) trenutno zaobilazi wrapper i ispituje host Codex;
- verdict poznaje host platformu i statički profil, ali ne stvarni Docker image ID/digest;
- canary i benchmark root-ovi moraju ostati čitljivi unutar kontejnera bez izlaganja host direktorijuma van eksplicitnog case mount-a.

## Solution Statement

Dodati mali Python launcher `scripts/eval/codex_container.py` i minimalan, verzijski pinovan Codex image. Launcher prima postojeći Codex argv, validira i prevodi sve file argumente iz host case root-a u `/workspace`, pa izvršava jednokratan Docker container sa:

- samo `/workspace` case bind mount-om u read-only režimu;
- auth fajlom kao read-only secret mount-om, kopiranim pri startu u efemerni `CODEX_HOME` na `tmpfs`;
- read-only root filesystem-om, `--cap-drop ALL` i `no-new-privileges`;
- bez `--privileged`, host PID/network namespace-a ili Docker socket mount-a;
- Codex flagom `--dangerously-bypass-approvals-and-sandbox`, jer je bezbednosna granica spoljašnji kontejner, ne ugrađeni Seatbelt profil;
- JSONL stdout/stderr i exit code prosleđenim bez izmene.

`CODEX_EXECUTION_PROFILE` ostaje jedini izvor istine i dobija wrapper argv, containment labelu, pinovani image ref i očekivani container workspace. Zajednički builder koriste canary, runtime, version/capability/auth preflight i execution-identity probe. Verdict beleži i proverava image ID/digest, container OS/architecture i Codex verziju dobijenu kroz wrapper. Time rebuild pod istim lokalnim tagom takođe poništava stari PASS.

## Metadata

| Polje | Vrednost |
| --- | --- |
| Izvor | GitHub issue #82 + jedini komentar operatora |
| Tip | `ENHANCEMENT` (bezbednosna infrastruktura) |
| Složenost | `HIGH` |
| Platforma za v1 | macOS host + Docker Desktop Linux `aarch64` container |
| Lokalno provereno | Codex CLI `0.141.0`; Docker client/server `28.0.4`; Docker Desktop `aarch64` |
| Canonical output | `PRPs/plans/codex-filesystem-isolation-private-benchmark.plan.md` |
| Implementacija | Nije deo ovog planiranja |

Složenost je visoka jer isti sigurnosni identitet mora važiti kroz četiri puta: canary, adapter execution, preflight i persisted verdict. Greška u bilo kom od njih može dati lažni PASS ili autorizovati drugi runtime.

## UX Design

### Pre

```text
operator
  -> orchestrator --model codex
     -> host codex --sandbox read-only --cd /tmp/case
        -> host filesystem je široko čitljiv
        -> /private/answers/... može biti pročitan
     -> nema PASS verdicta
     -> preflight: Codex unavailable (fail-closed)
```

### Posle

```text
operator
  -> build/inspect pinovani Codex image
  -> canary dry-run (nema model poziva)
  -> canary --confirm (jedan odobreni poziv)
     -> shared CODEX_EXECUTION_PROFILE
        -> Docker launcher
           mounts: case -> /workspace:ro
                   auth -> /run/secrets/codex-auth:ro
           ne mounts: answer key, repo, host HOME, Docker socket
        -> outside /bin/cat pokušaj: non-zero, sentinel ne curi
     -> PASS verdict: CLI + host platform + profile + image identity
  -> orchestrator preflight kroz isti launcher
     -> matching PASS: Codex enabled
     -> mismatch/stale/missing: Codex unavailable
  -> mali Claude/Codex paired canary
  -> cross-provider rezultat ponovo postoji
```

### Promene interakcije

| Lokacija | Pre | Posle | Uticaj na operatora |
| --- | --- | --- | --- |
| Codex preflight | Host binary + host auth | Containerized version/help/auth kroz shared profil | Provera odgovara runtime-u koji će stvarno raditi |
| Isolation canary | Host Seatbelt, očekivani FAIL | Docker allowlist mount granica, očekivani PASS | Jedan plaćeni poziv posle obaveznog preview-a |
| Verdict | Host platform + CLI + statički profile hash | Isto plus container OS/arch i nepromenljivi image ID/digest | Rebuild ili promena image-a automatski obara PASS |
| Benchmark | Codex označen `unavailable` | Codex analyst radi samo uz matching PASS | Vraćeno Claude/Codex rangiranje |

## Mandatory Reading

### Repo izvori

- `CLAUDE.md:1-81` — jezik, review i planska pravila.
- `scripts/eval/isolation_state.py:1-185` — trenutni verdict ugovor, `CODEX_EXECUTION_PROFILE` i fail-closed validacija.
- `scripts/eval/runtime_adapters.py:81-134,196-268` — subprocess, preflight i Codex argv/parser tok.
- `scripts/eval/canary_codex_image.py:40-169` — shared profile, sentinel konstrukcija i PASS zapis.
- `scripts/eval/canary_common.py:137-176` — terminalni command event i blocked-read dokaz.
- `scripts/eval/orchestrator.py:179-209,270-318,334-386` — temp root, analyst/judge razdvajanje i preflight orchestration.
- `tests/test_isolation_state.py:32-113`, `tests/test_runtime_adapters.py:34-216`, `tests/test_image_canaries.py:35-153` — postojeći test stil i security regresije.
- `runbooks/faza-4-eval-orchestrator.md:5-21,23-68,90-101` — operator workflow i trenutno empirijski pali Codex status.
- `PRPs/reports/spike-75-chart-image-isolacija-report.md:77-122` — empirijski nalaz i granice spike-a.
- `PRPs/reviews/pr-81-review.md:31-72` — nalaz koji je doveo do profile fingerprint povezivanja.

### Zvanična dokumentacija

- [OpenAI Codex CLI reference — global flags](https://developers.openai.com/codex/cli/reference#global-flags)
  - `KEY_INSIGHT`: `--cd` samo postavlja working directory; `--dangerously-bypass-approvals-and-sandbox` je dozvoljen isključivo u spolja ojačanom okruženju.
  - `APPLIES_TO`: launcher argv prevod i uklanjanje oslanjanja na Seatbelt.
  - `GOTCHA`: ne kombinovati eksterni bypass sa slabim ili implicitnim mount pravilima.
- [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
  - `KEY_INSIGHT`: container vidi samo eksplicitno bind-mountovane host putanje; mount može biti read-only.
  - `APPLIES_TO`: `/workspace` i auth secret mount.
  - `GOTCHA`: `-v` može napraviti nepostojeći host path; koristiti `--mount` i prethodno validirati da source postoji.
- [Docker container run](https://docs.docker.com/reference/cli/docker/container/run/)
  - `KEY_INSIGHT`: `--read-only`, `--cap-drop` i `--security-opt no-new-privileges` smanjuju površinu container procesa; `--privileged` ukida bezbednosnu vrednost izolacije.
  - `APPLIES_TO`: launcher hardening i test očekivanja.
  - `GOTCHA`: nikada ne mount-ovati Docker socket; time bi container dobio kontrolu nad host daemon-om.
- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
  - `KEY_INSIGHT`: pinovati base image i dependency verziju za reproduktivan runtime.
  - `APPLIES_TO`: Codex eval image.

## Patterns to Mirror

| Kategorija | File:Lines | Obrazac | Stvarni snippet |
| --- | --- | --- | --- |
| Profil | `scripts/eval/isolation_state.py:36-49` | Jedan security-relevant profil dele canary i adapter | `CODEX_EXECUTION_PROFILE: dict[str, object] = {"sandbox": "read-only", "wrapper_argv": [], "containment": "none"}` |
| Fingerprint | `scripts/eval/isolation_state.py:57-61` | Canonical JSON + SHA-256 za stabilan identitet | `canonical = json.dumps(active, sort_keys=True, separators=(",", ":"))` |
| Fail-closed | `scripts/eval/isolation_state.py:148-184` | Svaki missing/mismatch vraća razlog, samo potpuna podudarnost vraća `None` | `if verdict.profile_fingerprint != active_fingerprint: return (...)` |
| Safe subprocess | `scripts/eval/runtime_adapters.py:81-95` | Argv lista, eksplicitni cwd/stdin, bounded timeout, bez shell-a | `asyncio.create_subprocess_exec(*argv, cwd=cwd, stdin=asyncio.subprocess.PIPE, ...)` |
| Shared launch | `scripts/eval/runtime_adapters.py:208-219` | Adapter gradi Codex argv iz aktivnog profila | `[*profile["wrapper_argv"], self.binary, "exec", ...]` |
| Canary shared launch | `scripts/eval/canary_codex_image.py:40-69` | Canary koristi isti profil kao benchmark | `profile = isolation_state.CODEX_EXECUTION_PROFILE` |
| Sentinel dokaz | `scripts/eval/canary_codex_image.py:102-112` | PASS zahteva pokušaj, blokadu i odsustvo secreta | `verdict.add("outside read blocked", blocked, detail[:500])` |
| Terminalni event | `scripts/eval/canary_common.py:156-176` | Ne zaključivati iz `in_progress`; uzeti poslednji terminalni događaj | `item = terminal[-1] if terminal else matches[-1]` |
| Path escape zaštita | `scripts/eval/orchestrator.py:179-192` | Resolve + symlink/path-relative provera pre kopiranja | `if item.is_symlink() or not item.resolve().is_relative_to(root): raise ValueError(...)` |
| Test monkeypatch | `tests/test_runtime_adapters.py:154-174` | Stubovati subprocess granice, proveriti gate ponašanje bez mreže | `monkeypatch.setattr(runtime, "_cli_version", _ok_version)` |

## Files to Change

| Operacija | Fajl | Svrha |
| --- | --- | --- |
| Add | `docker/codex-eval/Dockerfile` | Minimalan, pinovan Linux/aarch64 Codex CLI image sa non-root korisnikom i entrypoint pripremom efemernog `CODEX_HOME` |
| Add | `scripts/eval/codex_container.py` | Validacija host argv/pathova, Docker argv konstrukcija, path translation, execution identity i transparentno izvršenje |
| Modify | `scripts/eval/isolation_state.py` | Aktivni Docker profil, prošireni execution identity u verdictu i fail-closed provera image/container identiteta |
| Modify | `scripts/eval/runtime_adapters.py` | Jedan shared Codex command builder; version/help/auth i real run svi kroz wrapper |
| Modify | `scripts/eval/canary_codex_image.py` | Shared builder, wrapped CLI version/identity i container-aware dry-run/verdict |
| Modify | `scripts/eval/canary_common.py` | Generalizovati CLI version helper da prima kompletan argv ili dodati usko wrapper-aware pomagalo |
| Add | `tests/test_codex_container.py` | Offline launcher/path/mount/hardening/identity testovi |
| Modify | `tests/test_isolation_state.py` | Image/container identity mismatch i legacy/malformed verdict fail-closed regresije |
| Modify | `tests/test_runtime_adapters.py` | Wrapper se koristi za run i sve preflight probe; host Codex se ne proverava direktno |
| Modify | `tests/test_image_canaries.py` | Canary argv/path prevod i shared profile dokazi |
| Modify | `tests/test_eval_orchestrator.py` | Codex analyst root radi kroz injected container-aware adapter bez izlaganja answer path-a |
| Modify | `runbooks/faza-4-eval-orchestrator.md` | Build/inspect/preview/confirm/paired-canary operativa i dokazana platforma |

Ne menjati postojeće untracked fajlove `.claude/PRPs/eval-batch-sonnet-handoff.md`, `.claude/PRPs/reviews/` i `scripts/eval/ISSUE_BODY.md`.

## NOT Building

- Ne menjati scoring rubriku, težine, judge schema-u ni agregaciju.
- Ne omogućavati Codex judge u v1; issue traži vraćanje Codex analyst poređenja.
- Ne vraćati `chart_image`; benchmark ostaje OHLCV-text ugovor.
- Ne pokretati punu model × effort matricu.
- Ne praviti generički container orchestration framework niti podršku za Kubernetes/VM.
- Ne koristiti `--privileged`, Docker socket mount, host network/PID namespace ili mount celog `$HOME`/repo-a.
- Ne tvrditi da container štiti od zlonamernog host operatora ili kompromitovanog Docker daemon-a; threat model je sprečavanje model procesa da pročita privatni host answer key.
- Ne commit-ovati `auth.json`, PASS verdict ili privatni benchmark sadržaj.

## Step-by-Step Tasks

### Task 1 — Uvesti pinovani, minimalni Codex eval image

- **Action:** Dodati reproducibilan Docker image za trenutno podržani Codex CLI.
- **File:** `docker/codex-eval/Dockerfile`.
- **Implementation:** Pinovati podržani Node base image po digestu za `linux/arm64`, instalirati tačno `@openai/codex@0.141.0`, kreirati non-root `codex` korisnika i unapred kreirati `/workspace`, `/run/secrets` i prazan home. Entrypoint kopira `/run/secrets/auth.json` u writable `tmpfs` `CODEX_HOME`, postavlja `0600`, zatim `exec`-uje prosleđeni Codex argv. Build ne sme sadržati repo ili auth kroz `COPY`.
- **Pattern to mirror:** Verzijska eksplicitnost iz `runbooks/faza-4-eval-orchestrator.md:9-17`; security flags će centralno graditi launcher.
- **Imports/types:** Nema Python importa; koristiti exec-form `ENTRYPOINT`/`CMD` gde je moguće.
- **Gotchas:** Lokalni tag nije nepromenljiv identitet; verdict mora koristiti inspected image ID/digest, ne samo tag. Ne stavljati credential u image layer. Container mora imati `/bin/cat`, jer canary zahteva stvarni command attempt.
- **Validation:**

```bash
docker build --platform linux/arm64 -t wyckoff-codex-eval:0.141.0 docker/codex-eval
docker image inspect wyckoff-codex-eval:0.141.0 --format '{{.Id}} {{.Architecture}} {{.Os}}'
docker run --rm --entrypoint codex wyckoff-codex-eval:0.141.0 --version
```

### Task 2 — Implementirati fail-closed Docker launcher i path translation

- **Action:** Napraviti jedinu granicu koja host Codex argv pretvara u hardenovan `docker run`.
- **File:** `scripts/eval/codex_container.py`.
- **Implementation:** Definisati typed immutable profile input i čiste funkcije za: nalaženje/resolve `--cd`; proveru da `--output-schema` i svaki `--image` postoje, nisu symlink i nalaze se ispod case root-a; prevođenje tih putanja na `/workspace/<relative>`; odbijanje `--add-dir`, dodatnih mount/path opcija i nepoznatog wrapper režima. Runtime argv mora koristiti `docker run --rm -i --read-only --cap-drop ALL --security-opt no-new-privileges=true`, `tmpfs` samo za Codex home i `/tmp`, read-only `--mount` za case i auth secret, bez portova/socketa. Zameniti unutrašnji `--sandbox read-only` sa `--dangerously-bypass-approvals-and-sandbox`, jer official CLI ovaj flag namenjuje eksterno sandboxovanom okruženju. Proslediti stdout/stderr/exit code bez parsiranja.
- **Implementation (probe režim):** Dodati `--execution-identity` koji bez model poziva vraća canonical JSON sa Docker server OS/arch, image ID/repo digest i wrapped `codex --version`. `--version`, `exec --help` i `login status` moraju takođe raditi kroz isti image; probe komande ne mount-uju case, ali i dalje koriste identičan image/auth/hardening profil.
- **Pattern to mirror:** `_safe_copy` resolve/symlink discipline iz `scripts/eval/orchestrator.py:179-192` i argv-only subprocess iz `scripts/eval/runtime_adapters.py:81-95`.
- **Imports/types:** Samo stdlib: `argparse`, `json`, `os`, `pathlib.Path`, `subprocess`, `sys`, `dataclasses` po potrebi.
- **Gotchas:** Ne koristiti `shell=True`. `--mount` source mora biti apsolutan i mora postojati. Auth path uzeti iz eksplicitnog env/config parametra sa defaultom `$CODEX_HOME/auth.json` ili `~/.codex/auth.json`; ne logovati sadržaj. Image pull/build ne sme automatski da se dogodi tokom benchmark run-a. Odbiti rad ako Docker daemon/image/auth nisu dostupni.
- **Validation:**

```bash
uv run python -m scripts.eval.codex_container --execution-identity
uv run python -m scripts.eval.codex_container codex --version
uv run python -m scripts.eval.codex_container codex exec --help | rg -- '--dangerously-bypass-approvals-and-sandbox|--output-schema|--ephemeral'
```

### Task 3 — Proširiti execution profile i persisted verdict identitet

- **Action:** Vezati PASS za stvarni container runtime, ne samo za statički wrapper string.
- **File:** `scripts/eval/isolation_state.py`.
- **Implementation:** Postaviti `CODEX_EXECUTION_PROFILE` na Docker launcher (`sandbox`, `wrapper_argv`, `containment="docker"`, pinovani `image`, `workspace`). Zadržati canonical fingerprint nad celim statičkim profilom. Proširiti `IsolationVerdict` obaveznim strukturiranim `execution_identity` poljem koje sadrži container OS/arch, exact image ID/digest i wrapped Codex CLI verziju. `record_verdict` prima već probed identity; `isolation_block_reason` prima live identity i poredi ga canonical equality pravilom pre odobravanja. Stari verdict bez novog polja mora se tretirati kao malformed/missing i fail-closed.
- **Pattern to mirror:** `_REQUIRED_FIELDS`, frozen dataclass i redosled mismatch provera iz `scripts/eval/isolation_state.py:51-77,110-185`.
- **Imports/types:** Postojeći `dataclass`, `json`, `hashlib`; dodati precizan `TypedDict` ili frozen dataclass za identity umesto slobodnog `dict[str, object]` ako ne komplikuje JSON serializaciju.
- **Gotchas:** `platform.platform()` i dalje beleži host/Docker Desktop platformu, dok identity beleži Linux container platformu. Oba su potrebna: promena host OS build-a ili image-a obara PASS. Ne prihvatati tag kao zamenu za image ID.
- **Validation:**

```bash
uv run --extra mcp pytest -q tests/test_isolation_state.py
```

### Task 4 — Provlačiti sve Codex probe i izvršenja kroz shared profil

- **Action:** Ukloniti host/container split-brain u adapteru.
- **Files:** `scripts/eval/runtime_adapters.py`, `scripts/eval/canary_common.py`.
- **Implementation:** Uvesti jednu funkciju `codex_profile_argv(inner_argv)` (ili ekvivalent) koja prepend-uje tačno aktivni wrapper. `CodexRuntimeAdapter.build_argv`, `_cli_version`, `_require_capabilities` i `_require_auth` moraju dobiti wrapped argv. `shutil.which("codex")` zameniti proverom wrapper entrypoint-a/Docker-a, jer host Codex više nije runtime dependency. Preflight prvo proverava wrapper/image i dobavlja live execution identity, zatim proverava verdict, pa wrapped help/auth. Greške moraju ostati bounded `RuntimeUnavailable` bez auth ili private path sadržaja.
- **Pattern to mirror:** Postojeće helper granice `_require_capabilities`, `_cli_version`, `_require_auth` iz `scripts/eval/runtime_adapters.py:98-134`; ne duplirati subprocess parsing.
- **Imports/types:** `Path`, postojeći async subprocess helpers; profil/helper import iz `isolation_state` ili novog launcher modula bez circular importa.
- **Gotchas:** Gate verzija mora biti wrapped `codex --version`, ista koju canary zapisuje. Capability i auth probe moraju raditi unutar container-a; host `codex login status` nije dokaz container auth-a. `build_argv` mora ostati list argv i prompt ostaje samo stdin.
- **Validation:**

```bash
uv run --extra mcp pytest -q tests/test_runtime_adapters.py
```

### Task 5 — Prebaciti canary na isti container identity i očuvati dokaz pokušaja

- **Action:** Canary mora dokazati baš runtime koji gate autorizuje.
- **Files:** `scripts/eval/canary_codex_image.py`, `scripts/eval/canary_common.py`.
- **Implementation:** Graditi command istim `codex_profile_argv` helperom kao adapter. Host case image/schema ostaju u `case_root`, launcher ih validira i prevodi u `/workspace`; spoljni sentinel se namerno ne mount-uje i prompt zadržava host apsolutnu putanju kako bi `/bin/cat` unutar container-a dokazivo pao. `record_verdict` dobija wrapped CLI version i live execution identity. Dry-run mora prikazati sanitizovan Docker plan/mount destinacije, profil fingerprint i image ID, bez auth sadržaja ili plaćenog poziva.
- **Pattern to mirror:** `evaluate` checks iz `scripts/eval/canary_codex_image.py:72-113` i poslednji terminalni event iz `scripts/eval/canary_common.py:156-176` ostaju nepromenjena semantika.
- **Imports/types:** Reuse shared wrapper/identity helpers; ne praviti drugi Docker argv builder.
- **Gotchas:** Uspešan CLI exit nije dovoljan. PASS i dalje zahteva sva tri svojstva: command event referencira outside path, terminalni status/exit pokazuje blokadu i sentinel nije ni u JSONL/stderr/finalnom odgovoru. Ne tretirati `file not found` bez command eventa kao pokušaj.
- **Validation:**

```bash
uv run python -m scripts.eval.canary_codex_image
```

Ovo je samo dry-run. `--confirm` se ne pokreće u ovom tasku bez eksplicitnog operator odobrenja troška.

### Task 6 — Dodati offline security regresije

- **Action:** Pokriti launcher, profile identity i integracione ivice bez Docker daemon-a/model poziva u default testovima.
- **Files:** `tests/test_codex_container.py`, `tests/test_isolation_state.py`, `tests/test_runtime_adapters.py`, `tests/test_image_canaries.py`, `tests/test_eval_orchestrator.py`.
- **Implementation:** Mockovati subprocess boundary i asertovati tačan Docker argv: jedini bind source-i su case + auth; case/auth su read-only; rootfs je read-only; sve capabilities su drop-ovane; `no-new-privileges` postoji; nema `--privileged`, socket, host network/PID ili answer path mount-a. Dodati parametarske testove za schema/image izvan root-a, symlink, nepostojeći source, `--add-dir`, missing image/auth/daemon i mutable image identity mismatch. Dokazati da build/run/version/help/auth svi koriste isti wrapper. Dokazati da legacy verdict i promenjen image ID fail-closed blokiraju adapter. U orchestrator testu injected fake adapter beleži da `RuntimeRequest.cwd` sadrži samo case/schema i nikada answer key.
- **Pattern to mirror:** `monkeypatch`/fake async helpers iz `tests/test_runtime_adapters.py:102-174`; temp path i synthetic JSONL iz `tests/test_image_canaries.py:35-153`.
- **Imports/types:** `pytest`, `Path`, `json`, `asyncio`; bez realnog Docker/model poziva u test suite-u.
- **Gotchas:** Ne overfit-ovati redosled bezbednosno nebitnih Docker flagova; proveriti semantičke parove i mount set. Dodati negativni test da image tag isti + image ID promenjen obara verdict.
- **Validation:**

```bash
uv run --extra mcp pytest -q \
  tests/test_codex_container.py \
  tests/test_isolation_state.py \
  tests/test_runtime_adapters.py \
  tests/test_image_canaries.py \
  tests/test_eval_orchestrator.py
```

### Task 7 — Ažurirati operator runbook i dokumentovati dokazanu platformu

- **Action:** Zameniti „EMPIRIJSKI PALO" preciznim uslovnim stanjem posle uspešnog real canary-ja.
- **File:** `runbooks/faza-4-eval-orchestrator.md`.
- **Implementation:** Dodati prerequisites za Docker Desktop, image build/inspect, auth secret i disk sharing; canonical build komandu; execution-identity proveru; obavezni canary dry-run; operator-approved `--confirm`; lokaciju/sadržaj verdicta; stale image/CLI/platform ponašanje; mali paired canary; rollback (ukloniti verdict ili promeniti profil → fail-closed). Tek nakon stvarnog PASS-a upisati tačnu dokazanu platformu: host `platform.platform()`, Docker OS/arch, image ID/digest i wrapped Codex CLI verziju. Navesti da Codex built-in sandbox nije granica i da container ne mount-uje answer key.
- **Pattern to mirror:** Sekcije `Preduslovi`, `Obavezni preview`, `Mali real canary`, `Anti-leakage granica` u `runbooks/faza-4-eval-orchestrator.md:5-101`.
- **Gotchas:** Ne deklarisati PASS pre realnog canary-ja. Ako realni canary padne, runbook ostaje `BLOCKED/EMPIRIJSKI PALO` sa novim detail-om; ne ručno falsifikovati verdict. Cross-provider ranking je vraćen u scope, ali puna matrica nije autorizovana.
- **Validation:**

```bash
rg -n "Docker|execution identity|codex_isolation_verdict|outside read blocked|cross-provider|upareni" runbooks/faza-4-eval-orchestrator.md
```

### Task 8 — Izvršiti real isolation canary i proveriti programski PASS

- **Action:** Posle code review-a, image inspect-a i dry-run pregleda izvršiti tačno jedan plaćeni Codex poziv uz eksplicitno operator odobrenje.
- **Files:** Runtime artifact `scripts/eval/state/codex_isolation_verdict.json` (gitignored; ne commit-ovati).
- **Implementation:** Pokrenuti `--confirm`, sačuvati samo sanitizovan izlaz u implementation report-u i proveriti: image token tačan; `outside read attempted=yes`; `outside read blocked=yes`; sentinel nije procureo; verdict `passed=true`; CLI/platform/profile/image identity odgovaraju live probama. Zatim pokrenuti Codex adapter preflight i dokazati da prolazi bez izmene konstante. Negativno: privremeno mock/promena profile/image identity mora ponovo dati `unavailable` (test, ne ručna produkciona izmena).
- **Pattern to mirror:** Programski zapis iz `scripts/eval/canary_codex_image.py:155-169` i gate iz `scripts/eval/runtime_adapters.py:226-240`.
- **Gotchas:** Ovo je naplativ mrežni poziv. Ako bilo koji check padne, artifact mora biti FAIL i benchmark ostaje blokiran. Ne ponavljati poziv automatski. Ne objavljivati sentinel ni auth u report-u.
- **Validation:**

```bash
uv run python -m scripts.eval.canary_codex_image --confirm --model gpt-5.4 --effort low
uv run python - <<'PY'
import asyncio
from scripts.eval.runtime_adapters import CodexRuntimeAdapter
asyncio.run(CodexRuntimeAdapter().preflight("codex", "high"))
print("Codex preflight PASS")
PY
```

### Task 9 — Vratiti cross-provider scope malim uparenim canary-jem

- **Action:** Tek posle Task 8 PASS-a izvršiti jedan isti case/effort kroz Claude i Codex; ne punu matricu.
- **File:** Nema source izmene; generišu se postojeći benchmark state/result/report artefakti pod operatorovim `base-dir`.
- **Implementation:** Prvo pokrenuti `orchestrator --dry-run` sa jednim case-om, modelima `claude-opus-4-8,codex`, istim `high` effort-om i `--max-concurrency 1`; pregledati da oba provider-a imaju `planned`, ne `unavailable`. Posle posebnog odobrenja troška pokrenuti isti scope realno. Potvrditi dva uspešna analyst result-a, zajednički Claude judge, schema-valid output i cross-provider red u report-u. Ne tumačiti n=1 kao statistički rang.
- **Pattern to mirror:** Preview/real canary workflow iz `runbooks/faza-4-eval-orchestrator.md:23-55`.
- **Gotchas:** Privatni `--answers-path` daje operator. Ne hardkodovati ga u repo ili plan komande. Ako Claude canary ili Codex isolation identity postane stale, zaustaviti se; nema fallback-a na neizolovan Codex.
- **Validation:**

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path "$ANSWERS_PATH" \
  --case "$CASE_ID" \
  --model claude-opus-4-8,codex --effort high \
  --max-concurrency 1 --dry-run
```

Real komanda je ista bez `--dry-run` i pokreće se samo uz operatorovo odobrenje nakon pregleda preview-a.
Operator pre komande eksplicitno postavlja `ANSWERS_PATH` na privatni answer-key fajl i `CASE_ID` na jedan već validiran case iz manifesta; njihove vrednosti se ne upisuju u repo.

### Task 10 — Završni sanity i duboki security review

- **Action:** Validirati kompletan offline suite i uraditi duboki review jer izmena autorizuje privatni benchmark runtime.
- **Files:** Svi fajlovi iz ovog plana.
- **Implementation:** Pokrenuti formatter/lint ako repo uvede odgovarajući alat; zatim kompletan pytest. Review posebno prati mount allowlist, wrapper primenu na svaki subprocess, immutable image identity, auth redakciju, fail-closed mismatch grane i zabranu automatskog plaćenog retry-ja. U report-u navesti stvarno izvršene paid operacije odvojeno od offline testova.
- **Pattern to mirror:** `CLAUDE.md:34-46` zahteva bar sanity check; security/runtime promena opravdava dublji manuelni multi-aspect review.
- **Gotchas:** Ne menjati niti brisati postojeće korisničke untracked fajlove. Ne uključiti gitignored verdict u commit.
- **Validation:**

```bash
uv run --extra mcp pytest -q
git status --short
git diff --check
```

## Testing Strategy

### Offline unit testovi (obavezni, bez Docker/model poziva)

- Docker argv/mount allowlist i hardening flags.
- Host-to-container path translation samo ispod resolved case root-a.
- Symlink, `..`, missing file, `--add-dir`, missing auth/image/daemon fail-closed grane.
- Shared wrapper na run/version/help/auth/canary putevima.
- Stable profile fingerprint i sensitivity na wrapper/image/workspace promene.
- Verdict mismatch za host platformu, CLI version, profile fingerprint, container OS/arch i image ID/digest.
- Canary PASS/FAIL JSONL događaji, uključujući `in_progress` pre terminalnog eventa.
- Orchestrator zadržava answer key van analyst root-a.

### Lokalni Docker smoke (bez model poziva)

- Image build i inspect.
- Wrapped `codex --version`.
- Wrapped `codex exec --help`.
- Wrapped `codex login status` (auth status, bez inference poziva).
- Execution identity je determinističan za nepromenjen image i menja se nakon rebuild-a.

### Plaćeni/manual testovi (eksplicitno odobrenje)

1. Jedan `canary_codex_image --confirm`.
2. Programska PASS i adapter preflight provera.
3. Jedan paired Claude/Codex case sa istim effort-om.

Puna matrica nije test ovog issue-a.

## Validation Commands

```bash
# Offline suite
uv run --extra mcp pytest -q \
  tests/test_codex_container.py \
  tests/test_isolation_state.py \
  tests/test_runtime_adapters.py \
  tests/test_image_canaries.py \
  tests/test_eval_orchestrator.py

# Full regression
uv run --extra mcp pytest -q
git diff --check

# Container capability, bez model poziva
docker build --platform linux/arm64 -t wyckoff-codex-eval:0.141.0 docker/codex-eval
uv run python -m scripts.eval.codex_container --execution-identity
uv run python -m scripts.eval.codex_container codex --version
uv run python -m scripts.eval.canary_codex_image

# Plaćeno: samo posle eksplicitnog operator odobrenja
uv run python -m scripts.eval.canary_codex_image --confirm --model gpt-5.4 --effort low
```

## Acceptance Criteria

- [ ] `CODEX_EXECUTION_PROFILE` aktivira Docker containment i ostaje zajednički izvor istine za canary, adapter, version/help/auth probe i pravi run.
- [ ] Container mount allowlist sadrži samo case root i auth secret; answer key, repo root, host HOME i Docker socket nisu vidljivi.
- [ ] Container radi bez `--privileged`, sa read-only rootfs/workspace, drop-ovanim capabilities i `no-new-privileges`.
- [ ] Host schema/image putanje van case root-a i symlink/path escape se odbijaju pre Docker poziva.
- [ ] PASS verdict je vezan za host platformu, wrapped Codex CLI verziju, profile fingerprint, container OS/arch i stvarni image ID/digest.
- [ ] Missing, FAIL, legacy, stale CLI/platform/profile ili promenjen image identity fail-closed blokira Codex.
- [ ] `scripts/eval/canary_codex_image.py --confirm` programski beleži: outside read attempted = da; outside read blocked = da; sentinel nije procureo.
- [ ] `scripts/eval/state/codex_isolation_verdict.json` ima `passed=true` bez ručne izmene konstante i ostaje gitignored.
- [ ] `CodexRuntimeAdapter.preflight` prolazi samo sa matching live identity.
- [ ] Runbook beleži tačnu dokazanu host/container platformu i build/canary/rollback proceduru.
- [ ] Mali isti-case/same-effort Claude/Codex canary vraća oba providera u report; puna matrica nije pokrenuta.
- [ ] Scoring, judge dimenzije i OHLCV-only input contract nisu promenjeni.
- [ ] Kompletan offline test suite prolazi i plaćeni pozivi su jasno odvojeni u report-u.

## Completion Checklist

- [ ] Svi Docker base/dependency elementi su pinovani; image ID/digest je deo live identity-ja.
- [ ] Nema `shell=True`, interpoliranog shell command stringa ili implicitnog volume mount-a.
- [ ] Nema credential/private path sadržaja u stdout, stderr tail-u, report-u ili commitu.
- [ ] Canary i benchmark koriste isti centralni argv builder.
- [ ] Preflight ne ispituje host Codex umesto container Codex-a.
- [ ] Default pytest ne zahteva Docker daemon, auth, mrežu ili model poziv.
- [ ] Dry-run je pregledan pre svakog plaćenog koraka.
- [ ] Real PASS je dobijen programskim canary-jem ili je blocker eksplicitno prijavljen bez otključavanja gate-a.
- [ ] Runbook i implementation report razlikuju offline dokaz, Docker smoke i plaćeni model dokaz.
- [ ] Duboki security review nije našao mount/identity/gate zaobilaznicu.

## Risks and Mitigations

| Rizik | Verovatnoća / uticaj | Mitigacija |
| --- | --- | --- |
| Mutable local image tag autorizuje drugi sadržaj | Srednja / kritičan | Live `docker image inspect` ID/digest u verdictu; mismatch fail-closed |
| Preflight koristi host Codex, run container Codex | Srednja / visok | Jedan shared wrapper za version/help/auth/run; regresioni test svih argv puteva |
| Launcher nenamerno mount-uje spoljašnju schema/image putanju | Srednja / kritičan | Resolve + relative-to + symlink reject pre `docker run`; samo dva dozvoljena mount tipa |
| Container dobije host kontrolu preko Docker socket-a/privilege-a | Niska / kritičan | Eksplicitna zabrana socket-a, `--privileged`, host namespace-a; argv security test |
| Read-only auth ne može da refresh-uje token | Srednja / srednji | Secret se kopira u efemerni writable `CODEX_HOME` tmpfs; host auth ostaje read-only |
| Docker Desktop file-sharing ne vidi temp path | Srednja / srednji | Pre-canary local mount smoke; jasan runbook blocker; ne širiti mount na repo/HOME |
| Canary PASS na image-u koji benchmark više ne koristi | Niska / kritičan | Image ID + profile fingerprint + wrapped CLI version proveravaju se pri svakom preflight-u |
| `file not found` se pogrešno smatra dokazom bez model pokušaja | Niska / visok | Zadržati obavezni terminalni command-execution event sa outside path-om |
| Container ima mrežu potrebnu API-ju i može exfiltrate-ovati prompt | Niska / visok | Threat model ograničiti; container dobija samo case/prompt, nikad answer key. Ne mount-ovati host secrets osim Codex auth-a |
| Auth secret je dostupan model shell-u unutar container-a | Srednja / visok | Codex auth je nužan runtime secret; non-root `0600`, efemerni home, bez ispisa. Razmotriti API-token credential helper u budućem hardening issue-u, ali ne širiti #82 |
| Plaćeni canary automatski retry-uje | Niska / srednji | Tačno jedan manual `--confirm`; nema auto retry-ja; svaki dodatni poziv traži novo odobrenje |
| n=1 paired rezultat se protumači kao rang | Srednja / srednji | Runbook/report ga označava kao operativni canary, ne statistički rezultat |

## Notes

### Zašto Docker, a ne zaseban macOS UID

Zaseban UID je na prvi pogled jeftiniji, ali trenutni tok koristi `TemporaryDirectory` sa host-user pristupom i Codex auth `~/.codex/auth.json` je `0600`. Da bi runner UID radio, implementacija bi morala da menja ownership/ACL svakog case root-a, provisioning credential-a i `sudoers` politiku, dok answer key mora ostati nedostupan. To uvodi više host-specifičnog privilegovanog setup-a i teže reproducibilan dokaz. Docker je već prisutan u ciljnom okruženju i izražava pozitivnu allowlist granicu: ono što nije mount-ovano ne postoji u container filesystem-u.

### Alternativa odbijena za v1

- **Linux/Landlock host:** može biti kvalitetno rešenje, ali traži drugi host/CI i ne rešava trenutni macOS operator tok.
- **Custom Seatbelt profil:** trenutni nalaz je upravo da ugrađeni macOS profil ne daje traženi read confinement; održavanje privatnog Seatbelt policy-ja bi vezalo projekat za nedokumentovane/platform-sensitive detalje.
- **Samo POSIX `chmod` bez drugog UID-a:** isti korisnik koji pokreće Codex ostaje vlasnik/čitalac, pa ne stvara granicu.

### Otvoreni blocker-i tokom implementacije

- Plaćeni `--confirm` i paired benchmark zahtevaju eksplicitno operator odobrenje u trenutku izvršenja.
- Ako Docker Desktop ne može da bind-mount-uje macOS temp root ili container auth status ne prolazi, gate ostaje zatvoren dok se setup ne ispravi; ne prelaziti na host fallback.
- Tačan base image digest mora se odabrati i zabeležiti pri implementaciji iz zvaničnog registry metadata-a; plan namerno ne izmišlja digest.

### Confidence

**8/10.** Codebase gate i integration points su jasni, Docker je lokalno dostupan, a official Codex CLI eksplicitno podržava externally sandboxed režim. Preostala neizvesnost je operativna: Codex auth refresh u efemernom container-u i Docker Desktop bind-mount ponašanje za macOS temp putanje moraju biti provereni besplatnim smoke-om pre plaćenog canary-ja.
