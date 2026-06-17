from __future__ import annotations

import struct
from pathlib import Path

import pandas as pd
import pytest

from scripts.mcp import chart_renderer


def sample_ohlcv(count: int = 80) -> list[dict]:
    candles: list[dict] = []
    for index in range(count):
        open_price = 100 + index * 0.5
        close_price = open_price + (0.8 if index % 2 == 0 else -0.6)
        candles.append(
            {
                "open_time": index * 86_400_000,
                "open": open_price,
                "high": max(open_price, close_price) + 1.5,
                "low": min(open_price, close_price) - 1.0,
                "close": close_price,
                "volume": 1_000 + index * 10,
            }
        )
    return candles


def png_dimensions(path: str | Path) -> tuple[int, int]:
    with Path(path).open("rb") as handle:
        signature = handle.read(8)
        assert signature == b"\x89PNG\r\n\x1a\n"
        ihdr_length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        assert ihdr_length == 13
        assert chunk_type == b"IHDR"
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


def test_validation_accepts_valid_candles() -> None:
    candles = chart_renderer.validate_ohlcv_data(sample_ohlcv(2))

    assert candles[0]["open"] == 100.0
    assert candles[1]["volume"] == 1010.0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda candles: candles.clear(), "non-empty"),
        (lambda candles: candles[0].pop("open"), "missing"),
        (lambda candles: candles[0].update({"close": "bad"}), "numeric"),
        (lambda candles: candles[0].update({"low": 0}), "positive"),
        (lambda candles: candles[0].update({"volume": -1}), "volume"),
        (lambda candles: candles[0].update({"high": 99}), "high"),
        (lambda candles: candles[0].update({"low": 102}), "low"),
        (lambda candles: candles[1].update({"open_time": candles[0]["open_time"]}), "increasing"),
    ],
)
def test_validation_rejects_invalid_candles(mutation, message: str) -> None:
    candles = sample_ohlcv(2)
    mutation(candles)

    with pytest.raises(ValueError, match=message):
        chart_renderer.validate_ohlcv_data(candles)


def test_ohlcv_to_dataframe_uses_datetime_index_and_mpf_columns() -> None:
    df = chart_renderer.ohlcv_to_dataframe(sample_ohlcv(3))

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert df.iloc[0]["Open"] == 100.0


def test_make_wyckoff_style_returns_mpf_style() -> None:
    style = chart_renderer.make_wyckoff_style()

    assert style["facecolor"] == "#ffffff"
    assert style["gridcolor"] == "#e8e8e8"


def test_render_creates_png_with_minimum_dimensions(tmp_path: Path) -> None:
    result = chart_renderer.render_chart_image(
        sample_ohlcv(80),
        "Mock BTC 1d",
        output_dir=tmp_path,
    )

    assert result["format"] == "png"
    assert result["candle_count"] == 80
    assert Path(result["path"]).exists()
    assert png_dimensions(result["path"]) == (1200, 600)


def test_render_chart_image_rejects_small_dimensions(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 1200x600"):
        chart_renderer.render_chart_image(sample_ohlcv(2), output_dir=tmp_path, width=800, height=400)


def test_render_chart_image_supports_annotations(tmp_path: Path) -> None:
    result = chart_renderer.render_chart_image(
        sample_ohlcv(80),
        "Annotated",
        {
            "horizontal_lines": [
                {"price": 105, "label": "SC", "color": "#444444"},
                {"price": 118, "label": "AR"},
            ],
            "phase_labels": [
                {"index": 10, "label": "A"},
                {"index": 40, "label": "B", "color": "#8a4b00"},
            ],
        },
        output_dir=tmp_path,
    )

    assert Path(result["path"]).exists()
    assert png_dimensions(result["path"]) == (1200, 600)


def test_render_chart_image_rejects_bad_annotations(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside candle range"):
        chart_renderer.render_chart_image(
            sample_ohlcv(4),
            annotations={"phase_labels": [{"index": 99, "label": "E"}]},
            output_dir=tmp_path,
        )


def test_render_cache_returns_existing_path_on_identical_request(tmp_path: Path) -> None:
    chart_renderer._render_cache.clear()

    first = chart_renderer.render_chart_image(sample_ohlcv(20), "Cache", output_dir=tmp_path)
    second = chart_renderer.render_chart_image(sample_ohlcv(20), "Cache", output_dir=tmp_path)

    assert first["path"] == second["path"]
    assert first["cached"] is False
    assert second["cached"] is True


def test_render_chart_wrapper_returns_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chart_renderer, "RENDER_CACHE_DIR", tmp_path)

    result = chart_renderer.render_chart(sample_ohlcv(10), "Wrapper", None)

    assert result["title"] == "Wrapper"
    assert result["width"] == 1200
    assert Path(result["path"]).exists()


class FakeMarketDataClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, int | str | None]] = []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: int | str | None = None,
    ) -> list[dict]:
        self.calls.append((symbol, timeframe, limit, end_time))
        return sample_ohlcv(limit)


def test_render_chart_for_symbol_uses_market_data_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(chart_renderer, "market_data_client", fake)
    monkeypatch.setattr(chart_renderer, "RENDER_CACHE_DIR", tmp_path)

    result = chart_renderer.render_chart_for_symbol("BTC", "1d", 12)

    assert fake.calls == [("BTC", "1d", 12, None)]
    assert result["title"] == "BTC 1d"
    assert Path(result["path"]).exists()


def test_render_chart_for_symbol_forwards_end_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMarketDataClient()
    monkeypatch.setattr(chart_renderer, "market_data_client", fake)
    monkeypatch.setattr(chart_renderer, "RENDER_CACHE_DIR", tmp_path)

    chart_renderer.render_chart_for_symbol("BTC", "1d", 12, end_time="2019-04-01")

    assert fake.calls == [("BTC", "1d", 12, "2019-04-01")]


def test_render_chart_for_symbol_reports_missing_market_data_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chart_renderer, "market_data_client", None)

    with pytest.raises(RuntimeError, match="requires issue #9 market data client"):
        chart_renderer.render_chart_for_symbol("BTC", "1d", 200)


def test_vertical_lines_annotation(tmp_path: Path) -> None:
    candles = sample_ohlcv(80)
    k = 40

    result = chart_renderer.render_chart_image(
        candles,
        "Vertical line test",
        {"vertical_lines": [{"index": k, "label": "as-of T"}]},
        output_dir=tmp_path,
    )

    assert Path(result["path"]).exists()
    assert png_dimensions(result["path"]) == (1200, 600)


def test_vertical_lines_out_of_range_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside candle range"):
        chart_renderer.render_chart_image(
            sample_ohlcv(4),
            annotations={"vertical_lines": [{"index": 99, "label": "X"}]},
            output_dir=tmp_path,
        )


def test_normalize_annotations_vertical_lines_missing_index() -> None:
    with pytest.raises(ValueError, match="missing index"):
        chart_renderer.normalize_annotations(
            {"vertical_lines": [{"label": "no index", "color": "#aaa"}]}
        )
