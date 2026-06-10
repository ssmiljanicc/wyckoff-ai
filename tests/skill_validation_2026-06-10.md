# Skill Validation Report — 2026-06-10

Issue: #13, "End-to-end skill validation against test prompts"

## Summary

Phase A source of truth was reconciled to
`knowledge/wiki/scenarios/test-set.md`, not the stale five-prompt list in the
issue body. The deleted `uncommon_concepts` source from the original issue is
not used; the reusable baseline now points at existing wiki concept pages and
the canonical eight-prompt harness.

Result: **8 / 8 Phase A prompts pass** against the contract. This exceeds the
Faza 1 PRD target of at least 6 / 8 contract-compliant answers.

Scope discipline: `skills/wyckoff-trader-skill/SKILL.md` and
`knowledge/wiki/` were not changed. Findings below are recommendations only.

## Sources Preloaded / Read JIT

Runtime model followed `SKILL.md`: preload `knowledge/wiki/index.md`, then read
only pages needed by each prompt.

Core contract pages:

- `skills/wyckoff-trader-skill/SKILL.md`
- `knowledge/wiki/index.md`
- `knowledge/wiki/scenarios/test-set.md`
- `knowledge/wiki/scenarios/output-contract.md`
- `knowledge/wiki/scenarios/playbook-master.md`

Wiki pages used by prompt:

- A1: `events/spring.md`, `events/upthrust-after-distribution.md`,
  `concepts/phase-c.md`
- A2: `events/no-shake-phase-c.md`, `scenarios/no-shake-foothold.md`,
  `events/last-point-of-support.md` / `events/last-point-of-supply.md` via
  linked pages
- A3: `events/spring.md`, `events/upthrust-after-distribution.md`,
  `concepts/phase-c.md`
- A4: `events/spring.md`, `concepts/labeling-is-last-step.md`,
  `concepts/phase-c.md`
- A5: `concepts/phase-b.md`, `events/st-as-msos.md`,
  `concepts/labeling-is-last-step.md`
- A6: `structures/distribution.md`, `events/upthrust-after-distribution.md`,
  `concepts/labeling-is-last-step.md`
- A7: `scenarios/output-contract.md`, `scenarios/playbook-master.md`,
  `scenarios/accumulation-phase-c-entry.md`,
  `scenarios/distribution-phase-c-entry.md`,
  `scenarios/crypto-rotation-watch.md`, `crypto/intermarket-gate.md`,
  `crypto/rotation-hierarchy.md`, `crypto/comparative-strength.md`,
  `crypto/bitcoin-leader-vs-funding-source.md`
- A8: `scenarios/output-contract.md`, `scenarios/playbook-master.md`,
  `scenarios/accumulation-phase-c-entry.md`,
  `scenarios/crypto-rotation-watch.md`, `crypto/intermarket-gate.md`,
  `crypto/spread-charts.md`, `crypto/comparative-strength.md`,
  `crypto/rotation-hierarchy.md`

## Phase A Results

| ID | Prompt | Mode | Result | Notes |
|---|---|---:|---:|---|
| A1 | What is a spring? | concept | PASS | Short definition, citations, related links, worked example; no scenario contract. |
| A2 | What's a no-shake Phase C? | concept | PASS | Names LPS/LPSY as primary operational event and links no-shake foothold. |
| A3 | Spring vs UTAD difference | concept | PASS | Correct mirror framing and directionality. |
| A4 | BTC downside wick back into range | diagnostic | PASS | Behavior first, spring candidate second, explicit provisional status. |
| A5 | ETH 8-week range, falling volume, high probe failed | diagnostic | PASS | Phase B accumulation / UA-mSOS candidate, not spring. |
| A6 | Uptrend stopped, upper probe failed on strong volume | diagnostic | PASS | Leans distribution and UTAD candidate with label discipline. |
| A7 | BTC 1d scenario after 6-week range | scenario | PASS | Full nine-section contract, leading + alternate, trigger/invalidation, crypto overlay. |
| A8 | LINK range, BTC sprang, Nasdaq basing | scenario | PASS | Full nine-section contract, intermarket gate first, spread-detect/USD-execute, no bare trade call. |

## Phase A Full Responses And Evaluation

### A1 — Concept

Prompt: "What is a spring?"

Response:

**Definition.** A spring is a Phase C shake in an accumulation structure: price
temporarily breaks below range support, then re-enters the range as the operator
tests whether meaningful supply remains. Its function is to transfer stock from
weak hands to strong hands and verify that the path of least resistance can turn
up. The label stays provisional until the action later causes the range to break
up.

**Citations.** `[[spring]]`, `[[phase-c]]`

