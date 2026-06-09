# Skill Updator

This process has moved. The skill no longer holds hand-distilled
`references/*.md` files; its knowledge is the provenance-tracked wiki at
`../../knowledge/wiki/`.

To fold new Wyckoff or crypto material into the skill, **ingest the source into
the wiki** — the wiki is what `SKILL.md` reads at runtime. The canonical ingest
process (citation discipline, cross-batch awareness, cross-author rule, semantic
spot-check, validation scripts) lives in:

- **Runbook:** [`../../runbooks/wyckoff-wiki-ingest.md`](../../runbooks/wyckoff-wiki-ingest.md)
- **Domain schema (where each page goes):** [`../../CLAUDE.md`](../../CLAUDE.md) §2–§9

After ingesting, no separate edit to `SKILL.md` is usually needed: it navigates
the wiki through [`../../knowledge/wiki/index.md`](../../knowledge/wiki/index.md).
Update `SKILL.md` only when the *workflow* or *mode contract* changes, not when
knowledge is added.
