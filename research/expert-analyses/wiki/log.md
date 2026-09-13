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

## 2026-09-12 — B02 (book, page_021–page_040)

Pregledano je tačno 20 dodeljenih stranica: 3 validna schematic para
(`page_033`, `page_038`, `page_040`), 17 odbijenih dokumenata i 0 paywalled.
Concept-only dijagrami (Speed, Projection, Depth i opšte line/channel tehnike),
dekorativna pregrada i strane bez primarne slike nisu prihvaćeni kao samostalni
event/structure primeri. Resume tačka za B03 je `raw/book/pages/page_041.md`.

Citation verification drill primenjen je pre svakog citata, a završni
misattribution check ponovo je potvrdio source locator, doslovni pasus i
manifestovani primary image_path za sva 3 nova extract-a.

## 2026-09-12 — B02 ingest (complete)

Ingest B02: validator fail=0 warn=0.

## 2026-09-12 — B03 (book, page_041–page_060)

Pregledano je tačno 20 dodeljenih stranica: 4 validna para (`page_042`,
`page_044`, `page_054`, `page_057`), 16 odbijenih dokumenata i 0 paywalled.
Concept-only order-book, price/volume i projection prikazi bez prirodnog
event/structure mapiranja, dekorativna pregrada i strane bez primarne slike nisu
prihvaćeni kao samostalni primeri. Resume tačka za B04 je
`raw/book/pages/page_061.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B03 ingest (complete)

Ingest B03: validator fail=0 warn=0.

## 2026-09-12 — B03 semantic correction (page_057–page_058)

Semantic spot-check je ispravio AAPL point-and-figure extract: chart je dnevni
reaccumulation primer, a doslovni pasus na `page_058.md` definiše count od
Automatic Reaction-a do Last Point of Support-a. Extract sada koristi
`page_range: 57-58`, zadržava primary sliku sa `page_057.md` i ima pointere iz
`automatic-reaction`, `last-point-of-support` i `reaccumulation` indeksa;
pogrešan `accumulation` pointer je uklonjen. Coverage ledger je nepromenjen.

Ponovljena je canonical-verbatim provera nad opsegom 57–58, kao i provera
source/page lokatora i primary image manifesta.

## 2026-09-12 — B04 (book, page_061–page_080)

Pregledano je tačno 20 dodeljenih stranica: 4 validna schematic para
(`page_068`, `page_072`, `page_077`, `page_080`), 16 odbijenih dokumenata i 0
paywalled. Concept-only effort/result prikazi bez prirodnog event/structure
mapiranja i strane bez primarne slike nisu prihvaćeni kao samostalni primeri.
Resume tačka za B05 je `raw/book/pages/page_081.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B04 ingest (complete)

Ingest B04: validator fail=0 warn=0.

## 2026-09-12 — B05 (book, page_081–page_100)

Pregledano je tačno 20 dodeljenih stranica: 4 validna schematic para
(`page_086`, `page_094`, `page_098` sa citatnim nastavkom na `page_099`, i
`page_100`), 16 odbijenih dokumenata i 0 paywalled. Strane bez manifestovane
primarne slike, skenirani fragment teksta na `page_085` i schematic na
`page_095` bez konkretnog tumačenja prikazanog grafikona nisu prihvaćeni.
Ledger je završen na `raw/book/pages/page_100.md`; resume tačka za B06 je
`raw/book/pages/page_101.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B05 ingest (complete)

Ingest B05: validator fail=0 warn=0.

## 2026-09-12 — B06 (book, page_101–page_120)

Pregledano je tačno 20 dodeljenih stranica: 6 validnih schematic parova
(`page_106`, `page_108`, `page_109`, `page_111`, `page_117` i `page_119`), 14
odbijenih dokumenata i 0 paywalled. Strane bez manifestovane primarne slike i
definicioni tekst bez konkretnog prikaza nisu prihvaćeni; exhaustion prikazi su
mapirani samo na postojeće accumulation/distribution structure indekse, bez
izmišljanja novih event slugova. Ledger je završen na
`raw/book/pages/page_120.md`; resume tačka za B07 je
`raw/book/pages/page_121.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B06 ingest (complete)

Ingest B06: validator fail=0 warn=0.

## 2026-09-12 — B07 (book, page_121–page_140)

