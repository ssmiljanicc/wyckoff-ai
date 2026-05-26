# Operation: Semantic Spot-Check

**Kada se koristi:** za review koji ide preko strukturalnih provera — kada hoćemo da uhvatimo lošu sintezu, tihu redefiniciju već-postojećih pojmova, citation misattribution-e, i površne cross-linkove koji prolaze `review_pr.py` ali nemaju semantičkog smisla.

**Trenutno obavezno za:** **Batch 2** i **Batch 3** — kalibrišemo kvalitet ingest-a. Posle toga važi decision rule iz §1.

**Ko ga izvršava:** Opus sesija (ne Codex/Sonnet). Traži Wyckoff domain judgment i poređenje sa raw izvorima.

**Pretpostavka:** mehanički review (`review_pr.py`) je već prošao. Ovo je drugi sloj, ne zamena.

**Veza sa runbook-om:** spot-check verifikuje da je pisac batch-a sledio runbook §3.5 (Unknown claim protocol) i §3.6 (Citation verification drill). Ako je sledio, spot-check je brz; ako nije, ovde se nalazi.

---

## 1. Decision rule (kada se pokreće — posle Batch 3)

Pokreni spot-check ako je **bar jedan** trigger ispunjen:

1. Batch uvodi novi izvor tipa (npr. Fraser prvi put, crypto archive prvi put)
2. Batch dodaje ≥3 nove **definicione** stranice (`concepts/`, `events/`, `structures/`) — ne applied case
3. Reviewer ima konkretnu sumnju ("ovo deluje kao parafraza", "ovo redefiniše pojam koji već postoji")

Ako nijedan trigger nije ispunjen i mehanički review je pass → merge bez spot-check-a.

---

## 2. Sampling protokol

Cilj: 3–5 stranica koje su najveći rizik za semantičke probleme.

### 2.1 Obavezni sample (targeted)

Uzmi **sve** stranice koje zadovoljavaju jedan od ovih kriterijuma:

- **Definicione stranice** — nove u `concepts/`, `events/`, ili `structures/`
- **Boundary-crossing stranice** — stranice koje linkuju ka pojmovima uvedenim u prethodnom batch-u (`[[name]]` ka postojećim `concepts/events/structures/`)
- **Termin-redefinitori** — stranice čiji naslov je sličan već postojećoj stranici (npr. nova `events/secondary-test.md` kada već postoji `events/st-as-msos.md` — moguć overlap)
- **Multi-claim stranice** — stranice sa "Common X" / "The Book Flags" / "Common Mistakes" sekcijama (visok rizik synthesis-as-claim per runbook §3.5)

Detekcija:
```bash
# Nove definicione stranice u PR-u
gh pr diff <PR_NUMBER> --name-only | grep -E 'knowledge/wiki/(concepts|events|structures)/'

# Stranice koje linkuju ka postojećim osnovnim pojmovima
gh pr diff <PR_NUMBER> | grep -oE '\[\[[^\]]+\]\]' | sort -u

# "Common X" / "The Book Flags" sekcije (visok rizik)
gh pr diff <PR_NUMBER> | grep -E '^### Common|^### The Book'
```

### 2.2 Random sanity check (opciono)

Ako obavezni sample da <3 stranice, dodaj **1 random stranicu** iz ostatka PR-a (`sources/`, `crypto/`, `scenarios/`) kao kontrolu — da uhvatiš probleme van targetovanog skupa.

Ako obavezni sample već daje ≥5 stranica, **preskoči random** — fokusiraj se na rizično.

### 2.3 Cap

Maks 5 stranica po spot-check sesiji. Ako PR ima više rizičnih, prijavi to user-u i predloži ili (a) reviewer-ov subset, ili (b) podelu PR-a.

---

## 3. Checklist (4 stavke × po sample stranici)

Za svaku odabranu stranicu, prođi kroz 4 provere:

### 3.1 Source fidelity (cross-check sa runbook §3.6)

Uzmi **2 ključne tvrdnje** iz wiki stranice. Otvori `raw/...` fajl iz frontmatter `sources:`. Klasifikuj svaku tvrdnju:

- **Directly stated** — izvor kaže baš to → OK
- **Paraphrased** — izvor kaže to, drugim rečima → OK ako je paraphrase tačan
- **Synthesis** — kombinacija više izvora ili generalizacija → mora biti markirano per runbook §3.5 (`> **Synthesis:**`)
- **Hallucination / misattribution** — nije ni u jednom izvoru, ili je u drugom izvoru a citation pokazuje na pogrešan → **FAIL**

