# Feature: Exhaustive Citation Audit Tool

## Summary

Issue #57 traži novi audit alat za wiki provenance: deterministički Sloj-1 koji iscrpno trijažira citate u `knowledge/wiki/`, Sloj-2 operacioni protokol za Opus semantičku presudu nad flagovima, full sweep izveštaj i runbook gate. Scope je striktan: gradimo alat, pokrećemo sweep i pišemo izveštaj; ne popravljamo pronađene wiki citation greške u ovom PR-u.

## User Story

As a wiki maintainer,
I want an exhaustive citation audit that catches citation misattribution even when links resolve,
So that inherited provenance errors from #7 are visible before they propagate into future wiki work.

## Problem Statement

`validate_links.py` proverava samo da inline markdown linkovi postoje na disku, ne da raw stranica podržava tvrdnju. Runbook §3.6 već traži ručni citation drill, ali to nije iscrpno i spot-check je sampled. Issue #57 dokumentuje off-by-one i image-only greške koje su prošle postojeće mehaničke provere.

## Solution Statement

Dodati `audit_citations.py` kao stdlib Python 3.11+ skriptu koja parsira wiki frontmatter i inline book citate, izvodi jeftine content-level heuristike, izlazi 0/1 kao postojeći validator i podržava `--pr N`. Dokumentovati Sloj-2 `citation-audit` operaciju za Opus i ažurirati `Validation` sekciju runbook-a da Sloj-1 bude obavezan pre merge-a uz `validate_links.py`.

## Metadata

- Feature type: `NEW_CAPABILITY`
- Complexity: `MEDIUM`
- Source spec: GitHub issue #57, `https://github.com/ssmiljanicc/wyckoff-ai/issues/57`
- Affected systems: `skills/wyckoff-wiki-ingest/scripts/`, `skills/wyckoff-wiki-ingest/operations/`, `runbooks/wyckoff-wiki-ingest.md`, `knowledge/wiki/health/`
- External docs: not needed; implementation is Python stdlib and existing repo conventions are sufficient.

## UX Design

Current operator flow:

```text
wiki edits -> validate_links.py -> review_pr.py -> sampled semantic spot-check
          -> resolving link can still point at wrong raw page
```

Future operator flow:

