# Wyckoff AI — PRD pregled (srpski)

Ovaj folder sadrži sve PRD dokumente projekta. Konvencija: `.prd.md` po `prp-prd` standardu (`.claude/PRPs/prds/`).

## Tri faze, tri PRD-a

Projekat je razdvojen u tri jasno odvojene faze. Razlog razdvajanja: **prva faza ide nazad u upstream repo**, druga i treća su interne ekstenzije van prvobitne vizije.

```
┌─────────────────────────────────────────────────────────────┐
│  FAZA 1: Skill Modernization                                │
│  → unapređenje postojećeg skill-a u skladu sa vizijom       │
│    originalnog naiemk/wyckoff-ai repo-a                     │
│  → kontribucija upstream-u (PR + opciono unfork)            │
│  → milestones M1, M2, M3                                    │
│  → faza-1-skill-modernization.prd.md                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
                  završena, PR upstream
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FAZA 2: Live Market Analysis (MCP)                         │
│  → MCP serveri za OHLCV, chart rendering, spread charts     │
│  → agent može autonomno da analizira "BTC 1d" bez user      │
│    input-a osim simbola                                     │
│  → milestone M4                                             │
│  → faza-2-live-market-analysis.prd.md                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FAZA 3: Trading Simulation & ML Extensions                 │
│  → virtual portfolio + scanner + signal logger + backtest   │
│  → ML pipeline: annotation → features → classifier → MCP    │
│  → Signal mod u skill-u (4. mod posle scenario/concept/     │
│    diagnostic)                                              │
│  → milestones M5, M6                                        │
│  → faza-3-trading-and-ml.prd.md                             │
└─────────────────────────────────────────────────────────────┘
```

## Šta svaki PRD pokriva

### [Faza 1 — Skill Modernization](./faza-1-skill-modernization.prd.md)

**Šta:** rebuild postojećeg skill-a sa provenance-tracked wiki-jem, recovered chart slikama, Vision captions, clean book extraction i tri-mode output contract-om (scenario / concept / diagnostic).

**Zašto upstream:** sve ovo se uklapa u originalnu viziju `naiemk/wyckoff-ai` — edukativni Wyckoff analitičar. Poboljšanja su aditivna (wiki dodaje provenance, modovi rešavaju broken UX, slike dodaju ono što je nedostajalo) bez menjanja core ideje.

**Granica faze:** E2E validacija prolazi → PR otvoren ka upstream-u → odluka o unfork-u nakon merge-a.

**Issues (već postoje):** #2 ✓, #3 ✓, #4 (blokirano na PDF), #5, #6 ✓, #7, #8, #13
**Novi issues:** "Open upstream PR", "Decide fork detach"

---

### [Faza 2 — Live Market Analysis (MCP)](./faza-2-live-market-analysis.prd.md)

**Šta:** tri MCP servera (OHLCV, chart render, spread chart) koji daju agentu **ruke i oči** za autonomnu analizu. Skill iz Faza 1 ostaje mozak; MCP dodaje data sloj.

**Zašto interno:** nije bilo deo originalne vizije. Agent koji autonomno pulluje Binance API + render-uje chart + Vision-analizira je dovoljno različito od "skill koji čita user-opis chart-a" da bi bilo aditivno upstream-u.

**Granica faze:** "Analyze BTC 1d" sa samo simbolom kao input-om daje pun scenario output sa MCP tool-call trace-om.

**Issues (već postoje):** #9, #10, #11, #12
**Novi issues:** "Skill: integrate MCP into SKILL.md", "E2E Phase B validation"

---

### [Faza 3 — Trading Simulation & ML](./faza-3-trading-and-ml.prd.md)

**Šta:** dve paralelne ekstenzije:
1. **Trading Simulation MCP** — virtual portfolio, multi-symbol scanner, signal logger, backtest runner
2. **ML pipeline** — annotation → feature engineering → baseline RandomForest classifier → classifier kao MCP server

Plus 4. mod u skill-u: **Signal/Trading mode** sa output contract-om za signale (entry / invalidation / target / virtual position size).

**Zašto interno:** **eksplicitno van vizije originalnog repo-a.** Predstavlja transformaciju skill-a iz analitičkog alata u Wyckoff istraživačko/practice okruženje sa P&L feedback-om.

**Granica faze:** korisnik može da pokrene backtest strategije ("long na spring+retest, short na UTAD+LPSY") preko 3 godine BTC istorije sa stabilnim P&L izveštajem; ML klasifikator daje phase predikciju > 60% accuracy na test set-u.

**Issues:** sve nove — listirane na dnu PRD-3, biće kreirane uz ovaj commit.

---

## Pravila održavanja

1. **PRD-ovi su living documents** — kako se zatvori issue ili promeni odluka, PRD se ažurira (`Implementation Phases` tabela + `Decisions Log`)
2. **Issues referenciraju PRD** u svom body-ju (link na konkretan PRD fajl)
3. **PRD-ovi referenciraju issues** u `Linked GitHub Issues` sekciji
4. **Milestones na GitHub-u mapiraju 1:N na PRD faze** (Faza 1 = M1+M2+M3, Faza 2 = M4, Faza 3 = M5+M6)
5. **Faze ne preskaču** — Faza 2 ne počinje dok Faza 1 nije završena u smislu skill-rebuild-a; Faza 3 ne počinje dok Faza 2 osnovno nije gotova (osim ML annotation pipeline koji može krenuti čim Faza 1 wiki postoji)

## Konvencije iz prp-prd skill-a

- **Folder:** `.claude/PRPs/prds/` (umesto starog `prds/` koji je obrisan)
- **Naming:** `kebab-case-name.prd.md`
- **Template sekcije:** Problem Statement → Evidence → Proposed Solution → Hypothesis → What We're NOT Building → Success Metrics → Open Questions → Users & Context → Solution Detail (MoSCoW) → Technical Approach → Implementation Phases → Decisions Log → Research Summary
- **Status field na dnu:** DRAFT / ACTIVE / PLANNED / COMPLETED

## Kako se ovo razlikuje od starog `prds/` foldera

Pre 2026-05-24, koristili smo `prds/01-knowledge-base.md`, `prds/02-trading-use.md`, itd. Stari PRD-ovi su imali pravu suštinu ali:

- Nisu pratili prp-prd konvenciju (`.prd.md` naming, `.claude/PRPs/prds/` lokacija)
- Mešali su upstream-pogodne ideje (rebuild skill-a) sa internim ekstenzijama (MCP, ML) u istom dokumentu
- Faza 1a (analiza postojećeg skill-a) je bila zasebni fajl ali pravo mesto za to je sekcija "Evidence" + "Current State" u Faza-1 PRD-u

Novi struktura: 3 čista PRD-a po fazi, sa eksplicitnim "what we're NOT building" sekcijama koje razdvajaju faze.

---

## Sledeći koraci posle ovog commit-a

1. **Faza 1** je delom u toku — pratiti M1/M2/M3 issues
2. **Faza 2** PRD je gotov, čeka da Faza 1 završi pre konkretne implementacije (osim ako se odluči da MCP započne ranije)
3. **Faza 3** PRD je gotov, čeka da Faza 1 wiki bude bar 80% gotov pre annotation pipeline-a
4. **GitHub sync** uz ovaj commit: nove milestones (M5, M6), nove labele (`phase:1/2/3`), novi issues za Faza 3

---

*Poslednje ažuriranje: 2026-05-24*
