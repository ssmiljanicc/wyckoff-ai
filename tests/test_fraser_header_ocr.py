from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import fraser_header_ocr as ocr


def _observation(
    text: str, *, confidence: float = 0.95, x: float = 0.02, y: float = 0.95
) -> dict:
    return {
        "text": text,
        "confidence": confidence,
        "x": x,
        "y": y,
        "w": 0.4,
        "h": 0.03,
    }


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def test_parse_header_accepts_only_exact_high_confidence_header_tokens() -> None:
    parsed = ocr.parse_header(
        [
            _observation("AAPL Apple Inc. Nasdaq GS", y=0.96),
            _observation("40 AAPL (Daily) 190.00", y=0.84),
            _observation("PS", y=0.82),
        ]
    )

    assert parsed["asset"]["value"] == "AAPL"
    assert parsed["asset"]["unique"] is True
    assert parsed["timeframe"]["value"] == "daily"
    assert parsed["timeframe"]["unique"] is True


def test_parse_header_abstains_on_low_confidence_or_ambiguous_values() -> None:
    parsed = ocr.parse_header(
        [
            _observation("AAPL Apple Inc.", confidence=0.84, y=0.96),
            _observation("MS Morgan Stanley", y=0.950),
            _observation("V Visa Inc.", y=0.951),
            _observation("40 MS (Daily) 10", y=0.84),
            _observation("40 MS (Weekly) 10", y=0.83),
        ]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["candidates"] == ["MS", "V"]
    assert parsed["timeframe"]["value"] == "unknown"
    assert parsed["timeframe"]["candidates"] == ["daily", "weekly"]


def test_parse_header_keeps_only_proven_indu_alias() -> None:
    parsed = ocr.parse_header([_observation("$INDU Dow Jones Industrial Average")])

    assert parsed["asset"]["value"] == "DJIA"


def test_parse_header_abstains_when_vision_turns_indu_dollar_sign_into_s() -> None:
    parsed = ocr.parse_header([_observation("SINDU Dow Jones Industrial Average INDX")])

    assert parsed["asset"]["value"] == "unknown"


def test_parse_header_repairs_dollar_as_s_only_for_index_title_row() -> None:
    parsed = ocr.parse_header(
        [_observation("SSPX S&P 500 Large Cap Index INDX", x=0.152, y=0.968)]
    )

    assert parsed["asset"]["value"] == "SPX"
    assert parsed["asset"]["unique"] is True


def test_parse_header_prefers_explicit_symbol_over_higher_implicit_ocr() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "SWTIC Light Crude Oil - Continuous Contract (EOD) CME",
                x=0.053,
                y=0.977,
            ),
            _observation("* $WTIC (Daily) 49.31", x=0.062, y=0.947),
        ]
    )

    assert parsed["asset"]["value"] == "WTIC"
    assert parsed["timeframe"]["value"] == "daily"


def test_parse_header_prefers_structured_lower_panel_header_over_body_label() -> None:
    parsed = ocr.parse_header(
        [
            _observation("BC", x=0.298, y=0.969),
            _observation("A S&P 500 Large Cap Index (15 min)", x=0.009, y=0.961),
            _observation(
                "$SPX S&P 500 Large Cap Index INDX 23-May-2018, 14:44 ET, "
                "05MN Scaling: User-Defined [Reversal: 1, Box Size:1.73] "
                "(c) StockCharts.com",
                x=0.010,
                y=0.403,
            ),
        ]
    )

    assert parsed["asset"]["value"] == "SPX"
    assert parsed["asset"]["members"] == ["SPX"]


@pytest.mark.parametrize(
    "title",
    [
        "SRUT Russell 2000 Small Cap Index INDX",
        "SWTIC Light Crude Oil - Continuous Contract (EOD) CME",
    ],
)
def test_parse_header_abstains_on_implicit_s_for_dollar_market_title(
    title: str,
) -> None:
    parsed = ocr.parse_header([_observation(title, x=0.07, y=0.98)])

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["members"] == []


