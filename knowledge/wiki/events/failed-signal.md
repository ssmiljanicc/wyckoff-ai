---
title: "Failed Signal (Failed Spring / Failed UTAD / Failed Breakout)"
type: event
status: active
updated: 2026-05-25
sources:
  - path: raw/book/pages/page_141.md
    note: "labeling discipline — a shake that does not cause the eventual range break is not a Spring/UTAD"
  - path: raw/book/pages/page_142.md
    note: "post-break re-entry signature; price failing to stay outside = false break"
  - path: raw/book/pages/page_158.md
    note: "no-re-entry as the diagnostic for genuine break; converse = failed signal"
  - path: raw/book/pages/page_160.md
    note: "SOS fails → labeled as UT; symmetric for SOW → Spring/JAC"
  - path: raw/book/pages/page_170.md
    note: "wide-range high-volume retest cancels the break — likely a Shake"
  - path: raw/book/pages/page_187.md
    note: "Chapter 24 — third Phase D scenario: failed break + new Phase C shake to opposite side"
---

# Failed Signal (Failed Spring / Failed UTAD / Failed Breakout)

## Summary

A **failed signal** in Wyckoff is any event that **appears** to produce
the expected structural resolution but is invalidated by the price
action that follows. The most operationally relevant forms:

- **Failed Spring** — a downside probe that does not produce a
  subsequent SOS; the upward thesis collapses and the structure resolves
  bearishly.
- **Failed UTAD** — an upside probe that does not produce a subsequent
  SOW; the downward thesis collapses.
- **Failed Breakout (SOS / SOW)** — a Phase D break that fails to hold
  outside the range; price re-enters the structure and the labeled
  break is retroactively reclassified.

The book is explicit on the discipline
([book p.141](../../raw/book/pages/page_141.md)): a shake is only
labeled [[spring]] / [[upthrust-after-distribution|UTAD]] **if it
causes the eventual range break**. Anything else is "just a test" — by
construction these were potential events whose status is settled by
what follows.

This page is a placeholder for Batch 2 — Bruce Fraser and crypto
archive will populate the specific failure modes with examples.

## Key Points

### How Failure Is Diagnosed — No-Re-Entry Rule

The book's primary diagnostic ([book p.158](../../raw/book/pages/page_158.md)):

> "The most powerful indication for valuing breakout as genuine is that
> the price manages to stay out of the range."

The contrapositive defines a failed signal: if price **re-enters the
range** after the apparent break, the break is false. The methodology
relabels the move:

- **Bullish break that re-enters** → [[upthrust|Upthrust (UT)]]
  ([book p.160](../../raw/book/pages/page_160.md)).
- **Bearish break that re-enters** → [[spring|Spring]] / Jump Across
  the Creek — i.e. the supposedly bearish event was actually a
  shake for an accumulation that hadn't been recognized yet.

### The Confirmation Test As Distinguisher

The Phase D confirmation event ([[back-up-to-the-edge-of-the-creek|BUEC]]
/ [[fall-through-the-ice|FTI]] / LPS / LPSY) is where the failure
becomes diagnosable
([book p.169–170](../../raw/book/pages/page_169.md)):

- A confirmation test with **narrow ranges and low volume** → genuine
  break.
- A confirmation test with **wide ranges and high volume** → very
  likely a failed signal; price likely returns to the range.

This is why the book is so insistent on waiting for the confirmation
test before entering — entering on the break itself exposes the trader
to converting a profitable trade into a stopped-out one when the
"break" was actually a UT (or symmetric).

### Phase D Has Three Possible Outcomes

The book enumerates Phase D scenarios
([book p.187](../../raw/book/pages/page_187.md)):

1. **Successful break + confirmation test** → markup / markdown begins
   (Phase E).
2. **Attempt fails at Creek/Ice → fall back to an internal LPS / LPSY
   → next attempt may succeed.** Not a failed signal in the strict
   sense; the structure simply takes another run at the boundary.
3. **Attempt fails + new Phase C shake to the opposite side → range
   resolves the other way.** This is the **failed signal** scenario:
   what looked like (e.g.) an accumulation was actually a
   distribution, and the bullish break failed to materialize while
   the eventual move came down through the lower boundary.

Scenario 3 is the most damaging diagnostic mistake. It means the
trader was on the wrong side of the structure throughout. The book
notes ([book p.187](../../raw/book/pages/page_187.md)) that "higher
forces have been absorbing in the opposite direction" via a much more
discreet absorption campaign — the structural read was misread because
the dominant operator's intent was the opposite of what the visible
events suggested.

### Trade Implications

- **Stop loss discipline:** the structural stop (below spring low,
  above UTAD high) catches the failed-signal case at known cost.
  Skipping the stop because "the structure is clear" turns failed
  signals into catastrophic losses.
- **Re-entry rule:** when a failed signal becomes evident, the
  failed-direction trade is closed at stop; the opposite-direction
  trade has its own structure to wait for (a new Phase C event in the
  reversed direction).
- **Probabilistic framing:** see [[concepts/labeling-is-last-step]] —
  in real time the trader assigns probabilities; the failed signal is
  the path where the lower-probability scenario printed.

## Status — Placeholder Until Fraser / Crypto Batches

This page records what the book of Phase D / Phase E confirmation
chapters says about failure modes. The richer treatment — specific
failed-spring case studies, crypto-specific failure modes, the "second
chance" entries the Fraser archive discusses — will land in later
batches:

- Crypto archive (Batches 4–5): vol 27 March 2020 BTC has a famous
  near-failed spring example worth a case-study link from here.
- Bruce Fraser (Batches 6–9): "Pruning the line" articles cover
  failed-signal recovery sequences.

## Why It Matters For Wyckoff Reading

- The label `[[spring]]` / `[[upthrust-after-distribution|UTAD]]` is
  always provisional in real time. The discipline of "label after the
  fact" protects against committing too early.
- A failed signal is not a defect of the methodology — it is the
  methodology working as designed (the confirmation test exists
  precisely to surface the failure).
- The third Phase D scenario (failed break + opposite Phase C shake)
  is the highest-cost diagnostic error in the methodology.

## Links

- Failed-spring source: [[spring]], [[upthrust]] (when a "spring"
  re-enters the range, see the relabeling discussion in [[spring]])
- Failed-UTAD source: [[upthrust-after-distribution]], [[spring]] /
  [[jump-across-the-creek]]
- Confirmation events: [[back-up-to-the-edge-of-the-creek]],
  [[fall-through-the-ice]], [[last-point-of-support]],
  [[last-point-of-supply]]
- Phase: [[concepts/phase-c]], [[concepts/phase-d]]
- Methodology: [[concepts/labeling-is-last-step]],
  [[concepts/action-test-confirmation]]
- Sources: [[book-chapter-18]], [[book-chapter-19]],
  [[book-chapter-20]], [[book-chapter-24]]