**Related concepts.** `[[upthrust-after-distribution]]`,
`[[labeling-is-last-step]]`, `[[accumulation-phase-c-entry]]`

**Worked example.** BTC has spent six weeks in a range after a decline. It
prints a long lower wick below support, closes back inside the range, then later
tests above the spring low on lower volume and breaks the upper boundary with
SOS behavior. That sequence supports a spring read; without the upward
resolution, the low remains only a test.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS, concept mode only; no nine-section scenario output.
- Provenance traceback: PASS via `events/spring.md` and `concepts/phase-c.md`.
- Hallucination check: PASS, only wiki-defined labels used.

### A2 — Concept

Prompt: "What's a no-shake Phase C?"

Response:

**Definition.** A no-shake Phase C is the Phase C variant where the range does
not produce a terminal spring or UTAD before resolving. The wiki maps this to
Basic Accumulation #2 / Basic Distribution #2: absorption was thorough enough
that the market starts the Phase D resolution from inside the range. The
operational location moves to the LPS/BUEC in accumulation or LPSY/FTI in
distribution.

**Citations.** `[[no-shake-phase-c]]`, `[[no-shake-foothold]]`

**Related concepts.** `[[last-point-of-support]]`,
`[[last-point-of-supply]]`, `[[phase-d]]`

**Worked example.** LINK ranges for weeks with volume steadily drying up, never
undercuts support, then breaks above the Creek and backs up on low volume. The
setup is not missing a spring; it is a no-shake accumulation path where the
confirmation test is the LPS/BUEC.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS.
- Provenance traceback: PASS via `events/no-shake-phase-c.md` and
  `scenarios/no-shake-foothold.md`.
- Hallucination check: PASS.

### A3 — Concept

Prompt: "Difference between a spring and an upthrust after distribution?"

Response:

**Definition.** A spring and a UTAD are mirror Phase C shakes. A spring belongs
to accumulation: price probes below support, re-enters the range, and if later
confirmed, supports an upward resolution. A UTAD belongs to distribution:
price probes above resistance, re-enters the range, and if later confirmed,
supports a downward resolution. In both cases the false break gathers liquidity
at the wrong side of the range and tests whether the opposing side can still
participate.

**Citations.** `[[spring]]`, `[[upthrust-after-distribution]]`

**Related concepts.** `[[phase-c]]`, `[[labeling-is-last-step]]`,
`[[distribution-phase-c-entry]]`

**Worked example.** A BTC range after a downtrend that briefly breaks support
and reclaims it is a spring candidate. A range after an uptrend that briefly
breaks resistance on strong activity and falls back below resistance is a UTAD
candidate.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS.
- Provenance traceback: PASS via both event pages and `concepts/phase-c.md`.
- Hallucination check: PASS.

### A4 — Diagnostic

Prompt: "BTC 1d just printed a low below the 6-week range support on a long
lower wick, then closed back inside the range on elevated volume. What is this?"

Response:

**What price/volume shows.** The bar first broke the lower boundary of a
six-week range, then rejected the breakdown and closed back inside the range.
The long lower wick says downside result was limited relative to the selling
effort, while elevated volume says real orders crossed at the support sweep.
That behavior is a failed downside break, not yet a completed bullish
resolution.

**Candidate labels.** Leading label: provisional spring candidate in an
accumulation context. Runner-up: a Phase B lower-end test / ST as SOW if the
range has not yet built enough cause or if follow-through demand fails to
appear.

**Confidence and missing evidence.** Confidence is medium. The spring label is
not confirmed until the action causes the range to break up; until then, the
wiki discipline says to keep the label provisional. Confirmation would be a
valid spring test above the spring low, followed by SOS/JAC behavior through the
upper boundary. Denial would be acceptance back below the swept low or a weak
rally that leaves Phase B unresolved.

**Optional escalation.** If you want a forward plan, this can be escalated to a
scenario read with trigger, invalidation, and alternate path.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS, behavior before label.
- Provenance traceback: PASS via `events/spring.md`,
  `concepts/labeling-is-last-step.md`, and `concepts/phase-c.md`.
- Hallucination check: PASS.

### A5 — Diagnostic

Prompt: "ETH has ranged ~8 weeks after a downtrend; volume is falling; the last
probe of the highs reversed quickly back into the range. What phase?"

Response:

**What price/volume shows.** ETH has a lateral range after a prior downtrend,
with falling volume across the range. That suggests cause-building and
absorption rather than an active trend. The latest upper-end probe could not
hold above resistance and quickly returned inside the range, so it is a test of
the upper boundary, not a terminal downside shake.

