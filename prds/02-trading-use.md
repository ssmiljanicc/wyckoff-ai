# PRD-02: Trading Use

**Status:** **DRAFT — assumptions pre-filled, requires user review**
**Created:** 2026-05-24 (initial draft from existing skill artifacts)
**Tracking issue:** [#15](https://github.com/ssmiljanicc/wyckoff-ai/issues/15)
**Related PRDs:** [PRD-01](./01-knowledge-base.md), [PRD-01a](./01a-existing-skill-snapshot.md)
**Hard deadline:** finalized before [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) starts (after [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) wiki ingest is at least ~80%)

---

## How to use this draft

Each decision below is marked one of:

- **[ASSUMED]** — pre-filled from existing skill artifacts; needs explicit user confirm or override
- **[OPEN]** — genuinely unanswered; needs `/prp-prd` interactive session or direct user input
- **[DECIDED]** — settled by PRD-01 or existing skill

To finalize: walk top-to-bottom, flip every **[ASSUMED]** to **[CONFIRMED]** or **[REVISED: ...]**, and resolve every **[OPEN]**. Then this becomes the input for [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8).

---

## 1. Who is the user

**[ASSUMED]** Primary user: **solo trader / Wyckoff practitioner watching crypto charts**, intermediate-to-advanced Wyckoff vocabulary, wants disciplined scenario thinking instead of single-call predictions.

**[ASSUMED]** Secondary user: **Wyckoff student** at intermediate level, uses the skill to deepen understanding by querying concepts and seeing them applied to live structures.

**[ASSUMED]** NOT a target: bot/algo signal feed consumers, automated trading systems, complete Wyckoff beginners (they should read the book first).

**Justification:** The existing `SKILL.md` description targets "building, reviewing, or updating Wyckoff-based market scenarios, especially for crypto assets" — assumes Wyckoff vocabulary. The 9-section output contract assumes a user who can act on a scenario tree (knows what trigger/invalidation mean).

---

## 2. Mode discriminator (NEW — the most important addition over existing skill)

**[ASSUMED]** The agent operates in one of **three modes**, picked from query shape:

| Mode | Query shape | Output | Example query |
|---|---|---|---|
| **Scenario** | "Build a scenario for X" / "Analyze X" / "What's the play on X" | Full 9-section contract (per existing `scenario_playbook.md`) | "BTC 1d is at $42k after a 6-week range — walk me through the playbook" |
| **Concept** | "What is X?" / "Define X" / "How does X work?" | 1–2 paragraphs + wiki citations + 1 chart example if relevant | "What's a spring?" |
| **Diagnostic** | "What phase is this?" / "Is this a spring?" / "Is this distribution?" | Phase ID + 3–5 evidence bullets + alt phase considered + what would change the read | "Is ETHBTC in markup or re-accumulation?" |

**Why this matters:** the existing skill applies the 9-section contract to everything. Asking "what is a spring?" and getting back a 9-section scenario tree is broken UX. Mode discriminator fixes this.

**[OPEN]** — Confirm three modes is right? Add a fourth (e.g., **Comparison** for "compare X vs Y")?

---

## 3. Representative query set (PRD-02 must produce — drafted here)

**[ASSUMED]** These 8 queries exemplify expected use. They become the test set for [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) Phase A:

### Scenario mode
1. "BTC 1d is consolidating at $42k after a 6-week range following a 30% drop — walk me through the Wyckoff playbook."
2. "ETHBTC has been in markup for 4 weeks while BTC consolidates — what's the play on altcoin rotation right now?"
3. "LINK/USDT 4h shows a possible spring after a 2-month accumulation — build the scenario and the alternate."

### Concept mode
4. "What's a no-shake Phase C variant?"
5. "Explain the difference between AR (automatic rally) and an automatic reaction."
6. "What's the 'principle in the principle' concept?"

### Diagnostic mode
7. "Looking at SOL/USDT 1d for the past 3 months — what phase do you think we're in?"
8. "Is this a failed upthrust or a successful UTAD?" *(user provides chart description)*

**[OPEN]** — Are 8 queries enough? Add ones specific to MCP usage (Phase B in #13)?

---

## 4. What the user provides (input contract)

**[ASSUMED]** Three input shapes the agent must support:

| Input shape | Example | Agent behavior |
|---|---|---|
| **Symbol + timeframe only** | `"BTC 1d"` | With MCP (M4): pull OHLCV, render chart, analyze. Without MCP: ask user for chart description or OHLCV data. |
| **Symbol + described scenario** | `"BTC 1d at $42k, 6-week range, last bar long-tailed down, volume spike"` | Build scenario from description. Don't fabricate phase events not in the description. Optionally pull via MCP for verification. |
| **Uploaded chart image** | (image attachment) | Vision-analyze the chart. Cross-check with wiki for phase/event identification. With MCP: cross-reference live data if symbol is identifiable. |

**[OPEN]** — Should the agent ever proactively pull additional context (e.g., always check intermarket if symbol is BTC)? Or only on request?

---

## 5. Boundary (what the agent NEVER does)

**[ASSUMED]** Explicit non-outputs:

- ❌ **No buy/sell signals.** Output is "scenario with trigger + invalidation", not "enter at $X".
- ❌ **No position sizing.** No "size 1% of portfolio" or "set stop at $Y".
- ❌ **No price targets as commitments.** Targets are scenarios; the trigger that confirms vs. invalidates is the actionable part.
- ❌ **No prediction language.** "Likely path is ... IF trigger happens" not "BTC will go to $50k".
- ❌ **No emotional language.** No "great setup", "amazing", "huge move coming". Wyckoff is calm and technical.
- ❌ **No labels without evidence.** Per `concepts/labeling-is-last-step.md` — read first, label second.

**[ASSUMED]** The user is responsible for the trade decision; the agent is responsible for the analysis quality.

**Justification:** Existing `SKILL.md` core rules already imply this (label last, scenarios not certainties, no-trade is valid). Making it explicit in PRD-02 prevents drift in #8 rewrite.

---

## 6. Failure modes (what the agent does when stuck)

**[ASSUMED]**

| Situation | Response |
|---|---|
| Ambiguous chart, no clear phase | `Tactical quality: watchlist only` + describe what would resolve ambiguity |
| Two phases equally plausible | Build TWO leading scenarios, both with equal weight; tie-breaker is what behavior would distinguish |
| Conflicting timeframes | State the conflict explicitly; ask user for primary timeframe OR default to requested timeframe with note about HTF disagreement |
| Missing intermarket data (no MCP) | Flag explicitly; ask user OR proceed with explicit "intermarket not checked" caveat |
| Outside wiki coverage | Mark as `synthesis` per `/CLAUDE.md` §5, OR mark `WIKI_GAP` if no relevant wiki page exists; never fabricate |
| User asks for a buy/sell signal | Politely redirect to scenario-tree output; explain the boundary from §5 |

---

## 7. Intermarket / cross-asset behavior

**[ASSUMED]** Intermarket depth depends on asset:

| Asset class | Auto-check |
|---|---|
| BTC, ETH | Always check: S&P/Nasdaq direction, dollar index, BTC dominance |
| Major alts (LINK, SOL, AVAX, etc.) | Always check: BTC leadership (USD pair vs. /BTC pair), sector index if available |
| Low caps | Always check: BTC, sector index, thematic peers |
| Spread charts (ETHBTC, etc.) | Always check: both legs' USD performance to disambiguate ratio direction |

**[ASSUMED]** "Auto-check" means: pull the data via MCP (when available) and integrate into the analysis. Without MCP: ask user OR explicitly note "not checked".

**[OPEN]** — Add macro layer (yields, oil, gold) for BTC analysis? Or limit to equity-index gating only?

---

## 8. Multi-timeframe (MTF) policy

**[ASSUMED]** The agent **always considers one timeframe higher** than the requested one for context. Example: user asks "BTC 4h" → agent also pulls/considers BTC 1d as context, mentions it in §1 (Context) of the output.

**[ASSUMED]** Lower-timeframe drill-down is **on request only** — don't preemptively pull 1h when user asked for 1d. Avoids noise.

**[OPEN]** — Should HTF context be mandatory section in output, or optional? (Currently §1 "Context" mentions higher-timeframe cycle position — could be elevated.)

---

## 9. MCP integration scope (refines #9, #10, #11, #12)

Based on the above, **required MCP capabilities** (must-have for the full skill experience):

| Tool | Issue | Required because |
|---|---|---|
| `get_ohlcv(symbol, timeframe, limit)` | [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9) | All three input shapes need data unless user provides verbatim |
| `render_chart(...)` returning image for Vision | [#10](https://github.com/ssmiljanicc/wyckoff-ai/issues/10) | Wyckoff is visual; agent analyzes via Vision on rendered chart |
| `render_spread_chart(base, quote, ...)` | [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11) | Crypto rotation analysis needs spread charts |

**Nice-to-have (cut if scope pressure):**

- `get_btc_dominance()` — could be derived from individual asset OHLCV; defer unless heavily used
- `get_context_chain(symbol)` — auto-pulls HTF context. Useful but can be composed by the agent calling `get_ohlcv` twice.

**Cut:**

- Real-time streaming — agent is request/response, not streaming. Polling on user request is enough.

**[OPEN]** — Add tool for sector/thematic index data? (DeFi index, exchange-token index, etc.) — depends on whether thematic group analysis is high-frequency in actual use.

---

## 10. Output contract (final spec — replaces existing SKILL.md §Output Contract)

### Scenario mode (existing 9-section contract, refined)

```
1. Context (asset, timeframe, HTF cycle position, buying/selling/neutral)
2. Wyckoff story (plain language, no labels yet)
3. Phase + event evidence (labels NOW)
4. Crypto overlay (intermarket + BTC leadership + rotation — required, not optional)
5. Leading scenario (thesis + trigger + invalidation + expected path + confidence in words)
6. Alternate scenario(s) (at least 1 credible alt; if 2 plausible primaries — both as leading)
7. Trigger, invalidation, target path (each scenario)
8. What would change the read (failed signal list)
9. Tactical quality (Phase C aggressive / Phase D confirmation / Phase E continuation / watchlist / no-trade)
```

Existing 9-section structure preserved; section 9 (Decision) renamed to **Tactical quality** to match `scenario_playbook.md` taxonomy (more actionable than yes/no).

### Concept mode (NEW)

```
- Definition (1–2 sentences)
- Where it fits (phase + structure context)
- 1 worked example (linked from wiki, with chart if available)
- Sources (wiki page citations)
- Related concepts (links)
```

### Diagnostic mode (NEW)

```
- Verdict (e.g., "likely Phase B" or "ambiguous between spring and failed test")
- 3–5 evidence bullets
- Alt verdict considered + why ruled less likely
- What would change the read
```

---

## 11. Confirmation checklist (before this PRD goes to #8)

Once all **[ASSUMED]** flags above are flipped, the user confirms:

- [ ] Three-mode discriminator (§2) is the right shape
- [ ] 8 representative queries (§3) cover the expected use
- [ ] Three input shapes (§4) are exhaustive (no fourth missing)
- [ ] Boundary list (§5) is complete — nothing to add or relax
- [ ] Failure modes (§6) are exhaustive
- [ ] Intermarket policy (§7) matches actual analysis depth
- [ ] MTF policy (§8) matches preferred behavior
- [ ] MCP scope (§9) — must-haves are right, nice-to-haves can be deferred
- [ ] Output contracts (§10) for all three modes are usable

When all 9 are checked: PRD-02 is final, [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) can start.

---

## 12. Changes that propagate from this PRD

Once finalized, the following artifacts must update:

| Artifact | Update |
|---|---|
| [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) body | Reference PRD-02 §10 output contract |
| `skills/wyckoff-trader-skill/SKILL.md` | Add mode discriminator (§2), update output contract to match §10 |
| `/CLAUDE.md` §3 required pages | Add `scenarios/concept-mode-contract.md` and `scenarios/diagnostic-mode-contract.md` if §10 stands |
| [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9), [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11) | Confirm scope matches §9 must-haves; cut nice-to-haves from minimum-viable |
| [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) | Use 8 prompts from §3 as Phase A test set |

---

**Next action:** user reviews this draft. Either (a) walks through `/prp-prd` to refine interactively, or (b) inlines `[CONFIRMED]` / `[REVISED]` markers and commits the final version.
