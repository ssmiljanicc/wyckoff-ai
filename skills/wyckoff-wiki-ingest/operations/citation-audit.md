# Operation: Citation Audit

**Kada se koristi:** za Sloj-2 semantic pass (semantički prolaz - LLM proverava da li tvrdnja zaista proizlazi iz izvora) nad citatima koje je `audit_citations.py` flagovao, ili nad svim novim/izmenjenim citatima u PR-u kada reviewer traži stroži provenance review.

**Ko ga izvršava:** Opus sesija. Ova operacija traži domenski sud: da li raw stranica direktno tvrdi isto što i wiki claim, da li je parafraza korektna, ili je citation misattribution.

**Pretpostavka:** Sloj-1 je vec pokrenut:

```bash
uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py
```

Za PR scope:

```bash
uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --pr <PR_NUMBER>
```

---

## 1. Input

Uzmi jedan od ova dva input-a:

1. `audit_citations.py` output (`--json` preferirano za iscrpan sweep).
2. Reviewer-ov ručni spisak citata iz PR-a.

Za svaki flag pripremi:

- wiki fajl i liniju
- claim oko citata (najmanje pasus iznad i ispod)
- cited raw path
- raw tekst citirane strane
- ako postoji očigledan off-by-one kandidat, raw tekst prethodne i sledeće strane

Za book page raspon (`p.A-B`) procitaj sve raw strane u rasponu.

---

## 2. Scope Pravilo

### Pre-merge PR audit

Obradi sve nove ili izmenjene citate u PR-u koje Sloj-1 hard-flaguje. Ako je broj flagova veliki, nemoj uzorkovati nasumicno; prvo pokrij sve `image_only`, `missing_raw`, `quote_not_found`, `range_*`, i `frontmatter_missing` nalaze. `section_boundary` i `inline_missing` su warning / Sloj-2 backlog i ulaze tek kada reviewer trazi siru semanticku proveru.

### Full sweep

Obradi sve Sloj-1 flagove iz baze. Full sweep je namenjen da otkrije nasledjene greske iz #7; output ide u `knowledge/wiki/health/citation-audit-<date>.md`.

---

## 3. Presuda Po Citatima

Za svaki citat klasifikuj rezultat kao tacno jednu vrednost:

| Label | Znacenje | Akcija |
| --- | --- | --- |
| `directly-stated` | Raw stranica eksplicitno tvrdi isto sto wiki claim tvrdi. | OK |
| `paraphrase-ok` | Raw stranica podrzava istu substancu drugim recima; wiki claim ne dodaje novu tvrdnju. | OK |
| `misattribution` | Citat pokazuje na pogresnu raw stranicu, image-only stranicu, pogresnu stranu raspona, ili raw ne podrzava claim. | Zabelezi predlozeni source, ne popravljaj u ovom audit PR-u |
| `needs-human-review` | Sadrzaj je dvosmislen ili trazi domain odluku van dostupnog raw teksta. | Zabelezi pitanje i minimalni kontekst |

Posebna pravila:

- Direktan quote mora biti pronadjen verbatim ili kroz jasnu OCR-normalizovanu frazu u citiranoj raw strani. Ako je na susednoj strani, to je `misattribution`.
- `image_only` nalaz je `misattribution` osim ako wiki claim eksplicitno citira samu sliku/figuru i ne tvrdi prozni sadrzaj.
- `section_boundary` nije automatski fail. Procitaj sledecu stranu; ako je tvrdnja tamo, klasifikuj `misattribution` i predlozi sledecu stranu.
- `frontmatter_missing` i `inline_missing` su provenance parity problemi. Ako claim/raw veza jeste tacna, klasifikuj `paraphrase-ok` uz `parity-fix-needed` u napomeni.
- Scenario stranice imaju transitive provenance special-case iz `CLAUDE.md` §5: tvrdnje koje samo restate-uju linked definition page ne moraju duplirati upstream raw source u frontmatter-u.

---

## 4. Output Contract

Izvestaj pisi na srpskom, ali zadrzi classification labele tacno kako su gore definisane:

```md
# Citation Audit Report - <scope/date>

## Summary

- Scope:
- Sloj-1 command:
- Total reviewed:
- directly-stated:
- paraphrase-ok:
- misattribution:
- needs-human-review:

## Findings

### <wiki-path>:L<line> - <label>

- Claim: "<kratak claim>"
- Current citation: `<raw/path.md>`
- Verdict: `<directly-stated|paraphrase-ok|misattribution|needs-human-review>`
- Evidence: <kratak opis sta raw kaze ili ne kaze>
- Suggested source: `<raw/path.md>` / `none found`
- Notes: <parity/range/section-boundary napomena ako postoji>
```

Ne menjaj wiki sadrzaj tokom ove operacije. Ispravke idu u zaseban PR koji referencira audit report i konkretne nalaze.

---

## 5. Validation

Za Sloj-1 generated report:

```bash
uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json > /tmp/citation-audit.json || true
python3 -m json.tool /tmp/citation-audit.json >/dev/null
rg -n "Hard Gate Flags|Warning / Sloj-2 Backlog|quote_not_found|section_boundary" knowledge/wiki/health/citation-audit-*.md
```

Za Sloj-2 semantic verdict report:

```bash
rg -n "misattribution|needs-human-review|directly-stated|paraphrase-ok" knowledge/wiki/health/citation-audit-*.md
```

Ako je operacija radjena za PR, u PR body ili review komentar dodaj kratko:

```md
Sloj-2 citation audit: <PASS / FAIL / NEEDS FOLLOW-UP>, report: <path-or-comment-link>
```
