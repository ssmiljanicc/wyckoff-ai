# Feature: Phase 6 — Benchmark batch + report (model × effort, dva kontrolna Δskor-a)

## Summary

Integracioni vrh Faze 4: jedan **benchmark runner** koji nad **identičnim** zamrznutim snapshotima pušta matricu **model × effort** (analitičar = `wyckoff-trader-skill`), beleži **token-cost** uz skor (ROI = skor/$), i izračunava **obe kontrole** kao Δskor: (a) **anon→revealed** (pretraining-leakage) i (b) **slep→vidljiva-budućnost** (lookahead-honesty). Rezultat je jedan **report** (tabela `model × effort × skor × token-cost` po dimenziji i event-tipu, rangiranje po skoru i po ROI, oba Δskor-a). Po ustaljenom obrascu Faze 2/4 — **kod priprema run-matricu + skoruje + agregira; samo *pozivanje* analitičara i sudije je runbook korak** (orkestrator pušta izolovane subagent-e po (model, effort)). Reuse Phase 4 skoringa (`scripts/eval/scoring.py`) i Phase 2/3 snapshot-builder-a (`scripts/eval/snapshot_builder.py`), uz jednu kontroliranu dopunu: **`reveal` mod** snapshot-a (neanonimizovan grafik) koji omogućava anon-vs-revealed A/B.

## User Story

As a eval-harness evaluator (Stefan, graditelj sistema)
I want to da nad istim slepim ulazom uporedim model × effort po skoru i token-cost-u, i da kvantifikujem oba curenja (pretraining + lookahead)
So that empirijski biram koji model/effort vredi za koji tip zadatka i znam treba li uopšte puni blinding — izlaz hrani `model:*` labele na budućim issue-ima.

## Problem Statement

Phase 2–5 daju kompletan **jedno-prolazni** eval: snapshot (`data/eval/case_XX/`) + answer key (`_answers/<case>.answer.json` sa `event_type/realized_direction/decisive/post_t_candles`) → slep analitičar → deterministički + izolovani sudija skor (`scripts/eval/scoring.py`) → `_scores/<case>.score.json`. Ali ne postoji: (1) **matrica** koja parametrizuje (model, effort) nad istim ulazom; (2) **token-cost/ROI** uz skor; (3) **agregacija** po dimenziji/event-tipu/modelu; (4) **kontrole** — `snapshot_builder.build_snapshot` **uvek anonimizuje** (`snapshot_builder.py:237`), pa nema „revealed" prolaza za merenje pretraining-leakage-a; lookahead-honesty Δ se može meriti jer `future_visible` mod postoji, ali nije ugrađen u jedinstven report. Bez ovoga „koji model/effort" i „koliko curi" ostaju subjektivni.

## Solution Statement

Nov modul `scripts/eval/benchmark.py`:

1. **Matrica + run-manifest** (`build_run_matrix`): enumeriše `RunSpec`-ove po osama `case × (time_mode ∈ {blind, future_visible}) × (anon_mode ∈ {anon, revealed}) × model × effort`. Baseline = `(blind, anon)`. Kontrole dodaju samo dva ugla: `(blind, revealed)` i `(future_visible, anon)`. Piše `data/eval/_benchmark/benchmark_runs.json` (šablon koji orkestrator popunjava — preslikan obrazac `lookahead_probe.probe_result.json`). Kod **ne zove** analitičara.
2. **Skor po prolazu** (`score_run`): uzima popunjen analitičarev output + `usage{input_tokens, output_tokens}` + sudijin verdikt, zove `scoring.score_deterministic` + `scoring.combine_scores`, računa `cost_usd` (`MODEL_PRICING`) i `roi = aggregate / cost_usd` → `BenchmarkRow`.
3. **Agregacija + Δ** (`aggregate_report`): grupisanje po `(model, effort)`; srednji agregat + po-dimenziji + po-event-tipu; **Δleakage** = mean(revealed) − mean(anon) nad zajedničkim slučajevima; **Δlookahead** = mean(future_visible) − mean(blind); rangiranje po skoru i po ROI.
4. **Report** (`render_report_markdown`): jedna markdown tabela + oba Δskor-a → `data/eval/_benchmark/report.md` (+ `report.json`).

