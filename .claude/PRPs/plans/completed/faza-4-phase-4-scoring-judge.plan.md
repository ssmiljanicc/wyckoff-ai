# Feature: Phase 4 — Scoring rubric + isolated judge

## Summary

Skoring sloj za *verovatnosni* output slepe Wyckoff analize. Dva odvojena kanala: (1) **deterministički** (kod, bez LLM) — ispravnost vodećeg smera + razumnost trigger/invalidacije, dobijeni čitanjem `realized_direction/decisive/post_t_candles` iz answer key-a i „replay"-om analitičarevog forecast-a protiv tih post-T anon sveća, naslonjeno na `signal_logger.replay_signal`; (2) **izolovani LLM-sudija** (Opus) — semantička tačnost strukture/faze/eventa, kvalitet narativa, i **kalibracija confidence-a**, uz **wait-pravilo**. Sudija vidi **samo agentov output + answer key, NIKAD grafik/anon candles**. Kod priprema ulaz za sudiju i deterministički deo; samo *pozivanje* sudije je runbook korak (kao Phase 2 probe). Rezultat: `ScoreRecord` po dimenziji + agregat, upisan van analitičarevog foldera.

## User Story

As a eval-harness evaluator
I want to da objektivno skorujem slepu analizu po Wyckoff dimenzijama bez da sudija vidi grafik
So that dobijem merljivu pouzdanost (po dimenziji, po modelu/effortu) otpornu na sudija-leakage.

## Problem Statement

Phase 2 generiše slepe snapshote i answer key (`data/eval/_answers/<case>.answer.json` sa `ground_truth`/`coef_meta`), Phase 3 proširuje answer key poljima `event_type/realized_direction/decisive/post_t_candles`, a Phase 5 beleži strukturisan `forecast{direction,trigger,invalidation,confidence}` (`analysis_journal_server.py:19-46`). Ali ne postoji način da se output OCENI: nema rubrike, nema determinističke provere smera/trigera, niti izolovanog sudije. Bez toga „kvalitet analize" ostaje subjektivan, a ako sudija vidi grafik može sam da „prepozna" setup (leakage).

## Solution Statement

Nov modul `scripts/eval/scoring.py`: (a) DETERMINISTIČKI skorer koji uzima analitičarev forecast (smer + numerički anon trigger + numerički anon invalidation), čita `realized_direction/decisive/post_t_candles` iz `answer_key`-a i „replay"-uje forecast protiv `post_t_candles` — reuse `replay_signal` logike (long: low≤invalidation→SL, high≥trigger→TP; short ogledalo; SL-first tie-break); rezultat: `direction_correct`, `trigger_hit`, `invalidation_respected`. Izvođenje iz replay-a postoji samo kao fallback za starije answer key fajlove bez novih polja. (b) `prepare_judge_input(output, answer_key)` koji sklapa SAMO output + `ground_truth` (eksplicitno BEZ `chart_path`/candles) + `JUDGE_PROMPT_TEMPLATE` (rubrika za sudiju: struktura/faza/event semantički, narativ, kalibracija, wait-pravilo). (c) `ScoreRecord` (po dimenziji + agregat + metod det/judge), upisan u `data/eval/_scores/<case>.score.json` (van case foldera). Pozivanje LLM-sudije je runbook korak — kod ga NE zove.

## Metadata

- **Type:** NEW_CAPABILITY
- **Complexity:** MEDIUM–HIGH (rubrika je suština vrednosti)
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 4 (depends: 2 ✅ merged, parallel: with 3)
- **Build target:** Opus @ high→extra-high za dizajn rubrike + JUDGE_PROMPT_TEMPLATE (NE Codex); Codex med za deterministički skorer (čista logika).
- **Affected systems:** nov eval skoring modul + testovi (ne dira postojeće servere).

## UX Design

