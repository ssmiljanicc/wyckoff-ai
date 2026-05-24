# PRD-02 — Sažetak (faza 2: trading use)

**Originalni dokument:** [`prds/02-trading-use.md`](./02-trading-use.md) (engleski, draft sa [ASSUMED] flagovima)
**Svrha ovog sažetka:** brzi pregled svih 12 poglavlja sa generalnom idejom i jasnim izvorom za svaku tvrdnju ili pretpostavku.

## Legenda izvora

- 🔵 **Originalni skill** — verbatim preneto iz `skills/wyckoff-trader-skill/` (postojeća verzija u repo-u, koja je forkovana sa `naiemk/wyckoff-ai`)
- 🟡 **Hibrid** — generalna ideja postoji u originalnom skill-u, ali sam je formalizovao ili proširio
- 🟢 **Moja pretpostavka** — nije postojalo u originalu, mislim da bi bilo korisno

---

## 1. Ko je korisnik

**Generalna ideja:** skill je za **solo tradera / Wyckoff praktikanta** koji već razume vokabular i traži discipliniranu scenario analizu, sekundarno za **Wyckoff studenta** srednjeg nivoa. Nije za botove, algo signale, ili kompletne početnike.

**Izvor:** 🟡 — Postojeći `SKILL.md` description kaže "build Wyckoff-based market scenarios, especially for crypto assets" što implicitno targetuje praktikanta sa vokabularom. **Moja dorada:** razdvajanje na primary (trader) i secondary (student), kao i eksplicitno isključivanje botova.

---

## 2. Tri moda agenta

**Generalna ideja:** agent operiše u jednom od tri moda zavisno od pitanja:
- **Scenario** — pun 9-sekcijski output (kao postojeći skill)
- **Concept** — kratka definicija + wiki citati (za "šta je spring?")
- **Diagnostic** — verdict + evidence (za "u kojoj smo fazi?")

**Izvor:** 🟢 — **Moja pretpostavka.** Postojeći skill primenjuje 9-sekcijski contract na SVAKO pitanje, što je broken UX za kratka pojmovna pitanja. Mode discriminator je verovatno najveće poboljšanje predloženo u ovom PRD-u. **Najvažnije pitanje za potvrdu od tebe.**

---

## 3. Reprezentativni set pitanja (8 query-ja)

**Generalna ideja:** 8 konkretnih korisničkih query-ja koji pokrivaju sva tri moda. Postaju test set za #13 Phase A validaciju.

**Izvor:** 🟡 — Postojeći "When To Use It" sekcija u SKILL.md lista tipove pitanja apstraktno (springs, leadership, scenarios). **Moja dorada:** konkretizovani primeri sa simbolima i opisima ("BTC 1d konsoliduje na $42k nakon 6-nedeljnog rangea..." itd.).

---

## 4. Šta korisnik pruža (input contract)

**Generalna ideja:** agent prima tri input shape-a:
- samo simbol + timeframe ("BTC 1d")
- simbol + opis scenarija (verbalno)
- upload-ovan chart image

**Izvor:** 🟢 — **Moja pretpostavka.** Postojeći skill implicitno pretpostavlja samo treću opciju (korisnik opisuje chart). Eksplicitno tri shape-a je posebno bitno za MCP integraciju (sa live data dva prva moda postaju upotrebljiva).

---

## 5. Granice (šta agent NIKAD ne radi)

**Generalna ideja:** 6 eksplicitnih zabrana:
- nema buy/sell signala
- nema position sizinga
- nema price target-a kao obavezujućih
- nema prediction language-a
- nema emocionalnog tona
- nema labela bez evidence

**Izvor:** 🟡 — Postojeća core rules već imaju "scenarios not certainties", "label last", "no-trade is valid". **Moja dorada:** eksplicitno svih 6 zabrana kao numerisana lista, da #8 rewrite ne odluta i ne uvede signal-feeling output.

---

## 6. Failure modes

**Generalna ideja:** propisano ponašanje kad situacija nije čista — ambivalentan chart, konfliktni TF-ovi, manjak intermarket data, query van wiki coverage, korisnik traži buy signal.

**Izvor:** 🟢 — **Moja pretpostavka.** Postojeći skill ima jedno globalno pravilo "mixed evidence → no-trade". Razloženo na 6 specifičnih situacija sa propisanim odgovorom da bi rebuild bio konzistentan u edge case-ovima.

---

## 7. Intermarket / cross-asset behavior

**Generalna ideja:** intermarket dubina zavisi od klase asset-a:
- BTC/ETH: uvek se proverava S&P/Nasdaq, dolar, BTC dominance
- major alts (LINK, SOL, AVAX): BTC leadership + sector index
- low caps: BTC + sector + thematic peers
- spread charts: oba leg-a u USD

