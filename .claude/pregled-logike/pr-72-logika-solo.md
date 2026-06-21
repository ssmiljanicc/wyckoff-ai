# Pregled Logike — PR #72 (Faza 4 / Phase 6: benchmark batch + report)

**Datum**: 2026-06-19
**Scope**: PR #72 — `scripts/eval/benchmark.py` (nov), `scripts/eval/snapshot_builder.py` (reveal mod), testovi

---

## Zaključak eksperta

Premisa je zdrava i verno prati PRD: „kod priprema matricu + skoruje + agregira; LLM se zove iz runbook-a" je dosledno Fazi 2/4, reuse `scoring.py` je tačan, a Δ-nad-zajedničkim-case-ovima (sa isključivanjem nedostajućih, ne kao 0) je statistički korektan. **Najveći logički propust:** od dve reklamirane kontrole, samo jedna (anon→revealed) je end-to-end — `--ensure-snapshots` generiše isključivo `__revealed`, dok `__fv` snapshote za 10 ground-truth tačaka **niko ne pravi** (Phase 3 `build_eval_set` pravi samo `blind`). Plan je pogrešno pretpostavio „blind/fv već postoje iz Phase 3"; to ne stoji, pa `delta_lookahead` u praksi izlazi prazan (ili gori — vidi rupu 1). **Najveća nepotrebna kompleksnost:** obe kontrole se kartezijanski množe sa celom model×effort matricom bez ijednog knoba za scope, pa ~2/3 od 480 ćelija (svaka = ručni analyst+judge subagent par) odgovara na pitanje koje podskup tačaka rešava.

**Ocene:**
| Dimenzija | Ocena | Ukratko |
|-----------|-------|---------|
| Zdravlje ideje | 8/10 | Premisa zdrava i PRD-usklađena; minus jer „obe kontrole" nije end-to-end |
| Logički tok | 6/10 | Δ/agregacija tačni; ali lookahead generacioni jaz + ROI mešanje jedinica + dual-source ingest |
| Opravdanost kompleksnosti | 6/10 | Većina opravdana; minus za kontrole × puna matrica bez scope knoba |

---

## Nivo 1 — Ideja i Premisa

**Šta sistem zapravo radi:** Enumeriše grid (case × kontrola × model × effort) eval-run-ova sa praznim slotovima koje eksterni orkestrator popunjava, pa skoruje/agregira popunjene run-ove i izračunava dva kontrasta (Δleakage, Δlookahead) + ROI rang u jedan report.

**Pretpostavke koje sistem uzima zdravo za gotovo:**
- `case__fv` (future_visible) snapshoti za ground-truth set već postoje → **NE drži** (Phase 3 pravi samo `blind`; vidi rupu 1).
- `trigger`/`invalidation` su numerički u prostoru answer key-a (anon za anon, real za revealed) → drži (answer key se rutira po `anon_mode`).
- Token-usage po (model,effort,case,kontrola) run-u beleži orkestrator → drži uslovno (harness daje usage za Claude subagent-e).
- `__fv` za `case_0X` odgovara istom instrumentu kao `case_0X` blind → **rizično** (namespace `case_01..03` deli sa Phase 2 probe-om koji ima DRUGE simbole/cutoff-e).

