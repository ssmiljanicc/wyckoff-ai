import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "spikes" / "wiki_usage_cost.py"
SPEC = importlib.util.spec_from_file_location("wiki_usage_cost", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_price_attempt_separates_cached_and_uncached_and_uses_long_band() -> None:
    row = MODULE.price_attempt(
        {
            "label": "analyst__case__arm_b",
            "stage": "analyst",
            "attempt": 1,
            "accepted": True,
            "resolved_model": "gpt-5.6-luna",
            "effort": "xhigh",
            "duration_seconds": 12.5,
            "usage": {
                "input_tokens": 300_000,
                "cached_input_tokens": 200_000,
                "output_tokens": 10_000,
            },
        }
    )

    assert row["arm"] == "arm_b"
    assert row["context_band"] == "long"
    assert row["uncached_input_tokens"] == 100_000
    assert row["api_equivalent_cost_usd"] == pytest.approx(0.066)


def test_price_attempt_rejects_impossible_cached_usage() -> None:
    with pytest.raises(ValueError, match="Cached input exceeds input"):
        MODULE.price_attempt(
            {
                "label": "judge__case",
                "stage": "judge",
                "resolved_model": "gpt-5.6-sol",
                "usage": {"input_tokens": 10, "cached_input_tokens": 11},
            }
        )
