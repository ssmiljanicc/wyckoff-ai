# Feature: Phase 2 — Lookahead probe + dual-mode snapshot prep + anonimizacija

## Summary

Reproducibilan generator zamrznutih eval-snapshota sa dva moda — `blind` (sveće samo do T) i `future_visible` (sveće do T+N + „as-of T" marker) — i lookahead-honesty probe koji **prvo** dokazuje da li agent „vara" gledanjem budućnosti. Ako probe pokaže da ne vara, ostatak blinding mašinerije se gradi tanje. Generator koristi `get_ohlcv(end_time=...)` iz Phase 1, popravlja pilot-curenja anonimizacije (neuobičajen cenovni opseg, neutralisani datumi i volume-stil), i piše snapshote u `data/eval/case_XX/` sa answer key-em fizički **van** tog foldera. Postojeći pilot se refaktoriše da koristi generator umesto sirovog `httpx`-a.

## User Story

As a eval-harness pripremač
I want to da jednom komandom napravim anonimizovan, reproducibilan isečak u oba moda i da izmerim da li vidljiva budućnost menja analizu
So that ne gradim skupu mašineriju za sečenje budućnosti pre nego što dokažem da je potrebna.

## Problem Statement

Pilot (`scripts/eval/pilot_blind_slice.py`) dokazuje mehaniku ali ima tri mane: (1) zaobilazi klijent sirovim `httpx`-om (`fetch_until`, linije 51-71) iako `get_ohlcv` sad ima `end_time`; (2) anonimizacija curi — `PRICE_COEF=7.31` slučajno gura BTC u ~25–55k (BTC-like), `FAKE_START_MS` je `2009-01-01` (Bitcoin genesis era — prepoznatljivo), volume-stil je projektni `make_wyckoff_style` (prepoznatljiv); (3) samo blind mod — ne postoji način da se izmeri da li agent uopšte vara kad vidi budućnost. Bez te provere gradimo blind pipeline na pretpostavci.

## Solution Statement

Novi modul `scripts/eval/snapshot_builder.py` centralizuje: dohvat preko `get_ohlcv(end_time)`, deterministička anonimizacija (cena/volume × koeficijent biran da padne u neuobičajen opseg; bar-relativna x-osa umesto datuma; neutralan eval render-stil), i snapshot layout `data/eval/case_XX/{candles.json, chart.png}` + answer key u **odvojenom** `data/eval/_answers/`. Dual-mode `mode: Literal["blind","future_visible"]`: blind → `end_time=T`; future_visible → `end_time=T+N` + vertikalni „as-of T" marker (nova `vertical_lines` anotacija u rendereru) + tekst-instrukcija. `scripts/eval/lookahead_probe.py` postavlja 2–3 poznata slučaja u oba moda i piše `probe_result` šablon; sama LLM-analiza je dokumentovan runbook korak (Notes). Pilot se refaktoriše da poziva generator.

## Metadata

- **Type:** NEW_CAPABILITY (+ REFACTOR pilota)
- **Complexity:** MEDIUM
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 2 (depends: 1 ✅ merged, parallel: -)
- **Build target:** Opus @ high za probe-dizajn + anonimizacijske odluke (vizuelno-judgment, **ne Codex**); Sonnet @ medium (/ Codex med) za render/I/O plumbing.
- **Affected systems:** eval generator (nov), chart renderer (mala anotacija), pilot (refactor), `.gitignore`.

## UX Design

Operator/pipeline workflow:

```
PRE:  pilot -> sirov httpx(endTime) -> anon (BTC-like opseg, 2009 datumi, wyckoff volume) -> 1 chart (samo blind)

POSLE:
  build_snapshot(case, mode="blind")          -> data/eval/case_01/{candles.json, chart.png}   (do T)
  build_snapshot(case, mode="future_visible") -> data/eval/case_01__fv/{candles.json, chart.png} (do T+N, "as-of T" linija)
  answer key                                  -> data/eval/_answers/case_01.answer.json  (VAN analitičarevog foldera)
  manifest (bez istine)                        -> data/eval/manifest.json
  lookahead_probe -> 2-3 slučaja x 2 moda -> (runbook: slep analitičar) -> data/eval/_answers/probe_result.json
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| eval dohvat | sirov httpx | `get_ohlcv(end_time)` | jedan put, keširan, testabilan |
| anonimizacija | BTC-like/2009/wyckoff | neuobičajen opseg/bar-osa/neutral stil | brani od pretraining-prepoznavanja |
| modovi | samo blind | blind + future_visible | omogućava lookahead probe (gate) |

## Mandatory Reading

- `scripts/mcp/market_data_client.py:138-182` — `get_ohlcv(symbol, timeframe, limit, end_time)`: vraća `list[Candle]` (TypedDict sa `open_time` ms, `open/high/low/close/volume`).
- `scripts/mcp/market_data_client.py:300-329` — `_normalize_end_time` (int ms / ISO str / datetime → ms); future_visible računa `T+N` u ms.
- `scripts/mcp/market_data_client.py:33-42` — `Candle` TypedDict (oblik koji generator anonimizuje).
- `scripts/mcp/chart_renderer.py:189-245` — `render_chart_image(ohlcv_data, title, annotations, output_dir, width, height)` → `RenderedChart` (`path`); prima proizvoljan OHLCV (`open_time/open/high/low/close/volume`).
- `scripts/mcp/chart_renderer.py:163-186` — `make_wyckoff_style` (projektni stil — NE koristiti za eval; napraviti neutralan).
- `scripts/mcp/chart_renderer.py:275-360` — `normalize_annotations` + `_apply_annotations` (`horizontal_lines`, `phase_labels` po candle indeksu) — obrazac za novu `vertical_lines` anotaciju (axvline po indeksu).
- `scripts/eval/pilot_blind_slice.py:38-129` — `fetch_until` (51-71, sirov httpx — ZAMENITI), `anonymize` (74-87, curenja), `main` (90-129, ANSWER_KEY upis) — referenca koja se refaktoriše.
- `.gitignore:175-177` — sekcija „Runtime signal log"; `data/journal/` postoji, `data/eval/` i `scripts/eval/pilot_out/` NE → dodati.

## Patterns to Mirror

- **Dohvat:** `BinanceMarketDataClient().get_ohlcv(sym, tf, limit, end_time=...)` umesto httpx (pilot `fetch_until`).
- **Render:** `render_chart_image(anon_candles, title=..., annotations=..., output_dir=...)` → `result["path"]` (kao pilot `main:95-97`).
- **Anotacije:** nova `vertical_lines` ide 1:1 po obrascu `horizontal_lines` u `normalize_annotations` (294-305) i `_apply_annotations` (336-352), samo `axvline(index)` umesto `axhline(price)`.
- **Determinizam/UTC:** `_datetime_to_epoch_ms` (`market_data_client.py:324-329`) za T i T+N.
- **TypedDict + ValueError validacija:** kao u `market_data_client` (jasne poruke).

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/snapshot_builder.py` | create | dohvat + anonimizacija + dual-mode + snapshot layout + answer key (van foldera) + manifest |
| `scripts/eval/lookahead_probe.py` | create | postavi 2–3 slučaja × 2 moda; piše `probe_result.json` šablon; runbook izvršenje |
| `scripts/mcp/chart_renderer.py` | edit | dodati `vertical_lines` anotaciju (axvline po candle indeksu) |
| `scripts/eval/pilot_blind_slice.py` | edit (refactor) | koristi `snapshot_builder` (bez sirovog httpx); zadržati kao thin primer |
| `.gitignore` | edit | + `data/eval/`, + `scripts/eval/pilot_out/` |
| `tests/test_snapshot_builder.py` | create | anonimizacija/layout/dual-mode/answer-key testovi |
| `tests/test_chart_renderer.py` | edit | + `vertical_lines` anotacija test |

## NOT Building

- Skoring rubriku / izolovanog sudiju — Phase 4. Probe ovde koristi grubu „curi/ne-curi" procenu, ne punu rubriku.
- Ground-truth test set (~10 tačaka) — Phase 3. Ovde samo 2–3 probe-slučaja.
- Automatsko pokretanje LLM-analitičara iz koda — probe execution je runbook korak (orkestrator pušta subagent). Kod samo priprema slučajeve i šablon rezultata.
- Pun snapshot-blinding ako probe pokaže da nije potreban — tada generator ostaje, ali se workflow svodi na živi `end_time` + as-of instrukciju (dokumentovati odluku, ne graditi višak).

## Step-by-Step Tasks

1. **`vertical_lines` anotacija** — `scripts/mcp/chart_renderer.py`
   - Action: u `normalize_annotations` (275-325) dodati granu za `vertical_lines` (lista objekata `{index:int, label:str, color:str}`, default boja npr. `#888`); u `_apply_annotations` (332+) iscrtati `price_axis.axvline(index, ...)` + opcioni tekst, po obrascu `phase_labels` (validacija `0 <= index < len(df)`).
   - Pattern: `horizontal_lines`/`phase_labels` grane.
   - Gotcha: ne menjati postojeće ponašanje kad `vertical_lines` nema (aditivno); `ChartAnnotations`/`VerticalLineAnnotation` tip dodati uz postojeće.
   - Validate: `uv run --extra mcp pytest tests/test_chart_renderer.py -q`

2. **Anonimizator (deterministički, bez curenja)** — `scripts/eval/snapshot_builder.py`
   - Action: `anonymize(candles, *, seed|case_id) -> (anon_candles, coef_meta)`:
     - `price_coef` biran tako da medijana anon-cene padne na FIKSAN neuobičajen target izveden iz `case_id` (npr. iz skupa `{137.0, 1234.5, 88000.0, 0.0042}` rotiranih po case_id) → opseg garantovano van BTC-like ~25–55k; `volume_coef` slično.
     - `open_time` → bar-relativni indeks (0..n-1) ili neutralan ms koji render NE prikazuje kao datum (vidi task 4).
   - Pattern: pilot `anonymize` (74-87), ali target-driven koeficijent.
   - Gotcha: isti `case_id`+ulaz → isti bajtovi (round na fiksan broj decimala, sortiran JSON).
   - Validate: `uv run --extra mcp pytest tests/test_snapshot_builder.py -k anonymize -q`

3. **Neutralan eval render-stil + x-osa** — `scripts/eval/snapshot_builder.py`
   - Action: `render_eval_chart(anon_candles, title, annotations, output_dir)` koje zove `render_chart_image` ali sa generičkim naslovom (`ASSET-X <TF>`) i — pošto `render_chart_image` koristi `datetime_format` na ms indeksu — anon `open_time` postaviti na neutralan monoton niz koji daje bezznačajne x-labele (ne 2009, ne realan kalendar); razmotriti generički naslov bez TF ako TF odaje.
   - Pattern: pilot `main:95` poziv `render_chart_image`.
   - Gotcha: `render_chart_image` deli keš po sadržaju (`_cache_key`) — različiti slučajevi imaju različite candles pa nema kolizije; isti slučaj reproducibilan.
   - Validate: `uv run --extra mcp pytest tests/test_snapshot_builder.py -k render -q`

4. **Dual-mode generator + snapshot layout** — `scripts/eval/snapshot_builder.py`
   - Action: `build_snapshot(symbol, timeframe, cutoff, n_bars, mode, case_id, *, future_bars=20, client=None) -> SnapshotResult`:
     - `blind`: `get_ohlcv(symbol, tf, limit=n_bars, end_time=cutoff)`.
     - `future_visible`: `end_time = cutoff + future_bars*timeframe_ms`; render sa `vertical_lines=[{index: index_of_T, label:"as-of T"}]`; upiše `instruction.txt` („analiziraj kao da je sada T (vertikalna linija); ne koristi sveće desno od linije").
     - Piše `data/eval/<case_dir>/candles.json` + `chart.png`; answer key u `data/eval/_answers/<case_id>.answer.json` (real symbol/cutoff/coef/`ground_truth` šta posle T); update `data/eval/manifest.json` (samo `case_id, mode, n_bars, paths` — BEZ istine).
   - Pattern: pilot `main` (90-129), ali split answer-key VAN case foldera.
   - Gotcha: `_answers/` mora biti van svakog `case_XX/`; analitičar dobija samo putanju do `case_XX/`.
   - Validate: `uv run --extra mcp pytest tests/test_snapshot_builder.py -k "snapshot or answer_key or manifest" -q`

5. **Lookahead probe scaffold** — `scripts/eval/lookahead_probe.py`
   - Action: definiše 2–3 poznata slučaja (npr. pilot BTC 2019-04-01 + 1–2 druga); za svaki generiše blind I future_visible preko `build_snapshot`; piše `data/eval/_answers/probe_result.json` šablon sa poljима `{case_id, blind_score:null, fv_score:null, fv_leaked:null, delta:null, decision:null}`; štampa runbook uputstvo.
   - Gotcha: kod NE poziva LLM — samo priprema; izvršenje analitičara je runbook korak (Notes).
   - Validate: `uv run --extra mcp python -m scripts.eval.lookahead_probe --dry-run` (generiše bez mreže ako je `client` stub) ili dokumentovan ručni run.

6. **Refactor pilota** — `scripts/eval/pilot_blind_slice.py`
   - Action: zameniti `fetch_until` (sirov httpx) pozivom `build_snapshot(..., mode="blind")`; ukloniti hardkodovane curljive konstante (`PRICE_COEF=7.31`, `FAKE_START_MS=2009`); zadržati fajl kao tanak primer koji delegira na `snapshot_builder`.
   - Gotcha: ne menjati javni „run" ugovor više nego što treba; ostaje izvršiv `python -m scripts.eval.pilot_blind_slice`.
   - Validate: `uv run --extra mcp python -m scripts.eval.pilot_blind_slice` (lokalno, sa mrežom) ili test sa stub klijentom.

7. **gitignore** — `.gitignore`
   - Action: u sekciju eval/journal dodati `data/eval/` i `scripts/eval/pilot_out/` (proveriti da `data/journal/` već postoji — da).
   - Validate: `git check-ignore data/eval/x scripts/eval/pilot_out/x`

8. **Testovi** — `tests/test_snapshot_builder.py` (+ `tests/test_chart_renderer.py`) — vidi Testing Strategy.
   - Validate: `uv run --extra mcp pytest tests/test_snapshot_builder.py tests/test_chart_renderer.py -q`

## Testing Strategy

`tests/test_snapshot_builder.py` (stub/`FakeClient` koji vraća fiksne `Candle`-ove, bez mreže; `tmp_path` za `data/eval`):
1. `test_anonymize_pushes_to_unusual_range` — anon medijana cene pada na očekivani neuobičajen target; NIJE u ~25–55k.
2. `test_anonymize_deterministic` — isti `case_id`+ulaz → isti bajtovi (dvostruki poziv identičan).
3. `test_blind_mode_excludes_future` — `build_snapshot(mode="blind")` prosleđuje `end_time=cutoff` klijentu (stub beleži kwarg); n sveća == n_bars.
4. `test_future_visible_extends_and_marks` — `mode="future_visible"` prosleđuje `end_time=cutoff+future_bars*tf_ms`; snapshot ima `vertical_lines` marker na indeksu T; postoji `instruction.txt`.
5. `test_answer_key_outside_case_dir` — `_answers/<case_id>.answer.json` postoji i NIJE unutar `case_XX/`; `case_XX/` ne sadrži real symbol/cutoff/ground_truth.
6. `test_manifest_has_no_truth` — `manifest.json` nema `symbol`/`cutoff`/`ground_truth`.
7. `test_x_axis_not_real_calendar` — anon `open_time` ne mapira na prepoznatljiv datum (npr. nije 2009 era).

`tests/test_chart_renderer.py`:
8. `test_vertical_lines_annotation` — `render_chart_image(..., annotations={"vertical_lines":[{"index":k,"label":"as-of T"}]})` ne baca i vraća validan `path`; index van opsega → `ValueError`.

## Validation Commands

```bash
# CLAUDE.md: koristiti uv, ne pip
uv run --extra mcp pytest tests/test_snapshot_builder.py tests/test_chart_renderer.py -q   # ciljani
uv run --extra mcp pytest -q                                                                # pun set — postojeći zeleni
git check-ignore data/eval/x scripts/eval/pilot_out/x                                       # gitignore radi
uv run --extra mcp python -m scripts.eval.lookahead_probe --dry-run                         # probe scaffold (stub klijent)
```

## Acceptance Criteria

- `build_snapshot` radi u oba moda preko `get_ohlcv(end_time)` (bez sirovog httpx-a); blind nema sveće > T, future_visible ima do T+N sa „as-of T" markerom + instrukcijom.
- Anonimizacija: cenovni opseg neuobičajen (ne BTC-like), x-osa neprepoznatljiva, neutralan volume-stil; isti parametri → isti bajtovi.
- Answer key i probe istina fizički u `data/eval/_answers/` (van case foldera); manifest bez istine.
- `lookahead_probe` generiše 2–3 slučaja × 2 moda i piše `probe_result.json` šablon; runbook za izvršenje dokumentovan.
- Pilot refaktorisan na `snapshot_builder`; `data/eval/` i `scripts/eval/pilot_out/` u `.gitignore`.
- Svi postojeći testovi zeleni; novi prolaze.

## Completion Checklist

- [ ] `vertical_lines` anotacija u rendereru (+ test).
- [ ] `snapshot_builder.py`: anonimizacija (neuobičajen opseg, bar-osa, neutral stil), dual-mode, layout, answer-key van foldera, manifest.
- [ ] `lookahead_probe.py`: 2–3 slučaja × 2 moda + `probe_result.json` šablon.
- [ ] Pilot refaktorisan (bez sirovog httpx / curljivih konstanti).
- [ ] `.gitignore` + `data/eval/`, `scripts/eval/pilot_out/`.
- [ ] `uv run --extra mcp pytest -q` ceo zelen.
- [ ] Gate odluka (blind treba/ne-treba) upisana u `probe_result.json` posle runbook izvršenja.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Koeficijent slučajno padne u poznat opseg (pilot greška) | target-driven koeficijent iz fiksnog neuobičajenog skupa po `case_id`; test `test_anonymize_pushes_to_unusual_range` |
| `render_chart_image` `datetime_format` oda eru kroz x-osu | neutralan monoton `open_time` koji daje bezznačajne labele; test `test_x_axis_not_real_calendar` |
| Answer key procuri u case folder | fizički odvojen `_answers/`; test `test_answer_key_outside_case_dir` |
| Menjanje deljenog renderera lomi postojeće | `vertical_lines` strogo aditivno; pun suite + namenski test |
| future_visible „as-of" dvosmislen → nepošteno poređenje | eksplicitna vertikalna linija + `instruction.txt`; dokumentovano u probe runbook-u |

## Notes

**Probe runbook (gate — izvršava orkestrator, ne kod):** za svaki probe slučaj: (a) pusti slep subagent (bez konteksta, bez pristupa `_answers/`) na `blind` snapshot → zabeleži analizu; (b) isti na `future_visible` snapshot uz „as-of T" instrukciju; (c) uporedi: da li FV analiza referencira događaje posle T (leak) i da li skor skače; (d) upiši `blind_score/fv_score/fv_leaked/delta/decision` u `data/eval/_answers/probe_result.json`. **Gate:** `delta ≈ 0 & !leaked` → blind sečenje suvišno, workflow se svodi na živi `end_time` + as-of instrukciju (zabeleži, ne gradi višak snapshot mašinerije za Phase 3); inače → pun snapshot blinding kako planiran. `future_bars` default 20; `case_id` rotira anon target da spreči slučajan poznat opseg. `_normalize_end_time` već prima ISO/ms/datetime, pa `cutoff` može ostati ISO string.