Pregledano je tačno 20 dodeljenih stranica: 7 validnih schematic parova
(`page_121`, `page_122`, `page_123` sa citatnim nastavkom na `page_124`,
`page_126` sa citatnim nastavkom na `page_127`, `page_128`, `page_132` i
`page_137` sa citatnim nastavkom na `page_138`), 13 odbijenih dokumenata i 0
paywalled. Strane bez manifestovane primarne slike i definicioni tekst bez
konkretne interpretacije prikaza nisu prihvaćeni; `page_133` je odbijen jer
njegova raw jedinica ne tumači konkretni No Supply prikaz, a prethodna strana
ne može biti citatni nastavak za sliku sa strane 133. Ledger je završen na
`raw/book/pages/page_140.md`; resume tačka za B08 je
`raw/book/pages/page_141.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B07 ingest (complete)

Ingest B07: validator fail=0 warn=0.

## 2026-09-12 — B08 (book, page_141–page_160)

Pregledano je tačno 20 dodeljenih stranica: 11 validnih schematic parova
(`page_145`, `page_146`, `page_147`, `page_148`, `page_150`, `page_151`,
`page_154`, `page_156`, `page_157`, `page_158` i `page_159`), 9 odbijenih
dokumenata i 0 paywalled. Strane bez manifestovane primarne slike su odbačene;
Ordinary Shakeout je mapiran samo na postojeću `reaccumulation` strukturu, dok
je minor UTAD dobio `last-point-of-supply` samo kao eksplicitnu alternativnu
oznaku iz istog pasusa. Ledger je završen na
`raw/book/pages/page_160.md`; resume tačka za B09 je
`raw/book/pages/page_161.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B08 ingest (complete)

Ingest B08: validator fail=0 warn=0.

## 2026-09-12 — B09 (book, page_161–page_180)

Pregledano je tačno 20 dodeljenih stranica: 11 validnih schematic parova
(`page_161`, `page_164`, `page_165`, `page_167`, `page_169`, `page_170`,
`page_171`, `page_174`, `page_176`, `page_178` i `page_180`), 9 odbijenih
dokumenata i 0 paywalled. Strane bez manifestovane primarne slike su odbačene;
`page_163` nema interpretativni tekst, a `page_173` na istoj raw jedinici ne
tumači prikazani volume-profile schematic. Ledger je završen na
`raw/book/pages/page_180.md`; resume tačka za B10 je
`raw/book/pages/page_181.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B09 ingest (complete)

Ingest B09: validator fail=0 warn=0.

## 2026-09-12 — B10 (book, page_181–page_200)

Pregledano je tačno 20 dodeljenih stranica: 8 validnih schematic parova
(`page_182`, `page_184`, `page_186`, `page_189`, `page_192`, `page_195`,
`page_196` i `page_199`) i 12 odbijenih dokumenata, uz 0 paywalled. Strane bez
manifestovane primarne slike su odbačene; `page_197` manifestuje rasterizovan
tekst umesto grafikona. Citati sa `page_189` i `page_199` koriste neposrednu
sledeću stranu samo kao nastavak, dok primary image_path ostaje na izvornoj
strani. Ledger je završen na `raw/book/pages/page_200.md`; resume tačka za B11
je `raw/book/pages/page_201.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B10 ingest (complete)

Ingest B10: validator fail=0 warn=0.

## 2026-09-12 — B11 (book, page_201–page_220)

