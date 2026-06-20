# Feature: Source-anchored crypto eval set v1

## Izmene od pregled-plana

Ovaj plan utkiva tri PLAN DEFECT popravke iz pregleda (`.claude/pregled-plana/source-anchored-crypto-eval-set-v1.md`); kanonska `prp-plan` struktura je očuvana. (Operator je prihvatio `.revised` i prepisao original 2026-06-20.)

1. **`analysis_mode` prenos zatvoren (Task 3 + Task 6 + Acceptance).** Task 4 zahteva da `score_deterministic` vidi `analysis_mode`, ali lanac `_answer_extra → build_snapshot → angle answer key → score_run` to ne garantuje. Propagacioni allowlist sada eksplicitno uključuje `analysis_mode`, a dodat je integracioni test i acceptance stavka za end-to-end prenos.
2. **Provenance se ne kopira u angle ključeve (Contract + Task 3).** Izolacija judge-a je već zagarantovana allowlist-om u `prepare_judge_input` (`scoring.py:369-379`); ništa ne čita provenance iz angle ključa. Provenance/reconstruction ostaju isključivo u gitignored master privatnom ključu; u angle se propagira samo `analysis_mode` (+ postojeća tri polja).
3. **`make_placeholder_answers` prepisana (Task 2).** Funkcija zavisi od `EVENT_QUOTA` koju Task 2 uklanja; bez prepisivanja dry-run puca. Dodata eksplicitna stavka sa VALIDATE.

## Summary

Zameniti sadašnjih deset proizvoljno izabranih tržišnih preseka najmanjim korisnim skupom crypto slučajeva za koje postoje: originalni ekspertski grafikon, neposredno vezan ekspertski tekst i pouzdano rekonstruisan Binance OHLCV presek do cutoff-a T. Zadržati postojeći privatni answer-key, snapshot, judge i deterministic scoring tok; ukloniti fiksnu event kvotu, dodati provenance i `analysis_mode`, a postojeće dimenzije prikazati kao odvojene `expert_alignment_score` i `realized_outcome_score`.

Plan sprovodi `SIMPLIFY` presudu sa issue-a #76. V1 ne popravlja Fraser slike, ne uvodi non-Binance market-data adapter, ne inventariše iscrpno sva tri raw korpusa i ne menja analyst input modalitet iz #75.

## User Story

Kao operator evaluacionog harness-a,
želim da svaki benchmark slučaj bude vezan za postojeću ekspertsku analizu istog tržišnog preseka,
kako bi rezultat merio slaganje sa proverljivim Wyckoff tumačenjem i odvojeno realizovani post-T ishod, umesto slaganja sa naknadno izmišljenim ground truth-om.

## Problem Statement

`GROUND_TRUTH_CASES` trenutno sadrži deset simbola i datuma bez veze sa ekspertskim izvorom, dok validator nameće tačno deset slučajeva, fiksnu event kvotu i dva post-2026 slučaja. Takav ugovor može proizvesti tehnički validan benchmark čiji ground truth nema dokazivo ekspertsko poreklo.

## Solution Statement

Kurirati target 3–5 crypto kandidata, ali prihvatiti manji v1 ako samo manji broj prođe sve source/reconstruction kapije. Za svaki prihvaćeni slučaj privatni answer key mora sadržati proverljivu raw Markdown + image vezu, veran `ground_truth` sažetak, `analysis_mode` i reconstruction belešku. Validator proverava kvalitet svakog slučaja, a ne kvotu skupa. Postojeći judge rezultat postaje `expert_alignment_score`; postojeće determinističke dimenzije postaju `realized_outcome_score`. Retrospective slučajevi dobijaju `N/A` za outcome dimenzije.

## Metadata

- **Source:** GitHub issue #76 + komentar `SIMPLIFY` od 2026-06-20
- **Input type:** issue body i obavezujuća gate presuda, tretirani kao feature opis
- **Feature type:** `ENHANCEMENT`
- **Complexity:** `MEDIUM`
- **Primary systems:** eval case registry, private answer contract, snapshot metadata propagation, scoring/reporting, operator runbook
- **Current planning worktree:** `/Users/ssmiljanic/projekti/wyckoff-ai`
- **Current branch:** `fix/issue-77-eval-runtime`
- **Parallelism with #77:** kuracija i većina izmena mogu na zasebnoj grani/worktree-u; završni real canary čeka da #77 bude merge-ovan. Ne implementirati #76 direktno preko dirty #77 worktree-a.
- **External research:** nije potrebna. Suženi v1 koristi postojeći lokalni raw korpus, Binance klijent i interne eval ugovore; ne uvodi novu biblioteku ili API.

