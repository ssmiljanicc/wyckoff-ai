# Operation: Ingest Batch

**Kada se koristi:** na početku svake batch sesije (Batch 3–9), bez obzira da li je Opus ili Codex.

**Veza sa runbook-om:** ova operacija je hands-on procedure. Disciplinske invariante (path depth, cross-batch awareness, unknown claim, citation verification, context budget) su u runbook-u `runbooks/wyckoff-wiki-ingest.md` §1–§3.7.

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

Ovo ti daje vokabular koji već postoji. Sve termine koji se pojave u tvom izvoru a već imaju stranicu — linkuj preko `[[name]]`, ne redefiniši (per runbook §3).

## Korak 2: Pročitaj batch scope iz runbook-a §1

Identifikuj svoj batch broj i source range u runbook-u. Issue #7 ima konkretnu listu stranica koje se očekuju u svakom batch-u (vidi CLAUDE.md §3 required pages).

## Korak 3: Read raw sources

- Book batch: `raw/book/pages/page_XXX.md` za relevantne strane
- Crypto archive batch: `raw/crypto_archive/posts/` (filter po vol-u)
- Fraser batch: `raw/bruce_fraser/articles/` (filter po temi)

**Čitaj raw stranice eksplicitno** preko Read tool-a (ili `cat`). Ne oslanjaj se na pamćenje sadržaja iz prethodnih batch-eva. Citation verification iz §3.6 runbook-a zahteva da raw fajl bude svež u kontekstu pre nego što napišeš inline link.

## Korak 4: Pisanje wiki stranica

**Pre nego što uvedeš ijednu novu tvrdnju u wiki tekst, vidi runbook §3.5 (Unknown claim protocol):**
- Direktan quote → grep verbatim u raw fajlu pre pisanja
- Parafraza → tvrdnja mora biti prepoznatljivo prisutna u izvoru
- Sinteza → eksplicitan `> **Synthesis:**` marker sa listom izvora
- Bez podrške u izvoru/wiki-u → reformuliši ili `WIKI_GAP`, **nikad training data**

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

Frontmatter ↔ inline parity (runbook §3.6): svaki `[book p.XXX]` u tekstu mora imati entry u `sources:`, i obrnuto.

### Inline citation depth (KRITIČNO — vidi runbook §2)

Za stranicu u `knowledge/wiki/concepts/`, `events/`, `structures/`, `crypto/`, `scenarios/`:
```md
... ([book p.142](../../../raw/book/pages/page_142.md)) ...
```

Za stranicu u `knowledge/wiki/sources/book/`:
```md
... ([p.12](../../../../raw/book/pages/page_012.md)) ...
```

### Citation verification drill (runbook §3.6)

Pre nego što napišeš `[book p.XXX]` link:
1. Read tool → `raw/book/pages/page_XXX.md`
2. Ako je direktan quote → grep verbatim quote u tom fajlu, mora se naći
3. Ako je parafraza → potvrdi prisutnost tvrdnje
4. Ako se ne nađe → ili je page broj pogrešan, ili je tvrdnja sinteza

**Nikad ne piši page broj iz pamćenja** — page broj nije nešto što treba zapamtiti, već naći u trenutnom raw fajlu.

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

**Anti-pattern (Batch 2 lesson):** sekcije tipa `### Common Trading Mistakes The Book Flags` koje liste tvrdnje bez inline citacija. Ovo je sinteza — mora biti markirano `> **Synthesis:**` ili reformulisano sa eksplicitnim izvorima.

## Korak 5: Posle svake logičke grupe — commit

```bash
git add knowledge/wiki/<folder>/
git commit -m "Wiki Batch N.X: <grupa>"
```

**Context-budget protokol (runbook §3.7):** commit-uj po logičkim grupama tokom rada, ne čekaj kraj batch-a. Ako proceniš da je context iskorišćen ≥75%, **stani** posle trenutne grupe — misattribution rizik raste eksponencijalno na poslednjim stranicama pre context cut-a. Resume u sledećoj sesiji je validan i preferiran.

## Korak 6: Pre PR-a — validate

```bash
uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
```

Mora pass-ovati. Ako fail-uje, popravi pa ponovo commit.

Opciono (ali preporučeno za visok-rizik batch): pre push-a, pokreni mini self-spot-check po runbook §3.6:
```bash
# Uzmi 2 random inline citation linka iz najnovijih wiki stranica i grep verbatim u target raw fajlu
grep "<distinct phrase>" raw/book/pages/page_XXX.md
```

## Korak 7: Update index + log

- `knowledge/wiki/index.md` — dodaj sve nove stranice
- `knowledge/wiki/log.md` — append entry sa datumom, scope, commit listom, otvorenim WIKI_GAP markerima

Commit: `Wiki Batch N: ažurira index.md i log.md za batch N`

## Korak 8: Push + PR

```bash
git push -u origin <branch>
gh pr create --title "#7 Wiki ingest Batch N (source, scope)" --body-file PR_BODY.md --base main
```

PR body na srpskom, struktura kao PR #37. Refs #7. Bez self-merge.

## Output contract

Završen batch ima:
- N commit-eva po logičkim grupama (po §3.7 disciplina)
- Sve nove stranice u frontmatter + cross-reference disciplini
- Sve inline citacije verifikovane po §3.6
- Sve sinteze markirane po §3.5
- `validate_links.py` pass
- `index.md` i `log.md` update
- Otvoren PR sa naslovom `#7 Wiki ingest Batch N (...)`

Ne commit-uj ako validate_links.py fail-uje.
