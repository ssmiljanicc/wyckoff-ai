"""Tests for signal_logger_server: list filter, deterministic replay, JSONL roll-over."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.mcp.signal_logger_server import SignalNotFoundError, SignalStore


def _base_kwargs(**overrides) -> dict:
    base = {
        "symbol": "BTC/USDT",
        "timeframe": "1d",
        "signal_type": "long_spring_retest",
        "entry_zone": [42000.0, 42500.0],
        "invalidation": 40500.0,
        "target_zone": [48000.0, 52000.0],
        "tactical_quality": "Phase C aggressive",
        "evidence": ["climactic low at $30k", "AR to $38k", "spring printed"],
        "phase_identified": "C",
        "wiki_pages_cited": ["events/spring.md", "structures/accumulation.md"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test 1: list filter works
# ---------------------------------------------------------------------------


def test_list_filter_by_symbol(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    store.log_signal(**_base_kwargs(symbol="BTC/USDT"))
    store.log_signal(**_base_kwargs(symbol="ETH/USDT"))

    results = store.list_signals(symbol="BTC/USDT")
    assert len(results) == 1
    assert results[0]["symbol"] == "BTC/USDT"

    # Non-matching symbol excluded
    assert store.list_signals(symbol="SOL/USDT") == []


def test_list_filter_by_signal_type(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    store.log_signal(**_base_kwargs(signal_type="long_spring_retest"))
    store.log_signal(**_base_kwargs(signal_type="short_utad"))

    results = store.list_signals(signal_type="long_spring_retest")
    assert len(results) == 1
    assert results[0]["signal_type"] == "long_spring_retest"

    # Non-matching type excluded
    assert store.list_signals(signal_type="long_sos") == []


def test_list_filter_by_date_range(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    store.log_signal(**_base_kwargs(timestamp="2026-05-01T00:00:00Z"))
    store.log_signal(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))

    results = store.list_signals(
        start="2026-05-01T00:00:00Z",
        end="2026-05-31T23:59:59Z",
    )
    assert len(results) == 1
    assert results[0]["logged_at"].startswith("2026-05")


def test_list_returns_chronological_order(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    store.log_signal(**_base_kwargs(timestamp="2026-05-10T12:00:00Z"))
    store.log_signal(**_base_kwargs(timestamp="2026-05-03T08:00:00Z"))
    store.log_signal(**_base_kwargs(timestamp="2026-05-20T00:00:00Z"))

    results = store.list_signals()
    logged_ats = [r["logged_at"] for r in results]
    assert logged_ats == sorted(logged_ats)


# ---------------------------------------------------------------------------
# Test 2: deterministic replay
# ---------------------------------------------------------------------------


def _log_long(store: SignalStore) -> str:
    record = store.log_signal(**_base_kwargs(
        signal_type="long_spring_retest",
        entry_zone=[42000.0, 42500.0],
        invalidation=40500.0,
        target_zone=[48000.0, 52000.0],
    ))
    return record["signal_id"]


def test_replay_hit_tp_ohlcv(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    ohlcv = [
        {"open_time": 1, "high": 43000.0, "low": 41000.0},  # in range
        {"open_time": 2, "high": 49000.0, "low": 44000.0},  # high >= 48000 → TP
    ]
    result = store.replay_signal(sid, ohlcv)
    assert result["outcome"] == "hit_tp"
    assert result["side"] == "long"
    assert result["resolved_at"] == 2


def test_replay_hit_sl_ohlcv(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    ohlcv = [
        {"open_time": 1, "high": 43000.0, "low": 41000.0},  # in range
        {"open_time": 2, "high": 42000.0, "low": 40000.0},  # low <= 40500 → SL
    ]
    result = store.replay_signal(sid, ohlcv)
    assert result["outcome"] == "hit_sl"


def test_replay_open_ohlcv(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    ohlcv = [
        {"open_time": 1, "high": 43000.0, "low": 41000.0},
        {"open_time": 2, "high": 44000.0, "low": 42000.0},
    ]
    result = store.replay_signal(sid, ohlcv)
    assert result["outcome"] == "open"
    assert result["resolved_at"] is None


def test_replay_same_bar_both_touched_resolves_sl(tmp_path: Path) -> None:
    """When a single bar spans both SL and TP the conservative tie-break is hit_sl."""
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    # low=39000 <= invalidation=40500 (SL hit) AND high=50000 >= min(target)=48000 (TP hit)
    ohlcv = [{"open_time": 1, "high": 50000.0, "low": 39000.0}]
    result = store.replay_signal(sid, ohlcv)
    assert result["outcome"] == "hit_sl"


def test_replay_deterministic(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    ohlcv = [{"open_time": 1, "high": 49000.0, "low": 44000.0}]
    assert store.replay_signal(sid, ohlcv) == store.replay_signal(sid, ohlcv)


def test_replay_short_signal_hit_tp(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    record = store.log_signal(**_base_kwargs(
        signal_type="short_utad",
        entry_zone=[50000.0, 49000.0],
        invalidation=52000.0,
        target_zone=[42000.0, 40000.0],
    ))
    sid = record["signal_id"]
    # low=41000 <= max(target_zone)=42000 → TP; high=49000 < 52000 → no SL
    ohlcv = [{"open_time": 1, "high": 49000.0, "low": 41000.0}]
    result = store.replay_signal(sid, ohlcv)
    assert result["outcome"] == "hit_tp"
    assert result["side"] == "short"


def test_replay_empty_ohlcv_returns_open(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    result = store.replay_signal(sid, [])
    assert result["outcome"] == "open"


def test_replay_scalar_hit_tp(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    result = store.replay_signal(sid, 49000.0)
    assert result["outcome"] == "hit_tp"


def test_replay_scalar_hit_sl(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    result = store.replay_signal(sid, 40000.0)
    assert result["outcome"] == "hit_sl"


def test_replay_scalar_open(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    sid = _log_long(store)
    result = store.replay_signal(sid, 43000.0)
    assert result["outcome"] == "open"


# ---------------------------------------------------------------------------
# Test 3: JSONL roll-over across months
# ---------------------------------------------------------------------------


def test_two_months_produce_two_files(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    store.log_signal(**_base_kwargs(timestamp="2026-04-15T10:00:00Z"))
    store.log_signal(**_base_kwargs(timestamp="2026-05-15T10:00:00Z"))

    files = sorted(tmp_path.glob("*.jsonl"))
    assert len(files) == 2
    assert files[0].name == "2026-04.jsonl"
    assert files[1].name == "2026-05.jsonl"

    # Each file has exactly one line
    for f in files:
        non_empty = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(non_empty) == 1

    # list_signals returns both
    assert len(store.list_signals()) == 2


# ---------------------------------------------------------------------------
# Edge cases and validation
# ---------------------------------------------------------------------------


def test_invalid_signal_type_prefix_raises(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    with pytest.raises(ValueError, match="long_"):
        store.log_signal(**_base_kwargs(signal_type="buy_spring"))


def test_empty_symbol_raises(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    with pytest.raises(ValueError, match="symbol"):
        store.log_signal(**_base_kwargs(symbol=""))


def test_entry_zone_wrong_length_raises(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    with pytest.raises(ValueError, match="entry_zone"):
        store.log_signal(**_base_kwargs(entry_zone=[42000.0]))


def test_get_signal_miss_returns_none(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    assert store.get_signal("nonexistent-id") is None


def test_get_signal_on_missing_dir_returns_none(tmp_path: Path) -> None:
    store = SignalStore(tmp_path / "nonexistent")
    assert store.get_signal("any-id") is None


def test_list_signals_on_missing_dir_returns_empty(tmp_path: Path) -> None:
    store = SignalStore(tmp_path / "nonexistent")
    assert store.list_signals() == []


def test_replay_not_found_raises_signal_not_found(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    with pytest.raises(SignalNotFoundError):
        store.replay_signal("nonexistent-uuid", [])


def test_log_signal_returns_record_with_signal_id(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    record = store.log_signal(**_base_kwargs())
    assert "signal_id" in record
    assert len(record["signal_id"]) == 36  # uuid4 format
    assert record["logged_at"].endswith("Z")
    assert record["symbol"] == "BTC/USDT"


def test_get_signal_roundtrip(tmp_path: Path) -> None:
    store = SignalStore(tmp_path)
    logged = store.log_signal(**_base_kwargs())
    fetched = store.get_signal(logged["signal_id"])
    assert fetched == logged
