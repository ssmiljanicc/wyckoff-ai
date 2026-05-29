"""MCP server exposing virtual portfolio tracking tools."""

from __future__ import annotations

from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only without the mcp extra.
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None:
            self.name = name

        def tool(self) -> Any:
            def decorator(func: Any) -> Any:
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError("FastMCP requires the mcp extra: uv run --extra mcp ...")

from scripts.mcp.portfolio_store import (
    DEFAULT_STARTING_CASH,
    Position,
    PortfolioState,
    PortfolioStore,
)


mcp = FastMCP("wyckoff-portfolio")
store = PortfolioStore()


@mcp.tool()
def open_position(
    portfolio: str,
    symbol: str,
    side: str,
    size: float,
    entry_price: float,
    sl: float | None = None,
    tp: float | None = None,
    note: str = "",
) -> Position:
    """Open a new virtual position in the named portfolio.

    Args:
        portfolio: Portfolio name (e.g. 'main').  Created automatically if absent.
        symbol:    Trading pair (e.g. 'BTC/USDT').
        side:      'long' or 'short'.
        size:      Position size in base asset units (must be > 0).
        entry_price: Fill price (must be > 0).  Required — P&L is undefined without it.
        sl:        Optional stop-loss price.
        tp:        Optional take-profit price.
        note:      Optional free-text annotation.

    Returns:
        The newly created Position dict with its assigned id.
    """
    return store.open_position(portfolio, symbol, side, size, entry_price, sl, tp, note)


@mcp.tool()
def close_position(
    portfolio: str,
    position_id: str,
    exit_price: float,
    reason: str = "",
) -> Position:
    """Close an open position and book realized P&L.

    Args:
        portfolio:   Portfolio name.
        position_id: Position id string (as returned by open_position).
        exit_price:  Exit fill price.
        reason:      Optional reason string (e.g. 'target hit', 'stopped out').

    Returns:
        The closed Position dict with realized_pnl filled in.
    """
    return store.close_position(portfolio, position_id, exit_price, reason)


@mcp.tool()
def list_positions(
    portfolio: str,
    status: str = "all",
) -> list[Position]:
    """List positions in a portfolio, optionally filtered by status.

    Args:
        portfolio: Portfolio name.
        status:    'open', 'closed', or 'all' (default).

    Returns:
        List of Position dicts matching the requested status.
    """
    return store.list_positions(portfolio, status)


@mcp.tool()
def get_portfolio_state(portfolio: str) -> dict:
    """Return a summary of the portfolio: cash, realized/unrealized P&L, equity, open positions.

    Args:
        portfolio: Portfolio name.

    Returns:
        Dict with name, starting_cash, cash, realized_pnl, unrealized_pnl, total_equity,
        open_positions list, and closed_count.
    """
    return store.get_portfolio_state(portfolio)


@mcp.tool()
def reset_portfolio(
    portfolio: str,
    starting_cash: float = DEFAULT_STARTING_CASH,
) -> PortfolioState:
    """Reset a portfolio to a fresh empty state with the given starting cash.

    Args:
        portfolio:     Portfolio name.
        starting_cash: Initial cash balance (default 100 000.0).

    Returns:
        The freshly seeded PortfolioState dict.
    """
    return store.reset_portfolio(portfolio, starting_cash)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
