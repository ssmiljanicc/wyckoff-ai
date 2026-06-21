# Pregled Logike — PR #74 `feat: add end-to-end evaluation orchestrator`

**Datum**: 2026-06-20
**Scope**: PR #74 — orkestrator za Faza 4 eval benchmark (`scripts/eval/orchestrator.py`, `runtime_adapters.py`, šeme, izmene u `benchmark.py`, testovi, runbook)

---

## Zaključak eksperta

Ideja je zdrava i nedostajala je: `benchmark.py` je namerno nikad ne zove model (priprema matricu i skoruje), pa je orkestrator tačno taj nedostajući izvršni sloj koji spawn-uje izolovane analyst/judge procese, atomski checkpointuje i vraća se u postojeći `ingest`. Za skup koji troši **naplative** i spore LLM pozive preko matrice od desetina runova, crash-safety + resume + idempotencija + cost-preflight su opravdani — to nije over-engineering, to je adekvatan odgovor na cenu i trajanje posla.

Najveći logički propust nije u state mašini nego u **premisi izolacije analyst-a**: analyst za Claude se spawn-uje sa `--tools ""` (runbook izričito kaže „provider nema alate"), ali se snapshot isporučuje *kao fajlovi u cwd-u*, a prompt samo **nabraja imena fajlova** — sadržaj se nigde ne inline-uje. Ako Claude proces nema Read alat, on fizički ne može da otvori `candles.json`. Cео offline test paket koristi `FakeAdapter` koji vraća gotov odgovor bez obzira na prompt, a real canary po priznanju PR-a nije pokrenut — dakle baš ovaj, najskuplji i najvažniji put (da li analyst uopšte vidi podatke koje skorujemo?) je neproveren.

Najveća nepotrebna kompleksnost je blaga: dvostruko građenje matrice (in-memory pa ponovo iz manifesta) i `file_lock` koji štiti scenario dva paralelna procesa kakav single-process asyncio orkestrator realno nema. Ništa od toga ne ruši sistem — to su mesta za pojednostavljenje, ne za prepravku.

**Ocene:**
| Dimenzija | Ocena | Ukratko |
|-----------|-------|---------|
| Zdravlje ideje | 8/10 | Nužan izvršni sloj iznad code-only pipeline-a; minus za neproverenu premisu isporuke podataka analyst-u |
| Logički tok | 7/10 | Koherentan i pažljiv (reconcile, fingerprint, resume); minus za analyst-read gap, dvostruki build i polu-mrtav `max_attempts` u jednom pozivu |
| Opravdanost kompleksnosti | 7/10 | Robusnost opravdana profilom posla; blagi višak (flock, stage/next_stage dualitet, dupli build) |

---

## Nivo 1 — Ideja i Premisa

**Šta sistem zapravo radi:** Spawn-uje izolovane CLI procese (Claude/Codex za analyst-a, Opus za sudiju) po svakom redu eval matrice, validira njihov strukturisani JSON izlaz protiv šema, atomski čuva checkpoint po runu radi sigurnog nastavka, pa pušta postojeći `benchmark.ingest` da skoruje i napravi izveštaj.

**Pretpostavke koje sistem uzima zdravo za gotovo:**
- CLI flagovi (`--bare`, `--effort`, `--json-schema`, `--no-session-persistence`, `--tools`, odnosno `--sandbox`, `--output-schema`, `--ephemeral`) postoje i ponašaju se kako se očekuje → **delimično pokriveno**: `_require_capabilities` proverava prisustvo flaga u `--help` tekstu (dobro), ali prisustvo flaga ne garantuje semantiku.
- Izolovani analyst zaista ne može do mreže/MCP/parent putanja → **pokriveno za Codex** (`--sandbox read-only --cd`), **slabije za Claude** (oslonac na `--tools ""` + prompt; nema OS sandbox-a, proces i dalje ima FS i env korisnika).
- **Analyst dobija podatke koje treba da analizira** → **NE drži za Claude config** (vidi rupu ispod) — i to je neprovereno za oba providera jer testovi koriste `FakeAdapter`.
- Judge ne treba pristup fajlovima → drži: judge dobija payload kroz stdin (`prepare_judge_input`), `judge_root` sadrži samo šemu. Konzistentno.

**Rupe u premisi:**

### Isporuka snapshot podataka analyst-u (Claude путем) je neusklađena sa „bez alata"
**Problem**: `analyst_prompt` kaže „read only the files in the current directory: <imena>" i nabraja fajlove, ali nigde ne ubacuje njihov **sadržaj** u prompt. Za Claude `build_argv` ide sa `--tools ""` (i runbook §Anti-leakage to potvrđuje: „provider nema alate"). Bez Read alata Claude proces ne može da otvori `candles.json` — dobija spisak imena bez načina da ih pročita. Za Codex put je verovatniji jer `--sandbox read-only` dozvoljava čitanje iz sandbox-a, pa nastaje i asimetrija ponašanja između providera.
**Posledica**: Claude analyst potencijalno „analizira" bez ijednog podatka — vraća halucinaciju koja prođe šemu i biva skorovana kao validan rezultat. Skup, naplativ run koji meri šum. Offline testovi ovo ne hvataju (`FakeAdapter`), canary nije pokrenut.
**Uticaj**: visok