def test_parse_header_uses_structured_explicit_series_when_s_title_abstains() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "SWTIC Light Crude Oil - Continuous Contract (EOD) CME",
                x=0.07,
                y=0.98,
            ),
            _observation("40 $WTIC (Daily) 57.20", x=0.02, y=0.70),
        ]
    )

    assert parsed["asset"]["value"] == "WTIC"
    assert parsed["asset"]["members"] == ["WTIC"]


def test_parse_header_does_not_promote_unstructured_body_ticker_over_mismatch() -> None:
    parsed = ocr.parse_header(
        [
            _observation("MS Morgan Stanley NYSE", x=0.02, y=0.97),
            _observation("$AAPL", x=0.02, y=0.50),
        ]
    )

    assert parsed["asset"]["value"] == "MS"
    assert parsed["asset"]["members"] == ["MS"]


def test_parse_header_does_not_promote_explicit_chart_body_comparison() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "XLB Materials Select Sector SPDR Fund NYSE", x=0.018, y=0.980
            ),
            _observation("40XLB (Daily) 44.34", x=0.020, y=0.947),
            _observation("$SPX", x=0.209, y=0.902),
        ]
    )

    assert parsed["asset"]["value"] == "XLB"
    assert parsed["asset"]["members"] == ["XLB"]
    assert parsed["timeframe"]["value"] == "daily"


def test_parse_header_collects_only_far_left_explicit_panel_headers() -> None:
    parsed = ocr.parse_header(
        [
            _observation("$TRAN Dow Jones Transportation Average INDX", y=0.983),
            _observation("40$TRAN (Weekly) 9133.75", y=0.955),
            _observation("A0 $INDU 21813.67", y=0.402),
            _observation("$SPX", x=0.209, y=0.902),
        ]
    )

    assert parsed["asset"]["value"] == "TRAN"
    assert parsed["asset"]["members"] == ["DJIA", "TRAN"]
    assert all("$SPX" not in item["text"] for item in parsed["asset"]["member_evidence"])


@pytest.mark.parametrize(
    ("title", "x", "y"),
    [
        (
            "$NDX:$INDU Nasdaq 100 Index/Dow Jones Industrial Average INDX",
            0.014,
            0.963,
        ),
        (
            "$NDX:$INDU Nasdaq 100 Index/Dow Jones Industrial Average INDX",
            0.062,
            0.965,
        ),
    ],
)
def test_parse_header_collects_explicit_colon_composite_members(
    title: str, x: float, y: float
) -> None:
    parsed = ocr.parse_header([_observation(title, x=x, y=y)])

    assert parsed["asset"]["value"] == "NDX"
    assert parsed["asset"]["members"] == ["DJIA", "NDX"]


@pytest.mark.parametrize(
    ("text", "x", "expected_members"),
    [
        ("$NDX:INDU Nasdaq/Dow INDX", 0.014, ["NDX"]),
        ("$NDX:$SPX Nasdaq/S&P INDX", 0.014, ["NDX", "SPX"]),
        ("Compare $NDX:$INDU leadership", 0.014, []),
        ("$NDX:$INDU", 0.20, ["NDX"]),
    ],
)
def test_parse_header_colon_composite_requires_two_explicit_far_left_members(
    text: str, x: float, expected_members: list[str]
) -> None:
    parsed = ocr.parse_header([_observation(text, x=x, y=0.963)])

    assert parsed["asset"]["members"] == expected_members


