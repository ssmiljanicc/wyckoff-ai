# Feature: Vision Caption Pass

## Summary

Implement issue #5 by adding a Python CLI script at `scripts/vision_caption_pass.py` that finds raw Markdown chart image references with empty alt text, captions the local image with Claude Vision, and writes the generated caption back as Markdown alt text.

The implementation must be idempotent: image references with non-empty alt text are skipped on later runs. The operator workflow must run a 20-image pilot with `claude-sonnet-4-6` before any full corpus pass, log captioned/skipped/failed counts, and report approximate API cost in USD.

## User Story

As a Wyckoff skill maintainer, I want all recovered chart images to have concise semantic captions, so agents that cannot inspect images still have chart context during wiki ingestion and skill reconstruction.

## Problem Statement

The raw Fraser and crypto Markdown files currently include inline image references without alt text, for example `![](../images/...)`. The wiki schema says #5 captions should be copied verbatim during ingest, and if an image remains uncaptioned the wiki ingest must add TODO markers. Without #5, downstream issue #7 either loses visual meaning or requires re-ingest after captions land.

Current local evidence:

- `pyproject.toml:12-15` already defines a `[vision]` optional dependency with `anthropic>=0.40`.
- `CLAUDE.md:210-221` defines the expected captioned Markdown image format and downstream ingest behavior.
- `knowledge/wiki/log.md:30-38` records that Vision captions should land before ingest.
- `raw/bruce_fraser/posts/...` has 243 Markdown posts with 854 empty image refs in this worktree.
- `raw/crypto_archive/posts/...` has 46 Markdown posts with 190 empty image refs and 190 local image files.
- `raw/bruce_fraser/images/` is gitignored at `.gitignore:158-162`, so the implementation must fail clearly when referenced local images are absent and document rerunning the existing Fraser downloader to populate local ignored images.

## Solution Statement

Create a narrow, resumable CLI that:

1. Scans `raw/bruce_fraser/posts/**/*.md`, `raw/crypto_archive/posts/**/*.md`, and later `raw/book/**/*.md` if present.
2. Parses Markdown image references, preserving references that already have non-empty alt text.
3. Resolves relative image paths from each Markdown file to local files.
4. Sends one image at a time to Claude using the exact prompt from issue #5:

   `Describe this financial chart in one or two sentences. Focus on: what instrument, what structure or pattern is shown, what phase or key event is labeled if any.`

5. Writes sanitized caption text into the Markdown alt field.
6. Supports `--limit 20` for the Sonnet pilot, `--dry-run`, source filters, model override, retry/backoff, and JSONL logging.
7. Prints and logs captioned/skipped/failed totals plus approximate USD cost from API usage tokens.

## Metadata

| Field | Value |
| --- | --- |
| Feature type | `NEW_CAPABILITY` |
| Complexity | `MEDIUM` |
| Issue | https://github.com/ssmiljanicc/wyckoff-ai/issues/5 |
| PRD | `.claude/PRPs/prds/faza-1-skill-modernization.prd.md` |
| PRD phase | Phase 1, Raw data ready |
| Plan path | `PRPs/plans/vision-caption-pass.plan.md` |
| Worktree | `/Users/ssmiljanic/.kild/worktrees/wyckoff-ai/vision-captions` |
| Branch | `kild/vision-captions` |
| Primary files | `scripts/vision_caption_pass.py`, raw Markdown files after running the script |
| Model | `claude-sonnet-4-6` default |
| Secret | `ANTHROPIC_API_KEY` from environment only; never commit |

## UX Design

Operator workflow before:

```text
raw Markdown
  ![](../images/chart.png)
       |
       v
wiki ingest sees empty alt text
       |
       v
TODO marker / visual context missing
```

Operator workflow after:

```text
uv run --extra vision python scripts/vision_caption_pass.py --limit 20
       |
       v
review 20 caption diffs and log summary
       |
       v
uv run --extra vision python scripts/vision_caption_pass.py
       |
       v
raw Markdown
  ![BTC daily chart showing absorption after a shakeout...](../images/chart.png)
       |
       v
wiki ingest copies alt text verbatim
```

| Location | Before | After | User Impact |
| --- | --- | --- | --- |
| `raw/*/posts/*.md` | `![](path)` image refs | `![caption](path)` refs for successfully captioned images | Source corpus carries visual semantics |
| CLI | No caption tool | `scripts/vision_caption_pass.py` with pilot/full/dry-run modes | Operator can run safely and resume |
| Logs/stdout | No API/cost audit | Captioned/skipped/failed plus approximate cost | Cost and failures are visible |
| Wiki ingest | Must mark empty image alt as TODO | Can copy captions directly | Avoids avoidable re-ingest churn |

