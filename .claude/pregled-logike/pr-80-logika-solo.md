# Pregled Logike — PR #80 (source-anchored crypto eval skup v1)

**Datum**: 2026-06-20
**Scope**: PR #80 — `feature/issue-76-source-anchored-eval` (13 fajlova; jezgro: `ground_truth_cases.py`, `scoring.py`, `benchmark.py`, `build_eval_set.py`)

---

## Zaključak eksperta

Osnovna ideja je odlična i to je najvažniji nalaz: vezivanje ground truth-a za **postojeći ekspertski tekst koji je već opisao baš taj grafikon** umesto za naknadno izmišljenu analizu rešava jedinu stvar koja je stari skup od 10 „proizvoljnih preseka" činila neupotrebljivim — proverljivost. Per-case provenance validator (path containment, postojanje slike, image-ref unutar excerpt opsega) je tačno mesto gde disciplina treba da živi. Dve rupe koje je plan-review označio (`analysis_mode` prenos do scoring-a, kopiranje provenance-a u angle ključeve) su u kodu **stvarno zatvorene** — verifikovao sam end-to-end test i izolaciju, 89/89 prolazi.

Najveći logički propust nije u implementaciji nego u **dimenziji skupa naspram deklarisane svrhe**: benchmark postoji da rangira model × effort (`rank_by_aggregate`), a n=3 (od čega samo 2 forward case-a hrane `realized_outcome_score`, 1 retrospective) ne može statistički da razlikuje modele — rang lista je tehnički ispravna, ali bezvredna kao signal. Drugorazredni propust: grupni `aggregate` meša forward i retrospective case-ove čiji se po-case skor renormalizuje preko **različitih imenilaca** (8 dimenzija vs samo judge dimenzije), pa headline broj koji ulazi u rang nije apples-to-apples. Najveća nepotrebna nepreciznost je ime `expert_alignment_score` — uključuje `narrative_quality` i `calibration`, koje nisu „slaganje sa ekspertskim čitanjem" nego kvalitet rezonovanja.

**Ocene:**
| Dimenzija | Ocena | Ukratko |
|-----------|-------|---------|
| Zdravlje ideje | 9/10 | Source-anchoring je prava premisa; rešava proverljivost ground truth-a. |
| Logički tok | 8/10 | Lanac zatvoren i testiran; ostaje mešanje imenilaca u `aggregate` koji ulazi u rang. |
| Opravdanost kompleksnosti | 8/10 | Reuse postojećeg toka, bez paralelnog scorer-a; jedino ime jednog podskora overclaim-uje. |

---

## Nivo 1 — Ideja i Premisa

**Šta sistem zapravo radi:** Generiše blind Wyckoff eval skup od 3 crypto case-a gde je svaki vezan za stvarni ekspertski grafikon + neposredni pasus, rekonstruiše Binance OHLCV do cutoff-a, i skoruje analizu kroz dva razdvojena podskora — slaganje sa ekspertom (judge) i uspeh forecast-a vs realizovana cena (deterministički replay).

**Pretpostavke koje sistem uzima zdravo za gotovo:**
- Binance OHLCV za 2020 datume je pouzdano rekonstruišljiv do cutoff-a → drži za vol-43/vol-24 (4h/1d, likvidni BTC/LINK); ostaje operatorov manuelni vizuelni QA da rekonstrukcija odgovara slici.
- Ekspertski pasus uz sliku = validan ground truth → drži; to je upravo poenta source-anchoring-a i jača je od ranije izmišljene analize.
- 3 case-a su dovoljna za **v1 temelj** → drži kao temelj, ali NE kao benchmark koji rangira (vidi rupu ispod).
- Judge dobija samo dozvoljena polja bez obzira na sadržaj answer ključa → drži; `prepare_judge_input` allowlist (`scoring.py:403-413`) je nezavisan od propagacije.

**Rupe u premisi:**

