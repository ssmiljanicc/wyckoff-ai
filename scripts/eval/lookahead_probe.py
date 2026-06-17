"""Lookahead probe scaffold (Phase 2 gate).

Generates 2-3 known cases × 2 modes and writes a probe_result.json
template. The actual LLM analysis is a runbook step — this script only
prepares the cases; it does NOT call an LLM.

Run (with network):
    uv run --extra mcp python -m scripts.eval.lookahead_probe

Run (no network, stub client):
    uv run --extra mcp python -m scripts.eval.lookahead_probe --dry-run

Gate logic (runbook step):
    For each case: (a) run a blind analyst on the blind snapshot;
    (b) run the same analyst on the future_visible snapshot with the
    as-of T instruction; (c) check whether the FV analysis references
    events after T (leaked) and whether the score jumps; (d) fill
    blind_score/fv_score/fv_leaked/delta/decision in probe_result.json.

    Gate: delta≈0 and !leaked → blind-slicing unnecessary for Phase 3;
    workflow reduces to live end_time + as-of instruction (document the
    decision, do not build surplus snapshot machinery).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.eval.snapshot_builder import build_snapshot


PROBE_CASES = [
    {
        "case_id": "case_01",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2019-04-01",
        "n_bars": 180,
        "ground_truth": (
            "Late accumulation after Nov-2018 capitulation; Q1-2019 base. "
            "Markup breakout began 2019-04-02: BTC ran from ~$4.1k to ~$5.6k "
            "within days, then to ~$13.8k by Jun 2019."
        ),
    },
    {
        "case_id": "case_02",
        "symbol": "ETHUSDT",
        "timeframe": "1d",
        "cutoff": "2020-03-13",
        "n_bars": 180,
        "ground_truth": (
            "COVID capitulation low. ETH crashed to ~$100 on Mar 12-13 2020. "
            "Accumulation base formed; ETH recovered to ~$400+ by Aug 2020."
        ),
    },
    {
        "case_id": "case_03",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "cutoff": "2021-05-19",
        "n_bars": 180,
        "ground_truth": (
            "Mid-2021 distribution/markdown. BTC dropped from ~$60k to ~$30k "
            "in May 2021. Choppy re-accumulation through summer; new ATH ~$69k "
            "Nov 2021."
        ),
    },
]

BASE_DIR = Path("data/eval")


class _DryRunClient:
    """Stub returning fixed candles without any network calls."""

    def __init__(self) -> None:
        self.call_log: list[dict] = []

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: Any = None,
    ) -> list[dict]:
        self.call_log.append(
            {"symbol": symbol, "timeframe": timeframe, "limit": limit, "end_time": end_time}
        )
        price = 5000.0
        candles = []
        for i in range(limit):
            candles.append(
                {
                    "open_time": i * 86_400_000,
                    "open": price + i,
                    "high": price + i + 50,
                    "low": max(1.0, price + i - 50),
                    "close": price + i + 10,
                    "volume": 1000.0 + i * 5,
                    "close_time": (i + 1) * 86_400_000 - 1,
                    "quote_volume": (1000.0 + i * 5) * (price + i + 10),
                    "trades": 100,
                }
            )
        return candles


def run_probe(dry_run: bool = False) -> None:
    client: Any = _DryRunClient() if dry_run else None

    for case in PROBE_CASES:
        case_id = case["case_id"]
        print(f"\n[probe] {case_id} — blind...")
        build_snapshot(
            symbol=case["symbol"],
            timeframe=case["timeframe"],
            cutoff=case["cutoff"],
            n_bars=case["n_bars"],
            mode="blind",
            case_id=case_id,
            ground_truth=case["ground_truth"],
            client=client,
            base_dir=BASE_DIR,
        )
        print(f"[probe] {case_id} — future_visible...")
        build_snapshot(
            symbol=case["symbol"],
            timeframe=case["timeframe"],
            cutoff=case["cutoff"],
            n_bars=case["n_bars"],
            mode="future_visible",
            case_id=case_id,
            ground_truth=case["ground_truth"],
            client=client,
            base_dir=BASE_DIR,
        )

    answers_dir = BASE_DIR / "_answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    probe_result = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "cases": [
            {
                "case_id": case["case_id"],
                "blind_score": None,
                "fv_score": None,
                "fv_leaked": None,
                "delta": None,
                "decision": None,
            }
            for case in PROBE_CASES
        ],
        "_instructions": (
            "For each case: (a) run blind analyst (no context, no _answers access) "
            "on blind snapshot and record analysis; (b) run same analyst on "
            "future_visible snapshot with as-of T instruction; "
            "(c) check if FV analysis references events after T (fv_leaked); "
            "(d) compare quality scores (blind_score vs fv_score); "
            "(e) fill delta = fv_score - blind_score and set decision. "
            "Gate: delta≈0 and !fv_leaked → blinding not needed; workflow "
            "reduces to live end_time + as-of instruction for Phase 3."
        ),
    }
    result_path = answers_dir / "probe_result.json"
    result_path.write_text(json.dumps(probe_result, indent=2) + "\n")
    print(f"\n[probe] probe_result.json written to: {result_path}")

    if dry_run:
        print("[probe] dry-run complete — stub client used, no network calls made")
    else:
        print("[probe] Snapshots ready. Fill probe_result.json after running the analyst runbook.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lookahead probe scaffold")
    parser.add_argument("--dry-run", action="store_true", help="Use stub client (no network)")
    args = parser.parse_args()
    run_probe(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