def test_parse_header_does_not_promote_colon_composite_from_chart_body() -> None:
    parsed = ocr.parse_header(
        [_observation("$NDX:$INDU leadership", x=0.02, y=0.50)]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["members"] == []


def test_parse_header_collects_numeric_dollar_header_from_lower_panel() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "SMH VanEck Vectors Semiconductor ETF NYSE",
                x=0.017778,
                y=0.982796,
            ),
            _observation("40 SMH (Daily) 106.60", x=0.020000, y=0.954839),
            _observation("90 $NDX 7450.83", x=0.020000, y=0.402151),
            _observation("$NDX Resumes Uptrend in", x=0.724444, y=0.210753),
        ]
    )

    assert parsed["asset"]["value"] == "SMH"
    assert parsed["asset"]["members"] == ["NDX", "SMH"]
    assert parsed["timeframe"]["value"] == "daily"


def test_parse_header_splits_letter_ticker_from_glued_decimal_quote() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "$COMPQ Nasdaq Composite INDX",
                x=0.033333,
                y=0.979798,
            ),
            _observation("40$COMPQ (Daily) 5444.50", x=0.037778, y=0.946970),
            _observation("90$SPX2259.53", x=0.037778, y=0.467172),
        ]
    )

    assert parsed["asset"]["value"] == "COMPQ"
    assert parsed["asset"]["members"] == ["COMPQ", "SPX"]
    assert parsed["timeframe"]["value"] == "daily"


def test_parse_header_collects_explicit_price_legend_from_lower_panel() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "$UST20Y 20-Year US Treasury Yield (EOD) INDX",
                x=0.014142,
                y=0.981735,
            ),
            _observation("$UST20Y (Weekly) 1.78 (29 Aug)", x=0.028283, y=0.952055),
            _observation(
                "* 20 Year US Tsy Yield Falls Below $SPX Yield",
                x=0.567677,
                y=0.876712,
            ),
            _observation("- $SPX 2915.39", x=0.018182, y=0.470320),
        ]
    )

    assert parsed["asset"]["value"] == "UST20Y"
    assert parsed["asset"]["members"] == ["SPX", "UST20Y"]
    assert parsed["timeframe"]["value"] == "weekly"


@pytest.mark.parametrize(
    ("lower_panel", "expected_members"),
    [
        (None, ["UST20Y"]),
        ("- $NDX 7450.83", ["NDX", "UST20Y"]),
    ],
)
def test_parse_header_lower_panel_legend_preserves_missing_or_wrong_member_evidence(
    lower_panel: str | None, expected_members: list[str]
) -> None:
    observations = [
        _observation(
            "$UST20Y 20-Year US Treasury Yield (EOD) INDX", x=0.014, y=0.982
        ),
        _observation("$UST20Y (Weekly) 1.78", x=0.028, y=0.952),
    ]
    if lower_panel is not None:
        observations.append(_observation(lower_panel, x=0.018, y=0.470))

    parsed = ocr.parse_header(observations)

    assert parsed["asset"]["value"] == "UST20Y"
    assert parsed["asset"]["members"] == expected_members


def test_parse_header_does_not_promote_bare_lower_panel_body_ticker() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "$UST20Y 20-Year US Treasury Yield (EOD) INDX", x=0.014, y=0.982
            ),
            _observation("$SPX", x=0.018, y=0.470),
        ]
    )

    assert parsed["asset"]["value"] == "UST20Y"
    assert parsed["asset"]["members"] == ["UST20Y"]


