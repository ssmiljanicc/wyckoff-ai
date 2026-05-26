# Operation: Ingest Batch

**Kada se koristi:** na početku svake batch sesije (Batch 3–9), bez obzira da li je Opus ili Codex.

## Predikondicije

- Lokalna grana je sveža od `origin/main` (`git pull --ff-only`)
- Prethodni batch je merge-ovan (proveri `git log --oneline origin/main | head -5`)
- `validate_links.py` prolazi na trenutnom main-u

## Korak 1: Učitaj postojeći wiki

```bash
cat knowledge/wiki/index.md
tail -100 knowledge/wiki/log.md
ls knowledge/wiki/concepts/ knowledge/wiki/events/ knowledge/wiki/structures/ knowledge/wiki/sources/book/
```

Ovo ti daje vokabular koji već postoji. Sve termine koji se pojave u tvom izvoru a već imaju stranicu — linkuj preko `[[name]]`, ne redefiniši.

## Korak 2: Pročitaj batch scope iz SKILL.md §1

Identifikuj svoj batch broj i source range. Issue #7 ima konkretnu listu stranica koje se očekuju u svakom batch-u (vidi CLAUDE.md §3 required pages).

## Korak 3: Read raw sources

- Book batch: `raw/book/pages/page_XXX.md` za relevantne strane
- Crypto archive batch: `raw/crypto_archive/posts/` (filter po vol-u)
- Fraser batch: `raw/bruce_fraser/articles/` (filter po temi)

## Korak 4: Pisanje wiki stranica

**Pre nego što uvedeš ijedan Wyckoff termin u sintezu, vidi SKILL.md §3.5 (Unknown term protocol):** termin mora biti ili u trenutnom raw izvoru, ili u postojećem wiki-u. Nema improvizacije iz training data — ili reformuliši, ili stavi `WIKI_GAP`.

### Frontmatter shape (obavezno za svaku stranicu)
```yaml
---
title: "Page Title"
type: concept|event|structure|crypto|scenario|source
status: active
updated: YYYY-MM-DD
sources:
  - path: raw/book/pages/page_XXX.md
    note: "primary definition" | "applied example" | etc.
---
```

### Inline citation depth (KRITIČNO — vidi SKILL.md §2)

Za stranicu u `knowledge/wiki/concepts/`, `events/`, `structures/`, `crypto/`, `scenarios/`:
```md
... ([book p.142](../../../raw/book/pages/page_142.md)) ...
```

Za stranicu u `knowledge/wiki/sources/book/`:
```md
... ([p.12](../../../../raw/book/pages/page_012.md)) ...
```

### Cross-references
```md
The spring is the most common test event ([[spring]]). It contrasts with
the [[upthrust]] in distribution structures and links upstream to
[[phase-c]].
```

### Sekcijska struktura (konzistentna sa Batch 1 + 2)
- `# Title`
- `## Summary` — 2–4 rečenice, šta je
- `## Key Points` — bullet lista, 5–10 stavki
- domen sekcije (npr. `## Volume Behavior`, `## What Confirms It`, `## Typical Trap`)
- `## Why It Matters For Wyckoff Reading` (samo events/concepts)
- `## Synthesis` (ako ima cross-source generalizacija — explicit marker)
- `## Links` — lista [[backlinks]] ka povezanim stranicama

## Korak 5: Posle svake logičke grupe — commit

```bash
git add knowledge/wiki/<folder>/
git commit -m "Wiki Batch N.X: <grupa>"
```

## Korak 6: Pre PR-a — validate

```bash
uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
```

Mora pass-ovati. Ako fail-uje, popravi pa ponovo commit.

## Korak 7: Update index + log

- `knowledge/wiki/index.md` — dodaj sve nove stranice
- `knowledge/wiki/log.md` — append entry sa datumom, scope, commit listom

Commit: `Wiki Batch N: ažurira index.md i log.md za batch N`

## Korak 8: Push + PR

```bash
git push -u origin <branch>
gh pr create --title "#7 Wiki ingest Batch N (source, scope)" --body-file PR_BODY.md --base main
```

PR body na srpskom, struktura kao PR #37. Refs #7. Bez self-merge.

## Output contract

Završen batch ima:
- N commit-eva po logičkim grupama
- Sve nove stranice u frontmatter + cross-reference disciplini
- `validate_links.py` pass
- `index.md` i `log.md` update
- Otvoren PR sa naslovom `#7 Wiki ingest Batch N (...)`

Ne commit-uj ako validate_links.py fail-uje.
