"""Generator zamrznutih eval-snapshota u blind i future_visible modu.

Koristi get_ohlcv(end_time) za dohvat, deterministicku anonimizaciju
(neuobičajen cenovni opseg, bar-relativna x-osa), i piše snapshote u
data/eval/<case_id>/ sa answer key-em fizički van tog foldera u
data/eval/_answers/.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

from scripts.mcp.chart_renderer import EVAL_STYLE_VERSION, make_eval_style, render_chart_image


# Targets chosen to be clearly artificial and outside all recognizable crypto ranges:
# - not in BTC-like ~25k–55k band
# - not in known ETH (~137, ~1234), BNB, DOGE (~0.0042), SHIB (~0.0001) ranges
# - large enough that round(target/median_close, 8) never underflows to 0.0
#   even for BTC-like prices up to ~$100k (smallest target 0.314: 0.314/100000 = 3.14e-6 ≠ 0)
UNUSUAL_PRICE_TARGETS = [333.33, 9999.1, 88000.0, 0.00317, 555555.0, 0.314]
VOLUME_SCALE_FACTORS = [0.001, 10000.0, 0.00001, 50000.0, 0.1, 100000.0]
# Epoch 0 (1970-01-01 UTC) — clearly artificial, not recognizable as any market era
NEUTRAL_EPOCH_MS = 0
DAY_MS = 86_400_000

TIMEFRAME_MS: dict[str, int] = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

DEFAULT_BASE_DIR = Path("data/eval")


class SnapshotResult(TypedDict):
    case_dir: str
    candles_path: str
    chart_path: str
    answer_key_path: str
    mode: str
    case_id: str
    n_bars: int


def _case_index(case_id: str) -> int:
    digest = hashlib.sha256(case_id.encode()).hexdigest()
    return int(digest[:8], 16) % len(UNUSUAL_PRICE_TARGETS)


def anonymize(candles: list[dict], *, case_id: str) -> tuple[list[dict], dict]:
    """Return (anon_candles, coef_meta) with deterministic, unusual-range pricing.

    Same case_id + same input → identical bytes. Price median falls on an
    unusual target outside the ~25k–55k BTC-like range. open_time is remapped
    to a neutral monotonic bar index starting from epoch 0 (1970).
    """
    if not candles:
        raise ValueError("candles must be non-empty")
    closes = [float(c["close"]) for c in candles]
    median_close = statistics.median(closes)
    if median_close == 0:
        raise ValueError("median close price is zero — cannot compute price coefficient")

    idx = _case_index(case_id)
    price_target = UNUSUAL_PRICE_TARGETS[idx]
    price_coef = round(price_target / median_close, 8)
    if price_coef == 0:
        raise ValueError(
            f"price_coef rounded to zero for case_id={case_id!r} "
            f"(price_target={price_target}, median_close={median_close:.6g}); "
            "choose a larger price_target in UNUSUAL_PRICE_TARGETS"
        )
    volume_coef = round(VOLUME_SCALE_FACTORS[idx], 8)

    coef_meta = {
        "price_coef": price_coef,
        "volume_coef": volume_coef,
        "price_target": price_target,
    }
    return anonymize_with_meta(candles, coef_meta=coef_meta), coef_meta


def anonymize_with_meta(
    candles: list[dict],
    *,
    coef_meta: dict,
    start_index: int = 0,
) -> list[dict]:
    """Apply existing anonymization coefficients to another candle slice."""
    price_coef = float(coef_meta["price_coef"])
    volume_coef = float(coef_meta["volume_coef"])

    anon: list[dict] = []
    for offset, c in enumerate(candles):
        i = start_index + offset
        anon.append(
            {
                "open_time": NEUTRAL_EPOCH_MS + i * DAY_MS,
                "open": round(float(c["open"]) * price_coef, 4),
                "high": round(float(c["high"]) * price_coef, 4),
                "low": round(float(c["low"]) * price_coef, 4),
                "close": round(float(c["close"]) * price_coef, 4),
                "volume": round(float(c["volume"]) * volume_coef, 4),
            }
        )
    return anon


def passthrough_candles(candles: list[dict]) -> list[dict]:
    """Return candles in REAL space — used by reveal mode (no anonymization).

    Keeps the real ``open_time`` (no neutral-epoch remap) and real
    open/high/low/close/volume, rounded to 4 decimals to match the
    serialization width of the anon path. This is the identity-coefficient
    counterpart of :func:`anonymize_with_meta`.
    """
    if not candles:
        raise ValueError("candles must be non-empty")
    out: list[dict] = []
    for c in candles:
        out.append(
            {
                "open_time": int(c["open_time"]),
                "open": round(float(c["open"]), 4),
                "high": round(float(c["high"]), 4),
                "low": round(float(c["low"]), 4),
                "close": round(float(c["close"]), 4),
                "volume": round(float(c["volume"]), 4),
            }
        )
    return out


def render_eval_chart(
    anon_candles: list[dict],
    title: str = "ASSET-X",
    annotations: Any = None,
    output_dir: str | Path | None = None,
) -> dict:
    """Render eval chart with neutral style — no project-specific color fingerprints."""
    return render_chart_image(
        anon_candles,
        title=title,
        annotations=annotations,
        output_dir=str(output_dir) if output_dir is not None else None,
        style=make_eval_style(),
        style_key=EVAL_STYLE_VERSION,
    )


def _cutoff_to_ms(cutoff: int | str) -> int:
    if isinstance(cutoff, int):
        if cutoff <= 0:
            raise ValueError("cutoff must be a positive millisecond epoch")
        return cutoff
    raw = str(cutoff)
    if "T" not in raw and " " not in raw:
        raw = raw + "T00:00:00"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid cutoff value: {cutoff!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return int(parsed.timestamp() * 1000)


def build_snapshot(
    symbol: str,
    timeframe: str,
    cutoff: int | str,
    n_bars: int,
    mode: Literal["blind", "future_visible"],
    case_id: str,
    *,
    future_bars: int = 20,
    client: Any = None,
    ground_truth: str = "",
    answer_extra: dict[str, Any] | None = None,
    include_post_t_candles: bool = False,
    reveal: bool = False,
    base_dir: str | Path | None = None,
) -> SnapshotResult:
    """Build an eval snapshot in blind or future_visible mode.

    blind: fetches n_bars candles ending at cutoff; no future data visible.
    future_visible: fetches n_bars + future_bars candles ending at
        cutoff + future_bars*tf_ms; renders an "as-of T" vertical marker
        at candle index n_bars-1 and writes instruction.txt.

    reveal (anon vs revealed A/B control): when True the snapshot is NOT
        anonymized — real prices/volume and real open_time pass through
        (identity coefficients), the chart uses the recognizable default style
        with a ``<symbol> <TF>`` title, the case dir is suffixed ``__revealed``
        and the answer key is written to ``_answers/<case_id>__revealed.answer.json``
        so it never overwrites the anon key. post_t_candles are kept in real
        space. Default False preserves the full anonymized behavior.

    Answer key (real symbol, cutoff, coef_meta, ground_truth) is written to
    base_dir/_answers/<case_id>.answer.json (or ``<case_id>__revealed.answer.json``
    when reveal=True) — physically outside the case directory so an analyst
    given only the case dir cannot access it.

    Notes:
    - candles.json is deterministic for fixed inputs; chart.png bytes are NOT
      guaranteed deterministic across matplotlib versions or platforms (mplfinance
      renders non-deterministically), but the content is visually identical.
    - Paths in manifest.json are absolute; the manifest is not portable across
      machines. This is acceptable for single-developer eval workflow.
    - ground_truth is stored in the answer key file, not in the case directory.
      PROBE_CASES in lookahead_probe.py contain ground_truth in committed code —
      intentional for the probe phase (testing leak mechanics, not production eval).
    """
    if mode not in ("blind", "future_visible"):
        raise ValueError(f"mode must be 'blind' or 'future_visible', got {mode!r}")
    if reveal and mode == "future_visible":
        # The (future_visible, revealed) corner is intentionally not built — three
        # control angles suffice for both deltas (see benchmark.CONTROLS). Refuse
        # it loudly rather than silently emit a __revealed dir for it.
        raise ValueError(
            "reveal=True is not supported with mode='future_visible' "
            "(the future_visible+revealed corner is intentionally out of scope)"
        )

    tf_lower = timeframe.strip().lower()
    if tf_lower not in TIMEFRAME_MS:
        supported = ", ".join(TIMEFRAME_MS)
        raise ValueError(f"Unsupported timeframe {timeframe!r}; supported: {supported}")
    tf_ms = TIMEFRAME_MS[tf_lower]

    cutoff_ms = _cutoff_to_ms(cutoff)
    base = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR

    if client is None:
        from scripts.mcp.market_data_client import BinanceMarketDataClient  # noqa: PLC0415
        client = BinanceMarketDataClient()

    if mode == "blind":
        candles: list[dict] = client.get_ohlcv(symbol, timeframe, n_bars, end_time=cutoff_ms)
        if len(candles) < n_bars:
            raise ValueError(
                f"Expected {n_bars} candles for {case_id} blind "
                f"but got {len(candles)} — choose a later cutoff or reduce n_bars"
            )
        case_dir_name = case_id
        annotations: Any = None
        instruction: str | None = None
    else:
        end_time_fv = cutoff_ms + future_bars * tf_ms
        candles = client.get_ohlcv(
            symbol, timeframe, n_bars + future_bars, end_time=end_time_fv
        )
        if len(candles) < n_bars + future_bars:
            raise ValueError(
                f"Expected {n_bars + future_bars} candles for {case_id} future_visible "
                f"but got {len(candles)} — try a more recent cutoff or reduce n_bars/future_bars"
            )
        case_dir_name = f"{case_id}__fv"
        t_marker_index = n_bars - 1
        annotations = {
            "vertical_lines": [
                {"index": t_marker_index, "label": "as-of T", "color": "#888888"}
            ]
        }
        instruction = (
            "Analyze this chart as if the current time is at the vertical line marker "
            "(as-of T). Do NOT use candles to the right of the line — they are future "
            "data not available at T."
        )

    if reveal:
        # Revealed control: real prices/dates pass through, identity coefficients.
        anon_candles = passthrough_candles(candles)
        coef_meta = {"price_coef": 1.0, "volume_coef": 1.0, "price_target": None}
        case_dir_name = f"{case_id}__revealed"
    else:
        anon_candles, coef_meta = anonymize(candles, case_id=case_id)

    post_t_candles: list[dict] | None = None
    if include_post_t_candles:
        if mode == "future_visible":
            post_t_raw = candles[n_bars - 1 :]
        else:
            post_t_end = cutoff_ms + future_bars * tf_ms
            post_t_raw = client.get_ohlcv(
                symbol,
                timeframe,
                future_bars + 1,
                end_time=post_t_end,
            )
        expected_post_t = future_bars + 1
        if len(post_t_raw) < expected_post_t:
            raise ValueError(
                f"Expected {expected_post_t} post-T candles for {case_id} "
                f"but got {len(post_t_raw)} — choose an older cutoff or reduce future_bars"
            )
        if reveal:
            post_t_candles = passthrough_candles(post_t_raw[-expected_post_t:])
        else:
            post_t_candles = anonymize_with_meta(
                post_t_raw[-expected_post_t:],
                coef_meta=coef_meta,
                start_index=n_bars - 1,
            )

    case_dir = base / case_dir_name
    case_dir.mkdir(parents=True, exist_ok=True)

    candles_path = case_dir / "candles.json"
    candles_path.write_text(json.dumps(anon_candles, indent=2) + "\n")

    if reveal:
        # Recognizable default style + real symbol/TF title (the whole point of reveal).
        rendered = render_chart_image(
            anon_candles,
            title=f"{symbol} {tf_lower.upper()}",
            annotations=annotations,
            output_dir=case_dir,
        )
    else:
        rendered = render_eval_chart(anon_candles, "ASSET-X", annotations, output_dir=case_dir)
    chart_path = case_dir / "chart.png"
    Path(rendered["path"]).replace(chart_path)

    if instruction is not None:
        (case_dir / "instruction.txt").write_text(instruction + "\n")

    answers_dir = base / "_answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    answer_key_name = f"{case_id}__revealed.answer.json" if reveal else f"{case_id}.answer.json"
    answer_key_path = answers_dir / answer_key_name
    answer_key = {
        "case_id": case_id,
        "symbol": symbol,
        "cutoff": str(cutoff),
        "coef_meta": coef_meta,
        "ground_truth": ground_truth,
        "n_bars": n_bars,
    }
    if answer_extra:
        answer_key.update(answer_extra)
    if post_t_candles is not None:
        answer_key["post_t_candles"] = post_t_candles
    answer_key_path.write_text(json.dumps(answer_key, indent=2) + "\n")

    manifest_path = base / "manifest.json"
    manifest: dict = {"cases": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    entries: list[dict] = manifest.get("cases", [])
    entries = [
        e
        for e in entries
        if not (e["case_id"] == case_id and e["mode"] == mode and e.get("reveal", False) == reveal)
    ]
    entries.append(
        {
            "case_id": case_id,
            "mode": mode,
            "reveal": reveal,
            "n_bars": n_bars,
            "paths": {
                "candles": str(candles_path),
                "chart": str(chart_path),
            },
        }
    )
    manifest["cases"] = entries
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return {
        "case_dir": str(case_dir),
        "candles_path": str(candles_path),
        "chart_path": str(chart_path),
        "answer_key_path": str(answer_key_path),
        "mode": mode,
        "case_id": case_id,
        "n_bars": n_bars,
    }
