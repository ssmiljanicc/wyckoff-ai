# Faza 4 eval orkestrator — operator runbook

Ovaj tok izvršava benchmark matricu kroz izolovane analyst i judge procese, čuva atomske checkpoint-e i završava postojećim `benchmark.ingest` izveštajem. Ground truth (referentni tačan odgovor) se nikada ne generiše u ovom toku.

## Preduslovi

- Privatni answer key, na primer `data/eval/_answers/ground_truth_answers.json`; fajl ne sme biti commit-ovan.
- Autentifikovani lokalni Claude Code 2.1.183 i Codex CLI 0.141.0 za modele koje birate.
- Capability preflight (provera podržanih mogućnosti CLI-ja):

```bash
claude --version
claude --help | rg -- '--model|--effort|--json-schema|--no-session-persistence|--setting-sources|--strict-mcp-config|--disable-slash-commands|--tools'
codex --version
codex exec --help | rg -- '--model|--cd|--sandbox|--output-schema|--ephemeral|--ignore-user-config'
```

Orkestrator ponavlja proveru pre izvršavanja i označava nepodržan provider/model kao `unavailable`. `claude-fable-5` nema mapiranje u v1 i zato se eksplicitno preskače.

Claude Code 2.1.183 `--bare` režim ne čita OAuth/keychain prijavu, pa se ne koristi sa lokalnim `claude.ai` subscription profilom. Umesto njega adapter eksplicitno isključuje user/project/local settings (`--setting-sources ""`), nasleđene MCP servere (`--strict-mcp-config --mcp-config '{}'`) i skills/commands (`--disable-slash-commands`), uz postojeće `--tools ""` i `--no-session-persistence` granice.

## 1. Obavezni preview

`--dry-run` validira privatni odgovor i selektore, ali ne pravi snapshot, manifest, state ili result fajlove i ne poziva modele/mrežu:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 --model claude-opus-4-8 --effort high --dry-run
```

Opcije `--case`, `--model` i `--effort` mogu da se ponove ili prime CSV listu. Pregledajte `scope`, `planned` i `unavailable` pre realnog poziva.

## 2. Mali real canary

Ovo pravi naplative pozive. Pokrenite tek posle pregleda preview-a:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case case_01 --model claude-opus-4-8 --effort high \
  --max-concurrency 1 --min-start-interval 2
```

Pre prvog punog batch-a ručno proverite da canary fajl postavljen izvan privremenog runtime root-a nije dostupan analyst-u. Ako instalirana CLI/sandbox kombinacija ne garantuje granicu, real run mora da se prekine; ne prelazite na prompt-only izolaciju.

Pre punog batch-a ručno pregledajte canary rezultat:

1. `analysis_output` je JSON objekat sa svih devet obaveznih polja (`narrative`, `evidence`, `direction`, `trigger`, `invalidation`, `confidence`, `structure`, `phase`, `event`).
2. `narrative` i `evidence` opisuju price/volume ponašanje pre nego što `structure`, `phase` i `event` dodele Wyckoff labele.
3. Sačuvani output nema markdown fence niti tekst van JSON objekta.
4. `usage`, analyst checkpoint, `judge_verdict` i završni report postoje i prolaze schema validaciju.
5. Sentinel fajl van privremenog runtime root-a nije dostupan analyst-u.
6. Privremeni `CLAUDE.md` sentinel u canary snapshot-u ne utiče na output; uklonite ga posle provere. Ako se sentinel pojavi u outputu, non-bare CLI je automatski učitao projektni kontekst i benchmark mora da se prekine.

## 3. Pun run i nastavak

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --max-concurrency 2 --min-start-interval 2 --max-attempts 2 --timeout 900

uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json --resume
```

`--resume` preskače kompletne rezultate. Ako je analyst checkpoint kompletan, ponavlja samo judge fazu. `--no-ingest` preskače završni report, ali ne menja checkpoint semantiku. `--reset-state` koristite samo posle pregleda manifest fingerprint mismatch-a; postojeće validne rezultate ne briše i reconciliation (usklađivanje) će ih ponovo označiti kao uspešne.

## Status i izlazi

- State: `<base-dir>/_benchmark/orchestrator_state.json`
- Rezultati: `<base-dir>/_benchmark/results/<run_id>.json`
- Izveštaji: `<base-dir>/_benchmark/report.md` i `report.json`

`max_attempts` se troši unutar istog poziva: run koji padne se ponavlja in-process (ponavlja se samo judge faza ako je analyst checkpoint već kompletan) do uspeha ili iscrpljenja budžeta. `failed` znači da je run iscrpeo `max_attempts`; `pending` ostaje samo posle prekida ili pada (radi bezbednog nastavka kroz `--resume`); `skipped` znači eksplicitno nedostupan provider/model. Exit status je `0` samo kada selektovani scope nema `failed` ili `pending`; konfiguracija/preflight koristi `2`, parcijalni batch `3`, a prekid `130`.

**Trade-off: semaphore i retry.** Semaphore slot se drži kroz sve retry pokušaje jednog spec-a (ceo `execute_run` je unutar jednog `async with semaphore`). Sa `--max-concurrency 1` i `--max-attempts 2`, spec koji padne dva puta blokira ostale workere do `2 × --timeout` sekundi (podrazumevano 1800s) pre nego što slot postane slobodan. Sa `--max-concurrency 2` (podrazumevano) uticaj je manji. Za mali batch (desetak spec-ova) ovo je prihvatljivo; za veće run-ove razmotrite `--max-attempts 1` + `--resume` umesto visokog `--max-attempts`.

## Evaluacioni ugovor: ulaz analyst-a (OHLCV, ne grafikon)

**Eksplicitna odluka (promena u odnosu na prvobitni plan koji je predviđao grafikon analyst-u):** analyst dobija anonimizovani **OHLCV niz** (`candles.json`) ugrađen u prompt, a **ne** `chart.png`. Razlozi:

- **Informacioni sadržaj OHLCV-a očuvan je za anon slučaj.** Za anonimizovani put, `chart.png` se renderuje iz `anon_candles` sa generičkim naslovom „ASSET-X" (`render_eval_chart`), pa ne nosi nijednu informaciju koje nema u `candles.json`. Za `future_visible`, „as-of T" marker je u `instruction.txt` (takođe inline). Ekvivalentnost kvaliteta modela između tekstualnog OHLCV-a i grafikona nije empirijski potvrđena — ovaj benchmark meri kvalitet Wyckoff analize nad OHLCV tekstualnim ulazom, ne opštu chart-vision sposobnost modela. **Napomena:** `revealed` chart renderuje se sa pravim simbolom u naslovu (`render_chart_image(..., title=f"{symbol} {tf_lower.upper()}")`) koji `candles.json` ne sadrži — ali pošto chart nikad nije bio isporučen analyst-u (ni pre ni posle ove promene), ova razlika ne utiče na integritet mjerenja.
- **Fer poređenje modela.** `claude -p` (headless) nema flag za lokalni prilog slike; Codex ima `-i`. Mešanje modaliteta (slika za neke, tekst za druge modele) bi pokvarilo cilj benchmark-a — rangiranje modela. Jedan zajednički modalitet (OHLCV tekst) je metodološki ispravan; provider-neutralan unos slike trenutno nije dostupan.
- **Leakage kontrola je suženija ali čistija.** `revealed` `candles.json` zadržava prave cene i prave timestamp-ove (passthrough) — model može da identifikuje asset po cenovnom opsegu i datumima, što je validan pretraining-leakage signal. Direktni simbolov recall (naziv instrumenta u naslovu grafikona) nije u ulazu — `Δleakage` mjeri leakage kroz prepoznavanje cena i timestampova, ne i kroz eksplicitan naziv. Ovo je konzervativnija (suženija) mjera od teorijskog maksimuma, ali metodološki ispravna za dostupan input.

Ako se ikad zahteva chart-vision evaluacija, to je zaseban evaluacioni ugovor (i zahteva provider-neutralan put za sliku), ne izmena ovog toka.

## Anti-leakage granica

Analyst dobija anonimizovane OHLCV podatke (`candles.json`) ugrađene direktno u prompt; svaki model dobija identičan ulaz. `chart.png` se namerno ne isporučuje (binarno je, bez fer cross-provider puta za prilog; `candles.json` nosi isti OHLCV koji grafikon crta za anon slučaj). Kopija case fajlova i schema-e u sistemskom temp root-u služi kao izolaciona granica i izvor schema-e za CLI; symlink i path escape se odbijaju, answer key i repo root se ne kopiraju. Judge radi u drugom praznom root-u i dobija samo payload iz `scoring.prepare_judge_input`, bez grafikona, candles, identiteta i putanja. Prompt i privatni judge payload se ne upisuju u state ili stderr dijagnostiku.

**Izolacione garancije po provider-u:**
- **Claude**: `--tools ""` gasi sve built-in alate uključujući Read — model fizički ne može da otvori fajlove van prompta. `--setting-sources ""`, strogi prazni MCP config i `--disable-slash-commands` sprečavaju nasleđivanje settings/MCP/skill konteksta bez OAuth-nekompatibilnog `--bare` režima. Automatsko učitavanje `CLAUDE.md`/memory konteksta u non-bare režimu ostaje **UNVERIFIED** dok canary sentinel provera iz §2 ne prođe; ako se sentinel pojavi, prekinite benchmark.
- **Codex**: `--sandbox read-only --cd <temp-root>` — model ima alate ali u read-only sandboxu. **UNVERIFIED**: scope sandboxa u odnosu na `--cd` putanju nije programatski verifikovan; capability preflight samo provjerava da `--sandbox` flag postoji u `--help`. Ručni canary test (§2) je obavezan pre prvog plaćenog run-a da bi se potvrdilo da Codex ne može da čita fajlove van privremenog root-a (npr. answer key iz repo stabla).

## Opt-in manual smoke

Posle promene Claude/Codex verzije ponovite jedan canary po provider-u. Proverite structured JSON, usage zbir, `result` checkpoint i report. Ovaj smoke nije deo podrazumevanog `pytest` paketa zbog autentifikacije, mreže i troška.
