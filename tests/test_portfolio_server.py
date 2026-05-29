from __future__ import annotations

import json
import os

import pytest

from scripts.mcp import portfolio_server
from scripts.mcp.portfolio_store import (
    InvalidPositionState,
    PortfolioNotFound,
    PortfolioStore,
    PositionNotFound,
    compute_pnl,
)


# ---------------------------------------------------------------------------
# Issue success signal #1 — restart persistence
# ---------------------------------------------------------------------------


def test_open_position_persists_across_restart(tmp_path) -> None:
    store1 = PortfolioStore(base_dir=tmp_path)
    store1.open_position("main", "BTC/USDT", "long", 0.1, entry_price=42000, sl=40000, tp=50000)

    # Simulate restart: brand-new PortfolioStore over the same directory.
    store2 = PortfolioStore(base_dir=tmp_path)
    positions = store2.list_positions("main", "open")

    assert len(positions) == 1
    pos = positions[0]
    assert pos["symbol"] == "BTC/USDT"
    assert pos["side"] == "long"
    assert pos["size"] == 0.1
    assert pos["entry_price"] == 42000
    assert pos["sl"] == 40000
    assert pos["tp"] == 50000
    assert pos["status"] == "open"
    assert (tmp_path / "main.json").exists()


# ---------------------------------------------------------------------------
# Issue success signal #2 — 5-position P&L vs manual
# ---------------------------------------------------------------------------


