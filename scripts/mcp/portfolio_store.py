"""Virtual portfolio persistence, locking, and P&L logic for Wyckoff MCP servers."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Literal, TypedDict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STARTING_CASH = 100_000.0
PORTFOLIO_DIR_ENV = "WYCKOFF_PORTFOLIO_DIR"
DEFAULT_PORTFOLIO_DIR = Path("data/portfolios")

Side = Literal["long", "short"]
PositionStatus = Literal["open", "closed"]


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class Position(TypedDict):
    id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    sl: float | None
    tp: float | None
    note: str
    status: str
    opened_at: str
    closed_at: str | None
    exit_price: float | None
    reason: str | None
    realized_pnl: float | None


class PortfolioState(TypedDict):
    name: str
    starting_cash: float
    cash: float
    next_id: int
    positions: list[Position]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PortfolioError(RuntimeError):
    """Base exception for portfolio failures."""


class PortfolioNotFound(PortfolioError):
    """Raised when the requested portfolio file does not exist."""


class PositionNotFound(PortfolioError):
    """Raised when a position id is not found in the portfolio."""


class InvalidPositionState(PortfolioError):
    """Raised for illegal state transitions (e.g. closing an already-closed position)."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def compute_pnl(side: str, entry_price: float, exit_price: float, size: float) -> float:
    """Return realized P&L for a closed position (no fees/slippage at MVP)."""
    if side == "long":
        return (exit_price - entry_price) * size
    if side == "short":
        return (entry_price - exit_price) * size
    raise ValueError(f"Unknown side {side!r}; expected 'long' or 'short'")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Atomic write + file lock
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write *data* to *path* atomically: temp-file in same dir → fsync → os.replace."""
    tmp_path_str: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False, mode="w", suffix=".tmp"
        ) as f:
            tmp_path_str = f.name
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path_str, path)
        tmp_path_str = None  # replaced successfully; nothing to clean up
    except Exception:
        if tmp_path_str is not None and os.path.exists(tmp_path_str):
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
        raise


@contextmanager
def _locked(path: Path) -> Generator[None, None, None]:
    """Acquire an exclusive POSIX file lock on <path>.lock for the duration of the block."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# PortfolioStore
# ---------------------------------------------------------------------------


class PortfolioStore:
    """Manages named virtual portfolios backed by atomic JSON files."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is not None:
            self.base_dir = base_dir
        else:
            env_val = os.environ.get(PORTFOLIO_DIR_ENV)
            self.base_dir = Path(env_val) if env_val else DEFAULT_PORTFOLIO_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name or ".." in name:
            raise ValueError(f"Invalid portfolio name: {name!r}")
        return self.base_dir / f"{name}.json"

    def _load(self, name: str) -> PortfolioState:
        path = self._path(name)
        if not path.exists():
            raise PortfolioNotFound(f"Portfolio {name!r} does not exist")
        with open(path) as f:
            return json.load(f)

    def _seed(self, name: str, starting_cash: float = DEFAULT_STARTING_CASH) -> PortfolioState:
        now = _now_iso()
        return {
            "name": name,
            "starting_cash": starting_cash,
            "cash": starting_cash,
            "next_id": 1,
            "positions": [],
            "created_at": now,
            "updated_at": now,
        }

    def open_position(
        self,
        portfolio: str,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        sl: float | None = None,
        tp: float | None = None,
        note: str = "",
    ) -> Position:
        if side not in ("long", "short"):
            raise ValueError(f"side must be 'long' or 'short', got {side!r}")
        if size <= 0:
            raise ValueError(f"size must be > 0, got {size}")
        if entry_price <= 0:
            raise ValueError(f"entry_price must be > 0, got {entry_price}")

        path = self._path(portfolio)
        with _locked(path):
            state: PortfolioState = (
                self._load(portfolio) if path.exists() else self._seed(portfolio)
            )
            position: Position = {
                "id": str(state["next_id"]),
                "symbol": symbol,
                "side": side,
                "size": size,
                "entry_price": entry_price,
                "sl": sl,
                "tp": tp,
                "note": note,
                "status": "open",
                "opened_at": _now_iso(),
                "closed_at": None,
                "exit_price": None,
                "reason": None,
                "realized_pnl": None,
            }
            state["next_id"] += 1
            state["positions"].append(position)
            state["updated_at"] = _now_iso()
            _atomic_write_json(path, state)
        return position

    def close_position(
        self,
        portfolio: str,
        position_id: str,
        exit_price: float,
        reason: str = "",
    ) -> Position:
        path = self._path(portfolio)
        with _locked(path):
            state = self._load(portfolio)
            target: Position | None = None
            for pos in state["positions"]:
                if pos["id"] == position_id:
                    target = pos
                    break
            if target is None:
                raise PositionNotFound(
                    f"Position {position_id!r} not found in portfolio {portfolio!r}"
                )
            if target["status"] != "open":
                raise InvalidPositionState(
                    f"Position {position_id!r} is already {target['status']!r}"
                )
            pnl = compute_pnl(target["side"], target["entry_price"], exit_price, target["size"])
            target["status"] = "closed"
            target["closed_at"] = _now_iso()
            target["exit_price"] = exit_price
            target["reason"] = reason
            target["realized_pnl"] = pnl
            state["cash"] = state["cash"] + pnl
            state["updated_at"] = _now_iso()
            _atomic_write_json(path, state)
        return target

    def list_positions(self, portfolio: str, status: str = "all") -> list[Position]:
        if status not in ("open", "closed", "all"):
            raise ValueError(f"status must be 'open', 'closed', or 'all', got {status!r}")
        state = self._load(portfolio)
        if status == "all":
            return list(state["positions"])
        return [p for p in state["positions"] if p["status"] == status]

    def get_portfolio_state(
        self,
        portfolio: str,
        marks: dict[str, float] | None = None,
    ) -> dict:
        state = self._load(portfolio)
        open_positions = [p for p in state["positions"] if p["status"] == "open"]
        closed_positions = [p for p in state["positions"] if p["status"] == "closed"]
        realized_pnl = sum(
            p["realized_pnl"] for p in closed_positions if p["realized_pnl"] is not None
        )
        unrealized_pnl = 0.0
        if marks:
            for pos in open_positions:
                mark = marks.get(pos["symbol"])
                if mark is not None:
                    unrealized_pnl += compute_pnl(
                        pos["side"], pos["entry_price"], mark, pos["size"]
                    )
        return {
            "name": state["name"],
            "starting_cash": state["starting_cash"],
            "cash": state["cash"],
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_equity": state["cash"] + unrealized_pnl,
            "open_positions": open_positions,
            "closed_count": len(closed_positions),
        }

    def reset_portfolio(
        self,
        portfolio: str,
        starting_cash: float = DEFAULT_STARTING_CASH,
    ) -> PortfolioState:
        path = self._path(portfolio)
        with _locked(path):
            fresh = self._seed(portfolio, starting_cash)
            _atomic_write_json(path, fresh)
        return fresh
