"""Scoring rubric and isolated judge input helpers for eval analyses."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast


ScoreMethod = Literal["deterministic", "judge"]
ScoreStatus = Literal["scored", "na"]
Direction = Literal["up", "down", "none"]
Outcome = Literal["hit_tp", "hit_sl", "open"]

DETERMINISTIC_DIMENSIONS = {"direction", "trigger", "invalidation"}
JUDGE_DIMENSIONS = {"structure", "phase", "event", "narrative_quality", "calibration"}
DIMENSIONS = DETERMINISTIC_DIMENSIONS | JUDGE_DIMENSIONS

DIMENSION_METHOD: dict[str, ScoreMethod] = {
    "structure": "judge",
    "phase": "judge",
    "event": "judge",
    "direction": "deterministic",
    "trigger": "deterministic",
    "invalidation": "deterministic",
    "narrative_quality": "judge",
    "calibration": "judge",
}

DIMENSION_WEIGHTS: dict[str, float] = {
    "structure": 0.15,
    "phase": 0.15,
    "event": 0.15,
    "direction": 0.15,
    "trigger": 0.10,
    "invalidation": 0.10,
    "narrative_quality": 0.10,
    "calibration": 0.10,
}

JUDGE_PROMPT_TEMPLATE = """You are an isolated Wyckoff eval judge.

You receive only:
1. the analyst output;
2. the answer key ground_truth and structured labels.

You must never infer from, request, or rely on charts, candles, case folders,
filesystem paths, symbols, or dates. Score only the provided text and labels.

Return strict JSON:
{
  "structure": {"score": 0.0-1.0, "rationale": "..."},
  "phase": {"score": 0.0-1.0, "rationale": "..."},
  "event": {"score": 0.0-1.0, "rationale": "..."},
  "narrative_quality": {"score": 0.0-1.0, "rationale": "..."},
  "calibration": {"score": 0.0-1.0, "rationale": "..."}
}

Rubric:
- structure: semantic match to the realized Wyckoff structure; allow synonyms.
- phase: semantic match to the correct phase; do not require exact wording.
- event: semantic match to event_type; allow equivalent Wyckoff terms.
- narrative_quality: reasoning quality, evidence ordering, and no hindsight claims.
- calibration: confidence matches decisiveness and ambiguity.

