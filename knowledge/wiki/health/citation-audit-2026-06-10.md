# Citation Audit Report - 2026-06-10

## Summary

- Scope: full `knowledge/wiki/` content sweep (`knowledge/wiki/health/` excluded so generated reports do not self-audit)
- Command: `uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --json`
- Files checked: 182
- Files with flags: 61
- Total Sloj-1 flags: 242
- Hard gate flags: 58
- Warning / Sloj-2 backlog flags: 184
- Note: This is a Layer-1 triage report. Flags are suspicious citations, not content fixes. Wiki citation fixes belong in a separate PR per #57.

## Summary By Severity

- `HARD`: 58
- `WARNING`: 184

## Summary By Flag

- `frontmatter_missing`: 42
- `image_only`: 1
- `inline_missing`: 98
- `quote_not_found`: 3
- `range_missing_frontmatter`: 11
- `range_target`: 1
- `section_boundary`: 86

## Gate Tiering

- Hard pre-merge gate: `image_only`, `missing_raw`, `range_*`, `frontmatter_missing`, and strictly confirmed `quote_not_found`.
- Warning / Sloj-2 backlog: `section_boundary` and `inline_missing`. These are heuristics and do not block merge by themselves.

## Self-Verification Controls

- PASS: `uv run skills/wyckoff-wiki-ingest/scripts/audit_citations.py --self-check` exits 0 with the expected strict control flag set.
- PASS: literal spring p.141 vs p.142 quote-not-found control remains flagged.
- PASS: known p.149 attribution quote is no longer a `quote_not_found` false positive.
- PASS: multiline `> **Synthesis:**` blocks are skipped as synthesis, not direct quotes.
- PASS: comma-separated book citation control includes both pages in parity/range checks.
- PASS: range citation p.144-147 does not emit inline `section_boundary` when it already includes the next page.

Current `quote_not_found` flags after tolerant matching:
- `knowledge/wiki/events/upthrust-after-distribution.md:L146` -> `raw/book/pages/page_141.md`; blockquote phrase not found in cited raw page: 'UTAD is the shaking event of the highs of the structure but'
- `knowledge/wiki/events/upthrust.md:L66` -> `raw/book/pages/page_160.md`; blockquote phrase not found in cited raw page: 'If the SOS fails to stay above the Creek and re-enters the'
- `knowledge/wiki/structures/accumulation.md:L133` -> `raw/book/pages/page_040.md`; blockquote phrase not found in cited raw page: 'The objective of the price is to visit this liquidity zone but'

## Hard Gate Flags

### knowledge/wiki/concepts/buying-selling-neutral-position.md

- L33 `frontmatter_missing` `book p.15` -> `raw/book/pages/page_015.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_015.md

### knowledge/wiki/concepts/creek-and-ice.md

- L108 `frontmatter_missing` `book p.158` -> `raw/book/pages/page_158.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_158.md

### knowledge/wiki/concepts/labeling-is-last-step.md

- L45 `frontmatter_missing` `book p.149` -> `raw/book/pages/page_149.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_149.md
- L63 `frontmatter_missing` `book p.105` -> `raw/book/pages/page_105.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_105.md
- L68 `frontmatter_missing` `book p.158` -> `raw/book/pages/page_158.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_158.md

### knowledge/wiki/concepts/phase-a.md

- L78 `frontmatter_missing` `book p.79` -> `raw/book/pages/page_079.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_079.md
- L98 `frontmatter_missing` `book p.93` -> `raw/book/pages/page_093.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_093.md
- L108 `frontmatter_missing` `book p.108, p.111` -> `raw/book/pages/page_108.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_108.md, raw/book/pages/page_111.md
- L108 `range_missing_frontmatter` `book p.108, p.111` -> `raw/book/pages/page_108.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_108.md, raw/book/pages/page_111.md

### knowledge/wiki/concepts/phase-b.md

- L100 `frontmatter_missing` `book p.139` -> `raw/book/pages/page_139.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_139.md
- L120 `frontmatter_missing` `book p.184` -> `raw/book/pages/page_184.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_184.md

### knowledge/wiki/concepts/phase-c.md

- L116 `frontmatter_missing` `book p.134` -> `raw/book/pages/page_134.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_134.md

### knowledge/wiki/concepts/phase-e.md

- L68 `frontmatter_missing` `book p.174` -> `raw/book/pages/page_174.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_174.md
- L94 `frontmatter_missing` `book p.130` -> `raw/book/pages/page_130.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_130.md

### knowledge/wiki/concepts/random-vs-purposeful-range.md