## UX Design

### Pre

```text
10 hard-coded datuma + fiksna event kvota
                  |
                  v
privatni slobodno napisani ground_truth
                  |
                  v
snapshot -> analyst -> judge + deterministic scorer -> jedan aggregate
```

### Posle

```text
raw crypto chart ↔ neposredni ekspertski pasus
                  |
        source/reconstruction kapije
                  |
                  v
promenljiv mali case set + privatni source-anchored answer key
                  |
                  v
postojeći snapshot -> analyst -> postojeći judge/deterministic scorer
                                      |                 |
                                      v                 v
                           expert_alignment     realized_outcome
                           (uvek)               (forward only)
```

| Lokacija | Pre | Posle | Uticaj |
| --- | --- | --- | --- |
| Case validacija | tačno 10 + tačna event kvota | svaki case mora imati dokaziv source anchor; broj nije hard-coded | kvalitet izvora ima prioritet nad kvotom |
| Answer key | četiri obavezna evaluaciona polja | postojeća polja + provenance, `analysis_mode` i reconstruction dokaz | ground truth je auditabilan |
| Retrospective case | tretiran kao predikcija | judge alignment ostaje, outcome je `N/A` | nema hindsight kontaminacije prediktivnog skora |
| Benchmark report | jedan aggregate + dimenzije | aggregate ostaje radi kompatibilnosti, uz dva imenovana podskora | operator vidi šta rezultat zapravo meri |

## Mandatory Reading

- `CLAUDE.md:21-64` — srpski user-facing tekst i review disciplina.
- GitHub issue #76, posebno komentar `SIMPLIFY` — obavezujuća granica v1 scope-a.
- `scripts/eval/ground_truth_cases.py:17-24,47-154,181-244` — fiksna kvota, trenutni scaffold, placeholder i validacija koje treba suziti/preoblikovati.
- `scripts/eval/build_eval_set.py:22-69` — generator koji učitava answer key i delegira snapshot builder-u.
- `scripts/eval/snapshot_builder.py:180-221,243-265,288-362` — Binance-only fetch, post-T sveće, answer-key izolacija i `answer_extra` propagation.
- `scripts/eval/scoring.py:17-62,255-339,362-441` — postojeća podela judge/deterministic dimenzija, redaction i weighted aggregate.
- `scripts/eval/benchmark.py:393-445,453-499,546-646,845-976` — score row, grupisanje/report i tri snapshot ugla.
- `scripts/eval/orchestrator.py:331-375` — dry-run preflight, case registry i privatni answer path; ovaj fajl je u aktivnom #77 scope-u i ne treba ga menjati ako nije neophodno.
- `runbooks/faza-4-eval-orchestrator.md:20-43,68-88` — zero-cost preview, plaćeni canary i trenutni OHLCV/izolacioni ugovor.
- `raw/crypto_archive/posts/wyckoff-crypto-report-vol-43.md:10-15` + pripadajuća slika — potvrđen početni kandidat: BTC/USDT 4h Binance, forward scenario i pattern failure.
- `raw/crypto_archive/posts/wyckoff-crypto-report-vol-24.md:12-28,39-41` + pripadajuće slike — kandidati koji moraju proći exchange/cutoff proveru; XTZ Kraken slika nije automatski prihvatljiv Binance reconstruction.

## Patterns to Mirror