Dopuna `scripts/eval/snapshot_builder.py`: **`reveal: bool = False`** na `build_snapshot`. Kada `True`: koeficijent identitet (`price_coef=1.0, volume_coef=1.0`), **stvarni** `open_time` i cene/volume (passthrough, ne neutralni epoch), title `f"{symbol} {TF}"`, default chart-stil (prepoznatljiv), `case_dir = <case_id>__revealed`, answer key `_answers/<case_id>__revealed.answer.json` (da **ne pregazi** anon answer key; `post_t_candles` u realnom prostoru za deterministički replay revealed-trigera). Default `False` čuva celokupno postojeće ponašanje.

## Metadata

- **Type:** NEW_CAPABILITY
- **Complexity:** MEDIUM–HIGH (agregacija + dva Δ + reveal kontrola; sama mašinerija je plumbing, vrednost je u tačnoj agregaciji/izveštaju)
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 6 (depends: 3 ✅, 4 ✅; integracioni vrh)
- **Build target:** Opus @ high→xhigh za sintezu/agregaciju/report (judgment) ; **Codex med–high** za batch-runner/cost plumbing (čista logika).
- **Affected systems:** nov eval benchmark modul + dopuna snapshot-builder-a + testovi (ne dira servere; reuse `scoring`).

## Effort-tier rezolucija (zatvara PRD Open Question)

Claude Code `/effort` nivoi su **`low` · `medium` · `high` · `xhigh` · `max`** (potvrđeno preko `claude-api` reference). PRD-ovo „extra-high" = **`xhigh`** (između `high` i `max`); gornji tier = **`max`**.
- `xhigh`: Fable 5, Opus 4.5+, Sonnet 4.6. `max`: Fable 5, Opus 4.6+, Sonnet 4.6.
- **Haiku 4.5 ne podržava `effort` param** → nije u sweep-u (PRD matrica ga ionako ne navodi); ako se ikad meri, samo na default effort-u.

## Model IDs + pricing (za `MODEL_PRICING`, izvor: `claude-api` reference, keširano 2026-06-04)

| Model | ID | Input $/1M | Output $/1M | Effort sweep |
|---|---|---|---|---|
| Claude Sonnet 4.x | `claude-sonnet-4-6` | 3.00 | 15.00 | medium, high, xhigh, max |
| Claude Opus 4.x | `claude-opus-4-8` | 5.00 | 25.00 | medium, high, xhigh, max |
| Claude Fable 5 | `claude-fable-5` | 10.00 | 50.00 | medium, high, xhigh, max (čim bude dostupan u harness-u) |
| Codex (GPT-5.x-codex) | `codex` (placeholder) | **TBD** | **TBD** | low, medium, high, xhigh |

> **Gotcha:** pricing se menja — `MODEL_PRICING` je jedna konstanta sa komentarom o datumu izvora; **ne hardkodovati po fajlovima**. Codex pricing nije iz `claude-api` reference: u v1 ostaje `None` → za Codex se izveštava **tokens-only ROI** (skor/1k tok) uz jasnu oznaku „cost N/A". Fable 5 redovi se popunjavaju „čim bude dostupan" (PRD).

## UX Design (operator workflow, ne ekran)

