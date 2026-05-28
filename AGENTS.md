# AGENTS.md — Wyckoff AI Project Instructions for All Agents

Ovaj fajl sadrži pravila za sve AI agente (Codex, Claude Code, Gemini, Cursor, drugi) koji rade na ovom projektu. Identičan u sadržaju sa **glavnim CLAUDE.md fajlom u repo root-u** — koristi se kao alternativni put pretrage jer različiti alati traže različita imena (Claude → `CLAUDE.md`, Codex/drugi → `AGENTS.md`).

**Kompletan sadržaj projektnih pravila i wiki schema-e:** [CLAUDE.md](./CLAUDE.md)

## Kritična pravila — sažetak

Pre nego što radiš bilo šta u ovom repo-u, pročitaj:

### Jezik komunikacije

- **Default: srpski** za sve user-facing tekst (issues, komentari, planski dokumenti, PRD-ovi)
- **Engleski:** kod, file paths, wiki content, PR-ovi koji idu upstream, output contracts skill-a
- **Engleski termin u srpskom tekstu:** prvi put dodaj prevod + kratko objašnjenje u zagradi
- Detaljno: [CLAUDE.md §0.1](./CLAUDE.md#01-default-language-serbian)

### Code review

- Pre svake merge-a, lagani sanity check obavezan
- Za skill / schema / wiki ingest izmene — duboki review (`prp-review-agents`)
- [CLAUDE.md §0.2](./CLAUDE.md#02-code-review-pre-merge-a)

### Issue konvencija

- Naslov: engleski
- Body: srpski
- Labele: `phase:1/2/3`, `model:opus/sonnet`, plus tip
- Milestone obavezan
- [CLAUDE.md §0.3](./CLAUDE.md#03-github-issue-convention)

### Wiki schema (za rad sa `knowledge/wiki/`)

Sva pravila o folder layout-u, provenance-u, image alt textu, WIKI_GAP marker-ima:
[CLAUDE.md §1–§11](./CLAUDE.md)

---

**Za bilo šta van ovog sažetka, čitaj direktno [CLAUDE.md](./CLAUDE.md).**