| Kategorija | File:lines | Obrazac | Stvarni snippet |
| --- | --- | --- | --- |
| Privatnost | `scripts/eval/ground_truth_cases.py:1-5` | pravi odgovor ostaje van git istorije | `The real answer key is intentionally loaded from an ignored local JSON file` |
| Precizne greške | `scripts/eval/ground_truth_cases.py:196-230` | svaka validaciona greška nosi `case_id` | `raise ValueError(f"{case_id} missing answer key entry")` |
| Answer propagation | `scripts/eval/snapshot_builder.py:350-362` | osnovni key + eksplicitni `answer_extra` | `if answer_extra: answer_key.update(answer_extra)` |
| Outcome replay | `scripts/eval/scoring.py:288-339` | post-T ishod već postoji; ne praviti drugi scorer | `outcome, bars_to_resolution = _replay(...)` |
| Judge izolacija | `scripts/eval/scoring.py:342-389` | allowlist + path/candle redaction | `if key_text in SENSITIVE_JUDGE_KEYS or key_text.endswith("_path")` |
| N/A dimenzije | `scripts/eval/scoring.py:267-286` | neprimenljive dimenzije imaju `score=None` | `"trigger": _score(None, "deterministic", ...)` |
| Partial mean | `scripts/eval/benchmark.py:453-457` | `None` se izuzima, ne pretvara u nulu | `nums = [v for v in values if v is not None]` |
| No-write preview | `scripts/eval/orchestrator.py:353-356` | dry-run završava pre snapshot/state upisa | `if args.dry_run: ... return EXIT_OK` |

## Answer-Key Contract v1

Zadržati postojeće polje `ground_truth` kao jedini judge-facing ekspertski sažetak; ne uvoditi paralelni `expert_analysis_summary` sa istim sadržajem. Privatni zapis po slučaju mora imati:

```json
{
  "event_type": "spring",
  "realized_direction": "up",
  "decisive": true,
  "ground_truth": "Current formation has no distributional signs; the source presents continuation above resistance and a spring near 15.5k as bullish scenarios, with 14.3k support revisit as pattern failure.",
  "analysis_mode": "forward_looking",
  "expert_author": "Alessio Rutigliano",
  "source_path": "raw/crypto_archive/posts/wyckoff-crypto-report-vol-43.md",
  "source_url": "https://www.wyckoffanalytics.com/wyckoff-crypto-report-vol-43/",
  "source_image_path": "raw/crypto_archive/images/wyckoff-crypto-report-vol-43/01-lead-71fc2a91.png",
  "source_excerpt_location": {"start_line": 10, "end_line": 15},
  "expert_structure": "not_stated",
  "expert_phase": "not_stated",
  "expert_event": "spring",
  "expert_scenario": "Continuation if resistance becomes support; alternatively a spring near 15.5k; failure revisits 14.3k support.",
  "expert_trigger": "not_stated",
  "expert_invalidation": 14300,
  "reconstruction_notes": "Kako su symbol/timeframe/cutoff potvrđeni i šta je vizuelno upoređeno."
}
```

Pravila:

- `analysis_mode` je `forward_looking` ili `retrospective`.
- Nepomenuto ekspertsko polje je literal `not_stated`; validator odbija prazne stringove i nagađanjem popunjene sentinel varijante.
- `realized_direction` može biti `up|down|none` samo za forward slučaj; za retrospective je `not_applicable`.
- `source_path` i `source_image_path` su repo-relative, moraju se resolve-ovati unutar `raw/crypto_archive/`, postojati i biti međusobno povezani Markdown image referencom.
- `source_excerpt_location` mora označiti postojeći opseg linija koji neposredno analizira navedenu sliku.
- Provenance i reconstruction polja ostaju **isključivo u gitignored master privatnom ključu** (`data/eval/_answers/ground_truth_answers.json`); **nikad se ne kopiraju u angle-specific `*.answer.json`**. U angle ključeve se iz answer zapisa propagira samo `analysis_mode` (pored postojećih `event_type/realized_direction/decisive`) — jedino što scoring zaista čita. Tako provenance ne dolazi ni do analyst-a, ni do judge-a, ni do public manifesta po konstrukciji, a ne samo zahvaljujući judge allowlist-u. Judge i dalje dobija samo postojeći kontrolisani sažetak/labels allowlist (`scoring.py:369-379`).
- Placeholder odgovori moraju imati eksplicitni marker i dozvoljeni su samo u `build_eval_set --dry-run`; orkestrator ih odbija čak i kada radi preview realnog answer fajla.

## Candidate Curation Gate

Za svaki kandidat implementer mora redom dokazati:

