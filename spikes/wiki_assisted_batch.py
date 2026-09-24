#!/usr/bin/env python3
"""Ten-case, physically isolated wiki-assisted Wyckoff A/B replication spike."""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import hashlib
import json
import os
import random
import re
import shlex
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import validate as validate_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval.runtime_adapters import CodexRuntimeAdapter, RuntimeRequest


MODEL = "gpt-5.6-sol"
EFFORT = "high"
MODEL_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
ALLOWED_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh"})
TIMEOUT_SECONDS = 1800
MAX_ATTEMPTS = 2
HARNESS_CONTRACT_VERSION = "wiki-assisted-batch-v8"
ANALYST_CONCURRENCY = 2
PROOF_DELTA_THRESHOLD = 0.03
PROOF_POSITIVE_CASES = 6
PROOF_ARM_MEAN_THRESHOLD = 0.50
KILL_ARM_MEAN_THRESHOLD = 0.40
ALIGNMENT_DIMENSIONS = (
    "structure",
    "phase",
    "key_events",
    "leading_scenario",
    "trigger",
    "invalidation",
    "alternative_scenario",
    "confidence",
)
PROCESS_DIMENSIONS = (
    "market_context",
    "relative_strength",
    "structure_control",
    "three_laws_price_volume",
    "cause_objective",
    "phase_events",
    "scenario_evidence",
    "trading_area_readiness",
    "trigger",
    "invalidation_stop",
    "target_reward_risk",
    "confidence_uncertainty",
)
PILOT_CASE_ID = "link_vol24_2020_06"
PILOT_TARGET_EXTRACT = "crypto_v24_07_back-up-to-the-edge-of-the-creek_link.md"
PILOT_ALLOWLIST = (
    "book_p229_sign-of-strength_es-weekly-reaccumulation.md",
    "book_p231_back-up-to-the-edge-of-the-creek_6b-8h.md",
    "crypto_v28_04_back-up-to-the-edge-of-the-creek_xtz.md",
    "crypto_v29_02_back-up-to-the-edge-of-the-creek_small-cap-index.md",
    "crypto_v31_05_sign-of-strength_atom.md",
    "crypto_v34_01_flat-reaction_btc.md",
    "crypto_v51_03_back-up-to-the-edge-of-the-creek_crv.md",
    "fraser_p016_img04_back-up-to-the-edge-of-the-creek_expe.md",
    "fraser_p046_img02_last-point-of-support_djia-30m.md",
    "fraser_p060_img02_back-up-to-the-edge-of-the-creek_djia-pnf.md",
    "fraser_p102_img02_back-up-to-the-edge-of-the-creek_tsla.md",
    "fraser_p200_img04_sign-of-strength_work-daily.md",
)
THEORY_BOOK_ALLOWLIST = tuple(f"book-chapter-{number:02d}.md" for number in range(1, 28))
TEMPORAL_TREATMENT_AUDIT = {
    "book_p229_sign-of-strength_es-weekly-reaccumulation.md": {
        "source": "raw/book/pages/page_229.md", "source_date": "2019-01-01", "date_basis": "book copyright year",
    },
    "book_p231_back-up-to-the-edge-of-the-creek_6b-8h.md": {
        "source": "raw/book/pages/page_231.md", "source_date": "2019-01-01", "date_basis": "book copyright year",
    },
    "fraser_p016_img04_back-up-to-the-edge-of-the-creek_expe.md": {
        "source": "raw/bruce_fraser/posts/articles-wyckoff-2015-08-when-termites-get-into-your-trends.md",
        "source_date": "2015-08-07", "date_basis": "source Date header",
    },
    "fraser_p046_img02_last-point-of-support_djia-30m.md": {
        "source": "raw/bruce_fraser/posts/articles-wyckoff-2016-04-wyckoff-buy-strategies.md",
        "source_date": "2016-04-15", "date_basis": "source Date header",
    },
    "fraser_p060_img02_back-up-to-the-edge-of-the-creek_djia-pnf.md": {
        "source": "raw/bruce_fraser/posts/articles-wyckoff-2016-07-point-and-figure-pie-in-the-sky.md",
        "source_date": "2016-07-22", "date_basis": "source Date header",
    },
    "fraser_p102_img02_back-up-to-the-edge-of-the-creek_tsla.md": {
        "source": "raw/bruce_fraser/posts/articles-wyckoff-2017-06-shorts-find-tsla-shocking.md",
        "source_date": "2017-06-10", "date_basis": "source Date header",
    },
}
FROZEN_TREATMENT_SHA256 = {
    "book_p229_sign-of-strength_es-weekly-reaccumulation.md":
        "ae042bc5a115159bb3c281e4c846a79dbb64288ea3023b909b68b3987671366c",
    "book_p231_back-up-to-the-edge-of-the-creek_6b-8h.md":
        "417c15f260b1c9f031a2908c35ad6347dbc4ac17be213e8bbdc419c4683ee8e8",
    "fraser_p016_img04_back-up-to-the-edge-of-the-creek_expe.md":
        "a0d2b9829aec797b07bbb5f6ccc60d0e31ed27eb002ca65173deaac8aeee2cc8",
    "fraser_p046_img02_last-point-of-support_djia-30m.md":
        "15529a50743cc53c42a16f156a632ab94c4387b21387114f27a5293f8868e840",
    "fraser_p060_img02_back-up-to-the-edge-of-the-creek_djia-pnf.md":
        "19e1e309219004731cf63aafd03de1e9d0ec554375562d14824a05a8e83d95c0",
    "fraser_p102_img02_back-up-to-the-edge-of-the-creek_tsla.md":
        "de2d94a26ebd8bb545fcce4443fd841c7fb0e9d918183002cfff0c76d6e5d202",
}

# Capability splits fixed before the valid run. Text not listed here remains one
# applicable fragment. Observable semantics are retained; unavailable chart
# overlays, raw price scale, benchmark and P&F evidence are excluded.
CLAIM_FRAGMENT_OVERRIDES: dict[str, list[dict[str, str]]] = {
    "btc_vol14_2020_03.c01": [
        {"status": "applicable", "text": "The market is in a consolidation."},
        {"status": "na", "text": "Price is retesting the specifically drawn ice line.", "capability_reason": "drawn_trendline_or_ice_absent"}],
    "btc_vol14_2020_03.c02": [
        {"status": "applicable", "text": "Failure to hold range resistance leads to a bearish downmove."},
        {"status": "na", "text": "The downmove objective is the raw $5,300 level.", "capability_reason": "raw_unconverted_price_target"}],
    "btc_vol14_2020_03.c03": [
        {"status": "applicable", "text": "Failure to hold range resistance activates the bearish scenario."},
        {"status": "na", "text": "The trigger is the specifically drawn ice line.", "capability_reason": "drawn_trendline_or_ice_absent"}],
    "btc_vol16_2020_04.c01": [
        {"status": "applicable", "text": "High-volume effort at the capitulation-bar top suggests at least a retest of that high."},
        {"status": "na", "text": "The capitulation-bar top is the raw $7,350 level.", "capability_reason": "raw_unconverted_price_level"}],
    "btc_vol16_2020_04.c04": [
        {"status": "applicable", "text": "Support failure implies short-term downside."},
        {"status": "na", "text": "The downside objective is the raw $5,600 level.", "capability_reason": "raw_unconverted_price_target"}],
    "btc_vol16_2020_04.c05": [
        {"status": "applicable", "text": "A quick rebound requires reconsidering the bearish bias."},
        {"status": "na", "text": "The rebound occurs on the specifically drawn upsloping support.", "capability_reason": "drawn_trendline_absent"}],
    "btc_vol22_2020_05.c03": [
        {"status": "applicable", "text": "The higher high is Upthrust Action in Phase B."},
        {"status": "na", "text": "The higher high occurs at the specifically drawn overbought trendline.", "capability_reason": "drawn_trendline_absent"}],
    "btc_vol22_2020_05.c04": [
        {"status": "applicable", "text": "A shakeout occurred."},
        {"status": "na", "text": "The shakeout reached the specifically drawn oversold trendline.", "capability_reason": "drawn_trendline_absent"}],
    "btc_vol22_2020_05.c05": [
        {"status": "applicable", "text": "Continued absorption supports an upside continuation scenario."},
        {"status": "na", "text": "The upside objective is the raw $11,000 level.", "capability_reason": "raw_unconverted_price_target"}],
    "btc_vol22_2020_05.c06": [
        {"status": "applicable", "text": "Continued signs of absorption are the condition for the upside scenario."},
        {"status": "na", "text": "That scenario is identified by the raw $11,000 objective.", "capability_reason": "raw_unconverted_price_target"}],
    "btc_vol27f_2020_07.c02": [
        {"status": "applicable", "text": "A break of nearby resistance confirms the potential spring setup."},
        {"status": "na", "text": "The breakout threshold is the raw $9,300 level.", "capability_reason": "raw_unconverted_price_level"}],
    "btc_vol27f_2020_07.c03": [
        {"status": "applicable", "text": "After the resistance break, quick upside acceleration is expected."},
        {"status": "na", "text": "The upside objective is the raw $10,000-$10,400 range.", "capability_reason": "raw_unconverted_price_target"}],
    "btc_vol27f_2020_07.c05": [
        {"status": "na", "text": "The potential spring is a very-low-risk intraday opportunity.", "capability_reason": "intraday_granularity_absent"}],
    "xtz_vol30_2020_08.c02": [
        {"status": "applicable", "text": "Price committed above a prior major high and is testing supply there."},
        {"status": "na", "text": "The prior high is identified by the calendar label February.", "capability_reason": "calendar_identity_absent"}],
    "trx_vol23_2020_05.c05": [
        {"status": "applicable", "text": "Local supply must be absorbed for price to advance."},
        {"status": "na", "text": "The supply is located in the specifically drawn red zone.", "capability_reason": "drawn_zone_absent"}],
    "btc_vol35_2020_09.c02": [
        {"status": "applicable", "text": "Emergent supply must be tested and upthrust risk remains relevant."},
        {"status": "na", "text": "The test is at the specifically drawn halfway point of the original selling zone.", "capability_reason": "drawn_zone_absent"}],
    "btc_vol43_2020_11.c02": [
        {"status": "applicable", "text": "The formation suggests upside continuation."},
        {"status": "na", "text": "The PnF objective provides room to the raw $18,000 level.", "capability_reason": "point_and_figure_and_raw_target_absent"}],
    "btc_vol43_2020_11.c04": [
        {"status": "applicable", "text": "The alternative scenario seeks a spring, then entry after its test or a resistance breakout."},
        {"status": "na", "text": "The spring is at the raw $15,500 level.", "capability_reason": "raw_unconverted_price_level"}],
    "btc_vol43_2020_11.c05": [
        {"status": "applicable", "text": "Pattern failure means renewed supply and a revisit of trading-range support."},
        {"status": "na", "text": "Trading-range support is the raw $14,300 level.", "capability_reason": "raw_unconverted_price_level"}],
}

BAR_DURATION_MS = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

ANALYST_PROMPT = """You are an isolated Wyckoff market analyst.

Your entire evidence universe is the current /workspace package. Do not use the
network, credentials, process metadata, environment variables, or paths outside
/workspace. Shell commands may inspect only files under /workspace.
The only permitted read-only inspection commands are ls, head, tail and cat.
Prefer cat and head. Do not use shell chaining,
redirection, substitutions, parent paths, or any other executable; doing so
invalidates the entire attempt.

Read input/metadata.json, then analyze input/candles.json as an anonymized OHLCV
series frozen at the decision cutoff. It contains no future bars. The metadata
contains only timeframe, bar count, bar duration, and whether the final bar is
complete. When final_bar_complete is false, the final OHLCV bar contains only
observations available by the cutoff; use final_bar_elapsed_fraction to avoid
treating its partial volume as a completed-bar total. First describe observed price/volume facts,
then assign Wyckoff labels. Read the 27 theory summaries directly under
knowledge/methodology. Follow the documented
Wyckoff decision sequence: context/timeframe; structure and control; observable
supply/demand plus effort/result; phase/events; leading and alternative scenarios
with confirming evidence; trading area/readiness; then entry trigger, invalidation
stop, target and reward:risk. Do not pretend to have relative-strength benchmark
data or a Point-and-Figure chart when the package supplies neither. If
knowledge/expert_examples exists, use its small fixed set of non-target examples
as analogical guidance without copying their conclusions.

Do not infer or name the asset, exchange, calendar date, arm, or provenance.
Return one leading scenario, one credible alternative, calibrated confidence,
and a trade_plan locked before future data is visible. A trade plan is either:
- enter_now: market entry at the next available bar/open after cutoff;
  entry_level records only the current final-close/reference level, not a future fill;
- wait_for_trigger: a stop/limit entry that remains pending until its stated
  numeric stop_loss is touched before entry or entry_expiry_bars elapses;
- no_trade: no entry, with null levels, null entry expiry, null holding horizon,
  and a concrete reason/cancellation rule.
For actionable plans, give normalized numeric entry, stop, target, and a 1-60
bar maximum holding horizon. wait_for_trigger also requires a 1-60 bar
entry_expiry_bars; enter_now and no_trade require null. cancellation_condition
must explain the same numeric stop/expiry logic, not add a free-text rule.
Same-bar pending entry and target touches are intrabar ambiguous and will be
replayed conservatively rather than automatically credited as a win. Levels
must be internally ordered for long/short.
Return only JSON matching analysis_output.schema.json.
"""