```
benchmark_runs.json (šablon: case × time_mode × anon_mode × model × effort, prazni result slotovi)
        │  [runbook] za svaki RunSpec: orkestrator pušta IZOLOVAN blind-analitičar subagent
        │            (model override + effort), čita SAMO snapshot dir → vraća eval-output + usage
        │            (revealed prolaz = NOVI subagent bez konteksta anon prolaza — anti-contamination)
        ▼
results/<run_id>.json  ({analysis_output, usage{input_tokens,output_tokens}, judge_verdict})
        │  [runbook] sudija = izolovan Opus subagent po scoring.prepare_judge_input (BEZ grafika)
        ▼
score_run(run_spec, output, usage, judge_verdict, answer_key)  → BenchmarkRow (aggregate, dims, cost_usd, roi)
        ▼
aggregate_report(rows)  → grupisano po (model,effort) + po event-tipu + Δleakage + Δlookahead + rang
        ▼
render_report_markdown → data/eval/_benchmark/report.md (+ report.json)
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| izbor model/effort | subjektivan | tabela skor × token-cost × ROI po dimenziji | empirijski izbor `model:*` |
| pretraining-leakage | nemerljiv | Δleakage = mean(revealed) − mean(anon) | kvantifikovan |
| lookahead-honesty | probe ad-hoc (Phase 2) | Δlookahead = mean(fv) − mean(blind), u istom report-u | odluka o blinding-u |
| revealed grafik | ne postoji (uvek anon) | `build_snapshot(reveal=True)` | A/B kontrola moguća |

## Mandatory Reading

- `scripts/eval/scoring.py` — `score_deterministic(*, direction, trigger_level, invalidation_level, answer_key, confidence)` (:255), `combine_scores(deterministic, judge_verdict, *, wait_case=None, analysis_id=None)` (:409), `prepare_judge_input` (:362), `write_score` (:444), `DIMENSION_WEIGHTS`/`DIMENSIONS` (:53,:20), `ScoreRecord`/`DimensionScore` TypedDicts. Benchmark **reuse-uje** ovo — ne reimplementira skoring.
- `scripts/eval/snapshot_builder.py` — `build_snapshot(... mode, case_id, *, future_bars, ground_truth, answer_extra, include_post_t_candles, base_dir)` (:152), `anonymize`/`anonymize_with_meta` (:57,:90) i answer-key blok (:276-291) sa `case_id__fv` suffiksom (:224). Dopuna `reveal` ide ovde.
- `scripts/eval/lookahead_probe.py` — obrazac „kod priprema cases + piše JSON šablon; runbook pušta LLM i popunjava" (`PROBE_CASES`, `run_probe`, `probe_result.json`). **Preslikati** za `benchmark_runs.json`.
- `scripts/eval/ground_truth_cases.py` — `GROUND_TRUTH_CASES` (10 slučajeva, :47), `load_answer_key` (:157), `EVENT_QUOTA` (:17). Benchmark čita case_ids odavde; event-tip dolazi iz answer key-a.
- `scripts/eval/build_eval_set.py` — `run(...)` obrazac za regeneraciju snapshota (`build_snapshot` u petlji, dry-run preko `_DryRunClient`). Mirror za „ensure revealed snapshots".
- `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` — Phase 6 scope (:188-192), „Model × Effort B" matrica (:217-224), Decisions Log: anon-vs-revealed = double-run **različit agent po prolazu** (:238).

## Patterns to Mirror

- **Kod-priprema vs runtime-LLM:** `lookahead_probe.run_probe` + `probe_result.json` šablon → `build_run_matrix` + `benchmark_runs.json`. Kod NE poziva model.
- **Reuse skoringa:** zvati `scoring.score_deterministic`/`combine_scores`, ne kopirati replay logiku.
- **Out-of-folder izolacija:** `_benchmark/` pored `_answers/`/`_scores/` (svi van `case_XX/`); sudija nikad ne dobija grafik (već garantovano u `prepare_judge_input`).
- **Suffiks po modu:** `case_id__fv` (postoji) → `case_id__revealed` (novo), istom logikom u `build_snapshot`.
- **Dry-run stub:** `_DryRunClient` (iz `lookahead_probe`) za testove/dry-run bez mreže.
- **TypedDict + validacija:** stil iz `scoring.py`/`analysis_journal_server.py` (`_number`, `ValueError` sa jasnom porukom).

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/snapshot_builder.py` | edit | +`reveal` param na `build_snapshot`; +`passthrough_candles` helper (realni open_time + identitet koef); `case_id__revealed` dir + answer fajl |
| `scripts/eval/benchmark.py` | create | `MODEL_PRICING`, `BENCHMARK_MATRIX`, `RunSpec`/`RunResult`/`BenchmarkRow`/`BenchmarkReport` TypedDicts, `build_run_matrix` (+`benchmark_runs.json`), `compute_cost`, `score_run`, `aggregate_report` (Δleakage/Δlookahead/ROI), `render_report_markdown`, CLI (`--dry-run`, `--ensure-snapshots`, `--ingest <dir>`) |
| `tests/test_benchmark.py` | create | matrica, cost, score_run, agregacija + oba Δ, ROI, event-tip breakdown, dry-run |
| `tests/test_snapshot_builder.py` | edit | +`reveal` testovi (realne cene/datumi, identitet koef, `__revealed` dir/answer, real post_t_candles) |
| `.gitignore` | check | `data/eval/` već pokriva `_benchmark/` (Phase 2, :180) — samo proveriti |