```
analitičarev output (struktura, faza, event, smer, anon trigger/invalidation, confidence)
        +
answer key (_answers/<case>.answer.json: ground_truth, event_type, realized_direction, decisive, post_t_candles, coef_meta)
        │
        ├── DETERMINISTIČKI (kod): replay forecast vs answer_key.post_t_candles
        │      → direction_correct, trigger_hit, invalidation_respected
        │
        └── prepare_judge_input(output, answer_key)  [BEZ grafika/candles]
               → (runbook) izolovani Opus sudija po JUDGE_PROMPT_TEMPLATE
               → structure/phase/event_correct, narrative_quality, calibration
        │
        ▼
   ScoreRecord (po dimenziji + agregat)  →  data/eval/_scores/<case>.score.json
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| ocena outputa | ne postoji | rubrika + det. skorer + izolovani sudija | merljiva pouzdanost po dimenziji |
| sudija ulaz | — | output + answer_key, BEZ grafika | nema sudija-leakage |

## Answer-Key And Eval-Output Contract

`answer_key` fajl `data/eval/_answers/<case>.answer.json` mora da nosi, pored postojećih `case_id/symbol/cutoff/coef_meta/ground_truth/n_bars`:

- `event_type: str`
- `realized_direction: "up" | "down" | "none"`
- `decisive: bool`
- `post_t_candles: list[dict]` — anonimizovane sveće za `T..T+future_bars`, isti `coef_meta`/koeficijent kao blind snapshot, za deterministički replay u Phase 4.

Eval-output šema analitičara koju troše probe runbook i Phase 6: `direction`, numerički anon `trigger`, numerički anon `invalidation`, `confidence`.

## Mandatory Reading

- `scripts/mcp/signal_logger_server.py:210-271` — `replay_signal`: side iz signal_type, `_check_long`/`_check_short` (low≤invalidation→hit_sl, high≥min(target)→hit_tp, SL-first tie-break), iteracija po barovima sa `open_time`. Obrazac za deterministički replay.
- `scripts/mcp/analysis_journal_server.py:19-46` — `Forecast`/`Review`/`AnalysisRecord` (oblik output-a koji se skoruje); `:92-98` — `_confidence` (0..1).
- `scripts/eval/snapshot_builder.py` — `build_snapshot` answer key blok (`_answers/<case_id>.answer.json` sa `case_id/symbol/cutoff/coef_meta/ground_truth/n_bars`) i `future_visible` post-T candles (`n_bars`..`n_bars+future_bars`); `anonymize` `coef_meta` (price_coef) za mapiranje nivoa; Phase 3 dodaje `event_type/realized_direction/decisive/post_t_candles`.
- `scripts/eval/lookahead_probe.py` — obrazac „kod priprema + runbook izvršava LLM" (probe_result šablon) — preslikati za sudiju.

## Patterns to Mirror

- **Deterministički ishod:** `replay_signal` long/short provera + SL-first tie-break (kopiraj logiku u scoring, ne importuj privatno).
- **Validacija/TypedDict:** `analysis_journal_server` `_required_text`/`_confidence` + TypedDict zapisi.
- **Out-of-folder izolacija:** `snapshot_builder` `_answers/` van `case_XX/` → `_scores/` po istom principu; sudija nikad ne dobija putanju do `case_XX/`.
- **Kod-priprema vs runtime-LLM:** `lookahead_probe` (šablon + runbook), preslikati za judge.

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/scoring.py` | create | rubrika (dimenzije+težine), deterministički skorer (replay), `prepare_judge_input` (bez grafika), `JUDGE_PROMPT_TEMPLATE`, `ScoreRecord`, persist u `_scores/` |
| `tests/test_scoring.py` | create | deterministički replay, izolacija (judge input bez grafika), wait-pravilo, agregat |
| `.gitignore` | edit (ako treba) | `data/eval/` već ignorisan (Phase 2) → `_scores/` pokriveno; proveriti |

## NOT Building

- Automatsko pozivanje LLM-sudije iz koda — to je runbook korak (orkestrator pušta izolovani Opus subagent).
- Ground-truth set (~10 tačaka) — Phase 3.
- Agregacija model × effort × token-cost — Phase 6.
- Promenu `analysis_journal`/`signal_logger` — samo se naslanjamo.
- Trade pozive.

## Step-by-Step Tasks

1. **Rubrika + ScoreRecord** — `scripts/eval/scoring.py`
   - Action: definisati dimenzije (`structure`, `phase`, `event`, `direction`, `trigger`, `invalidation`, `calibration`), `DIMENSION_METHOD` (det vs judge), `DIMENSION_WEIGHTS`; `DimensionScore` (`score: float 0..1`, `method: Literal["deterministic","judge"]`, `rationale: str`) i `ScoreRecord` TypedDict (`case_id`, `analysis_id|None`, `dimensions: dict`, `aggregate: float`, `wait_case: bool`).
   - Pattern: TypedDict + validacija iz `analysis_journal_server`.
   - Gotcha: agregat preskače `NA` dimenzije (vidi wait-pravilo).
   - Validate: `uv run --extra mcp python -c "import scripts.eval.scoring"`