JUDGE_PROMPT = """You are a blind evaluator of two anonymized Wyckoff analyses.

Your entire evidence universe is /workspace. Do not use the network, future
market outcomes, or paths outside /workspace. Read process_rubric.json,
expert_ground_truth.json and both candidate JSON files. Never guess which experimental arm produced a
candidate. Candidate prices are anonymized and need not share the expert's
original scale; compare semantics and relative structure, not raw price numbers.
If shell inspection is needed, use only ls, head, tail or cat on relative paths
or /workspace paths, without chaining or expansion.
Any other command invalidates the entire attempt.

Use only the expert's explicit statements. Score every predeclared applicable item in
expert_claims independently; this claim-level score is the primary expert
agreement. Also produce the legacy eight-field compatibility view according to
applicable_alignment_dimensions. For an applicable compatibility dimension use
status "scored", integer 0-4 and rationale. For every unstated dimension use
status "na", score null, and say the expert did not state it. Never award
compatibility points for an unstated expert claim.

Separately assess adherence to the documented Wyckoff process using the frozen
definitions and experiment-specific anchors in process_rubric.json. This is analysis
quality, not expert agreement. wyckoff_process_applicability_by_candidate declares
which checks each input/decision can support. An honest no_trade makes trigger,
stop and target/R:R N/A rather than wrong. Unsupported relative-strength and Point-and-Figure
/ Cause-objective checks must be N/A, never rewarded or penalized.

For applicable dimensions: 4=excellent semantic match, 3=materially correct
with a minor gap, 2=mixed/partial, 1=mostly wrong, 0=absent or contradictory.
Keep process and trade-plan quality separate from expert alignment. Return only JSON
matching judge_output.schema.json.
"""

ANALYSIS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "observations", "structure", "phase", "key_events", "leading_scenario",
        "alternative_scenario", "confidence", "uncertainties", "trade_plan",
        "process_assessment",
    ],
    "properties": {
        "observations": {"type": "array", "minItems": 3, "items": {"type": "string"}},
        "structure": {"type": "string", "minLength": 1},
        "phase": {"type": "string", "minLength": 1},
        "key_events": {"type": "array", "items": {"type": "string"}},
        "leading_scenario": {"$ref": "#/$defs/scenario"},
        "alternative_scenario": {"$ref": "#/$defs/scenario"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "trade_plan": {"$ref": "#/$defs/trade_plan"},
        "process_assessment": {"$ref": "#/$defs/process_assessment"},
    },
    "$defs": {
        "scenario": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "direction", "thesis", "trigger_condition", "trigger_level",
                "invalidation_condition", "invalidation_level", "expected_path",
            ],
            "properties": {
                "direction": {"enum": ["up", "down", "none"]},
                "thesis": {"type": "string"},
                "trigger_condition": {"type": "string"},
                "trigger_level": {"type": ["number", "null"]},
                "invalidation_condition": {"type": "string"},
                "invalidation_level": {"type": ["number", "null"]},
                "expected_path": {"type": "string"},
            },
        },
        "trade_plan": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "action", "direction", "entry_type", "entry_level", "stop_loss",
                "take_profit", "entry_expiry_bars", "max_holding_bars",
                "cancellation_condition",
            ],
            "properties": {
                "action": {"enum": ["enter_now", "wait_for_trigger", "no_trade"]},
                "direction": {"enum": ["long", "short", "none"]},
                "entry_type": {"enum": ["market", "stop", "limit", "none"]},
                "entry_level": {"type": ["number", "null"]},
                "stop_loss": {"type": ["number", "null"]},
                "take_profit": {"type": ["number", "null"]},
                "entry_expiry_bars": {"type": ["integer", "null"], "minimum": 1, "maximum": 60},
                "max_holding_bars": {"type": ["integer", "null"], "minimum": 1, "maximum": 60},
                "cancellation_condition": {"type": "string", "minLength": 1},
            },
        },
        "process_assessment": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "context_timeframe", "structure_control", "supply_demand",
                "effort_result", "cause_effect", "trading_area_readiness",
                "reward_risk",
            ],
            "properties": {
                "context_timeframe": {"type": "string", "minLength": 1},
                "structure_control": {"type": "string", "minLength": 1},
                "supply_demand": {"type": "string", "minLength": 1},
                "effort_result": {"type": "string", "minLength": 1},
                "cause_effect": {"type": ["string", "null"]},
                "trading_area_readiness": {"type": "string", "minLength": 1},
                "reward_risk": {"type": "string", "minLength": 1},
            },
        },
    },
}