## Mandatory Reading

- `.claude/PRPs/prds/faza-1-skill-modernization.prd.md`
  - Read Phase 1 success signal and issue #5 dependency context.
- `CLAUDE.md:210-221`
  - Defines the final Markdown alt-text convention and downstream wiki behavior.
- `knowledge/wiki/log.md:30-38`
  - Confirms captions should land before ingest.
- `pyproject.toml:12-15`
  - Confirms `anthropic` is already available through the `vision` extra.
- `scripts/download_fraser_images.py:20-28`, `scripts/download_fraser_images.py:56-58`, `scripts/download_fraser_images.py:266-292`
  - Mirrors repo-root constants, Markdown image path format, argparse style, and summary printing.
- `scripts/scrape_crypto_archive.py:238-296`, `scripts/scrape_crypto_archive.py:310-363`, `scripts/scrape_crypto_archive.py:372-424`
  - Mirrors post processing, idempotent skip behavior, manifest/stat accumulation, and final summary output.
- `raw/crypto_archive/posts/wyckoff-crypto-report-vol-20.md:10-14`
  - Example empty alt image refs adjacent to source text.
- `raw/bruce_fraser/posts/articles-wyckoff-2016-06-brexit-and-os.md:7-33`
  - Example Fraser image refs and nearby article context.

## Patterns to Mirror

| Category | File:Lines | Pattern Description | Code Snippet |
| --- | --- | --- | --- |
| NAMING | `scripts/download_fraser_images.py:20-28` | Module-level repo path constants with `Path(__file__).resolve().parents[1]`. | `REPO_ROOT = Path(__file__).resolve().parents[1]` |
| CLI | `scripts/download_fraser_images.py:266-292` | Simple `argparse` CLI and final plain-text stats. | `parser.add_argument("--delay", type=float, default=0.5)` |
| IDEMPOTENCY | `scripts/scrape_crypto_archive.py:322-331` | Skip already complete work and update stats instead of redoing it. | `if html_path.exists() and post_path.exists() and slug in previous and not rebuild_existing:` |
| MARKDOWN | `scripts/scrape_crypto_archive.py:252-257` | Existing Markdown image syntax keeps source alt text when present. | `emit(f"![{alt}]({path})")` |
| ATOMIC WRITE | `scripts/scrape_crypto_archive.py:366-369` | Write temp file then replace final path. | `tmp_path.write_text(...); tmp_path.replace(OUTPUT_MANIFEST)` |
| ERRORS | `scripts/scrape_crypto_archive.py:409-414` | Catch exception, record error count, print to stderr, return non-zero. | `print(f"ERROR: {exc}", file=sys.stderr)` |
| LOGGING | `scripts/download_fraser_images.py:283-292` | End-of-run summary includes all counts and byte totals. | `print(f"images skipped: {stats.skipped}")` |
| TYPES | `scripts/scrape_crypto_archive.py:64-72` | Dataclass for accumulating counters. | `@dataclass class Stats:` |
| CONFIG | `pyproject.toml:12-15` | Optional dependency extras for task-specific tooling. | `vision = ["anthropic>=0.40"]` |
| FLOW | `CLAUDE.md:212-221` | Captions are stored as Markdown alt text and copied by wiki ingest. | `![Accumulation schematic showing SC, AR, and spring at support](images/page_047_fig_1.png)` |

## External Documentation

