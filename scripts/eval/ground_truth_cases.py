"""Curated source-anchored crypto case metadata for blind Wyckoff evals.

The real answer key is intentionally loaded from an ignored local JSON file,
not committed in this module. Keeping full ground truth out of repo history
preserves the blind-eval workflow for analysts who receive the repository.

v1 (issue #76): every case is anchored to an existing expert-analyzed crypto
chart (Wyckoff Crypto Report) — a real chart the expert already interpreted,
its directly-attached text, and a reliably reconstructible Binance OHLCV slice
up to cutoff T. There is no fixed event quota and no hard-coded case count:
the validator checks PER-CASE source provenance and quality, not set-level
event distribution. A smaller-but-valid v1 set is preferred over padding the
count with un-anchored dates.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any, Literal

AnalysisMode = Literal["forward_looking", "retrospective"]


REQUIRED_FIELDS = {
    "case_id",
    "symbol",
    "timeframe",
    "cutoff",
    "n_bars",
}

# Evaluation-facing answer fields — judge + deterministic scoring read these.
ANSWER_REQUIRED_FIELDS = {
    "event_type",
    "realized_direction",
    "decisive",
    "ground_truth",
    "analysis_mode",
}

# Provenance / reconstruction fields — the proof that ground_truth is
# source-anchored. These live ONLY in the master private key; they are never
# propagated into angle-specific answer keys, the judge payload, or the public
# manifest (see angle_answer_metadata / ANGLE_ANSWER_KEYS).
PROVENANCE_REQUIRED_FIELDS = {
    "expert_author",
    "source_path",
    "source_url",
    "source_image_path",
    "source_excerpt_location",
    "reconstruction_notes",
}

# Structured expert labels — kept for auditability. Each is either an explicit
# source value or the literal "not_stated"; never a guessed sentinel. They may
# be absent entirely (treated the same as not_stated).
EXPERT_OPTIONAL_FIELDS = {
    "expert_structure",
    "expert_phase",
    "expert_event",
    "expert_scenario",
    "expert_trigger",
    "expert_invalidation",
}

ANALYSIS_MODES = {"forward_looking", "retrospective"}
FORWARD_REALIZED_DIRECTIONS = {"up", "down", "none"}
RETROSPECTIVE_REALIZED_DIRECTION = "not_applicable"
NOT_STATED = "not_stated"

# The ONLY fields copied from a master answer record into an angle-specific
# answer key (and therefore the only answer fields reachable by snapshot
# post-processing and scoring). analysis_mode MUST be here — score_deterministic
# reads it to route retrospective cases down the N/A path; without it the
# retrospective branch would never trigger in a real run. Provenance and
# reconstruction fields are deliberately excluded.
ANGLE_ANSWER_KEYS = ("event_type", "realized_direction", "decisive", "analysis_mode")

# Every source/image path must resolve inside this repo-relative root. v1 is
# crypto-only (Binance-reconstructible); Fraser/book sources are out of scope.
RAW_CRYPTO_ROOT = Path("raw/crypto_archive")

# Explicit marker so dry-run placeholder answers can never be mistaken for a
# real source-anchored answer key in a paid/orchestrated run.
PLACEHOLDER_MARKER = "__placeholder__"

_IMAGE_REF_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


# Source-anchored v1 set. Each case_id maps to a private answer record (in the
# gitignored master key) that carries the full provenance + ground truth. See
# PRPs/reports/source-anchored-crypto-eval-set-v1-report.md for the curation
# audit (accepted/rejected candidates).
GROUND_TRUTH_CASES: list[dict[str, Any]] = [
    {
        # Wyckoff Crypto Report vol 43 — Bitcoin / TetherUS · 4h · BINANCE.
        # Forward-looking: continuation vs spring-near-15.5k scenarios, 14.3k
        # revisit = pattern failure.
        "case_id": "btc_vol43_2020_11",
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "cutoff": "2020-11-13",
        "n_bars": 120,
    },
    {
        # Wyckoff Crypto Report vol 24 — ChainLink / TetherUS · 1D · BINANCE.
        # Forward-looking: absorbed upsloping range, shallow backing-up, PnF
        # target ~$5.50.
        "case_id": "link_vol24_2020_06",
        "symbol": "LINKUSDT",
        "timeframe": "1d",
        "cutoff": "2020-06-05",
        "n_bars": 120,
    },
    {
        # Wyckoff Crypto Report vol 24 — Bitcoin (Daily). Retrospective
        # bar-by-bar "WYCKOFF STORY": absorption read; the down-bar that looks
        # like an upthrust is actually absorption. Outcome dimensions are N/A.
        "case_id": "btc_vol24_2020_06",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2020-06-05",
        "n_bars": 120,
    },
]


def angle_answer_metadata(answer: dict[str, Any]) -> dict[str, Any]:
    """Return only the allowlisted answer fields that may flow into an
    angle-specific answer key (and thus into snapshot post-processing/scoring).

    This is the single source of truth for cross-snapshot metadata propagation
    (used by build_eval_set and benchmark). Provenance and reconstruction
    fields are deliberately excluded — they stay in the master private key so
    they never reach the analyst, the judge, or the public manifest by
    construction, not merely via the judge allowlist. ``analysis_mode`` IS
    included because score_deterministic reads it.
    """
    return {key: answer[key] for key in ANGLE_ANSWER_KEYS if key in answer}


def make_placeholder_answers(
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return synthetic answers for dry-run and tests only.

    Quota-free: one placeholder answer per case, carrying ``analysis_mode`` and
    an explicit placeholder marker so a real (orchestrated) run can refuse them.
    The mode alternates purely to exercise BOTH the forward and retrospective
    scoring branches in a dry-run — it is intentionally NOT tied to a case's real
    analysis_mode (a dry-run never uses the real answer key), so do not read any
    case→mode correspondence into it.
    """
    selected = GROUND_TRUTH_CASES if cases is None else cases
    answers: dict[str, dict[str, Any]] = {}
    for index, case in enumerate(selected):
        case_id = str(case["case_id"])
        # Branch-coverage only (see docstring): every 3rd case goes retrospective.
        mode: AnalysisMode = "retrospective" if index % 3 == 2 else "forward_looking"
        realized = (
            RETROSPECTIVE_REALIZED_DIRECTION if mode == "retrospective" else "up"
        )
        answers[case_id] = {
            "event_type": "spring",
            "realized_direction": realized,
            "decisive": True,
            "analysis_mode": mode,
            PLACEHOLDER_MARKER: True,
            "ground_truth": (
                f"Dry-run placeholder answer for {case_id}; "
                "not the real eval ground truth."
            ),
        }
    return answers