Pregledano je tačno 20 dodeljenih stranica: 7 validnih schematic parova na 6
raw stranica (`page_202`, `page_204`, `page_209`, `page_217`, dva para na
`page_218` i `page_220`), 14 odbijenih dokumenata i 0 paywalled. Strane bez
manifestovane primarne slike su odbačene; generički reversal i order-management
prikazi nisu prirodno mapirani na taksonomiju, a `page_213` i `page_219`
manifestuju rasterizovan tekst umesto grafikona. Ledger je završen na
`raw/book/pages/page_220.md`; resume tačka za B12 je
`raw/book/pages/page_221.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a.

## 2026-09-12 — B11 ingest (complete)

Ingest B11: validator fail=0 warn=0.

## 2026-09-12 — B12 (book, page_221–page_240)

Pregledano je tačno 20 dodeljenih stranica: 9 validnih parova na 9 raw
stranica (`page_222`, `page_223`, `page_228`, `page_229`, `page_231`,
`page_233`, `page_235`, `page_237` i `page_239`), 11 odbijenih dokumenata i
0 paywalled. Dva para su `type: schematic`, a sedam `type: retrospective`.
Strane bez manifestovane primarne slike odbačene su kao samostalni dokumenti;
`page_224` je odbačen kao concept-only liquidity-zone schematic bez prirodnog
event/structure mapiranja. Citati sa `page_229`, `page_231`, `page_235` i
`page_237` koriste neposrednu sledeću stranu samo kao nastavak, dok primary
image_path ostaje na izvornoj strani. Ledger je završen na
`raw/book/pages/page_240.md`; resume tačka za B13 je
`raw/book/pages/page_241.md`.

Citation verification drill primenjen je pre svakog citata. Završni
misattribution check ponovo je proverio source locator, doslovni pasus i
manifestovani primary image_path za poslednja 3 nova extract-a (`page_235`,
`page_237` i `page_239`).

## 2026-09-12 — B12 ingest (complete)

Ingest B12: validator fail=0 warn=0.

## 2026-09-12 — B13 (book, page_241–page_248)

Pregledano je tačno 8 dodeljenih stranica: 1 validan retrospective par na
`page_241` sa nastavkom citata na `page_242`, 7 odbijenih dokumenata i 0
paywalled. `page_243`–`page_245` i `page_248` nemaju grafikon, dok slike na
`page_246` i `page_247` nisu tržišni grafikoni i nemaju konkretnu Wyckoff
interpretaciju. Ledger je završen na `raw/book/pages/page_248.md`; book izvor je
na kanonskom kraju i nema dalje resume tačke.

Citation verification drill primenjen je pre citata. Završni misattribution
check ponovo je proverio source locator, doslovni pasus i manifestovani primary
image_path za novi extract sa `page_241`.

## 2026-09-12 — B13 ingest (complete)

Ingest B13: validator fail=0 warn=0. Kapija semantic-lint (završni book batch) sprovedena.

## 2026-09-12 — B13 semantic-gate corrections

Ispravljene su dispozicije pet book extract-a iz završne semantičke kapije:
Preliminary Supply (`page_100`) mapiran je na postojeći umbrella event
`preliminary-support` (PS/PSY), Selling Exhaustion (`page_108`) na
`selling-climax`, Buying Exhaustion (`page_111`) na `buying-climax`, a Ordinary
Shakeout (`page_148`) na `spring`. Primary Secondary Test sa `page_122`
ispravljen je iz Phase B u Phase A; tekst o ponašanju koje sledi u Phase B ostaje
kontekst, ne faza samog eventa. Odgovarajući by-event pointeri, raw `sources` i
opisi sinhronizovani su sa master indeksom. `_progress.md` brojevi i B13
`blocked` status nisu menjani.

Oba režima expert validatora (`--skip-git` i puna git-integrity provera) posle
ispravki imaju `warn=0` i nemaju nijedan non-boundary FAIL. Jedini očekivani
nalaz je `F-BATCH-SCOPE-INCOMPLETE`: B13 je namerno `blocked`, dok je book ledger
već stigao do kanonskog kraja 248/248; retry kapije je odvojen od ove sadržajne
ispravke.

## 2026-09-12 — B14 (crypto, manifest pozicije 1–16)

Pregledano je tačno 16 dodeljenih manifest jedinica, od
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-14.md` do
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-29.md`: 42 validna
chart–interpretation para, 1 odbačen dostupan dokument i 1 paywalled dokument.
`wyckoff-crypto-report-vol-15` je odbačen jer su relevantni chart asseti HTML
fallback dokumenti umesto proverljivih slika; `wyckoff-crypto-report-vol-26`
je evidentiran kao WIKI_GAP. Ledger je završen na manifest poziciji 16; resume
tačka za B15 je pozicija 17,
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-30.md`.

Citation verification drill primenjen je pre svakog od 42 citata. Završni
misattribution check primenjen je nad poslednja 3 nova extract-a proverom
source locator-a, doslovnog citata i image_path-a protiv iste raw jedinice.

## 2026-09-12 — B14 ingest (complete)

Ingest B14: validator fail=0 warn=0.

## 2026-09-12 — B15 (crypto, manifest pozicije 17–31)

Pregledano je tačno 15 dodeljenih manifest jedinica, od
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-30.md` do
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-44.md`: 27 validnih
chart–interpretation parova, 0 odbačenih dokumenata i 0 paywalled dokumenata.
Ledger je završen na manifest poziciji 31; resume tačka za B16 je pozicija 32,
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-45.md`.

Citation verification drill primenjen je pre svakog od 27 citata. Završni
misattribution check primenjen je nad poslednja 3 nova extract-a proverom source
locator-a, doslovnog citata i image_path-a protiv iste raw jedinice.

## 2026-09-12 — B16 (crypto, manifest pozicije 32–46)

Pregledano je tačno 15 dodeljenih manifest jedinica, od
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-45.md` do
`raw/crypto_archive/posts/wyckoff-crypto-report-59.md`: 12 validnih
chart–interpretation parova, 0 odbačenih dokumenata i 9 paywalled dokumenata.
Resume je počeo na manifest poziciji 32,
`raw/crypto_archive/posts/wyckoff-crypto-report-vol-45.md`; ledger je završen
na kanonskom kraju crypto manifesta, poziciji 46, pa nema sledeće crypto resume
tačke.

