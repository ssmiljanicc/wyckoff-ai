# Expert Analyses — batch raspored

## Protokol

1. Jedan red rasporeda izvršava se u jednoj novoj sesiji sa jakim modelom.
2. Preflight čita `research/expert-analyses/EXTRACT_TEMPLATE.md`, `research/expert-analyses/_progress.md`, ceo `wiki/index.md`, poslednjih 50 linija `wiki/log.md` i relevantne postojeće `by-event`/`by-structure` stranice.
3. `raw/` (repo-root nivo: `raw/book`, `raw/crypto_archive`, `raw/bruce_fraser`) je read-only tokom ingest-a.
4. Cilj je serija od ≤20 raw dokumenata po batch-u (mirror stari plan Batch protokol: serije ≤20, stop na ≥50% konteksta).
5. Stani ranije ako proceniš ≥50% konteksta; ažuriraj `_progress.md`/`wiki/log.md` i označi batch kao `partial`.
6. Nastavak dobija novu sesiju i sufiks, na primer `B01b`.
7. Na kraju proveri poslednje 2-3 `sources:` reference i lake lokalne linkove.
8. Dozvoljeni statusi su `pending | partial | complete | blocked`.
9. **Granica vlasništva (mirror skills-kb/issues-kb obrazac).** Ovaj plan (`PRPs/plans/wyckoff-onboarding-runner.plan.md`) autoriše strukturu rasporeda (koja jedinica → koji batch, kojim redom). Runner je potrošač + pisac stanja: čita ovaj fajl, bira sledeći batch i upisuje **samo polja napretka** (Status / Datum / Wiki stranice / Preostali izvori / Log) — nikad ne re-particioniše raspored. `batches.md` je jedina koordinaciona tačka strukture; validator (`scripts/validate_expert_analyses.py`) je njen **čitalac**, ne pisac.
10. **Runner (`~/projekti/poligon/scripts/ingest_runner.py`) je izvršni pisac polja napretka** — ista mašinerija kao issues-KB/skills-KB, pozvana apsolutnom putanjom (ADR 0006, poziv ne import). Upisuje **isključivo** Status / Datum / Wiki stranice / Preostali izvori / Log za tekući batch. Gate poziv za ovaj KB koristi `--validator-script scripts/validate_expert_analyses.py`.

## Šema rasporeda (kanonska, parse-kompatibilna)

Tabela „Raspored" je ugovor sa determinističkim core parserom (`parse_batches` iz `~/projekti/poligon/scripts/validate_kb_core.py`), koji mapira kolone po imenu zaglavlja (tolerantno na pomeranje). Obavezno prepoznatljive kolone:

| Uloga (validator ključ) | Zaglavlje počinje / sadrži | Sadržaj |
| --- | --- | --- |
| `batch` | počinje `Batch` | ID oblika `B\d+` (npr. `B01`) |
| `units` | počinje `Jedinic` | opis raw dokumenata u ovom batch-u (opisni tekst za crypto/fraser, tačan opseg za book) |
| `status` | tačno `Status` | jedan od `pending \| partial \| complete \| blocked` |
| `pages` | sadrži `Wiki` | broj kreiranih/izmenjenih wiki stranica (extracts + by-event/by-structure) |
| `remaining` | sadrži `Preostal` | preostali izvori (slobodan tekst) |

Dodatne kolone („Izvor", „Datum", „Log", „Posebna kapija") su slobodne — core `parse_batches` ih ignoriše, ali runner-ova sopstvena `_build_header_index` (batches.md round-trip upis + gate čitanje) prepoznaje `Datum`/`Log`/kolonu koja sadrži `kapija` supstring.

Kolona „Jedinice" NIJE mašinski-parseabilna lista identiteta za crypto/fraser (raw imena su slug, ne sekvencijalni brojevi) — resume ide isključivo preko `_progress.md last_reviewed`, ne preko ove kolone. Book koristi tačan `page_NNN-page_NNN` opseg jer su book imena sekvencijalna.