def test_pnl_matches_manual_five_positions(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    starting_cash = 100_000.0

    # Define trades: (symbol, side, size, entry, exit, expected_pnl)
    trades = [
        ("BTC/USDT", "long", 0.1, 42000.0, 48000.0, 600.0),    # win long
        ("ETH/USDT", "long", 1.0, 2000.0, 1800.0, -200.0),     # loss long
        ("BTC/USDT", "short", 0.2, 50000.0, 45000.0, 1000.0),  # win short
        ("SOL/USDT", "long", 10.0, 100.0, 120.0, 200.0),       # win long
        ("ETH/USDT", "short", 2.0, 2500.0, 2600.0, -200.0),    # loss short
    ]

    opened_ids: list[str] = []
    for symbol, side, size, entry, _exit, _pnl in trades:
        pos = store.open_position("perf", symbol, side, size, entry_price=entry)
        opened_ids.append(pos["id"])

    for (symbol, side, size, entry, exit_price, expected_pnl), pos_id in zip(trades, opened_ids):
        closed = store.close_position("perf", pos_id, exit_price=exit_price)
        assert closed["realized_pnl"] == pytest.approx(expected_pnl), (
            f"{symbol} {side}: expected {expected_pnl}, got {closed['realized_pnl']}"
        )

    manual_total = sum(pnl for *_, pnl in trades)  # 600 - 200 + 1000 + 200 - 200 = 1400
    state = store.get_portfolio_state("perf")
    assert state["cash"] == pytest.approx(starting_cash + manual_total)
    assert state["realized_pnl"] == pytest.approx(manual_total)


# ---------------------------------------------------------------------------
# Issue success signal #3 — interrupted write does not corrupt
# ---------------------------------------------------------------------------


def test_interrupted_write_does_not_corrupt(tmp_path, monkeypatch) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    store.open_position("safe", "BTC/USDT", "long", 0.5, entry_price=30000)

    # Record valid on-disk state before the failed write.
    valid_json = (tmp_path / "safe.json").read_text()
    valid_state = json.loads(valid_json)

    # Patch json.dump to blow up on the next call (simulates mid-write failure).
    original_dump = json.dump
    call_count = {"n": 0}

    def bomb_dump(obj, fp, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("simulated disk error")
        return original_dump(obj, fp, **kwargs)

    monkeypatch.setattr("scripts.mcp.portfolio_store.json.dump", bomb_dump)

    with pytest.raises(OSError, match="simulated disk error"):
        store.open_position("safe", "ETH/USDT", "long", 1.0, entry_price=2000)

    # The original file must still be parseable and unchanged.
    recovered = json.loads((tmp_path / "safe.json").read_text())
    assert recovered == valid_state

    # No stray .tmp files left behind.
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Stray temp files: {tmp_files}"

    # A fresh store still sees the original valid state.
    store2 = PortfolioStore(base_dir=tmp_path)
    positions = store2.list_positions("safe", "open")
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT"


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


def test_close_unknown_position_raises(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    store.open_position("p", "BTC/USDT", "long", 1.0, entry_price=40000)
    with pytest.raises(PositionNotFound):
        store.close_position("p", "999", exit_price=41000)


def test_close_already_closed_raises(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    pos = store.open_position("p", "BTC/USDT", "long", 1.0, entry_price=40000)
    store.close_position("p", pos["id"], exit_price=41000)
    with pytest.raises(InvalidPositionState):
        store.close_position("p", pos["id"], exit_price=42000)


def test_reset_portfolio_clears_positions_and_sets_cash(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    store.open_position("r", "BTC/USDT", "long", 1.0, entry_price=40000)
    fresh = store.reset_portfolio("r", starting_cash=50_000.0)
    assert fresh["cash"] == 50_000.0
    assert fresh["positions"] == []
    assert fresh["next_id"] == 1
    assert fresh["starting_cash"] == 50_000.0


def test_list_positions_status_filter(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    pos1 = store.open_position("f", "BTC/USDT", "long", 1.0, entry_price=40000)
    pos2 = store.open_position("f", "ETH/USDT", "short", 2.0, entry_price=2000)
    store.close_position("f", pos1["id"], exit_price=41000)

    all_pos = store.list_positions("f", "all")
    open_pos = store.list_positions("f", "open")
    closed_pos = store.list_positions("f", "closed")

    assert len(all_pos) == 2
    assert len(open_pos) == 1
    assert open_pos[0]["id"] == pos2["id"]
    assert len(closed_pos) == 1
    assert closed_pos[0]["id"] == pos1["id"]


def test_open_position_validates_side_and_size(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    with pytest.raises(ValueError, match="side"):
        store.open_position("v", "BTC/USDT", "buy", 1.0, entry_price=40000)
    with pytest.raises(ValueError, match="size"):
        store.open_position("v", "BTC/USDT", "long", -1.0, entry_price=40000)
    with pytest.raises(ValueError, match="size"):
        store.open_position("v", "BTC/USDT", "long", 0.0, entry_price=40000)


def test_compute_pnl_long_and_short() -> None:
    cases = [
        ("long", 100.0, 110.0, 2.0, 20.0),
        ("long", 100.0, 90.0, 2.0, -20.0),
        ("short", 100.0, 90.0, 2.0, 20.0),
        ("short", 100.0, 110.0, 2.0, -20.0),
        ("long", 42000.0, 48000.0, 0.1, 600.0),
    ]
    for side, entry, exit_p, size, expected in cases:
        result = compute_pnl(side, entry, exit_p, size)
        assert result == pytest.approx(expected), f"compute_pnl({side}, {entry}, {exit_p}, {size})"


# ---------------------------------------------------------------------------
# Server wrapper smoke test (monkeypatch)
# ---------------------------------------------------------------------------


def test_server_open_position_delegates_to_store(monkeypatch, tmp_path) -> None:
    fake_store = PortfolioStore(base_dir=tmp_path)
    monkeypatch.setattr(portfolio_server, "store", fake_store)

    result = portfolio_server.open_position("main", "BTC/USDT", "long", 0.1, entry_price=42000)
    assert result["symbol"] == "BTC/USDT"
    assert result["status"] == "open"

    positions = portfolio_server.list_positions("main", "open")
    assert len(positions) == 1


def test_portfolio_not_found_on_missing_portfolio(tmp_path) -> None:
    store = PortfolioStore(base_dir=tmp_path)
    with pytest.raises(PortfolioNotFound):
        store.list_positions("nonexistent")
