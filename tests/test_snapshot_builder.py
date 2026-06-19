"""Tests for scripts/eval/snapshot_builder.py"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from scripts.eval.snapshot_builder import (
    DAY_MS,
    NEUTRAL_EPOCH_MS,
    anonymize,
    build_snapshot,
)


def make_fake_candles(count: int = 60, base_price: float = 4500.0) -> list[dict]:
    candles: list[dict] = []
    for i in range(count):
        open_p = base_price + i * 10
        candles.append(
            {
                "open_time": i * 86_400_000,
                "open": open_p,
                "high": open_p + 50,
                "low": max(1.0, open_p - 50),
                "close": open_p + 5,
                "volume": 500.0 + i,
                "close_time": (i + 1) * 86_400_000 - 1,
                "quote_volume": (500.0 + i) * (open_p + 5),
                "trades": 100,
            }
        )
    return candles


class FakeClient:
    def __init__(self, candles: list[dict]) -> None:
        self._candles = candles
        self.calls: list[dict[str, Any]] = []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: Any = None,
    ) -> list[dict]:
        self.calls.append(
            {"symbol": symbol, "timeframe": timeframe, "limit": limit, "end_time": end_time}
        )
        return self._candles[:limit]


# --- anonymize tests ---


def test_anonymize_pushes_to_unusual_range() -> None:
    # BTC-like input: closes in the ~40k–41k range
    candles = make_fake_candles(60, base_price=40000.0)
    anon, _ = anonymize(candles, case_id="case_01")

    median_anon = statistics.median(c["close"] for c in anon)
    assert not (25_000 <= median_anon <= 55_000), (
        f"Anon median {median_anon:.2f} falls in BTC-like 25k–55k range"
    )


def test_anonymize_deterministic() -> None:
    candles = make_fake_candles(40)
    anon1, meta1 = anonymize(candles, case_id="my_case")
    anon2, meta2 = anonymize(candles, case_id="my_case")

    assert anon1 == anon2
    assert meta1 == meta2


def test_anonymize_raises_on_price_coef_zero() -> None:
    # Force price_coef underflow by patching targets to a value that rounds to 0
    # with a high base price (0.0001 / 35000 = 2.86e-9 → round(…, 8) = 0.0)
    candles = make_fake_candles(10, base_price=35000.0)
    with mock.patch("scripts.eval.snapshot_builder.UNUSUAL_PRICE_TARGETS", [0.0001]):
        with pytest.raises(ValueError, match="price_coef rounded to zero"):
            anonymize(candles, case_id="any_case")


def test_anonymize_different_cases_different_coefs() -> None:
    candles = make_fake_candles(30)
    _, meta_a = anonymize(candles, case_id="case_01")
    _, meta_b = anonymize(candles, case_id="case_02")

    assert meta_a["price_target"] != meta_b["price_target"]


def test_x_axis_not_real_calendar() -> None:
    candles = make_fake_candles(200)
    anon, _ = anonymize(candles, case_id="case_01")

    max_time = max(c["open_time"] for c in anon)
    # 2009-01-01 ≈ 1_230_768_000_000 ms; our neutral times are ≪ that
    assert max_time < 365 * DAY_MS, (
        f"open_time {max_time} is too large — may reveal real calendar era"
    )
    assert anon[0]["open_time"] == NEUTRAL_EPOCH_MS


# --- build_snapshot tests ---


def test_blind_mode_excludes_future(tmp_path: Path) -> None:
    n_bars = 60
    cutoff_ms = 1_554_076_800_000  # 2019-04-01 UTC
    client = FakeClient(make_fake_candles(n_bars + 20))

    result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff=cutoff_ms,
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        client=client,
        base_dir=tmp_path,
    )

    assert len(client.calls) == 1
    assert client.calls[0]["end_time"] == cutoff_ms
    assert client.calls[0]["limit"] == n_bars

    candles_data = json.loads(Path(result["candles_path"]).read_text())
    assert len(candles_data) == n_bars


def test_blind_mode_raises_when_history_is_short(tmp_path: Path) -> None:
    n_bars = 60
    client = FakeClient(make_fake_candles(20))

    with pytest.raises(ValueError, match="Expected 60 candles .* blind but got 20"):
        build_snapshot(
            symbol="BTCUSDT",
            timeframe="1d",
            cutoff=1_554_076_800_000,
            n_bars=n_bars,
            mode="blind",
            case_id="case_01",
            client=client,
            base_dir=tmp_path,
        )


def test_future_visible_extends_and_marks(tmp_path: Path) -> None:
    n_bars = 60
    future_bars = 20
    cutoff_ms = 1_554_076_800_000  # 2019-04-01 UTC
    tf_ms = 86_400_000  # 1d
    total = n_bars + future_bars
    client = FakeClient(make_fake_candles(total + 10))

    result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff=cutoff_ms,
        n_bars=n_bars,
        mode="future_visible",
        case_id="case_01",
        future_bars=future_bars,
        client=client,
        base_dir=tmp_path,
    )

    assert len(client.calls) == 1
    assert client.calls[0]["end_time"] == cutoff_ms + future_bars * tf_ms
    assert client.calls[0]["limit"] == total

    case_dir = Path(result["case_dir"])
    assert (case_dir / "instruction.txt").exists()

    candles_data = json.loads(Path(result["candles_path"]).read_text())
    assert len(candles_data) == total


def test_answer_key_outside_case_dir(tmp_path: Path) -> None:
    n_bars = 30
    client = FakeClient(make_fake_candles(n_bars + 25))

    result = build_snapshot(
        symbol="ETHUSDT",
        timeframe="1d",
        cutoff=1_584_057_600_000,  # 2020-03-13 UTC
        n_bars=n_bars,
        mode="blind",
        case_id="case_02",
        ground_truth="Some ground truth here",
        client=client,
        base_dir=tmp_path,
    )

    answer_key_path = Path(result["answer_key_path"])
    case_dir = Path(result["case_dir"])

    assert answer_key_path.exists()
    assert not answer_key_path.is_relative_to(case_dir)

    answer_key = json.loads(answer_key_path.read_text())
    assert answer_key["symbol"] == "ETHUSDT"
    assert "Some ground truth" in answer_key["ground_truth"]

    candles_text = (case_dir / "candles.json").read_text()
    assert "ETHUSDT" not in candles_text
    assert "ground_truth" not in candles_text


def test_manifest_has_no_truth(tmp_path: Path) -> None:
    n_bars = 30
    client = FakeClient(make_fake_candles(n_bars + 25))

    build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff=1_554_076_800_000,
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        ground_truth="Secret ground truth",
        client=client,
        base_dir=tmp_path,
    )

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    manifest_text = manifest_path.read_text()

    assert "BTCUSDT" not in manifest_text
    assert "ground_truth" not in manifest_text
    assert "cutoff" not in manifest_text

    manifest = json.loads(manifest_text)
    cases = manifest["cases"]
    assert len(cases) == 1
    assert cases[0]["case_id"] == "case_01"
    assert cases[0]["mode"] == "blind"
    assert cases[0]["n_bars"] == n_bars


def test_snapshot_result_paths_exist(tmp_path: Path) -> None:
    n_bars = 40
    client = FakeClient(make_fake_candles(n_bars + 25))

    result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        client=client,
        base_dir=tmp_path,
    )

    assert Path(result["candles_path"]).exists()
    assert Path(result["chart_path"]).exists()
    assert Path(result["answer_key_path"]).exists()


def test_fv_answer_key_separate_from_blind_with_different_coef(tmp_path: Path) -> None:
    """blind and future_visible must NOT share an answer key.

    Their anonymization coefficient differs (median over n_bars vs
    n_bars+future_bars candles), so post_t_candles live in different coef spaces.
    """
    n_bars = 30
    future_bars = 20
    candles = make_fake_candles(n_bars + future_bars + 10)
    answer_extra = {"event_type": "spring", "realized_direction": "up", "decisive": True}

    blind = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        future_bars=future_bars,
        answer_extra=answer_extra,
        include_post_t_candles=True,
        client=FakeClient(candles),
        base_dir=tmp_path,
    )
    fv = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="future_visible",
        case_id="case_01",
        future_bars=future_bars,
        answer_extra=answer_extra,
        include_post_t_candles=True,
        client=FakeClient(candles),
        base_dir=tmp_path,
    )

    blind_path = Path(blind["answer_key_path"])
    fv_path = Path(fv["answer_key_path"])
    assert blind_path.name == "case_01.answer.json"
    assert fv_path.name == "case_01__fv.answer.json"
    assert blind_path != fv_path
    assert blind_path.exists() and fv_path.exists()

    blind_key = json.loads(blind_path.read_text())
    fv_key = json.loads(fv_path.read_text())
    # Different anonymization coefficient — the root cause of the bug.
    assert blind_key["coef_meta"]["price_coef"] != fv_key["coef_meta"]["price_coef"]
    # post_t_candles therefore differ in scale — must not be identical bytes.
    assert blind_key["post_t_candles"] != fv_key["post_t_candles"]
    # The blind key survived (was not overwritten by the fv build).
    assert "post_t_candles" in blind_key


# --- reveal mode (anon vs revealed A/B control) tests ---

# 2019-04-01 UTC — a real epoch, clearly distinct from the neutral 1970 epoch.
REAL_BASE_TIME_MS = 1_554_076_800_000


def make_real_time_candles(count: int, base_price: float = 4500.0) -> list[dict]:
    candles = make_fake_candles(count, base_price=base_price)
    for i, candle in enumerate(candles):
        candle["open_time"] = REAL_BASE_TIME_MS + i * DAY_MS
    return candles


def test_reveal_preserves_real_prices_and_dates(tmp_path: Path) -> None:
    n_bars = 40
    candles = make_real_time_candles(n_bars + 25)
    client = FakeClient(candles)

    result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        client=client,
        reveal=True,
        base_dir=tmp_path,
    )

    revealed = json.loads(Path(result["candles_path"]).read_text())
    assert len(revealed) == n_bars

    # Identity coefficients: real prices pass through unchanged (rounded to 4).
    assert revealed[0]["close"] == round(candles[0]["close"], 4)
    median_revealed = statistics.median(c["close"] for c in revealed)
    median_input = statistics.median(c["close"] for c in candles[:n_bars])
    assert median_revealed == pytest.approx(median_input)

    # Real dates pass through — NOT remapped to the neutral 1970 epoch.
    assert revealed[0]["open_time"] == REAL_BASE_TIME_MS
    assert revealed[0]["open_time"] > 365 * DAY_MS
    assert revealed[0]["open_time"] != NEUTRAL_EPOCH_MS


def test_reveal_writes_separate_answer_key(tmp_path: Path) -> None:
    n_bars = 30
    candles = make_real_time_candles(n_bars + 25)
    answer_extra = {"event_type": "spring", "realized_direction": "up", "decisive": True}

    anon_result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        ground_truth="Real ground truth",
        answer_extra=answer_extra,
        include_post_t_candles=True,
        client=FakeClient(candles),
        base_dir=tmp_path,
    )
    anon_answer_path = Path(anon_result["answer_key_path"])
    anon_answer_before = anon_answer_path.read_text()

    rev_result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_01",
        ground_truth="Real ground truth",
        answer_extra=answer_extra,
        include_post_t_candles=True,
        reveal=True,
        client=FakeClient(candles),
        base_dir=tmp_path,
    )
    rev_answer_path = Path(rev_result["answer_key_path"])

    assert rev_answer_path.name == "case_01__revealed.answer.json"
    assert rev_answer_path != anon_answer_path
    assert rev_answer_path.exists()
    # The revealed key must NOT overwrite the anon key.
    assert anon_answer_path.read_text() == anon_answer_before

    rev_answer = json.loads(rev_answer_path.read_text())
    # Event labels are identical to the anon answer (only the price space differs).
    assert rev_answer["event_type"] == "spring"
    assert rev_answer["realized_direction"] == "up"
    assert rev_answer["coef_meta"]["price_coef"] == 1.0

    post_t = rev_answer["post_t_candles"]
    assert post_t
    # post_t_candles in real space — real dates, not the neutral epoch.
    assert post_t[0]["open_time"] > 365 * DAY_MS


def test_reveal_rejects_future_visible(tmp_path: Path) -> None:
    client = FakeClient(make_real_time_candles(60))
    with pytest.raises(ValueError, match="future_visible"):
        build_snapshot(
            symbol="BTCUSDT",
            timeframe="1d",
            cutoff="2019-04-01",
            n_bars=30,
            mode="future_visible",
            case_id="case_01",
            client=client,
            reveal=True,
            base_dir=tmp_path,
        )


def test_reveal_case_dir_suffix(tmp_path: Path) -> None:
    n_bars = 30
    client = FakeClient(make_real_time_candles(n_bars + 25))

    result = build_snapshot(
        symbol="BTCUSDT",
        timeframe="1d",
        cutoff="2019-04-01",
        n_bars=n_bars,
        mode="blind",
        case_id="case_07",
        client=client,
        reveal=True,
        base_dir=tmp_path,
    )

    assert Path(result["case_dir"]).name.endswith("__revealed")
    assert result["case_dir"].endswith("case_07__revealed")