2. **Deterministički skorer (replay)** — `scripts/eval/scoring.py`
   - Action: `score_deterministic(*, direction, trigger_level, invalidation_level, answer_key) -> dict` — primarno čitati `realized_direction`, `decisive` i `post_t_candles` iz `answer_key`; preslikati `replay_signal` logiku nad `post_t_candles`: long → `low<=invalidation` SL, `high>=trigger` TP; short ogledalo; SL-first; vrati `{trigger_hit: bool, invalidation_hit: bool, bars_to_resolution: int|None}`. `direction_correct` = poređenje `direction` sa `answer_key["realized_direction"]`. Ako stariji answer key nema nova polja, fallback sme da izvede realizaciju iz replay-a uz jasnu oznaku/komentar.
   - Pattern: `signal_logger_server.py:235-271`.
   - Gotcha: nivoi su u ANON prostoru (isti kao post-T anon candles) — ne mapirati nazad; ako je analitičarev trigger/invalidation tekst, parsira se u float (vidi Notes/assumption).
   - Validate: `uv run --extra mcp pytest tests/test_scoring.py -k deterministic -q`

3. **Wait-pravilo** — `scripts/eval/scoring.py`
   - Action: ako `answer_key["decisive"] == False` I analitičar dao nizak confidence + smer „wait/neutral" → determinističke dimenzije (`direction/trigger/invalidation`) = `NA` (ne kažnjavaju se, izuzete iz agregata); `wait_case=True`. Fallback za stariji answer key bez `decisive`: izvesti iz replay-a samo ako polje ne postoji. Kalibracija (judge) nagrađuje nizak confidence.
   - Gotcha: ne tretirati `NA` kao 0.
   - Validate: `uv run --extra mcp pytest tests/test_scoring.py -k wait -q`

4. **Judge ulaz + rubrika-prompt (izolacija)** — `scripts/eval/scoring.py`
   - Action: `prepare_judge_input(analysis_output: dict, answer_key: dict) -> dict` koji vraća SAMO `{output: ..., ground_truth: ...}` — eksplicitno IZBACUJE `chart_path`, `candles`, bilo koju putanju do `case_XX/`; `JUDGE_PROMPT_TEMPLATE` (string) sa rubrikom za sudiju: skoruj `structure/phase/event` semantički (sinonimi dozvoljeni), `narrative_quality`, `calibration`; primeni wait-pravilo; vrati STRUKTURISAN JSON (`{dimension: {score, rationale}}`).
   - Gotcha: tvrda garancija — funkcija NE sme da propusti grafik; test to dokazuje.
   - Validate: `uv run --extra mcp pytest tests/test_scoring.py -k isolation -q`

5. **Agregacija + persist** — `scripts/eval/scoring.py`
   - Action: `combine_scores(deterministic, judge_verdict, *, wait_case) -> ScoreRecord` (težinski agregat preko ne-NA dimenzija); `write_score(score_record, base_dir) -> Path` u `base_dir/_scores/<case_id>.score.json` (van case foldera).
   - Pattern: `snapshot_builder` `_answers/` upis.
   - Validate: `uv run --extra mcp pytest tests/test_scoring.py -k "aggregate or persist" -q`

6. **Testovi** — `tests/test_scoring.py` (vidi Testing Strategy).
   - Validate: `uv run --extra mcp pytest tests/test_scoring.py -q`

## Testing Strategy