1. Markdown ima lokalnu image referencu i neposredni ekspertski pasus.
2. Slika jasno ili pouzdano otkriva instrument, timeframe i desni rub T.
3. Binance ima isti instrument/timeframe/period; drugi exchange se ne smatra ekvivalentnim bez vizuelno dokumentovanog podudaranja.
4. Novi clean snapshot se završava na T i ne sadrži ekspertne oznake ili buduće sveće.
5. Originalni i clean chart su ručno vizuelno upoređeni po rasponu, ključnim pivotima i poslednjoj sveći; rezultat je upisan u `reconstruction_notes`.
6. `ground_truth` ne tvrdi ništa van označenog source excerpt-a; izostanci ostaju `not_stated`.

Početni shortlist nije automatski acceptance:

- **Visok prioritet:** crypto report vol. 43, BTC/USDT 4h Binance, linije 10–15 i `01-lead-71fc2a91.png`.
- **Proveriti:** crypto report vol. 24, Bitcoin daily, linije 12–20 i `02-BTC_DAILYY-3ae1b23c.png`.
- **Negativni kontrolni primer:** vol. 24 XTZ daily koristi Kraken; odbiti ako Binance reconstruction ne može jasno da se dokaže.

Target je 3–5 prihvaćenih slučajeva. Ako ih manje prođe, isporučiti manji validan skup i u handoff-u navesti odbijene kandidate i razlog; ne popunjavati broj proizvoljnim datumima.

## Files to Change

| Fajl | Akcija | Svrha |
| --- | --- | --- |
| `scripts/eval/ground_truth_cases.py` | izmena | source-first registry, promenljiva veličina, privatni contract i validacija bez kvote |
| `scripts/eval/build_eval_set.py` | izmena | shared metadata propagation i dry-run-only placeholder dozvola |
| `scripts/eval/scoring.py` | izmena | retrospective outcome `N/A` i dva podskora iz postojećih dimenzija |
| `scripts/eval/benchmark.py` | izmena | propagate private metadata i prikaz oba podskora u row/group/report izlazu |
| `tests/test_ground_truth_cases.py` | izmena | ukloniti quota/post-cutoff pretpostavke; testirati provenance i variable count |
| `tests/test_scoring.py` | izmena | forward/retrospective ponašanje, split score i redaction |
| `tests/test_benchmark.py` | izmena | row/group/report ugovor za podskorove i `N/A` |
| `tests/test_snapshot_builder.py` | izmena po potrebi | dokaz da eksplicitno prosleđena provenance metadata ostaje samo u answer key-u |
| `tests/test_eval_orchestrator.py` | mala izmena | realističan valid fixture umesto placeholder answer fajla |
| `runbooks/faza-4-eval-orchestrator.md` | izmena | source-anchored precondition, analysis modes, dva podskora i canary dependency na #77 |
| `PRPs/reports/source-anchored-crypto-eval-set-v1-report.md` | novo pri implementaciji | audit prihvaćenih/odbijenih kandidata bez kopiranja privatnog ground-truth sadržaja |

`scripts/eval/orchestrator.py` nije planiran za izmenu: zadržavanje imena `validate_event_coverage` kao kompatibilnog entry point-a izbegava konflikt sa paralelnim #77; docstring i ponašanje funkcije se menjaju iz quota validatora u per-case coverage/provenance validator. Event “coverage” sada znači da svaki real case ima validan, neprazan `event_type`, ne da skup zadovoljava fiksnu distribuciju.

## NOT Building

- Non-Binance market-data adapter.
- Download/repair Bruce Fraser slika.
- Iscrpan inventar Fraser/book/crypto korpusa.
- LLM-generisan ili novoannotiran “ekspertski” ground truth.
- Fiksnih deset slučajeva, event kvota ili post-knowledge-cutoff kvota.
- Novi scorer paralelan postojećem `scoring.py`.
- Dostavljanje originalne slike ili source teksta analyst-u/judge-u.
- Promenu analyst modaliteta (`ohlcv_text` vs `chart_image`) iz #75.
- Runtime adapter/prompt/parser popravke iz #77.
- Pun plaćeni benchmark; samo jedan operator-odobren canary posle #77.

## Step-by-Step Tasks

### Task 1 — Kurirati source-anchored crypto v1 slučajeve