- [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
  - KEY_INSIGHT: image content blocks may be base64 encoded, and Claude works best when the image comes before the text prompt.
  - APPLIES_TO: `caption_image()` request payload in `scripts/vision_caption_pass.py`.
  - GOTCHA: supported image types are JPEG, PNG, GIF, and WebP; animations use only the first frame, and large images may be resized.
- [Anthropic Vision cost guidance](https://platform.claude.com/docs/en/build-with-claude/vision#calculate-image-costs)
  - KEY_INSIGHT: image input tokens are approximately `width * height / 750`, capped by model native resolution; cost should be estimated from usage tokens when available.
  - APPLIES_TO: final cost summary and pilot/full-pass budget reporting.
  - GOTCHA: high-resolution images increase latency and token usage; do not upscale images for this task.
- [Anthropic Python SDK docs](https://platform.claude.com/docs/en/api/sdks/python)
  - KEY_INSIGHT: use `anthropic.Anthropic()` and `client.messages.create(...)`; the SDK reads `ANTHROPIC_API_KEY` from the environment.
  - APPLIES_TO: API client setup.
  - GOTCHA: keep the API key out of args, logs, commits, and `.env` files.
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
  - KEY_INSIGHT: `Claude Sonnet 4.6` pricing is listed as $3/MTok input and $15/MTok output; Batch API has a discount but this issue requests a per-image script and pilot, so synchronous per-image calls are simpler and more auditable.
  - APPLIES_TO: approximate cost calculation.
  - GOTCHA: default `global` routing uses standard pricing; `inference_geo: "us"` changes pricing and should not be introduced unless explicitly required later.
- [Anthropic rate limits](https://platform.claude.com/docs/en/api/rate-limits)
  - KEY_INSIGHT: Messages API rate limits are measured by requests per minute and token throughput.
  - APPLIES_TO: `--delay`, retries, and safe full-pass behavior.
  - GOTCHA: full corpus passes may hit rate limits; handle 429-style errors with bounded retry/backoff and resumability.

## Files to Change

| File | Change |
| --- | --- |
| `scripts/vision_caption_pass.py` | Add new CLI script for scanning, captioning, writing Markdown, logging, and cost summary. |
| `raw/bruce_fraser/posts/*.md` | Updated by running script after Fraser images exist locally; empty alt refs become non-empty captions. |
| `raw/crypto_archive/posts/*.md` | Updated by running script; empty alt refs become non-empty captions. |
| `raw/book/**/*.md` | Only if #4 has produced book Markdown and images by implementation time; include automatically if present. |
| Optional `raw/vision_caption_pass.jsonl` | Generated runtime log if implementer chooses committed audit log; otherwise use stdout plus ignored local log. |

Do not modify `pyproject.toml` unless the existing `anthropic>=0.40` extra is insufficient during implementation.

## NOT Building

- No wiki ingest for #7.
- No rewrite of `SKILL.md`.
- No Opus full pass unless the 20-image Sonnet pilot is judged materially vague.
- No image download implementation beyond documenting/running existing scripts if local ignored images are missing.
- No bypass of paywalls or external scraping.
- No storage or committing of `ANTHROPIC_API_KEY`.
- No trading signal generation or chart classification model.

## Step-by-Step Tasks

### 1. Confirm Local Image Preconditions

- Action: verify source posts and referenced local image files before writing caption code behavior around missing files.
- File: no code change.
- Instruction: count empty alt refs and local files. Note that Fraser images are gitignored and may be absent in a fresh worktree.
- Pattern to mirror: PRD/inventory source counts in `raw/INVENTORY.md:150-165`.
- Gotchas: do not treat missing `raw/bruce_fraser/images/` as a caption failure caused by Claude; it is a local data precondition.
- Validation command:

```bash
find raw/bruce_fraser/posts -type f -name '*.md' | wc -l
find raw/crypto_archive/posts -type f -name '*.md' | wc -l
rg -n '!\[\]\(' raw/bruce_fraser/posts raw/crypto_archive/posts | wc -l
find raw/crypto_archive/images -type f | wc -l
find raw/bruce_fraser/images -type f 2>/dev/null | wc -l
```

### 2. Create Script Skeleton and CLI

- Action: add `scripts/vision_caption_pass.py`.
- File: `scripts/vision_caption_pass.py`.
- Instruction: use `#!/usr/bin/env python3`, `from __future__ import annotations`, `argparse`, `dataclasses`, `Path`, and module-level constants:
  - `REPO_ROOT`
  - `DEFAULT_POST_ROOTS = [raw/bruce_fraser/posts, raw/crypto_archive/posts, raw/book]` filtering to existing paths
  - `DEFAULT_MODEL = "claude-sonnet-4-6"`
  - `PROMPT = "Describe this financial chart in one or two sentences. Focus on: what instrument, what structure or pattern is shown, what phase or key event is labeled if any."`
- CLI flags:
  - `--model`, default `claude-sonnet-4-6`
  - `--limit`, for pilot
  - `--source`, repeatable choices `bruce_fraser`, `crypto_archive`, `book`
  - `--dry-run`
  - `--delay`, default modest delay such as `0.2`
  - `--max-retries`, default `3`
  - `--log-path`, optional JSONL path
  - `--force`, recaption non-empty alt text only when explicitly requested
- Pattern to mirror: simple parser in `scripts/download_fraser_images.py:266-270`.
- Gotchas: default mode must skip non-empty alt text; `--force` must be opt-in and should not be used in acceptance.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --help
```

### 3. Parse Markdown Image References Safely

- Action: implement image reference scanning.
- File: `scripts/vision_caption_pass.py`.
- Instruction: define a small dataclass such as `ImageRef(markdown_path, start, end, alt, rel_path, abs_path)`. Use a compiled regex for inline Markdown images:

```python
IMAGE_RE = re.compile(r"!\[([^\]\n]*)\]\(([^)\n]+)\)")
```

Skip paths that are remote URLs. Resolve local relative paths from `markdown_path.parent / rel_path`. Ignore escaped edge cases only if documented in a comment; current generated raw files use simple refs.
- Pattern to mirror: generated Markdown images from `scripts/download_fraser_images.py:56-58` and `scripts/scrape_crypto_archive.py:252-257`.
- Imports/types: `re`, `dataclass`, `Path`, `Iterator`.
- Gotchas: preserve original `rel_path` exactly in the output; only replace the alt substring. Treat whitespace-only alt as empty.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --limit 5
```

### 4. Add Idempotency and Missing-File Classification

- Action: classify each discovered image reference as caption candidate, skipped with existing alt, or failed/missing local file.
- File: `scripts/vision_caption_pass.py`.
- Instruction: stats must include `found`, `captioned`, `skipped`, `failed`, `missing_files`, `input_tokens`, `output_tokens`, and `approx_cost_usd`. Empty alt with missing image increments `failed` and `missing_files`, logs failure detail, and keeps Markdown unchanged.
- Pattern to mirror: idempotent skip from `scripts/scrape_crypto_archive.py:322-331`.
- Gotchas: if `raw/bruce_fraser/images/` is absent, the pilot should still work by filtering to `--source crypto_archive`; full pass requires local images.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --source crypto_archive --limit 5
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --source bruce_fraser --limit 5
```

### 5. Implement Claude Vision Caption Call

- Action: call Anthropic Messages API for one image.
- File: `scripts/vision_caption_pass.py`.
- Instruction: create `caption_image(client, image_path, model) -> CaptionResult`. Read image bytes, base64 encode, detect media type. Use content order `[image block, text block]`. Use the exact issue prompt. Use `max_tokens` around 120 because captions must be one or two sentences.
- Pattern to mirror: no existing Anthropic use; follow official Anthropic Vision and Python SDK docs.
- Imports/types: `base64`, `mimetypes`, `anthropic`.
- Gotchas:
  - `.img` crypto files may have unknown MIME by suffix; inspect magic bytes for PNG/JPEG/GIF/WebP fallback or fail clearly.
  - If response has multiple content blocks, concatenate only text blocks.
  - Use API usage fields from the response for cost calculation.
  - Do not log raw base64, request bodies, or secret-derived values.
- Validation command:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --source crypto_archive --limit 1 --dry-run
```

### 6. Add Retry, Delay, and Failure Logging

- Action: implement bounded retry/backoff around caption calls and structured per-image logging.
- File: `scripts/vision_caption_pass.py`.
- Instruction: on transient API errors, retry up to `--max-retries`, sleeping with simple exponential backoff plus `--delay`. Record one JSON object per image when `--log-path` is set:
  - `event`: `captioned`, `skipped`, or `failed`
  - `markdown_path`
  - `image_path`
  - `model`
  - `input_tokens`
  - `output_tokens`
  - `approx_cost_usd`
  - `error` for failures only
- Pattern to mirror: error count and stderr behavior from `scripts/scrape_crypto_archive.py:409-414`.
- Gotchas: keep running after per-image failures; return non-zero only for script-level errors or when `failed > 0` after a non-dry run, depending on implementation preference. Document the choice in help text.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --limit 5 --log-path /tmp/vision_caption_pass.jsonl
tail -5 /tmp/vision_caption_pass.jsonl
```

### 7. Write Markdown Atomically

- Action: replace empty alt text with sanitized caption text.
- File: `scripts/vision_caption_pass.py`.
- Instruction: process one Markdown file at a time, collect replacements, apply them from end to start or rebuild the file content from slices, then write through a temp file and replace the original. Sanitize captions by collapsing whitespace and replacing `[` and `]` with parentheses or removing them so Markdown image syntax remains valid.
- Pattern to mirror: atomic temp replacement in `scripts/scrape_crypto_archive.py:366-369`.
- Gotchas: if multiple image refs are in one file, avoid offset drift by applying replacements from the end of the file backward. Preserve final newline and all non-image content.
- Validation command:

```bash
git diff -- raw/crypto_archive/posts | head -80
```

### 8. Print Final Summary and Cost

- Action: print run summary at the end.
- File: `scripts/vision_caption_pass.py`.
- Instruction: include at minimum:
  - `image refs found`
  - `images captioned`
  - `images skipped`
  - `images failed`
  - `missing files`
  - `input tokens`
  - `output tokens`
  - `approx API cost USD`
- Cost formula for Sonnet 4.6:
  - input: `$3 / 1_000_000`
  - output: `$15 / 1_000_000`
  - if model pricing is unknown, still print usage tokens and mark cost estimate as unavailable unless `--input-price-per-mtok` and `--output-price-per-mtok` overrides are supplied.
- Pattern to mirror: summary output in `scripts/download_fraser_images.py:283-292`.
- Gotchas: "approx" is required because API pricing may change and image tokenization may vary.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --limit 3
```

### 9. Run the Required 20-Image Sonnet Pilot

- Action: run pilot on available local images with Sonnet.
- File: raw Markdown files are changed unless `--dry-run`; this is the first real caption pass.
- Instruction: prefer a mixed pilot if Fraser images are locally present; otherwise run `--source crypto_archive --limit 20` and separately document Fraser image precondition. Review diff manually for concise one/two sentence captions and domain usefulness.
- Pattern to mirror: issue #5 explicit 20-image pilot recommendation.
- Gotchas: do not proceed to full pass if captions are vague on structures/events; consider prompt refinement first, and only escalate model after pilot review.
- Validation command:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --limit 20 --log-path /tmp/vision_caption_pilot.jsonl
git diff -- raw | sed -n '1,220p'
```

### 10. Ensure Fraser Images Are Present Before Full Pass

- Action: populate ignored Fraser image files locally if absent.
- File: no new implementation if existing script works.
- Instruction: if `find raw/bruce_fraser/images -type f` is zero, run the existing downloader. This uses existing #2 script output and does not change the #5 implementation.
- Pattern to mirror: Fraser downloader output roots in `scripts/download_fraser_images.py:24-27`.
- Gotchas: `raw/bruce_fraser/images/` is gitignored, so full pass can require a local data preparation step even on a clean checkout.
- Validation command:

```bash
uv run python scripts/download_fraser_images.py
find raw/bruce_fraser/images -type f | wc -l
```

### 11. Run Full Caption Pass

- Action: after pilot approval, run the full idempotent pass.
- File: raw Markdown files under `raw/bruce_fraser/posts`, `raw/crypto_archive/posts`, and `raw/book` if present.
- Instruction: run without `--limit`, keep JSONL log outside committed source unless project owner wants an audit artifact committed.
- Pattern to mirror: final count summary in existing raw scripts.
- Gotchas:
  - Re-runs must show already-captioned images as skipped.
  - Book captions are only included if #4 has produced book Markdown/images.
  - If any failures remain, inspect and decide whether unsupported formats or missing images should be fixed before closing issue #5.
- Validation command:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --log-path /tmp/vision_caption_full.jsonl
rg -n '!\[\]\(' raw/bruce_fraser/posts raw/crypto_archive/posts raw/book 2>/dev/null || true
```

### 12. Final Idempotency Verification

- Action: run a second dry run or real run to confirm no already-captioned images are modified.
- File: no expected changes.
- Instruction: command should report captioned `0` for sources already completed and skipped equal to captioned corpus refs.
- Pattern to mirror: skip behavior from existing scrapers.
- Gotchas: do not use `--force`.
- Validation command:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --dry-run
git diff --check
git status --short
```

## Testing Strategy

Focused tests are enough because this repo has script-style data tooling and no existing pytest suite.

- Static/script import smoke:

```bash
uv run --extra vision python -m py_compile scripts/vision_caption_pass.py
```

- CLI smoke:

```bash
uv run --extra vision python scripts/vision_caption_pass.py --help
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --limit 5
```

- Parser/idempotency manual fixture:
  - Use current raw files as fixtures.
  - Confirm non-empty alt refs are skipped after pilot.
  - Confirm empty alt refs are counted as candidates before pilot.

- API pilot:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --limit 20 --log-path /tmp/vision_caption_pilot.jsonl
```

- Full pass acceptance:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --log-path /tmp/vision_caption_full.jsonl
rg -n '!\[\]\(' raw/bruce_fraser/posts raw/crypto_archive/posts raw/book 2>/dev/null || true
```

## Validation Commands

Run before implementation:

```bash
git status --short --branch
find . -maxdepth 3 -type f \( -name 'pyproject.toml' -o -name 'package.json' -o -name 'go.mod' -o -name 'Cargo.toml' \) -print
rg -n '!\[\]\(' raw/bruce_fraser/posts raw/crypto_archive/posts | wc -l
```

Run after adding the script:

```bash
uv run --extra vision python -m py_compile scripts/vision_caption_pass.py
uv run --extra vision python scripts/vision_caption_pass.py --help
uv run --extra vision python scripts/vision_caption_pass.py --dry-run --limit 5
```

Run for required pilot:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --limit 20 --log-path /tmp/vision_caption_pilot.jsonl
git diff -- raw | sed -n '1,220p'
```

Run for full pass:

```bash
ANTHROPIC_API_KEY=... uv run --extra vision python scripts/vision_caption_pass.py --log-path /tmp/vision_caption_full.jsonl
rg -n '!\[\]\(' raw/bruce_fraser/posts raw/crypto_archive/posts raw/book 2>/dev/null || true
uv run --extra vision python scripts/vision_caption_pass.py --dry-run
git diff --check
```

## Acceptance Criteria

- `scripts/vision_caption_pass.py` exists and runs with `uv run --extra vision`.
- Script uses `claude-sonnet-4-6` by default.
- Script reads `ANTHROPIC_API_KEY` from the environment via the Anthropic SDK; no key is committed or printed.
- Script skips every Markdown image ref with non-empty alt text unless `--force` is explicitly provided.
- Script captions empty alt refs by loading local image files and sending one image plus the required prompt to Claude.
- Script writes captions back as Markdown alt text without changing image paths or unrelated content.
- Pilot command captions 20 images with Sonnet before full pass.
- Logs/stdout include captioned, skipped, failed, missing-file counts, token usage, and approximate API cost USD.
- Full pass leaves no empty alt refs for image files that exist locally.
- Re-running without `--force` captions zero already-captioned images and reports them as skipped.

## Completion Checklist

- [ ] Read issue #5 and this plan.
- [ ] Confirm local image availability, especially ignored Fraser images.
- [ ] Implement `scripts/vision_caption_pass.py`.
- [ ] Compile and CLI-smoke the script.
- [ ] Run dry-run candidate scan.
- [ ] Run required 20-image Sonnet pilot.
- [ ] Manually review pilot captions for specificity and one/two sentence length.
- [ ] Run full caption pass after pilot approval.
- [ ] Run idempotency verification.
- [ ] Ensure `ANTHROPIC_API_KEY` and local logs are not committed.
- [ ] Commit script plus updated raw Markdown captions needed for issue #5.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Fraser images absent because `raw/bruce_fraser/images/` is gitignored | Full pass fails for 854 refs | Detect missing files clearly; run existing `scripts/download_fraser_images.py` locally before full pass |
| Sonnet captions are too generic for Wyckoff structures | Weak downstream wiki captions | Required 20-image pilot and manual review before full pass |
| API rate limits during ~1,000 image pass | Interrupted run | Per-image idempotency, retries/backoff, and safe resume |
| Unsupported or ambiguous `.img` MIME files | Individual failures | Detect magic bytes; log unsupported files; leave Markdown unchanged |
| Markdown corruption from brackets/newlines in captions | Broken raw source refs | Sanitize captions and write atomically |
| Cost estimate drift if pricing changes | Misleading budget | Mark cost as approximate and calculate from response usage tokens plus configurable prices |
| Accidentally committing secrets/logs | Security issue | Use SDK env var behavior only; keep logs in `/tmp` by default or explicitly review before commit |

## Notes

- Current measured empty alt refs in this worktree: 854 Fraser + 190 crypto = 1,044 refs.
- Current measured local crypto images: 190 files.
- Current measured local Fraser images: 0 files because `raw/bruce_fraser/images/` is gitignored; issue #2's downloader should repopulate them locally.
- PRD says Phase 1 is already `in-progress`; this plan does not update the PRD table because there is no plan column and the selected phase status is already correct.
- Next recommended command after this plan is committed:

```bash
$prp-implement PRPs/plans/vision-caption-pass.plan.md
```
