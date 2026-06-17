"""Tests for analysis_journal_server: JSONL journaling, filters, and reviews."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.mcp import analysis_journal_server
from scripts.mcp.analysis_journal_server import AnalysisJournalStore, JournalCorruptionError


def _base_kwargs(**overrides) -> dict:
    base = {
        "symbol": "BTC/USDT",
        "timeframe": "1d",
        "model": "gpt-5",
        "effort": "medium",
        "narrative": "BTC is testing a Phase C spring with improving demand.",
        "structure": "accumulation",
        "phase": "C",
        "forecast": {
            "direction": "up",
            "trigger": "daily close above creek",
            "invalidation": "break below spring low",
            "confidence": 0.68,
        },
        "chart_path": "data/charts/btc-2026-06.png",
    }
    base.update(overrides)
    return base


def test_log_and_get_analysis_roundtrip(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))

    fetched = store.get_analysis(logged["analysis_id"])

    assert fetched == logged
    assert fetched is not None
    assert fetched["review"] is None
    assert fetched["logged_at"] == "2026-06-01T00:00:00Z"


def test_month_file_path_uses_logged_at_month(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    store.log_analysis(**_base_kwargs(timestamp="2026-07-15T10:00:00Z"))

    assert (tmp_path / "2026-07.jsonl").exists()
    assert not (tmp_path / "2026-06.jsonl").exists()


def test_list_analyses_filters_and_sorts(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    store.log_analysis(**_base_kwargs(
        symbol="ETH/USDT",
        model="gpt-4.1",
        timestamp="2026-06-10T00:00:00Z",
    ))
    btc_late = store.log_analysis(**_base_kwargs(
        symbol="BTC/USDT",
        model="gpt-5",
        timestamp="2026-06-20T00:00:00Z",
    ))
    btc_early = store.log_analysis(**_base_kwargs(
        symbol="BTC/USDT",
        model="gpt-5",
        timestamp="2026-06-05T00:00:00Z",
    ))
    store.log_analysis(**_base_kwargs(
        symbol="BTC/USDT",
        model="gpt-5-mini",
        timestamp="2026-07-01T00:00:00Z",
    ))

    results = store.list_analyses(
        symbol="BTC/USDT",
        model="gpt-5",
        start="2026-06-01T00:00:00Z",
        end="2026-06-30T23:59:59Z",
    )

    assert [r["analysis_id"] for r in results] == [
        btc_early["analysis_id"],
        btc_late["analysis_id"],
    ]


def test_two_logged_analyses_append_two_lines(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))
    store.log_analysis(**_base_kwargs(timestamp="2026-06-02T00:00:00Z"))

    lines = [
        line
        for line in (tmp_path / "2026-06.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(lines) == 2
    assert all("review" in json.loads(line) for line in lines)


def test_review_analysis_merges_into_get_and_list(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))

    review = store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="up",
        hit_trigger=True,
        note="Creek break followed through.",
        reviewed_at="2026-09-01T00:00:00Z",
    )

    assert review is not None
    fetched = store.get_analysis(logged["analysis_id"])
    listed = store.list_analyses(symbol="BTC/USDT")
    assert fetched is not None
    assert fetched["review"] == review
    assert listed[0]["review"] == review

    analysis_lines = (tmp_path / "2026-06.jsonl").read_text(encoding="utf-8").splitlines()
    review_lines = (tmp_path / "2026-09.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(analysis_lines) == 1
    assert len(review_lines) == 1
    assert json.loads(review_lines[0])["type"] == "review"


def test_latest_review_wins(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))

    store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="sideways",
        hit_trigger=False,
        note="Early review.",
        reviewed_at="2026-08-01T00:00:00Z",
    )
    latest = store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="up",
        hit_trigger=True,
        note="Later review.",
        reviewed_at="2026-09-01T00:00:00Z",
    )

    fetched = store.get_analysis(logged["analysis_id"])
    assert fetched is not None
    assert fetched["review"] == latest


def test_date_range_list_merges_review_from_later_month(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))
    review = store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="up",
        hit_trigger=True,
        note="Reviewed after the analysis window.",
        reviewed_at="2026-09-01T00:00:00Z",
    )

    results = store.list_analyses(
        start="2026-06-01T00:00:00Z",
        end="2026-06-30T23:59:59Z",
    )

    assert len(results) == 1
    assert results[0]["review"] == review


def test_missing_analysis_returns_none(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)

    assert store.get_analysis("missing-id") is None
    assert store.review_analysis(
        analysis_id="missing-id",
        realized_direction="up",
        hit_trigger=True,
        note="No-op.",
    ) is None


def test_invalid_forecast_or_symbol_raises(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)

    with pytest.raises(ValueError, match="symbol"):
        store.log_analysis(**_base_kwargs(symbol=""))

    incomplete_forecast = {
        "direction": "up",
        "trigger": "daily close above creek",
        "confidence": 0.68,
    }
    with pytest.raises(ValueError, match="forecast"):
        store.log_analysis(**_base_kwargs(forecast=incomplete_forecast))

    with pytest.raises(ValueError, match="forecast.confidence"):
        store.log_analysis(**_base_kwargs(forecast={**_base_kwargs()["forecast"], "confidence": 1.5}))

    with pytest.raises(ValueError, match="forecast.confidence"):
        store.log_analysis(**_base_kwargs(forecast={**_base_kwargs()["forecast"], "confidence": float("nan")}))

    with pytest.raises(ValueError, match="forecast.direction"):
        store.log_analysis(**_base_kwargs(forecast={**_base_kwargs()["forecast"], "direction": {}}))

    with pytest.raises(ValueError, match="narrative"):
        store.log_analysis(**_base_kwargs(narrative=" "))


def test_review_analysis_rejects_non_bool_hit_trigger(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))

    with pytest.raises(ValueError, match="hit_trigger"):
        store.review_analysis(
            analysis_id=logged["analysis_id"],
            realized_direction="up",
            hit_trigger="false",  # type: ignore[arg-type]
            note="String false must not become truthy.",
        )


def test_corrupt_jsonl_record_raises_with_file_and_line(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    (tmp_path / "2026-06.jsonl").write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(JournalCorruptionError, match=r"2026-06\.jsonl:1"):
        store.list_analyses()


def test_invalid_logged_at_record_raises(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    record = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))
    record["logged_at"] = "bad timestamp"
    (tmp_path / "2026-06.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(JournalCorruptionError, match="invalid logged_at"):
        store.list_analyses()


def test_valid_new_review_replaces_older_review(tmp_path: Path) -> None:
    store = AnalysisJournalStore(tmp_path)
    logged = store.log_analysis(**_base_kwargs(timestamp="2026-06-01T00:00:00Z"))
    old = store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="sideways",
        hit_trigger=False,
        note="Older review.",
        reviewed_at="2026-08-01T00:00:00Z",
    )
    new = store.review_analysis(
        analysis_id=logged["analysis_id"],
        realized_direction="up",
        hit_trigger=True,
        note="Newer review.",
        reviewed_at="2026-09-01T00:00:00Z",
    )

    assert old is not None
    fetched = store.get_analysis(logged["analysis_id"])
    assert fetched is not None
    assert fetched["review"] == new


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def log_analysis(self, **kwargs):
        self.calls.append(("log_analysis", kwargs))
        return {"analysis_id": "fake-analysis", "review": None}

    def list_analyses(self, **kwargs):
        self.calls.append(("list_analyses", kwargs))
        return [{"analysis_id": "fake-analysis", "review": None}]

    def get_analysis(self, analysis_id: str):
        self.calls.append(("get_analysis", {"analysis_id": analysis_id}))
        return {"analysis_id": analysis_id, "review": None}

    def review_analysis(self, **kwargs):
        self.calls.append(("review_analysis", kwargs))
        return {"reviewed_at": "2026-09-01T00:00:00Z"}


def test_mcp_tool_wrappers_delegate_to_module_store(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeStore()
    monkeypatch.setattr(analysis_journal_server, "store", fake)

    assert analysis_journal_server.log_analysis(
        symbol="BTC/USDT",
        timeframe="1d",
        model="gpt-5",
        effort="medium",
        narrative="Narrative",
        structure="accumulation",
        phase="C",
        forecast=_base_kwargs()["forecast"],
        chart_path="chart.png",
        timestamp="2026-06-01T00:00:00Z",
    )["analysis_id"] == "fake-analysis"
    assert analysis_journal_server.list_analyses(symbol="BTC/USDT")[0]["analysis_id"] == "fake-analysis"
    assert analysis_journal_server.get_analysis("fake-analysis")["analysis_id"] == "fake-analysis"
    assert analysis_journal_server.review_analysis(
        analysis_id="fake-analysis",
        realized_direction="up",
        hit_trigger=True,
        note="Reviewed.",
    )["reviewed_at"] == "2026-09-01T00:00:00Z"

    assert [call[0] for call in fake.calls] == [
        "log_analysis",
        "list_analyses",
        "get_analysis",
        "review_analysis",
    ]