## NOT Building

- Automatsko pozivanje analitičara/sudije iz koda — runbook korak (orkestrator pušta izolovane subagent-e po model×effort).
- Promenu `scoring.py` skoring logike — samo se reuse-uje.
- Real-money izvršenje, ML trening, tick-level (trajni non-goals).
- Codex pricing brojeve — `None` u v1 (tokens-only ROI za Codex), upisati kad bude poznato.
- `(future_visible, revealed)` četvrti ugao — nepotreban za dva Δ (tri ugla dovoljna); dokumentovati kao moguće proširenje.
- Aktivaciju u `.mcp.json` — benchmark je CLI/skripta, ne MCP server.

## Step-by-Step Tasks

1. **`reveal` mod u snapshot-builder-u** — `scripts/eval/snapshot_builder.py`
   - Action: dodati `passthrough_candles(candles) -> list[dict]` (zadržava realni `open_time`, `open/high/low/close/volume` zaokruženo na 4, BEZ neutral-epoch remapinga). U `build_snapshot` dodati `reveal: bool = False`. Kada `reveal=True`: `anon_candles = passthrough_candles(candles)`, `coef_meta = {"price_coef":1.0,"volume_coef":1.0,"price_target":None}`; render preko `render_chart_image` sa **default** stilom (ne `make_eval_style`) i title `f"{symbol} {timeframe.upper()}"`; `case_dir_name = f"{case_id}__revealed"`; answer key path `_answers/{case_id}__revealed.answer.json`; `post_t_candles` (kad `include_post_t_candles`) preko `passthrough_candles` (realni prostor). Kada `reveal=False`: nepromenjeno.
   - Pattern: postojeći `__fv` suffiks + answer-key blok (`snapshot_builder.py:224,276-291`).
   - Gotcha: revealed answer key **ne sme** da pregazi anon (`{case_id}.answer.json`) — otud `__revealed` suffiks; `event_type/realized_direction/decisive` ostaju identični (iz `answer_extra`), samo `post_t_candles` su u realnom prostoru.
   - Validate: `uv run --extra mcp pytest tests/test_snapshot_builder.py -k reveal -q`

2. **Konstante: pricing + matrica** — `scripts/eval/benchmark.py`
   - Action: `MODEL_PRICING: dict[str, dict[str, float]]` (po-1M input/output, vrednosti iz tabele gore; Codex `None`), `BENCHMARK_MATRIX: dict[str, list[str]]` (model_id → effort nivoi), `EFFORT_LEVELS`, `CONTROLS` (`baseline=(blind,anon)`, `leakage=(blind,revealed)`, `lookahead=(future_visible,anon)`). Komentar sa datumom izvora pricing-a.
   - Gotcha: Haiku NIJE u matrici (nema effort param); Fable 5 prisutan ali označen „pending availability".
   - Validate: `uv run --extra mcp python -c "import scripts.eval.benchmark as b; assert b.MODEL_PRICING['claude-opus-4-8']['input']==5.0 and b.BENCHMARK_MATRIX"`