### Izolacija analyst-a za Claude je „best-effort", ne sandbox
**Problem**: Runbook §2 i sam traži da operator ručno proveri da canary fajl van temp root-a nije dostupan, i da prekine run ako CLI/sandbox kombinacija ne garantuje granicu. To znači da granica zavisi od instalirane verzije CLI-ja, a ne od koda u ovom PR-u — za Claude nema OS-level sandbox-a kao kod Codex-a.
**Posledica**: Tvrdnja o izolaciji je uslovna; bez canary verifikacije ne zna se da li „anti-leakage granica" stvarno postoji za Claude.
**Uticaj**: srednji (ublažen jer runbook eksplicitno traži ručnu proveru pre punog batch-a)

---

## Nivo 2 — Logički Tok

**Tok sistema:**
1. `load_answer_key` + `validate_event_coverage` → ✓
2. in-memory `build_run_matrix` + `select_specs`, guard na prazan scope → ✓
3. instanciranje adaptera + `preflight` po modelu i sudiji → ✓
4. `--dry-run`: ispiše scope/unavailable i izađe bez pisanja → ✓ (testirano)
5. `ensure_snapshots` samo za dostupne case-ove → ✓
6. `build_matrix_manifest` (piše `benchmark_runs.json`) → re-čita specs iz manifesta → re-select → ⚠ (dupli build)
7. provera da snapshot dir i answer key postoje → ✓
8. `StateStore.initialize(selected, fingerprint_specs=all_specs)` → `reconcile` → ✓ (fingerprint nad celom matricom, ne nad subset-om — dobro za resume sa različitim `--case`)
9. označi nedostupne kao `skipped` → ✓
10. signal handleri, semaphore, `StartLimiter` → ✓
11. `gather` worker-a: `claim` → (analyst ako treba → checkpoint) → judge → checkpoint → `succeeded` → ✓
12. ako nije prekinut i ima validnih rezultata → `ingest` → report → ✓
13. ispis sažetka + exit kod (0/2/3/130) → ✓

**Propusti u toku:**