- L57 `frontmatter_missing` `book p.76` -> `raw/book/pages/page_076.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_076.md
- L58 `frontmatter_missing` `p.84` -> `raw/book/pages/page_084.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_084.md

### knowledge/wiki/concepts/three-laws.md

- L44 `frontmatter_missing` `book p.55` -> `raw/book/pages/page_055.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_055.md

### knowledge/wiki/concepts/trend-assessment.md

- L175 `frontmatter_missing` `book p.68` -> `raw/book/pages/page_068.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_068.md

### knowledge/wiki/concepts/waves-and-fractals.md

- L61 `frontmatter_missing` `book p.16` -> `raw/book/pages/page_016.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_016.md

### knowledge/wiki/events/automatic-reaction.md

- L107 `frontmatter_missing` `book p.116` -> `raw/book/pages/page_116.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_116.md

### knowledge/wiki/events/failed-signal.md

- L72 `frontmatter_missing` `book p.169–170` -> `raw/book/pages/page_169.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_169.md
- L72 `range_missing_frontmatter` `book p.169–170` -> `raw/book/pages/page_169.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_169.md

### knowledge/wiki/events/fall-through-the-ice.md

- L54 `frontmatter_missing` `book p.169–170` -> `raw/book/pages/page_169.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_169.md, raw/book/pages/page_170.md
- L54 `range_missing_frontmatter` `book p.169–170` -> `raw/book/pages/page_169.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_169.md, raw/book/pages/page_170.md
- L78 `frontmatter_missing` `book p.171–172` -> `raw/book/pages/page_171.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_171.md, raw/book/pages/page_172.md
- L78 `range_missing_frontmatter` `book p.171–172` -> `raw/book/pages/page_171.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_171.md, raw/book/pages/page_172.md
- L88 `frontmatter_missing` `book p.169` -> `raw/book/pages/page_169.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_169.md

### knowledge/wiki/events/no-shake-phase-c.md

- L43 `frontmatter_missing` `book p.40–45` -> `raw/book/pages/page_040.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_042.md, raw/book/pages/page_043.md
- L43 `range_missing_frontmatter` `book p.40–45` -> `raw/book/pages/page_040.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_042.md, raw/book/pages/page_043.md
- L53 `frontmatter_missing` `book p.75` -> `raw/book/pages/page_075.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_075.md
- L54 `frontmatter_missing` `book p.83` -> `raw/book/pages/page_083.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_083.md

### knowledge/wiki/events/preliminary-support.md

- L66 `frontmatter_missing` `book p.95–96` -> `raw/book/pages/page_095.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_096.md
- L66 `range_missing_frontmatter` `book p.95–96` -> `raw/book/pages/page_095.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_096.md

### knowledge/wiki/events/secondary-test.md

- L95 `frontmatter_missing` `book p.125` -> `raw/book/pages/page_125.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_125.md
- L101 `frontmatter_missing` `book p.126–127` -> `raw/book/pages/page_126.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_126.md, raw/book/pages/page_127.md
- L101 `range_missing_frontmatter` `book p.126–127` -> `raw/book/pages/page_126.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_126.md, raw/book/pages/page_127.md
- L110 `frontmatter_missing` `book p.128` -> `raw/book/pages/page_128.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_128.md
- L116 `frontmatter_missing` `book p.128` -> `raw/book/pages/page_128.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_128.md
- L135 `frontmatter_missing` `book p.130` -> `raw/book/pages/page_130.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_130.md
- L150 `frontmatter_missing` `book p.131–132` -> `raw/book/pages/page_131.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_132.md
- L150 `range_missing_frontmatter` `book p.131–132` -> `raw/book/pages/page_131.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_132.md

### knowledge/wiki/events/sign-of-strength.md

- L79 `frontmatter_missing` `book p.156–157` -> `raw/book/pages/page_156.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_157.md
- L79 `range_missing_frontmatter` `book p.156–157` -> `raw/book/pages/page_156.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_157.md

### knowledge/wiki/events/sign-of-weakness.md

- L100 `frontmatter_missing` `book p.159` -> `raw/book/pages/page_159.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_159.md

### knowledge/wiki/events/st-as-msos.md

- L61 `frontmatter_missing` `book p.139` -> `raw/book/pages/page_139.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_139.md
- L78 `frontmatter_missing` `book p.128` -> `raw/book/pages/page_128.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_128.md

### knowledge/wiki/events/upthrust-after-distribution.md

