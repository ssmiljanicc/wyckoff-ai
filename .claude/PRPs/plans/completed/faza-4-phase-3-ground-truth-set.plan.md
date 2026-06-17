# Feature: Phase 3 — Ground-truth test set v1 (~10 kuriranih Wyckoff tačaka)

## Summary

Kurirani skup od ~10 istorijskih Wyckoff „odlučujućih tačaka" (spring, UTAD/UT, SOS/SOW, redistribucija prerušena u akumulaciju, čista Phase-B buka, failed signali) preko više crypto simbola, sa ≥2 post-knowledge-cutoff tačke (van pretrening znanja modela). Svaka tačka je struktura `{case_id, symbol, timeframe, cutoff (T), n_bars, event_type, realized_direction, decisive, ground_truth}`. Generator zove `build_snapshot(mode="blind")` (Phase 2) za sve tačke i proizvodi `data/eval/case_XX/` + answer key u `data/eval/_answers/`. Ovo je ulaz koji Phase 4 (skoring) i Phase 6 (benchmark) troše. Obrazac je proširenje `lookahead_probe.PROBE_CASES`.

## User Story

As a eval-harness pripremač
I want to kurirani, event-tipovima izbalansiran skup istorijskih tačaka sa skrivenim ground truth-om
So that mogu da skorujem slepu Wyckoff analizu na reprezentativnom uzorku, ne samo na poznatim BTC vrhovima/dnima.

## Problem Statement