def test_parse_header_abstains_on_centered_bare_body_label() -> None:
    parsed = ocr.parse_header(
        [
            _observation("3,140", x=0.210948, y=0.972244),
            _observation("2,960", x=0.211027, y=0.946221),
            _observation("BCLX", x=0.351635, y=0.931497),
            _observation("S&P 500", x=0.093113, y=0.790541),
        ]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["members"] == []


@pytest.mark.parametrize("ticker", ["F", "S"])
def test_parse_header_keeps_far_left_bare_ticker_header(ticker: str) -> None:
    parsed = ocr.parse_header([_observation(ticker, x=0.02, y=0.97)])

    assert parsed["asset"]["value"] == ticker


@pytest.mark.parametrize("label", ["BCLX", "PSY", "AR", "ST", "SOS", "SOW"])
def test_parse_header_abstains_on_far_left_bare_multi_letter_label(
    label: str,
) -> None:
    parsed = ocr.parse_header([_observation(label, x=0.02, y=0.97)])

    assert parsed["asset"]["value"] == "unknown"


def test_parse_header_accepts_numeric_panel_series_but_not_body_prose() -> None:
    parsed = ocr.parse_header(
        [
            _observation("* $WTIC (Daily) 49.31", x=0.062, y=0.947),
            _observation("40 XLE 69.80", x=0.058, y=0.467),
            _observation("* XLE and WTIC Climax at same time", x=0.056, y=0.449),
        ]
    )

    assert parsed["asset"]["value"] == "WTIC"
    assert parsed["asset"]["members"] == ["WTIC", "XLE"]
    assert all("Climax" not in item["text"] for item in parsed["asset"]["member_evidence"])


def test_parse_header_accepts_longer_explicit_index_symbol_not_chart_label() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "$DJUSBT Dow Jones US Biotechnology Index INDX",
                x=0.016,
                y=0.980,
            ),
            _observation("BCLX", x=0.351, y=0.922),
            _observation("t #DJUSBT (Weekly) 1684.89", x=0.020, y=0.947),
        ]
    )

    assert parsed["asset"]["value"] == "DJUSBT"
    assert parsed["timeframe"]["value"] == "weekly"


def test_parse_header_keeps_real_s_prefixed_ticker_and_mismatch_signal() -> None:
    parsed = ocr.parse_header([_observation("SHOP Shopify Inc. NYSE")])

    assert parsed["asset"]["value"] == "SHOP"
    assert parsed["asset"]["value"] != "AAPL"


def test_parse_header_keeps_s_prefixed_index_without_duplicated_ocr_s() -> None:
    parsed = ocr.parse_header(
        [_observation("SPX S&P 500 Large Cap Index INDX", x=0.152, y=0.968)]
    )

    assert parsed["asset"]["value"] == "SPX"


def test_parse_header_abstains_on_unproven_duplicated_s_index_title() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "SSPX SSP 500 Large Cap Index NOX", x=0.068, y=0.959
            )
        ]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["members"] == []


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("SSYS Stratasys Ltd. NASDAQ GS", "SSYS"),
        ("S SentinelOne Inc. NYSE", "S"),
        ("SHOP Shopify Inc. NYSE", "SHOP"),
        ("SPX S&P 500 Large Cap Index INDX", "SPX"),
        ("$SSYS Stratasys Ltd. NASDAQ GS", "SSYS"),
    ],
)
def test_parse_header_preserves_genuine_s_prefixed_titles(
    title: str, expected: str
) -> None:
    parsed = ocr.parse_header([_observation(title, x=0.02, y=0.97)])

    assert parsed["asset"]["value"] == expected


def test_parse_header_prefers_market_title_over_slide_heading() -> None:
    parsed = ocr.parse_header(
        [
            _observation("V Two Way Markets", x=0.139, y=0.953),
            _observation("TGT Target Corp. NYSE", x=0.061, y=0.900),
            _observation(
                "18-Jan-2018, 12:11 ET, daily, O: 76.86", x=0.060, y=0.874
            ),
        ]
    )

    assert parsed["asset"]["value"] == "TGT"


def test_parse_header_abstains_on_suspicious_unreinforced_title_ocr() -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                "$GQILD Gold - Continuous Contract (EOD) CME",
                x=0.076,
                y=0.967,
            ),
            _observation(
                "27-Mar-2018, 14:30 ET, daily, O: 1,353.60",
                x=0.074,
                y=0.932,
            ),
        ]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["candidates"] == []
    assert parsed["asset"]["members"] == []


