#!/usr/bin/env python3
"""Generate optional, local Fraser chart-header OCR evidence on macOS.

The generated JSON is evidence, not extract metadata. It never edits the
expert corpus and is consumed only when explicitly passed to the validator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from spona.validated_ingest.core import validator as core


SCHEMA_VERSION = "fraser-header-ocr/v1"
PARSER_VERSION = 10
MIN_CONFIDENCE = 0.85
RUNS_PER_IMAGE = 2
ENGINE = "Apple Vision VNRecognizeTextRequest accurate"
UNKNOWN = "unknown"
MAX_ASSET_X = 0.50
MIN_ASSET_HEADER_Y = 0.895
MAX_EXPLICIT_HEADER_OFFSET = 0.05
MAX_PANEL_HEADER_X = 0.08

_EXPLICIT_ASSET_RE = re.compile(r"^[^A-Z0-9]{0,2}\$(?P<ticker>[A-Z][A-Z0-9]{0,9})\b")
_EXPLICIT_COMPOSITE_ASSET_RE = re.compile(
    r"^[^A-Z0-9]{0,2}\$(?P<left>[A-Z][A-Z0-9]{0,9})"
    r":\$(?P<right>[A-Z][A-Z0-9]{0,9})\b"
)
_PANEL_ASSET_RE = re.compile(
    r"^(?:[^A-Z$]{0,3}|[A-Z]\d{1,2}\s*)\$(?P<ticker>[A-Z][A-Z0-9]{0,9})\b"
)
_GLUED_DECIMAL_QUOTE_PANEL_RE = re.compile(
    r"^(?:[^A-Z$]{0,3}|[A-Z]\d{1,2}\s*)\$"
    r"(?P<ticker>[A-Z]+)(?P<quote>\d{2,}\.\d+)(?:\s|$)"
)
_IMPLICIT_PANEL_ASSET_RE = re.compile(
    r"^\d{1,2}\s+(?P<ticker>[A-Z]{1,5})\s+-?\d"
)
_PRIMARY_SERIES_ASSET_RE = re.compile(
    r"^\d{1,2}\s*(?P<ticker>[A-Z][A-Z0-9]{0,9})\s+"
    r"\((?:daily|weekly|monthly)\)(?:\s|$)",
    re.IGNORECASE,
)
_IMPLICIT_ASSET_RE = re.compile(r"^(?P<ticker>[A-Z]{1,5})\b(?:\s|$)")
_INDEX_TITLE_SUFFIX_RE = re.compile(r"\bINDX\s*$")
_MARKET_TITLE_SUFFIX_RE = re.compile(
    r"\b(?:NYSE(?:\s+ARCA)?|NASDAQ(?:\s+GS)?|AMEX|CME|INDX)\s*$"
)
_MARKET_HEADER_MARKER_RE = re.compile(
    r"\b(?:NYSE(?:\s+ARCA)?|NASDAQ(?:\s+GS)?|AMEX|CME|INDX)\b"
)
_CODED_PANEL_PREFIX_RE = re.compile(r"^[A-Z]\d{1,2}\s*\$")
_NUMERIC_PRIMARY_PANEL_PREFIX_RE = re.compile(r"^\d{1,2}\s*\$")
_EXPLICIT_PRICE_LEGEND_RE = re.compile(
    r"^[^A-Z0-9$]{1,3}\s*\$[A-Z][A-Z0-9]{0,9}\s+-?[\d,.]+(?:\s|$)"
)
_TIMEFRAME_RE = re.compile(r"\((daily|weekly|monthly)\)", re.IGNORECASE)
_IGNORED_ASSETS = {
    "OPEN",
    "HIGH",
    "LOW",
    "LAST",
    "CLOSE",
    "VOLUME",
    "CHG",
    # Vision can render the leading dollar sign in "$INDU" as an S on small
    # P&F headers. It is an observed OCR error, not an independently legible
    # ticker, so abstain instead of adding a fuzzy alias.
    "SINDU",
}
_ASSET_ALIASES = {"INDU": "DJIA"}

ObservationRunner = Callable[[Path], list[dict]]


def _evidence_observation(observation: dict) -> dict:
    return {
        "text": str(observation.get("text", "")),
        "confidence": float(observation.get("confidence", 0.0)),
        "x": float(observation.get("x", 0.0)),
        "y": float(observation.get("y", 0.0)),
        "w": float(observation.get("w", 0.0)),
        "h": float(observation.get("h", 0.0)),
    }


def _parsed_field(candidates: dict[str, list[dict]]) -> dict:
    values = sorted(candidates)
    selected = values[0] if len(values) == 1 else UNKNOWN
    return {
        "value": selected,
        "unique": len(values) == 1,
        "candidates": values,
        "evidence": candidates.get(selected, []),
    }


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _suspicious_title_ocr(text: str, ticker: str, ticker_end: int) -> bool:
    """Abstain when a title token nearly names its instrument but disagrees.

    This is only a rejection signal: it never repairs or invents a ticker.
    Exact/prefix relationships such as ``GOLD Gold``, ``GOOG Google`` and
    ``GUILD Guild`` remain eligible.
    """

    name = re.match(r"\s*([A-Za-z]{4,})\b", text[ticker_end:])
    if name is None or len(ticker) < 4:
        return False
    title_word = name.group(1).upper()
    if title_word.startswith(ticker) or ticker.startswith(title_word):
        return False
    return (
        ticker[0] == title_word[0]
        and ticker[-1] == title_word[-1]
        and _edit_distance(ticker, title_word) <= 2
    )


def _asset_candidate(text: str) -> tuple[str, bool] | None:
    """Return a conservative ticker candidate and whether it had an exact `$`."""

    explicit = _EXPLICIT_ASSET_RE.match(text)
    if explicit:
        ticker = explicit.group("ticker")
        if _suspicious_title_ocr(text, ticker, explicit.end("ticker")):
            return None
        return _ASSET_ALIASES.get(ticker, ticker), True

    implicit = _IMPLICIT_ASSET_RE.match(text)
    if not implicit:
        return None
    ticker = implicit.group("ticker")
    if ticker in _IGNORED_ASSETS:
        return None

    # A missing dollar sign is commonly rendered as a leading ``S``.  Do not
    # guess the intended ticker: an implicit S-prefixed market title is usable
    # only when the following instrument name also starts with S.  Otherwise
    # abstain and let a separate explicit market/series row prove the symbol.
    # Exact ``$S...`` titles never enter this branch.
    if ticker.startswith("S") and _MARKET_TITLE_SUFFIX_RE.search(text):
        following_initial = re.search(r"[A-Za-z]", text[implicit.end("ticker") :])
        if following_initial and following_initial.group(0).upper() != "S":
            return None

    # A duplicated dollar-sign-as-S reading can corrupt both the symbol and
    # the following S&P-style index name while also damaging the INDX suffix.
    # Without the already-proven INDX shape below, abstain instead of broadly
    # stripping a leading S from genuine S-prefixed symbols.
    following_word = re.match(r"\s*([A-Za-z]+)\b", text[implicit.end("ticker") :])
    if (
        ticker.startswith("SS")
        and not _INDEX_TITLE_SUFFIX_RE.search(text)
        and following_word is not None
        and following_word.group(1).upper().startswith("SS")
        and re.search(r"\bIndex\b", text, re.IGNORECASE)
    ):
        return None

    # Apple Vision can read the small leading dollar sign as an extra ``S``.
    # Require that duplicated prefix on a StockCharts index title row; ordinary
    # S-prefixed tickers and body labels retain their literal spelling.
    if ticker.startswith("SS") and _INDEX_TITLE_SUFFIX_RE.search(text):
        ticker = ticker[1:]
        if not ticker:
            return None
    return _ASSET_ALIASES.get(ticker, ticker), False


def _explicit_composite_members(text: str) -> list[str]:
    """Return only a leading, fully dollar-marked colon pair."""

    match = _EXPLICIT_COMPOSITE_ASSET_RE.match(text)
    if match is None:
        return []
    members = {
        _ASSET_ALIASES.get(match.group(name), match.group(name))
        for name in ("left", "right")
        if match.group(name) not in _IGNORED_ASSETS
    }
    return sorted(members)


def _reliable_explicit_panel_candidate(text: str) -> str | None:
    glued_quote = _GLUED_DECIMAL_QUOTE_PANEL_RE.match(text)
    if glued_quote:
        return _ASSET_ALIASES.get(
            glued_quote.group("ticker"), glued_quote.group("ticker")
        )
    match = _PANEL_ASSET_RE.match(text)
    if not match:
        return None
    if not (
        _MARKET_HEADER_MARKER_RE.search(text)
        or _TIMEFRAME_RE.search(text)
        or _CODED_PANEL_PREFIX_RE.match(text)
        or _NUMERIC_PRIMARY_PANEL_PREFIX_RE.match(text)
        or _EXPLICIT_PRICE_LEGEND_RE.match(text)
    ):
        return None
    if _suspicious_title_ocr(text, match.group("ticker"), match.end("ticker")):
        return None
    ticker = match.group("ticker")
    if ticker in _IGNORED_ASSETS:
        return None
    return _ASSET_ALIASES.get(ticker, ticker)


def _panel_asset_candidate(text: str) -> str | None:
    explicit = _reliable_explicit_panel_candidate(text)
    match = _PRIMARY_SERIES_ASSET_RE.match(text) or _IMPLICIT_PANEL_ASSET_RE.match(
        text
    )
    if explicit:
        return explicit
    if match is None:
        return None
    ticker = match.group("ticker")
    if ticker in _IGNORED_ASSETS:
        return None
    return _ASSET_ALIASES.get(ticker, ticker)


def parse_header(observations: list[dict]) -> dict:
    """Extract only exact, high-confidence values from StockCharts headers."""

    top = [
        observation
        for observation in observations
        if float(observation.get("y", 0.0)) >= 0.80
        and float(observation.get("confidence", 0.0)) >= MIN_CONFIDENCE
    ]
    asset_header_rows = [
        observation
        for observation in top
        if float(observation.get("y", 0.0)) >= MIN_ASSET_HEADER_Y
        and float(observation.get("x", 0.0)) <= MAX_ASSET_X
    ]

    asset_rows: list[tuple[float, str, bool, dict]] = []
    primary_series_rows: list[tuple[float, str, bool, dict]] = []
    reliable_explicit_panel_rows: list[tuple[float, str, bool, dict]] = []
    panel_candidates: dict[str, list[dict]] = {}
    timeframe_candidates: dict[str, list[dict]] = {}
    for observation in observations:
        if (
            float(observation.get("confidence", 0.0)) < MIN_CONFIDENCE
            or float(observation.get("x", 0.0)) > MAX_PANEL_HEADER_X
        ):
            continue
        text = str(observation.get("text", "")).strip()
        composite_members = _explicit_composite_members(text)
        if composite_members and (
            _MARKET_HEADER_MARKER_RE.search(text) or _TIMEFRAME_RE.search(text)
        ):
            evidence = _evidence_observation(observation)
            for member in composite_members:
                panel_candidates.setdefault(member, []).append(evidence)
        explicit_panel_value = _reliable_explicit_panel_candidate(text)
        value = _panel_asset_candidate(text)
        if value:
            evidence = _evidence_observation(observation)
            panel_candidates.setdefault(value, []).append(evidence)
            if explicit_panel_value and (
                _MARKET_HEADER_MARKER_RE.search(text)
                or _NUMERIC_PRIMARY_PANEL_PREFIX_RE.match(text)
            ):
                reliable_explicit_panel_rows.append(
                    (
                        float(observation.get("y", 0.0)),
                        explicit_panel_value,
                        True,
                        evidence,
                    )
                )

    for observation in top:
        text = str(observation.get("text", "")).strip()
        if observation in asset_header_rows:
            primary_series = _PRIMARY_SERIES_ASSET_RE.match(text)
            if primary_series:
                ticker = primary_series.group("ticker").upper()
                if ticker not in _IGNORED_ASSETS:
                    primary_series_rows.append(
                        (
                            float(observation.get("y", 0.0)),
                            _ASSET_ALIASES.get(ticker, ticker),
                            False,
                            _evidence_observation(observation),
                        )
                    )
            candidate = _asset_candidate(text)
            if candidate:
                value, explicit = candidate
                bare_implicit = (
                    None if explicit else _IMPLICIT_ASSET_RE.fullmatch(text)
                )
                if bare_implicit and (
                    len(bare_implicit.group("ticker")) > 1
                    or float(observation.get("x", 0.0)) > MAX_PANEL_HEADER_X
                ):
                    continue
                asset_rows.append(
                    (
                        float(observation.get("y", 0.0)),
                        value,
                        explicit,
                        _evidence_observation(observation),
                    )
                )
        for match in _TIMEFRAME_RE.finditer(text):
            value = match.group(1).lower()
            timeframe_candidates.setdefault(value, []).append(
                _evidence_observation(observation)
            )

    highest_all = max((row[0] for row in asset_rows), default=-1.0)
    explicit_header_rows = [
        row
        for row in asset_rows
        if row[2] and highest_all - row[0] <= MAX_EXPLICIT_HEADER_OFFSET
    ]
    panel_members_ambiguous = False
    structured_scalar_selected = False
    if explicit_header_rows:
        asset_rows = explicit_header_rows
        structured_scalar_selected = True
    else:
        market_title_rows = [
            row
            for row in asset_rows
            if _MARKET_TITLE_SUFFIX_RE.search(str(row[3]["text"]))
        ]
        market_values = {row[1] for row in market_title_rows}
        series_values = {row[1] for row in primary_series_rows}
        series_reinforces_title = (
            len(market_values) == 1
            and len(series_values) == 1
            and next(iter(series_values)).startswith(next(iter(market_values)))
        )
        truncated_title_reinforced = (
            series_reinforces_title
            and next(iter(series_values)) != next(iter(market_values))
        )
        if primary_series_rows and (not market_title_rows or truncated_title_reinforced):
            asset_rows = primary_series_rows
            structured_scalar_selected = True
        elif market_title_rows:
            asset_rows = market_title_rows
            structured_scalar_selected = True
            panel_members_ambiguous = bool(primary_series_rows and not series_reinforces_title)
    reliable_panel_values = {row[1] for row in reliable_explicit_panel_rows}
    if not structured_scalar_selected and len(reliable_panel_values) == 1:
        asset_rows = reliable_explicit_panel_rows
    highest = max((row[0] for row in asset_rows), default=-1.0)
    asset_candidates: dict[str, list[dict]] = {}
    for y, value, _explicit, evidence in asset_rows:
        if highest - y <= 0.006:
            asset_candidates.setdefault(value, []).append(evidence)

    asset = _parsed_field(asset_candidates)
    if panel_members_ambiguous:
        panel_candidates = {}
    elif asset["unique"]:
        panel_candidates.setdefault(asset["value"], []).extend(asset["evidence"])
    asset["members"] = sorted(panel_candidates)
    asset["member_evidence"] = [
        evidence
        for value in sorted(panel_candidates)
        for evidence in panel_candidates[value]
    ]

    return {
        "asset": asset,
        "timeframe": _parsed_field(timeframe_candidates),
    }


def merge_runs(parsed_runs: list[dict]) -> dict:
    if len(parsed_runs) != RUNS_PER_IMAGE:
        raise ValueError(f"expected {RUNS_PER_IMAGE} OCR runs, got {len(parsed_runs)}")
    merged: dict[str, dict] = {}
    for field in ("asset", "timeframe"):
        values = [str(parsed[field]["value"]) for parsed in parsed_runs]
        eligible = all(bool(parsed[field]["unique"]) for parsed in parsed_runs)
        eligible = eligible and values[0] != UNKNOWN and len(set(values)) == 1
        merged[field] = {
            "value": values[0] if eligible else UNKNOWN,
            "decision_eligible": eligible,
            "runs": values,
            "evidence": [parsed[field]["evidence"] for parsed in parsed_runs],
        }
        if field == "asset":
            member_runs = [parsed[field]["members"] for parsed in parsed_runs]
            stable_members = bool(member_runs[0]) and member_runs[0] == member_runs[1]
            merged[field].update(
                {
                    "members": member_runs[0] if stable_members else [],
                    "members_decision_eligible": stable_members,
                    "member_runs": member_runs,
                    "member_evidence": [
                        parsed[field]["member_evidence"] for parsed in parsed_runs
                    ],
                }
            )
    return merged


def discover_fraser_images(kb_root: Path, repo_root: Path) -> list[Path]:
    image_root = (repo_root / "raw" / "bruce_fraser" / "images").resolve()
    paths: set[Path] = set()
    for extract_path in sorted((kb_root / "wiki" / "extracts").glob("*.md")):
        text = extract_path.read_text(encoding="utf-8")
        frontmatter = core.parse_frontmatter(text)
        source = str(frontmatter.get("source", "")).strip()
        image_path = str(frontmatter.get("image_path", "")).strip()
        if not source.startswith("raw/bruce_fraser/posts/") or not image_path:
            continue
        if image_path.lower().startswith("(remote:"):
            continue
        candidate = (repo_root / image_path).resolve()
        if candidate.is_relative_to(image_root) and candidate.is_file():
            paths.add(candidate)
    return sorted(paths)


def image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact(
    image_paths: list[Path],
    repo_root: Path,
    observe: ObservationRunner,
    *,
    toolchain: dict,
) -> dict:
    records: list[dict] = []
    for image_path in image_paths:
        parsed_runs = [parse_header(observe(image_path)) for _ in range(RUNS_PER_IMAGE)]
        merged = merge_runs(parsed_runs)
        records.append(
            {
                "image_path": image_path.relative_to(repo_root).as_posix(),
                "sha256": image_sha256(image_path),
                **merged,
            }
        )
    return {
        "schema": SCHEMA_VERSION,
        "generator": {
            "parser_version": PARSER_VERSION,
            "minimum_confidence": MIN_CONFIDENCE,
            "runs_per_image": RUNS_PER_IMAGE,
            "engine": ENGINE,
            "recognition_language": "en-US",
            "uses_language_correction": False,
            "toolchain": toolchain,
        },
        "images": records,
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def compile_helper(swiftc: str, destination: Path) -> None:
    source = Path(__file__).with_name("fraser_header_vision.swift")
    subprocess.run(
        [swiftc, str(source), "-o", str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )


def run_vision(binary: Path, image_path: Path) -> list[dict]:
    result = subprocess.run(
        [str(binary), str(image_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise ValueError("Vision helper output must be a JSON list")
    return payload


def _swift_version(swiftc: str) -> str:
    result = subprocess.run(
        [swiftc, "--version"], check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()[0].strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kb-root", type=Path, default=Path("research/expert-analyses")
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.resolve()
    if platform.system() != "Darwin":
        print("OCR_UNAVAILABLE: Apple Vision generator requires macOS", file=sys.stderr)
        return 2
    swiftc = shutil.which("swiftc")
    if swiftc is None:
        print("OCR_UNAVAILABLE: swiftc was not found", file=sys.stderr)
        return 2

    repo_root = Path.cwd().resolve()
    kb_root = args.kb_root.resolve()
    try:
        images = discover_fraser_images(kb_root, repo_root)
        with tempfile.TemporaryDirectory(prefix="fraser-header-ocr-") as temp_name:
            binary = Path(temp_name) / "fraser_header_vision"
            compile_helper(swiftc, binary)
            payload = build_artifact(
                images,
                repo_root,
                lambda image: run_vision(binary, image),
                toolchain={
                    "system": platform.system(),
                    "macos": platform.mac_ver()[0],
                    "machine": platform.machine(),
                    "swift": _swift_version(swiftc),
                },
            )
        atomic_write_json(output, payload)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"OCR generation failed: {exc}", file=sys.stderr)
        return 1

    observed = sum(
        any(record[field]["decision_eligible"] for field in ("asset", "timeframe"))
        for record in payload["images"]
    )
    unknown = len(payload["images"]) - observed
    unstable = sum(
        any(len(set(record[field]["runs"])) > 1 for field in ("asset", "timeframe"))
        for record in payload["images"]
    )
    print(
        json.dumps(
            {
                "images": len(payload["images"]),
                "observed": observed,
                "unknown": unknown,
                "unstable": unstable,
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