- L79 `frontmatter_missing` `book p.137–138` -> `raw/book/pages/page_137.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_137.md, raw/book/pages/page_138.md
- L79 `range_missing_frontmatter` `book p.137–138` -> `raw/book/pages/page_137.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_137.md, raw/book/pages/page_138.md
- L146 `quote_not_found` `book p.141` -> `raw/book/pages/page_141.md`: blockquote phrase not found in cited raw page: 'UTAD is the shaking event of the highs of the structure but'

### knowledge/wiki/events/upthrust.md

- L66 `quote_not_found` `book p.160` -> `raw/book/pages/page_160.md`: blockquote phrase not found in cited raw page: 'If the SOS fails to stay above the Creek and re-enters the'

### knowledge/wiki/log.md

- L14 `frontmatter_missing` ``raw/INVENTORY.md`` -> `raw/INVENTORY.md`: inline citation has no matching frontmatter source(s): raw/INVENTORY.md

### knowledge/wiki/scenarios/test-set.md

- L44 `frontmatter_missing` `book p.142` -> `raw/book/pages/page_142.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_142.md

### knowledge/wiki/sources/book/book-chapter-14.md

- L63 `frontmatter_missing` `p.95–96` -> `raw/book/pages/page_095.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_096.md
- L63 `range_missing_frontmatter` `p.95–96` -> `raw/book/pages/page_095.md`: range citation page(s) absent from frontmatter: raw/book/pages/page_096.md

### knowledge/wiki/sources/book/book-chapter-19.md

- L25 `image_only` `raw/book/pages/page_163.md` -> `raw/book/pages/page_163.md`: cited raw page contains only markdown image references and no prose

### knowledge/wiki/sources/book/book-chapter-24.md

- L54 `range_target` `p.186–187` -> `raw/book/pages/page_187.md`: range citation should link to first page raw/book/pages/page_186.md, got raw/book/pages/page_187.md

### knowledge/wiki/structures/accumulation.md

- L133 `quote_not_found` `book p.40–41` -> `raw/book/pages/page_040.md`: blockquote phrase not found in cited raw page: 'The objective of the price is to visit this liquidity zone but'

### knowledge/wiki/structures/reaccumulation.md

- L122 `frontmatter_missing` `book p.192` -> `raw/book/pages/page_192.md`: inline citation has no matching frontmatter source(s): raw/book/pages/page_192.md

## Warning / Sloj-2 Backlog Flags

### knowledge/wiki/concepts/action-test-confirmation.md

- L9 `inline_missing` `raw/book/pages/page_130.md` -> `raw/book/pages/page_130.md`: frontmatter source is not cited inline on this page
- L13 `inline_missing` `raw/book/pages/page_132.md` -> `raw/book/pages/page_132.md`: frontmatter source is not cited inline on this page
- L19 `inline_missing` `raw/book/pages/page_168.md` -> `raw/book/pages/page_168.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/concepts/cause-and-effect.md

- L19 `inline_missing` `raw/book/pages/page_060.md` -> `raw/book/pages/page_060.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/concepts/creek-and-ice.md

- L13 `inline_missing` `raw/book/pages/page_164.md` -> `raw/book/pages/page_164.md`: frontmatter source is not cited inline on this page
- L108 `section_boundary` `book p.158` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose

### knowledge/wiki/concepts/effort-and-result.md

- L17 `section_boundary` `raw/book/pages/page_066.md` -> `raw/book/pages/page_066.md`: cited book page ends with uppercase heading only: 'BY WAVES'; check next page for supporting prose
- L25 `inline_missing` `raw/book/pages/page_070.md` -> `raw/book/pages/page_070.md`: frontmatter source is not cited inline on this page
- L75 `section_boundary` `book p.66` -> `raw/book/pages/page_066.md`: cited book page ends with uppercase heading only: 'BY WAVES'; check next page for supporting prose

### knowledge/wiki/concepts/labeling-is-last-step.md

- L9 `inline_missing` `raw/book/pages/page_100.md` -> `raw/book/pages/page_100.md`: frontmatter source is not cited inline on this page
- L21 `inline_missing` `raw/book/pages/page_186.md` -> `raw/book/pages/page_186.md`: frontmatter source is not cited inline on this page
- L68 `section_boundary` `book p.158` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose

### knowledge/wiki/concepts/path-of-least-resistance.md

- L15 `section_boundary` `raw/book/pages/page_075.md` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose
- L55 `section_boundary` `book p.75` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose

### knowledge/wiki/concepts/phase-a.md

- L7 `inline_missing` `raw/book/pages/page_178.md` -> `raw/book/pages/page_178.md`: frontmatter source is not cited inline on this page
- L9 `inline_missing` `raw/book/pages/page_179.md` -> `raw/book/pages/page_179.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/concepts/reversal-of-movement.md

- L11 `inline_missing` `raw/book/pages/page_212.md` -> `raw/book/pages/page_212.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/concepts/three-laws.md