**Candidate labels.** Leading label: Phase B accumulation, with the upper-end
probe read as UA / possible mSOS depending on how long it held above
resistance. Runner-up: neutral ST in B if the structure is not yet clearly
accumulation rather than redistribution.

**Confidence and missing evidence.** Confidence is medium-high for Phase B
because eight weeks of range time after a downtrend and falling volume match
the cause-building profile. It is too early to call a spring because no support
sweep or Phase C shake has been described. Confirmation would be later Phase C
action: spring/test/SOS, or a no-shake break with LPS/BUEC. Denial would be
persistent high volatility, lower-bound weakness, or a failed support test that
turns the read toward redistribution.

**Optional escalation.** Scenario mode would map the next decision point:
wait for spring, no-shake LPS/BUEC, or failed Phase B extension.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS.
- Provenance traceback: PASS via `concepts/phase-b.md`,
  `events/st-as-msos.md`, and `concepts/labeling-is-last-step.md`.
- Hallucination check: PASS.

### A6 — Diagnostic

Prompt: "Is this accumulation or distribution? Range stopped an uptrend;
upper-end probe took out the highs on strong volume then fell back below
resistance."

Response:

**What price/volume shows.** The range formed after an uptrend, so the starting
context favors distribution over accumulation. The upper-end probe took out the
highs on strong volume, then failed and returned below resistance. That is an
upside liquidity sweep with effort present but no sustained upward result.

**Candidate labels.** Leading label: distribution structure with a provisional
UTAD candidate. Runner-up: a Phase B upthrust / ST in B if the range is not yet
mature enough for Phase C or if the later bearish break never appears.

**Confidence and missing evidence.** Confidence is medium. UTAD requires later
bearish resolution; the label is not final until the action causes the bearish
break out of the range. Confirmation would be a weak test below the UTAD high,
then SOW through the lower boundary and an LPSY/FTI confirmation test. Denial
would be acceptance above the swept highs or a strong recovery that makes the
probe a failed bearish read.

**Optional escalation.** Scenario mode would define the bearish leading case,
the failed-UTAD alternate, and what evidence changes the read.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS, behavior before label.
- Provenance traceback: PASS via `structures/distribution.md`,
  `events/upthrust-after-distribution.md`, and
  `concepts/labeling-is-last-step.md`.
- Hallucination check: PASS.

### A7 — Scenario

Prompt: "Build a Wyckoff scenario for BTC 1d at $42k after a 6-week range."

Response:

1. **Context.** BTC is in a six-week trading range on the daily chart. Without
   more observations, the market-cycle stance is neutral: a purposeful range is
   possible, but the read must be resolved by boundary behavior. Position:
   wait, not directional certainty.

2. **Wyckoff story.** The prior trend and range quality matter more than the
   $42k print. If the range followed a decline, the leading structural question
   is accumulation/reaccumulation; if it followed an advance, distribution is
   equally plausible. The current job is to read how price behaves at support,
   resistance, and on tests, not to forecast from the midpoint.

3. **Phase and event evidence.** With only "six-week range" supplied, the
   cleanest current label is Phase B unless a spring/UTAD/no-shake break has
   already occurred. Phase C starts when the terminal test begins: spring below
   support, UTAD above resistance, failed shake, or no-shake resolution.

4. **Crypto-specific overlays.** Run `[[crypto-rotation-watch]]` in parallel:
   intermarket gate first, then BTC role, rotation tier, comparative strength,
   and spread confirmation where relevant. A supportive Nasdaq/S&P tape or BTC
   outperformance during equity weakness improves evidence quality; a hostile
   gate or BTC acting as a funding source lowers it.

5. **Leading scenario.** Leading thesis: wait for an accumulation-side Phase C
   entry only if BTC sweeps support, re-enters the range, tests above the spring
   low on narrower spread/lower volume, then produces SOS/JAC behavior through
   the upper boundary. Trigger: spring test holds plus later SOS/LPS or BUEC
   confirmation. Invalidation: acceptance below the spring low, or an SOS that
   fails back into the range. Expected path: markup attempt from range to Phase
   E only after confirmation. Evidence quality: incomplete until boundary
   action appears.

6. **Alternate scenario(s).** Bearish alternate: the same range is distribution
   if BTC first stops an uptrend, then probes above resistance on strong volume
   and falls back below it. Trigger would be a UTAD test below the UTAD high,
   then SOW and LPSY/FTI. Second alternate: no-shake resolution if Phase B has
   already absorbed supply and price breaks upward without a terminal spring;
   in that case the clean evidence is the LPS/BUEC, not the missing spring.