Citation verification drill primenjen je pre svakog od 12 citata. Završni
misattribution check primenjen je nad poslednja 3 nova extract-a proverom
source locator-a, doslovnog citata i image_path-a protiv iste raw jedinice.

## 2026-09-12 — B16 ingest (complete)

Ingest B16: validator fail=0 warn=0. Kapija semantic-lint (završni crypto batch) sprovedena.

## 2026-09-12 — B17 (Fraser, LC_ALL=C pozicije 1–20)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-stocktalk-2024-02-swing-trading-strategies-tips-487.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2015-09-just-charts.md`: 50 validnih
chart–interpretation parova, 6 odbačenih dokumenata i 0 paywalled dokumenata.
Resume je počeo na LC_ALL=C poziciji 1; ledger je završen na poziciji 20, a
sledeća Fraser resume tačka je pozicija 21,
`raw/bruce_fraser/posts/articles-wyckoff-2015-10-redistribution-ruckus--.md`.

Citation verification drill primenjen je pre svakog od 50 citata. Završni
misattribution check primenjen je nad poslednja 3 nova extract-a (`ISRG`,
`GMCR`, `MS`) proverom source locator-a, doslovnog citata i image_path-a
protiv iste raw jedinice i Fraser image manifesta.

## 2026-09-12 — B17 ingest (complete)

Ingest B17: validator fail=0 warn=0.

## 2026-09-13 — B17 semantic-gate corrections

Ispravljena je vizuelno proverljiva Fraser metadata: p003 AAPL i p004 FISV,
ESRX, VIAB, V i AMZN chartovi su `daily`, kao i p005 SLB/DOW i p006 CMG.
P004 extract fajlovi i svi njihovi by-event/by-structure pointeri preimenovani
su prema tickerima na samim slikama. P019 FXI SOW je postavljen u Phase D, dok
KLAC LPSY extract koristi `phase: unknown` jer isti pasus objedinjuje LPSY
događaje iz late Phase B i Phase D. P020 ISRG locating kontekst je usklađen
sa Daily chartom.

P010 AAPL Stride/overbought chart je odbačen: Fraserov pasus ne podržava
Buying Climax event iz dozvoljene taksonomije. Uklonjeni su extract i njegov
by-event pointer; B17 ledger sada beleži 20 pregledanih jedinica, 49 validnih
parova i 7 odbačenih dokumenata. Master indeks i corpus-count su usklađeni.

## 2026-09-13 — B18 (Fraser, LC_ALL=C pozicije 21–40)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2015-10-redistribution-ruckus--.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2016-03-distribution-power-waves.md`:
44 validna chart–interpretation para, 4 odbačena dokumenta i 0 paywalled
dokumenata. Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C
poziciji 21; ledger je završen na poziciji 40. Sledeća Fraser resume tačka je
pozicija 41,
`raw/bruce_fraser/posts/articles-wyckoff-2016-03-judging-power-waves.md`.

Citation verification drill primenjen je neposredno pre svakog od 44 citata,
uz proveru lokalne slike protiv istog raw posta i Fraser image manifesta.
Završni misattribution check primenjen je nad poslednja 3 nova extract-a
(`DJIA`, `IWM`, `XLE`) proverom source locator-a, doslovnog citata i image_path-a
protiv iste raw jedinice.

## 2026-09-13 — B18 ingest (complete)

Ingest B18: validator fail=0 warn=0.

## 2026-09-13 — Fraser chart-header timeframe corrections

Vizuelnom proverom lokalnih slika i stabilnog opt-in OCR dokaza ispravljeni su
timeframe metadata i povezani `Kontekst` tekstovi za šest extract-a: IBB, AAPL,
PII, MU i WTIC sa `weekly` na `daily`, a DIS sa `monthly` na `weekly`. Kod DIS-a
StockCharts header `DIS (Weekly)` utvrđuje barsku granularnost iako autorska
anotacija i raw pasus isti višegodišnji prikaz nazivaju monthly chartom.
By-event, by-structure i master index pointeri ne ponavljaju timeframe, pa nisu
menjani. Broj extract-a i batch ledger ostali su nepromenjeni.

