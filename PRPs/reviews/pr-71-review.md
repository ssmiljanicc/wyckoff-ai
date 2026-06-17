---
pr: 71
title: "Implement Phase 4 scoring judge"
author: "ssmiljanicc"
reviewed: 2026-06-17T15:43:33Z
recommendation: request-changes
---

# PR Review: #71 - Implement Phase 4 scoring judge

## Summary

PR dodaje Phase 4 scoring/judge helper-e za eval harness: deterministički replay, wait-pravilo, izolovan judge payload, težinsku agregaciju i `_scores/` persistenciju. Osnovna long/short replay logika i SL-first tie-break su usklađeni sa `signal_logger`, a ciljani i puni test suite prolaze.

Ipak, našao sam dve greške koje mogu da proizvedu netačan finalni skor i treba ih popraviti pre merge-a: nepotpun judge verdict se prihvata kao validan i daje agregat preko preostalih dimenzija, a fallback za starije answer key-eve se zaobilazi za low-confidence wait jer missing `decisive` implicitno postaje `False`. Dodatno, sanitizer za judge input uklanja samo poznata imena ključeva, pa ne daje tvrdu garanciju protiv path/candle leakage-a kroz druga polja.

## Implementation Context

| Artifact | Path |
| --- | --- |
| Implementation Report | `.claude/PRPs/reports/faza-4-phase-4-scoring-judge-report.md` |
| Original Plan | `.claude/PRPs/plans/completed/faza-4-phase-4-scoring-judge.plan.md` |
| Documented Deviations | 2 |

Dokumentovane devijacije su prihvatljive same po sebi: `score=None/status=na` za NA dimenzije i bez PRD update-a jer PRD fajl nije prisutan u worktree-u.

## Findings

### Critical

No critical issues found.

### High

1. `combine_scores` prihvata nepotpun judge verdict i renormalizuje agregat preko preostalih dimenzija.

Lokacija: `scripts/eval/scoring.py:351`

`_judge_dimensions` preskače svaku judge dimenziju koja nedostaje (`continue`), a `combine_scores` zatim računa agregat samo preko dimenzija koje postoje. To znači da malformed ili prazan judge JSON može da proizvede potpuno validan `ScoreRecord`; ručna provera sa `{}` kao judge verdict vraća `aggregate: 1.0` kada su determinističke dimenzije 1.0. To krši strict JSON ugovor iz `JUDGE_PROMPT_TEMPLATE` i može sakriti failure izolovanog sudije ili missing `structure/phase/event/narrative_quality/calibration` skorove.

Preporuka: zahtevati svih 5 `JUDGE_DIMENSIONS` u `judge_verdict` i baciti `ValueError` za missing/extra-malformed dimenzije pre agregacije; dodati test za prazan i delimičan judge verdict.

2. Missing `decisive` se tretira kao `False`, pa se fallback replay za starije answer key-eve preskače kod low-confidence wait poziva.

Lokacija: `scripts/eval/scoring.py:237`

Kod radi `bool(answer_key.get("decisive", False))`, pa stariji answer key bez `decisive` izgleda kao eksplicitno non-decisive. Ako analitičar kaže `wait` sa niskim confidence-om, funkcija vraća `NA` za sve determinističke dimenzije pre nego što uopšte pozove `_post_t_candles`/fallback replay. To je suprotno planu koji kaže da se za starije answer key-eve bez `decisive` realizacija izvodi iz replay-a kada je moguće. Reprodukcija:

```py
score_deterministic(
    direction="wait",
    confidence=0.2,
    answer_key={"case_id": "old_case", "future_visible": [{"high": 120.0, "low": 100.0}]},
)
```

Trenutno vraća `wait_case=True`, sve tri determinističke dimenzije `NA`, i `used_fallback=False`, iako je to upravo fallback scenario.

Preporuka: razlikovati missing `decisive` od eksplicitnog `False`; wait NA pravilo primeniti samo kada je answer key eksplicitno non-decisive ili kada fallback replay ne nalazi odlučujući potez.

### Medium

1. Judge sanitizer nije tvrda izolaciona granica jer filtrira samo poznata imena ključeva, ne vrednosti i candle-shaped podatke pod drugim ključevima.

Lokacija: `scripts/eval/scoring.py:311`

`_sanitize_for_judge` uklanja ključeve iz `SENSITIVE_JUDGE_KEYS` i ključeve koji završavaju na `_path`, ali sve string vrednosti i liste pod drugim imenima prolaze dalje. Na primer, `{"notes": {"source": "/tmp/data/eval/case_01/chart.png"}, "data": [{"high": 1, "low": 0}]}` ostaje u judge payload-u. To slabi tvrdnju iz plana/testa da payload fizički ne sadrži putanju do `case_XX/` niti candle podatke. Postojeći test pokriva samo `chart_path`, `candles_path`, `case_dir` i literal `"candles"` kroz poznate ključeve.

Preporuka: ograničiti `analysis_output` na eksplicitni allowlist očekivanih output polja ili dodati vrednosno scrubovanje path-like stringova i candle-shaped lista/dict-ova; proširiti test da pokrije non-sensitive key sa `case_XX` path vrednošću.

### Suggestions

No suggestions.

## Validation Results

| Check | Status | Details |
| --- | --- | --- |
| Import smoke | PASS | `uv run --extra mcp python -c "import scripts.eval.scoring as s; assert s.JUDGE_PROMPT_TEMPLATE and s.prepare_judge_input"` |
| Targeted scoring tests | PASS | `uv run --extra mcp pytest tests/test_scoring.py -q` -> 8 passed |
| Full test suite | PASS | `uv run --extra mcp pytest -q` -> 196 passed |
| Manual old-key fallback probe | FAIL | Missing `decisive` + low-confidence wait returns `NA` without fallback replay. |
| Manual incomplete judge verdict probe | FAIL | `combine_scores(det, {})` returns a valid aggregate instead of rejecting missing judge dimensions. |
| Manual judge leakage probe | FAIL | Path string and candle-shaped data under non-sensitive keys remain in payload. |

## What's Good

- Deterministički long/short replay prati postojeći `signal_logger` obrazac, uključujući konzervativni SL-first tie-break.
- NA agregacija ne tretira `None` kao nulu i reweight-uje samo scored dimenzije.
- `_scores/<case_id>.score.json` persistencija je van case foldera i pokrivena testom.
- Judge payload iz answer key-a koristi allowlist i ne prosleđuje `symbol`, `cutoff`, `coef_meta` ili `post_t_candles`.

## Recommendation

**REQUEST CHANGES**

Popraviti validaciju judge verdict-a i missing-`decisive` fallback ponašanje pre merge-a. Sanitizer izolaciju bih takođe ojačao u ovom PR-u jer je to centralni security/eval-integrity cilj Phase 4.