- L9 `section_boundary` `raw/book/pages/page_046.md` -> `raw/book/pages/page_046.md`: cited book page ends with uppercase heading only: 'FUNDAMENTAL LAWS'; check next page for supporting prose
- L13 `inline_missing` `raw/book/pages/page_054.md` -> `raw/book/pages/page_054.md`: frontmatter source is not cited inline on this page
- L28 `section_boundary` `book p.46` -> `raw/book/pages/page_046.md`: cited book page ends with uppercase heading only: 'FUNDAMENTAL LAWS'; check next page for supporting prose

### knowledge/wiki/concepts/trend-assessment.md

- L33 `inline_missing` `raw/book/pages/page_030.md` -> `raw/book/pages/page_030.md`: frontmatter source is not cited inline on this page
- L37 `inline_missing` `raw/book/pages/page_032.md` -> `raw/book/pages/page_032.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/automatic-rally.md

- L11 `section_boundary` `raw/book/pages/page_114.md` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L13 `section_boundary` `raw/book/pages/page_115.md` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L33 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L61 `section_boundary` `book p.114` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L68 `section_boundary` `book p.114` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L90 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L93 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L113 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose

### knowledge/wiki/events/automatic-reaction.md

- L11 `section_boundary` `raw/book/pages/page_114.md` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L13 `section_boundary` `raw/book/pages/page_115.md` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L17 `inline_missing` `raw/book/pages/page_120.md` -> `raw/book/pages/page_120.md`: frontmatter source is not cited inline on this page
- L33 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L64 `section_boundary` `book p.114` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L94 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L114 `section_boundary` `book p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose

### knowledge/wiki/events/buying-climax.md

- L7 `inline_missing` `raw/book/pages/page_101.md` -> `raw/book/pages/page_101.md`: frontmatter source is not cited inline on this page
- L7 `section_boundary` `raw/book/pages/page_101.md` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose

### knowledge/wiki/events/failed-signal.md

- L9 `inline_missing` `raw/book/pages/page_142.md` -> `raw/book/pages/page_142.md`: frontmatter source is not cited inline on this page
- L11 `section_boundary` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose
- L15 `inline_missing` `raw/book/pages/page_170.md` -> `raw/book/pages/page_170.md`: frontmatter source is not cited inline on this page
- L52 `section_boundary` `book p.158` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose

### knowledge/wiki/events/jump-across-the-creek.md

- L7 `inline_missing` `raw/book/pages/page_160.md` -> `raw/book/pages/page_160.md`: frontmatter source is not cited inline on this page
- L11 `inline_missing` `raw/book/pages/page_038.md` -> `raw/book/pages/page_038.md`: frontmatter source is not cited inline on this page
- L13 `inline_missing` `raw/book/pages/page_040.md` -> `raw/book/pages/page_040.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/last-point-of-supply.md

- L7 `inline_missing` `raw/book/pages/page_167.md` -> `raw/book/pages/page_167.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/last-point-of-support.md

