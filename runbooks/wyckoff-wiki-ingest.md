# Wyckoff Wiki Ingest Runbook

## Purpose

Neutralni runbook za batched ingest sirovih izvora (book, crypto archive, Bruce Fraser) u `knowledge/wiki/`. Tokom Issue [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) (9 batch-eva) drži batch-specifičan protokol; posle Batch 9 se **trim-uje, ne briše** (vidi §7) — discipline ostaje za ad-hoc wiki update-e i buduće izvore. Sadrži cross-batch awareness pravila, citation verification protokol, cross-author pravilo, validation skripte i review checklist.

Runtime-agnostic — Claude Code adapter (§Claude Code Adapter) i Codex adapter (§Codex Adapter) na kraju mapiraju invocation. Sve operativne procedure ovde važe isto za oba runtime-a.

Tanki wrappers:
- Claude: [`.claude/skills/wyckoff-wiki-ingest/SKILL.md`](../.claude/skills/wyckoff-wiki-ingest/SKILL.md)
- Codex: [`.agents/skills/wyckoff-wiki-ingest/SKILL.md`](../.agents/skills/wyckoff-wiki-ingest/SKILL.md)

## Inputs

Treat invocation text as a wiki ingest request. Tipično:

- broj batch-a (1–9) — vidi §1 Ingest priority order
- ili PR broj — vidi `operations/review-pr.md` (review postojećeg PR-a)
- ili spot-check trigger — vidi `operations/semantic-spot-check.md`

## Outputs

- Wiki stranice u `knowledge/wiki/{concepts,events,structures,crypto,scenarios,sources}/`
- Index update u `knowledge/wiki/index.md`
- Log append u `knowledge/wiki/log.md`
- PR protiv `main` sa naslovom `#7 Wiki ingest Batch N (source, scope)`
- Validacioni rezultati (`validate_links.py` pass, opciono `review_pr.py` izveštaj)

## Scope

Ovaj runbook se koristi kada:
- Pokrećeš novi batch wiki ingest-a (Batch 3–9)
- Review-uješ batch PR pre merge-a (mehanički + semantic spot-check)
- Validiraš inline citation linkove

Tokom #7 (batch faza) fokus je na batch-eve. **Posle Batch 9** isti runbook (trim-ovan, §7) pokriva i ad-hoc dodavanje pojedinačnih stranica i ingest novih izvora — discipline (citation, cross-batch, cross-author, spot-check) važi isto.

Ne koristi se za: pisanje skill-a `wyckoff-trader-skill` (runtime contract, ne knowledge base).

---

## 1. Ingest priority order

Batched ingest sledi ovaj redosled (osim ako je drugi batch eksplicitno tražen):

| Batch | Source | Scope |
|---|---|---|
| 1 ✅ | Book | Chapters 1–13 (core framework) |
| 2 ✅ | Book | Chapters 14–25 (events, phases, structures) |
| 3 | Book | Chapters 26–27 (trade execution, Point & Figure) |
| 4 | Crypto Archive | Vol 14–28 (2020: post-crash repair, margin behavior) |
| 5 | Crypto Archive | Vol 29–59 (2020–2021: DeFi, rotation, terminal Bitcoin) |
| 6 | Bruce Fraser | Context and phase reading (~40 articles) |
| 7 | Bruce Fraser | Point & Figure (~30 articles) |
| 8 | Bruce Fraser | Relative strength and campaign logic (~40 articles) |
| 9 | Bruce Fraser | Preostalo (~130 articles) |

**Rationale:** knjiga definiše vokabular. Crypto archive i Fraser primenjuju isti vokabular — moraju biti ingest-ovani posle, da linkuju ka već postojećim concept stranicama umesto da redefinišu termine.

---

## 2. Path depth tabela (KRITIČNO)

Inline citation linkovi moraju razrešavati relativno iz **stvarne dubine stranice**. Repo struktura:

