---
title: "Scenario — Crypto Rotation Watch"
type: scenario
status: active
updated: 2026-06-09
primary_source: crypto_archive
sources:
  - path: raw/crypto_archive/html/wyckoff-crypto-report-59.html
    note: "Nasdaq low as the entry gate for crypto spring candidates (LINK, DOT)"
  - path: raw/crypto_archive/html/wyckoff-crypto-report-vol-33.html
    note: "start altcoin analysis on USD pair, use BTC pair as confirmation"
  - path: raw/crypto_archive/html/wyckoff-crypto-report-vol-36.html
    note: "sustainable rally needs capital flowing from Bitcoin into mid/low caps"
---

# Scenario — Crypto Rotation Watch

## Summary

The crypto overlay that runs **in parallel** with every structural read. It does
not replace the book scenarios; it gates and refines them. Evidence checklist,
not a trade call (`/CLAUDE.md` §9). Leaf of [[playbook-master]] step 0 (context
before pattern), invoked from every other scenario's "Crypto Overlay" section.

> **Synthesis:** This template sequences four archive tools — the
> [[intermarket-gate]], the [[rotation-hierarchy]], [[comparative-strength]], and
> [[spread-charts]] — into one watch order. Each tool's claims are cited on its
> own page; the ordering here is the composition.
> Sources: [[intermarket-gate]], [[rotation-hierarchy]], [[comparative-strength]], [[spread-charts]]

## Watch Order

1. **Intermarket gate first.** Check S&P / Nasdaq behavior
   ([[intermarket-gate]]). A crypto setup carries lower quality if the gate is
   hostile; a final Nasdaq low can be the literal entry signal for crypto names
   already in spring position
   ([vol 59](../../../raw/crypto_archive/html/wyckoff-crypto-report-59.html)).
2. **Rotation tier.** Locate where capital sits in the hierarchy — Bitcoin,
   large caps, mid caps, small/micro caps, themes ([[rotation-hierarchy]]). A
   durable rally typically needs flow **from Bitcoin into mid and low caps**
   ([vol 36](../../../raw/crypto_archive/html/wyckoff-crypto-report-vol-36.html));
   micro-cap leadership is double-edged (can mark exhaustion).
3. **Comparative strength.** Rank candidates by in-gear behavior
   ([[comparative-strength]]). Outperformance during equity weakness is
   constructive; underperformance during equity strength is a warning.
4. **Detect on spread, execute on USD.** Use altcoin/BTC spread charts
   (ETHBTC, LINKBTC) to **detect** leadership and rotation, then look for the
   entry on the **USD pair**
   ([vol 33](../../../raw/crypto_archive/html/wyckoff-crypto-report-vol-33.html))
   ([[spread-charts]]).

## Trigger, Invalidation, Path

- **Supportive evidence:** gate is risk-on (or crypto is outperforming a weak
  equity tape), rotation flow favors the candidate's tier, and the spread chart
  confirms leadership while the USD pair shows a clean structural setup.
- **Veto evidence:** hostile intermarket gate, rotation draining away from the
  candidate's tier, or spread-chart leadership contradicting the USD-pair read.
- **Path note:** this overlay changes *conviction and selection*, not the
  structural label. A spring is still a spring; the overlay decides whether to
  act on it and which instrument to use.

## Crypto-Specific Cautions

- Low-liquidity names print climactic tails and faked breaks more often
  ([[low-liquidity-tolerance]]) — weight confirmation tests more heavily.
- In risk-off, watch the [[risk-off-refuge-hierarchy]] (Tether → BTC → alts) for
  where capital flees; BTC can act as [[bitcoin-as-source-of-funding|a source of
  funding]] for alts during stress.

## Links

- Router: [[playbook-master]] · Contract: [[output-contract]]
- Crypto tools: [[intermarket-gate]], [[rotation-hierarchy]],
  [[comparative-strength]], [[spread-charts]],
  [[bitcoin-leader-vs-funding-source]]
- Crypto cautions: [[low-liquidity-tolerance]], [[risk-off-refuge-hierarchy]],
  [[bitcoin-as-source-of-funding]]
- Structural scenarios gated by this overlay: [[accumulation-phase-c-entry]],
  [[distribution-phase-c-entry]], [[phase-d-breakout-test]],
  [[no-shake-foothold]]
