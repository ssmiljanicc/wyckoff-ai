"""MCP server for append-only Wyckoff analysis journaling."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from mcp.server.fastmcp import FastMCP


DEFAULT_JOURNAL_DIR = Path("data/journal")
FORECAST_KEYS = {"direction", "trigger", "invalidation", "confidence"}


class Forecast(TypedDict):
    direction: str
    trigger: str
    invalidation: str
    confidence: float


class Review(TypedDict):
    reviewed_at: str
    realized_direction: str
    hit_trigger: bool
    note: str


class AnalysisRecord(TypedDict):
    analysis_id: str
    logged_at: str
    symbol: str
    timeframe: str
    model: str
    effort: str
    narrative: str
    structure: str
    phase: str
    forecast: Forecast
    chart_path: str | None
    review: Review | None


class ReviewRecord(TypedDict):
    type: Literal["review"]
    analysis_id: str
    review: Review


class AnalysisJournalError(RuntimeError):
    """Base exception for analysis journal failures."""


class JournalCorruptionError(AnalysisJournalError):
    """Raised when an existing JSONL journal file contains invalid data."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return _to_aware_utc(dt).isoformat().replace("+00:00", "Z")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _forecast_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"forecast.{field} must be a non-empty string")
    return value.strip()


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("forecast.confidence must be a number between 0 and 1")
    confidence = float(value)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("forecast.confidence must be a finite number between 0 and 1")
    return confidence


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


