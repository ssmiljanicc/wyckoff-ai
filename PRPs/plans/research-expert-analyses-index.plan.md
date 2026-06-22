# Feature: `research/expert-analyses/` tematski index ekspertskog korpusa

## Izmene od pregled-plana

Re-pakovano nakon `/pregled-plana` (izveštaj: `.claude/pregled-plana/research-expert-analyses-index.md`).
Utkane PLAN DEFECT popravke:

1. **Coverage ledger (VAŽNO)** — uveden `research/expert-analyses/_progress.md` per-source ledger;
   `Ukupno pregledano` se izvodi iz njega (ne iz broja extract-a), jer brojanje extract-a ne razlikuje
   „odbačeno" od „nepregledano". Novi Zadatak 0 + dopuna Zadataka 3/4/5 + Acceptance/Validation za
   punu pokrivenost (reviewed == 248/243/46).
2. **Stroga provera obaveznih polja (VAŽNO)** — Validation #3 prepisan: sidri na frontmatter ključeve
   (`^kljuc:`) i proverava **svih** 10 obaveznih polja (uz `page|post_url` either/or), umesto labavog
   substring grep-a nad 4 polja.
3. **Validacija `image_path` (VAŽNO)** — novi Validation korak: svaki ne-`(remote)`/ne-prazan
   `image_path` mora da pokazuje na postojeći fajl (`test -f`).
4. **Paywalled WIKI_GAP rutiranje (SITNO)** — paywalled crypto WIKI_GAP ide u `_gaps.md`, ne u
   event-specifičan `by-event` fajl (event je nepoznat jer sadržaj nije skrejpovan).

Usputne korekcije brojeva (ne defekt, ali tačnije): crypto lokalne slike = **190**, paywalled = **10**
(`"status":"paywalled"`), `analyst_prompt` na `orchestrator.py:212` (NO-tools komentar `:213`).

## Izmene od [#93] (batch izvršavanje)

Per presudi #93 (PROCEED, Pristup C): Zadatak 3 (book) i Zadatak 5 (Fraser) razbijeni u grube pod-zadatke
(3.1–3.3 / 5.1–5.3) — resume jedinice za `prp-implement` — sa **serijama ≤20 dokumenata** i **stop-signalom
na ≥50% konteksta** unutar svake (Batch protokol, Notes). Crypto (Zadatak 4) ostaje jedan zadatak ali
poštuje isti ≤20/50% protokol. Serija `page_001–020` vezana za [#92] kao deljeni merni uzorak (model
benchmark / potrošnja tokena). Sve ostalo (Zadaci 0/1/2/6/7/8, Validation, Acceptance) nepromenjeno.

## Summary