def test_parse_header_prefers_compact_primary_series_over_truncated_title() -> None:
    parsed = ocr.parse_header(
        [
            _observation("P Polaris Inds, Inc. NYSE", x=0.018, y=0.974),
            _observation("40PII (Weekly) 119.64", x=0.020, y=0.921),
        ]
    )

    assert parsed["asset"]["value"] == "PII"
    assert parsed["asset"]["members"] == ["PII"]
    assert parsed["timeframe"]["value"] == "weekly"


def test_parse_header_keeps_market_title_when_series_ocr_is_unrelated() -> None:
    parsed = ocr.parse_header(
        [
            _observation("GDX Market Vectors Gold Miners NYSE", x=0.018, y=0.980),
            _observation("40 GBW (Daily) 20.40 (7 Mar)", x=0.020, y=0.947),
        ]
    )

    assert parsed["asset"]["value"] == "GDX"
    assert parsed["asset"]["members"] == []
    assert parsed["timeframe"]["value"] == "daily"


@pytest.mark.parametrize(
    ("title", "series", "expected"),
    [
        ("F Ford Motor Co. NYSE", None, "F"),
        ("V Visa Inc. NYSE", "40V (Daily) 250.00", "V"),
        ("$GUILD Guild Holdings Co. NYSE", None, "GUILD"),
        ("$GOLD Gold - Continuous Contract (EOD) CME", None, "GOLD"),
        ("$SWTIC Light Crude Oil - Continuous Contract (EOD) CME", None, "SWTIC"),
        ("PIII PIII Holdings Inc. NYSE", "40PIII (Weekly) 10.00", "PIII"),
    ],
)
def test_parse_header_preserves_legitimate_short_and_similar_long_symbols(
    title: str, series: str | None, expected: str
) -> None:
    observations = [_observation(title, x=0.02, y=0.97)]
    if series is not None:
        observations.append(_observation(series, x=0.02, y=0.92))

    parsed = ocr.parse_header(observations)

    assert parsed["asset"]["value"] == expected


def test_parse_header_preserves_real_mismatch_evidence() -> None:
    parsed = ocr.parse_header(
        [
            _observation("MS Morgan Stanley NYSE", x=0.02, y=0.97),
            _observation("40MS (Daily) 100.00", x=0.02, y=0.92),
        ]
    )

    assert parsed["asset"]["value"] == "MS"
    assert parsed["asset"]["value"] != "AAPL"


@pytest.mark.parametrize(
    ("annotation", "x", "y", "timeframe"),
    [
        ("ST", 0.753333, 0.946970, "weekly"),
        ("LPSY", 0.891111, 0.916667, "monthly"),
    ],
)
def test_parse_header_ignores_right_side_wyckoff_annotations_as_assets(
    annotation: str, x: float, y: float, timeframe: str
) -> None:
    parsed = ocr.parse_header(
        [
            _observation(
                f"A0 $DJUSAR ({timeframe.title()}) 209.91",
                x=0.05,
                y=0.946970,
            ),
            _observation(annotation, x=x, y=y),
        ]
    )

    assert parsed["asset"]["value"] == "unknown"
    assert parsed["asset"]["candidates"] == []
    assert parsed["timeframe"]["value"] == timeframe


def test_merge_runs_decides_each_field_independently() -> None:
    first = ocr.parse_header(
        [_observation("AAPL Apple Inc."), _observation("40 AAPL (Daily)", y=0.84)]
    )
    second = ocr.parse_header(
        [_observation("AAPL Apple Inc."), _observation("40 AAPL (Weekly)", y=0.84)]
    )

    merged = ocr.merge_runs([first, second])

    assert merged["asset"]["value"] == "AAPL"
    assert merged["asset"]["decision_eligible"] is True
    assert merged["timeframe"]["value"] == "unknown"
    assert merged["timeframe"]["decision_eligible"] is False
    assert merged["timeframe"]["runs"] == ["daily", "weekly"]