```
wyckoff-ai/                                ← repo root
├── raw/
│   └── book/pages/page_XXX.md             ← cilj citacija
└── knowledge/
    └── wiki/
        ├── concepts/X.md                  ← 3 nivoa duboko
        ├── events/X.md                    ← 3 nivoa duboko
        ├── structures/X.md                ← 3 nivoa duboko
        ├── crypto/X.md                    ← 3 nivoa duboko
        ├── scenarios/X.md                 ← 3 nivoa duboko
        └── sources/
            └── book/X.md                  ← 4 nivoa duboko
```

| Lokacija stranice | Tačan path do `raw/` | Primer |
|---|---|---|
| `knowledge/wiki/concepts/three-laws.md` | `../../../raw/...` | `[book p.36](../../../raw/book/pages/page_036.md)` |
| `knowledge/wiki/events/spring.md` | `../../../raw/...` | `[book p.142](../../../raw/book/pages/page_142.md)` |
| `knowledge/wiki/structures/accumulation.md` | `../../../raw/...` | `[book p.95](../../../raw/book/pages/page_095.md)` |
| `knowledge/wiki/crypto/intermarket-gate.md` | `../../../raw/...` | `[vol 27](../../../raw/crypto_archive/posts/...)` |
| `knowledge/wiki/scenarios/X.md` | `../../../raw/...` | isto |
| `knowledge/wiki/sources/book/book-chapter-01.md` | `../../../../raw/...` | `[p.12](../../../../raw/book/pages/page_012.md)` |

**Frontmatter `sources:` koristi repo-root relativne putanje (BEZ `../`):**

```yaml
sources:
  - path: raw/book/pages/page_142.md
    note: "primary definition"
```

To je drugačiji format od inline linkova jer frontmatter ne mora da bude clickable iz Markdown render-a.

---

## 3. Cross-batch awareness protokol

**Pre nego što napišeš BILO KOJU novu wiki stranicu:**

### Korak 1: Učitaj postojeći wiki
```bash
cat knowledge/wiki/index.md
tail -50 knowledge/wiki/log.md
```

### Korak 2: Za svaki Wyckoff pojam koji naletiš u sirovom izvoru
1. Proveri da li već ima wiki stranicu (preko `index.md`)
2. Ako DA:
   - **NE redefiniši** termin u novoj stranici
   - Linkuj preko `[[name]]`
   - Pročitaj postojeću stranicu pre nego što napišeš nešto što bi bilo u kontradikciji sa njom
3. Ako tvoj batch dodaje primer ili applied case postojećeg pojma:
   - Stavi primer u tvoju novu stranicu (npr. "Spring in low-liquidity crypto" → `crypto/`)
   - Nadoveži se na postojeći `[[spring]]` — bez ponavljanja definicije

### Korak 3: Ako pojam nije pokriven u tvom izvoru i nema wiki stranicu
- Marker `WIKI_GAP` u stranici gde se pojam pojavljuje
- Zapis u `log.md` kao "open follow-up"

### Korak 4: Pre nego što commit-uješ
- `uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py` — proverava sve inline linkove
- Popravi sve broken pre commit-a

---

## 3.5 Unknown claim protocol

Cross-batch awareness iz §3 pokriva slučaj "termin se pojavi u sirovom izvoru". Ovaj odeljak proširuje pravilo na **bilo koju tvrdnju** u wiki tekstu, ne samo termine.

**Strogo pravilo:** wiki ne sme da sadrži tvrdnju koja nije direktno povezana sa raw izvorom ili eksplicitno markirana kao sinteza. Training data nije citativan izvor.

### Klasifikacija svake tvrdnje pre nego što je napišeš

| Tip tvrdnje | Validacija | Marker |
|---|---|---|
| **Direktni quote** | Otvori raw fajl + grep verbatim quote. Mora se naći. | Inline citation `[book p.XXX]` + quote u blockquote |
| **Parafraza** | Otvori raw stranicu; tvrdnja mora biti prepoznatljivo prisutna u izvornom tekstu (ne samo "u duhu"). | Inline citation `[book p.XXX]` |
| **Cross-source sinteza** | Kombinacija ≥2 izvora ili generalizacija van bilo kog jednog. Mora biti eksplicitno markirana. | `> **Synthesis:** ...` blok sa listom izvora po CLAUDE.md §5 |
| **Tvrdnja bez izvora** | Ako ni jedan raw fajl ni postojeća wiki stranica ne podržava → **ne piši**. | Reformuliši na vokabular izvora ili `WIKI_GAP` + entry u `log.md` |