- **Action:** pregledati shortlist i ostale crypto report kandidate; prihvatiti samo one koji prolaze svih šest curation kapija. Zameniti proizvoljni `GROUND_TRUTH_CASES` tačnim `case_id/symbol/timeframe/cutoff/n_bars` vrednostima prihvaćenih slučajeva. Napraviti privatni `data/eval/_answers/ground_truth_answers.json` po ugovoru iz ovog plana; ne commit-ovati ga.
- **Files:** `scripts/eval/ground_truth_cases.py`, lokalni ignored answer key, kasniji implementation report.
- **Pattern:** case metadata ostaje odvojena od privatnog odgovora kao u `ground_truth_cases.py:1-5,47-118`.
- **Gotchas:** publication timestamp nije automatski cutoff; exchange mismatch nije automatski prihvatljiv; projekcije nacrtane desno od T ne smeju ući u clean input.
- **Validation:** `git check-ignore data/eval/_answers/ground_truth_answers.json`; za svaki case ručno otvoriti source image i clean chart i upisati zaključak u reconstruction notes/report.

### Task 2 — Zameniti quota validator source-anchor validatorom

- **Action:** ukloniti `EVENT_QUOTA`, očekivani count i post-2026 minimum. Proširiti `ANSWER_REQUIRED_FIELDS`; validirati enum/sentinel pravila, repo-relative path containment, postojanje source/image fajlova, image referencu iz Markdown-a, source line range i jedinstvenost case ID-jeva. Zadržati javno ime `validate_event_coverage` radi #77 paralelizma, uz novi docstring. Dodati eksplicitni `allow_placeholders=False`; samo build dry-run ga uključuje. **Prepisati `make_placeholder_answers`** (trenutno sagrađena oko `EVENT_QUOTA`, `ground_truth_cases.py:121-154`) u quota-free generator koji za promenljiv case set proizvodi placeholder odgovore sa eksplicitnim placeholder markerom i `analysis_mode`; pozivaju je `build_eval_set.run(dry_run=True)` i `benchmark._load_benchmark_cases_and_answers`, pa mora preživeti uklanjanje `EVENT_QUOTA`.
- **File:** `scripts/eval/ground_truth_cases.py`.
- **Pattern:** precizne `case_id` greške iz `ground_truth_cases.py:196-230`; `Path.resolve()` containment disciplina iz snapshot/orchestrator path provera.
- **Gotchas:** ne čitati/emitovati privatni `ground_truth` u greškama; symlink/path escape mora pasti; prazan skup mora pasti, ali broj >0 nije drugačije kvotiran.
- **Validation:** `uv run --extra mcp pytest -q tests/test_ground_truth_cases.py`.

### Task 3 — Centralizovati snapshot metadata propagation

- **Action:** dodati eksplicitnu allowlist helper funkciju u `ground_truth_cases.py` koja iz answer zapisa vraća metadata za angle-specific answer key. **Allowlist je tačno `{event_type, realized_direction, decisive, analysis_mode}`** — `analysis_mode` mora biti uključen jer ga `score_deterministic` čita (Task 4), inače retrospective detekcija nikad ne okine u realnom run-u. **Provenance/reconstruction polja (`source_path`, `source_image_path`, `expert_author`, `source_url`, `source_excerpt_location`, `reconstruction_notes`, `expert_*`) se NE uvrštavaju** — ostaju samo u master privatnom ključu (vidi Contract). Koristiti helper i u `build_eval_set.py` (inline lista `:49-53`) i u `benchmark.py` (`_answer_extra`, `:864-869`) umesto dve ručno održavane liste. Ne prosleđivati nepoznata polja dict-spreadom.
- **Files:** `scripts/eval/ground_truth_cases.py`, `scripts/eval/build_eval_set.py`, `scripts/eval/benchmark.py`.
- **Pattern:** `answer_extra` merge u `snapshot_builder.py:350-362`; učitavanje angle ključa za scoring u `benchmark.py:821`.
- **Imports/types:** `Path`, `Any`; zadržati postojeće dict-based ugovore bez nove biblioteke.
- **Gotchas:** `ground_truth` se i dalje prosleđuje posebnim argumentom; `post_t_candles` i `coef_meta` ostaju builder-owned; provenance/reconstruction nikada ne ulaze ni u angle answer key ni u case manifest — jedina nova propagacija je `analysis_mode`.
- **Validation:** `uv run --extra mcp pytest -q tests/test_ground_truth_cases.py tests/test_snapshot_builder.py tests/test_benchmark.py`.

