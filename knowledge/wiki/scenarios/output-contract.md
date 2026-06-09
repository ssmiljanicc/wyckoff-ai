---
title: "Output Contract — Three Response Modes"
type: scenario
status: active
updated: 2026-06-09
primary_source: book
sources:
  - path: raw/book/pages/page_184.md
    note: "Phase C as the operational entry phase — anchors scenario-mode evidence"
  - path: raw/book/pages/page_142.md
    note: "labeling discipline — a read is provisional until the structure resolves"
---

# Output Contract — Three Response Modes

## Summary

This page defines **what an answer from the Wyckoff trader skill looks like**.
It is a skill design contract, not a Wyckoff source claim: the three-mode
structure is a project decision recorded in the Faza 1 PRD
(`.claude/PRPs/prds/faza-1-skill-modernization.prd.md`). The motivation is that
a single nine-section scenario template applied to every query — including a
plain definitional question like "what is a spring?" — is poor UX.

The skill answers in **one of three modes**. The first job of any response is to
pick the mode; the rest of the response follows that mode's contract.

> **Synthesis:** The mode taxonomy below composes the project's UX decision
> (Faza 1 PRD) with the Wyckoff discipline that labels are provisional until a
> structure resolves ([[labeling-is-last-step]],
> [book p.142](../../../raw/book/pages/page_142.md)). It is not stated in any
> single raw source.
> Sources: [[labeling-is-last-step]], [book p.142](../../../raw/book/pages/page_142.md), Faza 1 PRD (`.claude/PRPs/prds/faza-1-skill-modernization.prd.md`)

## Mode Discriminator

Pick exactly one mode, in this decision order:

1. **Concept mode** — the query asks *what a term means* ("what is a spring?",
   "explain Phase C", "difference between a spring and an upthrust?"). No live
   price data is supplied; the user wants knowledge.
2. **Diagnostic mode** — the query supplies *specific price/volume/structure
   observations* and asks *what they are* ("is this a spring?", "what phase is
   BTC in here?", "is this accumulation or distribution?"). The user wants a
   **classification of what already happened**, not a forward plan.
3. **Scenario mode** — the query asks for a *forward-looking plan*: a scenario
   tree with trigger, invalidation, and path ("build a Wyckoff scenario for
   BTC", "what's the setup here?", "go / wait / no-trade?").

Tie-breaks:

- Diagnostic vs scenario: if the user wants a forward path with trigger and
  invalidation → **scenario**; if they want "what is this right now" → 
  **diagnostic**. A diagnostic answer may end by *offering* to escalate to a
  scenario.
- Concept vs diagnostic: if a concrete chart/observation is present →
  **diagnostic**; if the question is general → **concept**.

## Mode Contracts

### Concept mode

Short and citation-backed. Structure:

1. **Definition** — 2–4 sentences, using book vocabulary.
2. **Citations** — 1–2 wiki pages (which themselves carry raw provenance).
3. **Related concepts** — 2–3 Obsidian-style wiki links for the reader to drill
   into.
4. **One worked example** — a single concrete illustration (crypto preferred).

Do **not** emit the nine-section scenario contract for a concept question.

### Diagnostic mode

Classification of supplied observations, with the labeling discipline enforced
([[labeling-is-last-step]]). Structure:

1. **What the price/volume shows** — restate the observation in Wyckoff terms
   (effort/result, significant bars) *before* naming any label.
2. **Candidate label(s)** — the most likely event/phase, plus the runner-up.
3. **Confidence and what is missing** — what evidence would confirm or deny the
   leading label (e.g. a spring is not confirmed until it causes the range to
   break up — [book p.142](../../../raw/book/pages/page_142.md)).
4. **Optional escalation** — offer scenario mode if the user wants a plan.

### Scenario mode

The full nine-section contract. This is the highest-effort mode and is reserved
for forward-looking analysis. Structure:

1. **Context** — dominant market-cycle position on the relevant higher
   timeframe; buying / selling / neutral position.
2. **Wyckoff story** — the narrative of supply and demand so far.
3. **Phase and event evidence** — Phase A–E read and the events seen.
4. **Crypto-specific overlays** — intermarket gate, BTC leadership, rotation,
   relative strength (see `crypto/`).
5. **Leading scenario** — structural thesis, trigger, invalidation, expected
   path, intermarket dependency, evidence quality.
6. **Alternate scenario(s)** — at least one credible alternate.
7. **Trigger, invalidation, target path** — explicit, comparative, not absolute.
8. **What would change the read** — the observations that flip the thesis.
9. **Trade / wait / no-trade conclusion** — including no-trade when evidence is
   mixed.

See [[playbook-master]] for the scenario decision tree that feeds section 5–7.

## Why It Matters For Wyckoff Reading

- It enforces [[labeling-is-last-step]]: diagnostic answers describe behavior
  before assigning a label, and scenario answers stay provisional with explicit
  invalidation.
- It keeps the skill honest about provenance — every concept/diagnostic claim
  routes back to a wiki page, which routes back to a raw source.
- It respects the no-trade-call rule (`/CLAUDE.md` §9): scenarios describe what
  *would* count as evidence; they never emit a bare "buy here".

## Links

- Scenario tree: [[playbook-master]]
- Entry scenarios: [[accumulation-phase-c-entry]],
  [[distribution-phase-c-entry]], [[phase-d-breakout-test]],
  [[no-shake-foothold]], [[crypto-rotation-watch]]
- Discipline: [[labeling-is-last-step]], [[action-test-confirmation]],
  [[path-of-least-resistance]]
- Phase anchor: [[phase-c]]