### Anti-patterns koji su uzrokovali Batch 2 CONCERN-e

- **"The Book Flags X"** lista bez inline citacija → sinteza prikazana kao direktna izvorska tvrdnja
- **"The Book States Y"** uvodni header → implicira citativnu osnovu koju listanje ne podržava
- Generička "Common Mistakes" sekcija bez page reference → najčešće training data popunjava

Ako pišeš sekciju koja kategorizuje, lista, ili generalizuje (npr. "Common Trading Mistakes", "Typical Failures", "Recurring Patterns"), pretpostavi da je to **sinteza** dok ne dokažeš suprotno. Default je `> **Synthesis:**` blok, ne direktna tvrdnja.

---

## 3.6 Citation verification drill

Pre nego što napišeš `[book p.XXX](../../../raw/book/pages/page_XXX.md)` inline link:

1. **Read tool** → `raw/book/pages/page_XXX.md`
2. **Ako citiraš direktan quote:** `grep` quote (ili distinktivnu frazu iz njega) u tom fajlu. Quote se mora naći **doslovno**. Ako se ne nađe — ili je page broj pogrešan, ili je quote sintetisan iz pamćenja.
3. **Ako pišeš parafrazu:** pročitaj page; tvrdnja mora biti prepoznatljivo prisutna u izvornom tekstu (ista substanca, ne samo "kompatibilna").
4. **Frontmatter ↔ inline parity:** svaka stranica iz frontmatter `sources:` mora biti citirana inline bar jednom. Svaki inline `[book p.XXX]` mora imati paritetan entry u frontmatter-u.

### Anti-pattern detektovan u Batch 2

`spring.md` quote "Spring must necessarily cause the range to break up..." atribuiran je `[book p.141]`. Quote je doslovno na **p.142**. P.141 sadrži drugu temu (diagnostics — UA/mSOW signal, price re-entry). Mehanički link validator nije detektovao grešku jer p.141 fajl postoji — link "razrešava", ali ka pogrešnom sadržaju.

Verifikacija: jedan grep poziv (`grep "must necessarily cause" raw/book/pages/page_141.md`) bi u trenutku pisanja vratio prazan rezultat i sprečio misattribution.

### Specijalan slučaj: page range citation

`[book p.139–140](../../../raw/book/pages/page_139.md)` cita raspon. Pravilo:
- Link target je prva stranica raspona
- **Obe stranice** moraju biti u frontmatter `sources:` (ne samo prva)
- Sadržaj raspona mora biti distribuiran kroz raw fajlove tog raspona (proveri obe)

---

## 3.7 Context-budget protokol

Veliki batch-evi (npr. 25+ stranica iz 12 poglavlja) često dovedu agenta do konteksta limita. Iz Batch 1/2 retrospektive — citation misattribution rizik raste eksponencijalno na poslednjim ingestiranim stranicama pre context cut-a.

**Pravilo:**
1. **Commit po logičkim grupama** — ne čekaj do kraja batch-a. Svaka logička grupa (npr. "Phase A events", "structures") = jedan commit u toku rada.
2. **Stop signal** — ako subjektivno procenjuješ da je context iskorišćen ≥75%, **stani** posle trenutne logičke grupe. Ne pokušavaj da kompletiraš ostatak batch-a "u jednom dahu".
3. **Resume u sledećoj sesiji** je validan i preferiran. Preciznije je bolje od kompletnijeg.
4. **Misattribution check** — pre context cut-a, vrati se na poslednje 2–3 inline citation linka koje si napisao i verifikuj po §3.6 protokolu. Tu se kompresioni misattribution najčešće javlja.

