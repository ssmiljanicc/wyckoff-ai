# Implementacioni izveštaj — Source-anchored crypto eval set v1

**Plan:** `PRPs/plans/source-anchored-crypto-eval-set-v1.plan.md`
**Source issue:** #76 (+ `SIMPLIFY` komentar od 2026-06-20)
**Grana:** `feature/issue-76-source-anchored-eval`
**Datum:** 2026-06-20
**Status:** COMPLETE (offline); jedan plaćeni canary ostaje operator-gated do merge-a #77

---

## Sažetak

Zamenjen je skup od deset proizvoljno izabranih tržišnih preseka source-anchored skupom od **3 crypto slučaja** za koje postoje originalni ekspertski grafikon, neposredni ekspertski tekst i pouzdano rekonstruisan Binance OHLCV presek do cutoff-a T. Uklonjena je fiksna event kvota, fiksni count i post-2026 minimum; validacija je sada **po-case** (source anchor + kvalitet), ne set-level distribucija. Dodati su `analysis_mode` (forward/retrospective) i provenance u privatni answer key, a postojeće dimenzije su izložene kao dva imenovana podskora: `expert_alignment_score` i `realized_outcome_score`. Postojeći snapshot/analyst/judge/deterministic tok i `aggregate`/ranking ostaju nepromenjeni.

---

## Kuracioni audit (Task 1)

Kandidati su pregledani vizuelnim otvaranjem originalnih slika i čitanjem pripadajućeg ekspertskog pasusa. Šest curation kapija iz plana primenjeno na svaki.

### Prihvaćeni slučajevi (3)

| case_id | Izvor | Slika | Symbol/TF/cutoff | analysis_mode | Dokaz |
| --- | --- | --- | --- | --- | --- |
| `btc_vol43_2020_11` | crypto-report-vol-43 (l. 10–15) | `…/vol-43/01-lead-71fc2a91.png` | BTCUSDT · 4h · 2020-11-13 | forward_looking | Naslov panela eksplicitno „Bitcoin / TetherUS · 4h · BINANCE". Direktan Binance match. Forward scenariji (continuation / spring ~15.5k) i pattern failure @14.3k. Dashed projekcije desno od T se ne rekonstruišu. |
| `link_vol24_2020_06` | crypto-report-vol-24 (l. 34–36) | `…/vol-24/07-CHAINLINK-f87a5082.png` | LINKUSDT · 1d · 2020-06-05 | forward_looking | Naslov „ChainLink / TetherUS · 1D · BINANCE". Forward „bullish scenario", PnF target ~$5.50. Ekspertske labele (PSY/BC/ST/AR/SPRING/MSOS/LPS/BU) i projekcija se uklanjaju rekonstrukcijom iz raw OHLCV-a. |
| `btc_vol24_2020_06` | crypto-report-vol-24 (l. 12–20) | `…/vol-24/02-BTC_DAILYY-3ae1b23c.png` | BTCUSDT · 1d · 2020-06-05 | retrospective | Bar-by-bar „WYCKOFF STORY" [1]–[5] objašnjava već realizovan obrazac → outcome dimenzije `N/A`. Naslov „BITCOIN (DAILY)" bez exchange taga, ali za taj period (mart 2020 ~5k → ~9.7k) Binance BTCUSDT daily sveće odgovaraju štampanom opsegu. |

### Odbijeni kandidati

| Kandidat | Razlog odbijanja |
| --- | --- |
| crypto-report-vol-24 — XTZ daily (`09-xtz______-dfd5ee30.png`) | Naslov „XTZ / USD · 1D · **KRAKEN**". Negativni kontrolni primer iz plana: exchange mismatch, nema dokumentovanog vizuelnog podudaranja sa Binance XTZUSDT; ima i green forward projekciju desno od T. Odbijen po kapiji #3. |

Target plana je bio 3–5; isporučeno 3 (2 forward + 1 retrospective), što daje pokrivenost oba scoring puta i oba podskora. Manji-ali-validan v1 je eksplicitno dozvoljen planom; nije fabrikovan nijedan slučaj radi kvote.

**Napomena o vizuelnoj rekonstrukciji:** poređenje originalne anotirane slike i *čistog* rekonstruisanog grafikona po slučaju zahteva real (network) build i radi se na operator-gated canary koraku posle #77. Original-image analiza (symbol/timeframe/desni rub, projekcije) urađena je tokom kuracije i zabeležena u `reconstruction_notes` privatnog ključa.

---

## Privatni answer key

`data/eval/_answers/ground_truth_answers.json` — kreiran lokalno, **gitignored** (`git check-ignore` potvrđen). Sadrži veran `ground_truth` (bez tvrdnji van označenog excerpt-a; izostanci = `not_stated`), `analysis_mode`, provenance i reconstruction belešku. Sadržaj se ne kopira u ovaj izveštaj.

---

## Taskovi

| # | Task | Fajl(ovi) | Status |
| --- | --- | --- | --- |
| 1 | Kuracija + privatni answer key | `ground_truth_cases.py` (registry), lokalni ignored key | ✅ |
| 2 | Source-anchor validator umesto kvote | `ground_truth_cases.py` | ✅ |
| 3 | Centralizovana metadata propagacija (`analysis_mode`) | `ground_truth_cases.py`, `build_eval_set.py`, `benchmark.py` | ✅ |
| 4 | Forward/retrospective deterministic scoring | `scoring.py` | ✅ |
| 5 | Dva podskora iz postojećih dimenzija | `scoring.py`, `benchmark.py` | ✅ |
| 6 | Regresioni + integracioni testovi | `tests/test_*.py` (5 fajlova) | ✅ |
| 7 | Runbook + ovaj report | `runbooks/faza-4-eval-orchestrator.md`, ovaj fajl | ✅ |
| 8 | Offline validacija + dry-run; canary gated | — | ✅ (canary gated) |

