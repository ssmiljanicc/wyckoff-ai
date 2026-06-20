# Feature: End-to-end orkestrator za Faza 4 evaluaciju

## Summary

Issue [#73](https://github.com/ssmiljanicc/wyckoff-ai/issues/73) uvodi jednu dokumentovanu, crash-safe (otpornu na prekid procesa) Python CLI ulaznu tačku za postojeći Faza 4 eval tok. Presuda [PROCEED](https://github.com/ssmiljanicc/wyckoff-ai/issues/73#issuecomment-4752345609) obavezuje na hibridni dizajn: Python je jedini vlasnik determinističkog plana, trajnog stanja, retry/resume semantike (ponovni pokušaj/nastavak), ograničenja konkurentnosti i završnog ingest/report toka; tanki runtime adapteri (prilagođivači izvršnog okruženja) samo pokreću sveže Claude Code ili Codex procese.

Postojeći `scripts/eval/benchmark.py` ostaje integracioni vrh za matricu, snapshote, scoring, ingest i report. Novi sloj ne duplira te funkcije. Svaki analyst proces radi iz privremenog root-a koji sadrži samo kopiju odgovarajućeg case foldera i output schema-u; judge je zaseban Opus proces bez alata, nad payloadom iz `scoring.prepare_judge_input`. Trajno stanje i parcijalni result checkpoint-i omogućavaju nastavak judge faze bez ponovnog analyst poziva i preskakanje već uspešnih run-ova.

## User Story

Kao operator Faza 4 eval harness-a

Želim da jednom CLI komandom pregledam ili izvršim izabranu case × model × effort matricu kroz fizički razdvojene analyst i judge procese

Kako bih bez ručne orkestracije, gubitka parcijalnih rezultata ili ponavljanja uspešnih run-ova dobio postojeći benchmark report.

## Problem Statement

Faza 4 već ima stabilne determinističke ugovore, ali nema trajan kontrolni sloj:

- `scripts/eval/benchmark.py:1-29` eksplicitno ostavlja analyst/judge pozive runbook-u.
- `scripts/eval/benchmark.py:260-313` daje stabilan `run_id`, case/model/effort i eksplicitne snapshot/answer-key putanje.
- `scripts/eval/benchmark.py:316-337` upisuje samo prazne result slotove; nema status, stage, attempt, grešku ili recovery semantiku.
- `scripts/eval/benchmark.py:791-833` preskače nepotpune result fajlove pri ingest-u, ali ne upravlja njihovim izvršavanjem.
- Potvrđeni offline preview za 10 case-ova pravi 30 snapshotova i 180 analyst run-ova, pa ručno vođenje nije održivo.

Bez novog kontrolnog sloja prekid procesa, neuspeh jednog provider-a ili neuspešan judge poziv ostavljaju operatoru ručno zaključivanje šta treba ponoviti i mogu izazvati duple skupe pozive.

## Solution Statement

Dodati `scripts.eval.orchestrator` kao jedinu operator CLI tačku i podeliti implementaciju na tri jasna ugovora:

1. `benchmark_runs.json` ostaje nepromenljiv izvor specifikacija run-ova za dati plan.
2. `orchestrator_state.json` postaje atomski upisan izvor izvršnog stanja po `run_id`: `pending | running | succeeded | failed | skipped`, uz `stage`, `attempt`, timestamps i strukturisanu grešku.
3. `results/<run_id>.json` je trajni checkpoint payload-a: prvo analyst output + usage, zatim judge verdict. Postojeći ingest nastavlja da čita isti završni oblik.

Orkestrator radi preflight (prethodnu proveru), po potrebi koristi postojeći snapshot builder, kreira ili učitava manifest, filtrira run-ove, claim-uje posao pod lock-om, ograničava konkurentnost i minimalni razmak startova, poziva provider adapter, checkpoint-uje analyst rezultat, poziva izolovanog Opus judge-a, finalizuje result/status i na kraju poziva postojeći `benchmark.ingest`. `--dry-run` radi samo preflight i ispisuje deterministički execution plan bez snapshot mreže, subprocess model poziva ili promene postojećeg state/results sadržaja.

## Metadata

| Polje | Vrednost |
|---|---|
| Izvor | GitHub issue #73 + obavezujući PROCEED komentar |
| Tip | `ENHANCEMENT` / infrastruktura |
| Složenost | `HIGH` |
| Razlog složenosti | Više provider CLI ugovora, fizička anti-leakage granica, crash recovery, konkurentni state prelazi i skupi side effect pozivi |
| Pogođeni sistemi | `scripts/eval/`, eval testovi, operator runbook |
| Kanonski plan | `PRPs/plans/faza-4-end-to-end-eval-orchestrator.plan.md` |
| Projekat | `/Users/ssmiljanic/projekti/wyckoff-ai` |
| Grana | `main` |
| Lokalno proverene verzije | Claude Code `2.1.183`; Codex CLI `0.141.0` |
| Procena implementacionih fajlova | 8 novih/izmenjenih fajlova |
| Broj zadataka | 8 |

## UX Design

### Pre

```text
operator
  ├─ validate private answers
  ├─ ensure 3 snapshot ugla
  ├─ build matrix manifest
  ├─ za svaki run ručno pokreni analyst
  ├─ ručno pripremi i pokreni judge
  ├─ ručno upiši result JSON
  └─ pokreni ingest/report

prekid ili jedan neuspeh → operator ručno rekonstruiše stanje
```

### Posle

```text
operator
  └─ uv run --extra mcp python -m scripts.eval.orchestrator [opcije]
       ├─ preflight: answer key + CLI capability + selekcija + execution plan
       ├─ reuse benchmark.ensure_snapshots / build_run_matrix
       ├─ claim sledećih pending/failed run-ova
       ├─ analyst runtime (case-only privremeni root)
       ├─ atomic analyst checkpoint
       ├─ judge runtime (Opus, no-tools, sanitized payload, bez chart-a)
       ├─ atomic success/failure status po run_id
       └─ reuse benchmark.ingest → postojeći report.md/report.json

prekid → sledeći poziv reconciles state/checkpoints → nastavlja bez uspešnih run-ova
```

### Promene interakcije

| Lokacija | Pre | Posle | Uticaj na operatora |
|---|---|---|---|
| CLI | Četiri odvojene benchmark komande + ručni agent pozivi | Jedna `scripts.eval.orchestrator` komanda | Jedna dokumentovana ulazna tačka |
| Preview | `benchmark --dry-run` gradi stub snapshote i manifest | `orchestrator --dry-run` validira i ispisuje izabrane/skipovane run-ove bez model poziva | Trošak i scope su vidljivi pre izvršavanja |
| Resume | Nepotpuni result se samo preskoči pri ingest-u | State + checkpoint reconciliation odlučuje nastavak po stage-u | Bez ponovnog uspešnog analyst/judge rada |
| Dijagnostika | Nema trajne run greške | Status, stage, attempt, provider, exit code i sažeta stderr poruka | Neuspeh je lokalizovan po `run_id` |
| Izolacija | Runbook instrukcija „čitaj samo folder” | Svež subprocess, privremeni case-only root, restrictive tools/sandbox, zaseban judge root | Granica je testabilna i nije samo prompt |

## Mandatory Reading

### Presuda i projektni ugovori

- [Issue #73](https://github.com/ssmiljanicc/wyckoff-ai/issues/73) — problem, očekivani tok, ograničenja i acceptance criteria.
- [PROCEED presuda](https://github.com/ssmiljanicc/wyckoff-ai/issues/73#issuecomment-4752345609) — obavezujuća hibridna podela odgovornosti i anti-leakage granica.
- `CLAUDE.md:1-68` — srpski jezik planova i projektna review disciplina.
- `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` — Faza 4 arhitektura, model × effort matrica i završeni fazni ugovori.

### Kod

- `scripts/eval/benchmark.py:1-29` — postojeći pipeline i zabrana LLM poziva iz tog modula.
- `scripts/eval/benchmark.py:106-120` — postojeći analyst/judge runbook ugovor i result shape.
- `scripts/eval/benchmark.py:260-337` — stabilni `run_id`, matrix spec i manifest format.
- `scripts/eval/benchmark.py:743-833` — manifest kao izvor istine za ingest i postojeći result format.
- `scripts/eval/benchmark.py:846-1008` — jedini postojeći put za blind/future-visible/revealed snapshot generisanje.
- `scripts/eval/ground_truth_cases.py:157-240` — private answer loader i potpuna validacija ground-truth skupa.
- `scripts/eval/scoring.py:362-406` — sanitizovan judge payload i obavezne judge dimenzije.
- `scripts/mcp/portfolio_store.py:99-137` — atomski JSON upis i POSIX lock obrazac.
- `scripts/mcp/scanner_server.py:390-415` — `asyncio.Semaphore` + per-item exception obrazac za kontrolisanu konkurentnost.
- `tests/test_benchmark.py:314-358` — offline manifest i ingest round-trip test stil.
- `tests/test_benchmark.py:427-495` — idempotent snapshot ensure i manifest-source-of-truth testovi.
- `skills/wyckoff-trader-skill/SKILL.md:40-99` — response mode i scenario sadržaj koji analyst prompt mora preneti bez davanja pristupa ostatku repo-a.

### Zvanična dokumentacija

- [Claude Code: programmatic/headless mode](https://code.claude.com/docs/en/headless)
  - `KEY_INSIGHT`: `-p`, `--bare`, `--json-schema`, eksplicitni tools i non-persistent session podržavaju deterministički adapter.
  - `APPLIES_TO`: Claude adapter i preflight capability check.
  - `GOTCHA`: `--bare` ne učitava CLAUDE.md, MCP, hooks ni memoriju; potreban analyst/judge prompt mora biti eksplicitno prosleđen.
- [Claude Code: custom subagents](https://code.claude.com/docs/en/sub-agents)
  - `KEY_INSIGHT`: svež kontekst nije isto što i filesystem izolacija; proces normalno počinje u prosleđenom cwd-u i tool/permission granice moraju biti eksplicitne.
  - `APPLIES_TO`: odluka da se koriste zasebni top-level `claude -p` procesi, a ne nested subagent prompt.
  - `GOTCHA`: implicitno lokalno podešavanje može proširiti pristup; zato koristiti bare/no-session režim i allowlist alata.
- [Codex CLI reference: `codex exec`](https://developers.openai.com/codex/cli/reference#command-details)
  - `KEY_INSIGHT`: non-interactive `exec` podržava `--model`, `--cd`, `--sandbox`, `--output-schema`, `--json` i `--ephemeral`.
  - `APPLIES_TO`: Codex adapter, structured output i usage parser.
  - `GOTCHA`: verzijski capability preflight mora da odbije nepodržane flagove pre skupih poziva.
- [Codex sandbox and approvals](https://developers.openai.com/codex/agent-approvals-security#sandbox-and-approvals)
  - `KEY_INSIGHT`: sandbox ograničava tehničke mogućnosti, dok approval policy upravlja pitanjima; za automatizaciju oba moraju biti eksplicitna.
  - `APPLIES_TO`: read-only analyst runtime i bezmrežni/no-write profil.
  - `GOTCHA`: sam `--cd` nije bezbednosna garancija; testirati efektivni root/sandbox i ne prosleđivati answer-key putanju analyst procesu.
- [Codex reasoning effort config](https://developers.openai.com/codex/config-basic#reasoning-effort)
  - `KEY_INSIGHT`: effort se prosleđuje kao `model_reasoning_effort` konfiguracija kada model to podržava.
  - `APPLIES_TO`: mapiranje benchmark effort-a u Codex CLI argv.

## Patterns to Mirror

| Kategorija | File:Lines | Obrazac | Stvarni snippet |
|---|---|---|---|
| NAMING | `scripts/eval/benchmark.py:260-313` | Deterministički identitet run-a | `run_id = f"{case_id}__{time_mode}__{anon_mode}__{model}__{effort}"` |
| FLOW | `scripts/eval/benchmark.py:743-756` | Manifest je izvor spec-a | `specs[run["run_id"]] = {key: run[key] for key in _SPEC_KEYS}` |
| ERRORS | `scripts/eval/ground_truth_cases.py:203-224` | Precizna validacija sa `case_id` kontekstom | `raise ValueError(f"{case_id} missing answer key entry")` |
| SECURITY | `scripts/eval/scoring.py:369-389` | Allowlist + rekurzivna sanitizacija judge input-a | `if str(key) in ANALYSIS_OUTPUT_ALLOWED_KEYS` |
| PERSISTENCE | `scripts/mcp/portfolio_store.py:103-122` | Temp fajl, flush, fsync, `os.replace` | `os.replace(tmp_path_str, path)` |
| LOCKING | `scripts/mcp/portfolio_store.py:125-137` | Ekskluzivni sidecar lock | `fcntl.flock(fd, fcntl.LOCK_EX)` |
| CONCURRENCY | `scripts/mcp/scanner_server.py:402-415` | Semaphore i izolovan rezultat/greška po stavci | `semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)` |
| TESTS | `tests/test_benchmark.py:335-358` | `tmp_path` end-to-end round trip bez pravog provider-a | `report = benchmark.ingest(results_dir, base_dir=tmp_path)` |

## Files to Change

| Akcija | Putanja | Odgovornost |
|---|---|---|
| Add | `scripts/eval/orchestrator.py` | CLI, preflight, plan/filter, state machine, scheduling, resume, završni ingest/summary |
| Add | `scripts/eval/runtime_adapters.py` | Provider-neutral protokol, Claude/Codex argv, subprocess izvršavanje, structured output/usage parsing, timeout/error tipovi |
| Add | `scripts/eval/schemas/analysis_output.schema.json` | Jedini strukturisani analyst output ugovor |
| Add | `scripts/eval/schemas/judge_verdict.schema.json` | Jedini strukturisani judge output ugovor, usklađen sa scoring dimenzijama |
| Modify | `scripts/eval/benchmark.py` | Uske javne helper funkcije/validacija za custom matricu i manifest reuse; ukloniti zastarelu tvrdnju da samo runbook poziva modele, bez premeštanja scoring/snapshot/report logike |
| Add | `tests/test_eval_orchestrator.py` | State transition, dry-run, resume, partial failure, selector, concurrency/rate-limit i ingest orchestration testovi |
| Add | `tests/test_runtime_adapters.py` | Tačan argv/cwd/tool/sandbox/schema ugovor i parser/error testovi bez pravih model poziva |
| Add | `runbooks/faza-4-eval-orchestrator.md` | Operator quickstart, konfiguracija, dry-run, real run, resume, statusi, failure recovery i anti-leakage granice |

Ne menjati niti brisati postojeće korisničke izmene u `CLAUDE.md`, `.claude/PRPs/`, `.claude/pregled-logike/` ili `scripts/eval/ISSUE_BODY.md`.

## NOT Building

- Ne generisati, dopunjavati niti kurirati `ground_truth_answers.json`; ljudska kuracija ostaje zaseban korak.
- Ne menjati Wyckoff rubriku, dimenzije scoring-a, ROI računanje, snapshot anonimizaciju ili report format.
- Ne praviti drugi trajni state u skill-u, shell skripti ili provider procesu.
- Ne koristiti in-process Claude/Codex SDK u ovoj iteraciji; lokalni CLI adapteri su tanji i već proverljivo dostupni.
- Ne koristiti nested subagenta kao anti-leakage garanciju.
- Ne uvoditi distribuirani queue, bazu podataka, remote worker-e, web UI ili multi-host locking.
- Ne automatizovati auth, kupovinu kredita, izbor „najboljeg” modela ili fallback na drugi model bez eksplicitne konfiguracije.
- Ne omogućavati analyst-u MCP, mrežu, repo root, answer key ili judge payload.
- Ne obećavati prenosivost aktivnog POSIX lock-a na Windows; projekat i provereni runtime su macOS/POSIX.

## Step-by-Step Tasks

### Task 1 — Zaključati JSON ugovore za analyst i judge

- **Action:** Dodati dve JSON Schema datoteke i učiniti ih jedinim structured-output ugovorima adaptera.
- **File:** `scripts/eval/schemas/analysis_output.schema.json`, `scripts/eval/schemas/judge_verdict.schema.json`.
- **Implementation:** Analyst schema mora zahtevati najmanje `direction`, numeričke ili null `trigger`/`invalidation`, `confidence`, `structure`, `phase` i `event`, uz `additionalProperties: false`. Dozvoljene direction vrednosti uskladiti sa `scoring.py`. Judge schema mora zahtevati svaki element `JUDGE_DIMENSION_NAMES`; svaka dimenzija sadrži brojčani `score` u postojećem opsegu i neprazni `rationale`. Ne unositi chart, candles, path ili answer-key putanje u analyst schema-u.
- **Pattern to mirror:** `scripts/eval/benchmark.py:106-119`, `scripts/eval/scoring.py:392-406`, `tests/test_scoring.py:223-247`.
- **Imports/types:** Nema Python importa; JSON Schema Draft 2020-12.
- **Gotchas:** Schema mora odgovarati stvarnom `combine_scores` očekivanju, ne samo prompt tekstu. `null` za trigger/invalidation mora ostati moguć za opravdani wait case.
- **Validation:** `uv run python -c 'import json; from pathlib import Path; [json.loads(p.read_text()) for p in Path("scripts/eval/schemas").glob("*.json")]' && uv run --extra mcp pytest -q tests/test_scoring.py`.

### Task 2 — Implementirati provider-neutral runtime adaptere

- **Action:** Dodati adapter protokol i Claude/Codex implementacije koje samo izvršavaju jedan analyst ili judge poziv.
- **File:** `scripts/eval/runtime_adapters.py`.
- **Implementation:** Definisati `RuntimeRequest`, `RuntimeResponse`, `RuntimeError`/`RuntimeUnavailable` i `RuntimeAdapter` protokol. Koristiti argument listu, `shell=False`, stdin za prompt, eksplicitni `cwd`, timeout i kontrolisani env allowlist. Claude analyst: `claude --bare -p --model ... --effort ... --json-schema ... --output-format json --no-session-persistence --permission-mode dontAsk --tools Read`; judge: isti fresh-process profil sa Opus modelom i `--tools ""`. Codex analyst: `codex exec - --model ... --cd ... --sandbox read-only --ephemeral --ignore-user-config --output-schema ... --json -c model_reasoning_effort=...`; ne koristiti Codex za judge u v1. Parsirati structured output i usage iz provider envelope-a, sačuvati samo bounded stderr tail i exit metadata. Preflight proverava binarni fajl, verziju, tražene flagove i mapiranje model/effort vrednosti.
- **Pattern to mirror:** eksplicitni exception tipovi u `scripts/mcp/market_data_client.py:43-65`; per-item error capture u `scripts/mcp/scanner_server.py:390-415`.
- **Imports/types:** `asyncio`, `dataclasses`, `json`, `os`, `pathlib.Path`, `shutil`, `typing.Protocol`; koristiti `asyncio.create_subprocess_exec`, ne shell string.
- **Gotchas:** Ne nasleđivati proizvoljan `CLAUDE.md`, MCP config, hooks, user config ili session istoriju. Ne logovati prompt jer judge prompt sadrži private answer. Claude `--bare` zahteva eksplicitno prosleđen kontekst/auth; auth nedostupnost je preflight greška, ne silent skip. Codex effort ide kroz config override, ne izmišljeni `--effort` flag.
- **Validation:** `uv run --extra mcp pytest -q tests/test_runtime_adapters.py -k 'argv or parse or preflight or timeout or redaction'`.

### Task 3 — Dodati atomski state store i recovery semantiku

- **Action:** U orkestratoru implementirati trajno stanje, claim i validne state prelaze po `run_id`.
- **File:** `scripts/eval/orchestrator.py`.
- **Implementation:** U `<base_dir>/_benchmark/orchestrator_state.json` čuvati `schema_version`, `manifest_fingerprint`, `updated_at`, i mapu run zapisa sa `status`, `stage`, `attempt`, `provider`, `started_at`, `finished_at`, `error`. Koristiti sidecar `fcntl` lock i temp+fsync+`os.replace`. Dozvoljeni terminalni statusi su `succeeded`, `failed`, `skipped`; `running` u sebi nosi `stage=analyst|judge`. Na startu reconcile: validan kompletan result → `succeeded`; analyst checkpoint bez judge-a → `pending` sa `next_stage=judge`; stale `running` bez checkpoint-a → `pending`; nevalidan/corrupt result → `failed` sa dijagnostikom, bez brisanja. Manifest fingerprint mismatch mora zaustaviti real run i tražiti novu state datoteku ili eksplicitni `--reset-state`; nikad tiho pridružiti staro stanje novoj matrici.
- **Pattern to mirror:** `scripts/mcp/portfolio_store.py:99-137`; stabilni manifest spec iz `scripts/eval/benchmark.py:743-756`.
- **Imports/types:** `contextlib.contextmanager`, `datetime`, `fcntl`, `hashlib`, `json`, `os`, `tempfile`, `TypedDict`/dataclasses.
- **Gotchas:** State update i result checkpoint su dva fajla; recovery mora biti projektovan za prekid između njih. `--reset-state` ne briše uspešne result fajlove; prvo ih reconciles ili zahteva posebnu eksplicitnu cleanup operaciju koja nije deo ovog issue-a.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py -k 'state or claim or stale or fingerprint or corrupt or atomic'`.

### Task 4 — Implementirati preflight, matrix config, selektore i pravi dry-run

- **Action:** Napraviti CLI plan fazu koja ništa skupo ne izvršava i ne menja postojeći execution state.
- **File:** `scripts/eval/orchestrator.py`, uska izmena `scripts/eval/benchmark.py` po potrebi.
- **Implementation:** CLI podržava `--answers-path`, `--base-dir`, ponovljivi/CSV `--case`, `--model`, `--effort`, `--max-concurrency`, `--min-start-interval`, `--max-attempts`, `--timeout`, `--dry-run`, `--resume`, `--no-ingest` i provider model mapiranje za generički `codex` matrix id. Preflight poziva `load_answer_key` + `validate_event_coverage`, proverava snapshot/answer-key putanje, schema-e i provider capabilities. Matrix filtrirati pre state inicijalizacije, ali zadržati deterministički `run_id`. `--dry-run` ne sme zvati `ensure_snapshots`, provider subprocess niti pisati/menjati manifest, state ili results; ispisuje JSON/text rezime planned/already-succeeded/retry/skipped/unavailable i razlog po grupi. Za potpuno offline fixture preview dodati eksplicitni test-only dependency injection, ne automatski placeholder ground truth u real CLI putu.
- **Pattern to mirror:** `scripts/eval/benchmark.py:1016-1087` za argparse/CSV i `scripts/eval/ground_truth_cases.py:157-240` za validaciju.
- **Imports/types:** `argparse`, `collections.Counter`, `pathlib.Path`; reuse `benchmark.RunSpec` i `BENCHMARK_MATRIX`.
- **Gotchas:** Postojeći `benchmark --dry-run` znači stub snapshot build; novi orchestrator `--dry-run` mora po issue-u biti preview bez mreže/modela i bez mutacije realnog stanja. Nedostupan `claude-fable-5` se prikazuje kao `skipped/unavailable`, ne kao prazni success.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py -k 'dry_run or selector or preflight or unavailable'`.

### Task 5 — Izgraditi anti-leakage runtime root i prompt boundary

- **Action:** Pre svakog poziva napraviti minimalni privremeni root i eksplicitne promptove za analyst/judge.
- **File:** `scripts/eval/orchestrator.py`.
- **Implementation:** Analyst root kreirati pod sistemskim temp direktorijumom, kopirati samo fajlove iz `spec.snapshot_dir` i analyst schema-u, odbiti symlink/path escape, ne kopirati answer key. Analyst prompt sastaviti u controller-u od stabilnih eval instrukcija i potrebne Wyckoff skill discipline; prompt imenuje samo relativne case fajlove. Judge payload dobiti isključivo preko `scoring.prepare_judge_input(analysis_output, answer_key)`; judge dobija zaseban prazan temp root sa judge schema-om, bez chart/candles/case putanje i bez alata. Posle procesa ukloniti temp root u `finally`; u debug režimu dozvoliti samo redigovan metadata dump, nikad private payload.
- **Pattern to mirror:** allowlist sanitizacija `scripts/eval/scoring.py:362-389`; snapshot file contract `scripts/eval/snapshot_builder.py:193-220`; skill disciplina `skills/wyckoff-trader-skill/SKILL.md:40-99`.
- **Imports/types:** `shutil`, `tempfile`, `pathlib.Path`; helper funkcije koje vraćaju context manager.
- **Gotchas:** Svež kontekst nije fizička izolacija. `cwd` nije dovoljan bez tool/sandbox ograničenja. Future-visible `instruction.txt` mora biti uključen; absolute paths iz spec-a ne smeju u prompt/output. Chart ostaje dostupan analyst-u kao lokalni fajl, ali nikad judge-u.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py tests/test_runtime_adapters.py -k 'isolation or root or symlink or judge or leakage or prompt'`.

### Task 6 — Implementirati scheduler, checkpoint, resume i rate limiting

- **Action:** Spojiti state store i adaptere u kontrolisani end-to-end tok.
- **File:** `scripts/eval/orchestrator.py`.
- **Implementation:** Koristiti `asyncio.Semaphore(max_concurrency)` i jedan monotonic start limiter koji garantuje `min_start_interval` između provider startova. Svaki worker atomski claim-uje run. Ako nema analyst checkpoint: pokrenuti analyst, validirati schema-u, atomski upisati `results/<run_id>.json` sa `analysis_output`, `usage`, `judge_verdict: null`, pa state prebaciti u judge stage. Zatim lokalno učitati private answer, pozvati `prepare_judge_input`, pokrenuti svež Opus judge, validirati verdict, dopuniti isti result atomski i tek potom označiti `succeeded`. Exception pripada samo tom run-u, povećava attempt i čuva stage/error; ostali taskovi nastavljaju. Resume preskače validne successes, nastavlja judge-only checkpoint i retry-uje failed do `max_attempts`; posle limita ostavlja terminalni `failed`. SIGINT/SIGTERM zaustavlja nove claims, čeka/prekida decu sa timeout-om i ostavlja reconciliation-u siguran nastavak.
- **Pattern to mirror:** `scripts/mcp/scanner_server.py:402-415` za semaphore/per-item failure i `scripts/mcp/portfolio_store.py:103-137` za trajnost.
- **Imports/types:** `asyncio`, `signal`, `time`; `RuntimeAdapter` protokol za fake test adaptere.
- **Gotchas:** Ne držati file lock tokom model poziva. Analyst i judge usage zbir čuvati bez menjanja postojećeg top-level `usage` oblika koji ingest očekuje; ako se čuva detalj po stage-u, derivirati kompatibilan total. Jedan failure ne sme otkazati `asyncio.gather` za sve run-ove.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py -k 'resume or checkpoint or partial or concurrency or rate_limit or max_attempts or interrupt'`.

### Task 7 — Zatvoriti tok postojećim ingest/report ugovorom i operator rezimeom

- **Action:** Nakon scheduler-a pozvati postojeći ingest i vratiti jasan exit status/summary.
- **File:** `scripts/eval/orchestrator.py`, eventualno uska javna validaciona helper izmena u `scripts/eval/benchmark.py`.
- **Implementation:** Ako postoji bar jedan kompletan result i `--no-ingest` nije zadat, pozvati `benchmark.ingest(results_dir, base_dir=...)`; ne reimplementirati `score_run`, `aggregate_report` ili `write_report`. Ispisati ukupne `succeeded/failed/skipped/pending`, attempt count, result/state/report putanje i listu neuspešnih `run_id` sa stage-om. Exit `0` samo kada nema terminalnih failed/pending run-ova u selektovanom scope-u; poseban non-zero za preflight/config, partial failures i interrupt. Ingest failure se beleži kao orchestration-level greška i ne menja već uspešne run statuse.
- **Pattern to mirror:** `scripts/eval/benchmark.py:791-833`.
- **Imports/types:** reuse `benchmark.ingest`; bez novih scoring tipova.
- **Gotchas:** Selector run ne sme lažno tvrditi da je cela matrica završena. Report se gradi iz svih kompletnih results poznatih manifestu, dok CLI summary jasno označava trenutni selektovani scope.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py tests/test_benchmark.py -k 'ingest or summary or exit_code or report or manifest'`.

### Task 8 — Dokumentovati i validirati operator workflow

- **Action:** Dodati srpski runbook i kompletan test paket bez pravih naplativih poziva.
- **File:** `runbooks/faza-4-eval-orchestrator.md`, `tests/test_eval_orchestrator.py`, `tests/test_runtime_adapters.py`.
- **Implementation:** Runbook mora sadržati prerequisites (private answer path, auth, lokalne CLI capability komande), obavezni `--dry-run`, mali real canary sa jednim case/model/effort izborom, pun run, `--resume`, status/result/report lokacije, kako se tumače `failed/skipped`, anti-leakage pretnje i činjenicu da ground truth nije generisan. Testovi koriste fake subprocess/adapter i `tmp_path`; nijedan standardni test ne sme zvati mrežu ili model. Dodati opt-in manual smoke proceduru koja proverava real Claude/Codex structured output i da canary fajl van runtime root-a nije dostupan; ona nije deo default pytest-a jer ima trošak/auth zavisnost.
- **Pattern to mirror:** srpski operator dokumenti i `tests/test_benchmark.py:314-358` offline stil.
- **Imports/types:** `pytest`, fake adapter fixtures, `monkeypatch`, `tmp_path`.
- **Gotchas:** Dokumentacija mora navesti proverene, a ne pretpostavljene flagove za Claude `2.1.183` i Codex `0.141.0`, uz preflight kao zaštitu od budućih CLI promena. Ne stavljati private answer sadržaj u primere ili fixture-e.
- **Validation:** `uv run --extra mcp pytest -q tests/test_eval_orchestrator.py tests/test_runtime_adapters.py tests/test_benchmark.py tests/test_ground_truth_cases.py tests/test_scoring.py tests/test_snapshot_builder.py && uv run ruff check scripts/eval tests/test_eval_orchestrator.py tests/test_runtime_adapters.py` ako je `ruff` dostupan; u suprotnom zabeležiti da projekat nema konfigurisan lint alat i izvršiti `uv run python -m compileall -q scripts/eval`.

## Testing Strategy

### Unit testovi

- Schema validacija: validan wait output; nevalidna direction; nedostajuća judge dimenzija; dodatna leakage polja.
- Provider argv: bez shell-a, tačan cwd, model/effort, bare/ephemeral, tool/sandbox i schema flagovi.
- Provider parser: success envelope, malformed JSON, non-zero exit, timeout, missing usage i stderr redaction.
- State machine: svaki dozvoljeni prelaz i odbijanje nevalidnog prelaza.
- Atomic persistence: simuliran prekid pre `os.replace` ne kvari prethodno stanje/result.
- Manifest fingerprint i stale-running reconciliation.

### Integracioni testovi sa fake adapterom

- Jedan run analyst → judge → result → postojeći ingest/report.
- Analyst failure ne zaustavlja drugi run.
- Judge failure čuva analyst checkpoint; `--resume` ne poziva analyst drugi put.
- Prekid posle result upisa, pre state success-a, reconciles u `succeeded`.
- Validni success se preskače; corrupt result ne proglašava success.
- `max_concurrency` se nikad ne prelazi; start vremena poštuju `min_start_interval`.
- Case/model/effort selektori daju deterministički scope.
- `--dry-run` ne poziva adapter, ne generiše snapshot i ne menja manifest/state/results mtimes.
- Judge request nema chart/candle/path i koristi Opus provider konfiguraciju.

### Regresioni testovi

- Sadašnjih 54 testova u `test_benchmark`, `test_ground_truth_cases`, `test_scoring`, `test_snapshot_builder` ostaje zeleno.
- Existing `benchmark.ingest` i report format ostaju nepromenjeni.
- Offline benchmark preview i dalje daje 10 blind + 10 future-visible + 10 revealed snapshotova i 180 run-ova.

### Opt-in real runtime smoke

- Jedan Claude analyst + Opus judge run nad testnim/dry fixture case-om, uz eksplicitnu operator potvrdu troška.
- Jedan Codex analyst run kada je konkretan Codex model mapiran.
- Canary test dokazuje da analyst ne može da pročita fajl van privremenog root-a; ako lokalni CLI/sandbox verzija ne garantuje ovu granicu, real run mora fail-closed (zatvoren neuspeh), ne degradirati na prompt-only izolaciju.

## Validation Commands

```bash
# 1. Plan artifact i bez placeholder-a
test -f PRPs/plans/faza-4-end-to-end-eval-orchestrator.plan.md
! rg -n 'TO[D]O:|TB[D]:|PLAC[E]HOLDER:' PRPs/plans/faza-4-end-to-end-eval-orchestrator.plan.md

# 2. Postojeća potvrđena osnova
uv run --extra mcp pytest -q \
  tests/test_benchmark.py \
  tests/test_ground_truth_cases.py \
  tests/test_scoring.py \
  tests/test_snapshot_builder.py

# 3. Novi ciljani testovi posle implementacije
uv run --extra mcp pytest -q \
  tests/test_eval_orchestrator.py \
  tests/test_runtime_adapters.py

# 4. Ceo relevantni eval paket
uv run --extra mcp pytest -q \
  tests/test_eval_orchestrator.py \
  tests/test_runtime_adapters.py \
  tests/test_benchmark.py \
  tests/test_ground_truth_cases.py \
  tests/test_scoring.py \
  tests/test_snapshot_builder.py

# 5. Statička sintaksna provera bez dodatne zavisnosti
uv run python -m compileall -q scripts/eval

# 6. Capability preflight bez model poziva
claude --version
claude --help | rg -- '--bare|--model|--effort|--json-schema|--no-session-persistence'
codex --version
codex exec --help | rg -- '--model|--cd|--sandbox|--output-schema|--ephemeral'

# 7. Orchestrator preview — ne poziva model/mrežu i ne menja execution state
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 \
  --model claude-opus-4-8 \
  --effort high \
  --dry-run

# 8. Mali real canary tek posle pregleda preview-a i eksplicitne potvrde troška
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 \
  --model claude-opus-4-8 \
  --effort high \
  --max-concurrency 1 \
  --min-start-interval 2
```

## Acceptance Criteria

- [ ] Jedna dokumentovana `python -m scripts.eval.orchestrator` komanda vodi validaciju, snapshot/matrix reuse, analyst, judge, result, ingest i report tok.
- [ ] `--dry-run` ne poziva mrežu/model, ne generiše ground truth i ne menja postojeće execution state/results fajlove.
- [ ] Svaki selektovani `run_id` ima trajni status, stage, attempt i strukturisanu grešku.
- [ ] Procesni prekid se bezbedno nastavlja; validni successful run se ne ponavlja.
- [ ] Judge failure posle uspešnog analyst-a nastavlja samo judge fazu.
- [ ] Neuspeh jednog run-a ne briše niti zaustavlja ostale rezultate.
- [ ] Operator može da bira case/model/effort, konkurentnost, minimalni start interval, timeout i max attempts.
- [ ] Analyst runtime dobija samo case kopiju + schema-u u privremenom root-u; nema answer key, repo root, mrežu ili MCP.
- [ ] Judge je svež Opus runtime nad `prepare_judge_input` payloadom, bez chart/candles/path i bez alata.
- [ ] Postojeći `benchmark.ingest` generiše isti `report.md` i `report.json` format.
- [ ] Nedostupan model/provider dobija eksplicitni `skipped` ili preflight failure sa razlogom; nema silent success-a.
- [ ] Postojećih 54 ciljanih eval testova i novi orchestration/recovery testovi prolaze.

## Completion Checklist

- [ ] Svi taskovi implementirani redom i svaki validation command prolazi.
- [ ] Nema duplirane snapshot, scoring, ingest ili reporting logike.
- [ ] State/result upisi su atomski i testirani simuliranim prekidom.
- [ ] Manifest fingerprint štiti resume od pogrešne matrice.
- [ ] Provider komandne linije koriste argv liste i `shell=False`.
- [ ] Promptovi, stderr i state greške ne otkrivaju private ground truth.
- [ ] Default testovi ne pozivaju mrežu niti naplative modele.
- [ ] Runbook sadrži dry-run pre real run-a i mali canary pre pune matrice.
- [ ] Duboki review pokriva runtime/skill granicu i anti-leakage tvrdnje pre merge-a, po `CLAUDE.md:54-68`.
- [ ] Nema `TODO`, `TBD`, placeholder-a ili skrivenih odluka koje implementator mora da pogađa.

## Risks and Mitigations

| Rizik | Verovatnoća / uticaj | Mitigacija |
|---|---|---|
| `cwd` se pogrešno tretira kao fizička izolacija | M / kritičan | Privremeni case-only root + bare/ignore-user-config + restrictive tools/sandbox + canary test; fail-closed ako provider ne može da potvrdi granicu |
| CLI flag/output format se promeni | M / visok | Verzijski capability preflight, adapter testovi nad stvarnim `--help`, jasna `RuntimeUnavailable` greška |
| Prekid između result i state upisa | M / visok | Atomski upisi + startup reconciliation gde validan result ima dokaznu prednost |
| Judge retry ponovi skupi analyst | M / visok | Analyst checkpoint pre judge poziva i `next_stage=judge` recovery |
| Concurrent workers prepišu state/result | L / visok | Kratak POSIX lock oko claim/state write-a; jedinstveni owner po run-u; temp+fsync+replace |
| Private answer procuri kroz log/error | L / kritičan | Judge prompt se ne loguje; bounded/redacted stderr; answer key se učitava tek posle analyst-a i nikad ne ulazi u analyst request |
| Nedostupan Fable ili nejasan Codex model alias | H / srednji | Preflight + eksplicitna provider/model mapa; status `skipped/unavailable`, bez automatskog fallback-a |
| Rate limit i trošak pune matrice | M / visok | Obavezni preview, selectors, max concurrency, monotonic start limiter i mali canary |
| Dry-run slučajno mutira manifest/state | L / visok | Plan/render put pre svih write funkcija; mtime/no-subprocess test |
| Result schema drift razbije ingest | M / visok | JSON schema + postojeći ingest round-trip regresioni test; zadržati top-level result shape |

## Notes

- Presuda je pročitana u celosti i tretirana kao obavezujuća. Ključna posledica je da eventualni budući skill može biti samo tanak wrapper koji poziva ovu CLI komandu; nije deo ove isporuke i ne poseduje stanje.
- External research je ograničen na zvanične Claude Code i OpenAI Codex izvore, uz lokalnu proveru instaliranih CLI verzija i flagova 2026-06-19.
- Početna validacija tokom planiranja: `54 passed in 3.75s`; offline preview: 30 snapshotova i 180 run-ova, bez mreže/model poziva.
- Postojeći worktree nije čist. `CLAUDE.md` je izmenjen, a više `.claude/PRPs/`, `.claude/pregled-logike/` i `scripts/eval/ISSUE_BODY.md` artefakata je untracked; implementator ih mora sačuvati i ne uključivati u scope issue-a #73.
- Plan ne menja Faza 4 PRD status jer je ulaz GitHub issue, ne PRD faza.
- Preporučeni sledeći korak posle pregleda plana: `$prp-implement PRPs/plans/faza-4-end-to-end-eval-orchestrator.plan.md`.