Kada se vraćaš u sledećoj sesiji, prvo `git log --oneline -10` da vidiš tačno gde si stao, pa `tail -50 knowledge/wiki/log.md` za open follow-ups iz prethodnog poteza.

---

## 3.8 Cross-author definition discipline

§3 (Cross-batch awareness) zabranjuje kontradikciju i zabranjuje redefinisanje već definisanog pojma. Ovaj odeljak proširuje pravilo na slučaj kad drugi autor *legitimno* koristi termin sa drugačijim naglaskom — ne sa pogrešnom definicijom, već sa različitim fokusom ili užim opsegom.

**Tipičan kontekst:** knjiga definiše Spring kroz tri tipa po supply intensity ([book p.144–147](../../../raw/book/pages/page_144.md)). Fraser ili crypto archive može da koristi "spring" sa drugačijim akcentom — recimo grupišući Spring #1 i Terminal Shakeout kao isti koncept, ili insistirajući na samo jednoj graphical varijanti. To **nije** sinteza dva izvora (§3.5) — to je jedan autor sa drugim naglaskom.

**Terminologija:** "primarni izvor" stranice = njen `primary_source` frontmatter key (default `book` kad key fali — vidi CLAUDE.md §5). Pravila ispod važe protiv `primary_source`-a TE stranice, ne specifično protiv knjige — pa rade i kad je stranica Fraser-origin.

### Klasifikacija

Odredi tačno **jedan** red, ovim redosledom odlučivanja (ne "viši red u tabeli"):

1. **Same-referent test PRVO:** da li autor B koristi token za *suštinski drugi koncept* (drugi referent), ili za *isti koncept* (eventualno sa drugim naglaskom)? Ako drugi referent → **red 2 (homonim)**, bez obzira na sve ostalo.
2. **Ako je isti koncept**, bira se disposition sa **najviše disclosure-a**:
   - postoji eksplicitna kontradikcija sa primarnim izvorom → **red 4** (Cross-Author Readings + `discrepancies.md`)
   - inače dodatni naglasak / uži opseg → **red 3** (Cross-Author Readings)
   - inače isto značenje → **red 1** (samo link)
   - pojam ne postoji u primarnom izvoru uopšte → **red 5** (nova stranica sa `primary_source`)

Kod preklapanja red-3-vs-red-4 (npr. 90% slaganja + jedna tačka neslaganja) bira se **red 4** — kontradikcija mora da ostavi trag u `discrepancies.md`, ne sme da se tiho apsorbuje kao "samo naglasak".

| # | Scenario | Postupak |
|---|---|---|
| 1 | Drugi autor koristi isti pojam sa **istim značenjem** | Linkuj `[[name]]`. Bez izmene postojeće definicione stranice. |
| 2 | Drugi autor koristi **isti token za suštinski drugi koncept** (homonim — ne uži opseg, nego drugi referent) | **Nova stranica sa disambiguacijom** (`events/<term>-<author-concept>.md`) + link iz oba pravca + kratka "not to be confused with" napomena na obe. **NE** Cross-Author Readings (pogrešno bi zakačilo nepovezan koncept za primarnu definiciju). |
| 3 | Drugi autor koristi pojam sa **dodatnim naglaskom** ili **užim opsegom** (isti koncept) | Na postojećoj definicionoj stranici dodaj sekciju `## Cross-Author Readings` sa pod-sekcijom `### As Used By <Human Name> (<source-value>)` — čitljivo ime + enum vrednost u zagradi radi parity provere, npr. `### As Used By Bruce Fraser (bruce_fraser)`. Inline citation u taj izvor + 2–3 rečenice šta autor naglašava/ograničava. **Bez prepisivanja primarne definicije.** Više `### As Used By X` pod-sekcija sme da se slaže (stacking). Ažuriraj `sources:` frontmatter. |
| 4 | Drugi autor se **eksplicitno ne slaže** sa primarnim izvorom (kontradikcija, ne samo naglasak) | Isto kao red 3 (Cross-Author Readings) **+** flag u `knowledge/wiki/health/discrepancies.md` (persistent, append-only, lint ga NE regeneriše — vidi CLAUDE.md §2) sa datumom, terminom, oba izvora, prirodom neslaganja. Reviewer odlučuje legit-alternative vs izvorska greška. |
| 5 | Pojam **postoji samo** u drugom izvoru, ne u primarnom (npr. Fraser-specific pojam koji knjiga ne pominje) | Nova stranica u odgovarajućem folderu sa frontmatter `primary_source: bruce_fraser` (ili `crypto_archive` — vrednost mora odgovarati raw folder imenu). Citira se autor doslovno — bez sintetske definicije iz training data-e. Ako kasnije treći izvor doda svoj naglasak na tu stranicu, primeni red 3/4 protiv NJENOG `primary_source`-a. |