def load_answer_key(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load private answer metadata from a local JSON file.

    Supported shapes:
    - {"case_01": {"event_type": ..., ...}, ...}
    - {"cases": [{"case_id": "case_01", "event_type": ..., ...}, ...]}
    """
    answer_path = Path(path)
    if not answer_path.exists():
        raise FileNotFoundError(
            f"Answer key file not found: {answer_path}. "
            "Create it outside git, e.g. data/eval/_answers/ground_truth_answers.json, "
            "or run with --dry-run for placeholder answers."
        )
    raw = json.loads(answer_path.read_text())
    if isinstance(raw, dict) and isinstance(raw.get("cases"), list):
        return _answers_from_list(raw["cases"])
    if isinstance(raw, list):
        return _answers_from_list(raw)
    if isinstance(raw, dict):
        return {str(case_id): dict(answer) for case_id, answer in raw.items()}
    raise ValueError(f"Unsupported answer key shape in {answer_path}")


def validate_event_coverage(
    cases: list[dict[str, Any]] | None = None,
    answers: dict[str, dict[str, Any]] | None = None,
    *,
    allow_placeholders: bool = False,
    raw_root: Path | None = None,
) -> None:
    """Validate per-case source anchoring and answer fields.

    Kept under the historical name ``validate_event_coverage`` so the parallel
    #77 work keeps a stable entry point, but it no longer enforces an event
    quota, a fixed case count, or a post-cutoff minimum. "Coverage" now means:
    every case carries the required metadata and a non-empty ``event_type``,
    and (for real answers) a verifiable source anchor — an existing crypto raw
    Markdown, a local image it references, and a valid excerpt range. Set-level
    event distribution is intentionally NOT enforced; quality of the source
    anchor takes priority over quota.

    An empty case set is rejected, but any count > 0 is accepted. Placeholder
    answers are accepted only when ``allow_placeholders`` is True (dry-run); a
    real run rejects them.
    """
    selected = GROUND_TRUTH_CASES if cases is None else cases
    if answers is None:
        answers = make_placeholder_answers(selected)
        allow_placeholders = True
    if not selected:
        raise ValueError(
            "GROUND_TRUTH_CASES is empty — at least one source-anchored case is required"
        )

    case_ids: list[str] = []
    for index, case in enumerate(selected, start=1):
        missing = REQUIRED_FIELDS - case.keys()
        case_id = str(case.get("case_id", f"<case #{index}>"))
        if missing:
            raise ValueError(f"{case_id} missing required fields: {sorted(missing)}")
        case_ids.append(case_id)

        if not str(case["symbol"]).strip():
            raise ValueError(f"{case_id} symbol must be non-empty")
        if not str(case["timeframe"]).strip():
            raise ValueError(f"{case_id} timeframe must be non-empty")
        if int(case["n_bars"]) <= 0:
            raise ValueError(f"{case_id} n_bars must be positive")
        _parse_cutoff(case["cutoff"], case_id=case_id)

        answer = answers.get(case_id)
        if answer is None:
            raise ValueError(f"{case_id} missing answer key entry")
        _validate_answer(
            case_id, answer, allow_placeholders=allow_placeholders, raw_root=raw_root
        )

    duplicate_ids = sorted(cid for cid, count in Counter(case_ids).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"Duplicate case_id values: {duplicate_ids}")


def _validate_answer(
    case_id: str,
    answer: dict[str, Any],
    *,
    allow_placeholders: bool,
    raw_root: Path | None,
) -> None:
    is_placeholder = bool(answer.get(PLACEHOLDER_MARKER))
    if is_placeholder and not allow_placeholders:
        raise ValueError(
            f"{case_id} uses a dry-run placeholder answer; a real run requires a "
            "source-anchored answer key (remove the placeholder marker)"
        )

    missing_answer_fields = ANSWER_REQUIRED_FIELDS - answer.keys()
    if missing_answer_fields:
        raise ValueError(
            f"{case_id} answer missing required fields: {sorted(missing_answer_fields)}"
        )

    analysis_mode = answer["analysis_mode"]
    if analysis_mode not in ANALYSIS_MODES:
        raise ValueError(
            f"{case_id} analysis_mode must be one of {sorted(ANALYSIS_MODES)}, "
            f"got {analysis_mode!r}"
        )

    if not str(answer["event_type"]).strip():
        raise ValueError(f"{case_id} event_type must be non-empty")

    realized = answer["realized_direction"]
    if analysis_mode == "retrospective":
        if realized != RETROSPECTIVE_REALIZED_DIRECTION:
            raise ValueError(
                f"{case_id} retrospective realized_direction must be "
                f"{RETROSPECTIVE_REALIZED_DIRECTION!r}, got {realized!r}"
            )
    elif realized not in FORWARD_REALIZED_DIRECTIONS:
        raise ValueError(
            f"{case_id} forward realized_direction must be one of "
            f"{sorted(FORWARD_REALIZED_DIRECTIONS)}, got {realized!r}"
        )

    if not isinstance(answer["decisive"], bool):
        raise ValueError(f"{case_id} decisive must be bool")
    if not str(answer["ground_truth"]).strip():
        raise ValueError(f"{case_id} ground_truth must be non-empty")

    if is_placeholder:
        return  # placeholders carry no provenance — already gated above

    _validate_provenance(case_id, answer, raw_root=raw_root)


def _validate_provenance(
    case_id: str, answer: dict[str, Any], *, raw_root: Path | None
) -> None:
    root = raw_root if raw_root is not None else Path.cwd()

    missing = PROVENANCE_REQUIRED_FIELDS - answer.keys()
    if missing:
        raise ValueError(
            f"{case_id} answer missing provenance fields: {sorted(missing)}"
        )

    # Reject empty strings and guessed sentinels: a field is either an explicit
    # value or the literal "not_stated".
    for field in sorted(PROVENANCE_REQUIRED_FIELDS | EXPERT_OPTIONAL_FIELDS):
        if field == "source_excerpt_location" or field not in answer:
            continue
        value = answer[field]
        if isinstance(value, str) and not value.strip():
            raise ValueError(
                f"{case_id} {field} must be a non-empty value or {NOT_STATED!r}"
            )

    source_path = _resolve_within(
        root, answer["source_path"], case_id=case_id, field="source_path"
    )
    image_path = _resolve_within(
        root, answer["source_image_path"], case_id=case_id, field="source_image_path"
    )
    if not source_path.is_file():
        raise ValueError(
            f"{case_id} source_path does not exist: {answer['source_path']}"
        )
    if not image_path.is_file():
        raise ValueError(
            f"{case_id} source_image_path does not exist: {answer['source_image_path']}"
        )

    start, end = _validate_excerpt_range(
        case_id, answer["source_excerpt_location"], source_path
    )
    _validate_image_reference(case_id, source_path, start, end, image_path)


def _resolve_within(
    root: Path, raw_value: Any, *, case_id: str, field: str
) -> Path:
    """Resolve a repo-relative raw path and assert it stays inside RAW_CRYPTO_ROOT.

    ``.resolve()`` follows symlinks, so a symlink or ``..`` that escapes the
    crypto root is rejected here, not silently followed.
    """
    candidate = Path(str(raw_value))
    if candidate.is_absolute():
        raise ValueError(
            f"{case_id} {field} must be repo-relative, got absolute path: {raw_value}"
        )
    base = (root / RAW_CRYPTO_ROOT).resolve()
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(
            f"{case_id} {field} must resolve inside {RAW_CRYPTO_ROOT}: {raw_value}"
        )
    return resolved


def _validate_excerpt_range(
    case_id: str, excerpt: Any, source_path: Path
) -> tuple[int, int]:
    if (
        not isinstance(excerpt, dict)
        or "start_line" not in excerpt
        or "end_line" not in excerpt
    ):
        raise ValueError(
            f"{case_id} source_excerpt_location must have start_line and end_line"
        )
    start = excerpt["start_line"]
    end = excerpt["end_line"]
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or isinstance(start, bool)
        or isinstance(end, bool)
    ):
        raise ValueError(
            f"{case_id} source_excerpt_location start_line/end_line must be integers"
        )
    if start < 1 or end < start:
        raise ValueError(
            f"{case_id} source_excerpt_location must satisfy 1 <= start_line <= end_line"
        )
    line_count = len(source_path.read_text(encoding="utf-8").splitlines())
    if end > line_count:
        raise ValueError(
            f"{case_id} source_excerpt_location end_line {end} exceeds file length {line_count}"
        )
    return start, end


def _validate_image_reference(
    case_id: str, source_path: Path, start: int, end: int, image_path: Path
) -> None:
    """Assert the excerpt directly references the source image.

    The Markdown uses relative refs like ``![](../images/<vol>/<file>.png)``;
    resolved against the post's directory it must equal ``source_image_path``,
    and the reference must occur within the cited [start, end] line range — so
    the answer key cannot point at an image the analyzed passage never shows.
    """
    lines = source_path.read_text(encoding="utf-8").splitlines()
    posts_dir = source_path.parent
    for line in lines[start - 1 : end]:
        for match in _IMAGE_REF_PATTERN.finditer(line):
            ref = match.group(1).strip()
            if not ref or ref.startswith(("http://", "https://")):
                continue
            if (posts_dir / ref).resolve() == image_path:
                return
    raise ValueError(
        f"{case_id} source_image_path is not referenced by the Markdown within "
        f"lines {start}-{end} of {source_path}"
    )


def _answers_from_list(raw_answers: list[Any]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    for index, raw_answer in enumerate(raw_answers, start=1):
        if not isinstance(raw_answer, dict):
            raise ValueError(f"Answer #{index} must be an object")
        if "case_id" not in raw_answer:
            raise ValueError(f"Answer #{index} missing case_id")
        answer = dict(raw_answer)
        case_id = str(answer.pop("case_id"))
        answers[case_id] = answer
    return answers


def _parse_cutoff(value: Any, *, case_id: str) -> datetime:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{case_id} cutoff must be a positive millisecond epoch")
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

    raw = str(value)
    if "T" not in raw and " " not in raw:
        raw = raw + "T00:00:00"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{case_id} has invalid cutoff: {value!r}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