Phase 2 (`scripts/eval/snapshot_builder.py`) može da napravi anonimizovan future-blind snapshot za JEDNU tačku, a `lookahead_probe.PROBE_CASES` (`scripts/eval/lookahead_probe.py:40-76`) ima samo 3 probe-slučaja, sva 3 **poznata BTC/ETH događaja** bez `event_type` oznake i bez balansa po Wyckoff fenomenu. Da bi se skor (Phase 4) merio reprezentativno, treba kurirani v1 skup (~10) sa: (a) miksom event-tipova, (b) više simbola uključujući mid-cap altove, (c) ≥2 post-cutoff tačke (model ih ne može „prepoznati iz pretreninga"), (d) failed signali (gde se očekivani Wyckoff ishod NIJE desio).

## Solution Statement

Nov modul `scripts/eval/ground_truth_cases.py` sa listom `GROUND_TRUTH_CASES` (~10 dict-ova, oblik kao `PROBE_CASES` + polja `event_type`, `realized_direction`, `decisive`) i validatorom kvote event-tipova. Nov generator `scripts/eval/build_eval_set.py` loop-uje preko liste i zove `build_snapshot(mode="blind", ...)` (obrazac `lookahead_probe.run_probe`, `scripts/eval/lookahead_probe.py:116-144`), pišući `data/eval/case_XX/` + `_answers/`. `build_snapshot` (ili `build_eval_set`) se proširuje unazad-kompatibilnim parametrom, npr. `answer_extra: dict | None`, da answer key upiše `event_type/realized_direction/decisive/post_t_candles`; `post_t_candles` su anonimizovane sveće `T..T+future_bars`, dohvaćene preko `get_ohlcv(end_time=T+future_bars)`, istim case koeficijentom kao blind snapshot. Stock tačka iz PRD-a se **odlaže** za v1 (Binance-only klijent) uz zabeleženi WIKI_GAP/TODO. Kuracija realnih tačaka (simbol/datum/ground_truth) je domenski rad implementera (Opus); plan daje strukturu, kvotu, kandidate i pravila verifikacije.

## Metadata

- **Type:** NEW_CAPABILITY (data curation)
- **Complexity:** MEDIUM (kod je lak; vrednost je u domenskoj kuraciji)
- **Source PRD:** `.claude/PRPs/prds/faza-4-eval-journal-harness.prd.md` → Phase 3 (depends: 2 ✅ merged; parallel: with 4)
- **Build target:** Opus @ high (izbor Wyckoff tačaka + verifikacija ground truth-a je suština; NE Codex). Sonnet/Codex može samo za generator I/O + testove.
- **Affected systems:** eval case-lista (nov), eval-set generator (nov).

## UX Design

Operator/pipeline workflow:

```
PRE:  lookahead_probe.PROBE_CASES = 3 BTC/ETH slučaja, bez event_type, bez balansa

POSLE:
  ground_truth_cases.GROUND_TRUTH_CASES  -> ~10 tačaka {case_id, symbol, tf, cutoff, n_bars, event_type, realized_direction, decisive, ground_truth}
  build_eval_set.run()                   -> za svaku: build_snapshot(blind)
                                            data/eval/case_XX/{candles.json, chart.png}
                                            data/eval/_answers/case_XX.answer.json (istina)
                                            data/eval/manifest.json (bez istine)
  validate_event_coverage()              -> potvrdi kvotu (2 spring, 2 UTAD/UT, 2 SOS/SOW, 1 redistrib, 1 Phase-B, 2 failed)
```

| Lokacija | Before | After | Impact |
| --- | --- | --- | --- |
| eval slučajevi | 3 probe-slučaja u kodu | ~10 kuriranih sa event_type | reprezentativan uzorak za skor |
| post-cutoff pokrivenost | nema | ≥2 tačke posle Jan-2026 cutoff-a | meri rezonovanje vs. pamćenje |

## Answer-Key And Eval-Output Contract

`answer_key` fajl `data/eval/_answers/<case>.answer.json` mora da nosi, pored postojećih `case_id/symbol/cutoff/coef_meta/ground_truth/n_bars`:

- `event_type: str`
- `realized_direction: "up" | "down" | "none"`
- `decisive: bool`
- `post_t_candles: list[dict]` — anonimizovane sveće za `T..T+future_bars`, isti `coef_meta`/koeficijent kao blind snapshot, za deterministički replay u Phase 4.

Eval-output šema analitičara koju troše probe runbook i Phase 6: `direction`, numerički anon `trigger`, numerički anon `invalidation`, `confidence`.

## Mandatory Reading

- `scripts/eval/lookahead_probe.py:40-76` — `PROBE_CASES` (obrazac case-dicta: `case_id, symbol, timeframe, cutoff, n_bars, ground_truth`) — proširiti `event_type`, `realized_direction` i `decisive` poljima.
- `scripts/eval/lookahead_probe.py:116-144` — `run_probe` loop koji zove `build_snapshot` po slučaju (obrazac generatora).
- `scripts/eval/lookahead_probe.py:81-113` — `_DryRunClient` (stub bez mreže; reuse za test/dry-run generatora).
- `scripts/eval/snapshot_builder.py` — `build_snapshot(symbol, timeframe, cutoff, n_bars, mode, case_id, *, future_bars, client, ground_truth, base_dir)` (potpis), `anonymize` (`:57`), `SnapshotResult` (`:42-49`), `_answers/` izolacija answer key-a.
- `scripts/mcp/market_data_client.py` — `get_ohlcv(symbol, timeframe, limit, end_time=...)` je **Binance-only (crypto)**; nema stock/equity izvor → diktира odluku oko stock-a (vidi NOT Building).

## Patterns to Mirror

- **Case-lista:** `PROBE_CASES` (lista dict-ova) → `GROUND_TRUTH_CASES` istog oblika + `event_type`.
- **Generator:** `run_probe` (`lookahead_probe.py:116-144`) loop + `build_snapshot(mode="blind", ...)`.
- **Dry-run/test bez mreže:** `_DryRunClient` (`lookahead_probe.py:81-113`).
- **Answer-key izolacija:** već u `build_snapshot` (`_answers/` van case foldera) — ne reimplementirati.

## Files to Change

| File | Action | Notes |
| --- | --- | --- |
| `scripts/eval/ground_truth_cases.py` | create | `GROUND_TRUTH_CASES` (~10) + `EVENT_QUOTA` + `validate_event_coverage()` |
| `scripts/eval/build_eval_set.py` | create | generator: loop → `build_snapshot(blind)`; `--dry-run`; štampa rezime pokrivenosti |
| `tests/test_ground_truth_cases.py` | create | kvota/polja/dry-run generator/answer-key izolacija testovi |

## NOT Building

- **Stock/equity tačka (v1)** — `market_data_client` je Binance-only; stock zahteva zaseban data-izvor (yfinance/Alpha Vantage adapter), što je **svoj enabler** (kao što je `end_time` bio Phase 1), ne deo Phase 3. **Odluka: v1 je crypto-only**; ostaviti `# WIKI_GAP: stock case zahteva non-Binance adapter` + TODO u `ground_truth_cases.py`. Obrazloženje: dodavanje stock adaptera proširuje opseg i rizik; bolje zaseban issue/faza. (Diversitet se postiže mid-cap altovima umesto akcijom.)
- **future_visible snapshoti** — Phase 3 generiše samo `blind` (skoring radi na blind ulazu); `future_visible` je probe-stvar (Phase 2).
- **Skoring/rubrika** — Phase 4.
- **Automatska verifikacija ground truth-a iz spoljnog izvora** — ground truth kurira/verifikuje implementer (Opus) ručno protiv istorije; kod samo nosi tekst.

## Step-by-Step Tasks

1. **Case-lista + kvota** — `scripts/eval/ground_truth_cases.py`
   - Action: definiši `EVENT_QUOTA = {"spring":2, "upthrust":2, "sos_sow":2, "redistribution_as_accumulation":1, "phase_b_noise":1, "failed_signal":2}` (ukupno 10) i `GROUND_TRUTH_CASES: list[dict]` gde svaki dict ima `case_id, symbol, timeframe, cutoff, n_bars, event_type, realized_direction, decisive, ground_truth`. Reuse oblik `PROBE_CASES`. Simboli: BTC, ETH (poznati) + mid-cap altovi (npr. LINK/ADA/DOT/AVAX/MATIC) za manje-poznate; **≥2 tačke sa `cutoff` posle 2026-01 (post-knowledge-cutoff)** sa realnim ishodom iz Q1-Q2 2026. Implementer (Opus) popunjava REALNE datume i ground_truth, verifikovane protiv istorije.
   - Pattern: `PROBE_CASES` (`lookahead_probe.py:40-76`).
   - Gotcha: `failed_signal` tačke = gde se očekivani Wyckoff ishod NIJE desio (npr. spring koji je propao u markdown) — ground_truth to eksplicitno kaže.
   - Validate: `uv run --extra mcp python -c "from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES; print(len(GROUND_TRUTH_CASES))"`

2. **Validator pokrivenosti** — `scripts/eval/ground_truth_cases.py`
   - Action: `validate_event_coverage(cases=GROUND_TRUTH_CASES) -> None`: prebroj po `event_type`, raise `ValueError` ako ne odgovara `EVENT_QUOTA`; potvrdi da svaki case ima sva obavezna polja, `realized_direction` u `{"up", "down", "none"}`, `decisive` bool i neprazan `ground_truth`; potvrdi ≥2 post-cutoff (`cutoff >= "2026-01-01"`); potvrdi `case_id` jedinstven.
   - Pattern: jasne `ValueError` poruke (kao `snapshot_builder` validacije).
   - Validate: `uv run --extra mcp python -c "from scripts.eval.ground_truth_cases import validate_event_coverage; validate_event_coverage(); print('ok')"`

3. **Generator** — `scripts/eval/build_eval_set.py`
   - Action: `run(dry_run=False, base_dir=Path('data/eval')) -> None`: prvo `validate_event_coverage()`; pa loop preko `GROUND_TRUTH_CASES` → `build_snapshot(mode="blind", client=_stub_if_dry_run, answer_extra={...}, ...)`; na kraju odštampaj rezime (broj generisanih, raspodela po event_type). `--dry-run` koristi stub klijent.
   - Pattern: `run_probe` (`lookahead_probe.py:116-144`) + `_DryRunClient` (`:81-113`) za dry-run.
   - Gotcha: pri pravom (ne-dry) run-u, post-cutoff tačke sa vrlo skorašnjim `cutoff` mogu imati manje od `n_bars` dostupnih sveća — generator treba da to prijavi jasno, ne da tiho preskoči.
   - Validate: `uv run --extra mcp python -m scripts.eval.build_eval_set --dry-run`

4. **Testovi** — `tests/test_ground_truth_cases.py` (vidi Testing Strategy).
   - Validate: `uv run --extra mcp pytest tests/test_ground_truth_cases.py -q`

## Testing Strategy

`tests/test_ground_truth_cases.py` (`tmp_path`, dry-run stub — bez mreže):
1. `test_case_count_and_quota` — `len(GROUND_TRUTH_CASES)` odgovara zbiru `EVENT_QUOTA`; `validate_event_coverage()` prolazi.
2. `test_all_cases_have_required_fields` — svaki case ima `case_id/symbol/timeframe/cutoff/n_bars/event_type/ground_truth`, neprazni.
3. `test_case_ids_unique` — nema duplikata `case_id`.
4. `test_at_least_two_post_cutoff` — ≥2 case sa `cutoff >= "2026-01-01"`.
5. `test_validate_rejects_bad_quota` — izmenjena lista koja krši kvotu → `ValueError`.
6. `test_build_eval_set_dry_run_generates_all` — `build_eval_set.run(dry_run=True, base_dir=tmp)` napravi `case_XX/` za svaku tačku i `_answers/<case>.answer.json` van case foldera; answer key sadrži `event_type/realized_direction/decisive/post_t_candles`; `manifest.json` bez `ground_truth`.

## Validation Commands

```bash
# CLAUDE.md: koristiti uv, ne pip
uv run --extra mcp pytest tests/test_ground_truth_cases.py -q          # ciljani
uv run --extra mcp pytest -q                                            # pun set — postojeći zeleni
uv run --extra mcp python -m scripts.eval.build_eval_set --dry-run      # generator scaffold (stub)
```

## Acceptance Criteria

- `GROUND_TRUTH_CASES` ima ~10 tačaka koje zadovoljavaju `EVENT_QUOTA`; `validate_event_coverage()` prolazi.
- ≥2 post-knowledge-cutoff (cutoff posle 2026-01) tačke sa realnim ishodom; ≥1 failed_signal eksplicitno označen.
- Multi-symbol (BTC/ETH + ≥2 mid-cap alta), NE samo poznati BTC vrhovi/dna.
- `build_eval_set --dry-run` generiše sve `case_XX/` + answer key-eve u `_answers/` (van case foldera), uključujući `event_type/realized_direction/decisive/post_t_candles`; manifest bez istine.
- Stock praznina dokumentovana (WIKI_GAP + TODO), v1 crypto-only.
- Svi postojeći testovi zeleni; novi prolaze.

## Completion Checklist

- [ ] `ground_truth_cases.py`: `GROUND_TRUTH_CASES` (~10) + `EVENT_QUOTA` + `validate_event_coverage()`.
- [ ] Realni, verifikovani ground_truth po tački (domenska kuracija — Opus).
- [ ] ≥2 post-cutoff + ≥1 eksplicitan failed_signal + multi-symbol.
- [ ] `build_eval_set.py` (loop + dry-run + rezime pokrivenosti).
- [ ] Stock WIKI_GAP/TODO zabeležen.
- [ ] 6 testova prolaze; `uv run --extra mcp pytest -q` ceo zelen.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Kurirane tačke su sve „udžbenički poznate" → model prepoznaje iz pretreninga | obavezne ≥2 post-cutoff tačke + mid-cap altovi; anon (Phase 2) dodatno brani; meri se anon-vs-revealed (Phase 6) |
| Pogrešno označen `event_type` ili netačan ground_truth | domenska verifikacija (Opus) protiv istorije; `failed_signal` eksplicitno opisan u ground_truth |
| Stock zahtev iz PRD-a nerešen | svesno odložen (WIKI_GAP + TODO); diversitet preko altova; zaseban enabler-issue za non-Binance adapter |
| Skorašnji post-cutoff `cutoff` → manje od n_bars sveća | generator jasno prijavi nedostatak, ne preskače tiho |

## Notes

Kuracija je nezavisna od ishoda Phase 2 lookahead probe-a: Phase 3 koristi `build_snapshot(mode="blind")` bez obzira da li probe pokaže da je blinding nužan. Ako probe (gate) kasnije pokaže da blinding nije potreban, generator se trivijalno prebacuje na živi `end_time` + as-of (isti `build_snapshot` API). Post-knowledge-cutoff = `cutoff` posle 2026-01 (knowledge cutoff modela je Jan 2026); danas je 2026-06, pa tačke sa T u Feb–Apr 2026 imaju realizovan ishod a van su pretrening znanja — najčistiji test „rezonovanje vs. pamćenje". Stock case ostaje u PRD-u kao budući diversitet kad postoji non-Binance data adapter.