Proći kroz sva tri immutable raw izvora (`raw/book/pages/`, `raw/bruce_fraser/posts/`,
`raw/crypto_archive/posts/`), identifikovati **ekspertske analize grafikona** (ne puke
definicije ni prazne schematike), izvući ih u pretraživu `research/expert-analyses/`
strukturu sa pointer-plus-citat extract fajlovima, i **izmeriti stvarni korpus** kroz
corpus-count tabelu. Ovo je Korak 0 za [#89](https://github.com/ssmiljanicc/wyckoff-ai/issues/89):
deblokira #86 (batch-02 kuracija) i hrani #84 (ML vs few-shot/RAG odluku).

Ovo je **kuraciona/research operacija nad postojećim podacima** — ne piše se nikakav
runtime kod, nijedan modul, nijedan test pod `tests/`. Output su markdown artefakti pod
novim `research/` korenom.

## User Story

```text
Kao istraživač koji odlučuje između ML i few-shot/RAG pristupa (#84)
želim pretraživ, prebrojan index ekspertskih Wyckoff analiza grafikona iz sva tri izvora
da bih znao tačnu veličinu i sastav korpusa pre nego što biram arhitekturu (ML feasibility, #91; KB ingest, #90).
```

## Problem Statement

Trenutno su ekspertske analize raštrkane kroz 537 raw dokumenata (248 book stranica,
243 Fraser posta, 46 crypto izveštaja) bez ikakve klasifikacije po Wyckoff eventu,
strukturi ili tipu (forward/retrospective/schematic). Niko ne zna **koliko** validnih
par(ova grafikon + ekspertska interpretacija) zapravo postoji. Bez tog broja, odluke
#84/#90/#91 se donose naslepo. Takođe ne postoji `research/` koren — folder treba kreirati
od nule, i to **strukturalno van eval putanje** da ne kontaminira blind backtest.

## Solution Statement

Kreirati `research/expert-analyses/` stablo (index + `by-event/` + `by-structure/` +
`extracts/` + `_progress.md` ledger + `_gaps.md`), definisati jedinstveni extract template
(pointer + verbatim citat, **nikad** kopija celog dokumenta), proći redom kroz tri izvora po
prioritetu (book → crypto → Fraser), klasifikovati svaki kandidat-par prema validacionim
kriterijumima iz #89, napisati po jedan extract fajl sa svim obaveznim poljima i
`status: candidate`, **uz beleženje pune pokrivenosti u `_progress.md`** (svaki dokument
zaveden kao pregledan, sa ishodom validan/odbačen/paywalled), povezati ih iz `by-event/` i
`by-structure/` index stranica, i popuniti corpus-count tabelu sa breakdown-om po
eventu/strukturi za svaki izvor.

Taksonomija `by-event/` i `by-structure/` fajlova **preslikava postojeći wiki vokabular**
(`knowledge/wiki/events/` — 23 fajla; `knowledge/wiki/structures/` — 5 fajlova), da bi
index bio konzistentan sa već uspostavljenom domenskom shemom (CLAUDE.md §3).

## Metadata

| Polje | Vrednost |
|---|---|
| Feature type | `NEW_CAPABILITY` (nova research artefakt struktura) |
| Complexity | `HIGH` — obim (537 dokumenata), ručna domenska klasifikacija, tri heterogena formata izvora |
| Affected systems | Novi `research/` koren; čita (read-only) `raw/`, `knowledge/wiki/events|structures/`, `raw/book/image_manifest.json`, `raw/crypto_archive/manifest.json` |
| Izvor inputa | GitHub issue #89 (telo; **bez komentara** — nijedan ne postoji) |
| Milestone | M7: Analysis Evaluation & Model Benchmarking (Faza 4) |
| Model preporuka | Opus (label `model:opus` na issue-u — domenska sinteza/nijansa) |
| Implementacija | Kuraciona — nema koda, nema PR-a obaveznog po CLAUDE.md §0.2 (čista nova dokumentacija/data pod `research/`, ne menja ponašanje sistema) |

## UX Design

Ovo je **operator/research workflow**, ne ekran. Before/after toka istraživača:

```
PRE:
  istraživač → "koliko spring primera imamo?" → grep -ri spring raw/  → 100+ pogodaka,
  pomešani: definicije, schematike, prave analize, paywalled stub-ovi → ručno čitanje
  537 fajlova → nema brojeva → #84 blokiran

POSLE:
  istraživač → research/expert-analyses/index.md → by-event/spring.md
            → lista pointera na N validnih primera (source + page/url + type + status)
            → extracts/<id>.md → verbatim ekspertov pasus + image_path
  corpus-count tabela → tačni brojevi po izvoru × eventu × tipu (sa potvrđenom punom
            pokrivenošću preko _progress.md) → #84 deblokiran
```

Tok podataka (read-only iz raw, write samo u research/):

```
raw/book/pages/*.md ─────────┐
raw/book/image_manifest.json ┤
raw/crypto_archive/posts/*.md ┤── sweep + klasifikacija ──► research/expert-analyses/
raw/crypto_archive/manifest.json┤                              ├─ extracts/<id>.md  (pointer+citat)
raw/bruce_fraser/posts/*.md ──┘                              ├─ by-event/<event>.md
knowledge/wiki/events|structures/ ── taksonomija ───────────►├─ by-structure/<struct>.md
                                                              ├─ _progress.md (coverage ledger)
                                                              ├─ _gaps.md (paywalled WIKI_GAP)
                                                              └─ index.md (+ corpus count)
```

| Lokacija | Pre | Posle | Vrednost za korisnika |
|---|---|---|---|
| `research/` koren | ne postoji | stablo sa indeksom i extract-ima | pretraživ korpus |
| corpus count | nepoznat | tabela po izvoru/eventu/tipu, izvedena iz potvrđene pokrivenosti | #84 odluka na osnovu brojeva |
| eval putanja | n/a | `research/` strukturalno van nje | blind backtest nezagađen |

## Mandatory Reading

Implementacioni agent MORA pročitati pre rada:

- `/Users/ssmiljanic/projekti/wyckoff-ai/CLAUDE.md` — §0.1 (srpski default), §2/§3 (wiki taksonomija koju `by-event`/`by-structure` preslikavaju), §5 (provenance/citat konvencije), §7 (WIKI_GAP za paywalled)
- Telo issue-a #89 — autoritativan spec outputa, validacionih kriterijuma i acceptance liste
- `raw/INVENTORY.md` — stanje izvora, image gap-ovi, paywall napomena
- `raw/book/image_manifest.json` — mapiranje stranica→figura (119 lokalnih book slika)
- `raw/crypto_archive/manifest.json` — status crypto postova (10 sa `"status":"paywalled"`)
- `scripts/eval/orchestrator.py` `analyst_prompt` (`:212`; NO-tools komentar `:213`, candles-only) — potvrda eval izolacije (analyst radi sa NO tools, samo embedded candles)

## Patterns to Mirror

Stvarni dokazi iz codebase-a (file:line + snippet):

| Category | File:Lines | Pattern | Snippet |
|---|---|---|---|
| FRONTMATTER (provenance) | `CLAUDE.md:§5` | YAML `sources:` sa `path` + `note`; `primary_source` default `book` | `sources:\n  - path: raw/book/pages/page_142.md\n    note: "primary definition"` |
| TAKSONOMIJA (events) | `knowledge/wiki/events/` (23 fajla) | kebab-case po eventu | `spring.md`, `upthrust.md`, `secondary-test.md`, `selling-climax.md`, `automatic-rally.md` |
| TAKSONOMIJA (structures) | `knowledge/wiki/structures/` (5 fajlova) | kebab-case po strukturi | `accumulation.md`, `distribution.md`, `reaccumulation.md`, `redistribution.md`, `trading-range.md` |
| BOOK IMAGE MAP | `raw/book/image_manifest.json:1-14` | niz objekata `image_path`+`page_number`+`figure_index` | `{"image_path": "raw/book/images/page_001_fig_1.png", "page_number": 1, "figure_index": 1}` |
| BOOK PAGE IMG REF | `raw/book/pages/page_001.md:1` | inline markdown image, relativna putanja | `![](images/page_001_fig_1.png)` |
| FRASER HEADER | `raw/bruce_fraser/posts/*.md:1-6` | `# Title` + `URL:` + `Date:` + `Author:` + **remote** img (`../images/<uuid>.jpg`, lokalno NE postoji) | `URL: https://articles.stockcharts.com/...`\n`![](../images/ab6dc9f2-...jpg)` |
| CRYPTO HEADER | `raw/crypto_archive/posts/*.md:1-9` | `# Wyckoff Crypto Report N` + `URL:` + `Date:` + `Author:` + **lokalni** img (`../images/<report>/<n>.png`) | `![](../images/wyckoff-crypto-report-53/01-...png)` |
| WIKI_GAP | `CLAUDE.md:§7` | marker za paywalled/nedostupan izvor | `WIKI_GAP — raw/.../vol-52.md je paywalled (status: paywalled u manifest)` |

## Files to Change

Svi su **novi fajlovi pod `research/`** (nijedan postojeći se ne menja; `raw/` je immutable):

| Putanja | Akcija | Sadržaj |
|---|---|---|
| `research/expert-analyses/index.md` | create | master pregled + corpus-count tabela + navigacija |
| `research/expert-analyses/EXTRACT_TEMPLATE.md` | create | kanonska forma extract fajla (obavezna polja) |
| `research/expert-analyses/_progress.md` | create | per-source coverage ledger (pregledano/ishod) |
| `research/expert-analyses/_gaps.md` | create | paywalled / nedostupni izvori (WIKI_GAP) |
| `research/expert-analyses/by-event/<event>.md` | create (≥3) | lista pointera po eventu (taksonomija = wiki events) |
| `research/expert-analyses/by-structure/<structure>.md` | create | lista pointera po strukturi (taksonomija = wiki structures) |
| `research/expert-analyses/extracts/<id>.md` | create (N) | pointer + verbatim citat po validnom paru |

Naming konvencija za extract id (per primeri u issue-u): `<source>_<lokator>_<event>_<asset>.md`,
npr. `book_p042_spring_example.md`, `crypto_vol53_spring_BTC.md`, `fraser_2024-02_swing_SIG.md`.

## NOT Building

Eksplicitno van obima (per issue #89 "Šta nije u obimu"):

- OHLCV rekonstrukcija za Fraser/book primere → #91
- ML label feasibility analiza → #91
- KB ingestion arhitektura (A/B/C odluka) → odloženo dok corpus count-ovi ne budu poznati (#90)
- Batch-02 evaluaciona kuracija → #86 (paralelno, kad `research/` postoji)
- Bilo kakav runtime kod, MCP, test, izmena `raw/`, izmena `knowledge/wiki/`, izmena eval pipeline-a
- Download Fraser slika (855 remote URL-ova) — van obima; Fraser primeri se beleže sa `image_path: (remote: <url>)` ili `bez slike`
- Validacija/`eval-used` promocija extract-a — svi ostaju `status: candidate` u ovom koraku

## Step-by-Step Tasks

> **Stanje izvršavanja:** Zadaci 0–2 (skela) su DONE (skela `research/expert-analyses/` postoji, commit `dce2f32`). `prp-implement` nastavlja od **Zadatka 3** (sweep).

### Zadatak 0 — Coverage ledger skela (`_progress.md`)

- **Action:** create `_progress.md` sa per-source tabelom pokrivenosti
- **Files:** `research/expert-analyses/_progress.md`
- **Instruction:** napravi tabelu sa po jednim redom po izvoru (`book`, `crypto`, `fraser`) i kolonama:
  `total_files` (248/243/46), `reviewed`, `valid`, `rejected`, `paywalled`, `last_reviewed` (poslednji
  pregledani fajl, radi resume-a). Inicijalno `reviewed=0`. Sweep zadaci (3/4/5) ažuriraju ovaj fajl
  posle svake serije. Svrha: brojanje extract-a NE razlikuje „odbačeno" od „nepregledano" — ledger to
  čini eksplicitnim i omogućava tačan `Ukupno pregledano` i pouzdan resume.
- **Pattern:** obična markdown tabela
- **Gotchas:** `_progress.md` je izvor istine za pokrivenost; corpus tabela u `index.md` se izvodi iz njega
- **Validation:** `test -f research/expert-analyses/_progress.md && grep -qE 'book|crypto|fraser' research/expert-analyses/_progress.md`

### Zadatak 1 — Skela `research/` stabla i template

- **Action:** create direktorijume i `EXTRACT_TEMPLATE.md` (+ `_gaps.md`)
- **Files:** `research/expert-analyses/{by-event,by-structure,extracts}/` + `EXTRACT_TEMPLATE.md` + `_gaps.md`
- **Instruction:** `mkdir -p research/expert-analyses/{by-event,by-structure,extracts}`. Napiši
  `EXTRACT_TEMPLATE.md` sa YAML frontmatter koji sadrži SVA obavezna polja iz #89: `source`,
  `page`/`post_url` (bar jedno), `asset`, `timeframe`, `wyckoff_event`, `structure`, `phase`,
  `image_path`, `type` (`forward`|`retrospective`|`schematic`), `status`
  (`candidate`|`validated`|`eval-used`), + telo za **verbatim pasus**. Frontmatter stil preslikati iz
  `CLAUDE.md:§5`. Kreiraj prazan `_gaps.md` sa H1 „## WIKI_GAP / paywalled i nedostupni izvori".
- **Pattern:** `CLAUDE.md:§5` frontmatter; `raw/book/image_manifest.json` za `image_path` oblik
- **Gotchas:** ne dodavati `research/` u eval putanju; folder mora ostati read-target-only za eval (vidi Risks)
- **Validation:** `test -d research/expert-analyses/extracts && test -f research/expert-analyses/EXTRACT_TEMPLATE.md && test -f research/expert-analyses/_gaps.md`

### Zadatak 2 — Generiši `by-event/` i `by-structure/` skelete iz wiki taksonomije

- **Action:** create prazne (sa headerom) index stranice po eventu/strukturi
- **Files:** `research/expert-analyses/by-event/*.md`, `research/expert-analyses/by-structure/*.md`
- **Instruction:** za svaki fajl u `knowledge/wiki/events/` i `knowledge/wiki/structures/` kreiraj
  odgovarajući `by-event/<isto-ime>.md` / `by-structure/<isto-ime>.md` sa H1 naslovom i praznom listom
  "## Primeri" koja će se puniti pointerima. Time je taksonomija garantovano usklađena sa CLAUDE.md §3.
- **Pattern:** `knowledge/wiki/events/` (23 imena), `knowledge/wiki/structures/` (5 imena)
- **Gotchas:** zadrži identičan kebab-case; ne izmišljaj nove evente
- **Validation:** `test $(ls research/expert-analyses/by-event/*.md | wc -l) -ge 3` i potvrdi da imena postoje u `knowledge/wiki/events/`

### Zadatak 3 — Sweep + klasifikacija: BOOK (`raw/book/pages/`, 248) — u serijama ≤20

**Izvršava se po Batch protokolu (vidi Notes):** mikro-serije **≤20 strana**, commit + `_progress.md`
update posle svake serije, **stop na ≥50% konteksta**, resume preko `_progress.md last_reviewed`.
Pod-zadaci 3.1/3.2/3.3 su **grube granice koje `prp-implement` nativno nastavlja** („first incomplete
task"); 20-strane serije unutar njih su zaštita od context cut-a.

**Zajednički kriterijumi (važe za 3.1–3.3):** validan par (kriterijumi #89) = postoji grafikon/jasna
referenca (proveri preko `raw/book/image_manifest.json` da li stranica ima figuru) + ekspert daje
**konkretnu Wyckoff interpretaciju** (ne samo definiciju ni goli schematic) + identifikabilan kontekst.
Za svaki par napiši extract sa **verbatim** pasusom (citat, ne parafraza), `image_path` iz manifesta ako
postoji, `type` (forward/retrospective/schematic), `status: candidate`. Schematik-only → `type:
schematic`. Drži se pointer+citat — **nikad** ne kopiraj celu stranicu. OCR artefakti (`gre ater`,
`selle rs` — INVENTORY.md): citiraj verbatim, ne „popravljaj". Posle svake serije ažuriraj `_progress.md`
red `book`. Cilj na kraju Zadatka 3: `reviewed == 248`.

- **Pattern:** `raw/book/pages/page_001.md:1` img ref; `image_manifest.json` map

#### Zadatak 3.1 — Book: page_001–page_080 (serije 001–020, 021–040, 041–060, 061–080)

- **Action:** sweep + extract + ledger, 4 serije po 20
- **Files:** `research/expert-analyses/extracts/book_*.md`, `research/expert-analyses/_progress.md`
- **Instruction:** primeni zajedničke kriterijume gore po Batch protokolu. **Serija `page_001–020` =
  deljeni merni uzorak za [#92] (model benchmark / potrošnja tokena):** ako je #92 već pokrenut, koristi
  njegov **ručni ground truth** za ovih 20 strana (samo materijalizuj extract-e + ledger, ne presuđuj
  ponovo); ako #92 nije pokrenut, ova serija JE njegov ulaz. Commit posle svake serije; stop na ≥50%
  konteksta posle tekuće serije.
- **Gotchas:** ova serija mora ostati identičan ulaz kao #92 (fair comparison) — ne menjaj redosled ni
  opseg `page_001–020`.
- **Validation:** `ls research/expert-analyses/extracts/book_*.md >/dev/null 2>&1; grep -A1 '| book' research/expert-analyses/_progress.md`

#### Zadatak 3.2 — Book: page_081–page_160 (serije po 20)

- **Action:** sweep + extract + ledger, 4 serije po 20
- **Files:** isti kao 3.1
- **Instruction:** nastavi od `_progress.md last_reviewed`; zajednički kriterijumi + Batch protokol;
  commit posle svake serije.
- **Validation:** `grep -A1 '| book' research/expert-analyses/_progress.md` (reviewed napreduje ka 160)

#### Zadatak 3.3 — Book: page_161–page_248 (serije po 20, poslednja 8)

- **Action:** sweep + extract + ledger
- **Files:** isti kao 3.1
- **Instruction:** nastavi od `_progress.md last_reviewed`; zajednički kriterijumi + Batch protokol;
  commit posle svake serije. Po završetku `reviewed == 248`.
- **Validation:** `grep -A1 '| book' research/expert-analyses/_progress.md` (reviewed == 248)

### Zadatak 4 — Sweep + klasifikacija: CRYPTO (`raw/crypto_archive/posts/`, 46)

- **Action:** identifikuj validne parove; markiraj paywalled; zavedi pokrivenost
- **Files:** `research/expert-analyses/extracts/crypto_*.md`, `research/expert-analyses/_gaps.md`, `_progress.md`
- **Instruction:** prođi kroz `raw/crypto_archive/posts/*.md`. Lokalne slike postoje (190, u
  `raw/crypto_archive/images/<report>/`) — `image_path` pokazuje na njih. Proveri
  `raw/crypto_archive/manifest.json` za `"status": "paywalled"` (**10 postova**): za paywalled, umesto
  extract-a ubaci **WIKI_GAP** napomenu (CLAUDE.md §7) u **`_gaps.md`** (NE u event-specifičan
  `by-event` fajl — event je nepoznat jer sadržaj nije skrejpovan), navedi slug + `status: paywalled`,
  i NE izmišljaj sadržaj. Ostalo isto kao Zadatak 3. **Ažuriraj `_progress.md` red `crypto`**
  (`reviewed`, `valid`, `rejected`, `paywalled`, `last_reviewed`); cilj `reviewed == 46`.
  **Batch protokol (vidi Notes):** 46 postova obradi u **serijama ≤20** (3 serije ~16), commit +
  `_progress.md` posle svake, stop na ≥50% konteksta. Crypto ostaje **jedan** zadatak (ne deli se na
  pod-zadatke — obim je mali), ali poštuje isti context-safe protokol.
- **Pattern:** `raw/crypto_archive/posts/*.md:1-9` header; `manifest.json` paywall status; `CLAUDE.md:§7` WIKI_GAP
- **Gotchas:** crypto img putanja je `../images/<report>/<n>.png` relativno — konvertuj u repo-relativnu `raw/crypto_archive/images/<report>/<n>.png` u `image_path` (Validation #5 proverava da fajl postoji).
- **Validation:** `ls research/expert-analyses/extracts/crypto_*.md >/dev/null 2>&1; grep -q 'paywalled' research/expert-analyses/_gaps.md || echo "PROVERI: nema paywalled u _gaps.md (očekivano ~10)"`

### Zadatak 5 — Sweep + klasifikacija: FRASER (`raw/bruce_fraser/posts/`, 243) — u serijama ≤20

**Izvršava se po Batch protokolu (vidi Notes):** mikro-serije **≤20 postova**, commit + `_progress.md`
posle svake, **stop na ≥50% konteksta**, resume preko `last_reviewed`. Pod-zadaci 5.1/5.2/5.3 su grube
granice koje `prp-implement` nativno nastavlja; serije ≤20 unutar njih su zaštita od context cut-a.

**Zajednički kriterijumi (važe za 5.1–5.3):** prođi kroz `raw/bruce_fraser/posts/*.md`. **Lokalne slike
NE postoje** (0 — potvrđeno; img ref su remote `../images/<uuid>.jpg`) → `image_path` postavi na
`(remote: <url iz posta>)` ili ostavi prazno. Mnogi Fraser postovi su video/edukacija (ne uvek
grafikon-analiza) → primeni kriterijum **strogo**: validan samo ako tekst nosi konkretnu Wyckoff
interpretaciju grafikona; mnogi će otpasti — očekivano. `asset`/`timeframe` često nedostaju → dozvoljeno
`unknown`. Pošto je hit-rate nizak, **ledger je jedini pouzdan dokaz da je sweep kompletan** (broj
extract-a sam ne razlikuje „odbačeno" od „nepregledano"). Posle svake serije ažuriraj `_progress.md` red
`fraser`. Cilj na kraju Zadatka 5: `reviewed == 243`.

- **Pattern:** `raw/bruce_fraser/posts/*.md:1-6` header (`URL:`/`Date:`/`Author:`)

#### Zadatak 5.1 — Fraser: posts 001–080 (serije po 20)

- **Action:** sweep + extract + ledger, 4 serije po 20
- **Files:** `research/expert-analyses/extracts/fraser_*.md`, `research/expert-analyses/_progress.md`
- **Instruction:** zajednički kriterijumi gore po Batch protokolu; commit posle svake serije; stop na ≥50%.
- **Validation:** `echo "fraser extracts: $(ls research/expert-analyses/extracts/fraser_*.md 2>/dev/null | wc -l)"; grep -A1 '| fraser' research/expert-analyses/_progress.md`

#### Zadatak 5.2 — Fraser: posts 081–160 (serije po 20)

- **Action:** sweep + extract + ledger, 4 serije po 20
- **Files:** isti kao 5.1
- **Instruction:** nastavi od `last_reviewed`; zajednički kriterijumi + Batch protokol; commit po seriji.
- **Validation:** `grep -A1 '| fraser' research/expert-analyses/_progress.md` (reviewed napreduje ka 160)

#### Zadatak 5.3 — Fraser: posts 161–243 (serije po 20, poslednja 3)

- **Action:** sweep + extract + ledger
- **Files:** isti kao 5.1
- **Instruction:** nastavi od `last_reviewed`; zajednički kriterijumi + Batch protokol; commit po seriji.
  Po završetku `reviewed == 243`.
- **Validation:** `grep -A1 '| fraser' research/expert-analyses/_progress.md` (reviewed == 243)

### Zadatak 6 — Popuni `by-event/` i `by-structure/` pointerima

- **Action:** poveži svaki extract iz `by-event`/`by-structure` stranica
- **Files:** `research/expert-analyses/by-event/*.md`, `.../by-structure/*.md`
- **Instruction:** za svaki extract dodaj red u odgovarajući `by-event/<event>.md` i
  `by-structure/<structure>.md`: link na extract + `source` + `page`/`url` + `type` + `status`. Jedan
  extract može biti listan pod više evenata ako analiza pokriva sekvencu (npr. SC→AR→ST).
- **Pattern:** Obsidian/markdown link na `../extracts/<id>.md`
- **Gotchas:** parity — svaki extract mora biti dostižan iz bar jednog `by-event` fajla
- **Validation:** za svaki `extracts/*.md` proveri da je ime referencirano bar jednom u `by-event/` (Validation #6)

### Zadatak 7 — Corpus-count tabela + `index.md`

- **Action:** prebroj i napiši master index
- **Files:** `research/expert-analyses/index.md`
- **Instruction:** popuni tabelu iz #89: redovi = tri izvora (sa ukupnim brojem fajlova 248/243/46),
  kolone = `Ukupno pregledano | Validni parovi | forward | retrospective | schematic | bez slike`.
  **`Ukupno pregledano` izvedi iz `_progress.md` `reviewed` kolone** (ne iz broja extract-a);
  `Validni parovi` mora == broj extract fajlova po izvoru (Validation #8). Dodaj breakdown po Wyckoff
  eventu/strukturi za svaki izvor. Dodaj navigaciju: linkovi na `by-event/`, `by-structure/`,
  `EXTRACT_TEMPLATE.md`, `_gaps.md`. Sve na srpskom (CLAUDE.md §0.1).
- **Pattern:** corpus-count tabela iz issue #89 tela (verbatim kolone)
- **Gotchas:** brojevi u index-u moraju odgovarati `_progress.md` (`Ukupno pregledano`) i broju fajlova u `extracts/` (`Validni parovi`) — ne sme se razilaziti
- **Validation:** `grep -c '|' research/expert-analyses/index.md`; ručna provera da `Validni parovi` zbir == `ls extracts/*.md | wc -l`

### Zadatak 8 — Konzistentnost i acceptance provera

- **Action:** finalna validacija prema #89 acceptance liste
- **Files:** sve gore
- **Instruction:** pokreni sve Validation Commands; potvrdi acceptance kriterijume iz #89 (vidi
  Acceptance Criteria), uključujući **punu pokrivenost** (`_progress.md` `reviewed` == 248/243/46);
  ispravi nedostatke.
- **Validation:** vidi Validation Commands blok

## Testing Strategy

Nema unit/integration testova — output je dokumentacija, ne kod. "Testiranje" = strukturna
i provenance validacija preko shell provera (dole) + domenski spot-check:

- **Strukturni:** svi obavezni folderi/fajlovi postoje; svaki extract ima **sva** obavezna polja (sidreno na frontmatter ključeve).
- **Pokrivenost:** `_progress.md` `reviewed` == ukupan broj fajlova po izvoru (puni sweep dokazan, ne pretpostavljen).
- **Provenance:** svaki `source` u extract-u pokazuje na **postojeći** raw fajl; svaki `image_path` (osim `(remote)`/prazno) pokazuje na postojeći fajl; nijedan extract nije kopija celog dokumenta (citat << izvor).
- **Domenski spot-check (ručno, Opus):** uzorkuj 5 extract-a (po izvoru) i potvrdi da je pasus zaista ekspertska interpretacija, ne definicija; da klasifikacija (event/type) odgovara tekstu; da je citat verbatim.
- **Eval-izolacija:** potvrdi da `research/` nije referenciran ni u jednom eval/orchestrator putanji.

## Validation Commands

```bash
cd /Users/ssmiljanic/projekti/wyckoff-ai

# 1. Struktura postoji
test -f research/expert-analyses/index.md
test -f research/expert-analyses/EXTRACT_TEMPLATE.md
test -f research/expert-analyses/_progress.md
test -f research/expert-analyses/_gaps.md
test -d research/expert-analyses/by-event
test -d research/expert-analyses/by-structure
test -d research/expert-analyses/extracts

# 2. Bar 3 by-event fajla popunjena (imaju bar jedan pointer red)
test $(grep -rl 'extracts/' research/expert-analyses/by-event/*.md | wc -l) -ge 3

# 3. Svaki extract ima SVA obavezna polja (sidreno na frontmatter ključ) + status candidate
for f in research/expert-analyses/extracts/*.md; do
  for k in source asset timeframe wyckoff_event structure phase image_path type status; do
    grep -qE "^${k}:" "$f" || echo "NEDOSTAJE $k u $f"
  done
  grep -qE '^(page|post_url):' "$f" || echo "NEDOSTAJE page|post_url u $f"
  grep -qE '^status:\s*candidate' "$f" || echo "STATUS nije candidate u $f"
done

# 4. Nijedan source pointer ne pokazuje na nepostojeći raw .md fajl
grep -rhoE 'raw/[A-Za-z0-9_./-]+\.md' research/expert-analyses/extracts/ | sort -u | while read p; do
  test -f "$p" || echo "BROKEN POINTER: $p"
done

# 5. image_path (osim remote/prazno) mora pokazivati na postojeću sliku
grep -rhE '^image_path:' research/expert-analyses/extracts/ \
  | sed -E 's/^image_path:[[:space:]]*//' \
  | grep -vE '^\(remote|^$|^bez slike' \
  | sed -E 's/^["'\'']?//; s/["'\'']?$//' \
  | while read img; do
      [ -z "$img" ] && continue
      test -f "$img" || echo "BROKEN IMAGE: $img"
    done

# 6. Nema kopije celog dokumenta — heuristika: nijedan extract > 400 reči
for f in research/expert-analyses/extracts/*.md; do
  w=$(wc -w < "$f"); test "$w" -le 400 || echo "PREVELIK (moguća kopija): $f ($w reči)"
done

# 7. Parity — svaki extract referenciran bar jednom iz by-event/
for f in research/expert-analyses/extracts/*.md; do
  b=$(basename "$f")
  grep -rq "$b" research/expert-analyses/by-event/ || echo "SIROČE (nije u by-event): $b"
done

# 8. Taksonomija usklađena sa wiki
for f in research/expert-analyses/by-event/*.md; do
  b=$(basename "$f"); test -f "knowledge/wiki/events/$b" || echo "VANSHEMA event: $b"
done

# 9. Eval izolacija — research/ se NE pojavljuje u eval kodu
! grep -rq 'research/expert-analyses' scripts/eval/ && echo "OK: research van eval putanje"

# 10. Puna pokrivenost — _progress.md reviewed == ukupan broj fajlova po izvoru (ručna kontrola)
echo "book pages:   $(ls raw/book/pages/page_*.md | wc -l)   (cilj reviewed=248)"
echo "crypto posts: $(ls raw/crypto_archive/posts/*.md | wc -l)   (cilj reviewed=46)"
echo "fraser posts: $(ls raw/bruce_fraser/posts/*.md | wc -l)   (cilj reviewed=243)"
echo "--- _progress.md ---"; cat research/expert-analyses/_progress.md

# 11. Corpus count: validni parovi == broj extract fajlova (ručna kontrola broja)
echo "extracts total: $(ls research/expert-analyses/extracts/*.md | wc -l)"
```

## Acceptance Criteria

Direktno iz issue #89 + popravke iz pregled-plana (sve moraju proći):

- [ ] `research/expert-analyses/index.md` postoji sa navigacijom po eventu i strukturi
- [ ] Bar 3 `by-event/` fajla popunjena sa pointerima na konkretne primere
- [ ] Corpus-count tabela popunjena za sva tri izvora (sa breakdown po eventu/strukturi)
- [ ] Svaki extract fajl ima **sva** obavezna polja (Validation #3 prazan izlaz) i `status: candidate`
- [ ] Svaki `image_path` (osim `(remote)`/prazno) pokazuje na postojeći fajl (Validation #5 prazan izlaz)
- [ ] **Puna pokrivenost**: `_progress.md` `reviewed` == 248 (book) / 46 (crypto) / 243 (fraser)
- [ ] Paywalled crypto postovi (~10) zavedeni WIKI_GAP u `_gaps.md` (ne u event fajl, ne izmišljen sadržaj)
- [ ] Nema kopije celog dokumenta u `extracts/` (samo pointer + verbatim pasus)

## Completion Checklist

- [ ] Zadaci 0–8 izvršeni
- [ ] Svih 11 Validation Commands prolazi bez grešaka
- [ ] 8 acceptance kriterijuma čekirano
- [ ] Domenski spot-check (5 uzoraka) urađen
- [ ] `_progress.md` potvrđuje puni sweep (reviewed == 248/46/243)
- [ ] Paywalled crypto postovi obeleženi WIKI_GAP u `_gaps.md`
- [ ] `index.md` i svi tekstualni opisi na srpskom (CLAUDE.md §0.1)
- [ ] #89 ažuriran: corpus brojevi izneti, veze ka #84/#86/#90/#91 napomenute

## Risks and Mitigations

| Rizik | Verovatnoća | Uticaj | Mitigacija |
|---|---|---|---|
| **Obim (537 dok.) prekoračuje jednu sesiju** | Visoka | Srednji | Dvoslojno: grube granice 3.1–3.3 / 5.1–5.3 (resume jedinice za `prp-implement`) + serije ≤20 strana sa stop-signalom na ≥50% konteksta i commit-om posle svake serije (Batch protokol, Notes); resume preko `_progress.md last_reviewed` (NE preko broja extract-a) |
| **Model „pukne" / degradira pred context cut** | Srednja | Srednji | Serija ≤20 + stop na ≥50% (konzervativnije od ingest §5 praga 75%); manje-ali-tačnije > više-ali-degradirano; merni dokaz iz #92 (`tokens_per_doc`) potvrđuje da li je 20 bezbedno ili treba ≤15 |
| **Nedovršen sweep izgleda kao završen** | Visoka | Visok | `_progress.md` `reviewed` mora == ukupan broj fajlova po izvoru (Validation #10 + Acceptance); ledger je izvor istine za `Ukupno pregledano` |
| **Extract bez obaveznog polja prođe validaciju** | Srednja | Srednji | Validation #3 sidri na frontmatter ključeve (`^kljuc:`) i proverava svih 10 polja + page\|post_url |
| **Pogrešno konvertovan `image_path`** | Srednja | Srednji | Validation #5 — svaki ne-remote `image_path` mora `test -f` |
| **Fraser nizak hit-rate / nema lokalnih slika** | Visoka | Nizak | Očekivano; `image_path: (remote: <url>)` ili prazno; `_progress.md` `reviewed` vs `valid` hvata odbacivanja |
| **Subjektivnost "validnog para"** | Srednja | Srednji | Striktna primena 4 #89 kriterijuma; domenski spot-check; granični slučaji `type: schematic` + napomena |
| **Kontaminacija eval putanje** | Niska | Visok | Validation #9 potvrđuje da `research/` nije u `scripts/eval/`; `_progress.md`/`_gaps.md` su čisti research artefakti |
| **OCR artefakti u book citatima** | Srednja | Nizak | Verbatim citat zadržati; ne "popravljati"; napomena uz extract |

## Notes

- **Input:** GitHub issue #89, samo telo — `comments: []`.
- **Bez PR-a (CLAUDE.md §0.2):** output je čista nova data/dokumentacija pod `research/` koja ne menja ponašanje sistema → može direktno na main bez PR-a. Ipak, zbog obima i domenske prosudbe, preporučuje se lagani sanity-check (spot-check 5 extract-a) pre commit-a.
- **Eksterni research:** nije potreban — interna kuracija nad immutable raw izvorima.
- **Redosled prioriteta sweep-a** (book → crypto → Fraser) prati gustinu signala.
- **Batch protokol (Zadaci 3.x / 4 / 5.x) — context-safe sweep:** book/crypto/Fraser se obrađuju u
  **mikro-serijama od najviše 20 dokumenata**. Posle svake serije: **commit** + update `_progress.md`
  (`reviewed`, `valid`, `rejected`, `last_reviewed`). **Stop signal: ako proceniš ≥50% iskorišćenog
  konteksta, stani posle tekuće serije** — ne guraj do kraja pod-zadatka „u jednom dahu". Resume
  isključivo preko `_progress.md last_reviewed`. Prag **50%** je konzervativniji od ingest §5 praga 75%
  jer domenska klasifikacija + verbatim citat troše kontekst brže; **20-strana plafon je tvrda granica
  čak i ispod 50%**. Manje-ali-tačnije > više-ali-degradirano (ingest §5 retrospektiva: misattribution
  raste pred context cut). Dvoslojna struktura: grube granice 3.1–3.3 / 5.1–5.3 daju `prp-implement`-u
  nativne resume jedinice („first incomplete task"), serije ≤20 unutar njih čuvaju model od gušenja.
- **Zašto baš 20 (LLM-wiki pattern):** pun wiki ingest radi ~1 izvor/sesiji jer svaki izvor dira 10–15
  wiki strana uz održavanje cross-ref grafa (težak posao). Naš zadatak je **lakši**: po dokumentu = 1
  pointer+citat extract ili 1 red u ledgeru, bez održavanja grafa. Zato >1 dok/seriji ima smisla, ali
  domenska prosudba (valid/reject/schematic) + verbatim citat i dalje traže pažnju → plafon 20 + stop na
  50% drže nas van zone degradacije.
- **Veza sa [#92] (model benchmark / potrošnja tokena):** #92 bira model za bulk sweep PRE Zadataka 3–5,
  merenjem kvaliteta + `tokens_per_doc` + `cost_per_doc` nad istim ulazom. Serija `page_001–020`
  (Zadatak 3.1) je **deljeni merni uzorak**: #92 nad njom ručno utvrđuje ground truth i meri tokene po
  produkcionoj seriji; sweep je posle reuse-uje (već validirana, bez dvostrukog rada). **Preporuka za
  #92:** usvojiti `page_001–020` (20 strana) kao benchmark prozor umesto fiksnih 30 — #92 već dozvoljava
  smanjenje, a time merni uzorak == produkciona serija. #92 token-merenje je i empirijska provera da li
  je 20-strana serija bezbedna ili treba ≤15.
- **Status svih extract-a ostaje `candidate`** — promocija u `validated`/`eval-used` je van obima (#86).
- **Deblokira:** #86; **hrani:** #84 (corpus brojevi), #91 (ML readiness), #90 (KB org).
```