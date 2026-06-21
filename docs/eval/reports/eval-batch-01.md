---
batch: "01"
date: "2026-06-21"
analyst_model: "claude-opus-4-8"
judge_model: "claude-opus-4-8"
effort: "high"
n_cases: 3
n_runs: 9
pricing_source: "2026-06-04"
---

# Eval izveštaj — Batch 01

## Ko je radio šta

| Komponenta | Model | Napomena |
|---|---|---|
| Analyst (analiza grafa) | claude-opus-4-8 / high | Jedan poziv po run-u |
| Judge (ocenjivanje) | claude-opus-4-8 / high | Jedan poziv po run-u |
| Canary validacija izolacije | claude-opus-4-8 | Urađena pre batcha, PROŠLA |
| Orchestrator / scoring / report | Python pipeline | Bez LLM troška |

## Case-ovi

| Case ID | Asset | Timeframe | Mode | Expert event | Expert autor |
|---|---|---|---|---|---|
| `btc_vol43_2020_11` | BTC | 4h | forward | spring | Alessio Rutigliano |
| `link_vol24_2020_06` | LINK | 1d | forward | backing_up | Alessio Rutigliano |
| `btc_vol24_2020_06` | BTC | 1d | retrospective | upthrust (absorption) | Alessio Rutigliano |

## Agregatni rezultati (blind, anon)

| Metrika | Batch 01 | Benchmark cilj |
|---|---|---|
| Aggregate | 0.6235 | — |
| **Expert alignment** | **0.5633** | — |
| Realized outcome | 0.7143 | — |
| Mean tokens | 3858 | — |
| Cost/call (USD) | 0.096 | — |
| ROI (skor/USD) | 6.49 | — |

## Po dimenziji

| Dimenzija | Batch 01 | Napomena |
|---|---|---|
| direction | **1.000** | Sve 3 case-a tačno |
| structure | 0.823 | Jak |
| narrative_quality | 0.717 | Solidan |
| calibration | 0.567 | Pod-konfidentan na decisive setup-ima |
| phase | 0.483 | Sistematski jedna faza ispred eksperta |
| event | **0.383** | Najslabiji — ključni gap |
| invalidation | 0.500 | Varijabilno |
| trigger | 0.500 | Varijabilno |

## Po event tipu

| Event tip | n | Aggregate |
|---|---|---|
| spring | 1 | 0.762 |
| upthrust | 1 | 0.643 |
| backing_up | 1 | 0.465 |

## Leakage i lookahead

| Metrika | Vrednost | Interpretacija |
|---|---|---|
| Δleakage (revealed − anon) | +0.0037 | ≈ 0 → anonimizacija radi; nema pretraining leakage |
| Δlookahead (future_visible − blind) | **−0.1009** | Negativno → buduće sveće ne pomažu, physical blinding nije potreban |

## Ključni zaključci

**Snage:**
- **Pravac: 100%** — program tačno čita bullish/bearish kontekst na svim 3 case-a
- **Struktura: 0.82** — akumulacija, re-akumulacija, distribucija — prepoznaje ispravno
- **Volumen mehanika** — climactic barovi, SOS impulsi, decline volumena — hronološki tačno

**Primarni gap vs. eksperti — event precision (0.38):**

Program ne razlikuje pouzdano:
1. *Backing up* (supply absorbovan, konstruktivan) od *thinning demand* (distribucioni signal) — ista vizuelna slika, suprotna implikacija
2. Spring koji tek dolazi od markup-a koji je već počeo (BTC: kaže Phase E umesto Phase C/D)
3. Absorption na supply nivou od distribucije — down-bar koji je ekspert čitao kao absorption, program čita kao resistance rejection

**Interpretivni sloj:** Ekspert razrešava dvosmislenost korišćenjem kontekstualnog lanca (ko drži pozicije, šta se desilo pre, koji deo ciklusa je). Program generalizuje na vizuelnim pattern-ima bez tog lanca.

**Δlookahead = −0.10 nalaz:** Physical blinding nije opravdan troška — as-of instrukcija je dovoljna.

## Troškovi batch-a

| Stavka | Vrednost |
|---|---|
| Ukupno runs | 9 |
| Ukupni trošak (est.) | ~$0.87 |
| Canary run (pre batch-a) | + ~$0.05 |

## Poređenje sa prethodnim batch-evima

*Batch 01 je prvi. Kolona "prethodni" biće popunjena u Batch 02.*

| Metrika | Batch 01 | Batch 02 | Δ | Trend |
|---|---|---|---|---|
| Expert alignment | 0.5633 | — | — | — |
| Event precision | 0.383 | — | — | — |
| Phase accuracy | 0.483 | — | — | — |
| Δlookahead | −0.101 | — | — | — |
| n cases | 3 | — | — | — |

## Sledeći batch (preporuke)

- **n:** 15–20 case-ova (statistički minimum za pouzdane trendove)
- **Event tipovi:** dodati SOW, LPS, LPSY, BC, SC za širi pokrivenost
- **Model varijacija:** testirati Sonnet (cost/quality tradeoff) uz Opus
- **Effort varijacija:** dodati `--effort medium` za poređenje
- **Autori:** diversifikovati van Rutigliano-a (Fraser, drugi crypto archive autori)