```text
wiki edits -> validate_links.py -> audit_citations.py -> review_pr.py
          -> Sloj-1 flags image-only/quote/parity/range/boundary risks
          -> Opus citation-audit protocol adjudicates flagged claims
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| `scripts/validate_links.py` pattern | Link existence only, exit 0/1, Serbian report | New sibling script mirrors CLI/report style | Familiar operator workflow |
| `runbooks/wyckoff-wiki-ingest.md` Validation | `validate_links.py` is mandatory; semantic pass sampled by trigger | `audit_citations.py` mandatory before merge | Misattribution triage becomes a gate |
| `operations/semantic-spot-check.md` | Sampled semantic review | New `citation-audit.md` covers exhaustive/flagged pass | Clear Sloj-2 protocol |

## Mandatory Reading

- `skills/wyckoff-wiki-ingest/scripts/validate_links.py:34-58` — `--pr` scoping convention via `origin/pr/<N>` and `origin/main`.
- `skills/wyckoff-wiki-ingest/scripts/validate_links.py:85-143` — exit 0/1 and human/JSON report style.
- `skills/wyckoff-wiki-ingest/scripts/review_pr.py:33-37` — existing regex approach for markdown links and frontmatter source paths.
- `runbooks/wyckoff-wiki-ingest.md:157-177` — citation drill, frontmatter parity, and page range special-case.
- `runbooks/wyckoff-wiki-ingest.md:421-429` — current Validation gate list to update.
- `skills/wyckoff-wiki-ingest/operations/semantic-spot-check.md:68-77` — source fidelity labels and quote grep rule to mirror in Sloj-2 protocol.

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| CLI | `skills/wyckoff-wiki-ingest/scripts/validate_links.py:85-89` | `argparse` with optional `--pr` and `--json`. | `parser.add_argument("--pr", type=int, help="Check only files in given PR")` |
| PR scoping | `skills/wyckoff-wiki-ingest/scripts/validate_links.py:34-58` | Fetch PR ref and diff `origin/main...ref` under `knowledge/wiki`. | `git diff --name-only origin/main...{ref} -- knowledge/wiki` |
| Reporting | `skills/wyckoff-wiki-ingest/scripts/validate_links.py:123-139` | Serbian summary first, then per-file issue list, exit 1 on findings. | `print(f"Provereno fajlova: {len(files)}")` |
| Parsing | `skills/wyckoff-wiki-ingest/scripts/review_pr.py:33-37` | Regex-based markdown/frontmatter extraction, no external deps. | `FRONTMATTER_RE = re.compile(r"^---\\n(.*?)\\n---\\n", re.DOTALL)` |
| Citation rules | `runbooks/wyckoff-wiki-ingest.md:161-177` | Quote grep, frontmatter-inline parity, and range special-case. | `Obe stranice moraju biti u frontmatter sources:` |

## Files to Change

- Add `skills/wyckoff-wiki-ingest/scripts/audit_citations.py`
- Add `skills/wyckoff-wiki-ingest/operations/citation-audit.md`
- Add `knowledge/wiki/health/citation-audit-2026-06-10.md`
- Update `runbooks/wyckoff-wiki-ingest.md`
- Add this plan file: `PRPs/plans/exhaustive-citation-audit-tool.plan.md`

## NOT Building

- No wiki content citation fixes in this PR.
- No new dependencies.
- No CI workflow unless an existing CI file requires a one-line script add; none is present in this repo snapshot.
- No full LLM semantic adjudication inside the Python script. Sloj-2 remains an operation protocol.

## Step-by-Step Tasks

1. Add `audit_citations.py`.
   - File: `skills/wyckoff-wiki-ingest/scripts/audit_citations.py`
   - Implement repo constants, `files_to_check(pr_number)`, markdown link extraction, frontmatter `sources:` extraction, raw path resolution, and `Issue` dataclass.
   - Mirror `validate_links.py` `--pr` and `--json` CLI style.
   - Validation: `python3 -m py_compile skills/wyckoff-wiki-ingest/scripts/audit_citations.py`

2. Implement Sloj-1 checks.
   - File: `audit_citations.py`
   - Checks: image-only cited raw page, quote-not-found for blockquotes near inline citations, section-boundary uppercase-tail heuristic, frontmatter↔inline parity with p.A-B special-case, and range sanity.
   - Gotcha: range inline target is first page, but every page in range must exist and be listed in frontmatter.
   - Validation: `uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json`

3. Self-verify controls.
   - File: `audit_citations.py` behavior only.
   - Must flag `raw/book/pages/page_163.md` if cited and image-only.
   - Must flag spring quote example where quote text is tied to p.141 but present on p.142 per runbook §3.6.
   - Validation: run audit and `rg "page_163|quote_not_found|Spring must necessarily cause" /tmp/audit-output`.

4. Add Sloj-2 operation.
   - File: `skills/wyckoff-wiki-ingest/operations/citation-audit.md`
   - Document Opus protocol, inputs, classifications `directly-stated`, `paraphrase-ok`, `misattribution`, and output contract.
   - Validation: `test -f skills/wyckoff-wiki-ingest/operations/citation-audit.md && rg -n "Opus|directly-stated|paraphrase-ok|misattribution" skills/wyckoff-wiki-ingest/operations/citation-audit.md`

5. Update runbook Validation gate.
   - File: `runbooks/wyckoff-wiki-ingest.md`
   - Add `audit_citations.py` as mandatory Sloj-1 gate immediately after `validate_links.py`.
   - Validation: `rg -n "audit_citations|Sloj-1" runbooks/wyckoff-wiki-ingest.md`

6. Run full sweep and write report.
   - File: `knowledge/wiki/health/citation-audit-2026-06-10.md`
   - Use script output as the authoritative flag list. Include command, date, scope, summary, and all remaining suspicious citations.
   - Validation: `test -f knowledge/wiki/health/citation-audit-2026-06-10.md && rg -n "image_only|quote_not_found|summary" knowledge/wiki/health/citation-audit-2026-06-10.md`

7. Final validation and PR.
   - Commands: `uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py`, `uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py`, `git diff --check`, `git status --short`.
   - Open PR against `main`, title in English, body in Serbian, refs #57, no self-merge.

## Testing Strategy

- Syntax test with `py_compile`.
- Human output test over full wiki.
- JSON output test for machine-readable report generation.
- Control-case assertions by searching output for known issue patterns.
- Existing `validate_links.py` remains part of final validation.

## Validation Commands

```bash
python3 -m py_compile skills/wyckoff-wiki-ingest/scripts/audit_citations.py
uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json > /tmp/citation-audit.json || true
uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py > /tmp/citation-audit.txt || true
rg "page_163|quote_not_found|Spring must necessarily cause" /tmp/citation-audit.txt /tmp/citation-audit.json
uv run skills/wyckoff-wiki-ingest/scripts/validate_links.py
git diff --check
```

## Acceptance Criteria

- `audit_citations.py` is stdlib-only, Python 3.11+, deterministic, and exits 1 when flags exist.
- `--pr N` limits scope to changed wiki markdown files.
- Full sweep flags known controls: image-only `page_163.md` and spring quote-not-found p.141 vs p.142 pattern.
- Sloj-2 protocol is documented in `operations/citation-audit.md`.
- `runbooks/wyckoff-wiki-ingest.md` Validation section lists Sloj-1 checks as mandatory pre-merge gate.
- Full sweep report exists in `knowledge/wiki/health/citation-audit-2026-06-10.md`.
- No wiki content fixes are included.

## Completion Checklist

- [ ] Plan saved.
- [ ] Script implemented.
- [ ] Controls verified.
- [ ] Operation protocol added.
- [ ] Runbook Validation updated.
- [ ] Full sweep report generated.
- [ ] Validation commands run.
- [ ] PR opened against `main`.

## Risks and Mitigations

- False positives from heuristics: label output as suspicious flags, not final semantic verdicts; Sloj-2 protocol adjudicates.
- Regex frontmatter parsing limitations: existing repo already uses predictable YAML-like `sources:` blocks; keep parser scoped to `path:` entries.
- Direct quote extraction can miss multi-line quote contexts: use blockquote aggregation and nearby inline citation detection; report as `quote_not_found` only when a distinctive phrase is available.
- `--pr` needs remote refs: mirror `validate_links.py`; if fetch fails, exit 2 with stderr.

## Notes

Ovaj plan namerno ne sadrži task za popravljanje `knowledge/wiki/` citata. Issue #57 i user prompt traže da se greške ispravljaju u zasebnom PR-u.
