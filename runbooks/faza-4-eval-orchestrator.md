# Faza 4 eval orkestrator — operator runbook

Ovaj tok izvršava benchmark matricu kroz izolovane analyst i judge procese, čuva atomske checkpoint-e i završava postojećim `benchmark.ingest` izveštajem. Ground truth (referentni tačan odgovor) se nikada ne generiše u ovom toku.

## Preduslovi

- **Source-anchored eval skup (issue #76).** Svaki case je vezan za postojeći ekspertski analiziran crypto grafikon (Wyckoff Crypto Report): originalna chart slika, neposredni ekspertski pasus i pouzdano rekonstruisan Binance OHLCV presek do cutoff-a T. Broj slučajeva nije fiksan i nema event kvote — validator proverava **po-case** source dokaz (postojeći raw Markdown, lokalna slika koju pasus referencira, validan excerpt opseg), ne distribuciju skupa. Detalji ugovora i kuracije: [`source-anchored eval set`](#source-anchored-eval-set-76).
- Privatni answer key, na primer `data/eval/_answers/ground_truth_answers.json`; fajl ne sme biti commit-ovan. Sadrži provenance + `analysis_mode` + strukturirana expert polja; placeholder odgovori su dozvoljeni samo u `build_eval_set --dry-run`, a orkestrator ih odbija i u preview-u.
- Autentifikovani lokalni Claude Code 2.1.183 i Codex CLI 0.141.0 za modele koje birate.
- Capability preflight (provera podržanih mogućnosti CLI-ja):

```bash
claude --version
claude --help | rg -- '--bare|--model|--effort|--json-schema|--no-session-persistence'
codex --version
codex exec --help | rg -- '--model|--cd|--sandbox|--output-schema|--ephemeral|--ignore-user-config'
```

Orkestrator ponavlja proveru pre izvršavanja i označava nepodržan provider/model kao `unavailable`. `claude-fable-5` nema mapiranje u v1 i zato se eksplicitno preskače.

## 1. Obavezni preview

`--dry-run` validira privatni odgovor i selektore, ali ne pravi snapshot, manifest, state ili result fajlove i ne poziva modele/mrežu:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case btc_vol43_2020_11 --model claude-opus-4-8 --effort high --dry-run
```

Opcije `--case`, `--model` i `--effort` mogu da se ponove ili prime CSV listu. Pregledajte `scope`, `planned` i `unavailable` pre realnog poziva.

## 2. Mali real canary

Ovo pravi naplative pozive. Pokrenite tek posle pregleda preview-a:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case btc_vol43_2020_11 --model claude-opus-4-8 --effort high \
  --max-concurrency 1 --min-start-interval 2
```

Pre prvog punog batch-a ručno proverite da canary fajl postavljen izvan privremenog runtime root-a nije dostupan analyst-u. Ako instalirana CLI/sandbox kombinacija ne garantuje granicu, real run mora da se prekine; ne prelazite na prompt-only izolaciju.

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
- **Claude**: `--tools ""` gasi sve built-in alate uključujući Read — model fizički ne može da otvori fajlove van prompta. Verifikovano dizajnom CLI-ja.
- **Codex**: `--sandbox read-only --cd <temp-root>` — model ima alate ali u read-only sandboxu. **UNVERIFIED**: scope sandboxa u odnosu na `--cd` putanju nije programatski verifikovan; capability preflight samo provjerava da `--sandbox` flag postoji u `--help`. Ručni canary test (§2) je obavezan pre prvog plaćenog run-a da bi se potvrdilo da Codex ne može da čita fajlove van privremenog root-a (npr. answer key iz repo stabla).

## Opt-in manual smoke

Posle promene Claude/Codex verzije ponovite jedan canary po provider-u. Proverite structured JSON, usage zbir, `result` checkpoint i report. Ovaj smoke nije deo podrazumevanog `pytest` paketa zbog autentifikacije, mreže i troška.

## Source-anchored eval set (#76)

V1 evaluacioni skup je suženo crypto-only i izveden isključivo iz ekspertski analiziranih grafikona iz `raw/crypto_archive/`. Ground truth se ne izmišlja — preuzima se iz postojećeg ekspertskog teksta vezanog za baš tu sliku i tržišni period.

**Source chart služi samo kuraciji, ne ulazu.** Originalna ekspertska slika (`source_image_path`) i tekst koriste se da se utvrde `symbol/timeframe/cutoff` i da se napiše veran `ground_truth`. Analyst i dalje dobija **samo anonimizovani OHLCV tekst** (vidi „Evaluacioni ugovor" gore) rekonstruisan iz Binance-a do T — bez ekspertnih oznaka, strelica, projekcija desno od T i bez originalne slike. #75 (chart-image vs OHLCV-text modalitet) nije implementiran ovde i ostaje zaseban.

**Privatni answer key — ugovor po slučaju:**

- Eval-facing polja koja scoring stvarno čita: `event_type`, `realized_direction`, `decisive`, `analysis_mode`, `ground_truth`.
- Provenance/reconstruction polja (`expert_author`, `source_path`, `source_url`, `source_image_path`, `source_excerpt_location`, `reconstruction_notes`, `expert_*`) postoje **samo** u master privatnom ključu. U angle-specific `*.answer.json` propagira se isključivo allowlist `{event_type, realized_direction, decisive, analysis_mode}` (`ground_truth.angle_answer_metadata`); provenance po konstrukciji ne dolazi ni do analyst-a, ni do judge-a, ni do public manifesta.
- Nepomenuto ekspertsko polje je literal `not_stated`; validator odbija prazne stringove i nagađane sentinele.

**`analysis_mode`: forward_looking vs retrospective.**

- `forward_looking` — ekspert piše na desnom rubu grafikona (prognoza). `realized_direction ∈ {up, down, none}`; determinističke dimenzije (`direction/trigger/invalidation`) se skoruju replay-em post-T sveća.
- `retrospective` — ekspert objašnjava već realizovan obrazac (npr. bar-by-bar „WYCKOFF STORY"). `realized_direction = not_applicable`; determinističke dimenzije su `N/A` (nikad 0). Judge alignment se i dalje računa — nema hindsight kontaminacije prediktivnog skora.

**Dva odvojena podskora u izveštaju:**

- `expert_alignment_score` — weighted mean judge dimenzija (slaganje sa postojećom ekspertskom Wyckoff analizom). Računa se uvek.
- `realized_outcome_score` — weighted mean ne-`N/A` determinističkih dimenzija (uspeh prognoze prema stvarnom post-T kretanju). `N/A` za retrospective i wait slučajeve.
- Postojeći `aggregate` i model ranking ostaju nepromenjeni radi kompatibilnosti starih izveštaja.

**Canary zavisnost od #77.** Real (plaćeni) canary za #76 pokrenuti tek kada je #77 (eval runtime fix) merge-ovan, operator potvrdi trošak i `--dry-run` output je pregledan. Codex izolacija ostaje `UNVERIFIED` dok odgovarajući canary ne prođe (vidi „Anti-leakage granica"). `--dry-run` ne dokazuje real source rekonstrukciju — vizuelno poređenje originalne slike i čistog snapshot-a po slučaju radi se na real build-u.
