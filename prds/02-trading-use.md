# PRD-02: Trading Use (STUB — to be written)

**Status:** Stub / not started
**Created:** 2026-05-24
**Tracking issue:** [#15](https://github.com/ssmiljanicc/wyckoff-ai/issues/15)
**Trigger:** must be written **before** [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) starts — i.e. during the natural pause after [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) completes
**Related PRDs:** [PRD-01](./01-knowledge-base.md) (knowledge base — independent through M2, joins at [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8))

---

## Why this PRD exists

PRD-01 covers what the agent *knows*. This PRD covers what the agent *does* — the actual trading-use workflow that determines the SKILL.md output contract, the scenario playbook structure, and which MCP capabilities are real requirements vs. nice-to-haves.

Without this PRD, [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) will reconstruct SKILL.md organized around the book's taxonomy (phases, events, structures) instead of around how a trader actually uses the agent (which questions, what kind of answer, what scenario walkthrough).

## Questions to answer (interactive — run `/prp-prd` to draft)

1. **Who uses this?** Solo trader watching crypto charts? Someone learning Wyckoff? Both? Different output contracts for each.
2. **What questions do they ask?** "Where are we in the cycle?" "Is this a spring?" "Should I enter here?" "Walk me through this setup." Need a representative set.
3. **What does a good answer look like?** Long discursive analysis? Structured scenario tree with branches? Phase ID + bullet list of evidence? Output format = SKILL.md contract.
4. **What does the user provide?** A symbol + timeframe? A described scenario? An uploaded chart image? This determines MCP requirements ([#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9)–[#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11)).
5. **What's the boundary?** Does the agent give actionable signals, or only analysis? Liability and use case both flow from this.
6. **Failure modes?** What does the agent do when it doesn't know? When the chart is ambiguous? When two phases are equally plausible?
7. **Intermarket checks:** Is BTC dominance / ETHBTC always pulled, or only on request? Determines [#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11) priority.
8. **Multi-timeframe:** does the agent need higher-timeframe context automatically? Determines whether MCP needs `get_context_chain(symbol)` style helper.

## What this PRD will produce

- A small set (3–5) of concrete user prompts that exemplify the use case
- An output contract spec — structure, length, required sections, what's never said
- A revised scenario playbook outline (overrides whatever [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8) would have done by default)
- Concrete MCP capability list — confirms / cuts / adds tools beyond [#9](https://github.com/ssmiljanicc/wyckoff-ai/issues/9)–[#11](https://github.com/ssmiljanicc/wyckoff-ai/issues/11)
- Test prompt set for [#13](https://github.com/ssmiljanicc/wyckoff-ai/issues/13) Phase B

## How to start when the time comes

Run `/prp-prd` interactively. Use issue [#8](https://github.com/ssmiljanicc/wyckoff-ai/issues/8), [#12](https://github.com/ssmiljanicc/wyckoff-ai/issues/12) bodies and the original `skills/wyckoff-trader-skill/SKILL.md` as inputs — they reveal the implicit assumptions about use that need to be made explicit.

---

**Do not start this PRD until [#7](https://github.com/ssmiljanicc/wyckoff-ai/issues/7) is nearly complete.** Earlier is wasted because trading-use decisions only matter once the knowledge base exists to back them.