### Cross-Author Readings vs sinteza (§3.5 granica)

`## Cross-Author Readings` sekcija sme **samo da OPIŠE** šta autor B naglašava/ograničava, citirajući B. Čim rečenica **uporedi** A i B ili izvuče zajednički zaključak ("oba izvora pokazuju...", "Fraser je uži od knjige jer..."), to je generalizacija preko ≥2 izvora = **sinteza** → mora `> **Synthesis:**` marker per §3.5. Test: da li rečenica može da stoji citirajući samo izvor B? Ako da → Cross-Author Reading. Ako joj treba i A da bi imala smisla → sinteza.

**Gray zone (implicitna komparacija).** Rečenica može biti *gramatički* jednoizvorna ("Fraser tretira Spring #1 i Terminal Shakeout kao jedan event") a *semantički* komparativna — jer joj relevantnost zavisi od kontrasta sa primarnom definicijom (koja ih razdvaja). Takva rečenica "stoji" po doslovnom testu, ali postoji samo zbog implicitnog poređenja. Pravilo: ako **relevantnost** rečenice zavisi od kontrasta sa primarnom definicijom (čak i kad je gramatički jednoizvorna), tretira se kao borderline → siguran default je `> **Synthesis:**` marker.

### `health/discrepancies.md` format (red 4)

Persistent, append-only (vidi CLAUDE.md §2). Samo **red 4** piše ovde — redovi 1–3 i 5 ne diraju ovaj fajl. Fiksni template po unosu:

```md
## [YYYY-MM-DD] <termin>
- **primary:** <source-value> — <šta primarni izvor tvrdi> ([citation])
- **conflicting:** <source-value> — <šta drugi autor tvrdi> ([citation])
- **priroda neslaganja:** <jedna rečenica>
- **verdikt:** <legit-alternative | izvorska-greška | nerešeno>
```

### Anti-patterns

Ako pišeš Fraser source-summary i primetiš da Fraser koristi "spring" sa drugim naglaskom (isti koncept — red 3):

- **NE** prepisuj postojeću `events/spring.md` definiciju
- **NE** napravi paralelnu stranicu `events/spring-fraser.md` za isti koncept (redefinisanje, banned po spot-check §3.2). *Izuzetak:* ako Fraser koristi "spring" za suštinski DRUGI koncept (homonim — red 2), disambiguirana stranica JE ispravna.
- **NE** označi to kao `> **Synthesis:**` (sinteza je kombinacija ≥2 izvora; ovo je jedan izvor sa drugim naglaskom — vidi "Cross-Author Readings vs sinteza" gore)
- **DA** dodaj `## Cross-Author Readings → ### As Used By Bruce Fraser (bruce_fraser)` na postojeću `events/spring.md`, sa inline citation u Fraser article-u

### Detection u spot-check-u

Spot-check §3.4 sad uključuje cross-author proveru. FAIL kategorije:
- Sintetisanje dva izvora u jedinstvenu definiciju bez `> **Synthesis:**` marker-a
- Paralelna stranica koja redefiniše već postojeći pojam
- Tiha izmena postojeće definicije (ubacivanje novog autora bez `## Cross-Author Readings` sekcije i bez ažuriranja `sources:`)

---

## 4. Output contract za batch

Svaki batch završava sa:

