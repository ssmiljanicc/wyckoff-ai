# Skill Validation Prompts

Reusable regression baseline for GitHub issue #13.

Source of truth for Phase A is `knowledge/wiki/scenarios/test-set.md`. These
files copy the prompt set into `tests/prompts/` so future skill changes can
rerun the same contract checks without rediscovering the wiki page.

- `phase_a_wiki_only.md` — eight deterministic wiki-only prompts from the
  canonical test set.
- `phase_b_mcp_live.md` — live-data MCP prompts retained as best-effort checks
  for market-data, chart-renderer, and spread-chart workflows.
