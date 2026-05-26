# Operation: Review PR

**Kada se koristi:** pre merge-a bilo kog batch PR-a (Batch 3–9). Cilj — mehanička provera bez dubokog Wyckoff judgment-a, da uhvati strukturalne probleme rano.

## Predikondicije

- PR je otvoren protiv `main`
- gh CLI je dostupan i autentikovan
- Repo je clone-ovan lokalno

## Korak 1: Pokreni automated review

```bash
uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py <PR_NUMBER>
```

Skript automatski:
1. Fetch-uje PR granu u privremeni worktree
2. Diff-uje protiv `origin/main`
3. Pokreće 6 mehaničkih provera:
   - **Provenance frontmatter** — svaka nova stranica ima `sources:` sa konkretnim raw/ putanjama koje postoje
   - **Inline citation links** — svaki `[...](path)` razrešava iz prave dubine stranice
   - **Cross-references** — `[[name]]` linkovi pokazuju na stranice koje postoje (osim eksplicitno markiranih future-batch linkova)
   - **Index/log update** — `index.md` i `log.md` imaju entry-je za novi batch
   - **Style konzistentan** — sekcijska struktura (Summary, Key Points, ...) prati prethodne batch-eve
   - **WIKI_GAP markeri** — nema neopravdanih gap-ova; svi gap-ovi imaju kontekst u log.md
4. Vraća JSON + human-readable srpski izveštaj
5. Briše worktree

Exit 0 = sve pass, exit 1 = bar jedan fail (sa detaljima).

## Korak 2: Interpretiraj rezultat

### Sve PASS
- Pošalji rezultat user-u kao komentar na PR-u (opciono) ili usmeno
- Spreman za merge

### Bar jedan FAIL
**Ne mergaj.** Akcije zavise od koje provere je fail:

| Fail | Akcija |
|---|---|
| Frontmatter provenance | Vrati u batch kild — dopuni nedostajuće `sources:` |
| Inline citation links | Pokreni `fix_inline_links.py` u batch kildu — depth bug se može fix-ovati automatski |
| Cross-references | Vrati u batch kild — popravi broken `[[name]]` ili dodaj future-batch komentar |
| Index/log | Vrati u batch kild — dopuni |
| Style | Manualno proverkaj na primere; opciono prepusti batch kildu |
| WIKI_GAP | Manualno odluči — možda je legitimni gap (paywall) ili previd |

## Korak 3: Posle fix-a u kildu

```bash
git push  # u kild-u
# skript možeš ponovo pokrenuti
uv run skills/wyckoff-wiki-ingest/scripts/review_pr.py <PR_NUMBER>
```

## Korak 4: Merge

Tek kada review prolazi:
```bash
gh pr merge <PR_NUMBER> --repo ssmiljanicc/wyckoff-ai --squash --delete-branch
```

Posle merge-a:
- `git checkout main && git pull --ff-only`
- Validate ceo wiki još jednom:
  ```bash
  uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
  ```
- Označi issue komentar ili checkbox na #7

## Korak 5 (opciono): Deep review

Ako batch ima novi domen (npr. crypto archive prvi put, ili novu vrstu Wyckoff sadržaja koju Batch 1/2 nisu pokrili), mehanički review nije dovoljan. Opciono pokreni:

- Manuelni spot-check 3–5 nasumičnih stranica:
  - Da li ima dubinu sinteze ili je samo parafraza izvora?
  - Da li koristi tačan Wyckoff vokabular (ne tržišni žargon)?
  - Da li cross-references vode na semantički povezane stranice (ne random)?
- Ova provera ide u Opus session (ne u Codex review kild) — traži dubok judgment.

## Output contract review-a

- `review_pr.py` izlaz ili manualni izveštaj
- Komentar na PR-u sa pass/fail po sekciji (ako pišeš)
- Akcija: merge ili back-to-kild