### 4.1 Commit grupe
Svaka logička grupa stranica = jedan commit. Primer iz Batch 2:
- `Wiki Batch 3.1: Phase X events` (X events grupisanih)
- `Wiki Batch 3.2: Y concepts`
- `Wiki Batch 3.3: source summaries za poglavlja A-B`
- `Wiki Batch 3: ažurira index.md i log.md za batch 3`

Po §3.7 — commit-uj često tokom rada, ne samo na kraju.

### 4.2 Index update
- `knowledge/wiki/index.md` — dodaj sve nove stranice pod tačnim folderom
- Sortirano alfabetski po nazivu

### 4.3 Log update
- `knowledge/wiki/log.md` — append-only entry sa:
  - Datumom
  - Scope-om (npr. "book ch 26–27")
  - Brojem stranica kreiranih
  - Listom commit-eva (kratko)
  - Open follow-ups za sledeći batch
  - WIKI_GAP markeri otvoreni u ovom batch-u

### 4.4 PR
Naslov: `#7 Wiki ingest Batch N (source, scope)`. Body na **srpskom** sa istom strukturom kao [PR #37](https://github.com/ssmiljanicc/wyckoff-ai/pull/37):
- Sažetak
- Šta je urađeno po folderu
- Provenance disciplina (citacije + frontmatter)
- Commit grupe
- Validacija (`validate_links.py` mora proći, opciono `review_pr.py`)
- Šta sledi za sledeći batch

Refs `#7`. **Bez self-merge.**

---

## 5. Operacije

- [`skills/wyckoff-wiki-ingest/operations/ingest-batch.md`](../skills/wyckoff-wiki-ingest/operations/ingest-batch.md) — protokol za pokretanje novog batch-a (Opus ili Codex). Pozovi PRVO pre slanja batch prompta.
- [`skills/wyckoff-wiki-ingest/operations/review-pr.md`](../skills/wyckoff-wiki-ingest/operations/review-pr.md) — protokol za mehanički review postojećeg batch PR-a.
- [`skills/wyckoff-wiki-ingest/operations/semantic-spot-check.md`](../skills/wyckoff-wiki-ingest/operations/semantic-spot-check.md) — protokol za semantic review (uhvata lošu sintezu, redefinisanje pojmova, površne cross-linkove koje mehanički review propušta). Obavezan za Batch 2/3 (kalibracija), posle toga decision rule.

---

## 6. Skripte

- `scripts/validate_links.py` — proverava da svaki inline `[...](path)` u svim wiki .md fajlovima razrešava. Exit 0 ako sve OK, exit 1 sa report-om. Primer:
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
  uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py --pr 38   # samo fajlovi iz PR-a
  ```

- `scripts/audit_citations.py` — Sloj-1 citation audit: proverava image-only raw strane, direct quote grep, section-boundary heuristiku, frontmatter ↔ inline parity i range sanity. Exit 0 ako nema flagova, exit 1 ako postoje sumnjivi citati. Primer:
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py
  uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --pr 38   # samo fajlovi iz PR-a
  uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json
  ```

- `scripts/fix_inline_links.py` — jednokratni fix za citation depth bug. Idempotentan.
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py --dry-run
  uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py        # primeni
  ```

- `scripts/review_pr.py` — mehanički pre-merge review. Prima PR broj, vraća pass/fail po sekciji na srpskom.
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py 38
  ```

Sve skripte koriste samo stdlib (Python 3.11+). Bez novih dependencies u `pyproject.toml`.

**Limitacija mehaničkih skripti:** `review_pr.py` proverava strukturne aspekte (frontmatter postoji, link razrešava, wikilink target postoji). **Ne hvata** semantičke probleme: misattribution (link razrešava ali na pogrešan sadržaj), synthesis-as-claim, lošu parafrazu. Za to služi `operations/semantic-spot-check.md`.

---

## 7. Post-Batch 9 cleanup (trim, ne delete)

Posle merge-a Batch 9 PR-a skill se **ne briše** — ostaje kao trajna discipline za ad-hoc wiki update-e (novi izvori, dodatne knjige, dopune Fraser arhive, dodatne crypto volume). Trim-uju se samo Batch-specifični delovi.

### Što se uklanja

- §1 "Ingest priority order" tabela (Batch 1–9 raspored je istorija)
- §7 sam (ovaj odeljak postaje obsolete)
- `Inputs` sekciju update — ukloni "broj batch-a (1–9)" (ostaje "PR broj" i "scope description")

### Što se zadržava (trajno)

- §2 Path depth tabela
- §3 Cross-batch awareness protokol
- §3.5 Unknown claim protocol
- §3.6 Citation verification drill
- §3.7 Context-budget protokol
- §3.8 Cross-author definition discipline
- §4 Output contract (commit grupe, PR template — adaptiraj naslov)
- §5 Operacije (`ingest-batch`, `review-pr`, `semantic-spot-check`)
- §6 Skripte (`validate_links.py`, `review_pr.py`, `fix_inline_links.py`)
- Claude Code Adapter + Codex Adapter
- Wrapper-i u `.claude/skills/wyckoff-wiki-ingest/` i `.agents/skills/wyckoff-wiki-ingest/`

### Što se ažurira

U ovom runbook-u:
- `Purpose` (intro) — ukloni preostali batch-faza framing kad batch-evi prestanu
- `Scope` sekciju — fokus prebaci na ad-hoc + buduće izvore (batch faza gotova)
- `Inputs` — ukloni "broj batch-a (1–9)" (ostaje "PR broj" i "scope description")
- `Codex Adapter` invocation pattern — iz `$skill <batch-number>` u `$skill <scope-description>` (uskladi sa ingest-batch.md)
- `Source Evidence` — ukloni preostale "#7-specifičan / batch" reference
- `Operation: ingest-batch.md` — invocation pattern iz `$skill <batch-number>` u `$skill <scope-description>` (npr. `$skill "Fraser articles on Point & Figure section"`)
- PR title template — bez `Batch N` prefixa, koristi `#<issue> Wiki ingest (source, scope)` format

U `CLAUDE.md` (NE ostaje nepromenjen — mora se uskladiti istim cleanup PR-om):
- §4 "Ingest workflow" — ukloni batch priority order reference; opis trim-ovanog skill-a kao trajne ad-hoc discipline
- §11 "Quick reference" — red "Run a #7 batch ingest" → generički "Run a wiki ingest / PR review"

### Kada to izvesti

Posle merge-a Batch 9 PR-a, u **zasebnom PR-u** "Trim wiki ingest skill — post-Batch 9 cleanup". Ne meša se sa Batch 9 sadržajem.

CLAUDE.md drži trajne invariante (folder layout, provenance, vocabulary) koje ostaju i za ad-hoc wiki update-e — ali §4 i §11 reference na batch lifecycle treba uskladiti (gore).

---

## Claude Code Adapter

**Invocation:**
- Eksplicitno preko skill mehanizma: `.claude/skills/wyckoff-wiki-ingest/SKILL.md` (project-local discovery).
- Ili manuelno preko Read-a ovog runbook-a u sesiji.

**Tool mapping:**
- `Read` za raw stranice i postojeći wiki — uvek čitaj raw fajl pre nego što napišeš `[book p.XXX]` link (§3.6).
- `Bash` za `git`, `uv run scripts/...`, `gh pr create`.
- `Grep` za §3.6 verifikaciju (`grep "fraza" raw/book/pages/page_XXX.md`).
- `Edit` / `Write` za wiki stranice; `Edit` za index.md i log.md append.
- `TaskCreate` za multi-step batch — preporučeno za §3.7 logičke grupe.

**Subagenti:**
- Nije obavezno za batch ingest. Opciono — `Explore` agent za otkrivanje koje pojmove izvor pominje pre nego što počneš pisanje.

**Permissions:**
- Standardni Claude Code dozvole iz `.claude/settings.json`. `gh pr create` i `git push` traže potvrdu po default-u.

**Citation verification (§3.6) je obavezan korak — ne preskači čak i ako se čini da znaš page broj.** Read + Grep su jeftini, misattribution je skup.

## Codex Adapter

**Invocation:**
- `$wyckoff-wiki-ingest <batch-number>` ili `$wyckoff-wiki-ingest review-pr <PR>` ili `$wyckoff-wiki-ingest spot-check <PR>`.
- Tretiraj user prompt kao runbook input (batch broj, PR broj, ili scope).

**Tool mapping:**
- Codex obično ima direktan file access — koristi za §3.6 verifikaciju isto kao Claude.
- `bash` za `git`, `uv run`, `gh`.
- Codex `agents/openai.yaml` drži `allow_implicit_invocation: false` — skill se ne invoke-uje automatski, samo na eksplicitan poziv.

**Subagenti:**
- Codex skill ne spawn-uje sub-agente po default-u. Ako batch zahteva paralelan rad (npr. spot-check na 5 stranica), to je orchestrirano na vrhu (operator nivo), ne u skill-u.

**Policy:**
- `policy.allow_implicit_invocation: false` — skill je explicit-only. Operator (ili wrapper) bira kada da ga aktivira.

**Citation verification (§3.6) važi isto kao za Claude.** Nije runtime-specific — to je domain pravilo.

---

## Validation

Posle bilo koje izmene wiki sadržaja (batch, spot-fix, ad-hoc):

1. `uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py` — mora pass.
2. `uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py` — Sloj-1 citation audit mora pass ili imati eksplicitno review-disposition u PR-u. Obavezne pre-merge provere su: image-only page check, quote-not-found, section-boundary heuristika, frontmatter ↔ inline parity i range sanity.
3. `git diff --check` — bez whitespace problema.
4. Ako je PR otvoren: `uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py <PR>` — sve mehaničke provere pass.
5. Za Batch 2/3 (i kasnije po triger-u): `operations/semantic-spot-check.md` — Opus sesija, izveštaj na srpskom.
6. Za citate koje `audit_citations.py` flaguje u PR-u: `operations/citation-audit.md` — Opus Sloj-2 semantic pass nad flagovanim citatima pre merge-a.
7. Ako je spot-check ili citation audit pokrenut: obavezan 1-line audit trail entry u `knowledge/wiki/log.md` (per `operations/semantic-spot-check.md` §6 i `operations/citation-audit.md`) — prerequisite za merge, čak i kad je sve PASS.

## Handoff

Završen batch (PR ready za merge) ima:
- N commit-eva po logičkim grupama (§3.7 disciplina)
- Sve nove stranice u frontmatter + cross-reference + citation verification disciplini
- `validate_links.py` pass + `review_pr.py` pass
- `index.md` i `log.md` update
- Otvoren PR sa srpskim body-jem, refs #7, bez self-merge
- Ako je triger ispunjen: semantic-spot-check izveštaj sa eksplicitnom akcijom (merge / spot-fix / back-to-kild) **+ obavezan 1-line audit trail u `log.md`** (§6 operacije) — prerequisite za merge

## Source Evidence

Ovaj runbook je nastao iz Issue #7 batch ingest disciplinske evolucije:
- Originalna struktura: `skills/wyckoff-wiki-ingest/SKILL.md` (Batch 1 + Batch 2 ingest skill, merged 61aebd7)
- Adapter pattern preuzet iz `~/.agent-runbooks/portovanje-skila.md` i njegovih wrapper-a
- Hardening §3.5–§3.7 dodato kao odgovor na PR #38 semantic spot-check nalaze (1 FAIL `spring.md` misattribution + 2 CONCERN-a synthesis-as-claim u accumulation/distribution)
- Lokalan za projekat — `wyckoff-wiki-ingest` nije primenjiv na druge repo-e, pa ne živi u `~/.agent-runbooks/`

Trajna shema je u [`CLAUDE.md`](../CLAUDE.md). Ovaj runbook drži #7-specifičan radni protokol; posle merge-a Batch 9 PR-a se **trim-uje, ne briše** (§7) — discipline ostaje za ad-hoc update-e i buduće izvore.