class LeakageError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_registry(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    if len(raw.get("cases", [])) != 10:
        raise RuntimeError("registry must contain exactly 10 cases")
    frozen = raw.get("frozen") is True or raw.get("status") == "frozen"
    validation = raw.get("validated") is True or raw.get("validation_status") == "passed"
    validation = validation or raw.get("validation", {}).get("status") == "passed"
    if not frozen or not validation:
        raise RuntimeError("registry is not explicitly frozen and validated")
    ids = [case["case_id"] for case in raw["cases"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate case ids in registry")
    for case in raw["cases"]:
        applicable = case.get("applicable_alignment_dimensions", [])
        if not applicable or not set(applicable).issubset(ALIGNMENT_DIMENSIONS):
            raise RuntimeError(f"invalid applicable dimensions for {case['case_id']}: {applicable}")
        labels = case["expert_labels"]
        for dimension in ALIGNMENT_DIMENSIONS:
            stated = labels.get(dimension) is not None
            if stated != (dimension in applicable):
                raise RuntimeError(
                    f"applicability mismatch for {case['case_id']} {dimension}: "
                    f"label={labels.get(dimension)!r}, applicable={dimension in applicable}"
                )
        claims = case.get("expert_claims", [])
        if not claims:
            raise RuntimeError(f"no explicit expert claims for {case['case_id']}")
        claim_ids = [claim.get("claim_id") for claim in claims]
        if any(not item for item in claim_ids) or len(claim_ids) != len(set(claim_ids)):
            raise RuntimeError(f"invalid/duplicate expert claim ids for {case['case_id']}")
        if any(not claim.get("text") or not claim.get("category") for claim in claims):
            raise RuntimeError(f"incomplete expert claim for {case['case_id']}")
        for claim in claims:
            _claim_capability_fragments(claim)
    return raw


def _claim_capability_fragments(claim: dict[str, Any]) -> list[dict[str, str]]:
    fragments = claim.get("capability_fragments")
    if fragments is None:
        fragments = CLAIM_FRAGMENT_OVERRIDES.get(claim["claim_id"], [{
            "status": "applicable", "text": claim["text"],
        }])
    if not isinstance(fragments, list) or not fragments:
        raise RuntimeError(
            f"capability_fragments must be a non-empty list for {claim['claim_id']}"
        )
    validated: list[dict[str, str]] = []
    for index, fragment in enumerate(fragments, start=1):
        if not isinstance(fragment, dict):
            raise RuntimeError(
                f"capability fragment {index} is not an object for {claim['claim_id']}"
            )
        status = fragment.get("status")
        text = fragment.get("text")
        reason = fragment.get("capability_reason")
        if status not in {"applicable", "na"}:
            raise RuntimeError(
                f"invalid capability fragment status for {claim['claim_id']}: {status!r}"
            )
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(
                f"empty capability fragment text for {claim['claim_id']} fragment {index}"
            )
        if status == "na" and (not isinstance(reason, str) or not reason.strip()):
            raise RuntimeError(
                f"N/A capability fragment requires capability_reason for {claim['claim_id']} "
                f"fragment {index}"
            )
        if reason is not None and not isinstance(reason, str):
            raise RuntimeError(
                f"invalid capability_reason for {claim['claim_id']} fragment {index}"
            )
        validated.append({
            "status": status,
            "text": text.strip(),
            **({"capability_reason": reason.strip()} if isinstance(reason, str) else {}),
        })
    return validated


def evaluation_registry_v2(registry: dict[str, Any], original_sha256: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in registry["cases"]:
        applicability: list[dict[str, Any]] = []
        applicable_claims: list[dict[str, str]] = []
        for claim in case["expert_claims"]:
            fragments = _claim_capability_fragments(claim)
            for index, fragment in enumerate(fragments, start=1):
                fragment_id = claim["claim_id"] if len(fragments) == 1 else f"{claim['claim_id']}.f{index:02d}"
                item = {
                    "claim_id": fragment_id,
                    "source_claim_id": claim["claim_id"],
                    "category": claim["category"],
                    "text": fragment["text"],
                    "status": fragment["status"],
                    "capability_reason": fragment.get("capability_reason"),
                }
                applicability.append(item)
                if item["status"] == "applicable":
                    applicable_claims.append({
                        "claim_id": fragment_id,
                        "source_claim_id": claim["claim_id"],
                        "category": claim["category"],
                        "text": fragment["text"],
                    })
        if not applicable_claims:
            raise RuntimeError(f"no capability-supported claims for {case['case_id']}")
        cases.append({
            **case,
            "original_expert_claims": case["expert_claims"],
            "expert_claims": applicable_claims,
            "expert_claim_applicability": applicability,
            "primary_claim_denominator": 4 * len(applicable_claims),
        })
    return {
        "schema_version": 2,
        "status": "frozen",
        "frozen": True,
        "validated": True,
        "validation_status": "passed",
        "source_registry_sha256": original_sha256,
        "capability_contract": {
            "available": ["anonymized_single_series_ohlcv", "first_close_100_relative_price_scale", "pre_t_median_volume_100_relative_scale", "timeframe_and_bar_duration"],
            "absent": ["asset_identity", "calendar_dates", "point_and_figure", "volume_profile", "drawn_trendline_or_ice", "broad_market_benchmark", "raw_price_scale"],
            "rule": "Split combined claims; score only observable fragments and retain unsupported fragments as N/A outside the denominator.",
        },
        "cases": cases,
    }


def freeze_evaluation_registry_v2(
    artifacts: Path, registry: dict[str, Any], original_sha256: str,
) -> tuple[dict[str, Any], str]:
    value = evaluation_registry_v2(registry, original_sha256)
    path = artifacts / "evaluation_registry_v2.json"
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text() != encoded:
        raise RuntimeError("frozen evaluation_registry_v2 differs from current capability rules")
    path.write_text(encoded)
    digest = sha256(path)
    counts = {
        case["case_id"]: {
            "applicable": len(case["expert_claims"]),
            "na": sum(item["status"] == "na" for item in case["expert_claim_applicability"]),
            "denominator": case["primary_claim_denominator"],
        }
        for case in value["cases"]
    }
    dump_json(artifacts / "evaluation_registry_v2_validation.json", {
        "status": "passed", "frozen": True, "sha256": digest,
        "source_registry_sha256": original_sha256, "case_count": len(value["cases"]),
        "counts_by_case": counts,
    })
    return value, digest


def process_rubric(case: dict[str, Any]) -> dict[str, Any]:
    definitions = {
        "market_context": {"definition": "Uses the supplied timeframe and single-instrument history to establish local context.", "evidence_bar": "States the relevant horizon/regime without claiming an absent broad-market view.", "source_basis": "Operational adaptation; not official broad-market Five-Step #1."},
        "relative_strength": {"definition": "Compares the instrument with a broad-market benchmark.", "evidence_bar": "Requires a benchmark series; otherwise N/A.", "source_basis": "Five-Step instrument selection/harmony."},
        "structure_control": {"definition": "Identifies range/trend structure and which side appears in control.", "evidence_bar": "Ties the conclusion to observable OHLCV swings.", "source_basis": "Villahermosa (2019) context-to-structure hierarchy, a modern Wyckoff-derived textbook rather than an official school script."},
        "three_laws_price_volume": {"definition": "Applies Supply/Demand and Effort-vs-Result to price/volume.", "evidence_bar": "Cites spread, volume and follow-through; does not imply a P&F Cause count.", "source_basis": "Three Laws; Cause/Effect is scored separately."},
        "cause_objective": {"definition": "Uses a defensible Cause/Effect objective supported by Point-and-Figure evidence.", "evidence_bar": "Requires P&F input; otherwise N/A.", "source_basis": "Five-Step sufficient Cause and Nine Tests objective."},
        "phase_events": {"definition": "Assigns phase/events only after reading context and structure.", "evidence_bar": "Labels are supported by observable sequence and volume behavior.", "source_basis": "Villahermosa (2019) hierarchy, modern Wyckoff-derived guidance."},
        "scenario_evidence": {"definition": "Provides leading and alternative scenarios with confirming evidence.", "evidence_bar": "Each scenario names observable confirming or disconfirming behavior.", "source_basis": "Experiment operationalization of conditional chart reading."},
        "trading_area_readiness": {"definition": "Distinguishes a valid trading area/setup from premature action.", "evidence_bar": "Explains readiness or why waiting/no-trade is appropriate.", "source_basis": "Villahermosa (2019) structure-to-trading-area hierarchy and Nine Tests readiness."},
        "trigger": {"definition": "Defines an actionable entry trigger.", "evidence_bar": "Numeric structured trigger for actionable plans; N/A for an honest no_trade decision.", "source_basis": "Villahermosa (2019) trigger step."},
        "invalidation_stop": {"definition": "Defines protective invalidation/stop for an actionable plan.", "evidence_bar": "Numeric structured stop with coherent ordering; N/A for no_trade.", "source_basis": "Five-Step timing/protection and Villahermosa (2019) stop step."},
        "target_reward_risk": {"definition": "Checks whether the experiment's OHLCV trade plan has a target and coherent reward:risk.", "evidence_bar": "Numeric target/R:R for actionable plans; N/A for no_trade. This is not proof of Nine Test #9 or a P&F objective.", "source_basis": "Experiment operational-plan check informed by reward:risk guidance."},
        "confidence_uncertainty": {"definition": "Calibrates confidence and names material missing evidence.", "evidence_bar": "Confidence matches uncertainty and absent capabilities are acknowledged.", "source_basis": "Experiment analysis-quality check."},
    }
    return {
        "status": "frozen",
        "warning": "The documented procedure is Wyckoff-derived; the 0-4 anchors are experiment-specific and not an official school grading rubric.",
        "documented_procedure": {
            "five_step": [
                "Assess market position and probable future trend.",
                "Select instruments in harmony with the market using relative strength when a benchmark exists.",
                "Verify sufficient Cause/objective when Point-and-Figure evidence exists.",
                "Assess readiness with direction-appropriate Buying/Selling Tests.",
                "Time commitment with the market turn and define protective stop and reward:risk.",
            ],
            "nine_tests_scope": "Direction-specific evidence includes objective, stopping action, volume/activity character, stride break, HH/HL or LH/LL, relative strength/weakness, base/crown and at least 3:1 reward:risk; absent inputs are N/A.",
            "three_laws": ["supply_and_demand", "cause_and_effect", "effort_vs_result"],
            "operational_hierarchy": ["context", "structure", "trading_area", "trigger", "stop_or_invalidation", "target"],
        },
        "sources": [
            "https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial (Five-Step Approach and Nine Tests; tutorial notes Hank Pruden adaptation)",
            "raw/bruce_fraser/posts/articles-wyckoff-2015-12-the-laws-of-wyckoff.md:9-39",
            "raw/book/pages/page_191.md:3-5", "raw/book/pages/page_195.md:5-23",
            "raw/book/pages/page_198.md:3-17", "raw/book/pages/page_212.md:3-15",
            "raw/book/pages/page_213.md:3-5", "raw/book/pages/page_214.md:3-23",
            "raw/book/pages/page_215.md:11-14", "raw/book/pages/page_216.md:8-19",
            "raw/book/pages/page_220.md:7-11", "raw/book/pages/page_221.md:7-14",
        ],
        "dimensions": list(PROCESS_DIMENSIONS),
        "dimension_definitions": definitions,
        "applicability": process_applicability(case),
        "candidate_specific_applicability": "trigger, invalidation_stop and target_reward_risk are N/A when that candidate chose no_trade; other case-level capability rules still apply.",
        "anchors": {
            "4": "Complete, evidence-grounded application with no material process gap.",
            "3": "Materially correct application with one minor gap.",
            "2": "Mixed or partial application with important omissions.",
            "1": "Mostly unsupported or incorrect application.",
            "0": "Absent or contradicted by the candidate analysis.",
            "na": "Input capability is absent or the candidate made a valid no_trade decision that makes the execution check inapplicable; exclude from the denominator.",
        },
    }


def process_applicability(case: dict[str, Any], trade_action: str | None = None) -> dict[str, bool]:
    capabilities = case.get("input_capabilities", {})
    actionable = trade_action != "no_trade"
    return {
        "market_context": True,
        "relative_strength": bool(capabilities.get("broad_market_benchmark", False)),
        "structure_control": True,
        "three_laws_price_volume": True,
        "cause_objective": bool(capabilities.get("point_and_figure", False)),
        "phase_events": True,
        "scenario_evidence": True,
        "trading_area_readiness": True,
        "trigger": actionable,
        "invalidation_stop": actionable,
        "target_reward_risk": actionable,
        "confidence_uncertainty": True,
    }


def normalize_repo_path(value: str) -> str:
    value = value.replace("\\", "/").lstrip("./")
    return value


def path_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(normalize_repo_path(value))
    elif isinstance(value, list):
        for item in value:
            found.extend(path_values(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "extract_path", "source_path", "image_path"}:
                found.extend(path_values(item))
            elif isinstance(item, (dict, list)):
                found.extend(path_values(item))
    return found


def build_union(registry: dict[str, Any]) -> dict[str, Any]:
    exact_paths: set[str] = set()
    markers: set[str] = {
        PILOT_CASE_ID.lower(),
        PILOT_TARGET_EXTRACT.lower(),
        "wyckoff-crypto-report-vol-24",
        "crypto_v24_",
        "chainlink",
        "linkusdt",
        "link/usd",
        "link/usdt",
    }
    base_asset_tokens: set[str] = {"LINK"}
    families: list[dict[str, Any]] = [{
        "case_id": PILOT_CASE_ID,
        "target_extract": PILOT_TARGET_EXTRACT,
        "source_family": "wyckoff-crypto-report-vol-24 / crypto_v24 / LINK",
    }]
    exact_paths.add(f"research/expert-analyses/wiki/extracts/{PILOT_TARGET_EXTRACT}")
    for case in registry["cases"]:
        case_paths = {normalize_repo_path(case["extract_path"])}
        case_paths.update(path_values(case.get("exclusion_family", {})))
        case_paths.update(path_values(case.get("source", {})))
        if case.get("image_path"):
            case_paths.add(normalize_repo_path(case["image_path"]))
        exact_paths.update(case_paths)
        source = case.get("source", {})
        market = case.get("market", {})
        marker_values = [
            case["case_id"], Path(case["extract_path"]).name,
            Path(case["extract_path"]).stem, source.get("path"), market.get("asset"),
            market.get("symbol"), Path(str(source.get("path", ""))).stem,
        ]
        for raw in marker_values:
            if not raw:
                continue
            text = str(raw).strip().lower()
            if text:
                markers.add(text)
        asset = str(market.get("asset", "")).strip()
        symbol = str(market.get("symbol", "")).strip().upper()
        if "/" in asset:
            base_asset_tokens.add(asset.split("/", 1)[0].upper())
        elif symbol:
            for quote in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH"):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    base_asset_tokens.add(symbol[:-len(quote)])
                    break
        families.append({
            "case_id": case["case_id"],
            "target_extract": case["extract_path"],
            "exact_paths": sorted(case_paths),
            "asset": market.get("asset"),
            "symbol": market.get("symbol"),
        })
    exact_paths.update(path_values(registry.get("cross_holdout_union_exclusions", [])))
    return {
        "exact_paths": sorted(exact_paths),
        "markers": sorted(markers),
        "base_asset_tokens": sorted(base_asset_tokens),
        "families": families,
    }


def marker_hits(relative: str, text: str, union: dict[str, Any]) -> list[str]:
    haystack = f"{relative.lower()}\n{text.lower()}"
    hits: list[str] = []
    for marker in union["markers"]:
        if marker and marker in haystack:
            hits.append(marker)
    for token in union.get("base_asset_tokens", []):
        if re.search(rf"\b{re.escape(token)}\b", f"{relative}\n{text}", re.I):
            hits.append(f"asset-family:{token}")
    # Short tickers need boundaries; registry curation supplies exact paths for ambiguous cases.
    if re.search(r"\bLINK(?:USDT|USD|BTC|/USD|/USDT|/BTC)?\b", text, re.I):
        hits.append("LINK asset family")
    return sorted(set(hits))


def file_repo_relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def select_treatment(repo: Path, union: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    extract_root = repo / "research/expert-analyses/wiki/extracts"
    selected: list[str] = []
    rejected: list[dict[str, Any]] = []
    exact = set(union["exact_paths"])
    earliest_cutoff = min(
        datetime.fromisoformat(case["market"]["cutoff"].replace("Z", "+00:00"))
        for case in registry["cases"]
    )
    for name, temporal in TEMPORAL_TREATMENT_AUDIT.items():
        path = extract_root / name
        rel = file_repo_relative(repo, path)
        text = path.read_text()
        reasons: list[str] = []
        source_date = datetime.fromisoformat(temporal["source_date"] + "T00:00:00+00:00")
        if source_date >= earliest_cutoff:
            reasons.append(f"source date {source_date.date()} is not before earliest cutoff {earliest_cutoff.date()}")
        if normalize_repo_path(temporal["source"]) not in text:
            reasons.append("extract provenance does not match temporal audit source")
        if rel in exact or name in exact:
            reasons.append("exact union exclusion")
        reasons.extend(marker_hits(rel, text, union))
        if reasons:
            rejected.append({"path": rel, "reasons": sorted(set(reasons))})
        else:
            selected.append(name)
    overlap = registry.get("fixed_treatment_overlap_check")
    if isinstance(overlap, dict) and overlap.get("status") not in {None, "passed", "pass", "clean"}:
        raise LeakageError(f"registry treatment overlap check did not pass: {overlap}")
    expected = list(FROZEN_TREATMENT_SHA256)
    if selected != expected:
        raise LeakageError(
            f"frozen six-file treatment corpus mismatch: expected={expected}, actual={selected}; "
            f"rejected={rejected}"
        )
    actual_hashes = {name: sha256(extract_root / name) for name in selected}
    if actual_hashes != FROZEN_TREATMENT_SHA256:
        raise LeakageError(
            "frozen treatment content hash mismatch: "
            f"expected={FROZEN_TREATMENT_SHA256}, actual={actual_hashes}"
        )
    return selected


def manifest_for(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise LeakageError(f"symlink forbidden: {path}")
        if path.is_file() and path.name != "allowlist_manifest.json":
            files.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            })
    return {"count": len(files), "total_bytes": sum(item["bytes"] for item in files), "files": files}


def package_fingerprint(root: Path) -> str:
    encoded = json.dumps(manifest_for(root), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def resolved_model(adapter: CodexRuntimeAdapter, requested_model: str) -> str:
    return getattr(adapter, "model_map", {}).get(requested_model, requested_model)


def stage_identity(
    adapter: CodexRuntimeAdapter, requested_model: str, effort: str,
) -> dict[str, str]:
    return {
        "requested_model": requested_model,
        "resolved_model": resolved_model(adapter, requested_model),
        "effort": effort,
    }


def result_namespace(
    stage: str, adapter: CodexRuntimeAdapter, requested_model: str, effort: str,
) -> str:
    identity = stage_identity(adapter, requested_model, effort)
    values = [stage, identity["requested_model"], identity["resolved_model"], effort]
    return "__".join(re.sub(r"[^A-Za-z0-9_.-]+", "-", value) for value in values)


def validate_runtime_choice(model: str, effort: str, stage: str) -> None:
    if MODEL_TOKEN_PATTERN.fullmatch(model) is None:
        raise RuntimeError(
            f"--{stage}-model must be a path-safe model token using only letters, "
            "digits, '.', '_' or '-'"
        )
    if effort not in ALLOWED_EFFORTS:
        allowed = ", ".join(sorted(ALLOWED_EFFORTS))
        raise RuntimeError(f"--{stage}-effort must be one of: {allowed}")


def call_contract(
    *, adapter: CodexRuntimeAdapter, package: Path, schema: Path, prompt: str,
    artifacts: Path, run_id: str, stage: str = "analyst",
    requested_model: str = MODEL, effort: str = EFFORT,
) -> dict[str, Any]:
    verdict = json.loads(adapter.verdict_path.read_text())
    identity = verdict["execution_identity"]
    return {
        "run_id": run_id,
        "stage": stage,
        "provider": "codex",
        **stage_identity(adapter, requested_model, effort),
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "harness_contract_version": HARNESS_CONTRACT_VERSION,
        "harness_source_sha256": sha256(Path(__file__)),
        "prompt_sha256": sha256_text(prompt),
        "schema_sha256": sha256(schema),
        "package_manifest_sha256": package_fingerprint(package),
        "treatment_corpus_sha256": sha256(artifacts / "treatment_corpus.json"),
        "runtime_image_id": identity["image_id"],
        "runtime_repo_digest": identity.get("repo_digest", ""),
        "runtime_cli_version": identity["cli_version"],
        "runtime_profile_fingerprint": verdict["profile_fingerprint"],
    }


def stable_run_id(
    analyst_adapter: CodexRuntimeAdapter, artifacts: Path, evaluation_registry_sha256: str,
    *, analyst_model: str = MODEL, analyst_effort: str = EFFORT,
    judge_adapter: CodexRuntimeAdapter | None = None,
    judge_model: str = MODEL, judge_effort: str = EFFORT,
) -> tuple[str, dict[str, Any]]:
    judge_adapter = judge_adapter or analyst_adapter

    def runtime_contract(
        adapter: CodexRuntimeAdapter, requested_model: str, effort: str,
    ) -> dict[str, str]:
        verdict = json.loads(adapter.verdict_path.read_text())
        identity = verdict["execution_identity"]
        return {
            **stage_identity(adapter, requested_model, effort),
            "runtime_image_id": identity["image_id"],
            "runtime_repo_digest": identity.get("repo_digest", ""),
            "runtime_cli_version": identity["cli_version"],
            "runtime_profile_fingerprint": verdict["profile_fingerprint"],
        }

    spec = {
        "stages": {
            "analyst": runtime_contract(analyst_adapter, analyst_model, analyst_effort),
            "judge": runtime_contract(judge_adapter, judge_model, judge_effort),
        },
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "harness_contract_version": HARNESS_CONTRACT_VERSION,
        "harness_source_sha256": sha256(Path(__file__)),
        "verdict_thresholds": {
            "proof_delta_b_minus_a": PROOF_DELTA_THRESHOLD,
            "proof_positive_case_count": PROOF_POSITIVE_CASES,
            "proof_arm_mean": PROOF_ARM_MEAN_THRESHOLD,
            "kill_arm_mean": KILL_ARM_MEAN_THRESHOLD,
            "kill_delta_b_minus_a_at_or_below": 0.0,
        },
        "analysis_prompt_sha256": sha256_text(ANALYST_PROMPT),
        "judge_prompt_sha256": sha256_text(JUDGE_PROMPT),
        "analysis_schema_sha256": sha256_text(json.dumps(ANALYSIS_SCHEMA, sort_keys=True, separators=(",", ":"))),
        "judge_schemas_sha256": sha256_text(json.dumps({
            case["case_id"]: judge_schema(
                ["candidate_cedar", "candidate_sable"],
                [claim["claim_id"] for claim in case["expert_claims"]],
            )
            for case in json.loads((artifacts / "evaluation_registry_v2.json").read_text())["cases"]
        }, sort_keys=True, separators=(",", ":"))),
        "evaluation_registry_sha256": evaluation_registry_sha256,
        "package_summary_sha256": sha256(artifacts / "package_summary.json"),
        "treatment_corpus_sha256": sha256(artifacts / "treatment_corpus.json"),
        "rubric_spec_sha256": sha256(artifacts / "rubric_spec.json"),
    }
    digest = sha256_text(json.dumps(spec, sort_keys=True, separators=(",", ":")))
    analyst_namespace = result_namespace(
        "analyst", analyst_adapter, analyst_model, analyst_effort,
    )
    judge_namespace = result_namespace("judge", judge_adapter, judge_model, judge_effort)
    return f"{analyst_namespace}__{judge_namespace}__{digest[:16]}", spec


def promote_build_to_run(artifacts: Path, run_id: str, run_spec: dict[str, Any]) -> Path:
    run_dir = artifacts / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    staging_packages = artifacts / "packages"
    target_packages = run_dir / "packages"
    if target_packages.exists():
        staged = {
            path.relative_to(staging_packages).as_posix(): sha256(path)
            for path in staging_packages.rglob("*") if path.is_file()
        }
        saved = {
            path.relative_to(target_packages).as_posix(): sha256(path)
            for path in target_packages.rglob("*") if path.is_file()
        }
        if staged != saved:
            raise RuntimeError("rebuilt packages differ from existing run namespace")
        shutil.rmtree(staging_packages)
    else:
        shutil.move(str(staging_packages), str(target_packages))
    for name in (
        "holdout_union.json", "treatment_corpus.json", "excluded_files.json",
        "package_summary.json", "leakage_control.json", "rubric_spec.json",
        "evaluation_registry_v2.json", "evaluation_registry_v2_validation.json",
    ):
        source = artifacts / name
        target = run_dir / name
        if target.is_file() and target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"frozen run support artifact changed: {name}")
        if not target.exists():
            shutil.copy2(source, target)
    source_transforms = artifacts / "_private/package_transforms"
    target_transforms = run_dir / "_private/package_transforms"
    if target_transforms.exists():
        source_hashes = {p.name: sha256(p) for p in source_transforms.glob("*.json")}
        target_hashes = {p.name: sha256(p) for p in target_transforms.glob("*.json")}
        if source_hashes != target_hashes:
            raise RuntimeError("private package transforms changed inside existing run")
    else:
        shutil.copytree(source_transforms, target_transforms)
    run_record = {"run_id": run_id, "status": "ready", "contract": run_spec}
    record_path = run_dir / "run_contract.json"
    if record_path.is_file() and json.loads(record_path.read_text()) != run_record:
        raise RuntimeError("run contract changed inside existing namespace")
    dump_json(record_path, run_record)
    return run_dir


def validate_package(root: Path, union: dict[str, Any]) -> dict[str, Any]:
    allowed = {"input", "knowledge", "prompt.txt", "analysis_output.schema.json", "allowlist_manifest.json"}
    for child in root.iterdir():
        if child.name not in allowed:
            raise LeakageError(f"non-allowlisted top-level package path: {child.name}")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise LeakageError("symlink in package")
    methodology_paths = {
        path.relative_to(root).as_posix()
        for path in (root / "knowledge/methodology").rglob("*") if path.is_file()
    }
    expected_methodology = {f"knowledge/methodology/{name}" for name in THEORY_BOOK_ALLOWLIST}
    if methodology_paths != expected_methodology:
        raise LeakageError(
            f"theory allowlist mismatch: missing={sorted(expected_methodology - methodology_paths)}, "
            f"extra={sorted(methodology_paths - expected_methodology)}"
        )
    forbidden_names = {".git", "answer", "ground_truth", "post_t", "future", "raw", "image", "log", "index"}
    for path in root.rglob("*"):
        if not path.is_file() or path.name == "allowlist_manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        lowered_parts = {part.lower() for part in path.relative_to(root).parts}
        if lowered_parts & forbidden_names:
            raise LeakageError(f"forbidden path class in package: {relative}")
        if path.suffix.lower() in {".md", ".txt", ".json"}:
            text = path.read_text(errors="replace")
            hits = [] if relative in expected_methodology else marker_hits(relative, text, union)
            if hits:
                raise LeakageError(f"holdout marker in {relative}: {hits}")
    expected = json.loads((root / "allowlist_manifest.json").read_text())
    actual = manifest_for(root)
    if expected != actual:
        raise LeakageError("allowlist manifest mismatch")
    return actual


def copy_theory_book(
    repo: Path, destination: Path, exclusions: list[dict[str, Any]], layer: str,
) -> int:
    source = repo / "knowledge/wiki/sources/book"
    allowed = set(THEORY_BOOK_ALLOWLIST)
    for path in sorted((repo / "knowledge/wiki").rglob("*")):
        if not path.is_file():
            continue
        repo_rel = file_repo_relative(repo, path)
        if path.parent == source and path.name in allowed:
            continue
        exclusions.append({
            "layer": layer,
            "path": repo_rel,
            "reasons": ["not in strict 27-file theory book allowlist"],
        })
    actual = {path.name for path in source.glob("book-chapter-*.md")}
    if not allowed.issubset(actual):
        raise LeakageError(f"missing theory book summaries: {sorted(allowed - actual)}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(allowed):
        shutil.copy2(source / name, destination / name)
    copied = {path.name for path in destination.iterdir() if path.is_file()}
    if copied != allowed:
        raise LeakageError(f"copied theory allowlist mismatch: {sorted(copied)}")
    return len(copied)


def resolve_candles(case: dict[str, Any], source_root: Path, artifacts: Path) -> tuple[str, Any, str]:
    del artifacts  # Candle evidence is allowed only from the frozen source root or registry.
    resolved_source_root = source_root.resolve()
    candidate_values = [
        case.get("input_candles_path"), case.get("candles_path"),
        case.get("market", {}).get("input_candles_path"),
    ]
    candidate_paths: list[Path] = []
    for value in candidate_values:
        if value:
            raw = Path(value)
            candidate_paths.append(raw if raw.is_absolute() else resolved_source_root / raw)
    case_id = case["case_id"]
    candidate_paths.extend([
        resolved_source_root / "case_data" / case_id / "candles.json",
        resolved_source_root / "cases" / case_id / "candles.json",
        resolved_source_root / "data/eval/benchmark" / case_id / "candles.json",
    ])
    for path in candidate_paths:
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(resolved_source_root):
            raise LeakageError(
                f"pre-T candle path escapes source_root for {case_id}: {path}"
            )
        if resolved_path.is_file():
            return (
                str(resolved_path), json.loads(resolved_path.read_text()), sha256(resolved_path),
            )
    embedded = case.get("candles") or case.get("pre_t_candles")
    if embedded is not None:
        encoded = json.dumps(embedded, indent=2, sort_keys=True).encode()
        return ("embedded:registry", embedded, hashlib.sha256(encoded).hexdigest())
    raise FileNotFoundError(f"no pre-T candles for {case_id}; tried {[str(p) for p in candidate_paths]}")


def copy_filtered_tree(
    repo: Path,
    source: Path,
    destination: Path,
    union: dict[str, Any],
    exclusions: list[dict[str, Any]],
    layer: str,
    selected_names: set[str] | None = None,
) -> int:
    count = 0
    exact = set(union["exact_paths"])
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise LeakageError(f"symlink in source tree: {path}")
        if not path.is_file() or path.name == ".gitkeep":
            continue
        repo_rel = file_repo_relative(repo, path)
        rel = path.relative_to(source)
        reasons: list[str] = []
        if selected_names is not None and path.name not in selected_names:
            reasons.append("not in fixed treatment corpus")
        if repo_rel in exact or rel.as_posix() in exact or path.name in exact:
            reasons.append("union exact exclusion")
        text = path.read_text(errors="replace")
        reasons.extend(f"union marker: {hit}" for hit in marker_hits(repo_rel, text, union))
        if path.name.lower() in {"index.md", "log.md"}:
            reasons.append("derived index/log excluded")
        if reasons:
            exclusions.append({"layer": layer, "path": repo_rel, "reasons": sorted(set(reasons))})
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def build_packages(repo: Path, source_root: Path, registry: dict[str, Any], artifacts: Path) -> dict[str, Any]:
    union = build_union(registry)
    treatment = select_treatment(repo, union, registry)
    packages_root = artifacts / "packages"
    if packages_root.exists():
        shutil.rmtree(packages_root)
    exclusions: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for case in registry["cases"]:
        case_id = case["case_id"]
        summaries[case_id] = {}
        candle_source, candles, candle_source_hash = resolve_candles(case, source_root, artifacts)
        expected_hash = case.get("ohlcv_validation", {}).get("input_sha256")
        if expected_hash != candle_source_hash:
            raise LeakageError(
                f"frozen candle hash mismatch for {case_id}: registry={expected_hash}, actual={candle_source_hash}"
            )
        expected_count = case.get("ohlcv_validation", {}).get("pre_t_count")
        if not isinstance(candles, list) or len(candles) != expected_count:
            raise LeakageError(
                f"frozen candle count mismatch for {case_id}: registry={expected_count}, actual={len(candles) if isinstance(candles, list) else 'not-list'}"
            )
        timeframe = case["market"]["timeframe"]
        if timeframe not in BAR_DURATION_MS:
            raise LeakageError(f"unsupported timeframe for anonymized metadata: {timeframe}")
        bar_duration = BAR_DURATION_MS[timeframe]
        final_bar_complete = case.get("market", {}).get("final_bar_complete", True)
        final_bar_elapsed_fraction = case.get("market", {}).get(
            "final_bar_elapsed_fraction", 1.0,
        )
        if not isinstance(final_bar_complete, bool):
            raise LeakageError(f"invalid final_bar_complete for {case_id}")
        if (
            not isinstance(final_bar_elapsed_fraction, (int, float))
            or isinstance(final_bar_elapsed_fraction, bool)
            or not 0 < float(final_bar_elapsed_fraction) <= 1
            or (final_bar_complete and float(final_bar_elapsed_fraction) != 1.0)
            or (not final_bar_complete and float(final_bar_elapsed_fraction) >= 1.0)
        ):
            raise LeakageError(f"invalid final_bar_elapsed_fraction for {case_id}")
        price_reference = float(candles[0]["close"])
        positive_volumes = [float(candle["volume"]) for candle in candles if float(candle["volume"]) > 0]
        if price_reference <= 0 or not positive_volumes:
            raise LeakageError(f"cannot normalize non-positive reference for {case_id}")
        volume_reference = float(statistics.median(positive_volumes))
        price_multiplier = 100.0 / price_reference
        volume_multiplier = 100.0 / volume_reference
        packaged_candles = []
        for index, candle in enumerate(candles):
            packaged_candles.append({
                **candle,
                "open_time": index * bar_duration,
                **{key: round(float(candle[key]) * price_multiplier, 8) for key in ("open", "high", "low", "close")},
                "volume": round(float(candle["volume"]) * volume_multiplier, 8),
            })
        if any(
            packaged_candles[index]["open_time"] - packaged_candles[index - 1]["open_time"] != bar_duration
            for index in range(1, len(packaged_candles))
        ):
            raise LeakageError(f"packaged candle duration mismatch for {case_id}")
        packaged_candle_sha = sha256_text(json.dumps(packaged_candles, indent=2, sort_keys=True) + "\n")
        dump_json(artifacts / "_private/package_transforms" / f"{case_id}.json", {
            "case_id": case_id,
            "price_scale": "first_close_100",
            "price_reference": price_reference,
            "price_multiplier": price_multiplier,
            "volume_scale": "pre_t_median_volume_100",
            "volume_reference": volume_reference,
            "volume_multiplier": volume_multiplier,
            "round_decimals": 8,
            "timeframe": timeframe,
            "bar_duration_ms": bar_duration,
            "source_input_sha256": candle_source_hash,
            "packaged_input_sha256": packaged_candle_sha,
        })
        for arm in ("arm_a", "arm_b"):
            root = packages_root / case_id / arm
            (root / "input").mkdir(parents=True, exist_ok=True)
            dump_json(root / "input/candles.json", packaged_candles)
            metadata = {
                "timeframe": timeframe,
                "bar_count": len(candles),
                "bar_duration": BAR_DURATION_MS[timeframe],
                "bar_duration_unit": "milliseconds",
                "final_bar_complete": final_bar_complete,
                "final_bar_elapsed_fraction": round(float(final_bar_elapsed_fraction), 8),
            }
            if any(key in metadata for key in ("asset", "symbol", "date", "cutoff", "source")):
                raise LeakageError("analyst metadata contains identifying or temporal fields")
            dump_json(root / "input/metadata.json", metadata)
            (root / "prompt.txt").write_text(ANALYST_PROMPT)
            dump_json(root / "analysis_output.schema.json", ANALYSIS_SCHEMA)
            methodology_count = copy_theory_book(
                repo, root / "knowledge/methodology", exclusions,
                f"{case_id}:{arm}:methodology",
            )
            expert_count = 0
            if arm == "arm_b":
                expert_count = copy_filtered_tree(
                    repo, repo / "research/expert-analyses/wiki/extracts",
                    root / "knowledge/expert_examples", union, exclusions,
                    f"{case_id}:{arm}:expert_examples", set(treatment),
                )
                if expert_count != len(treatment):
                    raise LeakageError(f"treatment corpus changed for {case_id}: {expert_count} != {len(treatment)}")
            manifest = manifest_for(root)
            dump_json(root / "allowlist_manifest.json", manifest)
            validate_package(root, union)
            summaries[case_id][arm] = {
                "candles_source": candle_source,
                "source_candles_sha256": candle_source_hash,
                "packaged_candles_sha256": packaged_candle_sha,
                "methodology_files": methodology_count,
                "expert_example_files": expert_count,
                "manifest": manifest,
            }
        common_a = {
            item["path"]: item["sha256"] for item in summaries[case_id]["arm_a"]["manifest"]["files"]
            if not item["path"].startswith("knowledge/expert_examples/")
        }
        common_b = {
            item["path"]: item["sha256"] for item in summaries[case_id]["arm_b"]["manifest"]["files"]
            if not item["path"].startswith("knowledge/expert_examples/")
        }
        if common_a != common_b:
            raise LeakageError(f"common bytes differ across arms for {case_id}")
    canary_tests: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="wiki-batch-leak-") as raw:
        fixture_root = Path(raw)
        for case in registry["cases"]:
            case_id = case["case_id"]
            source = case.get("source", {})
            market = case.get("market", {})
            injected_markers = [
                case_id,
                Path(case["extract_path"]).name,
                Path(case["extract_path"]).stem,
                str(source.get("path", "")),
                str(market.get("asset", "")),
                str(market.get("symbol", "")),
            ]
            injected_markers = [item for item in injected_markers if item]
            injected = fixture_root / case_id / "package"
            shutil.copytree(packages_root / case_id / "arm_b", injected)
            fixture_relative = "knowledge/expert_examples/leak_fixture.md"
            fixture = injected / fixture_relative
            fixture.write_text("intentional holdout-family leak\n" + "\n".join(injected_markers))
            dump_json(injected / "allowlist_manifest.json", manifest_for(injected))
            try:
                validate_package(injected, union)
            except LeakageError as exc:
                rejection = str(exc)
                if case_id.lower() not in rejection.lower():
                    raise LeakageError(
                        f"canary for {case_id} was rejected without detecting its case marker: {exc}"
                    ) from exc
                canary_tests.append({
                    "case_id": case_id,
                    "fixture_path": fixture_relative,
                    "injected_markers": injected_markers,
                    "rejection": rejection,
                    "status": "passed",
                })
            else:
                raise LeakageError(f"intentional leakage fixture was accepted for {case_id}")
    leak_control = {
        "status": "passed",
        "canary_count": len(canary_tests),
        "expected_canary_count": len(registry["cases"]),
        "tests": canary_tests,
    }
    dump_json(artifacts / "holdout_union.json", union)
    earliest_cutoff = min(case["market"]["cutoff"] for case in registry["cases"])
    dump_json(artifacts / "treatment_corpus.json", {
        "selected": treatment,
        "count": len(treatment),
        "sha256_by_file": {name: FROZEN_TREATMENT_SHA256[name] for name in treatment},
        "earliest_holdout_cutoff": earliest_cutoff,
        "temporal_safety_rule": "Every fixed treatment source predates the earliest holdout cutoff.",
        "temporal_audit": {name: TEMPORAL_TREATMENT_AUDIT[name] for name in treatment},
        "post_cutoff_examples_excluded": sorted(set(PILOT_ALLOWLIST) - set(treatment)),
    })
    dump_json(artifacts / "excluded_files.json", exclusions)
    dump_json(artifacts / "package_summary.json", summaries)
    dump_json(artifacts / "leakage_control.json", leak_control)
    dump_json(artifacts / "rubric_spec.json", {
        "primary_metric": {
            "name": "explicit expert claim alignment",
            "method": "Each source-anchored explicit claim is scored 0-4; numerator=sum(scores), denominator=4*claim_count.",
            "claims_by_case": {case["case_id"]: case["expert_claims"] for case in registry["cases"]},
        },
        "secondary_metric": {
            "name": "legacy eight-field compatibility",
            "warning": "Experiment-specific compatibility view, not an official Wyckoff 32-point rubric.",
            "dimensions": list(ALIGNMENT_DIMENSIONS),
            "rule": "Only expert-explicit dimensions are scored; every other dimension is N/A and excluded.",
        },
        "wyckoff_process_metric": {
            "name": "documented process adherence",
            "warning": "The 0-4 operational scoring scale is experiment-specific; the source procedure is not a numeric school grading rubric.",
            "dimensions": list(PROCESS_DIMENSIONS),
            "applicability_by_case": {case["case_id"]: process_applicability(case) for case in registry["cases"]},
            "local_sources": [
                "raw/bruce_fraser/posts/articles-wyckoff-2015-12-the-laws-of-wyckoff.md:9-39",
                "raw/book/pages/page_191.md:3-5",
                "raw/book/pages/page_195.md:5-23",
                "raw/book/pages/page_198.md:3-17",
                "raw/book/pages/page_212.md:3-15",
                "raw/book/pages/page_213.md:3-5",
                "raw/book/pages/page_214.md:3-23",
                "raw/book/pages/page_215.md:11-14",
                "raw/book/pages/page_216.md:8-19",
                "raw/book/pages/page_220.md:7-11",
                "raw/book/pages/page_221.md:7-14",
            ],
        },
    })
    return summaries


def validate_trade_plan(output: dict[str, Any]) -> None:
    plan = output["trade_plan"]
    action = plan["action"]
    if action == "no_trade":
        if plan["direction"] != "none" or plan["entry_type"] != "none":
            raise ValueError("no_trade must use none direction and entry type")
        if any(
            plan[key] is not None
            for key in ("entry_level", "stop_loss", "take_profit", "entry_expiry_bars", "max_holding_bars")
        ):
            raise ValueError("no_trade numeric fields and horizons must be null")
        return
    if plan["direction"] not in {"long", "short"}:
        raise ValueError("actionable trade must use long or short direction")
    if action == "enter_now" and plan["entry_type"] != "market":
        raise ValueError("enter_now must use market entry_type")
    if action == "enter_now" and plan["entry_expiry_bars"] is not None:
        raise ValueError("enter_now entry_expiry_bars must be null")
    if action == "wait_for_trigger" and plan["entry_type"] not in {"stop", "limit"}:
        raise ValueError("wait_for_trigger must use stop or limit entry_type")
    if action == "wait_for_trigger" and not isinstance(plan["entry_expiry_bars"], int):
        raise ValueError("wait_for_trigger requires integer entry_expiry_bars")
    if not isinstance(plan["max_holding_bars"], int):
        raise ValueError("actionable trade requires integer max_holding_bars")
    entry = float(plan["entry_level"])
    stop = float(plan["stop_loss"])
    target = float(plan["take_profit"])
    if plan["direction"] == "long" and not stop < entry < target:
        raise ValueError(f"long levels not ordered: stop={stop}, entry={entry}, target={target}")
    if plan["direction"] == "short" and not target < entry < stop:
        raise ValueError(f"short levels not ordered: target={target}, entry={entry}, stop={stop}")


def judge_schema(candidate_ids: list[str], claim_ids: list[str]) -> dict[str, Any]:
    dimension = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "score", "rationale"],
        "properties": {
            "status": {"enum": ["scored", "na"]},
            "score": {"type": ["integer", "null"], "minimum": 0, "maximum": 4},
            "rationale": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array", "minItems": 2, "maxItems": 2,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": [
                        "candidate_id", "expert_claims", "compatibility_dimensions",
                        "wyckoff_process", "analysis_quality_comment", "trade_plan_comment",
                    ],
                    "properties": {
                        "candidate_id": {"enum": candidate_ids},
                        "expert_claims": {
                            "type": "array", "minItems": len(claim_ids), "maxItems": len(claim_ids),
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "required": ["claim_id", "score", "rationale"],
                                "properties": {
                                    "claim_id": {"enum": claim_ids},
                                    "score": {"type": "integer", "minimum": 0, "maximum": 4},
                                    "rationale": {"type": "string"},
                                },
                            },
                        },
                        "compatibility_dimensions": {
                            "type": "object", "additionalProperties": False,
                            "required": list(ALIGNMENT_DIMENSIONS),
                            "properties": {name: dimension for name in ALIGNMENT_DIMENSIONS},
                        },
                        "wyckoff_process": {
                            "type": "object", "additionalProperties": False,
                            "required": list(PROCESS_DIMENSIONS),
                            "properties": {name: dimension for name in PROCESS_DIMENSIONS},
                        },
                        "analysis_quality_comment": {"type": "string"},
                        "trade_plan_comment": {"type": "string"},
                    },
                },
            }
        },
    }


