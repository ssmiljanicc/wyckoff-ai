# Pregled Plana — source-anchored-crypto-eval-set-v1

**Datum**: 2026-06-20
**Plan**: `PRPs/plans/source-anchored-crypto-eval-set-v1.plan.md`
**Presuda**: REVISE-PLAN

## Zaključak

Premisa je izrazito zdrava: plan zamenjuje deset proizvoljnih datuma source-anchored crypto skupom, gde je ground truth vezan za postojeći ekspertski grafikon + neposredni pasus, a postojeći snapshot/judge/deterministic tok se zadržava. Proverio sam seed kandidata — `raw/crypto_archive/posts/wyckoff-crypto-report-vol-43.md:8-16` i slika `01-lead-71fc2a91.png` stvarno postoje, a `ground_truth` sažetak u contract-u verno prepričava izvor (SCENARIO 1/2 + PATTERN FAILURE na $14300). Podela skora na `expert_alignment` (judge) i `realized_outcome` (deterministic replay) je čisto motivisana i dobro mapira na postojeći kod.

Najveći logički propust nije u premisi nego u **prenosu `analysis_mode` kroz lanac**: Task 4 zahteva da `score_deterministic` vidi `analysis_mode`, ali Task 3 (jedini koji gradi propagaciju u angle answer key) nigde eksplicitno ne navodi to polje, a nijedan acceptance kriterijum ne dokazuje end-to-end prenos — pa retrospective grana može tiho da nikad ne okine u realnim run-ovima dok unit scoring test prolazi. Najveća nepotrebna kompleksnost je odluka iz contract-a (linija 134) da se provenance/reconstruction polja kopiraju i u angle-specific answer ključeve, iako ih odande niko ne čita — to samo širi leak-surface koji Task 6 onda mora da testira.

**Ocene:** Premisa 9/10 · Tok 7/10 · Nužnost kompleksnosti 7/10

## Nalazi po težini

### [VAŽNO] `analysis_mode` prenos do scoring-a nije zatvoren između Task 3 i Task 4 — PLAN DEFECT

**Tvrdnja plana**: Task 4 (linije 214-220): „u `score_deterministic` rano prepoznati `analysis_mode == 'retrospective'`". Task 3 (linije 205-212): allowlist helper „vraća metadata za angle-specific answer key" — bez imenovanja kojih polja.

**Stvarnost**: Lanac do scoring-a je: `_answer_extra(answer)` (`benchmark.py:864-869`) i inline lista (`build_eval_set.py:49-53`) → `build_snapshot(..., answer_extra=...)` → `answer_key.update(answer_extra)` (`snapshot_builder.py:358-359`) → angle fajl `*.answer.json` → `json.loads(...answer_key_path)` (`benchmark.py:821`) → `score_run(..., answer_key)` → `score_deterministic(answer_key=...)` (`benchmark.py:406-412`). Trenutni `_answer_extra` prosleđuje **samo** `event_type/realized_direction/decisive`. Ako Task 3 helper ne uvrsti `analysis_mode` u allowlist, `score_deterministic` ga nikad ne dobije — retrospective detekcija nikad ne okine, a forward grana onda pokuša `_normalize_direction("not_applicable")` → `ValueError` (`scoring.py:195`), ili padne na fallback ako `realized_direction` fali.