Posebno za quote-ove: izvedi grep verbatim quote-a u citiranom raw fajlu. Ako se ne nađe — citation je misattribution (Batch 2 Pattern).

### 3.2 Definition uniqueness

Da li ova stranica definiše pojam koji već ima wiki stranicu?

```bash
# Pretraga: postoji li već stranica koja definiše ovaj termin?
grep -rn "^# " knowledge/wiki/concepts/ knowledge/wiki/events/ knowledge/wiki/structures/ \
  | grep -i "<termin>"
```

- Ako postoji druga stranica sa H1 koji definiše isti pojam → **FAIL** (redefinisanje)
- Ako nova stranica dodaje applied case postojećeg pojma (npr. "Spring u low-liquidity crypto") → **OK** ako linkuje `[[spring]]` i ne ponavlja definiciju
- Ako je termin uveden prvi put → **OK**

### 3.3 Cross-link semantic

Uzmi **2 `[[backlink]]`-a** iz stranice. Otvori target stranice. Proveri:

- Da li target sadržaj opravdava link? (Ne samo da target postoji.)
- Da li je veza usmerena (npr. event linkuje containing structure) — per CLAUDE.md §8?

Random/dekorativni linkovi (npr. `[[market-cycle]]` na svakoj stranici "jer je relevantan") → **CONCERN**, ne FAIL.

### 3.4 Vocabulary precision + synthesis discipline

Skeniraj stranicu za:

- **Wyckoff termine** — koristi se baš izrazom iz knjige? ("Sign of Strength", "spring", "secondary test")
- **Market žargon** — generički izrazi koji bi mogli zameniti precizan termin? ("breakout" umesto "JAC", "buyers step in" umesto "AR", "support holds" umesto "ST as MSOS")
- **Synthesis-as-claim** — sekcije tipa "Common Mistakes The Book Flags", "Typical Failures", "Recurring Patterns" bez `> **Synthesis:**` marker-a i bez inline citacija → **CONCERN** (per runbook §3.5)

Žargon umesto preciznog termina kada je precizan dostupan → **CONCERN**. Žargon u meta-pasusu (npr. uvod) je OK.

---

## 4. Izveštaj format

Za svaku sample stranicu:

```markdown
### `knowledge/wiki/events/spring.md`

| Provera | Status | Beleška |
|---|---|---|
| Source fidelity | PASS | Obe tvrdnje directly stated u `raw/book/pages/page_142.md` |
| Definition uniqueness | PASS | Nova definicija — pre nije bilo `events/spring.md` |
| Cross-link semantic | CONCERN | `[[market-cycle]]` deluje dekorativno; spring nije direktno o cycle-u |
| Vocabulary precision | PASS | Koristi "spring", "test", "secondary test" — knjiški |
```

Na kraju, **agregat**:

```markdown
## Ukupno
- 5 stranica pregledano
- 0 FAIL, 2 CONCERN, 18 PASS
- **Akcija:** merge (CONCERN-i ne blokiraju, ali zabeleženi za batch follow-up)
```

---

## 5. Akcija na osnovu rezultata

| Stanje | Akcija |
|---|---|
| Sve PASS | Merge. Komentar na PR-u opcionalan. |
| CONCERN-i bez FAIL | Merge dozvoljen. Ako je ≥3 CONCERN-a istog tipa (npr. 3× vocabulary) → zapiši u `log.md` open follow-up za sledeći batch. |
| 1–2 FAIL u 1 stranici | Spot-fix direktno u PR-u (`git commit --fixup` u kildu ili novi commit). Re-run spot-check za tu stranicu. |
| ≥3 FAIL ili FAIL-ovi preko više stranica | **Vrati u batch kild.** Pošalji listu problema kao prompt batch agentu, traži rebuild. Ne mergaj. |

---

## 6. Output contract

Spot-check sesija završava sa:

- Markdown izveštajem (struktura iz §4) — daj user-u u chat-u, ne commit-uj u repo
- Eksplicitnom akcijom (merge / spot-fix / back-to-kild)
- Ako CONCERN-i ostaju nakon merge-a — entry u `log.md` kao "spot-check follow-up Batch N"

Spot-check izveštaj **nije** PR komentar po default-u — ostaje između reviewer-a i user-a dok se ne odluči akcija.