7. **Trigger, invalidation, target path.** Bullish trigger: spring/test/SOS/LPS
   sequence or no-shake break followed by low-volume BUEC. Bullish invalidation:
   range support lost and accepted, or the upper breakout fails as an upthrust.
   Bearish trigger: UTAD/test/SOW/LPSY sequence. Targets should be comparative:
   first the opposite boundary, then the P&F count / Phase E path if the range
   resolves; do not assign an absolute target from the prompt alone.

8. **What would change the read.** A support sweep that cannot re-enter the
   range changes spring candidate into continuation weakness. A resistance
   break that holds above the Creek changes a bearish read into strength. A
   hostile intermarket gate or failed BTC leadership can veto an otherwise clean
   crypto setup.

9. **Trade / wait / no-trade conclusion.** **Wait.** The prompt gives context
   but not the event evidence needed for a trade-quality scenario. The next
   valid action is to wait for a Phase C event or a no-shake Phase D
   confirmation test, then reassess.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS, all nine sections present.
- Provenance traceback: PASS via `scenarios/output-contract.md`,
  `scenarios/playbook-master.md`, `scenarios/accumulation-phase-c-entry.md`,
  `scenarios/distribution-phase-c-entry.md`, and
  `scenarios/crypto-rotation-watch.md`.
- Hallucination check: PASS.

### A8 — Scenario

Prompt: "LINK has been ranging for weeks while BTC just sprang and the Nasdaq
is basing. What's the setup?"

Response:

1. **Context.** Start with the intermarket gate. Nasdaq is basing, so the gate
   is not fully risk-on yet, but it is potentially improving. BTC just sprang,
   which can be constructive for the crypto tape, but LINK still needs its own
   USD-pair setup and relative-strength confirmation.

2. **Wyckoff story.** LINK has a multi-week range, so the question is whether
   the range is purposeful accumulation and whether supply has been absorbed.
   BTC's spring can improve the background, but it does not automatically make
   LINK an entry. The LINK range must show its own spring/test/SOS sequence or
   no-shake LPS/BUEC path.

3. **Phase and event evidence.** With only "ranging for weeks" supplied, LINK
   is likely in Phase B unless it has already printed its own Phase C test. BTC
   may be in Phase C/early Phase D after spring, but LINK needs a Phase C event:
   support sweep and re-entry, or no-shake break followed by LPS/BUEC.

4. **Crypto-specific overlays.** Intermarket gate first: Nasdaq basing is a
   condition to monitor, not a completed green light. Then run rotation:
   BTC spring first, then look for capital flowing from BTC into leaders.
   Use LINKBTC as the spread chart to detect leadership, but execute only on
   LINKUSD if the USD pair prints the structure. Comparative strength improves
   if LINK reacts less than BTC on pullbacks and advances more cleanly on
   rallies.

5. **Leading scenario.** Leading thesis: LINK accumulation watchlist, not an
   immediate trade. Trigger: LINKUSD prints a spring/test/SOS sequence, or a
   no-shake break with low-volume BUEC, while LINKBTC confirms leadership and
   Nasdaq does not reject its base. Invalidation: LINKBTC fails while BTC leads
   alone, LINKUSD loses range support and accepts lower, or Nasdaq breaks down
   and closes the intermarket gate. Expected path: LINK follows BTC's repaired
   structure into Phase D only after its own confirmation.

6. **Alternate scenario(s).** Alternate one: BTC spring remains isolated
   leadership and LINK stays in Phase B; action is wait for more absorption.
   Alternate two: LINK's range is redistribution; a support break with weak
   recovery would make the prior range a pause before markdown. Alternate
   three: no-shake accumulation, where LINK skips the spring and the primary
   evidence becomes LPS/BUEC after the break.

7. **Trigger, invalidation, target path.** Trigger evidence: supportive Nasdaq
   base, LINKBTC relative-strength breakout or successful retest, and LINKUSD
   spring/test/SOS or no-shake BUEC. Invalidation: LINKUSD accepts below range
   support, LINKBTC underperforms BTC, or Nasdaq fails the base. Target path:
   first range resistance / Creek, then Phase D confirmation, then Phase E if
   the breakout holds; no absolute target from the prompt alone.

8. **What would change the read.** A Nasdaq downside failure turns the gate
   hostile. A BTC rally with no LINKBTC improvement says rotation has not
   reached LINK. A LINKUSD support sweep that immediately reclaims and tests
   well upgrades the setup; a high-volume breakdown downgrades it.

9. **Trade / wait / no-trade conclusion.** **Wait / watchlist.** The setup is
   constructive enough to monitor, but not a bare entry. The required next
   evidence is spread leadership plus a LINKUSD structural trigger.