def test_merge_runs_requires_stable_panel_member_set() -> None:
    first = ocr.parse_header(
        [_observation("$TRAN Transport INDX"), _observation("A0 $INDU 1", y=0.4)]
    )
    second = ocr.parse_header([_observation("$TRAN Transport INDX")])

    merged = ocr.merge_runs([first, second])

    assert merged["asset"]["value"] == "TRAN"
    assert merged["asset"]["decision_eligible"] is True
    assert merged["asset"]["members"] == []
    assert merged["asset"]["members_decision_eligible"] is False


def test_discover_fraser_images_uses_only_local_existing_extract_images(
    tmp_path: Path,
) -> None:
    kb_root = tmp_path / "research" / "expert-analyses"
    image = tmp_path / "raw" / "bruce_fraser" / "images" / "chart.png"
    _write(image, b"image")
    frontmatter = """---
source: raw/bruce_fraser/posts/article.md
image_path: raw/bruce_fraser/images/chart.png
---
"""
    _write(kb_root / "wiki" / "extracts" / "one.md", frontmatter)
    _write(kb_root / "wiki" / "extracts" / "duplicate.md", frontmatter)
    _write(
        kb_root / "wiki" / "extracts" / "remote.md",
        frontmatter.replace(
            "raw/bruce_fraser/images/chart.png", "(remote: https://example.com/chart.png)"
        ),
    )

    assert ocr.discover_fraser_images(kb_root, tmp_path) == [image]


def test_build_artifact_runs_each_image_twice_and_omits_declared_metadata(
    tmp_path: Path,
) -> None:
    image = tmp_path / "raw" / "bruce_fraser" / "images" / "chart.png"
    _write(image, b"image bytes")
    calls: list[Path] = []

    def observe(path: Path) -> list[dict]:
        calls.append(path)
        return [
            _observation("AAPL Apple Inc."),
            _observation("40 AAPL (Daily)", y=0.84),
        ]

    payload = ocr.build_artifact(
        [image], tmp_path, observe, toolchain={"system": "test"}
    )

    assert calls == [image, image]
    assert payload["schema"] == "fraser-header-ocr/v1"
    assert payload["generator"]["parser_version"] == 10
    assert payload["generator"]["runs_per_image"] == 2
    record = payload["images"][0]
    assert record["image_path"] == "raw/bruce_fraser/images/chart.png"
    assert record["sha256"] == hashlib.sha256(b"image bytes").hexdigest()
    assert record["asset"]["decision_eligible"] is True
    assert record["asset"]["members"] == ["AAPL"]
    assert record["asset"]["members_decision_eligible"] is True
    assert "declared" not in json.dumps(payload)
    assert "expected" not in json.dumps(payload)


def test_atomic_write_json_replaces_complete_payload(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "evidence.json"

    ocr.atomic_write_json(output, {"schema": ocr.SCHEMA_VERSION, "images": []})

    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == ocr.SCHEMA_VERSION
    assert list(output.parent.glob("*.tmp")) == []


def test_non_macos_preflight_is_unavailable_without_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(ocr.platform, "system", lambda: "Linux")

    result = ocr.main(["--kb-root", str(tmp_path), "--output", str(output)])

    assert result == 2
    assert not output.exists()
    assert "OCR_UNAVAILABLE" in capsys.readouterr().err


def test_missing_swiftc_is_unavailable_without_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(ocr.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)

    result = ocr.main(["--kb-root", str(tmp_path), "--output", str(output)])

    assert result == 2
    assert not output.exists()
    assert "OCR_UNAVAILABLE" in capsys.readouterr().err


def test_compile_failure_leaves_no_partial_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(ocr.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: "/usr/bin/swiftc")

    def fail_compile(_swiftc: str, _destination: Path) -> None:
        raise ocr.subprocess.CalledProcessError(1, ["swiftc"])

    monkeypatch.setattr(ocr, "compile_helper", fail_compile)

    result = ocr.main(["--kb-root", str(tmp_path), "--output", str(output)])

    assert result == 1
    assert not output.exists()
    assert "OCR generation failed" in capsys.readouterr().err