**Posledica**: Unit scoring test koji `analysis_mode` prosleđuje direktno u `answer_key` prolazi (Task 6 „retrospective testove" pod scoring-om), ali realni benchmark/orchestrator run puca ili tiho tretira retrospective kao forward. Acceptance lista (linije 300-312) to ne hvata — nijedan kriterijum ne dokazuje da `analysis_mode` preživi `_answer_extra → build_snapshot → load`.

**Popravka**: U Task 3 eksplicitno navesti da propagacioni allowlist sadrži `analysis_mode` (pored postojeća tri polja). U Task 6 dodati integracioni assert: posle `build_snapshot` angle `*.answer.json` sadrži `analysis_mode`, a `score_deterministic` nad učitanim angle ključem daje `N/A` determinističke dimenzije za retrospective case. Dodati i Acceptance stavku za taj end-to-end prenos.

### [VAŽNO] Provenance se kopira u angle-specific answer ključeve bez potrošača — PLAN DEFECT (over-build)

**Tvrdnja plana**: Contract, linija 134: „Provenance i reconstruction polja ostaju u privatnom answer key-u **i angle-specific kopijama**, ali se ne šalju analyst-u niti judge-u." Task 6 (linija 232) zato mora da testira da judge payload ne sadrži `source_path`, author, URL, reconstruction notes.

**Stvarnost**: Izolacija judge-a je već zagarantovana **allowlist-om** u `prepare_judge_input` (`scoring.py:369-379`) — judge dobija samo `ground_truth/event_type/realized_direction/decisive`, bez obzira šta još stoji u answer ključu. Scoring od novih polja treba **isključivo `analysis_mode`** (Nalaz 1). Audit/report (Task 7) čita master privatni ključ tokom kuracije, ne angle ključeve u benchmark-u. Dakle ništa ne čita `source_path/source_image_path/expert_author/source_url/reconstruction_notes` iz angle ključa.

**Posledica**: Plan svesno upisuje tajne (provenance) u generisane angle answer fajlove gde im nije mesto, pa onda gradi regresione testove (Task 6) da brani tu samonametnutu izloženost. Suvišan korak protivan samoj svrsi issue-a (#76 je o provenance disciplini i izolaciji).

**Popravka**: Suziti propagacioni allowlist na `analysis_mode` (+ postojeća tri). Provenance/reconstruction držati **isključivo u gitignored master privatnom ključu** `data/eval/_answers/ground_truth_answers.json`; nikad ih ne kopirati u angle `*.answer.json`. Tako Task 6 izolacioni testovi postaju defense-in-depth umesto čuvanja stvarne izloženosti, a linija 134 contract-a se prepravlja.

### [SITNO] `make_placeholder_answers` zavisi od `EVENT_QUOTA` koju Task 2 uklanja — PLAN DEFECT (completeness)

**Tvrdnja plana**: Task 2 (linija 199): „ukloniti `EVENT_QUOTA`, očekivani count i post-2026 minimum." Files to Change navodi `build_eval_set.py` sa svrhom „dry-run-only placeholder dozvola".

**Stvarnost**: `make_placeholder_answers` (`ground_truth_cases.py:121-154`) je sagrađena oko `EVENT_QUOTA` (iterira kvotu da napravi `event_sequence` i `directions`). Pozivaju je `build_eval_set.run(dry_run=True)` (`build_eval_set.py:28`) i `_load_benchmark_cases_and_answers` (`benchmark.py:857`). Nijedan task eksplicitno ne preoblikuje ovu funkciju u quota-free generator sa eksplicitnim placeholder markerom (koji contract linija 135 zahteva).

**Posledica**: Ako se `EVENT_QUOTA` obriše a `make_placeholder_answers` ne prepiše, dry-run i benchmark dry path bacaju `NameError`. Implicitno je, ali nije zakačeno za task sa VALIDATE.

**Popravka**: U Task 2 dodati eksplicitnu stavku: prepisati `make_placeholder_answers` da generiše placeholder odgovore za promenljiv case set bez kvote, sa eksplicitnim placeholder markerom i (sada) `analysis_mode`; VALIDATE preko `build_eval_set --dry-run` i postojećeg dry path-a.

## Van scope-a (post-code)

- Da li real Binance reconstruction za vol-24 BTC daily zaista vizuelno odgovara izvoru (Candidate Gate korak 5) — VALIDATION GAP, dokaziv tek pri implementaciji; ostaje operatorov manuelni QA po planu.
- Da li završni `aggregate`/ranking ostaje uporediv kad se mešaju forward i retrospective case-ovi u istoj grupi — IMPLEMENTATION DRIFT; isti efekat već postoji za `wait_case`, prati ga `prp-review` posle koda.

## Šta drži

- **Premisa i seed**: vol-43 izvor i slika postoje; `ground_truth` u contract-u verno prepričava izvor; `expert_invalidation: 14300` i spring 15.5k se poklapaju sa tekstom.
- **Reuse postojećeg toka**: podela na judge/deterministic podskorove direktno mapira na `scoring.py:17-20` dimenzije i `combine_scores` renormalizaciju (`:424-434`); plan ne pravi paralelni scorer.
- **#77 paralelizam**: zadržavanje imena `validate_event_coverage` čuva call-site `orchestrator.py:335` i izbegava konflikt — tačno i opravdano.
- **Retrospective nije špekulacija**: vol-24 BTC daily je stvarno retrospektivna naracija („WYCKOFF STORY [1]…[5]"), pa Task 4 mode nije over-build za scenario koji se neće desiti.
- **Negativni kontrolni primer**: XTZ je dokazano Kraken (`09-xtz...png`), pa je odbijanje kao ne-Binance reconstruction ispravno postavljeno.
