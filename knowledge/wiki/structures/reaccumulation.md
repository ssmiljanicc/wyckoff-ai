---
title: "Reaccumulation"
type: structure
status: active
updated: 2026-05-25
sources:
  - path: raw/book/pages/page_077.md
    note: "Chapter 11 intro — reaccumulation = accumulation mechanically; only difference is prior trend direction"
  - path: raw/book/pages/page_078.md
    note: "stock-control dynamic; duration influenced by strong/weak hand mix"
  - path: raw/book/pages/page_079.md
    note: "reaccumulation vs distribution — both start after stopping an upward move; key disambiguation"
  - path: raw/book/pages/page_148.md
    note: "Ordinary Shakeout — Phase C variant in reaccumulation (bearish push during an uptrend)"
---

# Reaccumulation

## Summary

**Reaccumulation** is mechanically **identical to [[accumulation]]**.
The single difference is the **prior trend direction**: accumulation
starts after a stop of a downward move; reaccumulation starts after a
stop of an upward move
([book p.77](../../raw/book/pages/page_077.md)).

It is a pause within an existing bullish trend, after which the
markup resumes. The structure rebuilds strong-hand control of stock
that has gradually drifted to weak hands during the prior uptrend
([book p.78](../../raw/book/pages/page_078.md)).

## Key Points

### Why Reaccumulation Happens

At the start of an uptrend, stock is largely in strong hands. As the
trend develops, stock gradually shifts to weak hands — late buyers
who entered at progressively higher prices
([book p.78](../../raw/book/pages/page_078.md)). When this drift
makes demand "of poor quality", the trend pauses for a fresh
absorption cycle: the operator buys back stock from weak hands to
re-establish control before the next leg up.

The objectives of the primary accumulation are not yet met. The
reaccumulation refreshes the cause for further markup.

### Duration Is Influenced By Strong/Weak Hand Mix

Critical structural property
([book p.78](../../raw/book/pages/page_078.md)):

- **Stock mostly in strong hands at the start of reaccumulation** →
  **shorter** duration. Less absorption work needed.
- **Stock mostly in weak hands** → **longer** duration. The operator
  must rebuild positions from scratch.

This is one of two cycle-position properties driving structure
duration. The other is the [[concepts/cause-and-effect|cause-effect]]
relationship between cause-building and expected trend magnitude.

### Same Events As Accumulation

Reaccumulation uses the **identical event vocabulary** as
[[accumulation]] — PS, SC, AR, ST, UA, ST-as-SOW, spring, LPS, SOS,
JAC, BUEC. The schematics #1 (with shake) and #2 (no-shake) apply
equally.

The only event-level difference: in reaccumulation, the Phase C shake
is sometimes labeled an **Ordinary Shakeout** rather than a Spring
([book p.148](../../raw/book/pages/page_148.md)):

> "An Ordinary Shakeout … is defined as a strong bearish push without
> extensive prior preparation that occurs during the development of
> an uptrend (reaccumulation). This is the main difference: the
> location."

The Ordinary Shakeout has wider price ranges and increased volume but
volume can be high, medium, or low. The function is identical to a
spring — liquidity grab before the trend continues.

### The Disambiguation Problem — Reaccumulation vs Distribution

The book frames this as "one of the most compromising situations
that any Wyckoff trader will encounter"
([book p.79](../../raw/book/pages/page_079.md)). Both structures
**start the same way**: after the stop of an upward move.

In real time, Phase A is identical. The trader must use Phase B
diagnostics to disambiguate:

- **Weak AR (small, intertwined, no volume peak), ST above the BC
  high** → leans toward reaccumulation (see
  [[events/automatic-reaction]]).
- **Phase B character: volume stays high, volatility persists** →
  leans toward distribution.
- **Phase B character: volume decreases, range narrows** → leans
  toward reaccumulation.
- **Phase B testing direction: clean UA / mSOS at the high** → leans
  toward reaccumulation.
- **Phase B testing direction: clean mSOW at the low, UT at the high
  fails to extend** → leans toward distribution.

These are probabilistic inputs, not deterministic signals. The
structure is finally confirmed at the Phase D break — see
[[events/failed-signal]] for the misread case.

### Operational Implications

- **Trade in the direction of the higher-timeframe trend.** A
  reaccumulation in an uptrend is best traded long — the methodology
  recommends "trade in favour of the larger structure". See
  [book p.192](../../raw/book/pages/page_192.md) (Part 7, ingest in
  Batch 3).
- **Entries are the same as accumulation:** Spring entry (Phase C),
  LPS entry (Phase D), BUEC entry (Phase D out-of-range).
- **The misclassification cost is high.** Treating a distribution as
  a reaccumulation means staying long into a markdown.

## Why It Matters For Wyckoff Reading

- Reaccumulation explains how a long uptrend keeps going — through
  successive cause-rebuilding pauses, not in a single straight line.
- The disambiguation against distribution is the methodology's most
  practically important diagnostic. Misreading is expensive.
- The duration-by-stock-mix rule gives early signal on how long the
  pause will last (and therefore how much markup follow-through to
  expect).

## Links

- Identical mechanics: [[accumulation]] (read first)
- Disambiguation partner: [[distribution]]
- Phase C variant: [[events/spring]] (Ordinary Shakeout variant
  documented inside the spring page)
- Phases: [[concepts/phase-a]], [[concepts/phase-b]],
  [[concepts/phase-c]], [[concepts/phase-d]], [[concepts/phase-e]]
- Cycle position: [[concepts/market-cycle]]
- Diagnostic concept: [[concepts/cause-and-effect]]
- Failure mode: [[events/failed-signal]]
- Sources: [[book-chapter-11]], [[book-chapter-18]]