Wait rule:
If decisive is false and the analyst explicitly chose wait, neutral, or no-trade
with low confidence, do not penalize deterministic direction/trigger/invalidation.
Reward calibration when the low-confidence wait call fits the ambiguous answer key.
"""

SENSITIVE_JUDGE_KEYS = {
    "candles",
    "ohlcv",
    "post_t_candles",
    "future_visible",
    "chart",
    "chart_path",
    "chart_file",
    "case_dir",
    "case_path",
    "candles_path",
    "answer_key_path",
    "paths",
    "symbol",
    "cutoff",
    "coef_meta",
}


class DimensionScore(TypedDict):
    score: float | None
    method: ScoreMethod
    rationale: str
    status: ScoreStatus


class ScoreRecord(TypedDict):
    case_id: str
    analysis_id: str | None
    dimensions: dict[str, DimensionScore]
    aggregate: float
    wait_case: bool


class DeterministicResult(TypedDict):
    case_id: str
    dimensions: dict[str, DimensionScore]
    direction_correct: bool | None
    trigger_hit: bool | None
    invalidation_hit: bool | None
    invalidation_respected: bool | None
    bars_to_resolution: int | None
    outcome: Outcome | None
    wait_case: bool
    used_fallback: bool


class JudgeInput(TypedDict):
    output: dict[str, Any]
    answer_key: dict[str, Any]
    prompt: str


class JudgeDimension(TypedDict):
    score: float
    rationale: NotRequired[str]


def _score(value: float | None, method: ScoreMethod, rationale: str) -> DimensionScore:
    if value is None:
        return {"score": None, "method": method, "rationale": rationale, "status": "na"}
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("dimension score must be between 0 and 1")
    return {"score": float(value), "method": method, "rationale": rationale, "status": "scored"}


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be numeric") from exc
    else:
        raise ValueError(f"{field} must be numeric")
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _confidence(value: Any) -> float | None:
    if value is None:
        return None
    confidence = _number(value, "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return confidence


def _normalize_direction(value: Any) -> Direction:
    raw = str(value).strip().lower()
    if raw in {"up", "long", "bull", "bullish", "higher"}:
        return "up"
    if raw in {"down", "short", "bear", "bearish", "lower"}:
        return "down"
    if raw in {"none", "flat", "neutral", "wait", "no trade", "no-trade", "stand aside"}:
        return "none"
    raise ValueError(f"Unsupported direction: {value!r}")


def _is_low_confidence_wait(direction: Any, confidence: Any) -> bool:
    try:
        normalized = _normalize_direction(direction)
    except ValueError:
        return False
    parsed_confidence = _confidence(confidence)
    return normalized == "none" and parsed_confidence is not None and parsed_confidence <= 0.35


def _post_t_candles(answer_key: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if "post_t_candles" in answer_key:
        candles = answer_key["post_t_candles"]
        used_fallback = False
    elif "future_visible" in answer_key:
        candles = answer_key["future_visible"]
        used_fallback = True
    else:
        candles = []
        used_fallback = "realized_direction" not in answer_key or "decisive" not in answer_key
    if not isinstance(candles, list):
        raise ValueError("post_t_candles must be a list")
    return cast(list[dict[str, Any]], candles), used_fallback


def _replay(direction: Direction, trigger_level: float, invalidation_level: float, candles: list[dict]) -> tuple[Outcome, int | None]:
    for idx, bar in enumerate(candles, start=1):
        high = _number(bar["high"], "bar.high")
        low = _number(bar["low"], "bar.low")
        if direction == "up":
            # Same-bar tie-break resolves to SL first, matching signal_logger.
            if low <= invalidation_level:
                return "hit_sl", idx
            if high >= trigger_level:
                return "hit_tp", idx
        elif direction == "down":
            if high >= invalidation_level:
                return "hit_sl", idx
            if low <= trigger_level:
                return "hit_tp", idx
    return "open", None


def _fallback_realized_direction(outcome: Outcome, direction: Direction) -> Direction:
    if outcome != "hit_tp":
        return "none"
    return direction


def score_deterministic(
    *,
    direction: Any,
    trigger_level: Any = None,
    invalidation_level: Any = None,
    answer_key: dict[str, Any],
    confidence: Any = None,
) -> DeterministicResult:
    """Score forecast direction, trigger, and invalidation without LLM calls."""
    if not isinstance(answer_key, dict):
        raise ValueError("answer_key must be a dict")

    case_id = str(answer_key.get("case_id", "unknown"))
    decisive = bool(answer_key.get("decisive", False))
    if not decisive and _is_low_confidence_wait(direction, confidence):
        dimensions = {
            "direction": _score(None, "deterministic", "Non-decisive answer key and low-confidence wait call."),
            "trigger": _score(None, "deterministic", "Wait call has no trigger requirement."),
            "invalidation": _score(None, "deterministic", "Wait call has no invalidation requirement."),
        }
        return {
            "case_id": case_id,
            "dimensions": dimensions,
            "direction_correct": None,
            "trigger_hit": None,
            "invalidation_hit": None,
            "invalidation_respected": None,
            "bars_to_resolution": None,
            "outcome": None,
            "wait_case": True,
            "used_fallback": False,
        }

    normalized_direction = _normalize_direction(direction)
    candles, used_fallback = _post_t_candles(answer_key)
    outcome: Outcome = "open"
    bars_to_resolution: int | None = None

    if normalized_direction in {"up", "down"}:
        trigger = _number(trigger_level, "trigger_level")
        invalidation = _number(invalidation_level, "invalidation_level")
        outcome, bars_to_resolution = _replay(normalized_direction, trigger, invalidation, candles)

    realized_raw = answer_key.get("realized_direction")
    if realized_raw is None:
        realized_direction = _fallback_realized_direction(outcome, normalized_direction)
        used_fallback = True
    else:
        realized_direction = _normalize_direction(realized_raw)

    direction_correct = normalized_direction == realized_direction
    trigger_hit = outcome == "hit_tp" if normalized_direction in {"up", "down"} else False
    invalidation_hit = outcome == "hit_sl" if normalized_direction in {"up", "down"} else False
    invalidation_respected = not invalidation_hit

    dimensions = {
        "direction": _score(
            1.0 if direction_correct else 0.0,
            "deterministic",
            f"Forecast direction {normalized_direction!r} vs realized {realized_direction!r}.",
        ),
        "trigger": _score(
            1.0 if trigger_hit else 0.0,
            "deterministic",
            f"Replay outcome was {outcome!r}.",
        ),
        "invalidation": _score(
            1.0 if invalidation_respected else 0.0,
            "deterministic",
            "Invalidation was not hit before trigger." if invalidation_respected else "Invalidation was hit before trigger.",
        ),
    }

    return {
        "case_id": case_id,
        "dimensions": dimensions,
        "direction_correct": direction_correct,
        "trigger_hit": trigger_hit,
        "invalidation_hit": invalidation_hit,
        "invalidation_respected": invalidation_respected,
        "bars_to_resolution": bars_to_resolution,
        "outcome": outcome,
        "wait_case": False,
        "used_fallback": used_fallback,
    }


def _sanitize_for_judge(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text in SENSITIVE_JUDGE_KEYS or key_text.endswith("_path"):
                continue
            clean[key_text] = _sanitize_for_judge(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_for_judge(item) for item in value]
    return value


def prepare_judge_input(analysis_output: dict[str, Any], answer_key: dict[str, Any]) -> JudgeInput:
    """Return judge payload with answer text and labels, but no chart/candle leakage."""
    if not isinstance(analysis_output, dict):
        raise ValueError("analysis_output must be a dict")
    if not isinstance(answer_key, dict):
        raise ValueError("answer_key must be a dict")

    allowed_answer_keys = {
        "case_id",
        "ground_truth",
        "event_type",
        "realized_direction",
        "decisive",
    }
    sanitized_answer = {
        key: _sanitize_for_judge(answer_key[key])
        for key in allowed_answer_keys
        if key in answer_key
    }
    return {
        "output": cast(dict[str, Any], _sanitize_for_judge(analysis_output)),
        "answer_key": sanitized_answer,
        "prompt": JUDGE_PROMPT_TEMPLATE,
    }


def _judge_dimensions(judge_verdict: dict[str, Any]) -> dict[str, DimensionScore]:
    dimensions: dict[str, DimensionScore] = {}
    for name in sorted(JUDGE_DIMENSIONS):
        if name not in judge_verdict:
            continue
        raw = judge_verdict[name]
        if not isinstance(raw, dict):
            raise ValueError(f"judge verdict for {name} must be an object")
        dimensions[name] = _score(
            _number(raw.get("score"), f"{name}.score"),
            "judge",
            str(raw.get("rationale", "")),
        )
    return dimensions


def combine_scores(
    deterministic: DeterministicResult | dict[str, Any],
    judge_verdict: dict[str, Any],
    *,
    wait_case: bool | None = None,
    analysis_id: str | None = None,
) -> ScoreRecord:
    """Combine deterministic and judge dimensions into a weighted ScoreRecord."""
    if not isinstance(judge_verdict, dict):
        raise ValueError("judge_verdict must be a dict")

    det_dimensions = cast(dict[str, DimensionScore], deterministic.get("dimensions", {}))
    dimensions: dict[str, DimensionScore] = dict(det_dimensions)
    dimensions.update(_judge_dimensions(judge_verdict))

    weighted_sum = 0.0
    weight_total = 0.0
    for name, dimension in dimensions.items():
        score_value = dimension.get("score")
        if score_value is None:
            continue
        weight = DIMENSION_WEIGHTS.get(name, 0.0)
        weighted_sum += score_value * weight
        weight_total += weight

    aggregate = round(weighted_sum / weight_total, 4) if weight_total else 0.0
    return {
        "case_id": str(deterministic.get("case_id", judge_verdict.get("case_id", "unknown"))),
        "analysis_id": analysis_id,
        "dimensions": dimensions,
        "aggregate": aggregate,
        "wait_case": bool(deterministic.get("wait_case", False) if wait_case is None else wait_case),
    }


def write_score(score_record: ScoreRecord, base_dir: str | Path) -> Path:
    """Write ScoreRecord to base_dir/_scores/<case_id>.score.json."""
    if not isinstance(score_record.get("case_id"), str) or not score_record["case_id"]:
        raise ValueError("score_record.case_id is required")
    scores_dir = Path(base_dir) / "_scores"
    scores_dir.mkdir(parents=True, exist_ok=True)
    path = scores_dir / f"{score_record['case_id']}.score.json"
    path.write_text(json.dumps(score_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