- L7 `inline_missing` `raw/book/pages/page_167.md` -> `raw/book/pages/page_167.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/no-shake-phase-c.md

- L11 `inline_missing` `raw/book/pages/page_044.md` -> `raw/book/pages/page_044.md`: frontmatter source is not cited inline on this page
- L13 `inline_missing` `raw/book/pages/page_045.md` -> `raw/book/pages/page_045.md`: frontmatter source is not cited inline on this page
- L15 `section_boundary` `raw/book/pages/page_074.md` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L17 `section_boundary` `raw/book/pages/page_082.md` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L21 `inline_missing` `raw/book/pages/page_185.md` -> `raw/book/pages/page_185.md`: frontmatter source is not cited inline on this page
- L39 `section_boundary` `book p.74` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L40 `section_boundary` `book p.82` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L53 `section_boundary` `book p.75` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose

### knowledge/wiki/events/secondary-test.md

- L7 `section_boundary` `raw/book/pages/page_121.md` -> `raw/book/pages/page_121.md`: cited book page ends with uppercase heading only: 'FUNCTIONS OF THE SECONDARY TEST'; check next page for supporting prose
- L13 `inline_missing` `raw/book/pages/page_124.md` -> `raw/book/pages/page_124.md`: frontmatter source is not cited inline on this page
- L15 `inline_missing` `raw/book/pages/page_129.md` -> `raw/book/pages/page_129.md`: frontmatter source is not cited inline on this page
- L30 `section_boundary` `book p.121` -> `raw/book/pages/page_121.md`: cited book page ends with uppercase heading only: 'FUNCTIONS OF THE SECONDARY TEST'; check next page for supporting prose

### knowledge/wiki/events/selling-climax.md

- L7 `section_boundary` `raw/book/pages/page_101.md` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose
- L13 `section_boundary` `raw/book/pages/page_104.md` -> `raw/book/pages/page_104.md`: cited book page ends with uppercase heading only: 'USES OF CLIMAX'; check next page for supporting prose
- L17 `inline_missing` `raw/book/pages/page_106.md` -> `raw/book/pages/page_106.md`: frontmatter source is not cited inline on this page
- L33 `section_boundary` `book p.101` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose
- L76 `section_boundary` `book p.104` -> `raw/book/pages/page_104.md`: cited book page ends with uppercase heading only: 'USES OF CLIMAX'; check next page for supporting prose

### knowledge/wiki/events/sign-of-strength.md

- L7 `inline_missing` `raw/book/pages/page_154.md` -> `raw/book/pages/page_154.md`: frontmatter source is not cited inline on this page
- L13 `section_boundary` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose
- L15 `inline_missing` `raw/book/pages/page_159.md` -> `raw/book/pages/page_159.md`: frontmatter source is not cited inline on this page
- L15 `section_boundary` `raw/book/pages/page_159.md` -> `raw/book/pages/page_159.md`: cited book page ends with uppercase heading only: 'BREAKOUT DOES NOT OFFER AN OPPORTUNITY'; check next page for supporting prose

### knowledge/wiki/events/sign-of-weakness.md

- L7 `inline_missing` `raw/book/pages/page_154.md` -> `raw/book/pages/page_154.md`: frontmatter source is not cited inline on this page
- L11 `inline_missing` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: frontmatter source is not cited inline on this page
- L11 `section_boundary` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose
- L15 `inline_missing` `raw/book/pages/page_165.md` -> `raw/book/pages/page_165.md`: frontmatter source is not cited inline on this page
- L100 `section_boundary` `book p.159` -> `raw/book/pages/page_159.md`: cited book page ends with uppercase heading only: 'BREAKOUT DOES NOT OFFER AN OPPORTUNITY'; check next page for supporting prose

### knowledge/wiki/events/spring.md

- L19 `inline_missing` `raw/book/pages/page_140.md` -> `raw/book/pages/page_140.md`: frontmatter source is not cited inline on this page
- L27 `section_boundary` `raw/book/pages/page_144.md` -> `raw/book/pages/page_144.md`: cited book page ends with uppercase heading only: 'SPRING #1 OR TERMINAL SHAKEOUT'; check next page for supporting prose

### knowledge/wiki/events/st-as-msos.md

- L7 `inline_missing` `raw/book/pages/page_125.md` -> `raw/book/pages/page_125.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/st-as-msow.md

- L7 `inline_missing` `raw/book/pages/page_125.md` -> `raw/book/pages/page_125.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/upthrust-after-distribution.md

- L9 `inline_missing` `raw/book/pages/page_135.md` -> `raw/book/pages/page_135.md`: frontmatter source is not cited inline on this page
- L15 `inline_missing` `raw/book/pages/page_142.md` -> `raw/book/pages/page_142.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/events/upthrust.md

- L7 `inline_missing` `raw/book/pages/page_126.md` -> `raw/book/pages/page_126.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/scenarios/output-contract.md

- L8 `inline_missing` `raw/book/pages/page_184.md` -> `raw/book/pages/page_184.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/scenarios/phase-d-breakout-test.md

- L8 `section_boundary` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose
- L44 `section_boundary` `book p.158` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose

### knowledge/wiki/scenarios/test-set.md

- L8 `inline_missing` `raw/book/pages/page_184.md` -> `raw/book/pages/page_184.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-04.md

- L11 `inline_missing` `raw/book/pages/page_022.md` -> `raw/book/pages/page_022.md`: frontmatter source is not cited inline on this page
- L13 `inline_missing` `raw/book/pages/page_023.md` -> `raw/book/pages/page_023.md`: frontmatter source is not cited inline on this page
- L17 `inline_missing` `raw/book/pages/page_025.md` -> `raw/book/pages/page_025.md`: frontmatter source is not cited inline on this page
- L19 `inline_missing` `raw/book/pages/page_026.md` -> `raw/book/pages/page_026.md`: frontmatter source is not cited inline on this page
- L25 `inline_missing` `raw/book/pages/page_029.md` -> `raw/book/pages/page_029.md`: frontmatter source is not cited inline on this page
- L31 `inline_missing` `raw/book/pages/page_032.md` -> `raw/book/pages/page_032.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-05.md