**Izvor:** 🟡 — Postojeći `crypto_adaptations.md` §1 eksplicitno kaže "intermarket je hard gate". **Moja dorada:** tabela ponašanja po klasi asset-a, jer original ne diferencira nivo provere po veličini asset-a.

---

## 8. Multi-timeframe (MTF) politika

**Generalna ideja:** agent UVEK pulluje/razmatra jedan TF iznad zatraženog (HTF kontekst). Niži TF samo na eksplicitan zahtev.

**Izvor:** 🟡 — Postojeći SKILL.md §1 traži "higher-timeframe cycle position" u kontekstu. **Moja dorada:** politika "1 iznad uvek, niži na zahtev" je eksplicitna, da agent ne pulluje pretreranu količinu podataka.

---

## 9. MCP scope (must-have vs nice-to-have)

**Generalna ideja:**
- **Must-have:** OHLCV, chart render, spread chart (#9, #10, #11)
- **Nice-to-have (defer):** BTC dominance helper, context chain, sector index
- **Cut:** real-time streaming (agent je request/response, ne stream)

**Izvor:** 🟢 — **Moja pretpostavka.** Postojeći skill nema MCP uopšte. Issues #9–#11 listaju tehnologiju, ali ne kategorizuju prioritete. Sečenje scope-a omogućava M4 prvu verziju bez svih bells-and-whistles.

---

## 10. Output contract (po modu)

**Generalna ideja:**
- **Scenario mode** zadržava 9-sekcijski format iz postojećeg skill-a (samo §9 "Decision" → "Tactical quality" sa kategorijama Phase C / D / E / watchlist / no-trade)
- **Concept mode** (nov): definicija + lokacija u Wyckoff-u + 1 worked example + sources + related
- **Diagnostic mode** (nov): verdict + 3-5 evidence bullets + alternative verdict + what would change

**Izvor:** 🟡 — Scenario contract je **100% iz postojećeg `scenario_playbook.md`** (samo manje preimenovanje sekcije 9). Concept i Diagnostic format-i su moja pretpostavka koja prirodno proističe iz mode discriminatora (§2).

---

## 11. Confirmation checklist

**Generalna ideja:** 9-stavka checklist koja se prolazi kroz draft (§1–§10) — kad sve flag-uješ kao [CONFIRMED] ili [REVISED], PRD-02 je gotov i #8 može da krene.

**Izvor:** 🟢 — Meta sekcija, **moja konstrukcija.** Služi kao formalni gate.

---

## 12. Šta propagira nakon finalizacije

**Generalna ideja:** tabela koja eksplicitno navodi koji artefakti se menjaju kad se PRD-02 zaključi: #8 body, SKILL.md, /CLAUDE.md required pages, #9/#11 (možda sečenje scope-a), #13 (test prompts).

**Izvor:** 🟢 — Meta sekcija, **moja konstrukcija.** Osigurava da PRD ne ostane "papir u praznom" — povlači concrete change-eve u druge artefakte.

---

## Ukupna ocena izvora po poglavljima

| Tip izvora | Poglavlja |
|---|---|
| 🔵 Verbatim iz originala | — (0 poglavlja) |
| 🟡 Hibrid (postojeća ideja + moja dorada) | §1, §3, §5, §7, §8, §10 (6 poglavlja) |
| 🟢 Moja pretpostavka | §2, §4, §6, §9, §11, §12 (6 poglavlja) |

## Tri najvažnije pretpostavke gde bih voleo eksplicitnu potvrdu

1. **Mode discriminator (§2)** — da li su 3 moda (Scenario / Concept / Diagnostic) prava podela? Postojeći skill ima samo Scenario mod. **Ovo je najveća promena u predloženom PRD-u.**
2. **Granice §5** — da li je sva 6 eksplicitnih zabrana ispravno? Posebno "no price targets as commitments" — postojeći skill ne kaže ovo direktno.
3. **MCP scope §9** — da li je sečenje na 3 must-have (OHLCV/chart/spread) i odlaganje nice-to-have prava odluka za M4? Ili treba sve odjednom?

Ostalo su uglavnom **formalizacije implicitnih odluka** koje postojeći skill već pravi (ali nikad ne piše).

---

## Šta NIJE u ovom PRD-u (eksplicitno)

- **Strategija promocije** ili distribucije skill-a
- **Pricing / monetizacija** (skill je open source, fork)
- **Konkretni model za vision / chart analysis** (vendor-agnostic)
- **Verzionisanje wiki-ja** (rešeno u PRD-01)
- **Plan za #8 implementaciju** (to dolazi u zaseban plan iz PRD-02 + PRD-01a)

---

**Stanje:** original draft (`prds/02-trading-use.md`) čeka tvoj review — flip-uješ [ASSUMED] u [CONFIRMED]/[REVISED]. Ovaj sažetak ti omogućava da to uradiš svesno (znaš šta je tuđe, šta je moje, gde si fleksibilan).