## 2026-09-13 — B19 (Fraser, LC_ALL=C pozicije 41–60)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2016-03-judging-power-waves.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2016-07-point-and-figure-pie-in-the-sky.md`:
55 validnih chart–interpretation parova, 2 odbačena dokumenta i 0 paywalled
jedinica. Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C
poziciji 41; ledger je završen na poziciji 60. Sledeća Fraser resume tačka je
pozicija 61, `raw/bruce_fraser/posts/articles-wyckoff-2016-07-stupid-chart-tricks-.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz
proveru lokalne slike protiv istog raw posta i Fraser image manifesta.
Završni misattribution check obuhvata poslednja 3 nova extract-a (`$INDU`
Accumulation/BUEC P&F, Reaccumulation P&F i UTAD scenario) proverom source
locator-a, doslovnog citata i image_path-a protiv iste raw jedinice.

## 2026-09-13 — B19 ingest (complete)

Ingest B19: validator fail=0 warn=0.

## 2026-09-13 — B19 GLD timeframe correction

Vizuelnom proverom lokalnog StockCharts headera ispravljen je timeframe GLD
extract-a `fraser_p059_img02_sign-of-strength_gld` sa `daily` na `weekly`, uz
usklađivanje njegovog `Kontekst` teksta. Taksonomski pointeri nisu menjani.

## 2026-09-13 — B20 (Fraser, LC_ALL=C pozicije 61–80)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2016-07-stupid-chart-tricks-.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2017-01-enjoying-the-short-term-view.md`:
57 validnih chart–interpretation parova, 1 odbačen dokument i 0 paywalled
jedinica. Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C
poziciji 61; ledger je završen na poziciji 80. Sledeća Fraser resume tačka je
pozicija 81, `raw/bruce_fraser/posts/articles-wyckoff-2017-01-going-for-the-gold.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz
proveru lokalne slike protiv istog raw posta i Fraser image manifesta.
Završni misattribution check obuhvata poslednja 3 nova extract-a (`$NDX`
daily Distribution, `$SPX` 60-minute SOW i `$SPX` 30-minute P&F Distribution)
proverom source locator-a, doslovnog citata i image_path-a protiv iste raw
jedinice i vizuelnim poređenjem lokalnih chartova.

## 2026-09-13 — B21 (Fraser, LC_ALL=C pozicije 81–100)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2017-01-going-for-the-gold.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2017-06-another-stupid-chart-trick.md`:
48 validnih chart–interpretation parova, 1 odbačen dokument i 0 paywalled
jedinica. Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C
poziciji 81; ledger je završen na poziciji 100. Sledeća Fraser resume tačka je
pozicija 101, `raw/bruce_fraser/posts/articles-wyckoff-2017-06-more-pie-bigger-sky.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz
proveru lokalne slike protiv istog raw posta i Fraser image manifesta.
Završni misattribution check obuhvata poslednja 3 nova extract-a ($SML daily
UTAD/Distribution i dva završna MU prikaza) proverom
source locator-a, doslovnog citata i image_path-a protiv iste raw jedinice i
vizuelnim poređenjem lokalnih chartova.

## 2026-09-13 — B21 ingest (complete)

Ingest B21: validator fail=0 warn=0.

## 2026-09-13 — B22 (Fraser, LC_ALL=C pozicije 101–120)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2017-06-more-pie-bigger-sky.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2017-11-crude-oil-runs-with-the-bulls.md`:
36 validnih chart–interpretation parova, 3 odbačena dokumenta i 0 paywalled
jedinica. Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C
poziciji 101; ledger je završen na poziciji 120. Sledeća Fraser resume tačka je
pozicija 121, `raw/bruce_fraser/posts/articles-wyckoff-2017-11-natural-gas-follows-crude.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz
proveru lokalne slike protiv istog raw posta i Fraser image manifesta.
Završni misattribution check obuhvatio je poslednja 3 nova extract-a (weekly
$WTIC Reaccumulation i dva završna $WTIC PnF prikaza) proverom source locator-a,
doslovnog citata i image_path-a protiv iste raw jedinice i vizuelnim poređenjem
lokalnih chartova.

## 2026-09-13 — B25 ingest (complete)

Ingest B25: validator fail=0 warn=0.

## 2026-09-13 — B26 (Fraser, LC_ALL=C pozicije 181–200)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2019-04-yields-flatten.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2020-05-work-area-ahead-901.md`: 40 validnih
chart–interpretation parova, 4 odbačena dokumenta i 0 paywalled jedinica. Jedan
GOLD daily kandidat dodatno je odbačen jer njegov raw evidence blok obuhvata i
monthly summary, pa jednoznačna timeframe atribucija nije prošla lokalni validator.
Resume je počeo posle prethodne `last_reviewed` tačke na poziciji 180 i ledger je
završen na poziciji 200; sledeća Fraser resume tačka je pozicija 201,
`raw/bruce_fraser/posts/articles-wyckoff-2020-06-power-charting-tv-special-gues-242.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz proveru
lokalne slike protiv istog raw posta i Fraser image manifesta. Završni
misattribution check obuhvata poslednja 3 nova extract-a (WORK daily, SMAR weekly i
TEAM weekly) proverom source locator-a, doslovnog citata i image_path-a protiv iste
raw jedinice i vizuelnim poređenjem lokalnih chartova.

## 2026-09-13 — B25 Fraser chart-header OCR correction

Svež Apple Vision OCR v6 dokaz i vizuelna provera lokalne slike ispravili su
timeframe metadata i povezani `Kontekst` tekst za EFA Selling Climax extract sa
`weekly` na `daily`. Preostala dva opt-in OCR nalaza su parser false positive-i,
pa extract podaci nisu menjani: dvostruki SMH/NDX panel je skraćen na prvi
header `SMH`, dok je na S&P 500 PnF chartu Wyckoff oznaka `BCLX` pogrešno
protumačena kao asset umesto jasno ispisanog `S&P 500`/`$SPX`. Batch ledger i
broj extract-a nisu menjani.

## 2026-09-13 — B22 ingest (complete)

Ingest B22: validator fail=0 warn=0.

## 2026-09-13 — B22 Fraser chart-header OCR corrections

Svež Apple Vision OCR dokaz i vizuelna provera lokalnih slika ispravili su
timeframe metadata i povezani `Kontekst` tekst za dva B22 extract-a: IWM sa
`weekly` na `daily`, a GE sa `daily` na `weekly`. Composite TRAN/INDU chart je
zadržao tačan `asset: TRAN and INDU`; parser v3 trenutno vidi samo prvi
eksplicitni `$TRAN` header i zato taj slučaj ostaje klasifikovan kao parser
false positive, bez izmene extract-a. Batch ledger i broj extract-a nisu menjani.

## 2026-09-13 — B23 (Fraser, LC_ALL=C pozicije 121–140)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2017-11-natural-gas-follows-crude.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2018-04-jumping-the-creek-a-review.md`:
50 validnih chart–interpretation parova, 1 odbačen dokument i 0 paywalled jedinica.
Resume je počeo posle prethodne `last_reviewed` tačke na LC_ALL=C poziciji 121;
ledger je završen na poziciji 140. Sledeća Fraser resume tačka je pozicija 141,
`raw/bruce_fraser/posts/articles-wyckoff-2018-04-sp-500-zooming-in.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz
proveru lokalne slike protiv istog raw posta i Fraser image manifesta. Završni
misattribution check obuhvatio je poslednja 3 nova extract-a (WTIC, PII i JWN
Jump Across the Creek prikazi) proverom source locator-a, doslovnog citata i
image_path-a protiv iste raw jedinice i vizuelnim poređenjem lokalnih chartova.

## 2026-09-13 — B23 ingest (complete)

Ingest B23: validator fail=0 warn=0.

## 2026-09-13 — B23 Fraser chart-header OCR correction

Svež Apple Vision OCR dokaz i vizuelna provera lokalne slike ispravili su
timeframe metadata i povezani `Kontekst` tekst za TGT 2011–2012 chart sa
`weekly` na `daily`. Preostala tri opt-in OCR nalaza su parser false positive-i,
pa extract podaci nisu menjani: TGT PnF header je pogrešno protumačio naslov
`Two Way Markets` kao asset `V`; Gold ticker je OCR-ovan kao `GQILD`; a PII je
skraćen na `P` uprkos punom `PII` u chart header-u. Batch ledger i broj
extract-a nisu menjani.

- 2026-09-13 — B23 Sol-high semantic checkpoint correction: `fraser_p123_img02_automatic-reaction_smh-pnf.md` timeframe corrected from `daily` to canonical `60min`, and locating context updated from “Daily” to “Sixty-minute”; citation, image, taxonomy, and pointers unchanged.

## 2026-09-13 — B24 (Fraser, LC_ALL=C pozicije 141–160)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2018-04-sp-500-zooming-in.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2018-09-defangd.md`: 41 validan
chart–interpretation par, 1 odbačen dokument i 0 paywalled jedinica. Resume je
počeo posle prethodne `last_reviewed` tačke na LC_ALL=C poziciji 141; ledger je
završen na poziciji 160. Sledeća Fraser resume tačka je pozicija 161,
`raw/bruce_fraser/posts/articles-wyckoff-2018-09-semi-tough.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz proveru
lokalne slike protiv istog raw posta i Fraser image manifesta. Završni
misattribution check obuhvatio je poslednja 3 nova extract-a (WTIC historical PnF,
WTIC 2018 PnF i FDN Hinge) proverom source locator-a, doslovnog citata i
image_path-a protiv iste raw jedinice i vizuelnim poređenjem lokalnih chartova.

## 2026-09-13 — B24 ingest (complete)

Ingest B24: validator fail=0 warn=0.

## 2026-09-13 — B25 (Fraser, LC_ALL=C pozicije 161–180)

Pregledano je tačno 20 dodeljenih raw jedinica, od
`raw/bruce_fraser/posts/articles-wyckoff-2018-09-semi-tough.md` do
`raw/bruce_fraser/posts/articles-wyckoff-2019-04-wynn-win.md`: 49 validnih
chart–interpretation parova, 0 odbačenih dokumenata i 0 paywalled jedinica.
Četiri content charta odbačena su kao concept/trend ili correlation prikazi bez
prirodnog mapiranja na postojeću taksonomiju, ali su njihovi postovi dali druge
validne parove. Resume je počeo posle prethodne `last_reviewed` tačke na poziciji
160 i ledger je završen na poziciji 180; sledeća Fraser resume tačka je pozicija
181, `raw/bruce_fraser/posts/articles-wyckoff-2019-04-yields-flatten.md`.

Citation verification drill primenjen je neposredno pre svakog citata, uz proveru
lokalne slike protiv istog raw posta i Fraser image manifesta. Završni
misattribution check obuhvata poslednja 3 nova extract-a proverom source locator-a,
doslovnog citata i image_path-a protiv iste raw jedinice, uz vizuelnu proveru
lokalnih chartova.

## 2026-09-13 — B25 ingest (complete)

Ingest B25: validator fail=0 warn=0.

## 2026-09-13 — B26 ingest (complete)

Ingest B26: validator fail=0 warn=0.

## 2026-09-13 — B26 Fraser chart-header OCR corrections

Svež Apple Vision OCR parser v7 dokaz i vizuelna provera lokalnih slika
ispravili su asset metadata i povezani `Kontekst` tekst za dva B26 extract-a:
p188 petominutni P&F i šezdesetominutni chart sa `INDU` na `SPX`. Oba
StockCharts headera eksplicitno navode `$SPX`, dok raw uvodni pasus opisuje
prethodni `$INDU` chart i ne nadjačava sliku. Treći opt-in OCR nalaz je parser
false positive: zajednički `$UST20Y`/`$SPX` chart je skraćen na gornji
`$UST20Y` header, pa ispravan composite `asset: $SPX / $UST20Y` nije menjan.
Batch ledger i broj extract-a nisu menjani.

## 2026-09-13 — B27 Fraser sweep (complete)

Pregledan je tačan LC_ALL=C scope pozicija 201–220, od
`raw/bruce_fraser/posts/articles-wyckoff-2020-06-power-charting-tv-special-gues-242.md`
do `raw/bruce_fraser/posts/articles-wyckoff-2022-05-is-the-trend-about-to-bend-736.md`.
Napravljena su 33 validna chart–interpretation extract-a iz 20 validnih dokumenata;
0 dokumenata je odbačeno i 0 je paywalled. Resume je pomeren sa pozicije 201 na
poziciju 221, `raw/bruce_fraser/posts/articles-wyckoff-2022-08-a-wyckoff-cause-is-forming-wha-60.md`.
Citation verification drill i misattribution check primenjeni su na
svaki citat uz njegovu neposrednu sliku; završna ponovna provera poslednja tri
extract-a obuhvatila je source locator, doslovni citat i manifestom potvrđen lokalni
`image_path`.

## 2026-09-13 — B27 ingest (complete)

Ingest B27: validator fail=0 warn=0.

## 2026-09-13 — B28 Fraser sweep (complete)

Pregledan je tačan LC_ALL=C scope pozicija 221–240, od
`raw/bruce_fraser/posts/articles-wyckoff-2022-08-a-wyckoff-cause-is-forming-wha-60.md`
do `raw/bruce_fraser/posts/articles-wyckoff-2024-10-secular-shenanigans-676.md`.
Napravljeno je 25 validnih chart–interpretation extract-a iz 14 validnih dokumenata;
6 dokumenata je odbačeno i 0 je paywalled. Resume je počeo posle prethodne
`last_reviewed` tačke na poziciji 220 i pomeren je na poziciju 241,
`raw/bruce_fraser/posts/articles-wyckoff-2024-12-swing-trading-with-point-figur-511.md`.
Citation verification drill primenjen je neposredno pre svakog citata, uz proveru
lokalne slike protiv istog raw posta i Fraser image manifesta. Završni
misattribution check obuhvatio je poslednja 3 nova extract-a proverom source
locator-a, doslovnog citata i `image_path`-a protiv iste raw jedinice.

## 2026-09-13 — B28 ingest (complete)

Ingest B28: validator fail=0 warn=0.

## 2026-09-13 — B29 Fraser sweep (complete)

Pregledan je tačan LC_ALL=C scope pozicija 241–243, od
`raw/bruce_fraser/posts/articles-wyckoff-2024-12-swing-trading-with-point-figur-511.md`
do `raw/bruce_fraser/posts/has-the-bull-run-its-course.md`. Napravljena su 3
validna chart–interpretation extract-a iz 1 validnog dokumenta; 2 dokumenta su
odbačena jer nemaju proverljivu Markdown sliku ni manifest mapiranje, a 0 je
paywalled. Resume je počeo posle prethodne `last_reviewed` tačke na poziciji 240
i stigao do kanonskog kraja Fraser spiska na poziciji 243, bez naredne resume
tačke. Citation verification drill primenjen je pre svakog citata, a završni
misattribution check ponovo je proverio sva 3 nova extract-a prema istom raw
postu i lokalnim slikama iz Fraser manifesta.

## 2026-09-13 — B29 ingest (complete)

Ingest B29: validator fail=0 warn=0. Kapija semantic-lint (završni fraser batch + korpus DoD) sprovedena.

## 2026-09-13 — B17 rejected-ledger correction

Ispravljen je izvedeni B17 rejected zbir: u scope-u od 20 dokumenata, 14
dokumenata ima ukupno 49 validnih extract-a, a 6 dokumenata nema nijedan
validan extract. P010 AAPL dokument i posle uklanjanja jednog nevalidnog
Stride/Buying Climax extract-a zadržava 3 validna extract-a, pa taj uklonjeni
extract smanjuje samo `valid` zbir i ne pretvara dokument u `rejected`.
Fraser `rejected` zbir je zato ispravljen sa 32 na 31; `reviewed: 243` i
`valid: 530` ostaju nepromenjeni.

## 2026-09-13 — JPM Phase D semantic adjudication

Nezavisni Sol-high pregled i direktna vizuelna provera slike
`raw/bruce_fraser/images/1528050661429295108804.png` potvrdili su da
`fraser_p148_img02_last-point-of-supply_jpm` ostaje `phase: D`. LPSY oznaka
potkrepljuje događaj, dok eksplicitna `Phase D` oznaka na desnom, aktuelnom delu
istog grafikona i susedni pasus o prelazu iz Distribution u Markdown
potkrepljuju fazu trenutnog stanja. Kontekst kartice je razjašnjen bez promene
frontmatter klasifikacije, citata, pointera ili ledgera.

## 2026-09-13 — P078 broadening-indexes metadata correction

Završna Fraser semantic-lint kapija i direktna vizuelna provera slike
`raw/bruce_fraser/images/1481399890507670306013.png` dokazale su da
`fraser_p078_img03_distribution_broadening-indexes` nije metadata-unknown:
gornji panel je eksplicitno `$COMPQ (Daily)`, donji panel je `$SPX`, a oba dele
istu dnevnu osu. `asset` je ispravljen na `$COMPQ / $SPX`, `timeframe` na
`daily`, a locating kontekst je usklađen. Taksonomija, citat, slika, pointeri i
ledger nisu menjani.

## 2026-09-13 — Fraser phase-evidence correction

Nezavisni Sol-high pregled vizuelno je proverio svih 37 kartica izdvojenih
završnom B29 semantičkom kapijom. U 36 kartica bez eksplicitne fazne oznake
`phase` je ispravljen na `unknown`; jedino je
`fraser_p130_img04_upthrust-after-distribution_aapl-pnf` zadržao `phase: C`, jer
raw izvor izričito povezuje taj AAPL UTAD sa fazom C. Ostala polja, pointeri i
ledger nisu menjani.