- L11 `inline_missing` `raw/book/pages/page_035.md` -> `raw/book/pages/page_035.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-06.md

- L9 `inline_missing` `raw/book/pages/page_038.md` -> `raw/book/pages/page_038.md`: frontmatter source is not cited inline on this page
- L11 `inline_missing` `raw/book/pages/page_039.md` -> `raw/book/pages/page_039.md`: frontmatter source is not cited inline on this page
- L17 `inline_missing` `raw/book/pages/page_042.md` -> `raw/book/pages/page_042.md`: frontmatter source is not cited inline on this page
- L19 `inline_missing` `raw/book/pages/page_043.md` -> `raw/book/pages/page_043.md`: frontmatter source is not cited inline on this page
- L23 `inline_missing` `raw/book/pages/page_045.md` -> `raw/book/pages/page_045.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-07.md

- L15 `inline_missing` `raw/book/pages/page_051.md` -> `raw/book/pages/page_051.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-08.md

- L19 `inline_missing` `raw/book/pages/page_060.md` -> `raw/book/pages/page_060.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-09.md

- L13 `inline_missing` `raw/book/pages/page_064.md` -> `raw/book/pages/page_064.md`: frontmatter source is not cited inline on this page
- L15 `inline_missing` `raw/book/pages/page_065.md` -> `raw/book/pages/page_065.md`: frontmatter source is not cited inline on this page
- L17 `inline_missing` `raw/book/pages/page_066.md` -> `raw/book/pages/page_066.md`: frontmatter source is not cited inline on this page
- L17 `section_boundary` `raw/book/pages/page_066.md` -> `raw/book/pages/page_066.md`: cited book page ends with uppercase heading only: 'BY WAVES'; check next page for supporting prose
- L21 `inline_missing` `raw/book/pages/page_068.md` -> `raw/book/pages/page_068.md`: frontmatter source is not cited inline on this page
- L25 `inline_missing` `raw/book/pages/page_070.md` -> `raw/book/pages/page_070.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-10.md

- L9 `section_boundary` `raw/book/pages/page_073.md` -> `raw/book/pages/page_073.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L11 `section_boundary` `raw/book/pages/page_074.md` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L13 `section_boundary` `raw/book/pages/page_075.md` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose
- L49 `section_boundary` `p.73` -> `raw/book/pages/page_073.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L52 `section_boundary` `p.74` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L55 `section_boundary` `p.74` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L58 `section_boundary` `p.75` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-12.md

- L9 `section_boundary` `raw/book/pages/page_081.md` -> `raw/book/pages/page_081.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L11 `section_boundary` `raw/book/pages/page_082.md` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L17 `inline_missing` `raw/book/pages/page_085.md` -> `raw/book/pages/page_085.md`: frontmatter source is not cited inline on this page
- L49 `section_boundary` `p.81` -> `raw/book/pages/page_081.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L52 `section_boundary` `p.82` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L55 `section_boundary` `p.82` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-14.md

- L19 `inline_missing` `raw/book/pages/page_100.md` -> `raw/book/pages/page_100.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-15.md

- L7 `section_boundary` `raw/book/pages/page_101.md` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose
- L13 `inline_missing` `raw/book/pages/page_104.md` -> `raw/book/pages/page_104.md`: frontmatter source is not cited inline on this page
- L13 `section_boundary` `raw/book/pages/page_104.md` -> `raw/book/pages/page_104.md`: cited book page ends with uppercase heading only: 'USES OF CLIMAX'; check next page for supporting prose
- L17 `inline_missing` `raw/book/pages/page_106.md` -> `raw/book/pages/page_106.md`: frontmatter source is not cited inline on this page
- L23 `inline_missing` `raw/book/pages/page_109.md` -> `raw/book/pages/page_109.md`: frontmatter source is not cited inline on this page
- L60 `section_boundary` `p.101` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose
- L62 `section_boundary` `p.101` -> `raw/book/pages/page_101.md`: cited book page ends with uppercase heading only: 'KEYS TO CLIMAX'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-16.md

