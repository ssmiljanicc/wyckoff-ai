"""MCP server for rendering OHLCV candlestick charts."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

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

try:
    from scripts.mcp.market_data_client import (  # type: ignore[import-not-found]
        DEFAULT_LIMIT,
        BinanceMarketDataClient,
    )
except ImportError:
    DEFAULT_LIMIT = 200
    BinanceMarketDataClient = None  # type: ignore[assignment,misc]


MIN_WIDTH = 1200
MIN_HEIGHT = 600
DEFAULT_DPI = 100
RENDER_CACHE_SIZE = 128
STYLE_VERSION = "wyckoff_style_v1"
EVAL_STYLE_VERSION = "eval_style_v1"
RENDER_CACHE_DIR = Path(tempfile.gettempdir()) / "wyckoff-ai-chart-renderer"
REQUIRED_CANDLE_FIELDS = ("open_time", "open", "high", "low", "close", "volume")


class ChartCandle(TypedDict):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: NotRequired[int]
    quote_volume: NotRequired[float]
    trades: NotRequired[int]


class HorizontalLineAnnotation(TypedDict, total=False):
    price: float
    label: str
    color: str


class PhaseLabelAnnotation(TypedDict, total=False):
    index: int
    label: str
    color: str


class VerticalLineAnnotation(TypedDict, total=False):
    index: int
    label: str
    color: str


class ChartAnnotations(TypedDict, total=False):
    horizontal_lines: list[HorizontalLineAnnotation]
    phase_labels: list[PhaseLabelAnnotation]
    vertical_lines: list[VerticalLineAnnotation]


class RenderedChart(TypedDict):
    path: str
    width: int
    height: int
    format: str
    candle_count: int
    title: str
    cached: bool


class _CacheEntry(TypedDict):
    result: RenderedChart


mcp = FastMCP("wyckoff-chart-renderer")
market_data_client = BinanceMarketDataClient() if BinanceMarketDataClient is not None else None
_render_cache: OrderedDict[str, _CacheEntry] = OrderedDict()


def validate_ohlcv_data(ohlcv_data: list[dict[str, Any]]) -> list[ChartCandle]:
    if not isinstance(ohlcv_data, list) or not ohlcv_data:
        raise ValueError("ohlcv_data must be a non-empty list of candles")

    candles: list[ChartCandle] = []
    previous_open_time: int | None = None
    for index, raw in enumerate(ohlcv_data):
        if not isinstance(raw, dict):
            raise ValueError(f"Candle {index} must be an object")
        missing = [field for field in REQUIRED_CANDLE_FIELDS if field not in raw]
        if missing:
            raise ValueError(f"Candle {index} missing required fields: {', '.join(missing)}")

        open_time = _coerce_int(raw["open_time"], f"candle {index} open_time")
        if previous_open_time is not None and open_time <= previous_open_time:
            raise ValueError("open_time values must be strictly increasing")
        previous_open_time = open_time

        open_price = _coerce_float(raw["open"], f"candle {index} open")
        high_price = _coerce_float(raw["high"], f"candle {index} high")
        low_price = _coerce_float(raw["low"], f"candle {index} low")
        close_price = _coerce_float(raw["close"], f"candle {index} close")
        volume = _coerce_float(raw["volume"], f"candle {index} volume")

        if min(open_price, high_price, low_price, close_price) <= 0:
            raise ValueError(f"Candle {index} prices must be positive")
        if volume < 0:
            raise ValueError(f"Candle {index} volume must be >= 0")
        if high_price < max(open_price, close_price):
            raise ValueError(f"Candle {index} high must be >= open and close")
        if low_price > min(open_price, close_price):
            raise ValueError(f"Candle {index} low must be <= open and close")
        if low_price > high_price:
            raise ValueError(f"Candle {index} low must be <= high")

        candle: ChartCandle = {
            "open_time": open_time,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        }
        candles.append(candle)

    return candles


def ohlcv_to_dataframe(ohlcv_data: list[dict[str, Any]]) -> pd.DataFrame:
    candles = validate_ohlcv_data(ohlcv_data)
    index = pd.to_datetime([candle["open_time"] for candle in candles], unit="ms", utc=True)
    return pd.DataFrame(
        {
            "Open": [candle["open"] for candle in candles],
            "High": [candle["high"] for candle in candles],
            "Low": [candle["low"] for candle in candles],
            "Close": [candle["close"] for candle in candles],
            "Volume": [candle["volume"] for candle in candles],
        },
        index=index,
    )


def make_wyckoff_style() -> Any:
    market_colors = mpf.make_marketcolors(
        up="#16803c",
        down="#b3261e",
        edge="inherit",
        wick={"up": "#16803c", "down": "#b3261e"},
        volume={"up": "#77a98a", "down": "#d28a85"},
    )
    return mpf.make_mpf_style(
        base_mpf_style="default",
        marketcolors=market_colors,
        facecolor="#ffffff",
        figcolor="#ffffff",
        gridcolor="#e8e8e8",
        gridstyle="-",
        y_on_right=False,
        rc={
            "axes.edgecolor": "#444444",
            "axes.labelcolor": "#222222",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "font.size": 9,
        },
    )


def make_eval_style() -> Any:
    """Neutral mplfinance style for eval charts — avoids project-specific color fingerprints."""
    return mpf.make_mpf_style(base_mpf_style="default", y_on_right=False)


def render_chart_image(
    ohlcv_data: list[dict[str, Any]],
    title: str = "",
    annotations: ChartAnnotations | None = None,
    output_dir: str | Path | None = None,
    width: int = MIN_WIDTH,
    height: int = MIN_HEIGHT,
    style: Any = None,
    style_key: str = STYLE_VERSION,
) -> RenderedChart:
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ValueError(f"Chart dimensions must be at least {MIN_WIDTH}x{MIN_HEIGHT}")

    df = ohlcv_to_dataframe(ohlcv_data)
    normalized_annotations = normalize_annotations(annotations)
    cache_key = _cache_key(df, title, normalized_annotations, width, height, style_key)
    cached = _get_cached_render(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cached"] = True
        return result

    output_root = Path(output_dir) if output_dir is not None else RENDER_CACHE_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{cache_key}.png"
    dpi = DEFAULT_DPI
    figsize = (width / dpi, height / dpi)

    plot_style = style if style is not None else make_wyckoff_style()
    fig, axes = mpf.plot(
        df,
        type="candle",
        volume=True,
        style=plot_style,
        title=title,
        figsize=figsize,
        returnfig=True,
        tight_layout=False,
        datetime_format="%Y-%m-%d",
        xrotation=0,
        warn_too_much_data=len(df) + 1,
    )
    try:
        _apply_annotations(axes, df, normalized_annotations)
        fig.set_size_inches(*figsize)
        fig.savefig(path, dpi=dpi, format="png", facecolor="white")
    finally:
        plt.close(fig)

    result: RenderedChart = {
        "path": str(path),
        "width": width,
        "height": height,
        "format": "png",
        "candle_count": len(df),
        "title": title,
        "cached": False,
    }
    _set_cached_render(cache_key, result)
    return dict(result)


@mcp.tool()
def render_chart(
    ohlcv_data: list[dict[str, Any]],
    title: str = "",
    annotations: ChartAnnotations | None = None,
) -> RenderedChart:
    """Render supplied OHLCV candles as a Vision-readable PNG chart."""
    return render_chart_image(ohlcv_data, title, annotations)


@mcp.tool()
def render_chart_for_symbol(
    symbol: str,
    timeframe: str,
    limit: int = DEFAULT_LIMIT,
    end_time: int | str | None = None,
) -> RenderedChart:
    """Fetch OHLCV through the market data client and render it as a PNG chart."""
    if market_data_client is None:
        raise RuntimeError(
            "render_chart_for_symbol requires issue #9 market data client; "
            "use render_chart with supplied OHLCV for local testing"
        )
    ohlcv_data = market_data_client.get_ohlcv(symbol, timeframe, limit, end_time=end_time)
    return render_chart(ohlcv_data, f"{symbol.upper()} {timeframe}", None)


def normalize_annotations(annotations: ChartAnnotations | None) -> ChartAnnotations:
    if annotations is None:
        return {}
    if not isinstance(annotations, dict):
        raise ValueError("annotations must be an object")

    normalized: ChartAnnotations = {}
    horizontal_lines = annotations.get("horizontal_lines", [])
    phase_labels = annotations.get("phase_labels", [])
    if horizontal_lines is None:
        horizontal_lines = []
    if phase_labels is None:
        phase_labels = []
    if not isinstance(horizontal_lines, list):
        raise ValueError("annotations.horizontal_lines must be a list")
    if not isinstance(phase_labels, list):
        raise ValueError("annotations.phase_labels must be a list")

    normalized_lines: list[HorizontalLineAnnotation] = []
    for index, line in enumerate(horizontal_lines):
        if not isinstance(line, dict):
            raise ValueError(f"horizontal_lines[{index}] must be an object")
        if "price" not in line:
            raise ValueError(f"horizontal_lines[{index}] missing price")
        normalized_lines.append(
            {
                "price": _coerce_float(line["price"], f"horizontal_lines[{index}].price"),
                "label": str(line.get("label", "")),
                "color": str(line.get("color", "#5b5b5b")),
            }
        )

    normalized_labels: list[PhaseLabelAnnotation] = []
    for index, label in enumerate(phase_labels):
        if not isinstance(label, dict):
            raise ValueError(f"phase_labels[{index}] must be an object")
        if "index" not in label or "label" not in label:
            raise ValueError(f"phase_labels[{index}] must include index and label")
        normalized_labels.append(
            {
                "index": _coerce_int(label["index"], f"phase_labels[{index}].index"),
                "label": str(label["label"]),
                "color": str(label.get("color", "#1f4e79")),
            }
        )

    vertical_lines = annotations.get("vertical_lines", [])
    if vertical_lines is None:
        vertical_lines = []
    if not isinstance(vertical_lines, list):
        raise ValueError("annotations.vertical_lines must be a list")

    normalized_vlines: list[VerticalLineAnnotation] = []
    for index, vline in enumerate(vertical_lines):
        if not isinstance(vline, dict):
            raise ValueError(f"vertical_lines[{index}] must be an object")
        if "index" not in vline:
            raise ValueError(f"vertical_lines[{index}] missing index")
        normalized_vlines.append(
            {
                "index": _coerce_int(vline["index"], f"vertical_lines[{index}].index"),
                "label": str(vline.get("label", "")),
                "color": str(vline.get("color", "#888888")),
            }
        )

    if normalized_lines:
        normalized["horizontal_lines"] = normalized_lines
    if normalized_labels:
        normalized["phase_labels"] = normalized_labels
    if normalized_vlines:
        normalized["vertical_lines"] = normalized_vlines
    return normalized


def main() -> None:
    mcp.run()


def _apply_annotations(axes: list[Any], df: pd.DataFrame, annotations: ChartAnnotations) -> None:
    if not axes:
        return
    price_axis = axes[0]
    for line in annotations.get("horizontal_lines", []):
        price = line["price"]
        color = line.get("color", "#5b5b5b")
        label = line.get("label", "")
        price_axis.axhline(price, color=color, linewidth=1.0, linestyle="--", alpha=0.85)
        if label:
            price_axis.text(
                0.99,
                price,
                label,
                color=color,
                fontsize=8,
                ha="right",
                va="bottom",
                transform=price_axis.get_yaxis_transform(),
                bbox={"facecolor": "white", "edgecolor": color, "alpha": 0.7, "pad": 1.5},
            )

    y_min, y_max = price_axis.get_ylim()
    label_y = y_max - ((y_max - y_min) * 0.08)
    candle_count = len(df)
    for phase_label in annotations.get("phase_labels", []):
        candle_index = phase_label["index"]
        if candle_index < 0 or candle_index >= candle_count:
            raise ValueError(f"phase label index {candle_index} outside candle range")
        price_axis.text(
            candle_index,
            label_y,
            phase_label["label"],
            color=phase_label.get("color", "#1f4e79"),
            fontsize=9,
            fontweight="bold",
            ha="center",
            va="top",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1.5},
        )

    for vline in annotations.get("vertical_lines", []):
        vidx = vline["index"]
        if vidx < 0 or vidx >= candle_count:
            raise ValueError(f"vertical line index {vidx} outside candle range")
        color = vline.get("color", "#888888")
        label = vline.get("label", "")
        price_axis.axvline(vidx, color=color, linewidth=1.0, linestyle="--", alpha=0.85)
        if label:
            price_axis.text(
                vidx,
                label_y,
                label,
                color=color,
                fontsize=8,
                ha="center",
                va="top",
                rotation=90,
                bbox={"facecolor": "white", "edgecolor": color, "alpha": 0.7, "pad": 1.5},
            )


def _cache_key(
    df: pd.DataFrame,
    title: str,
    annotations: ChartAnnotations,
    width: int,
    height: int,
    style_key: str = STYLE_VERSION,
) -> str:
    payload = {
        "style": style_key,
        "title": title,
        "annotations": annotations,
        "width": width,
        "height": height,
        "candles": [
            {
                "open_time": int(timestamp.timestamp() * 1000),
                "open": float(row.Open),
                "high": float(row.High),
                "low": float(row.Low),
                "close": float(row.Close),
                "volume": float(row.Volume),
            }
            for timestamp, row in df.iterrows()
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _get_cached_render(cache_key: str) -> RenderedChart | None:
    entry = _render_cache.get(cache_key)
    if entry is None:
        return None
    path = Path(entry["result"]["path"])
    if not path.exists():
        _render_cache.pop(cache_key, None)
        return None
    _render_cache.move_to_end(cache_key)
    return dict(entry["result"])


def _set_cached_render(cache_key: str, result: RenderedChart) -> None:
    _render_cache[cache_key] = {"result": dict(result)}
    _render_cache.move_to_end(cache_key)
    if len(_render_cache) > RENDER_CACHE_SIZE:
        _render_cache.popitem(last=False)


def _coerce_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        coerced = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(coerced):
        raise ValueError(f"{field_name} must be finite")
    return coerced


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field_name} must be an integer")
    return coerced


if __name__ == "__main__":
    main()