Evaluation:

- Must criteria: PASS.
- Mode contract: PASS, all nine sections present.
- Provenance traceback: PASS via `crypto/intermarket-gate.md`,
  `crypto/spread-charts.md`, `scenarios/accumulation-phase-c-entry.md`, and
  `scenarios/crypto-rotation-watch.md`.
- Hallucination check: PASS.

## Phase B MCP Live Check

Issue #9, #10, and #11 are all closed. In this kild, `uv run --extra mcp` can
start the MCP server modules and call tools through the MCP stdio client.

Smoke checks run:

- `market_data_server` stdio MCP:
  - Tools listed: `get_ohlcv`, `get_supported_symbols`, `get_timeframes`
  - Tool call: `get_ohlcv(symbol="BTC", timeframe="1d", limit=5)`
  - Result: returned Binance public OHLCV JSON.
- `chart_renderer` stdio MCP:
  - Tools listed: `render_chart`, `render_chart_for_symbol`
  - Tool call: `render_chart_for_symbol(symbol="BTC", timeframe="1d", limit=200)`
  - Result: rendered a 1200x600 PNG with 200 candles at
    `/tmp/wyckoff-ai-chart-renderer/79542059aa49f782923b68b651cb275e33c97dea93901760893e1d67e0dab3cf.png`.

One live prompt was then evaluated:

Prompt: "Pull BTC 1d for the last 200 days, render the chart, and identify the
current Wyckoff phase."

Observed data:

- Symbol/timeframe: BTCUSDT 1d
- Candles: 200
- Latest close during run: 61689.98
- Last six-week high: 82850.0
- Last six-week low: 59130.91
- Latest close location in that six-week range: 0.108 from low to high
- 20-day average volume: 20563.875
- Prior 20-day average volume: 13864.606

Vision/chart read:

The rendered chart shows a prior high area near the upper 90k zone, a sharp
February markdown into the mid-60k area, a multi-month repair rally into the
low 80k area, then a May/June selloff back toward the 59k-63k lower area. The
last six-week window is not a clean sideways Phase B range; it is a decline into
the lower end with elevated recent volume and only early stabilization.

Skill-style response:

1. **Context.** BTC 1d is below the prior multi-month rally high and near the
   lower end of the recent six-week window. The immediate stance is defensive /
   neutral, not confirmed accumulation.
2. **Wyckoff story.** The chart shows supply regained control after the rally
   into the low 80k area. Current action is testing whether the lower 60k area
   can stop the decline.
3. **Phase and event evidence.** Do not label a spring yet. There is no clear
   support sweep, re-entry, low-volume test above the spring low, and SOS
   sequence. The better provisional label is possible late markdown into a new
   range / early Phase A stopping attempt, pending AR/ST evidence.
4. **Crypto overlays.** Not evaluated with live Nasdaq/SPX data in this run;
   the overlay remains required before any directional conclusion.
5. **Leading scenario.** Wait for Phase A/Phase B evidence: selling climax,
   automatic rally, secondary test, and later Phase B absorption before any
   Phase C spring thesis.
6. **Alternate scenario(s).** If price accepts below the 59k area, the decline
   continues and the range hypothesis is premature. If price quickly reclaims
   the lower area and builds an AR/ST sequence, an accumulation watch can begin.
7. **Trigger, invalidation, target path.** Trigger for constructive read:
   recovery back inside a defined range, ST on reduced spread/volume, and later
   Phase C/SOS evidence. Invalidation: acceptance below the recent low with
   expanding downside result.
8. **What would change the read.** A fast reclaim of the breakdown area and a
   successful test would shift from markdown/stopping action toward
   accumulation watch. A weak bounce on poor demand keeps the bearish path
   primary.
9. **Trade / wait / no-trade conclusion.** **Wait / no-trade.** The live chart
   is not a completed Phase C setup; it needs stopping and range evidence first.

Phase B result: PASS as a live-data feasibility check. It proves the closed MCP
work can be started and called in this kild without API keys. It is not counted
inside the deterministic 8/8 Phase A score.

## Findings / Recommendations

1. `events/no-shake-phase-c.md` includes inline references to
   `raw/book/pages/page_075.md` and `raw/book/pages/page_083.md`, but those two
   paths are not listed in that page's frontmatter `sources:` block. This is a
   wiki provenance parity issue to fix separately.
2. Phase B live validation currently depends on Binance public availability and
   moving market data. Keep it separate from the deterministic Phase A gate.
3. Future regression can automate the Phase A checks by comparing each response
   against mode, required citations, forbidden nine-section output for concept
   prompts, and required trigger/invalidation fields for scenario prompts.
