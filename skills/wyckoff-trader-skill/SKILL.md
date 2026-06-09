---
name: wyckoff-trader-skill
description: Use this skill to answer Wyckoff questions about markets (especially crypto) in one of three modes — scenario (a full forward-looking scenario tree), concept (definition of a term), or diagnostic (classify what a chart is showing). It reads from a provenance-tracked wiki so every claim traces back to a source. Use it for springs, upthrusts, SOS/SOW, LPS/LPSY, accumulation vs distribution, phase reading, intermarket gates, crypto rotation, and relative strength.
---

# Wyckoff Trader Skill

## Overview

This skill turns chart observations into disciplined Wyckoff analysis. It is
optimized for crypto but the core method is classical Wyckoff: context first,
then structure, then phase and event evidence, then — only for forward-looking
questions — a scenario tree instead of a single prediction.

## Knowledge Base Architecture

The skill's knowledge lives in a **provenance-tracked wiki** at
`../../knowledge/wiki/` (relative to this file). Every substantive claim there
cites a raw source, so the skill's answers are traceable: answer → wiki page →
raw source.

**Runtime model (option B):** do **not** load the whole wiki. Always start by
reading the index, then read only the specific pages a query needs.

1. Read [`../../knowledge/wiki/index.md`](../../knowledge/wiki/index.md) — the
   navigation catalog. Every page is listed under its folder with a one-line
   description.
2. From the index, open the specific `concepts/`, `events/`, `structures/`,
   `crypto/`, or `scenarios/` pages the query requires.
3. Cite the wiki pages you used so the user can drill down to the raw source.

## Step 0 — Pick The Response Mode

Before answering, classify the query into **one** mode (full contract:
[`scenarios/output-contract.md`](../../knowledge/wiki/scenarios/output-contract.md)):

1. **Concept** — "what is X?", "explain Phase C", "spring vs upthrust?". No live
   data; the user wants knowledge.
2. **Diagnostic** — specific price/volume/structure observations supplied, asking
   "what is this?" / "what phase?". The user wants a classification.
3. **Scenario** — a forward-looking plan: scenario tree with trigger,
   invalidation, path ("build a scenario", "what's the setup?", "go/wait?").

Tie-breaks: forward path with trigger/invalidation → scenario; "what is this
right now" → diagnostic; general question → concept.

## Mode Workflows

### Concept mode

Read the relevant `concepts/` or `events/` page via the index. Return: a 2–4
sentence definition in book vocabulary, 1–2 wiki citations, 2–3 related wiki
links, and one worked example (crypto preferred). Do **not** emit the
nine-section scenario contract.

### Diagnostic mode

Enforce [labeling-is-last-step](../../knowledge/wiki/concepts/labeling-is-last-step.md):
describe the price/volume behavior **before** naming a label. Return: what the
behavior shows, the candidate label(s) plus runner-up, the confidence and what
evidence would confirm or deny it, and an optional offer to escalate to scenario
mode.

### Scenario mode

Route through the master tree
([`scenarios/playbook-master.md`](../../knowledge/wiki/scenarios/playbook-master.md)),
then produce the full nine-section contract:

1. Context (market-cycle position; buying/selling/neutral)
2. Wyckoff story (supply/demand narrative so far)
3. Phase and event evidence (Phase A–E + events)
4. Crypto overlays (intermarket gate, BTC leadership, rotation, relative
   strength — run
   [`scenarios/crypto-rotation-watch.md`](../../knowledge/wiki/scenarios/crypto-rotation-watch.md))
5. Leading scenario (thesis, trigger, invalidation, path, intermarket
   dependency, evidence quality)
6. Alternate scenario(s) — at least one credible alternate
7. Trigger, invalidation, target path (comparative, not absolute)
8. What would change the read
9. Trade / wait / no-trade conclusion

Pick the matching entry template from the tree:
[accumulation-phase-c-entry](../../knowledge/wiki/scenarios/accumulation-phase-c-entry.md),
[distribution-phase-c-entry](../../knowledge/wiki/scenarios/distribution-phase-c-entry.md),
[phase-d-breakout-test](../../knowledge/wiki/scenarios/phase-d-breakout-test.md),
or [no-shake-foothold](../../knowledge/wiki/scenarios/no-shake-foothold.md).

## Core Rules

- **Label last.** Read price/volume behavior first; assign structure labels only
  after the story is coherent.
- **Context outranks pattern.** A spring in the wrong background is noise.
- **Scenarios, not certainties.** Every forward read carries an explicit
  invalidation.
- **Path of least resistance**, not the most dramatic narrative.
- **Crypto:** always check the intermarket gate and internal rotation before a
  directional view.
- **Mixed evidence → no-trade / wait**, not a forced thesis.
- **No trade calls** (`/CLAUDE.md` §9): describe what *would* count as evidence;
  never emit a bare "buy here".
- **Cite the wiki.** Every concept/diagnostic claim names the wiki page it came
  from.

## Optional: Live Data (MCP)

When MCP market-data tools are available (Faza 2), use them to populate the
observations a scenario needs. The skill must still work **without** them — in
that case, analyze the observations the user provides.

## References

- Navigation: [`../../knowledge/wiki/index.md`](../../knowledge/wiki/index.md)
- Response contract: [`scenarios/output-contract.md`](../../knowledge/wiki/scenarios/output-contract.md)
- Scenario tree: [`scenarios/playbook-master.md`](../../knowledge/wiki/scenarios/playbook-master.md)
- Updating the skill / wiki: [`runbooks/wyckoff-wiki-ingest.md`](../../runbooks/wyckoff-wiki-ingest.md)
- Domain schema: [`/CLAUDE.md`](../../CLAUDE.md)