### `max_attempts` ne pokreće retry unutar jednog poziva
**Vrsta**: preskočen korak / pogrešno očekivanje
**Lokacija**: `orchestrator.py:249-287` (`execute_run`), `orchestrator.py:364-372` (`worker`/`gather`)
**Problem**: Svaki spec dobija jedan worker → jedan `execute_run` → jedan `claim` (attempt++). Na grešci, ako `attempt < max_attempts`, run se vrati na `pending`, ali worker se završava i `gather` ne petlja. Dakle u **jednom** pozivu svaki run ima tačno jedan pokušaj bez obzira na `max_attempts`; stanje `failed` (= „iscrpeo max_attempts") je praktično nedostižno u prvom pozivu — sve ostaje `succeeded`/`pending`/`skipped`. Drugi pokušaj se materijalizuje tek kad operator ponovo pokrene (`--resume`). PR opis („retry ... handling") sugeriše in-process retry kojeg nema.
**Predlog**: Ili dodati in-process retry petlju u `execute_run`/`worker` (loop dok `attempt < max_attempts` ili success), ili preimenovati/dokumentovati da je `max_attempts` brojač **preko poziva** (jedan attempt po invokaciji) — runbook §Status to delom kaže, ali kod i PR opis odaju utisak in-process retry-ja.
**Uticaj**: srednji

### Dvostruko građenje matrice i dvostruki `select_specs`
**Vrsta**: redundantan korak
**Lokacija**: `orchestrator.py:304-305` vs `334-337`
**Problem**: Matrica se gradi in-memory (`build_run_matrix`) i selektuje samo da bi se dobili jedinstveni modeli za preflight i `available_cases`; zatim se ista matrica ponovo gradi kroz `build_matrix_manifest`, pročita iz manifesta i ponovo selektuje sa istim selektorima. Oba poziva koriste iste default control modele/efforte, pa daju identičan skup.
**Predlog**: Izgraditi matricu jednom, uraditi preflight, pa `ensure_snapshots`, pa upisati manifest jednom i koristiti taj isti spec skup. Jedini razlog za redosled „preflight pre snapshot build-a" (da se ne troši na snapshot kad je CLI nedostupan) ostaje zadovoljen i sa jednim build-om.
**Uticaj**: nizak

### Sitno: šema se čita sa diska pri svakoj validaciji
**Vrsta**: neiskorišćena prilika (granično van scope-a)
**Lokacija**: `_valid_result`, `execute_run` (`json.loads(ANALYSIS_SCHEMA.read_text())` po pozivu)
**Problem**: Iste dve šeme se re-čitaju i re-parsiraju iz fajla na svakoj validaciji umesto da se učitaju jednom.
**Predlog**: Učitati šeme jednom (modul-level konstanta/cache). Čisto higijena, ne logički propust.
**Uticaj**: nizak

Pozitivno u toku (vredi reći jer su to mesta gde se lako pogreši): `fingerprint_specs=all_specs` čini resume nad subset-om bezbednim; `reconcile` self-heal-uje corrupt result (redo analyst); judge faza reuse-uje postojeći analyst checkpoint; `--dry-run` dokazano ne piše state ni ne zove adaptere (test `test_dry_run_does_not_write_execution_state`).

---

## Nivo 3 — Nužnost Kompleksnosti

**Direktan put vs. stvaran put:**
- Minimalan put: za svaki run → spawn analyst → spawn judge → upiši rezultat → `ingest`. (~4 koraka, suštinski telo `execute_run`-a.)
- Trenutni put: + atomski upis, file lock, fingerprint, reconcile/state mašina, preflight, dry-run, selektori, semaphore, rate-limiter, signal handling.
- Razlika: **delimično opravdana**. ~80% dodatka je opravdano profilom posla (skup, dugotrajan, naplativ batch gde gubitak progresa = realan novac). ~20% je granično.

**Nepotrebna kompleksnost:**

### `file_lock` (flock) u single-process asyncio orkestratoru
**Vrsta**: nepotreban sloj (granično)
**Lokacija**: `orchestrator.py:64-73`, korišćen u `StateStore`
**Problem**: Sve mutacije state-a se dešavaju u jednom procesu i jednom event loop-u; kritične sekcije (read+write pod lock-om) nemaju `await`, pa se asyncio task-ovi ne preplitaju. `flock` štiti samo scenario **dva paralelna orkestrator procesa** nad istim state-om, što tok ne predviđa (resume je zaseban, sekvencijalan poziv).
**Alternativa**: Bez flock-a (atomski `os.replace` već daje konzistentnost upisa) ili zadržati ali eksplicitno dokumentovati da je jedina svrha zaštita od dva paralelna procesa. Jeftino osiguranje, pa nije must-fix.
**Uticaj**: nizak