def parse_event_stream(stdout: str) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    usage: dict[str, int] | None = None
    for event in events:
        candidate = event.get("usage")
        if isinstance(candidate, dict):
            usage = {
                "input_tokens": int(candidate.get("input_tokens", 0) or 0),
                "cached_input_tokens": int(candidate.get("cached_input_tokens", 0) or 0),
                "output_tokens": int(candidate.get("output_tokens", 0) or 0),
            }
    return events, usage


def parse_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] | None = None
    for event in events:
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"} and item.get("text"):
            value = item["text"]
            output = json.loads(value) if isinstance(value, str) else value
    if output is None:
        raise RuntimeError("no structured agent output")
    return output


def validate_tool_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    allowed_executables = {"ls", "head", "tail", "cat"}

    def has_unquoted_shell_meta(payload: str) -> bool:
        quote: str | None = None
        index = 0
        while index < len(payload):
            char = payload[index]
            if quote == "'":
                if char == "'":
                    quote = None
            elif quote == '"':
                if char == '"':
                    quote = None
                elif char in {"$", "`"}:
                    return True
                elif char == "\\":
                    index += 1
            elif char in {"'", '"'}:
                quote = char
            elif char in {";", "&", "`", "$", "{", "}", "(", ")", "<", ">", "|", "\\"}:
                return True
            index += 1
        return quote is not None

    def split_unquoted_newlines(payload: str) -> list[str]:
        lines: list[str] = []
        buffer: list[str] = []
        quote: str | None = None
        index = 0
        while index < len(payload):
            char = payload[index]
            if quote == "'":
                buffer.append(char)
                if char == "'":
                    quote = None
            elif quote == '"':
                buffer.append(char)
                if char == '"':
                    quote = None
                elif char == "\\" and index + 1 < len(payload):
                    index += 1
                    buffer.append(payload[index])
            elif char in {"'", '"'}:
                quote = char
                buffer.append(char)
            elif char == "\n":
                if "".join(buffer).strip():
                    lines.append("".join(buffer))
                buffer = []
            else:
                buffer.append(char)
            index += 1
        if quote is not None:
            raise LeakageError(f"unbalanced command quoting: {payload}")
        if "".join(buffer).strip():
            lines.append("".join(buffer))
        return lines

    def checked_payload(command: str) -> str:
        try:
            outer = shlex.split(command)
        except ValueError as exc:
            raise LeakageError(f"unparseable command: {command}") from exc
        if (
            len(outer) == 3
            and outer[0] in {"/bin/sh", "/bin/bash", "sh", "bash"}
            and outer[1] in {"-c", "-lc"}
        ):
            payload = outer[2]
        else:
            payload = command
        if has_unquoted_shell_meta(payload):
            raise LeakageError(f"shell composition forbidden: {command}")
        for line in split_unquoted_newlines(payload):
            if not line.strip():
                continue
            try:
                tokens = shlex.split(line)
            except ValueError as exc:
                raise LeakageError(f"unparseable command line: {line}") from exc
            if not tokens or Path(tokens[0]).name not in allowed_executables:
                raise LeakageError(f"executable not allowlisted: {line}")
            if tokens[0] != Path(tokens[0]).name:
                raise LeakageError(f"executable path not allowed: {line}")
            for token in tokens[1:]:
                if token.startswith("~") or token == ".." or token.startswith("../") or "/../" in token:
                    raise LeakageError(f"parent/home path forbidden: {line}")
                if token.startswith("/") and token != "/workspace" and not token.startswith("/workspace/"):
                    raise LeakageError(f"absolute path outside workspace: {line}")
        return payload

    for event in events:
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))
        if "web_search" in item_type:
            raise LeakageError(f"web search used: {item_type}")
        if item_type == "command_execution":
            command = str(item.get("command", ""))
            checked_payload(command)
            commands.append({key: item.get(key) for key in ("command", "exit_code", "status")})
    return commands


