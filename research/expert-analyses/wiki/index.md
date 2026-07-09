---
title: Expert Analyses Index
description: "Master indeks ekspertskog Wyckoff korpusa (book/crypto/Fraser) — navigacija po eventu, strukturi, i corpus-count."
type: system
status: draft
updated: 2026-07-09
sources: []
---

# Research: Expert Analyses — Index

Master pregled ekspertskih Wyckoff analiza grafikona iz tri raw izvora (book, crypto arhiva, Bruce Fraser
članci). Ovo je Korak 0 za [wyckoff#89](https://github.com/ssmiljanicc/wyckoff-ai/issues/89) — deblokira #86,
hrani #84/#90/#91.

## Navigacija

- [`EXTRACT_TEMPLATE.md`](../EXTRACT_TEMPLATE.md) — kanonski oblik extract fajla
- [`_gaps.md`](../_gaps.md) — paywalled/nedostupni izvori (WIKI_GAP)
- [`_progress.md`](../_progress.md) — coverage ledger (izvor istine za pokrivenost sweep-a)
- [`../batches.md`](../batches.md) — runner batch raspored (B01-B29)

## Dva frontmatter režima

Ovaj KB namerno nosi DVA odvojena frontmatter režima nad dva različita sadržajna sloja:

1. **`wiki/extracts/*.md`** — domenska struktura po [`EXTRACT_TEMPLATE.md`](../EXTRACT_TEMPLATE.md)
   (`source`, `page`/`post_url`, `asset`, `timeframe`, `wyckoff_event`, `structure`, `phase`,
   `image_path`, `type` ∈ `forward|retrospective|schematic`, `status` ∈ `candidate|validated|eval-used`).
   Validira ih `scripts/validate_expert_analyses.py` SOPSTVENIM domenskim proverama — NE core-ov
   `check_frontmatter` (extract kartice nisu učitane kroz `page_dirs`, pa core generičke provere
   nikad ne vide njihov sadržaj).
2. **`wiki/by-event/*.md`** i **`wiki/by-structure/*.md`** — llm-wiki šablon
   (`title`/`description`/`type` ∈ `topic|system|comparison|source-summary|question|output|health`/
   `status` ∈ `draft|active|needs-review`/`updated`/`sources`). Validira ih core `check_frontmatter`
   NEPROMENJEN. Trenutno svih 28 postojećih stranica nosi minimalan `type: topic`/`status: draft`
   backfill (infrastrukturni plan `wyckoff-onboarding-runner.plan.md` Zadatak 1) — B01+ sweep dopunjava
   `sources`/`description`/`status` kako pointeri ka extract karticama pristižu.

## Taksonomija (events)

- [Automatic Rally](by-event/automatic-rally.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Automatic Reaction](by-event/automatic-reaction.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Back Up To The Edge Of The Creek](by-event/back-up-to-the-edge-of-the-creek.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Buying Climax](by-event/buying-climax.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Failed Signal](by-event/failed-signal.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Fall Through The Ice](by-event/fall-through-the-ice.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Feather](by-event/feather.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Flat Reaction](by-event/flat-reaction.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Hinge](by-event/hinge.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Jump Across The Creek](by-event/jump-across-the-creek.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Last Point Of Supply](by-event/last-point-of-supply.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Last Point Of Support](by-event/last-point-of-support.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [No Shake Phase C](by-event/no-shake-phase-c.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Preliminary Support](by-event/preliminary-support.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Secondary Test](by-event/secondary-test.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Selling Climax](by-event/selling-climax.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Sign Of Strength](by-event/sign-of-strength.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Sign Of Weakness](by-event/sign-of-weakness.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Spring](by-event/spring.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [St As Msos](by-event/st-as-msos.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [St As Msow](by-event/st-as-msow.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Upthrust After Distribution](by-event/upthrust-after-distribution.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Upthrust](by-event/upthrust.md) — Wyckoff event — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.

## Taksonomija (structures)

- [Accumulation](by-structure/accumulation.md) — Wyckoff struktura — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Distribution](by-structure/distribution.md) — Wyckoff struktura — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Reaccumulation](by-structure/reaccumulation.md) — Wyckoff struktura — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Redistribution](by-structure/redistribution.md) — Wyckoff struktura — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.
- [Trading Range](by-structure/trading-range.md) — Wyckoff struktura — pointeri na expert-analyses extract kartice dodaju se tokom sweep-a.

## Corpus-count (ažurira se tokom sweep-a)

Izvedeno iz `_progress.md` (izvor istine za pokrivenost — NE broj extract fajlova, jer to ne razlikuje
"odbačeno" od "nepregledano").

| Izvor | Ukupno | Ukupno pregledano | Validni parovi | forward | retrospective | schematic | bez slike |
|---|---:|---:|---:|---:|---:|---:|---:|
| book | 248 | 0 | 0 | 0 | 0 | 0 | 0 |
| crypto | 46 | 0 | 0 | 0 | 0 | 0 | 0 |
| fraser | 243 | 0 | 0 | 0 | 0 | 0 | 0 |

Sweep još nije počeo (B01 je prvi pending batch) — tabela će se ažurirati posle svakog batch-a preko
`_progress.md`.