3. **Run-matrica + manifest** — `scripts/eval/benchmark.py`
   - Action: `RunSpec` TypedDict (`run_id`, `case_id`, `time_mode`, `anon_mode`, `model`, `effort`, `snapshot_dir`, `answer_key_path`, `instruction|None`). `build_run_matrix(case_ids, *, matrix=BENCHMARK_MATRIX, controls=CONTROLS, base_dir=DEFAULT_BASE_DIR) -> list[RunSpec]`: za svaki (case, control-ugao, model, effort) → stabilan `run_id = f"{case_id}__{time_mode}__{anon_mode}__{model}__{effort}"`, mapira na snapshot dir (`case_id` / `case_id__fv` / `case_id__revealed`) i odgovarajući answer key; `instruction` čita iz `case_dir/instruction.txt` za `future_visible`. Pisati `_benchmark/benchmark_runs.json` (lista run-ova sa praznim result slotovima + `_instructions`).
   - Pattern: `lookahead_probe.run_probe` + `probe_result.json`.
   - Gotcha: leakage-ugao zahteva `case_id__revealed` snapshot — ako ne postoji, `build_run_matrix` ga **ne pravi** (to radi `--ensure-snapshots`), nego beleži `missing_snapshot: true` na RunSpec-u da orkestrator zna da prvo regeneriše.
   - Validate: `uv run --extra mcp pytest tests/test_benchmark.py -k matrix -q`

4. **Cost + skor po prolazu** — `scripts/eval/benchmark.py`
   - Action: `compute_cost(usage, model) -> float|None` = `(in*price_in + out*price_out)/1e6` (None ako pricing None). `RunResult` TypedDict (`analysis_output: dict`, `usage: dict`, `judge_verdict: dict`). `score_run(run_spec, result, answer_key) -> BenchmarkRow`: izvuče `direction/trigger/invalidation/confidence` iz `analysis_output`, zove `scoring.score_deterministic` + `scoring.combine_scores`; `BenchmarkRow` = `{run_id, case_id, model, effort, time_mode, anon_mode, event_type, aggregate, dimensions, total_tokens, cost_usd, roi}` (`roi = aggregate/cost_usd` ili `aggregate/(total_tokens/1000)` kad cost None, sa flagom `roi_basis`).
   - Pattern: `scoring.combine_scores` potpis i `ScoreRecord` oblik.
   - Gotcha: trigger/invalidation u ANON prostoru za anon prolaze, REAL za revealed — answer key (anon vs `__revealed`) već nosi odgovarajuće `post_t_candles`; `score_run` bira answer key preko `run_spec.answer_key_path`.
   - Validate: `uv run --extra mcp pytest tests/test_benchmark.py -k "cost or score_run" -q`

5. **Agregacija + Δskor + ROI rang** — `scripts/eval/benchmark.py`
   - Action: `aggregate_report(rows) -> BenchmarkReport`: po `(model, effort)` srednji `aggregate`, srednji po-dimenziji (`DIMENSIONS`), srednji po `event_type`, mean tokens/cost/roi; **Δleakage** po (model,effort) = mean(aggregate | anon_mode=revealed) − mean(... anon) nad zajedničkim `case_id`-evima; **Δlookahead** = mean(... time_mode=future_visible) − mean(... blind); rang liste po `aggregate` i po `roi`. `n` (broj slučajeva) eksplicitno u svakom redu.
   - Gotcha: Δ se računa SAMO nad zajedničkim case-ovima oba ugla (ako revealed nedostaje za neki case → izostavi iz Δ, ne tretiraj kao 0); wait-case redovi (`aggregate` preskače NA dimenzije, već u `combine_scores`) — ne dupliraj logiku.
   - Validate: `uv run --extra mcp pytest tests/test_benchmark.py -k "aggregate or delta or roi" -q`

6. **Report render + CLI** — `scripts/eval/benchmark.py`
   - Action: `render_report_markdown(report) -> str` (markdown: glavna tabela `model × effort × skor × tokens × cost × ROI`, po-dimenziji i po-event-tip podtabele, dve Δ tabele, rang). CLI: `--dry-run` (build matrice nad placeholder answers preko `_DryRunClient`), `--ensure-snapshots` (regeneriše nedostajuće `__revealed` snapshote preko `build_snapshot(reveal=True, include_post_t_candles=True)`), `--ingest <results_dir>` (učita `results/<run_id>.json`, skoruje, agregira, piše `_benchmark/report.{md,json}`). Pisati i `report.json`.
   - Pattern: `build_eval_set.main` argparse + `lookahead_probe.main`.
   - Validate: `uv run --extra mcp pytest tests/test_benchmark.py -k report -q` ; `uv run --extra mcp python -m scripts.eval.benchmark --dry-run`

