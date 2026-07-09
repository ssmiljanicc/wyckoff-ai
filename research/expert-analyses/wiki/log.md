# Log — research/expert-analyses/wiki

Hronološki, append-only operacioni log (mirror `knowledge/wiki/log.md` konvencije).

## 2026-07-09 — B01 (book, page_001–page_020)

Sweep prve serije book stranica (deljeni merni uzorak za wyckoff#92). Od 20
pregledanih stranica, 7 je imalo figuru po `raw/book/image_manifest.json`
(page_001, 009, 011, 012, 014, 017, 019); od njih su 2 zadovoljila kriterijum
validnog para (figura + konkretna Wyckoff interpretacija + identifikabilan
kontekst — stari plan `research-expert-analyses-index.plan.md` Zadatak 3):

- `book_p014_accumulation-distribution-cycle_schematic.md` — generički price-cycle
  schematic (Ch.2), labeluje sve četiri structure (accumulation, reaccumulation,
  distribution, redistribution) → pointer dodat u sve četiri `by-structure/*.md`
  stranice.
- `book_p017_trading-range_schematic.md` — generički Uptrend/Downtrend/Trading
  Range schematic (Ch.3) → pointer dodat u `by-structure/trading-range.md`.

Odbačeno (18): page_002–008, 010, 013, 015, 016, 018, 020 (nema figure na stranici);
page_001 (cover art, bez teksta); page_009 (portret, biografija — ne chart
interpretacija); page_011 (dekorativni part-divider, bez teksta); page_012
(waves schematic, gola definicija + van event/structure taksonomije); page_019
(trend-timeframe nesting schematic, van event/structure taksonomije).

Oba extract-a su `type: schematic` — nijedan par u ovom rasponu nije `forward`/
`retrospective` (Part 1 "How Markets Move" je uvodno poglavlje bez konkretnih
imenovanih događaja; ti počinju u Part 5, dalje u knjizi).

Misattribution check primenjen na oba extracta (citation verification drill,
`batches.md` § Disciplina citiranja) — verbatim citat i `page`/`image_path`
potvrđeni protiv `raw/book/pages/page_014.md` i `page_017.md`.

`_progress.md` red `book`: reviewed 0→20, valid 0→2, rejected 0→18,
last_reviewed → `raw/book/pages/page_020.md`.

Batch kompletan (svih 20 stranica obrađeno u jednom prolazu, nije dostignuto
≥50% konteksta) — resume tačka za B02 je `page_021.md`.

## 2026-07-09 — B01 ingest (complete)

Ingest B01: validator fail=0 warn=30.