- L11 `section_boundary` `raw/book/pages/page_114.md` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L13 `section_boundary` `raw/book/pages/page_115.md` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L21 `inline_missing` `raw/book/pages/page_119.md` -> `raw/book/pages/page_119.md`: frontmatter source is not cited inline on this page
- L23 `inline_missing` `raw/book/pages/page_120.md` -> `raw/book/pages/page_120.md`: frontmatter source is not cited inline on this page
- L63 `section_boundary` `p.114` -> `raw/book/pages/page_114.md`: cited book page ends with uppercase heading only: 'REACTION USES'; check next page for supporting prose
- L68 `section_boundary` `p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose
- L76 `section_boundary` `p.115` -> `raw/book/pages/page_115.md`: cited book page ends with uppercase heading only: 'IT PROVIDES US WITH THE MARKET CONTEXT'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-17.md

- L7 `section_boundary` `raw/book/pages/page_121.md` -> `raw/book/pages/page_121.md`: cited book page ends with uppercase heading only: 'FUNCTIONS OF THE SECONDARY TEST'; check next page for supporting prose
- L13 `inline_missing` `raw/book/pages/page_124.md` -> `raw/book/pages/page_124.md`: frontmatter source is not cited inline on this page
- L17 `inline_missing` `raw/book/pages/page_126.md` -> `raw/book/pages/page_126.md`: frontmatter source is not cited inline on this page
- L29 `inline_missing` `raw/book/pages/page_132.md` -> `raw/book/pages/page_132.md`: frontmatter source is not cited inline on this page
- L63 `section_boundary` `p.121` -> `raw/book/pages/page_121.md`: cited book page ends with uppercase heading only: 'FUNCTIONS OF THE SECONDARY TEST'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-18.md

- L11 `inline_missing` `raw/book/pages/page_136.md` -> `raw/book/pages/page_136.md`: frontmatter source is not cited inline on this page
- L15 `inline_missing` `raw/book/pages/page_138.md` -> `raw/book/pages/page_138.md`: frontmatter source is not cited inline on this page
- L27 `section_boundary` `raw/book/pages/page_144.md` -> `raw/book/pages/page_144.md`: cited book page ends with uppercase heading only: 'SPRING #1 OR TERMINAL SHAKEOUT'; check next page for supporting prose
- L29 `inline_missing` `raw/book/pages/page_145.md` -> `raw/book/pages/page_145.md`: frontmatter source is not cited inline on this page
- L31 `inline_missing` `raw/book/pages/page_146.md` -> `raw/book/pages/page_146.md`: frontmatter source is not cited inline on this page
- L33 `inline_missing` `raw/book/pages/page_147.md` -> `raw/book/pages/page_147.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-19.md

- L13 `section_boundary` `raw/book/pages/page_157.md` -> `raw/book/pages/page_157.md`: cited book page ends with uppercase heading only: 'NOT IMMEDIATELY RE-ENTERING IN THE TRADING RANGE'; check next page for supporting prose
- L15 `section_boundary` `raw/book/pages/page_158.md` -> `raw/book/pages/page_158.md`: cited book page ends with uppercase heading only: 'REPRESENTATION OF LACK OF INTEREST'; check next page for supporting prose
- L17 `section_boundary` `raw/book/pages/page_159.md` -> `raw/book/pages/page_159.md`: cited book page ends with uppercase heading only: 'BREAKOUT DOES NOT OFFER AN OPPORTUNITY'; check next page for supporting prose
- L25 `inline_missing` `raw/book/pages/page_163.md` -> `raw/book/pages/page_163.md`: frontmatter source is not cited inline on this page
- L29 `inline_missing` `raw/book/pages/page_165.md` -> `raw/book/pages/page_165.md`: frontmatter source is not cited inline on this page
- L31 `inline_missing` `raw/book/pages/page_166.md` -> `raw/book/pages/page_166.md`: frontmatter source is not cited inline on this page
- L52 `section_boundary` `p.159` -> `raw/book/pages/page_159.md`: cited book page ends with uppercase heading only: 'BREAKOUT DOES NOT OFFER AN OPPORTUNITY'; check next page for supporting prose
- L76 `section_boundary` `p.157` -> `raw/book/pages/page_157.md`: cited book page ends with uppercase heading only: 'NOT IMMEDIATELY RE-ENTERING IN THE TRADING RANGE'; check next page for supporting prose
- L86 `section_boundary` `p.159` -> `raw/book/pages/page_159.md`: cited book page ends with uppercase heading only: 'BREAKOUT DOES NOT OFFER AN OPPORTUNITY'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-20.md

