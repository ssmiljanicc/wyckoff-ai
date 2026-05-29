"""MCP server for logging and replaying Wyckoff trading signals."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

from mcp.server.fastmcp import FastMCP


DEFAULT_SIGNALS_DIR = Path("data/signals")


class Signal(TypedDict):
    signal_id: str
    logged_at: str
    symbol: str
    timeframe: str
    signal_type: str
    entry_zone: list[float]
    invalidation: float
    target_zone: list[float]
    tactical_quality: str
    evidence: list[str]
    phase_identified: str
    wiki_pages_cited: list[str]


class SignalLoggerError(RuntimeError):
    """Base exception for signal logger failures."""


class SignalNotFoundError(SignalLoggerError):
    """Raised when a signal_id cannot be found in the store."""


Outcome = Literal["hit_tp", "hit_sl", "open"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SignalStore:
    """Filesystem-backed store for Wyckoff trading signals.

    Signals are appended to monthly JSONL files under base_dir/<YYYY-MM>.jsonl.
    The store is append-only — signals are never edited or deleted.
    """

    def __init__(self, base_dir: Path | str = DEFAULT_SIGNALS_DIR) -> None:
        self.base_dir = Path(base_dir)

    def _month_file(self, when: datetime) -> Path:
        return self.base_dir / f"{when:%Y-%m}.jsonl"

    def log_signal(
        self,
        *,
        symbol: str,
        timeframe: str,
        signal_type: str,
        entry_zone: list[float],
        invalidation: float,
        target_zone: list[float],
        tactical_quality: str,
        evidence: list[str],
        phase_identified: str,
        wiki_pages_cited: list[str],
        timestamp: datetime | str | None = None,
    ) -> Signal:
        """Append a signal record to the monthly JSONL file and return it."""
        if not symbol:
            raise ValueError("symbol is required")
        if len(entry_zone) != 2:
            raise ValueError("entry_zone must be a 2-element list")
        if len(target_zone) != 2:
            raise ValueError("target_zone must be a 2-element list")
        if not (signal_type.startswith("long_") or signal_type.startswith("short_")):
            raise ValueError(
                f"signal_type must start with 'long_' or 'short_'; got {signal_type!r}"
            )

        if timestamp is None:
            logged_at_dt = _now()
        elif isinstance(timestamp, str):
            logged_at_dt = _parse_iso(timestamp)
        else:
            logged_at_dt = timestamp
        logged_at_dt = _to_aware_utc(logged_at_dt)
        logged_at_str = logged_at_dt.isoformat().replace("+00:00", "Z")

        record: Signal = {
            "signal_id": str(uuid.uuid4()),
            "logged_at": logged_at_str,
            "symbol": symbol,
            "timeframe": timeframe,
            "signal_type": signal_type,
            "entry_zone": list(entry_zone),
            "invalidation": float(invalidation),
            "target_zone": list(target_zone),
            "tactical_quality": tactical_quality,
            "evidence": list(evidence),
            "phase_identified": phase_identified,
            "wiki_pages_cited": list(wiki_pages_cited),
        }

        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self._month_file(logged_at_dt).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        return record

    def list_signals(
        self,
        *,
        symbol: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        signal_type: str | None = None,
    ) -> list[Signal]:
        """Return signals matching the given filters, sorted by logged_at."""
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

        if start is not None and end is not None:
            candidate_files = self._month_files_in_range(start, end)
        else:
            candidate_files = sorted(self.base_dir.glob("*.jsonl"))

        results: list[Signal] = []
        for path in candidate_files:
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record: Signal = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    logged_at = _to_aware_utc(_parse_iso(record["logged_at"]))
                    if symbol is not None and record["symbol"] != symbol:
                        continue
                    if signal_type is not None and record["signal_type"] != signal_type:
                        continue
                    if start is not None and logged_at < start:
                        continue
                    if end is not None and logged_at > end:
                        continue
                    results.append(record)

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

    def get_signal(self, signal_id: str) -> Signal | None:
        """Return the signal with the given id, or None if not found."""
        if not self.base_dir.exists():
            return None
        for path in sorted(self.base_dir.glob("*.jsonl"), reverse=True):
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record: Signal = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("signal_id") == signal_id:
                        return record
        return None

    def replay_signal(
        self,
        signal_id: str,
        current_price_or_ohlcv: float | int | list[dict],
    ) -> dict:
        """Deterministically compute hit_tp / hit_sl / open for a recorded signal.

        Tie-break rule: when a single bar's range spans both SL and TP,
        SL is resolved first (conservative — intrabar path is unknown).
        """
        record = self.get_signal(signal_id)
        if record is None:
            raise SignalNotFoundError(f"Signal not found: {signal_id!r}")

        signal_type = record["signal_type"]
        if signal_type.startswith("long"):
            side = "long"
        elif signal_type.startswith("short"):
            side = "short"
        else:
            raise ValueError(f"Cannot infer side from signal_type: {signal_type!r}")

        invalidation = record["invalidation"]
        target_zone = record["target_zone"]

        def _check_long(high: float, low: float) -> Outcome | None:
            # SL checked before TP — same-bar tie-break resolves to hit_sl (conservative).
            if low <= invalidation:
                return "hit_sl"
            if high >= min(target_zone):
                return "hit_tp"
            return None

        def _check_short(high: float, low: float) -> Outcome | None:
            # SL checked before TP — same-bar tie-break resolves to hit_sl (conservative).
            if high >= invalidation:
                return "hit_sl"
            if low <= max(target_zone):
                return "hit_tp"
            return None

        check = _check_long if side == "long" else _check_short

        if isinstance(current_price_or_ohlcv, (int, float)):
            price = float(current_price_or_ohlcv)
            outcome: Outcome = check(price, price) or "open"
            return {"signal_id": signal_id, "side": side, "outcome": outcome, "resolved_at": None}

        for bar in current_price_or_ohlcv:
            high = float(bar["high"])
            low = float(bar["low"])
            outcome = check(high, low)
            if outcome is not None:
                resolved_at = bar.get("open_time", None)
                return {
                    "signal_id": signal_id,
                    "side": side,
                    "outcome": outcome,
                    "resolved_at": resolved_at,
                }

        return {"signal_id": signal_id, "side": side, "outcome": "open", "resolved_at": None}


mcp = FastMCP("wyckoff-signal-logger")
# Module-level store; tests can swap it via monkeypatch.setattr(signal_logger_server, "store", ...)
store = SignalStore()


# MCP tool arg names follow the issue #21 interface (entry, sl, tp, phase) and are
# translated to schema field names (entry_zone, invalidation, target_zone, phase_identified)
# before reaching the store.
@mcp.tool()
def log_signal(
    symbol: str,
    timeframe: str,
    signal_type: str,
    entry: list[float],
    sl: float,
    tp: list[float],
    evidence: list[str],
    phase: str,
    tactical_quality: str,
    wiki_pages_cited: list[str] | None = None,
    timestamp: str | None = None,
) -> Signal:
    """Log a Wyckoff trading signal to the append-only monthly JSONL store."""
    return store.log_signal(
        symbol=symbol,
        timeframe=timeframe,
        signal_type=signal_type,
        entry_zone=entry,
        invalidation=sl,
        target_zone=tp,
        tactical_quality=tactical_quality,
        evidence=evidence,
        phase_identified=phase,
        wiki_pages_cited=wiki_pages_cited or [],
        timestamp=timestamp,
    )


@mcp.tool()
def list_signals(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    signal_type: str | None = None,
) -> list[Signal]:
    """Query logged signals filtered by symbol, date range, and/or signal_type."""
    return store.list_signals(symbol=symbol, start=start, end=end, signal_type=signal_type)


@mcp.tool()
def get_signal(signal_id: str) -> Signal | None:
    """Return a signal by its UUID, or None if not found."""
    return store.get_signal(signal_id)


@mcp.tool()
def replay_signal(signal_id: str, current_price_or_ohlcv: Any) -> dict:
    """Deterministically compute hit_tp / hit_sl / open for a recorded signal."""
    return store.replay_signal(signal_id, current_price_or_ohlcv)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