### Task 4 — Razlikovati forward i retrospective outcome scoring

- **Action:** u `score_deterministic` rano prepoznati `analysis_mode == "retrospective"` i vratiti postojeći `DeterministicResult` oblik sa `direction/trigger/invalidation` dimenzijama statusa `na`, bez normalizacije `realized_direction` ili replay-a. Forward put ostaje nepromenjen.
- **File:** `scripts/eval/scoring.py`.
- **Pattern:** wait-case N/A rezultat iz `scoring.py:267-286`.
- **Gotchas:** retrospective nije isto što i low-confidence wait; `wait_case` ostaje `False`; ne menjati judge dimenzije ili schema-u.
- **Validation:** `uv run --extra mcp pytest -q tests/test_scoring.py -k 'retrospective or deterministic or wait'`.

### Task 5 — Izvesti dva podskora iz postojećih dimenzija

- **Action:** dodati jednu shared weighted-mean helper funkciju. `expert_alignment_score` računa normalizovani weighted mean judge dimenzija; `realized_outcome_score` računa normalizovani weighted mean deterministic dimenzija koje nisu `N/A`. Zadržati postojeći `aggregate` radi kompatibilnosti. Dodati polja u `ScoreRecord`, benchmark row/group/report JSON i Markdown baseline tabelu.
- **Files:** `scripts/eval/scoring.py`, `scripts/eval/benchmark.py`.
- **Pattern:** postojeći weight-renormalization iz `scoring.py:424-440` i partial mean iz `benchmark.py:453-457`.
- **Gotchas:** `None` ostaje `N/A`, nikad 0; event bucket i delta/ranking nastavljaju da koriste postojeći aggregate u v1; ne menjati model ranking semantiku u istom issue-u.
- **Validation:** `uv run --extra mcp pytest -q tests/test_scoring.py tests/test_benchmark.py`.

### Task 6 — Ojačati isolation i contract regresione testove

- **Action:** zameniti quota testove variable-count/provenance testovima; dodati path escape, missing image, source-image mismatch, invalid excerpt, `not_stated`, placeholder-only-dry-run i retrospective testove. Potvrditi da judge payload ne sadrži `source_path`, `source_image_path`, author, URL ili reconstruction notes. **Dodati integracioni propagacioni test:** posle `build_snapshot` angle `*.answer.json` sadrži `analysis_mode` ali NE sadrži nijedno provenance/reconstruction polje; i da `score_deterministic` nad učitanim retrospective angle ključem daje `N/A` determinističke dimenzije (dokazuje da `analysis_mode` preživi `_answer_extra → build_snapshot → load`, a ne samo direktan unit poziv). U orchestrator testu koristiti validan real-like fixture umesto placeholder fajla.
- **Files:** `tests/test_ground_truth_cases.py`, `tests/test_scoring.py`, `tests/test_benchmark.py`, `tests/test_snapshot_builder.py`, `tests/test_eval_orchestrator.py`.
- **Pattern:** tempfile fixtures i redaction assertions iz `tests/test_scoring.py:125-166`; no-write dry-run iz `tests/test_eval_orchestrator.py:163-174`.
- **Gotchas:** test fixtures ne smeju zavisiti od privatnog lokalnog answer key-a ili mreže; source validation fixture koristi `tmp_path` repo-like raw stablo/injected root ako je validator dizajniran za testability.
- **Validation:** `uv run --extra mcp pytest -q tests/test_ground_truth_cases.py tests/test_snapshot_builder.py tests/test_scoring.py tests/test_benchmark.py tests/test_eval_orchestrator.py`.

### Task 7 — Ažurirati operator runbook i audit report

