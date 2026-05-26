---
name: wyckoff-wiki-ingest
description: Operativni protokol za batched ingest sirovih izvora (book, crypto archive, Bruce Fraser) u knowledge/wiki/. Privremen — koristi se dok se ne završi Issue #7 (9 batch-eva). Sadrži cross-batch awareness pravila, validation skripte i review checklist. Pozivaj se eksplicitno na početku svakog batch-a i pre svakog PR review-a.
---

# Wyckoff Wiki Ingest Skill

**Privremen skill za Issue [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7).**
Briše se nakon merge-a Batch 9. CLAUDE.md zadržava trajnu schemu; ovaj skill drži #7-specifičan radni protokol.

## Scope

Ovaj skill se koristi kada:
- Pokrećeš novi batch wiki ingest-a (Batch 3–9)
- Review-uješ batch PR pre merge-a
- Validiraš inline citation linkove

Ne koristi se za: dodavanje pojedinačnih stranica van batch-a, ad-hoc update-e, pisanje skill-a `wyckoff-trader-skill`.

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

## 3.5 Unknown term protocol

Cross-batch awareness iz §3 pokriva slučaj "termin se pojavi u sirovom izvoru". Ovaj odeljak pokriva drugi slučaj: **agent piše sintezu i poseže za pojmom koji nije u trenutnom raw izvoru.**

**Pravilo (strogo):** agent **ne sme** uvesti termin iz svog training data ako termin **nije** ni u trenutnom raw izvoru ni u postojećem wiki-u.

Algoritam kada se u sintezi javi takav termin:

1. **Proveri raw izvor** — da li je termin doslovno ili parafrazirano u jednom od `sources:` fajlova iz frontmatter-a?
   - DA → koristi termin, citiraj inline link na taj raw fajl
2. **Proveri postojeći wiki** — `grep -rn "<termin>" knowledge/wiki/` ili `cat knowledge/wiki/index.md`
   - DA → linkuj `[[name]]`, ne redefiniši
3. **Nije ni u izvoru ni u wiki-u** → **NE PIŠI termin**. Dve opcije:
   - **(a) Reformuliši sintezu** na vokabular koji raw izvor zaista koristi (preferirano)
   - **(b) `WIKI_GAP` marker** + entry u `log.md` ako je termin standardni Wyckoff pojam koji bi trebalo da postoji ali ga nijedan izvor u ovom batch-u ne pokriva

**Anti-pattern:** "agent zna da je `creek` standardni Wyckoff pojam iz training data, ali knjiga ga ne pominje u trenutnom poglavlju i wiki još nema stranicu" → ne sme se ubaciti definicija oslonjena na training data. Ili reformuliši, ili stavi WIKI_GAP.

Razlog: provenance disciplina (CLAUDE.md §5) zahteva da svaka tvrdnja u wiki-u bude cite-ovana protiv izvora. Training data nije citativan izvor.

---

## 4. Output contract za batch

Svaki batch završava sa:

### 4.1 Commit grupe
Svaka logička grupa stranica = jedan commit. Primer iz Batch 2:
- `Wiki Batch 3.1: Phase X events` (X events grupisanih)
- `Wiki Batch 3.2: Y concepts`
- `Wiki Batch 3.3: source summaries za poglavlja A-B`
- `Wiki Batch 3: ažurira index.md i log.md za batch 3`

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

### 4.4 PR
Naslov: `#7 Wiki ingest Batch N (source, scope)`. Body na **srpskom** sa istom strukturom kao [PR #37](https://github.com/ssmiljanicc/wyckoff-ai/pull/37):
- Sažetak
- Šta je urađeno po folderu
- Provenance disciplina (citacije + frontmatter)
- Commit grupe
- Validacija (`validate_links.py` mora proći)
- Šta sledi za sledeći batch

Refs `#7`. **Bez self-merge.**

---

## 5. Operacije

- `operations/ingest-batch.md` — protokol za pokretanje novog batch-a (Opus ili Codex). Pozovi ovo PRVO u kildu pre slanja batch prompta.
- `operations/review-pr.md` — protokol za review postojećeg batch PR-a. Pozovi ovo u review kildu.

---

## 6. Skripte

- `scripts/validate_links.py` — proverava da svaki inline `[...](path)` u svim wiki .md fajlovima razrešava. Exit 0 ako sve OK, exit 1 sa report-om ako nešto fali. Primer:
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
  uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py --pr 38   # samo fajlovi iz PR-a
  ```

- `scripts/fix_inline_links.py` — jednokratni fix za citation depth bug. Detektuje da li je link na pogrešnoj dubini i koriguje. Idempotentan — ne menja fajlove koji su već tačni.
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py --dry-run
  uv run skills/wyckoff-wiki-ingest/scripts/fix_inline_links.py        # primeni
  ```

- `scripts/review_pr.py` — mehanički pre-merge review. Prima PR broj, vraća pass/fail po sekciji na srpskom.
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py 38
  ```

Sve skripte koriste samo stdlib (Python 3.11+). Bez novih dependencies u `pyproject.toml`.

---

## 7. When to delete this skill

Posle merge-a Batch 9 PR-a:
```bash
git rm -rf skills/wyckoff-wiki-ingest/
git commit -m "Remove wiki ingest skill (Issue #7 closed)"
```

CLAUDE.md ostaje — drži trajne invariante koje se koriste i za ad-hoc wiki update-e u budućnosti.