### `stage` + `next_stage` dualitet
**Vrsta**: blaga mrtva kompleksnost
**Lokacija**: `_new_record`, `reconcile`, `claim`, `update`
**Problem**: Nose se dva polja koja se uglavnom drže sinhronizovano; `claim` koristi `next_stage or stage or "analyst"`. Za dvofazni tok (analyst→judge) jedno polje „next_stage" bi verovatno bilo dovoljno.
**Alternativa**: Jedno polje „next_stage" (ili enum trenutne pozicije) uz izvedeno „šta je sledeće". Trenutni dualitet pomaže debug-u, pa je trošak mali.
**Uticaj**: nizak

### `_safe_copy` hardening nad self-generisanim snapshot-ima
**Vrsta**: odbrambeni sloj tankog threat-modela
**Lokacija**: `orchestrator.py:178-191`
**Problem**: Symlink/path-escape zaštita štiti od malicioznog sadržaja u snapshot dir-u, a snapshot-e generiše sam benchmark iz ground-truth definicija — nije korisnički ulaz.
**Alternativa**: Zadržati (jeftino, i dobra navika za „temp root mora biti čist") — navodim radi kompletnosti, ne kao problem.
**Uticaj**: nizak

---

## Šta drži

- **Razdvajanje priprema/izvršavanje** je čista granica: `benchmark.py` nikad ne zove model, orkestrator je jedini izvršni sloj — `benchmark_runs.json` je jedinstveni izvor istine za `ingest`. Ovo je tačno mesto na kome se eval harnesovi obično zapetljaju, a ovde je disciplinovano.
- **Crash-safety dizajn je stvaran, ne kozmetički**: atomski `os.replace` + `fsync`, `reconcile` koji rekonstruiše stanje sa diska, idempotentan `claim` koji preskače `succeeded`/`running`, reuse analyst checkpoint-a u judge fazi. Test `test_atomic_write_preserves_previous_file_when_replace_fails` dokazuje da neuspeo upis ne kvari prethodni state.
- **Cost-disciplina**: preflight pre snapshot build-a, `--dry-run` koji ništa ne piše ni ne zove, eksplicitan `skipped` za nedostupne modele (nema praznih redova umesto rezultata), exit kodovi koji razlikuju config/partial/interrupt.
- **Anti-leakage namera je ispravna i delom dokazana**: judge dobija sanitizovan payload bez grafikona/candles/identiteta/putanja (`test_execute_run_checkpoints_and_isolates_judge` proverava da `candles`/`answer_key_path`/snapshot putanja nisu u judge prompt-u). Slabost je samo na analyst strani (Nivo 1), ne na judge strani.

---

## Preporučeni sledeći koraci

1. **Razrešiti analyst-read premisu pre ijednog punog runa (visok prioritet).** Pokrenuti canary po provideru i potvrditi da analyst stvarno prima podatke: za Claude `--tools ""` config — proveriti da li model uopšte može da pročita `candles.json`; ako ne može, ili inline-ovati sadržaj snapshot-a u `analyst_prompt`, ili dozvoliti minimalan read-only file alat ograničen na cwd. Bez ovoga rizikujemo skup batch koji skoruje halucinacije.
2. **Odlučiti semantiku `max_attempts`.** Ili dodati in-process retry petlju, ili preimenovati/dokumentovati da je to brojač preko poziva — i uskladiti PR opis koji sugeriše in-process retry.
3. **Ukloniti dvostruki build matrice** — izgraditi i selektovati jednom, upisati manifest jednom; sporedno učitati šeme jednom umesto po validaciji.

---
*Generisao: mk-pregled-logike-solo*
*Izveštaj: `.claude/pregled-logike/pr-74-logika-solo.md`*