`CorpusProfile` u `scripts/validate_expert_analyses.py` namerno NE poziva `check_complete_coverage` (core provera koja bi zahtevala 1:1 bijekciju raw-jedinica ↔ content-stranica) — wyckoff model je N raw → 0..M filtriranih extract kartica, pokrivenost prati `_progress.md` ledger, ne ova tabela.

## Raspored

| Batch | Izvor | Jedinice | Posebna kapija | Status | Datum | Wiki stranice | Preostali izvori | Log |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| B01 | book | page_001-page_020 | standardna | pending |  |  | nema |  |
| B02 | book | page_021-page_040 | standardna | pending |  |  | nema |  |
| B03 | book | page_041-page_060 | standardna | pending |  |  | nema |  |
| B04 | book | page_061-page_080 | standardna | pending |  |  | nema |  |
| B05 | book | page_081-page_100 | standardna | pending |  |  | nema |  |
| B06 | book | page_101-page_120 | standardna | pending |  |  | nema |  |
| B07 | book | page_121-page_140 | standardna | pending |  |  | nema |  |
| B08 | book | page_141-page_160 | standardna | pending |  |  | nema |  |
| B09 | book | page_161-page_180 | standardna | pending |  |  | nema |  |
| B10 | book | page_181-page_200 | standardna | pending |  |  | nema |  |
| B11 | book | page_201-page_220 | standardna | pending |  |  | nema |  |
| B12 | book | page_221-page_240 | standardna | pending |  |  | nema |  |
| B13 | book | page_241-page_248 | semantic-lint (završni book batch) | pending |  |  | nema |  |
| B14 | crypto | crypto serija 1/3 (~16 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B15 | crypto | crypto serija 2/3 (~15 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B16 | crypto | crypto serija 3/3 (~15 postova, sledećih po `_progress.md last_reviewed` redosledu) | semantic-lint (završni crypto batch) | pending |  |  | nema |  |
| B17 | fraser | fraser serija 1/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B18 | fraser | fraser serija 2/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B19 | fraser | fraser serija 3/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B20 | fraser | fraser serija 4/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B21 | fraser | fraser serija 5/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B22 | fraser | fraser serija 6/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B23 | fraser | fraser serija 7/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B24 | fraser | fraser serija 8/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B25 | fraser | fraser serija 9/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B26 | fraser | fraser serija 10/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B27 | fraser | fraser serija 11/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B28 | fraser | fraser serija 12/13 (~20 postova, sledećih po `_progress.md last_reviewed` redosledu) | standardna | pending |  |  | nema |  |
| B29 | fraser | fraser serija 13/13 (~3 postova, sledećih po `_progress.md last_reviewed` redosledu) | semantic-lint (završni fraser batch + korpus DoD) | pending |  |  | nema |  |

## Operativni režim

Isti FAIL/WARN duh kao issues-KB/skills-KB: deterministički validator (`scripts/validate_expert_analyses.py`) je rezervisan za mehaniku (frontmatter, index paritet, extract strukturna polja, image_path postojanje, ≤400 reči heuristika, by-event/by-structure parity), LLM ostaje rezervisan za domensku prosudbu (validan par vs. gola definicija, event/structure klasifikacija). **Kapijska kadenca ispod je provizorna** — B01 kalibracija (deljeni merni uzorak wyckoff#92) je empirijski koriguje, isto kao što je issues-KB/skills-KB iskustvo pokazalo da kadencu ne treba unapred pretpostavljati.

Kapije na kraju svakog izvora (B13 book, B16 crypto, B29 fraser) su `semantic-lint` obrazac (mirror skills-kb B09): posle završnog batch-a datog izvora, pokreni semantičku proveru kompletnog `by-event`/`by-structure` sadržaja tog izvora + DoD kontrolu pre nego što sledeći izvor počne. Ostali batch-evi nose standardnu (samo deterministički gate) kapiju.

## Copy/paste promptovi

Svaki blok je potpun copy/paste prompt. B01 nosi pun disciplinovan tekst (spreman za E2E). B02-B29 nose TODO placeholder — SKIL prolaz (van obima infrastrukturnog plana) dopunjava pun tekst pre stvarnog ingesta tih batch-eva.

### B01

```text
$B01 — expert-analyses book sweep, page_001-page_020. Pre pisanja pročitaj (redom): research/expert-analyses/EXTRACT_TEMPLATE.md, research/expert-analyses/_progress.md, research/expert-analyses/wiki/index.md, poslednjih 50 linija research/expert-analyses/wiki/log.md, CLAUDE.md §5 (provenance/citat konvencije) i §7 (WIKI_GAP).

Obradi TAČNO raw/book/pages/page_001.md do raw/book/pages/page_020.md (20 strana, ne manje ne više — ovo je deljeni merni uzorak za wyckoff#92, opseg se ne pomera).

Za svaku stranicu proveri kriterijum validnog para (per stari plan `PRPs/plans/research-expert-analyses-index.plan.md` Zadatak 3, i issue #89): postoji grafikon/jasna referenca (proveri `raw/book/image_manifest.json` da li stranica ima figuru) I ekspert daje konkretnu Wyckoff interpretaciju (ne golu definiciju, ne prazan schematic-only prikaz bez teksta) I identifikabilan kontekst. Schematic-only stranica → `type: schematic`. OCR artefakte citiraj verbatim, ne popravljaj.

Za svaki validan par napiši extract karticu u research/expert-analyses/wiki/extracts/book_<lokator>_<event-ili-struktura>_<asset-ili-example>.md po šablonu EXTRACT_TEMPLATE.md (svih 10 obaveznih polja + page/post_url either-or, verbatim citat u telu, `status: candidate`).

Za svaki extract dopuni ODGOVARAJUĆU POSTOJEĆU stranicu u research/expert-analyses/wiki/by-event/*.md i/ili research/expert-analyses/wiki/by-structure/*.md (stranice već postoje sa minimalnim frontmatter-om — NE kreiraj nove fajlove, samo ažuriraj postojeće): dodaj red pod "## Primeri" koji linkuje novi extract, i ažuriraj frontmatter `description`/`sources`/`status` te stranice (status ide na `active` kad dobije bar jedan pointer, `sources` dobija `- path: raw/book/pages/page_NNN.md` unos za svaki raw izvor na koji se stranica sada oslanja).

Ažuriraj research/expert-analyses/_progress.md red `book` (`reviewed`, `valid`, `rejected`, `last_reviewed`) — reviewed mora rasti za svaku obrađenu stranicu (validnu ili odbačenu), ne samo za validne.

Dopiši kratak unos u research/expert-analyses/wiki/log.md (mirror llm-wiki log konvencije: datum, batch-ID, kratak sažetak).

Batch protokol (stari plan Notes): ova serija (20 strana) je već ceo batch — nema dalje unutrašnje deljenje. AKO proceniš da si dostigao/prešao ≥50% iskorišćenog konteksta PRE nego što obradiš svih 20 strana, STANI odmah posle poslednje kompletirane stranice i ostavi `_progress.md last_reviewed` tačno na toj stranici (partial resume za sledeći poziv) — ne guraj do kraja "u jednom dahu".

NE piši u research/expert-analyses/batches.md (status/napredak upisuje isključivo runner), pa stani.
```

### B02

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B03

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B04

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B05

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B06

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B07

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B08

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B09

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B10

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B11

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B12

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B13

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B14

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B15

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B16

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B17

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B18

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B19

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B20

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B21

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B22

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B23

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B24

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B25

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B26

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B27

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B28

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```

### B29

```text
"TODO: puni tekst disciplinovanog prompta dolazi u SKIL prolazu (izmena-skila/pravljenje-skila nad ovim batches.md, posle wyckoff#89 disciplina rasprave). Placeholder ne sme biti korišćen za pravi ingest."
```