`tests/test_scoring.py` (sintetičke sveće/answer key sa punom šemom `event_type/realized_direction/decisive/post_t_candles`, `tmp_path` za `_scores`):
1. `test_deterministic_trigger_hit` — long forecast, post-T candle prelazi trigger → `trigger_hit=True`; SL-first tie-break kad bar pokriva oba.
2. `test_deterministic_direction_correct` — smer poklopljen/promašen vs realized.
3. `test_invalidation_respected` — invalidation pogođen pre trigera → `invalidation_hit`.
4. `test_judge_input_excludes_chart` — `prepare_judge_input` rezultat NEMA `chart_path`/`candles`/`case_dir` ključeve (izolacija sudije); ground_truth prisutan.
5. `test_wait_rule_not_penalized` — answer_key bez odlučujućeg poteza + low-confidence „wait" → det. dimenzije `NA`, `wait_case=True`, agregat ih preskače.
6. `test_aggregate_skips_na` — agregat računa samo ne-NA dimenzije.
7. `test_score_written_outside_case_dir` — `_scores/<case>.score.json` van `case_XX/`.

## Validation Commands

```bash
# CLAUDE.md: koristiti uv, ne pip
uv run --extra mcp pytest tests/test_scoring.py -q   # ciljani
uv run --extra mcp pytest -q                          # pun set — postojeći zeleni
uv run --extra mcp python -c "import scripts.eval.scoring as s; assert s.JUDGE_PROMPT_TEMPLATE and s.prepare_judge_input"
```

## Acceptance Criteria

- Deterministički skorer reprodukuje `replay_signal` ponašanje (trigger/invalidation/smer) na sintetičkim slučajevima; SL-first tie-break.
- `prepare_judge_input` fizički NE sadrži grafik/candles/putanju do case foldera — dokazano testom.
- Wait-pravilo: opravdan low-confidence „wait" bez trigera u prozoru NIJE kažnjen; kalibracija odvojeno.
- `ScoreRecord` po dimenziji + agregat (preskače NA); upisan u `_scores/` van case foldera.
- `JUDGE_PROMPT_TEMPLATE` postoji i sadrži rubriku (struktura/faza/event/narativ/kalibracija + wait-pravilo).
- Svi postojeći testovi zeleni.

## Completion Checklist

- [ ] Rubrika (dimenzije/metod/težine) + `ScoreRecord`.
- [ ] Deterministički skorer (replay, reuse `replay_signal` logike).
- [ ] Wait-pravilo (NA, ne 0).
- [ ] `prepare_judge_input` (bez grafika) + `JUDGE_PROMPT_TEMPLATE`.
- [ ] Agregacija + persist u `_scores/`.
- [ ] 7 testova prolaze; `uv run --extra mcp pytest -q` ceo zelen.
- [ ] Sudija-runbook dokumentovan u Notes.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Sudija „prepozna" setup ako vidi grafik | `prepare_judge_input` fizički izbacuje grafik/candles; namenski izolacioni test |
| Strogo string-poređenje faze/eventa prestrogo (sinonimi) | semantičke dimenzije ide LLM-sudija, ne deterministika |
| Wait-slučaj nepravedno kažnjen | wait-pravilo: NA dimenzije izuzete iz agregata; kalibracija nagrađuje oprez |
| Trigger/invalidation kao slobodan tekst nisu numerički | eval output schema traži numerički anon nivo (assumption); parser sa jasnim ValueError ako fali |
| Determinizam zavisi od post-T candles | čitaj `post_t_candles` iz answer key-a; `future_visible` replay je samo fallback za starije artefakte |

## Notes

**Sudija runbook (gate — izvršava orkestrator/LLM, ne kod):** za svaki slučaj: (a) `prepare_judge_input(output, answer_key)` → ulaz BEZ grafika; (b) pusti **izolovani Opus subagent** sa `JUDGE_PROMPT_TEMPLATE` + tim ulazom (subagent nema kontekst i NIKAD ne dobija grafik/anon candles); (c) sudija vrati strukturisan JSON verdikt; (d) `combine_scores(deterministic, judge_verdict, wait_case=...)` → `ScoreRecord` → `write_score`. **Assumption (zabeleži):** eval output analitičara sadrži NUMERIČKI `trigger`/`invalidation` na anon skali (da deterministički replay radi); journal čuva slobodan tekst, pa eval-output schema je strožija (numerički nivoi) — alternativa je parser teksta. **Answer-key contract:** Phase 3 answer key nosi `event_type`, `realized_direction`, `decisive` i `post_t_candles`; Phase 4 ih čita direktno, a izvođenje iz replay-a koristi samo kao fallback za starije artefakte. Rubrika i `JUDGE_PROMPT_TEMPLATE` su glavni izvor vrednosti — graditi na Opus @ high→extra-high.