class AnalysisJournalStore:
    """Filesystem-backed append-only store for complete Wyckoff analyses."""

    def __init__(self, base_dir: Path | str = DEFAULT_JOURNAL_DIR) -> None:
        self.base_dir = Path(base_dir)

    def _month_file(self, when: datetime) -> Path:
        return self.base_dir / f"{when:%Y-%m}.jsonl"

    def log_analysis(
        self,
        *,
        symbol: str,
        timeframe: str,
        model: str,
        effort: str,
        narrative: str,
        structure: str,
        phase: str,
        forecast: dict[str, Any],
        chart_path: str | None = None,
        timestamp: datetime | str | None = None,
    ) -> AnalysisRecord:
        """Append an analysis record to the monthly JSONL file and return it."""
        if not isinstance(forecast, dict):
            raise ValueError("forecast must be an object")
        symbol = _required_text(symbol, "symbol")
        timeframe = _required_text(timeframe, "timeframe")
        model = _required_text(model, "model")
        effort = _required_text(effort, "effort")
        narrative = _required_text(narrative, "narrative")
        structure = _required_text(structure, "structure")
        phase = _required_text(phase, "phase")

        missing_forecast_keys = FORECAST_KEYS - set(forecast)
        if missing_forecast_keys:
            missing = ", ".join(sorted(missing_forecast_keys))
            raise ValueError(f"forecast missing required keys: {missing}")

        if timestamp is None:
            logged_at_dt = _now()
        elif isinstance(timestamp, str):
            logged_at_dt = _parse_iso(timestamp)
        else:
            logged_at_dt = timestamp
        logged_at_dt = _to_aware_utc(logged_at_dt)

        record: AnalysisRecord = {
            "analysis_id": str(uuid.uuid4()),
            "logged_at": _iso_z(logged_at_dt),
            "symbol": symbol,
            "timeframe": timeframe,
            "model": model,
            "effort": effort,
            "narrative": narrative,
            "structure": structure,
            "phase": phase,
            "forecast": {
                "direction": _forecast_text(forecast["direction"], "direction"),
                "trigger": _forecast_text(forecast["trigger"], "trigger"),
                "invalidation": _forecast_text(forecast["invalidation"], "invalidation"),
                "confidence": _confidence(forecast["confidence"]),
            },
            "chart_path": chart_path,
            "review": None,
        }

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self._month_file(logged_at_dt).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, allow_nan=False) + "\n")

        return record

    def list_analyses(
        self,
        *,
        symbol: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        model: str | None = None,
    ) -> list[AnalysisRecord]:
        """Return analyses matching the given filters, sorted by logged_at."""
        if not self.base_dir.exists():
            return []

        if isinstance(start, str):
            start = _parse_iso(start)
        if isinstance(end, str):
            end = _parse_iso(end)
        if start is not None:
            start = _to_aware_utc(start)
        if end is not None:
            end = _to_aware_utc(end)

        records, reviews = self._load_records_and_reviews(start=start, end=end)

        results: list[AnalysisRecord] = []
        for record in records:
            logged_at = _to_aware_utc(_parse_iso(record["logged_at"]))
            if symbol is not None and record["symbol"] != symbol:
                continue
            if model is not None and record["model"] != model:
                continue
            if start is not None and logged_at < start:
                continue
            if end is not None and logged_at > end:
                continue
            results.append(self._with_latest_review(record, reviews))

        results.sort(key=lambda r: r["logged_at"])
        return results

    def _month_files_in_range(self, start: datetime, end: datetime) -> list[Path]:
        year, month = start.year, start.month
        end_year, end_month = end.year, end.month
        files = []
        while (year, month) <= (end_year, end_month):
            files.append(self.base_dir / f"{year:04d}-{month:02d}.jsonl")
            month += 1
            if month > 12:
                month = 1
                year += 1
        return files

    def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        """Return an analysis with the given id, or None if not found."""
        if not self.base_dir.exists():
            return None

        records, reviews = self._load_records_and_reviews()
        for record in reversed(records):
            if record.get("analysis_id") == analysis_id:
                return self._with_latest_review(record, reviews)
        return None

    def review_analysis(
        self,
        *,
        analysis_id: str,
        realized_direction: str,
        hit_trigger: bool,
        note: str,
        reviewed_at: datetime | str | None = None,
    ) -> Review | None:
        """Append a review record for an existing analysis and return it."""
        if self.get_analysis(analysis_id) is None:
            return None
        realized_direction = _required_text(realized_direction, "realized_direction")
        note = _required_text(note, "note")
        if not isinstance(hit_trigger, bool):
            raise ValueError("hit_trigger must be a bool")

        if reviewed_at is None:
            reviewed_at_dt = _now()
        elif isinstance(reviewed_at, str):
            reviewed_at_dt = _parse_iso(reviewed_at)
        else:
            reviewed_at_dt = reviewed_at
        reviewed_at_dt = _to_aware_utc(reviewed_at_dt)

        review: Review = {
            "reviewed_at": _iso_z(reviewed_at_dt),
            "realized_direction": realized_direction,
            "hit_trigger": bool(hit_trigger),
            "note": note,
        }
        record: ReviewRecord = {
            "type": "review",
            "analysis_id": analysis_id,
            "review": review,
        }

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self._month_file(reviewed_at_dt).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, allow_nan=False) + "\n")

        return review

    def _load_records_and_reviews(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[list[AnalysisRecord], dict[str, Review]]:
        all_files = sorted(self.base_dir.glob("*.jsonl"))
        if start is not None and end is not None:
            candidate_files = self._month_files_in_range(start, end)
        else:
            candidate_files = all_files

        records = self._load_analysis_records(candidate_files)
        reviews = self._load_reviews(all_files)
        return records, reviews

    def _load_analysis_records(self, candidate_files: list[Path]) -> list[AnalysisRecord]:
        records: list[AnalysisRecord] = []
        for path in candidate_files:
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    entry = self._load_json_object(path, line_no, line)
                    if entry.get("type") == "review":
                        continue
                    if entry.get("type") is not None:
                        raise JournalCorruptionError(
                            f"{path}:{line_no}: unsupported record type {entry['type']!r}"
                        )
                    self._validate_analysis_entry(path, line_no, entry)
                    records.append(cast(AnalysisRecord, entry))
        return records

    def _load_reviews(self, candidate_files: list[Path]) -> dict[str, Review]:
        reviews: dict[str, Review] = {}
        for path in candidate_files:
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    entry = self._load_json_object(path, line_no, line)
                    if entry.get("type") != "review":
                        continue
                    review = entry.get("review")
                    analysis_id = entry.get("analysis_id")
                    if not isinstance(analysis_id, str) or not isinstance(review, dict):
                        raise JournalCorruptionError(
                            f"{path}:{line_no}: review record has invalid shape"
                        )
                    self._validate_review(path, line_no, review)
                    self._store_latest_review(reviews, analysis_id, cast(Review, review))
        return reviews

    def _load_json_object(self, path: Path, line_no: int, line: str) -> dict[str, Any]:
        try:
            entry = json.loads(line, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            raise JournalCorruptionError(f"{path}:{line_no}: invalid JSONL record") from exc
        if not isinstance(entry, dict):
            raise JournalCorruptionError(f"{path}:{line_no}: JSONL record must be an object")
        return entry

    def _validate_analysis_entry(
        self,
        path: Path,
        line_no: int,
        entry: dict[str, Any],
    ) -> None:
        required_fields = {
            "analysis_id",
            "logged_at",
            "symbol",
            "timeframe",
            "model",
            "effort",
            "narrative",
            "structure",
            "phase",
            "forecast",
            "review",
        }
        missing = sorted(required_fields - set(entry))
        if missing:
            raise JournalCorruptionError(
                f"{path}:{line_no}: analysis record missing fields: {', '.join(missing)}"
            )
        try:
            _parse_iso(entry["logged_at"])
        except (AttributeError, TypeError, ValueError) as exc:
            raise JournalCorruptionError(
                f"{path}:{line_no}: analysis record has invalid logged_at"
            ) from exc

    def _validate_review(self, path: Path, line_no: int, review: dict[str, Any]) -> None:
        required_fields = {"reviewed_at", "realized_direction", "hit_trigger", "note"}
        missing = sorted(required_fields - set(review))
        if missing:
            raise JournalCorruptionError(
                f"{path}:{line_no}: review missing fields: {', '.join(missing)}"
            )
        if not isinstance(review.get("hit_trigger"), bool):
            raise JournalCorruptionError(f"{path}:{line_no}: review hit_trigger must be bool")
        try:
            _parse_iso(review["reviewed_at"])
        except (AttributeError, TypeError, ValueError) as exc:
            raise JournalCorruptionError(f"{path}:{line_no}: review has invalid reviewed_at") from exc

    def _store_latest_review(
        self,
        reviews: dict[str, Review],
        analysis_id: str,
        review: Review,
    ) -> None:
        existing = reviews.get(analysis_id)
        if existing is None:
            reviews[analysis_id] = review
            return
        if _parse_iso(review["reviewed_at"]) >= _parse_iso(existing["reviewed_at"]):
            reviews[analysis_id] = review

    def _with_latest_review(
        self,
        record: AnalysisRecord,
        reviews: dict[str, Review],
    ) -> AnalysisRecord:
        merged = cast(AnalysisRecord, dict(record))
        merged["review"] = reviews.get(record["analysis_id"])
        return merged


mcp = FastMCP("wyckoff-analysis-journal")
store = AnalysisJournalStore()


@mcp.tool()
def log_analysis(
    symbol: str,
    timeframe: str,
    model: str,
    effort: str,
    narrative: str,
    structure: str,
    phase: str,
    forecast: dict[str, Any],
    chart_path: str | None = None,
    timestamp: str | None = None,
) -> AnalysisRecord:
    """Log a complete Wyckoff analysis to the append-only monthly JSONL store."""
    return store.log_analysis(
        symbol=symbol,
        timeframe=timeframe,
        model=model,
        effort=effort,
        narrative=narrative,
        structure=structure,
        phase=phase,
        forecast=forecast,
        chart_path=chart_path,
        timestamp=timestamp,
    )


@mcp.tool()
def list_analyses(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    model: str | None = None,
) -> list[AnalysisRecord]:
    """Query logged analyses filtered by symbol, date range, and/or model."""
    return store.list_analyses(symbol=symbol, start=start, end=end, model=model)


@mcp.tool()
def get_analysis(analysis_id: str) -> AnalysisRecord | None:
    """Return an analysis by its UUID, or None if not found."""
    return store.get_analysis(analysis_id)


@mcp.tool()
def review_analysis(
    analysis_id: str,
    realized_direction: str,
    hit_trigger: bool,
    note: str,
    reviewed_at: str | None = None,
) -> Review | None:
    """Append a review record for an existing analysis."""
    return store.review_analysis(
        analysis_id=analysis_id,
        realized_direction=realized_direction,
        hit_trigger=hit_trigger,
        note=note,
        reviewed_at=reviewed_at,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