7. **Testovi** — `tests/test_benchmark.py` + dopuna `tests/test_snapshot_builder.py` (vidi Testing Strategy).
   - Validate: `uv run --extra mcp pytest tests/test_benchmark.py tests/test_snapshot_builder.py -q`

8. **gitignore provera + pun set** — `.gitignore` (samo `git check-ignore`), pa pun pytest.
   - Validate: `git check-ignore data/eval/_benchmark/report.md` ; `uv run --extra mcp pytest -q`

## Testing Strategy

`tests/test_benchmark.py` (sintetički `RunResult`/answer key sa punom šemom; `tmp_path` za `_benchmark`):
1. `test_build_run_matrix_shape` — matrica ima baseline+2 kontrole × model × effort; stabilni `run_id`; FV ima `instruction`.
2. `test_compute_cost` — opus 1000in/2000out = `(1000*5 + 2000*25)/1e6`; Codex (None pricing) → `cost_usd=None`.
3. `test_score_run_uses_scoring` — `score_run` reprodukuje `combine_scores` agregat na poznatom slučaju; `roi` ispravan.
4. `test_aggregate_delta_leakage` — revealed agregat > anon nad zajedničkim case-ovima → `Δleakage > 0`.
5. `test_aggregate_delta_lookahead` — fv agregat ~ blind → `Δlookahead ≈ 0`; Δ samo nad zajedničkim case-ovima.
6. `test_roi_tokens_basis_when_cost_none` — Codex red: `roi_basis == "tokens"`.
7. `test_event_type_breakdown` — agregat po event-tipu prisutan.
8. `test_render_report_has_both_deltas` — markdown sadrži „Δleakage" i „Δlookahead" + rang po ROI; `n` po redu.
9. `test_dry_run_builds_manifest` — `--dry-run` (stub) piše `benchmark_runs.json` bez mreže.

`tests/test_snapshot_builder.py` (dopuna):
10. `test_reveal_preserves_real_prices_and_dates` — revealed candles == realne cene (coef 1.0), realni `open_time` (ne 1970 epoch).
11. `test_reveal_writes_separate_answer_key` — `_answers/<case>__revealed.answer.json` postoji i NE gazi `<case>.answer.json`; `post_t_candles` u realnom prostoru.
12. `test_reveal_case_dir_suffix` — `case_dir` završava `__revealed`.

## Validation Commands

```bash
# CLAUDE.md: uv, ne pip
uv run --extra mcp pytest tests/test_benchmark.py tests/test_snapshot_builder.py -q   # ciljano
uv run --extra mcp python -m scripts.eval.benchmark --dry-run                          # matrica bez mreže
uv run --extra mcp python -c "import scripts.eval.benchmark as b; assert b.build_run_matrix and b.aggregate_report and b.render_report_markdown"
uv run --extra mcp pytest -q                                                           # pun set zelen
git check-ignore data/eval/_benchmark/report.md                                        # artefakti ignorisani
```

## Acceptance Criteria

