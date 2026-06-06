"""MCP server for scanning a universe of symbols against lightweight Wyckoff rules.

The scanner pulls OHLCV for many symbols concurrently (``asyncio.gather`` over
thread-offloaded synchronous fetches), evaluates each against a built-in rule,
and returns a ranked list with human-readable ``reason`` strings.

Built-in rules:
  - ``range_duration_gt_4w``        — closes held within ±5% of midpoint for ≥4 weeks
  - ``volume_declining``            — 10-bar volume MA has a negative slope
  - ``range_after_drop``            — ≥20% drawdown within the prior 8 weeks (accumulation candidate)
  - ``range_after_rally``           — ≥30% rally within the prior 8 weeks (distribution candidate)
  - ``relative_strength_top_decile``— symbol/BTC ratio performance in the top 10% of the universe

``relative_strength_top_decile`` is cross-sectional: a symbol's match depends on
the rest of the universe, so it is evaluated against the whole scanned set (or,
for a single ``evaluate_rule`` call, against ``top20_alts`` as the reference set).
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypedDict

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

from scripts.mcp.market_data_client import (
    MAX_LIMIT,
    BinanceMarketDataClient,
    normalize_symbol,
    normalize_timeframe,
)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

BARS_PER_WEEK: dict[str, int] = {"1h": 168, "4h": 42, "1d": 7, "1w": 1}

RANGE_BAND = 0.05            # ±5% of midpoint
RANGE_MIN_WEEKS = 4
VOLUME_MA_WINDOW = 10
DROP_PCT = 0.20             # ≥20% drawdown
RALLY_PCT = 0.30           # ≥30% rally
LOOKBACK_WEEKS = 8
RS_LOOKBACK_WEEKS = 4
RS_TOP_DECILE = 0.90       # 90th percentile
BTC_REFERENCE_SYMBOL = "BTC"
DEFAULT_MAX_RESULTS = 10
FETCH_BUFFER_BARS = 10
MAX_CONCURRENT_FETCHES = 8  # cap on simultaneous OHLCV pulls (rate-limit safety)

UNIVERSES: dict[str, list[str]] = {
    "top20_alts": [
        "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT", "LINK", "MATIC",
        "TRX", "LTC", "BCH", "ATOM", "UNI", "ETC", "XLM", "NEAR", "APT", "FIL",
    ],
    "defi_index": [
        "UNI", "AAVE", "MKR", "SNX", "COMP", "CRV", "SUSHI", "LDO", "CAKE",
        "DYDX", "1INCH", "BAL", "YFI",
    ],
    "low_caps": [
        "GALA", "ANKR", "CELR", "OGN", "RVN", "ZIL", "ONE", "HOT", "IOST",
        "KAVA", "BAND", "OCEAN", "STORJ", "SKL",
    ],
}


class ScannerError(RuntimeError):
    """Base exception for scanner failures."""


class UnknownRuleError(ScannerError):
    """Raised when a requested rule name is not built in."""


class UnknownUniverseError(ScannerError):
    """Raised when a requested universe name is not defined."""


class RuleResult(TypedDict):
    match: bool
    reason: str
    score: float


class ScanResult(TypedDict):
    symbol: str
    match: bool
    reason: str
    score: float


# ---------------------------------------------------------------------------
# Per-symbol rule evaluators
# ---------------------------------------------------------------------------

def _weeks_to_bars(weeks: int, timeframe: str) -> int:
    return weeks * BARS_PER_WEEK[timeframe]


def _insufficient(rule: str, have: int, need: int) -> RuleResult:
    return {
        "match": False,
        "reason": f"insufficient data for {rule}: have {have} bars, need {need}",
        "score": 0.0,
    }


def _evaluate_range_duration(candles: list[dict], timeframe: str) -> RuleResult:
    need = _weeks_to_bars(RANGE_MIN_WEEKS, timeframe)
    if len(candles) < need:
        return _insufficient("range_duration_gt_4w", len(candles), need)

    window = candles[-need:]
    closes = [float(c["close"]) for c in window]
    midpoint = (max(closes) + min(closes)) / 2
    if midpoint <= 0:
        return _insufficient("range_duration_gt_4w", len(candles), need)

    max_dev = max(abs(c - midpoint) for c in closes) / midpoint
    match = max_dev <= RANGE_BAND
    if match:
        reason = (
            f"{RANGE_MIN_WEEKS}+ weeks of closes within ±{RANGE_BAND * 100:.0f}% "
            f"of midpoint {midpoint:.4g} (max dev {max_dev * 100:.1f}%)"
        )
        # Tighter range ranks higher.
        score = RANGE_BAND - max_dev
    else:
        reason = (
            f"closes break ±{RANGE_BAND * 100:.0f}% band over last {RANGE_MIN_WEEKS} "
            f"weeks (max dev {max_dev * 100:.1f}%)"
        )
        score = 0.0
    return {"match": match, "reason": reason, "score": score}


def _evaluate_volume_declining(candles: list[dict], timeframe: str) -> RuleResult:
    # Need the MA window plus a few points to estimate a slope.
    need = VOLUME_MA_WINDOW + 5
    if len(candles) < need:
        return _insufficient("volume_declining", len(candles), need)

    volumes = [float(c["volume"]) for c in candles]
    ma_series = _rolling_mean(volumes, VOLUME_MA_WINDOW)
    slope = _least_squares_slope(ma_series)
    mean_volume = sum(volumes) / len(volumes)
    # Normalize slope by mean volume so it is comparable across symbols.
    normalized = slope / mean_volume if mean_volume > 0 else 0.0

    match = slope < 0
    direction = "declining" if match else "rising/flat"
    reason = (
        f"{VOLUME_MA_WINDOW}-bar volume MA slope {normalized * 100:.2f}%/bar ({direction})"
    )
    score = -normalized if match else 0.0
    return {"match": match, "reason": reason, "score": score}


def _evaluate_range_after_drop(candles: list[dict], timeframe: str) -> RuleResult:
    need = _weeks_to_bars(LOOKBACK_WEEKS, timeframe)
    if len(candles) < need:
        return _insufficient("range_after_drop", len(candles), need)

    window = candles[-need:]
    highs = [float(c["high"]) for c in window]
    lows = [float(c["low"]) for c in window]

    drawdown = _max_drawdown(highs, lows)
    match = drawdown >= DROP_PCT
    reason = (
        f"{drawdown * 100:.1f}% drawdown over prior {LOOKBACK_WEEKS} weeks"
        + ("" if match else f" (< {DROP_PCT * 100:.0f}% threshold)")
    )
    score = drawdown if match else 0.0
    return {"match": match, "reason": reason, "score": score}


def _evaluate_range_after_rally(candles: list[dict], timeframe: str) -> RuleResult:
    need = _weeks_to_bars(LOOKBACK_WEEKS, timeframe)
    if len(candles) < need:
        return _insufficient("range_after_rally", len(candles), need)

    window = candles[-need:]
    highs = [float(c["high"]) for c in window]
    lows = [float(c["low"]) for c in window]

    rally = _max_rally(highs, lows)
    match = rally >= RALLY_PCT
    reason = (
        f"{rally * 100:.1f}% rally over prior {LOOKBACK_WEEKS} weeks"
        + ("" if match else f" (< {RALLY_PCT * 100:.0f}% threshold)")
    )
    score = rally if match else 0.0
    return {"match": match, "reason": reason, "score": score}


_SINGLE_SYMBOL_RULES: dict[str, Callable[[list[dict], str], RuleResult]] = {
    "range_duration_gt_4w": _evaluate_range_duration,
    "volume_declining": _evaluate_volume_declining,
    "range_after_drop": _evaluate_range_after_drop,
    "range_after_rally": _evaluate_range_after_rally,
}

RELATIVE_STRENGTH_RULE = "relative_strength_top_decile"
RULE_NAMES: tuple[str, ...] = (*_SINGLE_SYMBOL_RULES, RELATIVE_STRENGTH_RULE)


# ---------------------------------------------------------------------------
# Relative strength (cross-sectional)
# ---------------------------------------------------------------------------

def relative_strength_metric(
    candles: list[dict],
    btc_candles: list[dict],
    timeframe: str,
) -> float | None:
    """Return the symbol/BTC ratio performance over the RS lookback, or None.

    The metric is the percentage change of the close ratio (symbol/BTC) from the
    start to the end of the lookback window, measured over candles that share an
    ``open_time`` so the two series are aligned.
    """
    btc_by_time = {int(c["open_time"]): float(c["close"]) for c in btc_candles}
    ratios: list[float] = []
    for candle in candles:
        btc_close = btc_by_time.get(int(candle["open_time"]))
        if btc_close is None or btc_close <= 0:
            continue
        sym_close = float(candle["close"])
        if sym_close <= 0:
            continue
        ratios.append(sym_close / btc_close)

    lookback = _weeks_to_bars(RS_LOOKBACK_WEEKS, timeframe)
    if len(ratios) < lookback or lookback < 2:
        return None
    window = ratios[-lookback:]
    start = window[0]
    if start <= 0:
        return None
    return window[-1] / start - 1.0


def _percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 1]) of a non-empty list."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * frac


def _evaluate_relative_strength(
    metrics: dict[str, float | None],
) -> dict[str, RuleResult]:
    """Evaluate the RS rule across a set of symbols, returning per-symbol results."""
    valid = {sym: m for sym, m in metrics.items() if m is not None}
    results: dict[str, RuleResult] = {}

    if not valid:
        for sym in metrics:
            results[sym] = {
                "match": False,
                "reason": "insufficient overlapping data for relative strength",
                "score": 0.0,
            }
        return results

    threshold = _percentile(list(valid.values()), RS_TOP_DECILE)
    for sym, metric in metrics.items():
        if metric is None:
            results[sym] = {
                "match": False,
                "reason": "insufficient overlapping data for relative strength",
                "score": 0.0,
            }
            continue
        match = metric >= threshold
        reason = (
            f"RS {metric * 100:+.1f}% vs BTC over {RS_LOOKBACK_WEEKS}w "
            f"({'in' if match else 'below'} top decile, threshold {threshold * 100:+.1f}%)"
        )
        results[sym] = {"match": match, "reason": reason, "score": metric}
    return results


# ---------------------------------------------------------------------------
# Numeric helpers (pure Python — no numpy dependency)
# ---------------------------------------------------------------------------

def _rolling_mean(values: list[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be >= 1")
    if len(values) < window:
        return []
    out: list[float] = []
    running = sum(values[:window])
    out.append(running / window)
    for i in range(window, len(values)):
        running += values[i] - values[i - window]
        out.append(running / window)
    return out


def _least_squares_slope(series: list[float]) -> float:
    """Slope of the best-fit line of ``series`` against its index (0..n-1)."""
    n = len(series)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(series) / n
    num = 0.0
    den = 0.0
    for i, y in enumerate(series):
        dx = i - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den == 0:
        return 0.0
    return num / den


def _max_drawdown(highs: list[float], lows: list[float]) -> float:
    """Largest peak-to-subsequent-trough decline as a fraction of the peak."""
    worst = 0.0
    running_peak = highs[0]
    for high, low in zip(highs, lows):
        running_peak = max(running_peak, high)
        if running_peak > 0:
            drawdown = (running_peak - low) / running_peak
            worst = max(worst, drawdown)
    return worst


def _max_rally(highs: list[float], lows: list[float]) -> float:
    """Largest trough-to-subsequent-peak advance as a fraction of the trough."""
    best = 0.0
    running_trough = lows[0]
    for high, low in zip(highs, lows):
        running_trough = min(running_trough, low)
        if running_trough > 0:
            rally = (high - running_trough) / running_trough
            best = max(best, rally)
    return best


# ---------------------------------------------------------------------------
# Concurrent OHLCV fetching
# ---------------------------------------------------------------------------

mcp = FastMCP("wyckoff-scanner")
market_data_client = BinanceMarketDataClient()


def _required_bars(rule: str, timeframe: str) -> int:
    if rule == "range_duration_gt_4w":
        return _weeks_to_bars(RANGE_MIN_WEEKS, timeframe) + FETCH_BUFFER_BARS
    if rule == "volume_declining":
        return VOLUME_MA_WINDOW + 5 + FETCH_BUFFER_BARS
    if rule in ("range_after_drop", "range_after_rally"):
        return _weeks_to_bars(LOOKBACK_WEEKS, timeframe) + FETCH_BUFFER_BARS
    if rule == RELATIVE_STRENGTH_RULE:
        return _weeks_to_bars(RS_LOOKBACK_WEEKS, timeframe) + FETCH_BUFFER_BARS
    raise UnknownRuleError(_unknown_rule_message(rule))


def _fetch_limit(rule: str, timeframe: str) -> int:
    return max(VOLUME_MA_WINDOW + 5, min(MAX_LIMIT, _required_bars(rule, timeframe)))


async def _fetch_one(
    symbol: str, timeframe: str, limit: int
) -> tuple[str, list[dict] | None, Exception | None]:
    try:
        candles = await asyncio.to_thread(
            market_data_client.get_ohlcv, symbol, timeframe, limit
        )
        return symbol, list(candles), None
    except Exception as exc:  # noqa: BLE001 - surfaced as a per-symbol reason, not swallowed.
        return symbol, None, exc


async def _fetch_many(
    symbols: list[str], timeframe: str, limit: int
) -> dict[str, tuple[list[dict] | None, Exception | None]]:
    # The shared BinanceMarketDataClient is synchronous and its rate limiter
    # assumes sequential calls; cap concurrency so a wide scan does not fire a
    # burst of simultaneous requests (risking HTTP 429) or thrash the LRU cache.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def _guarded(sym: str) -> tuple[str, list[dict] | None, Exception | None]:
        async with semaphore:
            return await _fetch_one(sym, timeframe, limit)

    gathered = await asyncio.gather(*(_guarded(sym) for sym in symbols))
    return {sym: (candles, err) for sym, candles, err in gathered}


# ---------------------------------------------------------------------------
# Scan orchestration
# ---------------------------------------------------------------------------

def _unknown_rule_message(rule: str) -> str:
    return f"Unknown rule {rule!r}; available: {', '.join(RULE_NAMES)}"


def _validate_rule(rule: str) -> None:
    if rule not in RULE_NAMES:
        raise UnknownRuleError(_unknown_rule_message(rule))


async def _scan_async(
    symbols: list[str], timeframe: str, rule: str
) -> list[ScanResult]:
    normalized_tf = normalize_timeframe(timeframe)
    fetch_limit = _fetch_limit(rule, normalized_tf)

    fetch_symbols = list(symbols)
    if rule == RELATIVE_STRENGTH_RULE and BTC_REFERENCE_SYMBOL not in fetch_symbols:
        fetch_symbols.append(BTC_REFERENCE_SYMBOL)

    fetched = await _fetch_many(fetch_symbols, normalized_tf, fetch_limit)

    if rule == RELATIVE_STRENGTH_RULE:
        return _scan_relative_strength(symbols, fetched, normalized_tf)
    return _scan_single_symbol(symbols, fetched, normalized_tf, rule)


def _scan_single_symbol(
    symbols: list[str],
    fetched: dict[str, tuple[list[dict] | None, Exception | None]],
    timeframe: str,
    rule: str,
) -> list[ScanResult]:
    evaluator = _SINGLE_SYMBOL_RULES[rule]
    results: list[ScanResult] = []
    for sym in symbols:
        candles, err = fetched[sym]
        if err is not None or candles is None:
            results.append(
                {"symbol": sym, "match": False, "reason": f"data fetch failed: {err}", "score": 0.0}
            )
            continue
        evaluation = evaluator(candles, timeframe)
        results.append({"symbol": sym, **evaluation})
    return results


def _scan_relative_strength(
    symbols: list[str],
    fetched: dict[str, tuple[list[dict] | None, Exception | None]],
    timeframe: str,
) -> list[ScanResult]:
    btc_candles, btc_err = fetched.get(BTC_REFERENCE_SYMBOL, (None, None))
    if btc_err is not None or btc_candles is None:
        raise ScannerError(f"relative strength requires BTC data: {btc_err}")

    metrics: dict[str, float | None] = {}
    fetch_errors: dict[str, Exception] = {}
    for sym in symbols:
        candles, err = fetched[sym]
        if err is not None or candles is None:
            metrics[sym] = None
            if err is not None:
                fetch_errors[sym] = err
            continue
        metrics[sym] = relative_strength_metric(candles, btc_candles, timeframe)

    evaluations = _evaluate_relative_strength(metrics)
    results: list[ScanResult] = []
    for sym in symbols:
        if sym in fetch_errors:
            results.append(
                {
                    "symbol": sym,
                    "match": False,
                    "reason": f"data fetch failed: {fetch_errors[sym]}",
                    "score": 0.0,
                }
            )
            continue
        results.append({"symbol": sym, **evaluations[sym]})
    return results


async def _scan_ranked(
    symbols: list[str],
    timeframe: str,
    rule: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[ScanResult]:
    """Scan ``symbols`` against ``rule`` and return ranked matches (async core)."""
    if not symbols:
        raise ValueError("symbols must be a non-empty list")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    _validate_rule(rule)

    all_results = await _scan_async(symbols, timeframe, rule)
    matches = [r for r in all_results if r["match"]]
    matches.sort(key=lambda r: r["score"], reverse=True)
    return matches[:max_results]


def scan(
    symbols: list[str],
    timeframe: str,
    rule: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[ScanResult]:
    """Synchronous entry point for ``_scan_ranked`` (CLI/tests outside an event loop)."""
    return asyncio.run(_scan_ranked(symbols, timeframe, rule, max_results))


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def scan_universe(
    symbols: list[str],
    timeframe: str,
    rule: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[ScanResult]:
    """Scan a list of symbols against a built-in rule, returning ranked matches.

    Returns up to ``max_results`` symbols that match ``rule``, sorted by score
    (strongest first), each with a human-readable ``reason``.

    Async so FastMCP awaits it on its own event loop — the concurrent OHLCV
    pulls run via ``asyncio.gather`` inside that loop (never a nested
    ``asyncio.run``, which would raise inside a running loop).
    """
    return await _scan_ranked(symbols, timeframe, rule, max_results)


@mcp.tool()
def get_universe(name: str) -> list[str]:
    """Return the symbols in a predefined universe (top20_alts, defi_index, low_caps)."""
    try:
        return list(UNIVERSES[name])
    except KeyError as exc:
        available = ", ".join(UNIVERSES)
        raise UnknownUniverseError(
            f"Unknown universe {name!r}; available: {available}"
        ) from exc


@mcp.tool()
async def evaluate_rule(symbol: str, timeframe: str, rule: str) -> RuleResult:
    """Evaluate a single symbol against one rule, returning {match, reason, score}.

    For ``relative_strength_top_decile`` the symbol is ranked against the
    ``top20_alts`` reference universe.

    Async so FastMCP awaits it on its own event loop (see ``scan_universe``).
    """
    return await _evaluate_async(symbol, timeframe, rule)


async def _evaluate_async(symbol: str, timeframe: str, rule: str) -> RuleResult:
    """Evaluate a single symbol against ``rule`` (async core)."""
    _validate_rule(rule)
    normalized_tf = normalize_timeframe(timeframe)

    if rule == RELATIVE_STRENGTH_RULE:
        return await _evaluate_relative_strength_for_symbol(symbol, normalized_tf)

    fetch_limit = _fetch_limit(rule, normalized_tf)
    candles = await asyncio.to_thread(
        market_data_client.get_ohlcv, symbol, normalized_tf, fetch_limit
    )
    return _SINGLE_SYMBOL_RULES[rule](candles, normalized_tf)


def evaluate(symbol: str, timeframe: str, rule: str) -> RuleResult:
    """Synchronous entry point for ``_evaluate_async`` (CLI/tests outside an event loop)."""
    return asyncio.run(_evaluate_async(symbol, timeframe, rule))


async def _evaluate_relative_strength_for_symbol(symbol: str, timeframe: str) -> RuleResult:
    reference = UNIVERSES["top20_alts"]
    normalized_target = normalize_symbol(symbol)
    universe = list(reference)
    if not any(normalize_symbol(s) == normalized_target for s in universe):
        universe.append(symbol)

    results = await _scan_async(universe, timeframe, RELATIVE_STRENGTH_RULE)
    for result in results:
        if normalize_symbol(result["symbol"]) == normalized_target:
            return {"match": result["match"], "reason": result["reason"], "score": result["score"]}
    raise ScannerError(f"symbol {symbol!r} missing from relative-strength scan")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
