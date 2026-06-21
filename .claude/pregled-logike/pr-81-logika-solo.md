# Pregled Logike — PR #81 (issue #75) — chart_image canary + Codex ban

**Datum**: 2026-06-21
**Scope**: PR #81 `spike/issue-75-chart-image-canary` (9 fajlova, +828/−7) — spike report, 3 canary skripte, runtime fail-closed gate
**Fokus po nalogu**: proporcionalnost odgovora, ne tačnost canary-ja (canary je tačan — `cat exit_code=0` je nedvosmislen empirijski fakt)

---

## Zaključak eksperta

Ideja spike-a je zdrava i discipline je primerna: dokaži izvodljivost za nultu cenu, fail-closed na bezbednosnoj granici pre prvog plaćenog run-a. Empirijski nalaz drži — Codex `--sandbox read-only --cd` je pročitao sentinel van case root-a i vratio ga; to je realna rupa u integritetu privatnog benchmark-a.

Ali odgovor **nije proporcionalan nalazu na dva mesta**. Prvo, skok „macOS read-only --cd curi" → „zabrani Codex u celosti (i tekstualni analyst)" preskače dve logičke prečke: rezultat je **Seatbelt/macOS-specifičan** (na Linux-u Codex read-only sandbox koristi Landlock i *može* da ograniči čitanje), a **OS-nivo containment** (uid/perms, kontejner, Codex-ov vlastiti „externally sandboxed" obrazac) sadržava curenje bez ijedne zabrane. Pun ban **nije jedini izlaz** — najjeftiniji izlaz (answer key na drugom uid-u, `chmod 700`) poražava baš ovaj `cat` za par sati rada, bez ijedne izmene Codex-a.

Drugo, najveća kompleksnost nije u kodu (kod je čist) nego u **mehanizmu otključavanja**: `CODEX_PRIVATE_BENCHMARK_ISOLATION_VERIFIED = False` je goli ljudski-uređivan boolean. Flip na `True` ponovo pušta Codex *na poverenje*, bez ijedne runtime/test tvrdnje da izolacija stvarno drži. Fail-closed koji se poništava izmenom jednog karaktera uz zelene testove nije čvrst gate.

**Najvažnije za tim:** merge fail-closed stanja je u redu kao privremena sigurnosna podrazumevana vrednost — ali samo ako je upario sa otvorenim containment issue-om. Takav follow-up issue **nisam našao otvoren**. Bez njega, Faza 4 tiho postaje single-provider benchmark i cross-provider rangiranje (verovatno najvredniji deliverable) nestaje bez odluke.

**Ocene:**
| Dimenzija | Ocena | Ukratko |
|-----------|-------|---------|
| Zdravlje ideje | 8/10 | Ispravan fail-closed instinkt, zero-cost metod, konkluzivan empirijski nalaz; ali generalizuje platform-specifičan rezultat |
| Logički tok | 6/10 | Nalaz→pun-ban preskače platformu i containment; unlock je goli boolean; ime gate-a šire od dosega |
| Opravdanost kompleksnosti | 8/10 | Canary skripte dobro skroirane, dry-run default, jedan plaćeni poziv; bez over-engineeringa |

---

## Direktni odgovori na tri pitanja iz naloga

### 1. Je li pun ban jedini izlaz, ili postoji containment koji spasava Codex?

**Pun ban nije jedini izlaz. Postoje tri containment puta, od kojih je bar jedan jeftin i standardan.**

Prvo, potvrda preko `codex exec --help` (0.141.0): sve tri sandbox vrednosti — `read-only`, `workspace-write`, `danger-full-access` — kontrolišu **upis**, ne čitanje. `read-only` znači „ne piši", ne „ne čitaj van root-a". `-C, --cd` je *working root*, ne read-jail. Dakle **nijedan sandbox *mode* ne ograničava čitanje** — nalaz reporta je tačan i ne može se rešiti drugom sandbox vrednošću. Fix mora biti OS-nivo. Ali OS-nivo containment je jeftin:

- **(a) POSIX perms / zaseban uid (najveći ROI).** Answer key / judge root u vlasništvu drugog korisnika, `chmod 700`; Codex se izvršava kao korisnik koji fizički ne može da `cat`-uje taj direktorijum. Poražava *baš* nalaz canary-ja (`cat` → `Permission denied` → `exit_code≠0` → canary „outside read blocked" prolazi). Nula izmena Codex-a, sati rada, bez kontejnera.
- **(b) Eksterni sandbox (kontejner/VM).** Codex-ov *vlastiti* help eksplicitno blagoslovi ovaj obrazac: `--dangerously-bypass-approvals-and-sandbox` je „intended solely for running in environments that are externally sandboxed". Pokreni Codex u kontejneru koji mount-uje samo case root + auth fajl; „van root-a" ne postoji za proces. Standardan, dokumentovan obrazac.
- **(c) Platforma.** Nalaz je dobijen na **Darwin/Seatbelt** (`uname -s` = Darwin, report navodi CLI 0.141.0/gpt-5.4 ali ne navodi da je rezultat platform-vezan). Na Linux-u Codex sandbox koristi **Landlock**, koji *može* da ograniči čitanje na workspace. Postojanje opt-in `sandbox_permissions=["disk-full-read-access"]` u help-u sugeriše da je puni read pristup ponegde *dodatna dozvola*, ne default. Benchmark host na Linux-u je moguće da dobije read-confinement nativno.

Report parcijalno priznaje ovo („dok se ne uvede stvarna filesystem izolacija") — ali naslov, `Closes #75` i enforcement čitaju se kao kategorično „Codex ne može da se izoluje", dok je precizno stanje „Codex-ov *default sandbox na macOS* ne ograničava čitanje, a OS-granicu još nismo ožičili".

### 2. Je li ban tekstualnog analyst-a proporcionalan?

**Najmanje proporcionalan deo PR-a.** Image rejection je dobro opravdan (i capability i izolacija padaju). Ban *teksta* počiva na slabijoj premisi — samo na deljenom sandbox profilu — a baš text-mode je **najlakši za sadržati**: `candles.json` je u promptu, Codex tekstualnom analyst-u **ne treba nijedan file-read**. Pretnja nije „pristup repo stablu" uopšteno, nego konkretno *Codex-ov shell alat čita apsolutnu putanju do ključa*.

Tvoja hipoteza „uži temp-root bez repo-pristupa" je u pravom smeru ali **sama nije dovoljna**: canary je pročitao *apsolutnu* putanju van `--cd` (`/bin/cat -- <outside_path>`), pa sužavanje cwd-a ne pomaže — Codex ne mari za cwd kad ima apsolutnu putanju. Uži temp-root radi *samo* ako ga podupire OS read-granica (perms/namespace) koja čini spoljne putanje stvarno nečitljivim. Proporcionalna text-mode mitigacija: učini ključ nečitljivim za codex uid (opcija a iznad), *ili* ukloni exec/shell vektor za text run-ove ako Codex to podržava. Pun ban provider-a je za text-mode prekomeran odgovor.

### 3. Prihvata li tim gubitak cross-provider rangiranja?

**Ovo je prava cena, i ona menja vrednost benchmark-a dovoljno da opravda containment sada, ne kasnije.** Deklarisana svrha Faze 4 je model × effort rangiranje *preko providera* (Claude vs GPT-5.4). Ban → Claude-only → pitanje „je li GPT bolji u Wyckoff analizi" — verovatno najzanimljivije — ostaje neodgovoreno. Pošto su containment fix-evi jeftini (uid/perms ≈ sati), odnos cena/korist favorizuje da se minimalni containment napravi **sada**: u suprotnom Faza 4 isporuči jednoprovajderski benchmark a cross-provider deliverable tiho ispari bez eksplicitne odluke. Fail-closed *merge* je prihvatljiv kao međustanje — pod uslovom da prati otvoreni containment issue (kog trenutno nema).

---

## Nivo 1 — Ideja i Premisa

**Šta sistem zapravo radi:** Pre plaćene text-vs-image evaluacije, dokazuje za nultu cenu da li se isti `chart.png` može bezbedno isporučiti Claude i Codex analyst-u; nalazi da Claude CLI image transport nije potvrđen a Codex sandbox ne sprečava čitanje van case root-a, pa runtime fail-closed blokira Codex za privatni benchmark.

**Pretpostavke koje sistem uzima zdravo za gotovo:**
- „`--cd` definiše granicu čitanja" → **NE drži** (i to je poenta nalaza) — `--cd` je working root; canary to ispravno obara.
- „Rezultat na macOS/Seatbelt važi za Codex uopšte" → **delom ne drži** — Linux/Landlock put nije testiran; generalizacija je preširoka.
- „Jedina alternativa fail-closed banu je degradacija na prompt-only" → **ne drži** — OS-nivo containment (uid/perms, kontejner) je treća opcija koju report ne vrednuje.
- „Privatni benchmark zahteva *nemogućnost* curenja, ne *malu verovatnoću*" → **drži** — za integritet privatnog skora ovo je ispravan, strog standard i opravdava fail-closed default.

**Rupe u premisi:**

### Platform-specifičnost prikazana kao opšti zakon
**Problem**: Empirijski nalaz je sa Darwin/Seatbelt; report ne ograđuje zaključak na platformu, a Codex na Linux-u koristi Landlock koji može da ograniči čitanje.
**Posledica**: „Codex se ne može izolovati" se pamti kao trajna istina; budući rad ne pokušava Linux host ili Landlock profil iako bi mogli nativno rešiti problem.
**Uticaj**: srednji

---

## Nivo 2 — Logički Tok

**Tok sistema:**
1. Capability introspekcija CLI-jeva (zero-cost) → ✓
2. Claude image transport canary → exit 1 pre model odgovora → „NIJE POTVRĐEN" → ✓ (pošten, neoboriv u ovom obimu)
3. Codex image capability canary → OCR token pročitan → ✓
4. Codex izolacioni canary → `cat` van root-a `exit_code=0` → curi → ✓ (nalaz tačan)
5. „dakle" → odbaci `chart_image` za oba → ✓ (sledi: Claude nema transport, Codex nema izolaciju)
6. „dakle" → zabrani Codex **u celosti, uključujući text** → ⚠ (preskače platformu + containment + činjenicu da text-mode ne treba file-read)
7. Enforcement preko `CODEX_PRIVATE_BENCHMARK_ISOLATION_VERIFIED=False` u preflight-u → ⚠ (radi, ali unlock je goli boolean i ban je bezuslovan)

**Propusti u toku:**

### Skok 4→6: nalaz ne implicira pun ban
**Vrsta**: preskočen korak
**Lokacija**: `PRPs/reports/spike-75-...md` §Odluka; `scripts/eval/runtime_adapters.py` preflight gate
**Problem**: Iz „default macOS sandbox ne ograničava čitanje" ne sledi „provider mora biti zabranjen". Sledi „ovaj harness profil nije bezbedan" — a između stoje uid/perms, kontejner i Linux/Landlock. Posebno za text-mode (candles.json u promptu) ne postoji ni potreba za file-read-om, pa je ban tu najmanje opravdan.
**Predlog**: Suzi zaključak na „Codex blokiran *na ovom macOS/default-sandbox harness-u*"; otvori containment issue (uid/perms kao prvi pokušaj); zadrži fail-closed dok ne prođe.
**Uticaj**: visok

### Unlock je goli ljudski boolean, ne dokaz
**Vrsta**: neiskorišćen rezultat / slab invariant
**Lokacija**: `scripts/eval/runtime_adapters.py:CODEX_PRIVATE_BENCHMARK_ISOLATION_VERIFIED`
**Problem**: Postoji izvršni sentinel canary koji *proizvodi verdikt*, ali gate ne čita taj verdikt — vezan je za konstantu koju čovek menja. Flip na `True` ponovo pušta Codex bez ijedne provere da izolacija drži; testovi ostaju zeleni.
**Predlog**: Veži gate za *prolazak* sentinel-canary-ja (npr. zapisani verdikt artefakt ili preflight koji odbije ako poslednji canary nije „PROŠAO"), ne za uređivanu konstantu.
**Uticaj**: srednji

### Doseg enforcement-a širi od imena
**Vrsta**: pogrešan doseg
**Lokacija**: `runtime_adapters.py` `CodexRuntimeAdapter.preflight`
**Problem**: Flag i poruka kažu „private-benchmark isolation", ali preflight bezuslovno obara *svaki* Codex run bez obzira da li je u igri privatni ključ. Ili je sve uvek-privatno (onda kvalifikator „private-benchmark" zavarava), ili gate treba uslovan na prisustvo privatnog ključa.
**Predlog**: Ako postoji legitiman ne-privatni Codex run (public eval, dry-run), uslovi gate; inače preimenuj da ne implicira uži doseg nego što enforcement ima.
**Uticaj**: nizak

---

## Nivo 3 — Nužnost Kompleksnosti

**Direktan put vs. stvaran put:**
- Minimalan broj koraka za cilj spike-a: ~4 (introspekcija → image capability → izolacioni canary → odluka)
- Trenutni broj: ~5 (+ runtime fail-closed gate)
- Razlika: opravdana — gate je tanak (jedan boolean + jedan raise) i pretvara nalaz u izvršnu zaštitu, što je vrednije od pukog dokumenta.

**Nepotrebna kompleksnost:**

Kompleksnost je uglavnom opravdana. Canary skripte su dry-run po default-u, jedan plaćeni poziv, deljeni `canary_common`. Nema apstrakcija za uklanjanje. `command_attempt` in_progress-vs-terminal fix je nužan (inače lažni negativ). Jedina napomena nije „mrtva kompleksnost" nego **pogrešno smeštena robusnost**: trud uložen u strog canary verdikt ne hrani gate (vidi Nivo 2, goli boolean) — robusnost postoji ali nije ožičena na mesto gde odlučuje.

---

## Šta drži

- **Fail-closed default je ispravan instinkt.** Za privatni benchmark, „nemogućnost curenja" je pravi standard; merge sigurnog međustanja je bolji od puštanja Codex-a uz poznatu rupu.
- **Zero-cost metodologija ispoštovana** — nalaz dobijen introspekcijom + minimalnim canary-jem, bez paljenja pune matrice.
- **Poštenje o Claude transportu** — „NIJE POTVRĐEN" umesto pretpostavke da API image blok znači CLI image blok; ispravan oprez.
- **Empirijski rigor** — in_progress/terminal evaluator bug uhvaćen i pokriven regresionim testom; verdikt bira poslednji terminalni događaj.
- **Symbol-leak marker** — ispravno obeležen kao preduslov (`ASSET-X` normalizacija) umesto tihog ostavljanja.

---

## Preporučeni sledeći koraci

1. **Otvori containment issue pre/uz merge** i u njemu prvo probaj najjeftiniji put: answer key / judge root na zasebnom uid-u, `chmod 700`, Codex kao korisnik bez prava čitanja — pa ponovo pokreni *isti* sentinel canary. Ako `cat` vrati `Permission denied`, Codex se vraća bez ijedne izmene benchmark logike.
2. **Suzi formulaciju odluke** u reportu i runbook-u sa „Codex se odbacuje" na „Codex blokiran na ovom macOS/default-sandbox harness-u"; eksplicitno zabeleži Linux/Landlock i kontejner kao netestirane, verovatno-rešavajuće puteve. Sačuvaj cross-provider rangiranje kao otvoreni cilj, ne kao odbačen.
3. **Veži gate za canary verdikt, ne za konstantu** — preflight treba da odbije Codex osim ako poslednji zapisani sentinel-canary verdikt nije „PROŠAO". Tako se fail-closed ne može poništiti izmenom jednog karaktera.
4. **Razdvoji text-mode od image-mode odluke** — image rejection je čvrst i može ostati; text-mode ban tretiraj kao privremen do (1), jer text analyst-u file-read uopšte ne treba i najlakši je za sadržati.

---
*Generisao: mk-pregled-logike-solo*
*Izveštaj: `.claude/pregled-logike/pr-81-logika-solo.md`*
