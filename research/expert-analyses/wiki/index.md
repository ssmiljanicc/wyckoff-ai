---
title: Expert Analyses Index
description: "Master indeks ekspertskog Wyckoff korpusa (book/crypto/Fraser) — navigacija po eventu, strukturi, i corpus-count."
type: system
status: draft
updated: 2026-09-13
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
   NEPROMENJEN. Svih 28 postojećih stranica nosi minimalan `type: topic`/lifecycle `status`
   backfill (infrastrukturni plan `wyckoff-onboarding-runner.plan.md` Zadatak 1) — B01+ sweep dopunjava
   `sources`/`description`/`status` kako pointeri ka extract karticama pristižu.

## Taksonomija (events)

- [Automatic Rally](by-event/automatic-rally.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [Automatic Reaction](by-event/automatic-reaction.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Back Up To The Edge Of The Creek](by-event/back-up-to-the-edge-of-the-creek.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Buying Climax](by-event/buying-climax.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Failed Signal](by-event/failed-signal.md) — Wyckoff event — book prikazuje false-break divergencije, a crypto primeri pokazuju failed upthrust i bearish failure putanju kada BTC Spring ne napravi higher high.
- [Fall Through The Ice](by-event/fall-through-the-ice.md) — Wyckoff event — book schematic i Fraser B18–B19/B24 primeri prikazuju potvrđene break-ove Ice-a.
- [Feather](by-event/feather.md) — Wyckoff event — crypto primeri prikazuju bullish feather kao higher lows ili uske upbar-ove na opadajućem volumenu, uz apsorpciju i moguću acceleration.
- [Flat Reaction](by-event/flat-reaction.md) — Wyckoff event — crypto primeri prikazuju očekivani flat reaction posle Bitcoin shakeout-a i aktuelnu low-volatility reakciju u gornjoj polovini range-a.
- [Hinge](by-event/hinge.md) — Wyckoff event — crypto i Fraser B23–B25 chart primeri prikazuju hinge, trendline-break i moguću novu trend fazu.
- [Jump Across The Creek](by-event/jump-across-the-creek.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [Last Point Of Supply](by-event/last-point-of-supply.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Last Point Of Support](by-event/last-point-of-support.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [No Shake Phase C](by-event/no-shake-phase-c.md) — Wyckoff event — accumulation i distribution varijante prikazuju Phase C test koji ne doseže granicu strukture.
- [Preliminary Support](by-event/preliminary-support.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Secondary Test](by-event/secondary-test.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [Selling Climax](by-event/selling-climax.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [Sign Of Strength](by-event/sign-of-strength.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Sign Of Weakness](by-event/sign-of-weakness.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Spring](by-event/spring.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [St As Msos](by-event/st-as-msos.md) — Wyckoff event — book prikazuje Phase B upper-end test, a crypto TRX accumulation primer razlikuje dynamic ST as mSOS in B od finalnog Sign of Strength-a.
- [St As Msow](by-event/st-as-msow.md) — Wyckoff event — book primeri prikazuju Phase B lower-end ST as SOW u accumulation, njegovu granicu prema Spring labeli i minor SOW u distribution kontekstu.
- [Upthrust After Distribution](by-event/upthrust-after-distribution.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Upthrust](by-event/upthrust.md) — Wyckoff event — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.

## Taksonomija (structures)

- [Accumulation](by-structure/accumulation.md) — Wyckoff structure — book i crypto primeri dopunjeni su Fraser B17–B29 konkretnim chart–interpretation primerima.
- [Distribution](by-structure/distribution.md) — Wyckoff structure — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Reaccumulation](by-structure/reaccumulation.md) — Wyckoff structure — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Redistribution](by-structure/redistribution.md) — Wyckoff structure — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.
- [Trading Range](by-structure/trading-range.md) — Wyckoff structure — book i crypto primeri dopunjeni su Fraser B17–B28 konkretnim chart–interpretation primerima.

## Corpus-count (ažurira se tokom sweep-a)

Izvedeno iz `_progress.md` (izvor istine za pokrivenost — NE broj extract fajlova, jer to ne razlikuje
"odbačeno" od "nepregledano").

| Izvor | Ukupno | Ukupno pregledano | Validni parovi | forward | retrospective | schematic | bez slike |
|---|---:|---:|---:|---:|---:|---:|---:|
| book | 248 | 248 | 77 | 0 | 10 | 67 | 0 |
| crypto | 46 | 46 | 81 | 75 | 6 | 0 | 0 |
| fraser | 243 | 243 | 530 | 376 | 151 | 3 | 0 |

B01 (book page_001–page_020) završen 2026-07-09 — 2 validna para, oba `type: schematic`
(generički price-cycle i trading-range dijagrami iz uvodnih poglavlja, bez konkretnog asseta).
B02 (book page_021–page_040) završen 2026-09-12 — 3 validna para, sva
`type: schematic` (trading-range tipovi i dve osnovne accumulation varijante); 17
dokumenata je odbačeno.
B03 (book page_041–page_060) završen 2026-09-12 — 4 validna para: 2
`type: schematic` (dve distribution varijante) i 2 `type: retrospective`
(cause/effect chart i AAPL daily point-and-figure reaccumulation count od AR do
LPS-a); 16 dokumenata
je odbačeno.
B04 (book page_061–page_080) završen 2026-09-12 — 4 validna para, sva
`type: schematic` (failed key-level break i uvodni accumulation,
reaccumulation i distribution prikazi); 16 dokumenata je odbačeno.
B05 (book page_081–page_100) završen 2026-09-12 — 4 validna para, sva
`type: schematic` (redistribution range pauze, dva Preliminary Support prikaza
i Preliminary Supply prikaz); 16 dokumenata je odbačeno.
B06 (book page_101–page_120) završen 2026-09-12 — 6 validnih parova, svi
`type: schematic` (Selling i Buying Climax, njihove exhaustion varijante i
Automatic Rally/Reaction); 14 dokumenata je odbačeno.
B07 (book page_121–page_140) završen 2026-09-12 — 7 validnih parova, svi
`type: schematic` (tri Secondary Test prikaza, accumulation/distribution Phase B
testovi, No Demand test u weak-market kontekstu i Spring appearance varijante);
13 dokumenata je odbačeno.
B08 (book page_141–page_160) završen 2026-09-12 — 11 validnih parova, svi
`type: schematic` (tri Spring tipa, Ordinary Shakeout u reaccumulation,
UTAD/minor UTAD i pet bullish breakout potvrda); 9 dokumenata je odbačeno.
B09 (book page_161–page_180) završen 2026-09-12 — 11 validnih parova, svi
`type: schematic` (Major SOW/SOW Bar, SOS i SOS Bar, bullish confirmation testovi,
failed breakout, LPS/LPSY tipovi i accumulation fazni prikazi); 9 dokumenata je
odbačeno.
B10 (book page_181–page_200) završen 2026-09-12 — 8 validnih parova, svi
`type: schematic` (Phase B–E accumulation prikazi, nested reaccumulation kao
BUEC većeg range-a, pet koraka strukture, Spring liquidity zone i Phase C
shake/test entry); 12 dokumenata je odbačeno. `page_197` manifestuje samo
rasterizovan tekst, ne grafikon.
B11 (book page_201–page_220) završen 2026-09-12 — 7 validnih parova, svi
`type: schematic`, na 6 raw stranica (Phase D/E entry pristupi, SOS/SOW
significant bars, Spring entry/test stop-loss prikazi, minor reaccumulation kao
LPS i BUEC/LPS stop ispod Creek-a); 14 dokumenata je odbačeno. `page_218`
sadrži dva zasebna validna para, dok `page_213` i `page_219` manifestuju samo
rasterizovan tekst.
B12 (book page_221–page_240) završen 2026-09-12 — 9 validnih parova: 2
`type: schematic` (climatic exit i distribution Phase A exit sekvenca) i 7
`type: retrospective` (unlabeled accumulation reading i realni ES, 6B, 6E,
BTCUSDT, ITX i GOOGL chart primeri); 11 dokumenata je odbačeno, uključujući
concept-only liquidity-zone schematic sa `page_224`.
B13 (book page_241–page_248) završen 2026-09-12 — 1 validan
`type: retrospective` par: realni 15-minute 6A chart sa sloping redistribution
preliminary-stop kontekstom, Phase C Spring + test-om i reaccumulation nastavcima;
7 dokumenata je odbačeno.
Book ledger je završen na kanonskom kraju `raw/book/pages/page_248.md`; nema dalje
book resume tačke.
B14 (crypto manifest pozicije 1–16) završen 2026-09-12 — 42 validna para
(37 `type: forward`, 5 `type: retrospective`), 1 odbačen dostupan post i 1
paywalled post. Pozicija 2 (`wyckoff-crypto-report-vol-15`) je odbačena jer su
relevantni chart asseti HTML fallback dokumenti umesto proverljivih slika, a
pozicija 13 (`wyckoff-crypto-report-vol-26`) evidentirana je kao WIKI_GAP.
Crypto resume tačka za B15 je manifest pozicija 17,
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-30.md`.
B15 (crypto manifest pozicije 17–31) završen 2026-09-12 — 27 validnih parova,
svi `type: forward`; nema odbačenih ni paywalled dokumenata. Pregledani su raw
postovi od `wyckoff-crypto-report-vol-30` do `wyckoff-crypto-report-vol-44`, a
ledger je stigao do manifest pozicije 31. Crypto resume tačka za B16 je pozicija
32, `raw/crypto_archive/posts/wyckoff-crypto-report-vol-45.md`.
B16 (crypto manifest pozicije 32–46) završen 2026-09-12 — 12 validnih parova
(11 `type: forward`, 1 `type: retrospective`), bez odbačenih dokumenata i sa 9
paywalled jedinica evidentiranih u `_gaps.md`. Dostupni postovi su volumeni
45–49 i 51; ledger je stigao do kanonskog kraja manifesta na poziciji 46,
`raw/crypto_archive/posts/wyckoff-crypto-report-59.md`, pa nema dalje crypto
resume tačke.
B17 (Fraser LC_ALL=C pozicije 1–20) završen 2026-09-12 — 49 validnih
chart–interpretation parova (10 `type: forward`, 39 `type: retrospective`),
bez schematic extract-a i paywalled jedinica; 6 dokumenata je odbačeno.
Pregledani scope je od `articles-stocktalk-2024-02-swing-trading-strategies-tips-487.md`
do `articles-wyckoff-2015-09-just-charts.md`. Fraser resume tačka za B18 je
LC_ALL=C pozicija 21, `raw/bruce_fraser/posts/articles-wyckoff-2015-10-redistribution-ruckus--.md`.
B18 (Fraser LC_ALL=C pozicije 21–40) završen 2026-09-13 — 44 validna
chart–interpretation para (10 `type: forward`, 34 `type: retrospective`),
bez schematic extract-a i paywalled jedinica; 4 dokumenta su odbačena kao
recap/definition-only ili concept-only sadržaj bez prirodnog mapiranja na
postojeću event/structure taksonomiju. Scope je završen na poziciji 40,
`raw/bruce_fraser/posts/articles-wyckoff-2016-03-distribution-power-waves.md`;
sledeća Fraser resume tačka je pozicija 41,
`raw/bruce_fraser/posts/articles-wyckoff-2016-03-judging-power-waves.md`.
B19 (Fraser LC_ALL=C pozicije 41–60) završen 2026-09-13 — 55 validnih
chart–interpretation parova (39 `type: forward`, 14 `type: retrospective`,
2 `type: schematic`), bez paywalled jedinica; 2 dokumenta su odbačena kao
recap/proceduralni sadržaj bez konkretnog chart–interpretation para. Scope je
završen na poziciji 60,
`raw/bruce_fraser/posts/articles-wyckoff-2016-07-point-and-figure-pie-in-the-sky.md`;
sledeća Fraser resume tačka je pozicija 61,
`raw/bruce_fraser/posts/articles-wyckoff-2016-07-stupid-chart-tricks-.md`.
B20 (Fraser LC_ALL=C pozicije 61–80) završen 2026-09-13 — 57 validnih
chart–interpretation parova (54 `type: forward`, 2 `type: retrospective`,
1 `type: schematic`), bez paywalled jedinica; 1 dokument je odbačen kao
concept-only trendline sadržaj bez prirodnog mapiranja na postojeću
event/structure taksonomiju. Scope je završen na poziciji 80,
`raw/bruce_fraser/posts/articles-wyckoff-2017-01-enjoying-the-short-term-view.md`;
sledeća Fraser resume tačka je pozicija 81,
`raw/bruce_fraser/posts/articles-wyckoff-2017-01-going-for-the-gold.md`.
B21 (Fraser LC_ALL=C pozicije 81–100) završen 2026-09-13 — 48 validnih
chart–interpretation parova (37 `type: forward`, 11 `type: retrospective`),
bez schematic extract-a i paywalled jedinica; 1 dokument je odbačen jer sadrži
samo edukativni tekst i dekorativnu sliku bez konkretnog grafikona. Header slike
i IWM chart uz koji nema Fraserove konkretne interpretacije nisu ekstrahovani.
Scope je završen na poziciji 100,
`raw/bruce_fraser/posts/articles-wyckoff-2017-06-another-stupid-chart-trick.md`;
sledeća Fraser resume tačka je pozicija 101,
`raw/bruce_fraser/posts/articles-wyckoff-2017-06-more-pie-bigger-sky.md`.
B22 (Fraser LC_ALL=C pozicije 101–120) završen 2026-09-13 — 36 validnih
chart–interpretation parova (33 `type: forward`, 3 `type: retrospective`),
bez schematic extract-a i paywalled jedinica; 3 dokumenta su odbačena kao
trendline/sector koncept bez prirodnog mapiranja na postojeću taksonomiju ili
memorijalni sadržaj bez konkretnog grafikona. Header i concept-only slike nisu
ekstrahovane. Scope je završen na poziciji 120,
`raw/bruce_fraser/posts/articles-wyckoff-2017-11-crude-oil-runs-with-the-bulls.md`;
sledeća Fraser resume tačka je pozicija 121,
`raw/bruce_fraser/posts/articles-wyckoff-2017-11-natural-gas-follows-crude.md`.
B23 (Fraser LC_ALL=C pozicije 121–140) završen 2026-09-13 — 50 validnih
chart–interpretation parova (33 `type: forward`, 17 `type: retrospective`), bez
schematic extract-a i paywalled jedinica; 1 dokument je odbačen kao edukativni
Distribution preview sa schematic definicijom i DECK chartom bez Fraserove
konkretne interpretacije tog grafikona. Scope je završen na poziciji 140,
`raw/bruce_fraser/posts/articles-wyckoff-2018-04-jumping-the-creek-a-review.md`;
sledeća Fraser resume tačka je pozicija 141,
`raw/bruce_fraser/posts/articles-wyckoff-2018-04-sp-500-zooming-in.md`.
B24 (Fraser LC_ALL=C pozicije 141–160) završen 2026-09-13 — 41 validan
chart–interpretation par (26 `type: forward`, 15 `type: retrospective`), bez
schematic extract-a i paywalled jedinica; 1 dokument je odbačen kao breadth/200dma
analiza bez prirodnog mapiranja na postojeću event/structure taksonomiju. Scope je
završen na poziciji 160,
`raw/bruce_fraser/posts/articles-wyckoff-2018-09-defangd.md`; sledeća Fraser resume
tačka je pozicija 161,
`raw/bruce_fraser/posts/articles-wyckoff-2018-09-semi-tough.md`.
B25 (Fraser LC_ALL=C pozicije 161–180) završen 2026-09-13 — 49 validnih
chart–interpretation parova (42 `type: forward`, 7 `type: retrospective`), bez
schematic extract-a, odbačenih dokumenata i paywalled jedinica. Četiri dodatna
content charta odbačena su kao concept/trend ili correlation prikazi bez prirodnog
mapiranja na dozvoljenu event/structure taksonomiju; njihovi postovi imaju druge
validne parove. Scope je završen na poziciji 180,
`raw/bruce_fraser/posts/articles-wyckoff-2019-04-wynn-win.md`; sledeća Fraser resume
tačka je pozicija 181,
`raw/bruce_fraser/posts/articles-wyckoff-2019-04-yields-flatten.md`.
B26 (Fraser LC_ALL=C pozicije 181–200) završen 2026-09-13 — 40 validnih
chart–interpretation parova (39 `type: forward`, 1 `type: retrospective`), bez
schematic extract-a i paywalled jedinica; 4 video/edukativna dokumenta su odbačena
bez validnog susednog para. Jedan GOLD daily kandidat nije upisan jer njegov raw
evidence blok meša daily pasus sa kasnijim monthly summary-jem. Scope je završen na
poziciji 200, `raw/bruce_fraser/posts/articles-wyckoff-2020-05-work-area-ahead-901.md`;
sledeća Fraser resume tačka je pozicija 201,
`raw/bruce_fraser/posts/articles-wyckoff-2020-06-power-charting-tv-special-gues-242.md`.
B27 (Fraser LC_ALL=C pozicije 201–220) završen 2026-09-13 — 33 validna
chart–interpretation para (30 `type: forward`, 3 `type: retrospective`), bez
schematic extract-a, odbačenih dokumenata i paywalled jedinica. Dekorativne slike,
concept-only schematic i chartovi bez vezane konkretne interpretacije nisu ekstrahovani.
Scope je završen na poziciji 220,
`raw/bruce_fraser/posts/articles-wyckoff-2022-05-is-the-trend-about-to-bend-736.md`;
sledeća Fraser resume tačka je pozicija 221,
`raw/bruce_fraser/posts/articles-wyckoff-2022-08-a-wyckoff-cause-is-forming-wha-60.md`.
B28 (Fraser LC_ALL=C pozicije 221–240) završen 2026-09-13 — 25 validnih
chart–interpretation parova (22 `type: forward`, 3 `type: retrospective`), bez
schematic extract-a i paywalled jedinica; 6 video/edukativnih ili concept-only
dokumenata odbačeno je bez prirodnog mapiranja na postojeću event/structure
taksonomiju. Scope je završen na poziciji 240,
`raw/bruce_fraser/posts/articles-wyckoff-2024-10-secular-shenanigans-676.md`;
sledeća Fraser resume tačka je pozicija 241,
`raw/bruce_fraser/posts/articles-wyckoff-2024-12-swing-trading-with-point-figur-511.md`.
B29 (Fraser LC_ALL=C pozicije 241–243) završen 2026-09-13 — 3 validna
chart–interpretation para (1 `type: forward`, 2 `type: retrospective`), bez
schematic extract-a i paywalled jedinica; 2 dokumenta bez Markdown slike i
manifest mapiranja su odbačena. Scope je završen na kanonskom kraju Fraser
spiska, `raw/bruce_fraser/posts/has-the-bull-run-its-course.md`; nema dalje
Fraser resume tačke.
