---
title: "Playbook — Master Scenario Tree"
type: scenario
status: active
updated: 2026-06-09
primary_source: book
sources:
  - path: raw/book/pages/page_184.md
    note: "Phase C verification — the branch point of the tree"
  - path: raw/book/pages/page_185.md
    note: "shake / no-shake / shake-fails — the three Phase C outcomes"
---

# Playbook — Master Scenario Tree

## Summary

This is the **top-level decision tree** for a Wyckoff read. It does not contain
trade calls (`/CLAUDE.md` §9); it routes an observed structure to the scenario
template that matches it, and names the evidence each branch needs. The leaf
templates ([[accumulation-phase-c-entry]] and siblings) carry the detailed
trigger / invalidation logic.

> **Synthesis:** The tree composes the phase model ([[phase-a]]–[[phase-e]]),
> the structure taxonomy ([[structures/accumulation]] and siblings), and the
> Phase C three-outcome framework
> ([book p.184–185](../../../raw/book/pages/page_184.md)) into a single
> navigation order. No raw source states the tree as such; each branch's claims
> are cited on the page it links to.

## The Tree

### Step 0 — Context before pattern

Always resolve context first ([[buying-selling-neutral-position]],
[[market-cycle]]). A pattern in the wrong background is noise
([[path-of-least-resistance]]). In crypto, run [[crypto-rotation-watch]] in
parallel — the intermarket gate ([[intermarket-gate]]) and BTC leadership
([[bitcoin-leader-vs-funding-source]]) can veto an otherwise clean structure.

### Step 1 — Is the range purposeful?

If the range is random balance, there is no campaign to trade
([[random-vs-purposeful-range]]). Only a purposeful range — one being built by
an operator — routes further down the tree.

### Step 2 — Which structure?

Classify the range ([[trading-range]]):

- Stopping a **downtrend** → [[structures/accumulation]]
- Pause **within an uptrend** → [[structures/reaccumulation]]
- Stopping an **uptrend** → [[structures/distribution]]
- Pause **within a downtrend** → [[structures/redistribution]]

This decides whether Phase C will shake **down** (spring, accumulation side) or
**up** (UTAD, distribution side).

### Step 3 — Which phase?

Read Phase A–E ([[phase-a]], [[phase-b]], [[phase-c]], [[phase-d]],
[[phase-e]]). The phase decides which leaf template applies:

| Phase | Accumulation side | Distribution side |
|---|---|---|
| C (test) | [[accumulation-phase-c-entry]] | [[distribution-phase-c-entry]] |
| C (no shake) | [[no-shake-foothold]] | [[no-shake-foothold]] |
| D (breakout test) | [[phase-d-breakout-test]] | [[phase-d-breakout-test]] |

### Step 4 — Phase C branch: the three outcomes

Per the book's framework ([book p.185](../../../raw/book/pages/page_185.md)):

1. **Shake confirms** → spring ([[spring]]) or UTAD
   ([[upthrust-after-distribution]]) prints, its test holds → go to the matching
   Phase C entry template.
2. **Shake fails** → the probe finds opposite-side participation. Either the
   campaign is abandoned, or Phase B extends. Treat the failed probe as fresh
   information ([[failed-signal]]), not as a setup.
3. **No shake** → absorption was thorough; the structure resolves through an
   internal [[last-point-of-support]] / [[last-point-of-supply]] →
   [[no-shake-foothold]].

### Step 5 — Phase D branch: confirmation and continuation

Once Phase C resolves, Phase D is the trend within the range
([[phase-d]]): [[sign-of-strength]] / [[sign-of-weakness]], the
[[jump-across-the-creek]] / [[fall-through-the-ice]], the back-up
([[back-up-to-the-edge-of-the-creek]]), and the [[last-point-of-support]] /
[[last-point-of-supply]]. This is [[phase-d-breakout-test]].

### Step 6 — Express as a scenario tree

Hand the resolved branch to the scenario-mode contract
([[output-contract]] §Scenario mode): leading scenario + at least one alternate,
each with trigger, invalidation, expected path, intermarket dependency, and
evidence quality.

## Why It Matters For Wyckoff Reading

- It encodes **context-before-pattern** and **structure-before-phase** as a
  fixed order, so the skill cannot jump to "this is a spring" before establishing
  that a purposeful accumulation range even exists.
- It makes the three Phase C outcomes (confirm / fail / no-shake) first-class, so
  a failed shake is handled as information rather than ignored.
- Every leaf is a separate template, so the trigger/invalidation detail lives
  with the evidence, not in the router.

## Links

- Response contract: [[output-contract]]
- Leaf templates: [[accumulation-phase-c-entry]], [[distribution-phase-c-entry]],
  [[phase-d-breakout-test]], [[no-shake-foothold]], [[crypto-rotation-watch]]
- Phases: [[phase-a]], [[phase-b]], [[phase-c]], [[phase-d]], [[phase-e]]
- Structures: [[structures/accumulation]], [[structures/distribution]],
  [[structures/reaccumulation]], [[structures/redistribution]],
  [[trading-range]]
- Discipline: [[random-vs-purposeful-range]], [[path-of-least-resistance]],
  [[labeling-is-last-step]]