async def preflight_adapter(
    repo: Path, model: str = MODEL, effort: str = EFFORT,
) -> CodexRuntimeAdapter:
    adapter = CodexRuntimeAdapter(
        model_map={model: model},
        verdict_path=repo / "scripts/eval/state/codex_isolation_verdict.json",
    )
    await adapter.preflight(model, effort)
    return adapter


async def preflight_stage_adapters(
    repo: Path, analyst_model: str, analyst_effort: str,
    judge_model: str, judge_effort: str,
) -> tuple[CodexRuntimeAdapter, CodexRuntimeAdapter]:
    analyst_adapter = await preflight_adapter(repo, analyst_model, analyst_effort)
    if (judge_model, judge_effort) == (analyst_model, analyst_effort):
        return analyst_adapter, analyst_adapter
    judge_adapter = await preflight_adapter(repo, judge_model, judge_effort)
    return analyst_adapter, judge_adapter


def append_ledger(artifacts: Path, entry: dict[str, Any], lock: threading.Lock) -> None:
    path = artifacts / "attempt_ledger.jsonl"
    with lock:
        with path.open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def run_in_process_group(
    argv: list[str], *, cwd: Path, input_text: str, timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run an adapter and kill its whole process group on timeout.

    The adapter launches Docker as a child. Killing only the adapter leaves a
    live container and a duplicate paid model call, so every attempt owns a new
    process group and timeout cleanup targets that group.
    """
    process = subprocess.Popen(  # noqa: S603 - argv is produced by the trusted runtime adapter.
        argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            exc.cmd, exc.timeout, output=stdout, stderr=stderr,
        ) from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def run_codex_attempt(
    *, adapter: CodexRuntimeAdapter, package: Path, schema: Path, prompt: str,
    label: str, artifacts: Path, attempt: int, ledger_lock: threading.Lock,
    output_validator: Callable[[dict[str, Any]], None] | None = None,
    run_id: str, stage: str = "analyst", requested_model: str = MODEL,
    effort: str = EFFORT,
) -> dict[str, Any]:
    request = RuntimeRequest(
        prompt, package, schema, requested_model, effort, TIMEOUT_SECONDS,
    )
    argv = adapter.build_argv(request)
    attempt_dir = artifacts / "attempts" / label / f"attempt_{attempt:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    started_wall = utc_now()
    started = time.monotonic()
    try:
        process = run_in_process_group(
            argv, cwd=package, input_text=prompt, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        (attempt_dir / "raw.jsonl").write_text(stdout)
        (attempt_dir / "stderr.txt").write_text(stderr)
        _, usage = parse_event_stream(stdout)
        append_ledger(artifacts, {
            "run_id": run_id, "label": label, "attempt": attempt,
            "stage": stage, **stage_identity(adapter, requested_model, effort),
            "started_at": started_wall, "duration_seconds": round(duration, 3),
            "returncode": None, "accepted": False, "error": "TimeoutExpired",
            "usage": usage, "usage_status": "partial" if usage is not None else "unavailable",
        }, ledger_lock)
        raise
    duration = time.monotonic() - started
    (attempt_dir / "raw.jsonl").write_text(process.stdout)
    (attempt_dir / "stderr.txt").write_text(process.stderr)
    ledger = {
        "run_id": run_id, "label": label, "attempt": attempt, "started_at": started_wall,
        "stage": stage, **stage_identity(adapter, requested_model, effort),
        "duration_seconds": round(duration, 3), "returncode": process.returncode,
        "accepted": False,
    }
    events, usage = parse_event_stream(process.stdout)
    ledger["usage"] = usage
    ledger["usage_status"] = "reported" if usage is not None else "unavailable"
    try:
        if process.returncode:
            raise RuntimeError(f"exit {process.returncode}: {process.stderr[-1200:]}")
        output = parse_events(events)
        if usage is None:
            raise RuntimeError("completed successful response omitted usage")
        validate_json(output, json.loads(schema.read_text()))
        commands = validate_tool_trace(events)
        if label.startswith("analyst__"):
            validate_trade_plan(output)
        if output_validator is not None:
            output_validator(output)
        meta = {
            **call_contract(
                adapter=adapter, package=package, schema=schema, prompt=prompt,
                artifacts=artifacts, run_id=run_id, stage=stage,
                requested_model=requested_model, effort=effort,
            ),
            "duration_seconds": round(duration, 3), "usage": usage, "commands": commands,
            "runtime_argv": argv, "attempt": attempt,
        }
        dump_json(attempt_dir / "parsed_output.json", output)
        dump_json(attempt_dir / "meta.json", meta)
        ledger.update({"accepted": True})
        append_ledger(artifacts, ledger, ledger_lock)
        return {"output": output, "meta": meta, "attempt_dir": str(attempt_dir)}
    except Exception as exc:
        ledger["error"] = f"{type(exc).__name__}: {exc}"
        append_ledger(artifacts, ledger, ledger_lock)
        raise


def load_saved_result(
    path: Path, package: Path, schema_path: Path, analyst: bool,
    adapter: CodexRuntimeAdapter, prompt: str, artifacts: Path, run_id: str,
    output_validator: Callable[[dict[str, Any]], None] | None = None,
    *, stage: str = "analyst", requested_model: str = MODEL, effort: str = EFFORT,
) -> dict[str, Any] | None:
    output_path = path / "output.json"
    meta_path = path / "meta.json"
    if not output_path.is_file() or not meta_path.is_file():
        return None
    output = json.loads(output_path.read_text())
    meta = json.loads(meta_path.read_text())
    expected = call_contract(
        adapter=adapter, package=package, schema=schema_path, prompt=prompt,
        artifacts=artifacts, run_id=run_id, stage=stage,
        requested_model=requested_model, effort=effort,
    )
    mismatches = {
        key: {"saved": meta.get(key), "expected": value}
        for key, value in expected.items() if meta.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"saved result execution-contract mismatch at {path}: {mismatches}")
    validate_json(output, json.loads(schema_path.read_text()))
    if analyst:
        validate_trade_plan(output)
    if output_validator is not None:
        output_validator(output)
    return {"output": output, "meta": meta, "resumed": True}


def execute_with_retry(
    *, adapter: CodexRuntimeAdapter, package: Path, schema: Path, prompt: str,
    label: str, result_dir: Path, artifacts: Path, ledger_lock: threading.Lock,
    analyst: bool, output_validator: Callable[[dict[str, Any]], None] | None = None,
    run_id: str, stage: str = "analyst", requested_model: str = MODEL,
    effort: str = EFFORT,
) -> dict[str, Any]:
    saved = load_saved_result(
        result_dir, package, schema, analyst, adapter, prompt, artifacts, run_id,
        output_validator, stage=stage, requested_model=requested_model, effort=effort,
    )
    if saved:
        return saved
    existing = list((artifacts / "attempts" / label).glob("attempt_*")) if (artifacts / "attempts" / label).exists() else []
    first_attempt = len(existing) + 1
    if first_attempt > MAX_ATTEMPTS:
        raise RuntimeError(
            f"{label} exhausted total attempt budget: existing={len(existing)}, max={MAX_ATTEMPTS}"
        )
    errors: list[str] = []
    for attempt in range(first_attempt, MAX_ATTEMPTS + 1):
        try:
            result = run_codex_attempt(
                adapter=adapter, package=package, schema=schema, prompt=prompt,
                label=label, artifacts=artifacts, attempt=attempt, ledger_lock=ledger_lock,
                output_validator=output_validator,
                run_id=run_id, stage=stage, requested_model=requested_model,
                effort=effort,
            )
            result_dir.mkdir(parents=True, exist_ok=True)
            dump_json(result_dir / "output.json", result["output"])
            dump_json(result_dir / "meta.json", result["meta"])
            return result
        except Exception as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"{label} failed after retries: {' | '.join(errors)}")


def analyst_schedule(registry: dict[str, Any]) -> list[tuple[str, str]]:
    schedule: list[tuple[str, str]] = []
    for case in registry["cases"]:
        arms = ["arm_a", "arm_b"]
        seed = int(hashlib.sha256(f"batch-arm-order:{case['case_id']}".encode()).hexdigest()[:8], 16)
        random.Random(seed).shuffle(arms)
        schedule.extend((case["case_id"], arm) for arm in arms)
    # Shuffle case pairs while preserving each case's randomized within-pair order.
    pairs = [schedule[index:index + 2] for index in range(0, len(schedule), 2)]
    random.Random(101).shuffle(pairs)
    return [item for pair in pairs for item in pair]


def build_judge_package(
    case: dict[str, Any], artifacts: Path, results: dict[str, dict[str, Any]],
) -> tuple[Path, dict[str, str], dict[str, str]]:
    case_id = case["case_id"]
    root = artifacts / "judge_packages" / case_id
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    ids = ["candidate_cedar", "candidate_sable"]
    arms = ["arm_a", "arm_b"]
    seed = int(hashlib.sha256(f"blind-map:{case_id}".encode()).hexdigest()[:8], 16)
    random.Random(seed).shuffle(arms)
    mapping = dict(zip(ids, arms, strict=True))
    candidate_actions: dict[str, str] = {}
    for candidate_id, arm in mapping.items():
        dump_json(root / f"{candidate_id}.json", results[arm]["output"])
        candidate_actions[candidate_id] = results[arm]["output"]["trade_plan"]["action"]
    truth = {
        "verbatim_ground_truth": case["verbatim_ground_truth"],
        "expert_claims": case["expert_claims"],
        "expert_claim_applicability": case["expert_claim_applicability"],
        "primary_claim_denominator": case["primary_claim_denominator"],
        "expert_labels": case["expert_labels"],
        "applicable_alignment_dimensions": case["applicable_alignment_dimensions"],
        "wyckoff_process_applicability_by_candidate": {
            candidate_id: process_applicability(case, action)
            for candidate_id, action in candidate_actions.items()
        },
    }
    dump_json(root / "expert_ground_truth.json", truth)
    dump_json(root / "process_rubric.json", process_rubric(case))
    dump_json(root / "judge_output.schema.json", judge_schema(ids, [item["claim_id"] for item in case["expert_claims"]]))
    (root / "prompt.txt").write_text(JUDGE_PROMPT)
    dump_json(artifacts / "private_arm_mappings" / f"{case_id}.json", mapping)
    return root, mapping, candidate_actions


def enforce_na(
    judge: dict[str, Any], case: dict[str, Any], mapping: dict[str, str],
    candidate_actions: dict[str, str],
) -> None:
    applicable = set(case["applicable_alignment_dimensions"])
    expected_claims = {claim["claim_id"] for claim in case["expert_claims"]}
    seen: set[str] = set()
    for candidate in judge["candidates"]:
        candidate_id = candidate["candidate_id"]
        if candidate_id not in mapping or candidate_id in seen:
            raise RuntimeError(f"invalid/duplicate blind candidate id: {candidate_id}")
        seen.add(candidate_id)
        process = process_applicability(case, candidate_actions[candidate_id])
        actual_claims = [item["claim_id"] for item in candidate["expert_claims"]]
        if set(actual_claims) != expected_claims or len(actual_claims) != len(expected_claims):
            raise RuntimeError(f"{case['case_id']} duplicate/missing expert claim score")
        for dimension in ALIGNMENT_DIMENSIONS:
            item = candidate["compatibility_dimensions"][dimension]
            if dimension in applicable:
                if item["status"] != "scored" or not isinstance(item["score"], int):
                    raise RuntimeError(f"{case['case_id']} {dimension} must be scored")
            elif item["status"] != "na" or item["score"] is not None:
                raise RuntimeError(f"{case['case_id']} {dimension} must be N/A")
        for dimension in PROCESS_DIMENSIONS:
            item = candidate["wyckoff_process"][dimension]
            if process[dimension]:
                if item["status"] != "scored" or not isinstance(item["score"], int):
                    raise RuntimeError(f"{case['case_id']} process {dimension} must be scored")
            elif item["status"] != "na" or item["score"] is not None:
                raise RuntimeError(f"{case['case_id']} process {dimension} must be N/A")
    if seen != set(mapping):
        raise RuntimeError("judge omitted a blinded candidate")


def score_case(
    case: dict[str, Any], results: dict[str, dict[str, Any]], judge: dict[str, Any], mapping: dict[str, str],
    candidate_actions: dict[str, str],
) -> dict[str, Any]:
    enforce_na(judge, case, mapping, candidate_actions)
    by_id = {item["candidate_id"]: item for item in judge["candidates"]}
    scored: dict[str, Any] = {
        "case_id": case["case_id"],
        "primary_expert_claims": case["expert_claims"],
        "secondary_compatibility_applicable_dimensions": case["applicable_alignment_dimensions"],
        "wyckoff_process_applicability_by_arm": {
            arm: process_applicability(case, candidate_actions[candidate_id])
            for candidate_id, arm in mapping.items()
        },
        "arms": {},
    }
    for candidate_id, arm in mapping.items():
        candidate = by_id[candidate_id]
        claim_values = {item["claim_id"]: item["score"] for item in candidate["expert_claims"]}
        claim_numerator = sum(claim_values.values())
        claim_denominator = 4 * len(claim_values)
        alignment = claim_numerator / claim_denominator
        compatibility_values = {
            dimension: candidate["compatibility_dimensions"][dimension]["score"]
            for dimension in case["applicable_alignment_dimensions"]
        }
        process_values = {
            dimension: candidate["wyckoff_process"][dimension]["score"]
            for dimension, is_applicable in process_applicability(case, candidate_actions[candidate_id]).items() if is_applicable
        }
        scored["arms"][arm] = {
            "blind_candidate_id": candidate_id,
            "primary_expert_claim_alignment": alignment,
            "primary_claim_score_numerator": claim_numerator,
            "primary_claim_score_denominator": claim_denominator,
            "primary_claim_scores": claim_values,
            "primary_claim_results": candidate["expert_claims"],
            "secondary_compatibility_alignment": sum(compatibility_values.values()) / (4 * len(compatibility_values)),
            "secondary_compatibility_scores": compatibility_values,
            "all_compatibility_results": candidate["compatibility_dimensions"],
            "wyckoff_process_score": sum(process_values.values()) / (4 * len(process_values)),
            "wyckoff_process_score_numerator": sum(process_values.values()),
            "wyckoff_process_score_denominator": 4 * len(process_values),
            "wyckoff_process_scores": process_values,
            "all_wyckoff_process_results": candidate["wyckoff_process"],
            "analysis_quality_comment": candidate["analysis_quality_comment"],
            "trade_plan_comment": candidate["trade_plan_comment"],
            "trade_plan": results[arm]["output"]["trade_plan"],
        }
    scored["delta_b_minus_a"] = (
        scored["arms"]["arm_b"]["primary_expert_claim_alignment"]
        - scored["arms"]["arm_a"]["primary_expert_claim_alignment"]
    )
    scored["secondary_compatibility_delta_b_minus_a"] = (
        scored["arms"]["arm_b"]["secondary_compatibility_alignment"]
        - scored["arms"]["arm_a"]["secondary_compatibility_alignment"]
    )
    scored["wyckoff_process_delta_b_minus_a"] = (
        scored["arms"]["arm_b"]["wyckoff_process_score"]
        - scored["arms"]["arm_a"]["wyckoff_process_score"]
    )
    return scored


def rescore_original_pilot(artifacts: Path) -> dict[str, Any]:
    pilot = artifacts.parent / "wiki-assisted-pilot"
    judge_path = pilot / "outputs/blind_judge_v2_scale_corrected.json"
    mapping_path = pilot / "private_arm_mapping.json"
    if not judge_path.is_file() or not mapping_path.is_file():
        return {"status": "unavailable"}
    judge = json.loads(judge_path.read_text())
    mapping = json.loads(mapping_path.read_text())
    applicable = ["structure", "key_events", "leading_scenario"]
    by_id = {item["candidate_id"]: item for item in judge["candidates"]}
    arms: dict[str, Any] = {}
    for candidate_id, arm in mapping.items():
        old_scores = by_id[candidate_id]["scores"]
        values = {name: old_scores[name]["score"] for name in applicable}
        arms[arm] = {"expert_alignment": sum(values.values()) / 12, "scores": values}
    return {
        "status": "rescored_from_existing_blind_judge",
        "case_id": PILOT_CASE_ID,
        "applicable_dimensions": applicable,
        "arms": arms,
        "delta_b_minus_a": arms["arm_b"]["expert_alignment"] - arms["arm_a"]["expert_alignment"],
        "limitation": "Reuses v2 judge's applicable dimension scores; no new judge call.",
    }


def attempt_accounting(run_dir: Path, run_id: str) -> dict[str, Any]:
    ledger_path = run_dir / "attempt_ledger.jsonl"
    attempts = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()] if ledger_path.is_file() else []
    if any(item.get("run_id") != run_id for item in attempts):
        raise RuntimeError("attempt ledger mixes run ids")
    known_usage = [item["usage"] for item in attempts if isinstance(item.get("usage"), dict)]
    timed = [
        (datetime.fromisoformat(item["started_at"]).timestamp(), float(item.get("duration_seconds", 0)))
        for item in attempts if item.get("started_at")
    ]
    return {
        "attempts": len(attempts),
        "accepted_attempts": sum(item.get("accepted") is True for item in attempts),
        "rejected_attempts": sum(item.get("accepted") is not True for item in attempts),
        "usage_reported_attempts": len(known_usage),
        "usage_unavailable_attempts": len(attempts) - len(known_usage),
        "duration_seconds": sum(float(item.get("duration_seconds", 0)) for item in attempts),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in known_usage),
        "cached_input_tokens": sum(int(item.get("cached_input_tokens", 0)) for item in known_usage),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in known_usage),
        "wall_clock_elapsed_seconds": round(
            max(start + duration for start, duration in timed) - min(start for start, _ in timed), 3,
        ) if timed else 0.0,
    }


def aggregate(
    registry: dict[str, Any], scorecards: list[dict[str, Any]], results: dict[str, dict[str, dict[str, Any]]],
    judges: dict[str, dict[str, Any]], registry_hash: str, evaluation_registry_hash: str,
    run_dir: Path, run_id: str, *, analyst_identity: dict[str, str],
    judge_identity: dict[str, str],
) -> dict[str, Any]:
    deltas = [item["delta_b_minus_a"] for item in scorecards]
    usage: dict[str, dict[str, float]] = {}
    for arm in ("arm_a", "arm_b"):
        metas = [results[case["case_id"]][arm]["meta"] for case in registry["cases"]]
        usage[arm] = {
            "calls": len(metas),
            "duration_seconds": sum(float(meta["duration_seconds"]) for meta in metas),
            "input_tokens": sum(int(meta["usage"]["input_tokens"]) for meta in metas),
            "cached_input_tokens": sum(int(meta["usage"]["cached_input_tokens"]) for meta in metas),
            "output_tokens": sum(int(meta["usage"]["output_tokens"]) for meta in metas),
        }
    judge_metas = [judges[case["case_id"]]["meta"] for case in registry["cases"]]
    usage["judge"] = {
        "calls": len(judge_metas),
        "duration_seconds": sum(float(meta["duration_seconds"]) for meta in judge_metas),
        "input_tokens": sum(int(meta["usage"]["input_tokens"]) for meta in judge_metas),
        "cached_input_tokens": sum(int(meta["usage"]["cached_input_tokens"]) for meta in judge_metas),
        "output_tokens": sum(int(meta["usage"]["output_tokens"]) for meta in judge_metas),
    }
    total = {
        key: sum(float(stage[key]) for stage in usage.values())
        for key in ("duration_seconds", "input_tokens", "cached_input_tokens", "output_tokens")
    }
    all_attempt_usage = attempt_accounting(run_dir, run_id)
    mean_delta = sum(deltas) / len(deltas)
    positive = sum(delta > 0 for delta in deltas)
    arm_means = {
        arm: {
            "primary_expert_claim_alignment": sum(
                item["arms"][arm]["primary_expert_claim_alignment"] for item in scorecards
            ) / len(scorecards),
            "secondary_compatibility_alignment": sum(
                item["arms"][arm]["secondary_compatibility_alignment"] for item in scorecards
            ) / len(scorecards),
            "wyckoff_process_score": sum(
                item["arms"][arm]["wyckoff_process_score"] for item in scorecards
            ) / len(scorecards),
        }
        for arm in ("arm_a", "arm_b")
    }
    minimum_arm_mean = min(
        arm_means[arm]["primary_expert_claim_alignment"]
        for arm in ("arm_a", "arm_b")
    )
    if minimum_arm_mean < KILL_ARM_MEAN_THRESHOLD or mean_delta <= 0:
        verdict = "DISPROVEN"
    elif (
        minimum_arm_mean >= PROOF_ARM_MEAN_THRESHOLD
        and mean_delta >= PROOF_DELTA_THRESHOLD
        and positive >= PROOF_POSITIVE_CASES
    ):
        verdict = "PROVEN"
    else:
        verdict = "CONDITIONAL"
    return {
        "status": "complete",
        "stages": {"analyst": analyst_identity, "judge": judge_identity},
        "run_id": run_id,
        "registry_sha256": registry_hash,
        "evaluation_registry_v2_sha256": evaluation_registry_hash,
        "case_count": len(scorecards),
        "paired_mean_delta_b_minus_a": mean_delta,
        "arm_mean_scores": arm_means,
        "secondary_compatibility_mean_delta_b_minus_a": (
            arm_means["arm_b"]["secondary_compatibility_alignment"]
            - arm_means["arm_a"]["secondary_compatibility_alignment"]
        ),
        "wyckoff_process_mean_delta_b_minus_a": (
            arm_means["arm_b"]["wyckoff_process_score"]
            - arm_means["arm_a"]["wyckoff_process_score"]
        ),
        "positive_case_count": positive,
        "zero_case_count": sum(delta == 0 for delta in deltas),
        "negative_case_count": sum(delta < 0 for delta in deltas),
        "per_case_deltas": {item["case_id"]: item["delta_b_minus_a"] for item in scorecards},
        "usage_by_stage_arm": usage,
        "accepted_usage_total": total,
        "all_attempt_usage_total": all_attempt_usage,
        "wall_clock_elapsed_seconds": all_attempt_usage["wall_clock_elapsed_seconds"],
        "usd_cost": None,
        "usd_cost_note": "Codex ChatGPT-auth CLI did not expose a per-call charge; no price was fabricated.",
        "precommitted_verdict": verdict,
        "verdict_thresholds": {
            "proof_delta_b_minus_a": PROOF_DELTA_THRESHOLD,
            "proof_positive_case_count": PROOF_POSITIVE_CASES,
            "proof_arm_mean": PROOF_ARM_MEAN_THRESHOLD,
            "kill_arm_mean": KILL_ARM_MEAN_THRESHOLD,
            "kill_delta_b_minus_a_at_or_below": 0.0,
        },
    }


def artifact_index(artifacts: Path) -> dict[str, Any]:
    files = []
    for path in sorted(artifacts.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            files.append({
                "path": path.relative_to(artifacts).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return {"generated_at": utc_now(), "file_count": len(files), "files": files}


def main() -> int:
    global TIMEOUT_SECONDS, MAX_ATTEMPTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--analysts-only", action="store_true")
    parser.add_argument("--judges-only", action="store_true")
    parser.add_argument("--one-analyst", help="schema/preflight call as CASE_ID:ARM; saved for resume")
    parser.add_argument("--analyst-model", default=MODEL)
    parser.add_argument("--analyst-effort", default=EFFORT)
    parser.add_argument("--judge-model", default=MODEL)
    parser.add_argument("--judge-effort", default=EFFORT)
    parser.add_argument("--timeout-seconds", type=int, default=TIMEOUT_SECONDS)
    parser.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    args = parser.parse_args()
    if not 60 <= args.timeout_seconds <= 3600:
        raise RuntimeError("--timeout-seconds must be between 60 and 3600")
    if not 1 <= args.max_attempts <= 3:
        raise RuntimeError("--max-attempts must be between 1 and 3")
    validate_runtime_choice(args.analyst_model, args.analyst_effort, "analyst")
    validate_runtime_choice(args.judge_model, args.judge_effort, "judge")
    TIMEOUT_SECONDS = args.timeout_seconds
    MAX_ATTEMPTS = args.max_attempts

    repo = Path(__file__).resolve().parents[1]
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    registry_path = args.registry.resolve()
    source_registry = load_registry(registry_path)
    registry_hash = sha256(registry_path)
    lock_path = artifacts / "registry_lock.json"
    if lock_path.is_file() and ((artifacts / "results").exists() or (artifacts / "attempts").exists()):
        prior_hash = json.loads(lock_path.read_text()).get("sha256")
        if prior_hash != registry_hash:
            raise RuntimeError(
                f"registry changed after execution began: locked={prior_hash}, current={registry_hash}"
            )
    dump_json(lock_path, {
        "source": str(registry_path), "sha256": registry_hash,
        "case_ids": [case["case_id"] for case in source_registry["cases"]],
        "locked_at": utc_now(),
    })
    registry, evaluation_registry_hash = freeze_evaluation_registry_v2(
        artifacts, source_registry, registry_hash,
    )
    summaries = build_packages(repo, args.source_root.resolve(), registry, artifacts)
    if args.build_only:
        dump_json(artifacts / "build_package_index.json", artifact_index(artifacts / "packages"))
        print(json.dumps({
            "status": "built", "registry_sha256": registry_hash,
            "evaluation_registry_v2_sha256": evaluation_registry_hash,
            "packages": summaries,
        }, indent=2))
        return 0

    analyst_adapter, judge_adapter = asyncio.run(preflight_stage_adapters(
        repo, args.analyst_model, args.analyst_effort,
        args.judge_model, args.judge_effort,
    ))
    analyst_identity = stage_identity(
        analyst_adapter, args.analyst_model, args.analyst_effort,
    )
    judge_identity = stage_identity(judge_adapter, args.judge_model, args.judge_effort)
    run_id, run_spec = stable_run_id(
        analyst_adapter, artifacts, evaluation_registry_hash,
        analyst_model=args.analyst_model, analyst_effort=args.analyst_effort,
        judge_adapter=judge_adapter, judge_model=args.judge_model,
        judge_effort=args.judge_effort,
    )
    manifest_path = artifacts / "valid_runs" / f"{run_id}.json"
    manifest = {"run_id": run_id, "contract": run_spec}
    if manifest_path.is_file() and json.loads(manifest_path.read_text()) != manifest:
        raise RuntimeError("immutable valid run manifest changed")
    dump_json(manifest_path, manifest)
    dump_json(artifacts / "latest_valid_run.json", {"run_id": run_id, "manifest": str(manifest_path)})
    run_dir = promote_build_to_run(artifacts, run_id, run_spec)
    shutil.copy2(analyst_adapter.verdict_path, run_dir / "codex_isolation_verdict.json")
    ledger_lock = threading.Lock()
    results: dict[str, dict[str, dict[str, Any]]] = {
        case["case_id"]: {} for case in registry["cases"]
    }
    schedule = analyst_schedule(registry)
    dump_json(run_dir / "run_order.json", {"seed": 101, "analyst_schedule": schedule, "max_concurrency": ANALYST_CONCURRENCY})

    def run_analyst(item: tuple[str, str]) -> tuple[str, str, dict[str, Any]]:
        case_id, arm = item
        package = run_dir / "packages" / case_id / arm
        result = execute_with_retry(
            adapter=analyst_adapter, package=package, schema=package / "analysis_output.schema.json",
            prompt=ANALYST_PROMPT,
            label=f"{result_namespace('analyst', analyst_adapter, args.analyst_model, args.analyst_effort)}__{case_id}__{arm}",
            result_dir=run_dir / "results" / case_id / arm,
            artifacts=run_dir, ledger_lock=ledger_lock, analyst=True, run_id=run_id,
            stage="analyst", requested_model=args.analyst_model,
            effort=args.analyst_effort,
        )
        return case_id, arm, result

    if args.one_analyst:
        try:
            one_case, one_arm = args.one_analyst.split(":", 1)
        except ValueError as exc:
            raise RuntimeError("--one-analyst must be CASE_ID:arm_a|arm_b") from exc
        if (one_case, one_arm) not in schedule:
            raise RuntimeError(f"unknown analyst selection: {args.one_analyst}")
        case_id, arm, result = run_analyst((one_case, one_arm))
        dump_json(run_dir / "schema_preflight.json", {
            "status": "passed", "case_id": case_id, "arm": arm,
            "attempt": result["meta"]["attempt"], "usage": result["meta"]["usage"],
            "duration_seconds": result["meta"]["duration_seconds"],
        })
        dump_json(run_dir / "artifact_index.json", artifact_index(run_dir))
        print(json.dumps({"status": "schema_preflight_passed", "case_id": case_id, "arm": arm}, indent=2))
        return 0

    if not args.judges_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=ANALYST_CONCURRENCY) as pool:
            futures = [pool.submit(run_analyst, item) for item in schedule]
            for future in concurrent.futures.as_completed(futures):
                case_id, arm, result = future.result()
                results[case_id][arm] = result
    else:
        for case in registry["cases"]:
            case_id = case["case_id"]
            for arm in ("arm_a", "arm_b"):
                package = run_dir / "packages" / case_id / arm
                result = load_saved_result(
                    run_dir / "results" / case_id / arm,
                    package, package / "analysis_output.schema.json", True,
                    analyst_adapter, ANALYST_PROMPT, run_dir, run_id,
                    stage="analyst", requested_model=args.analyst_model,
                    effort=args.analyst_effort,
                )
                if result is None:
                    raise RuntimeError(f"missing saved analyst output for {case_id} {arm}")
                results[case_id][arm] = result
    if args.analysts_only:
        dump_json(run_dir / "analyst_run_summary.json", {
            "status": "complete", "run_id": run_id, "registry_sha256": registry_hash,
            "evaluation_registry_v2_sha256": evaluation_registry_hash, "calls": 20,
            "stages": {"analyst": analyst_identity, "judge": judge_identity},
        })
        dump_json(run_dir / "artifact_index.json", artifact_index(run_dir))
        print(json.dumps({"status": "analysts_complete", "calls": 20}, indent=2))
        return 0

    judges: dict[str, dict[str, Any]] = {}
    scorecards: list[dict[str, Any]] = []
    for case in registry["cases"]:
        case_id = case["case_id"]
        judge_root, mapping, candidate_actions = build_judge_package(case, run_dir, results[case_id])
        judge_result = execute_with_retry(
            adapter=judge_adapter, package=judge_root, schema=judge_root / "judge_output.schema.json",
            prompt=JUDGE_PROMPT,
            label=f"{result_namespace('judge', judge_adapter, args.judge_model, args.judge_effort)}__{case_id}",
            result_dir=run_dir / "results" / case_id / "judge",
            artifacts=run_dir, ledger_lock=ledger_lock, analyst=False, run_id=run_id,
            stage="judge", requested_model=args.judge_model, effort=args.judge_effort,
            output_validator=lambda output, selected=case, blind=mapping, actions=candidate_actions: enforce_na(output, selected, blind, actions),
        )
        enforce_na(judge_result["output"], case, mapping, candidate_actions)
        judges[case_id] = judge_result
        scorecard = score_case(case, results[case_id], judge_result["output"], mapping, candidate_actions)
        dump_json(run_dir / "scorecards" / f"{case_id}.json", scorecard)
        scorecards.append(scorecard)

    if analyst_identity == judge_identity:
        original_rescore = rescore_original_pilot(artifacts)
    else:
        original_rescore = {
            "status": "not_applicable",
            "reason": "legacy pilot judge output is not reusable across mixed stage runtime identities",
            "stages": {"analyst": analyst_identity, "judge": judge_identity},
        }
    dump_json(run_dir / "original_link_na_rescore.json", original_rescore)
    summary = aggregate(
        registry, scorecards, results, judges, registry_hash,
        evaluation_registry_hash, run_dir, run_id,
        analyst_identity=analyst_identity, judge_identity=judge_identity,
    )
    dump_json(run_dir / "batch_summary.json", summary)
    dump_json(run_dir / "artifact_index.json", artifact_index(run_dir))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