### Rupa 1 — Lookahead kontrola nema generacioni put
**Problem**: `--ensure-snapshots` → `ensure_revealed_snapshots` pravi samo `__revealed`. `case__fv` za 10 ground-truth tačaka ne pravi niko: `build_eval_set.run` zove `build_snapshot(mode="blind")`, a nema `ensure_fv_snapshots`. `build_run_matrix` to signalizira (`missing_snapshot=True` za sve lookahead specove), ali ne postoji alat da se popravi.
**Posledica**: `delta_lookahead` izlazi prazan (n=0, delta=None) — jedna od dve PRD kontrole („obe kontrole") ne radi out-of-the-box. Gore: ako postoje stale `__fv` iz Phase 2 probe-a (`case_01..03`, ali BTC 2019 / ETH 2020 / BTC 2021 — drugi instrument od ground-truth `case_01..03`), Δlookahead bi se računao nad **pogrešnim podacima** tiho.
**Uticaj**: visok

### Rupa 2 — Deljen `case_id` namespace između probe-a i ground-truth seta
**Problem**: Phase 2 probe (`case_01/02/03` = BTC2019/ETH2020/BTC2021) i Phase 3 ground-truth (`case_01` = ETH2020-03-13, `case_02` = BTC2026, …) pišu u iste `data/eval/case_0X` dir-ove i `_answers/case_0X.answer.json`. Ovaj PR to ne uvodi, ali ga benchmark **aktivira**: lookahead angle čita `case_0X__fv` i `case_0X.answer.json` pretpostavljajući da su isti instrument.
**Posledica**: tiha kontaminacija ako oba sloja koegzistiraju na disku.
**Uticaj**: srednji (pre-postojeće, ali ovaj PR ga čini eksploatabilnim)

---

## Nivo 2 — Logički Tok

**Tok sistema:**
1. `build_run_matrix` → specovi po case × kontrola × model × effort → ✓
2. `write_run_matrix` → `benchmark_runs.json` sa praznim slotovima (kod ne zove LLM) → ✓
3. `--ensure-snapshots` → regeneriše `__revealed` → ⚠ (samo revealed, ne i fv — rupa 1)
4. [runbook] orkestrator puni `results/<run_id>.json` → ✓ (van koda, po dizajnu)
5. `--ingest` → `score_run` (reuse scoring) → `aggregate_report` → `render_report_markdown` → ✓
6. `aggregate_report` grupiše SAMO baseline (blind,anon) za rang/tabelu; Δ nad svim redovima sa internim filterom → ✓

**Propusti u toku:**

### Rang po ROI meša jedinice
**Vrsta**: neispravno korišćen rezultat
**Lokacija**: `benchmark.py` `aggregate_report` → `rank_by_roi` + `render_report_markdown` „Rank by ROI"
**Problem**: Codex redovi imaju `roi_basis="tokens"` (skor/1k tok), Claude redovi `roi_basis="usd"` (skor/$). Sve se sortira u JEDNU listu po numeričkoj vrednosti. ROI=0.5 (tokens) i ROI=0.5 (usd) nisu uporedivi; jedinstven rang poziva na nevalidno cross-model poređenje (Codex vs Opus).
**Predlog**: rangirati unutar svake `roi_basis` grupe odvojeno (dve tabele), ili rang po ROI raditi samo nad usd-basis redovima dok Codex nema cenu; basis kolona ostaje, ali bez mešanog sorta.
**Uticaj**: srednji

### Ingest re-derivira RunSpec iz run_id stringa
**Vrsta**: redundantan/duplican izvor istine
**Lokacija**: `benchmark.py` `_spec_from_run_id` vs `benchmark_runs.json`
**Problem**: `benchmark_runs.json` nosi pune specove, ali `ingest` ignoriše manifest i rekonstruiše spec iz imena fajla (`run_id.split("__")`, 5 delova). Dva koda grade `RunSpec` (`build_run_matrix` i `_spec_from_run_id`) koja moraju ostati u sinhronu; pozicioni `__` split puca čim neko polje dobije `__`.
**Predlog**: ingest da čita specove iz `benchmark_runs.json` (jedan izvor istine); run_id ostaje samo ključ za uparivanje sa `results/<run_id>.json`.
**Uticaj**: nizak-srednji

---

## Nivo 3 — Nužnost Kompleksnosti

**Direktan put vs. stvaran put:**
- Baseline benchmark (rang model×effort) zahteva pun sweep — opravdano.
- Dve kontrole odgovaraju na „da li recognition/lookahead naduvavaju skor?" — to je svojstvo koje se meri na PODSKUPU (PRD: „≥5 zajedničkih tačaka", ne „cela matrica").

### Kontrole × puna model×effort matrica bez scope knoba
**Vrsta**: over-engineering / mrtva kompleksnost u izvršavanju
**Lokacija**: `build_run_matrix` (kontrole se loop-uju zajedno sa `matrix`)
**Problem**: 10 case × 3 kontrole × 16 (model,effort) = **480 ćelija**; baseline je 160, kontrole 320. Svaka ćelija = jedan ručni analyst subagent + jedan judge subagent. Δleakage/Δlookahead nad SVIH 16 model×effort ćelija je 2/3 ručnog toila za pitanje koje PRD formuliše po broju tačaka. Nema parametra da se kontrole ograniče na npr. 1–2 reprezentativna (model,effort).
**Alternativa**: `build_run_matrix(..., control_models=…, control_efforts=…)` ili poseban tanji generator za kontrole; baseline dobija pun sweep, kontrole samo podskup.
**Uticaj**: srednji-visok (množilac ručnog toila na već ručnom procesu)

---

## Šta drži

- Premisa „kod priprema, runbook zove LLM" — čista i dosledna Fazi 2/4; kod stvarno ne zove model.
- `score_run` reuse-uje `scoring.score_deterministic`/`combine_scores` — ne reimplementira skoring.
- `_build_delta` nad **zajedničkim** case-ovima, nedostajući isključen (ne 0) — statistički ispravno.
- `aggregate_report` rangira SAMO baseline (kontrole ne zagađuju benchmark) — tačna separacija.
- `reveal` answer-key separacija (`__revealed` suffiks + manifest dedup po `(case, mode, reveal)`) — korektno rešava overwrite anon ključa.
- Četvrti ugao `(future_visible, revealed)` namerno izostavljen — dobra uzdržanost, ne over-build.

---

## Preporučeni sledeći koraci

1. **Zatvori lookahead generacioni jaz (rupa 1):** dodati `ensure_fv_snapshots` (build_snapshot `mode="future_visible"` za ground-truth set) i uvezati ga u `--ensure-snapshots`; bez toga ukloniti `delta_lookahead` iz reporta da ne reklamira praznu kontrolu. Ujedno rešiti deljeni `case_id` namespace probe↔ground-truth (rupa 2) — npr. prefiks `gt_` za ground-truth ili poseban base-dir.
2. **Ograniči kontrole na podskup matrice:** parametar za (model,effort) scope kontrola; baseline ostaje pun sweep. Smanjuje ručni toil sa ~480 na ~160+δ ćelija.
3. **Razdvoji ROI rang po basis-u:** ne sortirati usd i tokens ROI u istoj listi; dve tabele ili usd-only rang dok Codex nema cenu.
4. **(opc.) Ingest da čita specove iz `benchmark_runs.json`** umesto pozicionog parsiranja `run_id`.

---
*Generisao: mk-pregled-logike-solo*