### Skup je premali za deklarisanu svrhu rangiranja
**Problem**: Cilj benchmark-a je rangiranje modela i effort nivoa (`rank_by_aggregate`, ROI rang liste). Sa n=3 — i `realized_outcome_score` koji se računa nad samo 2 forward case-a — nijedna razlika u rangu nije statistički razlučiva. Jedan flip ishoda na jednom case-u preokrene celu sliku.
**Posledica**: Rang lista izlazi kao da je merodavna, a zapravo je šum. Rizik je interpretacioni: neko će je čitati kao „model A > model B".
**Uticaj**: srednji — namerna v1 odluka („smaller-but-valid preko padding-a") je ispravna za kvalitet ground truth-a, ali izlazni artefakt (rang) treba eksplicitno označiti kao indikativan/nedovoljan dok se skup ne proširi. Ideja je zdrava; instanca je još pretanka za ono što izveštaj tvrdi.

---

## Nivo 2 — Logički Tok

**Tok sistema:**
1. `GROUND_TRUTH_CASES` (javni metapodaci) + privatni gitignored answer ključ → ✓
2. `validate_event_coverage` — per-case provenance, path containment, excerpt↔image → ✓
3. `angle_answer_metadata(answer)` allowlist (`event_type/realized_direction/decisive/analysis_mode`, bez provenance) → ✓
4. `_answer_extra` / `build_eval_set` → `build_snapshot` → `answer_key.update(answer_extra)` → angle `*.answer.json` → ✓
5. load angle ključa → `score_deterministic` (retrospective → N/A rano, pre normalizacije) → ✓
6. `combine_scores` → `aggregate` (svi scored) + `expert_alignment_score` (judge) + `realized_outcome_score` (deterministic) → ⚠
7. `_build_groups` → `mean_*` preko `_mean` (N/A isključen, ne 0) → grupni `aggregate` → `rank_by_aggregate` → ⚠

**Propusti u toku:**

### Grupni `aggregate` meša case-ove sa različitim imeniocima, a hrani rang
**Vrsta**: pogrešan redosled/agregacija (mešanje nesamerljivih veličina)
**Lokacija**: `scoring.py:481` (`_weighted_mean_over` renormalizuje po-case preko scored dimenzija) → `benchmark.py:489-490, 512` (grupni prosek i `rank_by_aggregate`)
**Problem**: Forward case-u `aggregate` se renormalizuje preko 8 dimenzija; retrospective case-u preko samo 5 judge dimenzija (deterministic su N/A). Grupni `aggregate` zatim prosečuje te dve veličine kao da su iste, i taj prosek ulazi u rang listu. Dva nova podskora su uvedena baš da daju čistu komparaciju, ali headline broj koji rangira i dalje meša modove.
**Predlog**: Ili rangirati po `expert_alignment_score` (definisan za sve case-ove jednako), ili u izveštaju eksplicitno odvojiti rang forward vs retrospective, ili bar fusnotirati da je `aggregate` mod-zavisan. Isti efekat već postoji za `wait_case`, pa je ovo proširenje postojećeg duga, ne nov.
**Uticaj**: srednji — sa trenutnih 2F/1R skup je mali pa je distorzija vidljiva; raste ako se odnos modova promeni.

### `make_placeholder_answers` modovi se ne poklapaju sa stvarnim modovima case-ova
**Vrsta**: preskočen korak (slaba veza dry-run ↔ realnost)
**Lokacija**: `ground_truth_cases.py:158` (`index % 3 == 2`)
**Problem**: Placeholder dodeljuje retrospective samo 3. case-u po poziciji; slučajno se poklopi sa `btc_vol24` ali to je koincidencija indeksa, ne veza sa stvarnim modom case-a. Ako se redosled `GROUND_TRUTH_CASES` promeni, dry-run vežba pogrešan mod za case.
**Predlog**: Dry-run svrha je samo da okine obe grane scoring-a — što i radi — pa je nizak prioritet; ali komentar treba da kaže „alternira radi pokrivenosti grana, namerno nije vezan za stvarni mod".
**Uticaj**: nizak.

---

## Nivo 3 — Nužnost Kompleksnosti

**Direktan put vs. stvaran put:**
- Minimalan put (ground truth → snapshot → judge+deterministic → skor): ~5 koraka.
- Trenutni: ~7 koraka (dodati provenance validacija + split podskorovi).
- Razlika: 2 — **opravdana**. Provenance validacija je sama svrha issue-a; split podskorovi mapiraju 1:1 na postojeće `DETERMINISTIC_DIMENSIONS`/`JUDGE_DIMENSIONS` bez paralelnog scorer-a.

**Nepotrebna kompleksnost:**

### Ime `expert_alignment_score` overclaim-uje svoj sadržaj
**Vrsta**: nepreciznost imenovanja sa semantičkim teretom (ne mrtav kod)
**Lokacija**: `scoring.py:487` — `_weighted_mean_over(dimensions, JUDGE_DIMENSIONS)`
**Problem**: `JUDGE_DIMENSIONS` = `{structure, phase, event, narrative_quality, calibration}`. Prva tri jesu „slaganje sa ekspertskim čitanjem"; `narrative_quality` i `calibration` su kvalitet rezonovanja i kalibracija pouzdanosti — nisu alignment sa ekspertom. Ime tvrdi više nego što meri, a izveštaj (`render_report_markdown`) tu tvrdnju propagira u Markdown legendu.
**Alternativa**: Ili suziti `expert_alignment_score` na `{structure, phase, event}` (semantički match), ili preimenovati u `judge_score` da ime ne tvrdi semantiku koju ne garantuje. Nije nužno za merge, ali jeste konceptualni dug u contract-u.
**Uticaj**: nizak — ne lomi ništa, ali ime je deo eval ugovora pa zavodi čitaoca izveštaja.

---

## Šta drži

- **Premisa**: source-anchoring (ground truth iz postojećeg ekspertskog teksta vezanog za baš taj grafikon) je tačno rešenje za proverljivost — najvredniji deo PR-a.
- **Plan defekti su zatvoreni, ne samo obećani**: `angle_answer_metadata` uvrštava `analysis_mode` i isključuje provenance; integracioni test `test_analysis_mode_propagates_provenance_does_not` + `test_retrospective_angle_key_scores_na_end_to_end` dokazuju end-to-end prenos i odsustvo leak-a iz angle ključa. Verifikovano: 89/89 prolazi.
- **Defense-in-depth izolacija**: judge ostaje izolovan kroz `prepare_judge_input` allowlist nezavisno od propagacije — dva sloja, ne jedan.
- **Retrospective grana je rano, pre normalizacije** (`scoring.py:283`) — izbegava `_normalize_direction("not_applicable")` ValueError; tačan redosled.
- **Negativni kontrolni primer** (XTZ/Kraken odbijen kao ne-Binance) pokazuje da je validator stvarno diskriminativan, ne dekorativan.
- **`_mean` isključuje N/A umesto da broji 0** — sprečava da retrospective/wait podskorovi lažno spuste grupni prosek.

---

## Preporučeni sledeći koraci

1. **Označi rang kao indikativan dok je n mali.** U izveštaju (`render_report_markdown`) dodati eksplicitnu napomenu da `rank_by_aggregate` sa n=3 nije statistički merodavan — najjeftinija zaštita od pogrešnog čitanja. (Premisa-rupa, srednji uticaj.)
2. **Reši mod-zavisni `aggregate` u rangu.** Rangirati po `expert_alignment_score` (jednako definisan za sve modove) ili razdvojiti forward/retrospective rang; bar fusnotirati da `aggregate` imenilac zavisi od moda. (Tok-propust, srednji uticaj.)
3. **Suzi ili preimenuj `expert_alignment_score`** da ime ne uključuje narrative/calibration ako tvrdi „expert alignment". (Konceptualni dug, nizak uticaj.)
4. (Van koda) Plan proširenja skupa preko n=3 — definisati ciljani broj forward case-ova na kojem `realized_outcome` rang postaje smislen.

---
*Generisao: mk-pregled-logike-solo*
*Izveštaj: `.claude/pregled-logike/pr-80-logika-solo.md`*