- `build_run_matrix` daje baseline `(blind,anon)` + dve kontrole `(blind,revealed)`/`(future_visible,anon)` × matrica model×effort; stabilni `run_id`; `benchmark_runs.json` ima prazne result slotove (kod ne zove model).
- `build_snapshot(reveal=True)` piše `case_XX__revealed/` sa realnim cenama/datumima i ODVOJEN `__revealed` answer key (ne gazi anon); `post_t_candles` u realnom prostoru.
- `score_run` reuse-uje `scoring.score_deterministic`/`combine_scores` (ne reimplementira); `cost_usd` iz `MODEL_PRICING`; `roi` (skor/$ ili skor/1k tok kad cost None).
- `aggregate_report` daje **oba** Δskor-a (anon→revealed, slep→vidljiva budućnost) nad **zajedničkim** case-ovima, po-dimenziji i po-event-tipu, rang po skoru i po ROI, sa eksplicitnim `n`.
- `report.md` + `report.json` zapisani u `_benchmark/`; markdown čitljiv, prikazuje obe kontrole.
- Effort tier rezolucija dokumentovana (`low/medium/high/xhigh/max`, „extra-high"=`xhigh`).
- Svi postojeći testovi zeleni.

## Completion Checklist

- [ ] `reveal` mod (`passthrough_candles`, `__revealed` dir/answer, realni prostor) + 3 testa.
- [ ] `MODEL_PRICING` + `BENCHMARK_MATRIX` + `CONTROLS` (Haiku van; Codex None; Fable pending).
- [ ] `build_run_matrix` + `benchmark_runs.json` šablon (kod ne zove model).
- [ ] `compute_cost` + `score_run` (reuse `scoring`).
- [ ] `aggregate_report` (Δleakage + Δlookahead + ROI rang + event-tip).
- [ ] `render_report_markdown` + CLI (`--dry-run`/`--ensure-snapshots`/`--ingest`) → `report.{md,json}`.
- [ ] 9 benchmark testova + 3 reveal testa prolaze; `uv run --extra mcp pytest -q` ceo zelen.
- [ ] Benchmark runbook dokumentovan u Notes (analitičar + sudija koraci, anti-contamination).

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Revealed answer key gazi anon (isti case_id) | `__revealed` suffiks na dir-u i answer fajlu; test 11 dokazuje koegzistenciju |
| Δ računat nad različitim skupom case-ova → lažan signal | Δ samo nad zajedničkim `case_id`-evima oba ugla; nedostajući revealed se izostavlja, ne nula (test 4/5) |
| Revealed prolaz kontaminira anon prolaz istog modela | Runbook: NOVI izolovan subagent po prolazu (PRD Decisions Log :238); odvojeni `run_id`/spawn-ovi |
| Pricing zastareva / Codex nepoznat | Jedna `MODEL_PRICING` konstanta sa datumom; Codex `None` → tokens-only ROI; Fable označen „pending" |
| Trigger/invalidation u pogrešnom prostoru (anon vs real) za revealed | `score_run` bira answer key po `run_spec.answer_key_path`; revealed answer ima real `post_t_candles` |
| Token-usage nepouzdan po subagent-u | `usage` se beleži u `results/<run_id>.json` od orkestratora; `score_run` validira prisustvo; cost None ako fali |
| Mali n → skor statistički nestabilan | Report štampa `n` po redu; PRD jasno: v1 ~10 = signal, ne dokaz |

## Notes

**Benchmark runbook (gate — izvršava orkestrator/LLM, ne kod):**
1. `python -m scripts.eval.benchmark --ensure-snapshots` → regeneriše `__revealed` snapshote (blind/fv već postoje iz Phase 3).
2. `python -m scripts.eval.benchmark` (build matrice) → `benchmark_runs.json`.
3. Za svaki `RunSpec`: orkestrator pušta **izolovan blind-analitičar subagent** (`wyckoff-trader-skill`, model override = `model`, traženi `effort`) koji čita **samo** `snapshot_dir` (+ `instruction.txt` za FV) i vraća **eval-output schema** (`direction`, NUMERIČKI anon/real `trigger`, NUMERIČKI `invalidation`, `confidence`, `structure`, `phase`, `event`). **Revealed prolaz = potpuno nov subagent** (bez konteksta anon prolaza). Zabeleži `usage{input_tokens, output_tokens}` → `results/<run_id>.json`.
4. Za svaki output: sudija = **izolovan Opus subagent** preko `scoring.prepare_judge_input(output, answer_key)` (grafik fizički nije u promptu) → verdikt u `results/<run_id>.json`.
5. `python -m scripts.eval.benchmark --ingest results/` → `score_run` + `aggregate_report` + `render_report_markdown` → `data/eval/_benchmark/report.{md,json}`.

**Assumption (zabeleži):** eval-output analitičara nosi NUMERIČKI `trigger`/`invalidation` (anon za anon prolaz, real za revealed) — isto kao Phase 4. Token-cost dolazi iz harness-a (usage po subagent-u); kod ga ne meri sam. **Gate odluka (PRD hipoteza e):** ako `Δlookahead ≈ 0` na ≥5 slučajeva → blinding (fizičko sečenje) je suvišan, dovoljan živi `end_time` + as-of instrukcija; ako velik → puni snapshot blinding opravdan. Report eksplicitno prikazuje oba Δ da hrani ovu odluku i `model:*` preporuke.
