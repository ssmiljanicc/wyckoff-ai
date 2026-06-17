"""Pilot primer: anonimizovan, future-blind isečak za Wyckoff eval.

Thin wrapper oko snapshot_builder — demonstrira mehaniku bez sirovog httpx-a
ili hardkodovanih curljivih konstanti.

Run: uv run --extra mcp python -m scripts.eval.pilot_blind_slice
"""

from __future__ import annotations

from scripts.eval.snapshot_builder import build_snapshot

SYMBOL = "BTCUSDT"
TIMEFRAME = "1d"
CUTOFF = "2019-04-01"
N_BARS = 180
CASE_ID = "case_01"
GROUND_TRUTH = (
    "Late accumulation after Nov-2018 capitulation; Q1-2019 base. "
    "Markup breakout began 2019-04-02: BTC ran from ~$4.1k to ~$5.6k "
    "within days, then to ~$13.8k by Jun 2019."
)


def main() -> None:
    result = build_snapshot(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        cutoff=CUTOFF,
        n_bars=N_BARS,
        mode="blind",
        case_id=CASE_ID,
        ground_truth=GROUND_TRUTH,
    )
    print(f"chart:       {result['chart_path']}")
    print(f"candles:     {result['candles_path']} ({result['n_bars']} bars)")
    print(f"answer key (HIDDEN): {result['answer_key_path']}")


if __name__ == "__main__":
    main()