---

## Rezultati validacije

| Provera | Rezultat | Detalji |
| --- | --- | --- |
| Type/compile | ✅ | `python -m compileall -q scripts/eval` |
| Lint | ⏭️ | ruff nije konfigurisan u repo-u; `git diff --check` bez grešaka |
| Eval test paket | ✅ | 89 prošlo (sa 63 baseline) |
| Pun repo paket | ✅ | 272 prošlo |
| Orchestrator `--dry-run` | ✅ | `scope: 3, planned: 3, unavailable: {}`; privatni key validiran, provenance proverena nad realnim `raw/` stablom |
| Real canary | ⏳ | Operator-gated: posle merge-a #77 + potvrde troška |

Izvršena dry-run komanda (CASE_ID iz prvog prihvaćenog ID-a):

```bash
uv run --extra mcp python -m scripts.eval.orchestrator \
  --answers-path data/eval/_answers/ground_truth_answers.json \
  --case btc_vol43_2020_11 --model claude-opus-4-8 --effort high --dry-run
```

---

## Izmenjeni fajlovi

| Fajl | Akcija |
| --- | --- |
| `scripts/eval/ground_truth_cases.py` | prepisan: source-anchored registry, validator, `angle_answer_metadata`, quota-free `make_placeholder_answers` |
| `scripts/eval/build_eval_set.py` | `angle_answer_metadata` propagacija; `allow_placeholders=dry_run` |
| `scripts/eval/scoring.py` | retrospective `N/A` grana; `_weighted_mean_over`; dva podskora u `ScoreRecord` |
| `scripts/eval/benchmark.py` | podskorovi u row/group/report; `_answer_extra` delegira na helper |
| `tests/test_ground_truth_cases.py` | prepisan na provenance/variable-count/path-escape contract |
| `tests/test_scoring.py` | retrospective + split-score testovi |
| `tests/test_benchmark.py` | row/group/report podskorovi; real case_id za ensure_* |
| `tests/test_snapshot_builder.py` | integracioni propagation + provenance izolacija |
| `tests/test_eval_orchestrator.py` | real-like source-anchored fixture umesto placeholder fajla |
| `runbooks/faza-4-eval-orchestrator.md` | source-anchored sekcija, analysis modes, dva podskora, #77 canary |
| `data/eval/_answers/ground_truth_answers.json` | **gitignored**, nije u istoriji |

`scripts/eval/orchestrator.py` nije menjan (zadržan kompatibilan entry point `validate_event_coverage` radi #77 paralelizma).

---

## Odstupanja od plana

- **Broj slučajeva:** 3 prihvaćena (target 3–5). U okviru dozvoljenog manjeg-validnog v1; gap (Fraser/stock, dodatni crypto) dokumentovan.
- **`_weighted_mean_over` reuse za `aggregate`:** plan je tražio „zadržati postojeći aggregate"; `aggregate` je preračunat istim helper-om ali sa identičnom 0.0-when-empty semantikom (suma je order-nezavisna, `test_aggregate_skips_na` = 0.2308 nepromenjen), pa je vrednost bit-identična starom kodu.

Nema drugih odstupanja.

---

## Otklonjeni nalazi review-a (PR #80 — mk-pregled-logike-solo)

- **Mod-zavisni `aggregate` u rangu (srednji uticaj):** `expert_alignment_score` sužen na semantic-match dimenzije (`structure/phase/event`) — identično definisan za oba moda, pa je to apples-to-apples cross-mode poređenje. `render_report_markdown` sada fusnotira da je `aggregate` mode-dependent i preusmerava na `expert_alignment` za poređenje.
- **Mali n / rang kao šum (srednji uticaj):** rang sekcija u izveštaju nosi eksplicitno upozorenje „indikativno, ne statistički merodavno" sa prikazom najmanjeg `n`.
- **`expert_alignment_score` overclaim (nizak):** ime sada tačno odgovara sadržaju — `narrative_quality`/`calibration` su izvan podskora (ostaju u `aggregate` i per-dimension tabeli). Novi test `test_expert_alignment_covers_only_semantic_match_dimensions`.
- **Placeholder modovi (nizak):** docstring + inline komentar `make_placeholder_answers` sada eksplicitno kažu da mod alternira samo radi pokrivenosti grana i nije vezan za stvarni `analysis_mode` slučaja.

## Sledeći koraci

- [ ] Deep review pre merge-a (promena dira eval contract i ground-truth semantiku — per CLAUDE.md §0.2).
- [ ] Posle merge-a #77: pregledati dry-run, potvrditi trošak, pokrenuti jedan real canary i u tom koraku uraditi vizuelno poređenje original/clean chart po slučaju.
- [ ] (Van koda) Definisati ciljani broj **forward** slučajeva na kojem `realized_outcome` rang postaje statistički smislen, pre širenja skupa preko v1 n=3.
- [ ] PR ka grani #76.