- L19 `inline_missing` `raw/book/pages/page_173.md` -> `raw/book/pages/page_173.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/sources/book/book-chapter-26.md

- L17 `section_boundary` `raw/book/pages/page_203.md` -> `raw/book/pages/page_203.md`: cited book page ends with uppercase heading only: 'ENTRY INTO THE BREAK TEST (CONFIRMATION EVENT NO. 7)'; check next page for supporting prose
- L21 `section_boundary` `raw/book/pages/page_205.md` -> `raw/book/pages/page_205.md`: cited book page ends with uppercase heading only: 'ENTRY WITH MINOR STRUCTURES'; check next page for supporting prose
- L23 `inline_missing` `raw/book/pages/page_206.md` -> `raw/book/pages/page_206.md`: frontmatter source is not cited inline on this page
- L79 `section_boundary` `p.203` -> `raw/book/pages/page_203.md`: cited book page ends with uppercase heading only: 'ENTRY INTO THE BREAK TEST (CONFIRMATION EVENT NO. 7)'; check next page for supporting prose

### knowledge/wiki/sources/book/book-chapter-27.md

- L9 `inline_missing` `raw/book/pages/page_209.md` -> `raw/book/pages/page_209.md`: frontmatter source is not cited inline on this page
- L13 `inline_missing` `raw/book/pages/page_211.md` -> `raw/book/pages/page_211.md`: frontmatter source is not cited inline on this page
- L17 `inline_missing` `raw/book/pages/page_213.md` -> `raw/book/pages/page_213.md`: frontmatter source is not cited inline on this page
- L25 `inline_missing` `raw/book/pages/page_217.md` -> `raw/book/pages/page_217.md`: frontmatter source is not cited inline on this page
- L33 `inline_missing` `raw/book/pages/page_222.md` -> `raw/book/pages/page_222.md`: frontmatter source is not cited inline on this page
- L35 `inline_missing` `raw/book/pages/page_223.md` -> `raw/book/pages/page_223.md`: frontmatter source is not cited inline on this page
- L37 `inline_missing` `raw/book/pages/page_224.md` -> `raw/book/pages/page_224.md`: frontmatter source is not cited inline on this page
- L39 `inline_missing` `raw/book/pages/page_225.md` -> `raw/book/pages/page_225.md`: frontmatter source is not cited inline on this page
- L41 `inline_missing` `raw/book/pages/page_226.md` -> `raw/book/pages/page_226.md`: frontmatter source is not cited inline on this page

### knowledge/wiki/structures/accumulation.md

- L7 `inline_missing` `raw/book/pages/page_037.md` -> `raw/book/pages/page_037.md`: frontmatter source is not cited inline on this page
- L11 `inline_missing` `raw/book/pages/page_039.md` -> `raw/book/pages/page_039.md`: frontmatter source is not cited inline on this page
- L19 `inline_missing` `raw/book/pages/page_073.md` -> `raw/book/pages/page_073.md`: frontmatter source is not cited inline on this page
- L19 `section_boundary` `raw/book/pages/page_073.md` -> `raw/book/pages/page_073.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L21 `section_boundary` `raw/book/pages/page_074.md` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L23 `section_boundary` `raw/book/pages/page_075.md` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose
- L156 `section_boundary` `book p.74` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L162 `section_boundary` `book p.74` -> `raw/book/pages/page_074.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L175 `section_boundary` `book p.75` -> `raw/book/pages/page_075.md`: cited book page ends with uppercase heading only: 'ACCUMULATION RANGES'; check next page for supporting prose

### knowledge/wiki/structures/distribution.md

- L7 `inline_missing` `raw/book/pages/page_037.md` -> `raw/book/pages/page_037.md`: frontmatter source is not cited inline on this page
- L11 `inline_missing` `raw/book/pages/page_043.md` -> `raw/book/pages/page_043.md`: frontmatter source is not cited inline on this page
- L19 `inline_missing` `raw/book/pages/page_081.md` -> `raw/book/pages/page_081.md`: frontmatter source is not cited inline on this page
- L19 `section_boundary` `raw/book/pages/page_081.md` -> `raw/book/pages/page_081.md`: cited book page ends with uppercase heading only: 'HANDLING MANEUVERS'; check next page for supporting prose
- L21 `section_boundary` `raw/book/pages/page_082.md` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose
- L27 `inline_missing` `raw/book/pages/page_085.md` -> `raw/book/pages/page_085.md`: frontmatter source is not cited inline on this page
- L153 `section_boundary` `book p.82` -> `raw/book/pages/page_082.md`: cited book page ends with uppercase heading only: 'COUNTERPARTY, LIQUIDITY'; check next page for supporting prose

### knowledge/wiki/structures/trading-range.md

- L11 `inline_missing` `raw/book/pages/page_035.md` -> `raw/book/pages/page_035.md`: frontmatter source is not cited inline on this page