- **Action:** dokumentovati source-anchored precondition, private contract, forward/retrospective semantiku, dva podskora, variable case count i činjenicu da `chart.png` iz izvora služi samo kuraciji. U implementation report-u navesti prihvaćene i odbijene source/image putanje, reconstruction odluku i test rezultate, bez kopiranja privatnog ground truth-a.
- **Files:** `runbooks/faza-4-eval-orchestrator.md`, `PRPs/reports/source-anchored-crypto-eval-set-v1-report.md`.
- **Pattern:** plaćeni canary warning iz runbook-a `:32-43`; report format iz `PRPs/reports/faza-4-end-to-end-eval-orchestrator-report.md`.
- **Gotchas:** ne menjati OHLCV-only odluku; #75 ostaje zaseban; Codex isolation ostaje `UNVERIFIED` dok odgovarajući canary ne prođe.
- **Validation:** `rg -n "source-anchored|forward_looking|retrospective|expert_alignment_score|realized_outcome_score|#77" runbooks/faza-4-eval-orchestrator.md PRPs/reports/source-anchored-crypto-eval-set-v1-report.md`.

### Task 8 — Offline validacija, dry-run i uslovni real canary

- **Action:** pokrenuti kompletan offline eval paket i compile/diff provere. Zatim pokrenuti orkestrator `--dry-run` sa privatnim source-anchored answer key-em. Jedan real canary pokrenuti tek kada je #77 merge-ovan, operator potvrdi trošak i dry-run output je pregledan.
- **Files:** bez dodatne promene koda osim popravki otkrivenih validacijom unutar ovog scope-a.
- **Pattern:** runbook `:20-43`.
- **Gotchas:** `build_eval_set --dry-run` koristi stub/placeholder i ne dokazuje real source rekonstrukciju; orkestrator dry-run ne pravi snapshot; canary nije implicitno odobren ovim planom.
- **Validation:** komande iz naredne sekcije.

## Testing Strategy

1. **Unit — contract:** promenljiv broj slučajeva, required provenance, enums, `not_stated`, missing/escaped paths i source-image veza.
2. **Unit — scoring:** forward replay ne menja ponašanje; retrospective daje deterministic `N/A`; podskorovi pravilno renormalizuju težine.
3. **Unit — isolation:** provenance/reconstruction i candles nikad nisu u judge payload-u ili public manifestu.
4. **Integration offline:** stub snapshot generacija radi za ceo promenljivi registry; tri benchmark ugla dobijaju isto private metadata polazište bez mešanja koeficijenata.
5. **Manual data QA:** originalni annotated chart naspram clean snapshot-a za svaki prihvaćen case.
6. **CLI preview:** privatni key prolazi orkestrator `--dry-run` bez upisa execution state-a.
7. **Paid smoke:** tačno jedan case/model/effort posle #77 i eksplicitne potvrde troška.

## Validation Commands

```bash
uv run --extra mcp pytest -q \
  tests/test_ground_truth_cases.py \
  tests/test_snapshot_builder.py \
  tests/test_scoring.py \
  tests/test_benchmark.py \
  tests/test_eval_orchestrator.py

uv run python -m compileall -q scripts/eval
git diff --check

CASE_ID="$(uv run python -c 'from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES; print(GROUND_TRUTH_CASES[0]["case_id"])')"
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case "$CASE_ID" \
  --model claude-opus-4-8 \
  --effort high \
  --dry-run
```

`CASE_ID` se izvodi iz prvog stvarno prihvaćenog ID-a u finalnom registry-ju; vrednost i tačnu izvršenu komandu zabeležiti u implementation report-u.

Plaćeni canary, tek uz operatorovu potvrdu i posle #77:

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case "$CASE_ID" \
  --model claude-opus-4-8 \
  --effort high \
  --max-concurrency 1 \
  --min-start-interval 2
