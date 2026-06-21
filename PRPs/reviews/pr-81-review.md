---
pr: 81
title: "Dokumentuj #75 image canary i zabrani neizolovan Codex"
author: "ssmiljanicc"
reviewed: 2026-06-21T13:00:00+02:00
recommendation: request-changes
---

# PR Review: #81 - Dokumentuj #75 image canary i zabrani neizolovan Codex

## Summary

PR dodaje Claude/Codex image canary skripte, beleži empirijski neuspeh Codex read izolacije i fail-closed blokira Codex privatni benchmark. Trenutno blokiranje je bezbedno, ali novi mehanizam za buduće otključavanje ne dokazuje da se benchmark izvršava pod istim containment okruženjem u kojem je canary prošao. Zbog toga preporuka ostaje **REQUEST CHANGES**.

## Implementation Context

| Artifact | Path |
| --- | --- |
| Implementation Report | `PRPs/reports/spike-75-chart-image-isolacija-report.md` |
| Original Plan | Not found |
| Documented Deviations | N/A |

## Findings

### Critical

No critical issues found.

### High

1. **PASS verdict nije vezan za containment okruženje koje je dokazano** — `scripts/eval/isolation_state.py:93-125`, `scripts/eval/runtime_adapters.py:217-238`

   Gate proverava provider, `platform.system()` i Codex CLI verziju, ali ne proverava containment mehanizam ili njegovu konfiguraciju. Posle budućeg uspešnog canary-ja pod zasebnim UID-em, kontejnerom ili drugim wrapper-om, isti gitignored verdict može ostati na hostu; običan benchmark run sa istom CLI verzijom i OS-om, ali bez tog containment-a, proći će `preflight`. To ponovo omogućava čitanje answer key-a i ruši osnovnu garanciju privatnog benchmark-a. PASS mora biti vezan za izvršni profil koji adapter zaista koristi — na primer tako što preflight/run uvek ulaze kroz isti verifikovani wrapper i verdict sadrži/proverava identitet ili hash tog profila — ili se canary mora izvršavati u istom runtime putu neposredno pre benchmark-a.

### Medium

1. **Deklarisana platform fingerprint provera poredi samo naziv OS-a** — `scripts/eval/isolation_state.py:113-124`

   Verdict čuva i `platform.platform()`, a modul i runbook tvrde da je PASS vezan za trenutnu platformu, ali gate poredi samo `platform.system()`. PASS sa druge macOS verzije/arhitekture ostaje važeći iako se sandbox ponašanje može promeniti. Uporediti i sačuvani `verdict.platform` sa aktuelnim `platform.platform()` (ili preciznije definisanim stabilnim fingerprint-om) i dodati regresioni test.

2. **Naslov i uvod reporta protivreče zabeleženim realnim pozivima** — `PRPs/reports/spike-75-chart-image-isolacija-report.md:1-4`, `PRPs/reports/spike-75-chart-image-isolacija-report.md:104-122`

   Dokument na vrhu tvrdi „nulta cena, bez model poziva“ i „Nijedan model poziv nije izvršen“, dok završni odeljak opisuje više realnih Claude i Codex poziva. Ažurirati naslov/metod tako da razlikuje početnu zero-cost introspekciju od naknadno odobrenih canary poziva; sadašnji tekst daje netačan provenance izvršenja.

### Suggestions

1. `IsolationVerdict.canary` se zapisuje, ali gate ga nikad ne proverava. Provera očekivanog canary ID-a/version-a bi sprečila da drugi ili zastareli verdict format slučajno autorizuje runtime.

## Validation Results

| Check | Status | Details |
| --- | --- | --- |
| Ruff | PASS | `uv run ruff check` nad svim izmenjenim Python fajlovima |
| Test suite | PASS | `309 passed in 3.66s` |
| Claude canary dry-run | PASS | Bez model poziva; argv i stream-json payload konstruisani |
| Codex canary dry-run | PASS | Bez model poziva; image i outside sentinel putanje pravilno razdvojene |
| Diff whitespace | PASS | `git diff --check main...HEAD` |
| Python compile | PASS | `uv run python -m compileall -q scripts/eval tests` |
| Real paid canaries | SKIPPED | Postojeći report već beleži empirijske ishode; review nije ponavljao plaćene pozive |

## What's Good

- Dry-run je podrazumevan, a realni model poziv zahteva eksplicitni `--confirm`.
- Trenutno stanje bez PASS artefakta pravilno pada zatvoreno.
- Terminalni Codex command event se bira posle `in_progress` događaja i pokriven je regresionim testom.
- Issue #82 eksplicitno prati vraćanje bezbednog cross-provider rangiranja.

## Recommendation

**REQUEST CHANGES**

Zadržati trenutno fail-closed ponašanje, ali pre merge-a ukloniti mogućnost da PASS ostvaren pod jednim containment profilom autorizuje runtime bez tog profila. Srednje nalaze ispraviti u istom prolazu jer direktno određuju validnost bezbednosnog dokaza i tačnost spike reporta.
