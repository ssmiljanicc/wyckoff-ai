---
title: "E2E Test Set — 8 Canonical Prompts"
type: scenario
status: active
updated: 2026-06-09
primary_source: book
sources:
  - path: raw/book/pages/page_184.md
    note: "Phase C semantics underpin the diagnostic and scenario prompts"
---

# E2E Test Set — 8 Canonical Prompts

## Summary

The fixed prompt set for skill validation (#13). Each prompt names its expected
**mode** (per [[output-contract]]) and the wiki pages a contract-compliant answer
must route through. This is a test harness, not a Wyckoff knowledge claim:
"correct" means the answer picks the right mode, follows that mode's contract,
and cites the listed pages — not that it reaches a particular trade conclusion.

Target: **≥ 6 of 8** prompts produce contract-compliant output (Faza 1 PRD).

## Concept Mode (3)

1. **"What is a spring?"**
   - Mode: concept. Must: short definition, cite [[spring]], name related
     [[upthrust-after-distribution]] / [[phase-c]], one worked example. Must
     **not** emit the nine-section scenario contract.
2. **"What's a no-shake Phase C?"**
   - Mode: concept. Must: cite [[no-shake-phase-c]], explain LPS/LPSY as the
     primary trade, link [[no-shake-foothold]].
3. **"Difference between a spring and an upthrust after distribution?"**
   - Mode: concept. Must: contrast [[spring]] vs [[upthrust-after-distribution]]
     as mirror Phase C shakes; correct directional framing.

## Diagnostic Mode (3)

4. **"BTC 1d just printed a low below the 6-week range support on a long lower
   wick, then closed back inside the range on elevated volume. What is this?"**
   - Mode: diagnostic. Must: describe price/volume **before** labeling
     ([[labeling-is-last-step]]); name spring as the candidate; state it is not
     confirmed until it causes the upward break
     ([book p.142](../../../raw/book/pages/page_142.md)); cite [[spring]].
5. **"ETH has ranged ~8 weeks after a downtrend; volume is falling; the last
   probe of the highs reversed quickly back into the range. What phase?"**
   - Mode: diagnostic. Must: identify likely Phase B accumulation with a UA /
     mSOS read ([[st-as-msos]], [[phase-b]]); avoid premature spring call.
6. **"Is this accumulation or distribution? Range stopped an uptrend; upper-end
   probe took out the highs on strong volume then fell back below resistance."**
   - Mode: diagnostic. Must: lean distribution; name UTAD candidate
     ([[upthrust-after-distribution]]); cite the labeling discipline.

## Scenario Mode (2)

7. **"Build a Wyckoff scenario for BTC 1d at $42k after a 6-week range."**
   - Mode: scenario. Must: full nine-section contract ([[output-contract]]);
     route through [[playbook-master]]; include leading + alternate; explicit
     trigger / invalidation; crypto overlay ([[crypto-rotation-watch]]); end with
     go / wait / no-trade.
8. **"LINK has been ranging for weeks while BTC just sprang and the Nasdaq is
   basing. What's the setup?"**
   - Mode: scenario. Must: nine-section contract; intermarket gate first
     ([[intermarket-gate]]); detect-on-spread / execute-on-USD
     ([[spread-charts]]); [[accumulation-phase-c-entry]] evidence sequence;
     no bare trade call.

## Links

- Contract: [[output-contract]] · Router: [[playbook-master]]
- Scenarios exercised: [[accumulation-phase-c-entry]],
  [[distribution-phase-c-entry]], [[no-shake-foothold]],
  [[crypto-rotation-watch]]
- Discipline checked: [[labeling-is-last-step]]