```

## Acceptance Criteria

- [ ] Nijedan proizvoljni scaffold datum nije zadržan bez source/image/reconstruction dokaza.
- [ ] Svaki prihvaćeni case ima postojeći crypto raw Markdown, lokalnu sliku, validan excerpt opseg i dokumentovan symbol/timeframe/cutoff.
- [ ] Case count i event raspodela nisu hard-coded; prazan skup i nekvalitetan case se odbijaju.
- [ ] Privatni answer key koristi postojeći `ground_truth` kao veran ekspertski sažetak i sadrži provenance, `analysis_mode`, strukturirana expert polja i reconstruction notes.
- [ ] Nepomenute ekspertne činjenice su `not_stated`; retrospective outcome je `not_applicable` i determinističke dimenzije su `N/A`.
- [ ] Provenance/reconstruction podaci ne ulaze u analyst input, judge payload, angle `*.answer.json` ni public snapshot manifest; jedino `analysis_mode` se propagira u angle ključ.
- [ ] `analysis_mode` preživi pun lanac (`_answer_extra → build_snapshot → angle answer key → score_run`) i retrospective case dobija `N/A` determinističke dimenzije u realnom (ne samo unit) putu — dokazano integracionim testom.
- [ ] `expert_alignment_score` i `realized_outcome_score` postoje u score/row/group/report izlazima; postojeći aggregate/ranking ostaje kompatibilan.
- [ ] Existing forward deterministic replay, lookahead/leakage uglovi, answer-key isolation i no-write dry-run testovi ostaju zeleni.
- [ ] Runbook jasno kaže da source chart služi kuraciji, dok analyst i dalje dobija OHLCV tekst; #75 nije implementiran ovde.
- [ ] Implementation report navodi svaki prihvaćen/odbijen kandidat i evidence-based razlog, bez privatnog ground-truth teksta.
- [ ] Privatni key prolazi orkestrator dry-run. Real canary je ili uspešno pokrenut posle #77 i odobrenog troška, ili eksplicitno označen kao jedini preostali operator-gated korak.

## Completion Checklist

- [ ] #76 `SIMPLIFY` granica je očuvana.
- [ ] Implementacija je urađena na zasebnoj #76 grani/worktree-u, bez prepisivanja #77 dirty izmena.
- [ ] Svi taskovi imaju zabeležen validation rezultat.
- [ ] Nema novih dependencies, non-Binance koda ili Fraser/book scope creep-a.
- [ ] Nema privatnog answer key-a u git diff-u ili istoriji.
- [ ] Deep review je urađen pre merge-a jer promena dira eval contract i ground-truth semantiku.

## Risks and Mitigations

| Rizik | Posledica | Mitigacija |
| --- | --- | --- |
| Publication timestamp nije tačan cutoff | clean input ne odgovara izvoru | vizuelni pivot/last-candle gate; kandidat se odbija ako T nije pouzdan |
| Drugi exchange daje drugačije sveće | lažno “isti period” poređenje | Binance-direct kandidati prvi; exchange mismatch zahteva eksplicitni dokaz ili odbijanje |
| Premalo validnih slučajeva | nizak statistički signal | ship validan mali v1, dokumentuj gap; ne fabrikovati kvotu |
| Private metadata procuri judge-u | biased scoring | zadržati allowlist/redaction i dodati regresione testove |
| Retrospective case utiče na prediction score | hindsight kontaminacija | deterministic dimensions `N/A`, outcome group partial mean |
| Split score promeni ranking semantiku | neuporedivost starih izveštaja | aggregate i postojeći ranking ostaju nepromenjeni u v1 |
| Paralelni #77 dira orchestrator | merge konflikt ili izgubljena runtime popravka | ne menjati orchestrator u #76; zaseban worktree; canary posle #77 |
| Vizuelni QA nije automatski | ljudska greška | strukturisan reconstruction checklist + report sa prihvaćenim/odbijenim dokazima |

## Notes

- `prp-plan` runbook je adekvatan za ovaj zadatak: promena je codebase-first data/eval enhancement sa jasnim integracionim tačkama i testabilnim contract-ima. Jedina adaptacija je da su issue body i komentar korišćeni kao free-form feature input jer runbook ne navodi issue broj kao poseban input tip.
- Vizuelnim pregledom tokom planiranja potvrđeno je da vol. 43 slika eksplicitno prikazuje `Bitcoin / TetherUS · 4h · BINANCE`, dok vol. 24 XTZ slika prikazuje `XTZ / USD · 1D · KRAKEN`; zato druga nije bezuslovno validan Binance slučaj.
- Plan ne menja PRD status jer ulaz nije PRD faza.
- Sledeći izvođački korak posle review-a plana: `$prp-implement PRPs/plans/source-anchored-crypto-eval-set-v1.plan.md` na zasebnoj #76 grani/worktree-u.
