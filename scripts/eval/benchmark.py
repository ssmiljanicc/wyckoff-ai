"""Benchmark runner for the Phase 6 model × effort eval matrix.

This module is the integration top of Faza 4. Following the Phase 2/4 pattern,
**code prepares the run matrix + scores + aggregates**. The separate orchestrator
spawns isolated analyst and judge processes; this module never calls an LLM.

Pipeline:
    build_run_matrix(case_ids) -> [RunSpec]      # + benchmark_runs.json template
        [runbook] orchestrator fills results/<run_id>.json per RunSpec
    score_run(spec, result, answer_key) -> BenchmarkRow   # REUSES scoring.py
    aggregate_report(rows) -> BenchmarkReport    # Δleakage + Δlookahead + ROI
    render_report_markdown(report) -> str        # -> _benchmark/report.{md,json}

Two controls are computed as Δscore over the SAME frozen snapshots:
    Δleakage   = mean(revealed) − mean(anon)            # pretraining leakage
    Δlookahead = mean(future_visible) − mean(blind)     # lookahead honesty
Both are measured only over case_ids common to both angles. The benchmark owns
ALL its snapshots (blind, __fv, __revealed) under a dedicated BENCHMARK_BASE_DIR,
regenerated from the ground-truth definitions — it does NOT reuse data/eval/case_0X,
whose case_id namespace is shared with the Phase 2 probe (different instruments).
The baseline runs the full model×effort sweep; the controls run only a
representative (model, effort) subset (scope knob).

Run:
    uv run --extra mcp python -m scripts.eval.benchmark --ensure-snapshots  # build blind/fv/revealed
    uv run --extra mcp python -m scripts.eval.benchmark                     # build matrix
    uv run --extra mcp python -m scripts.eval.benchmark --dry-run           # stub, no network
    uv run --extra mcp python -m scripts.eval.benchmark --ingest results/
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from scripts.eval import scoring
from scripts.eval.dry_run_client import DryRunClient
from scripts.eval.snapshot_builder import DEFAULT_BASE_DIR, build_snapshot

# ---------------------------------------------------------------------------
# Constants: pricing + matrix + controls
# ---------------------------------------------------------------------------

# Token pricing per 1M tokens (USD). Source: claude-api reference, cached
# 2026-06-04. Pricing CHANGES — this is the single source of truth; do NOT
# hardcode prices anywhere else. Codex (GPT-5.x-codex) is not in the claude-api
# reference, so its pricing is None in v1 → reported as tokens-only ROI. Fable 5
# is listed but pending harness availability.
PRICING_SOURCE_DATE = "2026-06-04"
MODEL_PRICING: dict[str, dict[str, float] | None] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "codex": None,  # GPT-5.x-codex placeholder; pricing TBD
}

# Claude Code /effort tiers: low · medium · high · xhigh · max. PRD "extra-high"
# = xhigh (between high and max); top tier = max.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# model_id -> effort levels swept. Haiku 4.5 is intentionally ABSENT: it has no
# effort param. claude-fable-5 stays listed per PRD (benchmark it once the harness
# can spawn it); until then the orchestrator simply skips it — an unavailable model
# gets no runs, so it produces no rows rather than empty ones.
BENCHMARK_MATRIX: dict[str, list[str]] = {
    "claude-sonnet-4-6": ["medium", "high", "xhigh", "max"],
    "claude-opus-4-8": ["medium", "high", "xhigh", "max"],
    "claude-fable-5": ["medium", "high", "xhigh", "max"],  # pending availability
    "codex": ["low", "medium", "high", "xhigh"],
}

# Each control angle = (time_mode, anon_mode). baseline is the realistic eval
# condition; the two controls add one axis each. The fourth corner
# (future_visible, revealed) is intentionally NOT built — three angles give both
# deltas relative to the shared (blind, anon) baseline.
CONTROLS: dict[str, tuple[str, str]] = {
    "baseline": ("blind", "anon"),
    "leakage": ("blind", "revealed"),
    "lookahead": ("future_visible", "anon"),
}
BASELINE_CONTROL = "baseline"
_CONTROL_BY_ANGLE: dict[tuple[str, str], str] = {
    angle: name for name, angle in CONTROLS.items()
}

# Scope knob (PRD: the controls answer a per-points property — "≥5 common cases",
# NOT the whole matrix). Baseline always gets the FULL model×effort sweep; the
# leakage/lookahead controls run only on this representative subset, so the matrix
# stays ~baseline + small δ instead of controls × full matrix. Pass [] / None to
# build_run_matrix to widen back to the full sweep if ever needed.
DEFAULT_CONTROL_MODELS: tuple[str, ...] = ("claude-opus-4-8",)
DEFAULT_CONTROL_EFFORTS: tuple[str, ...] = ("high",)

# Benchmark snapshots live in a DEDICATED base dir, isolated from data/eval/ where
# the Phase 2 probe writes case_01..03 with DIFFERENT instruments. Without this,
# the lookahead/baseline angles could silently read stale probe __fv/blind data
# that shares the case_id namespace. Everything the benchmark needs (blind, __fv,
# __revealed + answer keys) is regenerated here from the ground-truth definitions.
BENCHMARK_BASE_DIR = DEFAULT_BASE_DIR / "benchmark"

BENCHMARK_RUNBOOK = (
    "Code prepares this matrix; scripts.eval.orchestrator owns analyst/judge execution. "
    "For each run with a filled-in snapshot: "
    "(1) spawn an ISOLATED blind-analyst subagent (wyckoff-trader-skill, model "
    "override = model, requested effort) that reads ONLY snapshot_dir "
    "(+ instruction.txt for future_visible) and returns the eval-output schema "
    "(direction, NUMERIC trigger, NUMERIC invalidation, confidence, structure, "
    "phase, event). The revealed pass MUST be a brand-new subagent with no "
    "context from the anon pass (anti-contamination). "
    "(2) Record usage{input_tokens, output_tokens}. "
    "(3) Judge = isolated Opus subagent via scoring.prepare_judge_input(output, "
    "answer_key) — the chart is physically absent from the prompt. "
    "(4) Write {analysis_output, usage, judge_verdict} to results/<run_id>.json. "
    "Then run --ingest results/ to score, aggregate, and render the report."
)


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class RunSpec(TypedDict):
    run_id: str
    case_id: str
    time_mode: str
    anon_mode: str
    control: str
    model: str
    effort: str
    snapshot_dir: str
    answer_key_path: str
    instruction: str | None
    missing_snapshot: bool


class RunResult(TypedDict):
    analysis_output: dict[str, Any]
    usage: dict[str, Any]
    judge_verdict: dict[str, Any]


class BenchmarkRow(TypedDict):
    run_id: str
    case_id: str
    model: str
    effort: str
    time_mode: str
    anon_mode: str
    event_type: str | None
    aggregate: float
    dimensions: dict[str, float | None]
    total_tokens: int
    cost_usd: float | None
    roi: float | None
    roi_basis: str
    wait_case: bool


class GroupRow(TypedDict):
    model: str
    effort: str
    n: int
    aggregate: float
    dimensions: dict[str, float | None]
    event_types: dict[str, float]
    mean_tokens: float
    mean_cost_usd: float | None
    mean_roi: float | None
    roi_basis: str


class DeltaRow(TypedDict):
    model: str
    effort: str
    n: int
    delta: float | None


class BenchmarkReport(TypedDict):
    n_rows: int
    groups: list[GroupRow]
    rank_by_aggregate: list[dict[str, Any]]
    # ROI ranks are split by basis — usd (skor/$) and tokens (skor/1k tok) are
    # different units and must never be sorted into one mixed list.
    rank_by_roi_usd: list[dict[str, Any]]
    rank_by_roi_tokens: list[dict[str, Any]]
    delta_leakage: list[DeltaRow]
    delta_lookahead: list[DeltaRow]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _snapshot_dir_name(case_id: str, time_mode: str, anon_mode: str) -> str:
    if anon_mode == "revealed":
        return f"{case_id}__revealed"
    if time_mode == "future_visible":
        return f"{case_id}__fv"
    return case_id


def _answer_key_name(case_id: str, time_mode: str, anon_mode: str) -> str:
    # Each angle has its OWN answer key — blind and future_visible do NOT share
    # one. They carry different anonymization coefficients (median over n_bars vs
    # n_bars+future_bars candles), so their post_t_candles are in different coef
    # spaces; scoring an fv-coef trigger against blind-coef post_t would be wrong.
    # Mirrors snapshot_builder's mode/anon-specific answer-key naming.
    if anon_mode == "revealed":
        return f"{case_id}__revealed.answer.json"
    if time_mode == "future_visible":
        return f"{case_id}__fv.answer.json"
    return f"{case_id}.answer.json"


def _read_instruction(snapshot_dir: Path) -> str | None:
    instruction_path = snapshot_dir / "instruction.txt"
    if instruction_path.exists():
        return instruction_path.read_text().strip()
    return None


# ---------------------------------------------------------------------------
# Run matrix (code prepares; orchestrator fills)
# ---------------------------------------------------------------------------


def _matrix_pairs(matrix: dict[str, list[str]]) -> list[tuple[str, str]]:
    return [(model, effort) for model, efforts in matrix.items() for effort in efforts]


def _control_pairs(
    matrix: dict[str, list[str]],
    control_models: tuple[str, ...] | list[str] | None,
    control_efforts: tuple[str, ...] | list[str] | None,
) -> list[tuple[str, str]]:
    """Matrix pairs restricted to the control scope.

    Intersected with the matrix so we never emit a (model, effort) the matrix
    doesn't define. Empty/None for either axis widens it back to the full sweep.
    """
    pairs: list[tuple[str, str]] = []
    for model, efforts in matrix.items():
        if control_models and model not in control_models:
            continue
        for effort in efforts:
            if control_efforts and effort not in control_efforts:
                continue
            pairs.append((model, effort))
    return pairs


def build_run_matrix(
    case_ids: list[str],
    *,
    matrix: dict[str, list[str]] = BENCHMARK_MATRIX,
    controls: dict[str, tuple[str, str]] = CONTROLS,
    control_models: tuple[str, ...] | list[str] | None = DEFAULT_CONTROL_MODELS,
    control_efforts: tuple[str, ...] | list[str] | None = DEFAULT_CONTROL_EFFORTS,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
) -> list[RunSpec]:
    """Enumerate RunSpecs over case × control-angle × model × effort.

    Stable run_id = "{case_id}__{time_mode}__{anon_mode}__{model}__{effort}".
    The baseline angle gets the FULL model×effort sweep; the leakage/lookahead
    controls run only on the (control_models × control_efforts) subset so the
    matrix is baseline + small δ, not controls × full matrix (PRD: controls are a
    per-points property). Pass control_models=None/[] to widen to the full sweep.

    Maps each angle to its snapshot dir (case / __fv / __revealed) and answer key.
    Does NOT build snapshots: if a required dir is missing, missing_snapshot=True
    is recorded so the orchestrator regenerates it first (via --ensure-snapshots).
    """
    base = Path(base_dir)
    specs: list[RunSpec] = []
    for case_id in case_ids:
        for control_name, (time_mode, anon_mode) in controls.items():
            pairs = (
                _matrix_pairs(matrix)
                if control_name == BASELINE_CONTROL
                else _control_pairs(matrix, control_models, control_efforts)
            )
            snapshot_dir = base / _snapshot_dir_name(case_id, time_mode, anon_mode)
            answer_key_path = base / "_answers" / _answer_key_name(case_id, time_mode, anon_mode)
            instruction = (
                _read_instruction(snapshot_dir) if time_mode == "future_visible" else None
            )
            missing = not snapshot_dir.exists()
            for model, effort in pairs:
                run_id = f"{case_id}__{time_mode}__{anon_mode}__{model}__{effort}"
                specs.append(
                    {
                        "run_id": run_id,
                        "case_id": case_id,
                        "time_mode": time_mode,
                        "anon_mode": anon_mode,
                        "control": control_name,
                        "model": model,
                        "effort": effort,
                        "snapshot_dir": str(snapshot_dir),
                        "answer_key_path": str(answer_key_path),
                        "instruction": instruction,
                        "missing_snapshot": missing,
                    }
                )
    return specs


def write_run_matrix(specs: list[RunSpec], *, base_dir: str | Path = BENCHMARK_BASE_DIR) -> Path:
    """Write the benchmark_runs.json template with empty result slots."""
    benchmark_dir = Path(base_dir) / "_benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "pricing_source_date": PRICING_SOURCE_DATE,
        "runs": [
            {
                **spec,
                # empty slots the orchestrator fills (code does not call the model):
                "analysis_output": None,
                "usage": None,
                "judge_verdict": None,
            }
            for spec in specs
        ],
        "_instructions": BENCHMARK_RUNBOOK,
    }
    path = benchmark_dir / "benchmark_runs.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def build_matrix_manifest(
    case_ids: list[str],
    *,
    control_models: tuple[str, ...] | list[str] | None = DEFAULT_CONTROL_MODELS,
    control_efforts: tuple[str, ...] | list[str] | None = DEFAULT_CONTROL_EFFORTS,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
) -> Path:
    """Convenience: build the matrix and write benchmark_runs.json."""
    specs = build_run_matrix(
        case_ids,
        control_models=control_models,
        control_efforts=control_efforts,
        base_dir=base_dir,
    )
    return write_run_matrix(specs, base_dir=base_dir)


# ---------------------------------------------------------------------------
# Cost + per-run scoring (reuses scoring.py)
# ---------------------------------------------------------------------------


def compute_cost(usage: dict[str, Any], model: str) -> float | None:
    """USD cost = (in*price_in + out*price_out)/1e6. None when pricing is None."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    in_tokens = int(usage.get("input_tokens", 0) or 0)
    out_tokens = int(usage.get("output_tokens", 0) or 0)
    return (in_tokens * pricing["input"] + out_tokens * pricing["output"]) / 1_000_000


def _roi_basis_for_model(model: str) -> str:
    """ROI basis is a property of the MODEL's pricing, not of one run's usage.

    A priced model is always "usd" (skor/$); an unpriced model (e.g. Codex) is
    always "tokens" (skor/1k tok). Deriving it from a single run's usage would
    mislabel a priced model as "tokens" whenever that run is missing usage.
    """
    return "usd" if MODEL_PRICING.get(model) is not None else "tokens"


def _compute_roi(
    aggregate: float, cost_usd: float | None, total_tokens: int, basis: str
) -> float | None:
    if basis == "usd":
        if cost_usd is not None and cost_usd > 0:
            return round(aggregate / cost_usd, 4)
        return None
    if total_tokens > 0:
        return round(aggregate / (total_tokens / 1000), 4)
    return None


def score_run(
    run_spec: RunSpec, result: RunResult, answer_key: dict[str, Any]
) -> BenchmarkRow:
    """Score one filled run by REUSING scoring.score_deterministic/combine_scores.

    trigger/invalidation are in the answer key's space (anon for anon runs, real
    for revealed) — score_run trusts run_spec.answer_key_path having selected the
    matching key, so the analyst's NUMERIC trigger/invalidation replay correctly.
    """
    analysis_output = result["analysis_output"]
    judge_verdict = result["judge_verdict"]
    usage = result.get("usage") or {}

    deterministic = scoring.score_deterministic(
        direction=analysis_output.get("direction"),
        trigger_level=analysis_output.get("trigger"),
        invalidation_level=analysis_output.get("invalidation"),
        answer_key=answer_key,
        confidence=analysis_output.get("confidence"),
    )
    record = scoring.combine_scores(
        deterministic, judge_verdict, analysis_id=analysis_output.get("analysis_id")
    )

    in_raw = usage.get("input_tokens")
    out_raw = usage.get("output_tokens")
    has_usage = in_raw is not None and out_raw is not None
    total_tokens = (int(in_raw) if in_raw is not None else 0) + (
        int(out_raw) if out_raw is not None else 0
    )
    cost_usd = compute_cost(usage, run_spec["model"]) if has_usage else None

    aggregate = record["aggregate"]
    roi_basis = _roi_basis_for_model(run_spec["model"])
    roi = _compute_roi(aggregate, cost_usd, total_tokens, roi_basis)
    dimensions = {name: dim.get("score") for name, dim in record["dimensions"].items()}

    return {
        "run_id": run_spec["run_id"],
        "case_id": run_spec["case_id"],
        "model": run_spec["model"],
        "effort": run_spec["effort"],
        "time_mode": run_spec["time_mode"],
        "anon_mode": run_spec["anon_mode"],
        "event_type": answer_key.get("event_type"),
        "aggregate": aggregate,
        "dimensions": dimensions,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "roi": roi,
        "roi_basis": roi_basis,
        "wait_case": record["wait_case"],
    }


# ---------------------------------------------------------------------------
# Aggregation + deltas + ranking
# ---------------------------------------------------------------------------


def _mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _build_groups(rows: list[BenchmarkRow]) -> list[GroupRow]:
    by_group: dict[tuple[str, str], list[BenchmarkRow]] = defaultdict(list)
    for row in rows:
        by_group[(row["model"], row["effort"])].append(row)

    groups: list[GroupRow] = []
    for (model, effort), grp in by_group.items():
        dim_means = {
            dim: _mean([r["dimensions"].get(dim) for r in grp])
            for dim in sorted(scoring.DIMENSIONS)
        }
        event_buckets: dict[str, list[float]] = defaultdict(list)
        for r in grp:
            if r["event_type"] is not None:
                event_buckets[r["event_type"]].append(r["aggregate"])
        event_types = {
            ev: round(sum(vals) / len(vals), 4) for ev, vals in event_buckets.items()
        }
        # PARTIAL MEAN: mean_cost_usd / mean_roi average only the rows that have a
        # value (runs with usage and a priced model). Rows missing usage are
        # excluded, not counted as 0 — so these means describe the priced subset of
        # the group, which can be < n. aggregate/dimensions use the full group.
        costs = [r["cost_usd"] for r in grp if r["cost_usd"] is not None]
        rois = [r["roi"] for r in grp if r["roi"] is not None]
        groups.append(
            {
                "model": model,
                "effort": effort,
                "n": len(grp),
                "aggregate": round(sum(r["aggregate"] for r in grp) / len(grp), 4),
                "dimensions": dim_means,
                "event_types": event_types,
                "mean_tokens": round(sum(r["total_tokens"] for r in grp) / len(grp), 2),
                "mean_cost_usd": round(sum(costs) / len(costs), 6) if costs else None,
                "mean_roi": round(sum(rois) / len(rois), 4) if rois else None,
                "roi_basis": _roi_basis_for_model(model),
            }
        )
    groups.sort(key=lambda g: (g["model"], g["effort"]))
    return groups


def _build_delta(
    rows: list[BenchmarkRow],
    *,
    vary: str,
    from_val: str,
    to_val: str,
    fixed: tuple[str, str],
) -> list[DeltaRow]:
    """Δ per (model, effort), measured ONLY over case_ids present in both angles.

    A missing 'to' case is excluded from the mean (not treated as 0), so a partial
    control sweep never fabricates a delta signal.
    """
    fixed_key, fixed_val = fixed
    sides: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: {"from": {}, "to": {}}
    )
    for row in rows:
        if row[fixed_key] != fixed_val:  # type: ignore[literal-required]
            continue
        group = (row["model"], row["effort"])
        if row[vary] == from_val:  # type: ignore[literal-required]
            sides[group]["from"][row["case_id"]] = row["aggregate"]
        elif row[vary] == to_val:  # type: ignore[literal-required]
            sides[group]["to"][row["case_id"]] = row["aggregate"]

    deltas: list[DeltaRow] = []
    for (model, effort), pair in sorted(sides.items()):
        common = sorted(set(pair["from"]) & set(pair["to"]))
        if not common:
            deltas.append({"model": model, "effort": effort, "n": 0, "delta": None})
            continue
        diffs = [pair["to"][cid] - pair["from"][cid] for cid in common]
        deltas.append(
            {
                "model": model,
                "effort": effort,
                "n": len(common),
                "delta": round(sum(diffs) / len(diffs), 4),
            }
        )
    return deltas


def aggregate_report(rows: list[BenchmarkRow]) -> BenchmarkReport:
    """Group baseline rows by (model, effort); compute both deltas + rankings."""
    baseline = [r for r in rows if r["time_mode"] == "blind" and r["anon_mode"] == "anon"]
    groups = _build_groups(baseline)

    rank_by_aggregate = [
        {"model": g["model"], "effort": g["effort"], "n": g["n"], "value": g["aggregate"]}
        for g in sorted(groups, key=lambda g: g["aggregate"], reverse=True)
    ]

    # ROI ranks are split by basis: usd (skor/$) and tokens (skor/1k tok) are
    # different units and would be a nonsense cross-model ranking if merged.
    def _roi_rank(basis: str) -> list[dict[str, Any]]:
        return [
            {"model": g["model"], "effort": g["effort"], "n": g["n"], "value": g["mean_roi"]}
            for g in sorted(
                (grp for grp in groups if grp["roi_basis"] == basis),
                key=lambda g: (g["mean_roi"] is not None, g["mean_roi"] or 0.0),
                reverse=True,
            )
        ]

    rank_by_roi_usd = _roi_rank("usd")
    rank_by_roi_tokens = _roi_rank("tokens")

    delta_leakage = _build_delta(
        rows, vary="anon_mode", from_val="anon", to_val="revealed", fixed=("time_mode", "blind")
    )
    delta_lookahead = _build_delta(
        rows,
        vary="time_mode",
        from_val="blind",
        to_val="future_visible",
        fixed=("anon_mode", "anon"),
    )

    return {
        "n_rows": len(rows),
        "groups": groups,
        "rank_by_aggregate": rank_by_aggregate,
        "rank_by_roi_usd": rank_by_roi_usd,
        "rank_by_roi_tokens": rank_by_roi_tokens,
        "delta_leakage": delta_leakage,
        "delta_lookahead": delta_lookahead,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _fmt(value: float | None, places: int = 4) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{places}f}"


def render_report_markdown(report: BenchmarkReport) -> str:
    lines: list[str] = []
    lines.append("# Benchmark Report — model × effort")
    lines.append("")
    lines.append(f"Scored runs: {report['n_rows']} · pricing source {PRICING_SOURCE_DATE}")
    lines.append("")

    # Main baseline table.
    lines.append("## Baseline (blind, anon) — model × effort")
    lines.append("")
    lines.append("| Model | Effort | n | Aggregate | Mean tokens | Cost (USD) | ROI | ROI basis |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for g in report["groups"]:
        lines.append(
            f"| {g['model']} | {g['effort']} | {g['n']} | {_fmt(g['aggregate'])} | "
            f"{g['mean_tokens']:.0f} | {_fmt(g['mean_cost_usd'], 6)} | "
            f"{_fmt(g['mean_roi'])} | {g['roi_basis']} |"
        )
    lines.append("")

    # Per-dimension breakdown.
    dims = sorted(scoring.DIMENSIONS)
    lines.append("## Per-dimension (mean)")
    lines.append("")
    lines.append("| Model | Effort | n | " + " | ".join(dims) + " |")
    lines.append("|---|---|---|" + "|".join(["---"] * len(dims)) + "|")
    for g in report["groups"]:
        cells = " | ".join(_fmt(g["dimensions"].get(d), 3) for d in dims)
        lines.append(f"| {g['model']} | {g['effort']} | {g['n']} | {cells} |")
    lines.append("")

    # Per-event-type breakdown.
    event_types = sorted({ev for g in report["groups"] for ev in g["event_types"]})
    lines.append("## Per-event-type (mean aggregate)")
    lines.append("")
    if event_types:
        lines.append("| Model | Effort | n | " + " | ".join(event_types) + " |")
        lines.append("|---|---|---|" + "|".join(["---"] * len(event_types)) + "|")
        for g in report["groups"]:
            cells = " | ".join(_fmt(g["event_types"].get(ev), 3) for ev in event_types)
            lines.append(f"| {g['model']} | {g['effort']} | {g['n']} | {cells} |")
    else:
        lines.append("_No event_type data._")
    lines.append("")

    # Rankings.
    lines.append("## Rank by aggregate")
    lines.append("")
    lines.append("| # | Model | Effort | n | Aggregate |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(report["rank_by_aggregate"], start=1):
        lines.append(f"| {i} | {r['model']} | {r['effort']} | {r['n']} | {_fmt(r['value'])} |")
    lines.append("")

    # ROI ranks are split by basis — usd and tokens are not comparable, so they
    # never share one sorted list.
    lines.append("## Rank by ROI (USD basis — skor/$)")
    lines.append("")
    lines.append("| # | Model | Effort | n | ROI |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(report["rank_by_roi_usd"], start=1):
        lines.append(f"| {i} | {r['model']} | {r['effort']} | {r['n']} | {_fmt(r['value'])} |")
    if not report["rank_by_roi_usd"]:
        lines.append("| — | _none_ | — | — | — |")
    lines.append("")

    lines.append("## Rank by ROI (tokens basis — skor/1k tok)")
    lines.append("")
    lines.append("Separate basis (unpriced models, e.g. Codex). NOT comparable to USD ROI.")
    lines.append("")
    lines.append("| # | Model | Effort | n | ROI |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(report["rank_by_roi_tokens"], start=1):
        lines.append(f"| {i} | {r['model']} | {r['effort']} | {r['n']} | {_fmt(r['value'])} |")
    if not report["rank_by_roi_tokens"]:
        lines.append("| — | _none_ | — | — | — |")
    lines.append("")

    # Δleakage (pretraining leakage).
    lines.append("## Δleakage (revealed − anon, blind)")
    lines.append("")
    lines.append("Positive Δleakage = revealed chart scores higher → pretraining leakage.")
    lines.append("")
    lines.append("| Model | Effort | n (common cases) | Δleakage |")
    lines.append("|---|---|---|---|")
    for d in report["delta_leakage"]:
        lines.append(f"| {d['model']} | {d['effort']} | {d['n']} | {_fmt(d['delta'])} |")
    lines.append("")

    # Δlookahead (lookahead honesty).
    lines.append("## Δlookahead (future_visible − blind, anon)")
    lines.append("")
    lines.append(
        "Δlookahead ≈ 0 on ≥5 cases → blinding (physical slicing) is unnecessary; "
        "live end_time + as-of instruction suffices. Large Δ → full blinding justified."
    )
    lines.append("")
    lines.append("| Model | Effort | n (common cases) | Δlookahead |")
    lines.append("|---|---|---|---|")
    for d in report["delta_lookahead"]:
        lines.append(f"| {d['model']} | {d['effort']} | {d['n']} | {_fmt(d['delta'])} |")
    lines.append("")

    return "\n".join(lines)


def write_report(
    report: BenchmarkReport, *, base_dir: str | Path = BENCHMARK_BASE_DIR
) -> tuple[Path, Path]:
    benchmark_dir = Path(base_dir) / "_benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    md_path = benchmark_dir / "report.md"
    json_path = benchmark_dir / "report.json"
    md_path.write_text(render_report_markdown(report) + "\n")
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    return md_path, json_path


# ---------------------------------------------------------------------------
# Ingest (score filled results -> report)
# ---------------------------------------------------------------------------


_SPEC_KEYS: tuple[str, ...] = (
    "run_id",
    "case_id",
    "time_mode",
    "anon_mode",
    "control",
    "model",
    "effort",
    "snapshot_dir",
    "answer_key_path",
    "instruction",
    "missing_snapshot",
)


def _load_specs_from_manifest(base_dir: str | Path) -> dict[str, RunSpec] | None:
    """Return {run_id: RunSpec} from benchmark_runs.json, or None if absent.

    benchmark_runs.json is the single source of truth for specs; ingest matches
    results/<run_id>.json against it by run_id.
    """
    manifest_path = Path(base_dir) / "_benchmark" / "benchmark_runs.json"
    if not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text())
    specs: dict[str, RunSpec] = {}
    for run in data.get("runs", []):
        specs[run["run_id"]] = {key: run[key] for key in _SPEC_KEYS}  # type: ignore[typeddict-item]
    return specs


def _spec_from_run_id(run_id: str, *, base_dir: str | Path) -> RunSpec:
    """Fallback spec reconstruction when no benchmark_runs.json exists on disk.

    Prefer the manifest (see _load_specs_from_manifest); this positional parse is
    only the no-manifest escape hatch and assumes no field contains '__'.
    """
    parts = run_id.split("__")
    if len(parts) != 5:
        raise ValueError(
            f"Malformed run_id {run_id!r}: expected "
            "'case__time_mode__anon_mode__model__effort'"
        )
    case_id, time_mode, anon_mode, model, effort = parts
    base = Path(base_dir)
    snapshot_dir = base / _snapshot_dir_name(case_id, time_mode, anon_mode)
    return {
        "run_id": run_id,
        "case_id": case_id,
        "time_mode": time_mode,
        "anon_mode": anon_mode,
        "control": _CONTROL_BY_ANGLE.get((time_mode, anon_mode), "custom"),
        "model": model,
        "effort": effort,
        "snapshot_dir": str(snapshot_dir),
        "answer_key_path": str(base / "_answers" / _answer_key_name(case_id, time_mode, anon_mode)),
        "instruction": _read_instruction(snapshot_dir)
        if time_mode == "future_visible"
        else None,
        "missing_snapshot": not snapshot_dir.exists(),
    }


def ingest(
    results_dir: str | Path, *, base_dir: str | Path = BENCHMARK_BASE_DIR
) -> BenchmarkReport:
    """Load results/<run_id>.json, score each filled run, aggregate, write report.

    Specs come from benchmark_runs.json (single source of truth); run_id is only
    the key that pairs a result file to its spec. Falls back to reconstructing the
    spec from run_id only when no manifest exists on disk.
    """
    results_path = Path(results_dir)
    if not results_path.exists():
        raise FileNotFoundError(f"results dir not found: {results_path}")

    manifest_specs = _load_specs_from_manifest(base_dir)

    rows: list[BenchmarkRow] = []
    for result_file in sorted(results_path.glob("*.json")):
        raw = json.loads(result_file.read_text())
        if raw.get("analysis_output") is None or raw.get("judge_verdict") is None:
            continue  # unfilled slot
        run_id = result_file.stem
        if manifest_specs is not None:
            spec = manifest_specs.get(run_id)
            if spec is None:
                print(
                    f"[benchmark] WARN: {run_id} has no entry in benchmark_runs.json "
                    "— skipping (rebuild the matrix to include it)"
                )
                continue
        else:
            spec = _spec_from_run_id(run_id, base_dir=base_dir)
        answer_key = json.loads(Path(spec["answer_key_path"]).read_text())
        result: RunResult = {
            "analysis_output": raw["analysis_output"],
            "usage": raw.get("usage") or {},
            "judge_verdict": raw["judge_verdict"],
        }
        rows.append(score_run(spec, result, answer_key))

    report = aggregate_report(rows)
    md_path, json_path = write_report(report, base_dir=base_dir)
    print(f"[benchmark] scored {len(rows)} runs → {md_path} , {json_path}")
    return report


# ---------------------------------------------------------------------------
# Ensure snapshots (regenerate the benchmark's own blind/fv/revealed dirs)
#
# The benchmark owns ALL its snapshots under BENCHMARK_BASE_DIR — it does NOT
# rely on data/eval/case_0X built by Phase 3, because that namespace is shared
# with the Phase 2 probe (case_01..03, DIFFERENT instruments). Regenerating from
# the ground-truth definitions into a dedicated dir removes any contamination.
# ---------------------------------------------------------------------------


def _load_benchmark_cases_and_answers(
    case_ids: list[str] | None, *, dry_run: bool, answers_path: Path | None
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    from scripts.eval.build_eval_set import DEFAULT_ANSWERS_PATH  # noqa: PLC0415
    from scripts.eval.ground_truth_cases import (  # noqa: PLC0415
        GROUND_TRUTH_CASES,
        load_answer_key,
        make_placeholder_answers,
    )

    cases = [c for c in GROUND_TRUTH_CASES if case_ids is None or c["case_id"] in case_ids]
    answers = (
        make_placeholder_answers()
        if dry_run
        else load_answer_key(answers_path or DEFAULT_ANSWERS_PATH)
    )
    return cases, answers


def _answer_extra(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": answer["event_type"],
        "realized_direction": answer["realized_direction"],
        "decisive": answer["decisive"],
    }


def ensure_blind_snapshots(
    case_ids: list[str] | None = None,
    *,
    dry_run: bool = False,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
    answers_path: Path | None = None,
) -> list[str]:
    """Build any missing baseline (blind, anon) snapshots into the benchmark dir."""
    cases, answers = _load_benchmark_cases_and_answers(
        case_ids, dry_run=dry_run, answers_path=answers_path
    )
    client: Any = DryRunClient() if dry_run else None
    base = Path(base_dir)
    built: list[str] = []
    for case in cases:
        case_id = case["case_id"]
        if (base / case_id).exists():
            continue
        build_snapshot(
            symbol=case["symbol"],
            timeframe=case["timeframe"],
            cutoff=case["cutoff"],
            n_bars=case["n_bars"],
            mode="blind",
            case_id=case_id,
            client=client,
            ground_truth=answers[case_id]["ground_truth"],
            answer_extra=_answer_extra(answers[case_id]),
            include_post_t_candles=True,
            base_dir=base,
        )
        built.append(case_id)
    return built


def ensure_fv_snapshots(
    case_ids: list[str] | None = None,
    *,
    dry_run: bool = False,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
    answers_path: Path | None = None,
    future_bars: int = 20,
) -> list[str]:
    """Build any missing (future_visible, anon) snapshots — the lookahead control.

    Without this the lookahead angle has NO generation path and Δlookahead comes
    out empty. Phase 3 build_eval_set builds only blind, so the benchmark must
    generate __fv itself from the same ground-truth definitions.
    """
    cases, answers = _load_benchmark_cases_and_answers(
        case_ids, dry_run=dry_run, answers_path=answers_path
    )
    client: Any = DryRunClient() if dry_run else None
    base = Path(base_dir)
    built: list[str] = []
    for case in cases:
        case_id = case["case_id"]
        if (base / f"{case_id}__fv").exists():
            continue
        build_snapshot(
            symbol=case["symbol"],
            timeframe=case["timeframe"],
            cutoff=case["cutoff"],
            n_bars=case["n_bars"],
            mode="future_visible",
            case_id=case_id,
            future_bars=future_bars,
            client=client,
            ground_truth=answers[case_id]["ground_truth"],
            answer_extra=_answer_extra(answers[case_id]),
            include_post_t_candles=True,
            base_dir=base,
        )
        built.append(case_id)
    return built


def ensure_revealed_snapshots(
    case_ids: list[str] | None = None,
    *,
    dry_run: bool = False,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
    answers_path: Path | None = None,
) -> list[str]:
    """Build any missing __revealed snapshots — the leakage control (reveal=True)."""
    cases, answers = _load_benchmark_cases_and_answers(
        case_ids, dry_run=dry_run, answers_path=answers_path
    )
    client: Any = DryRunClient() if dry_run else None
    base = Path(base_dir)
    built: list[str] = []
    for case in cases:
        case_id = case["case_id"]
        if (base / f"{case_id}__revealed").exists():
            continue
        build_snapshot(
            symbol=case["symbol"],
            timeframe=case["timeframe"],
            cutoff=case["cutoff"],
            n_bars=case["n_bars"],
            mode="blind",
            case_id=case_id,
            client=client,
            ground_truth=answers[case_id]["ground_truth"],
            answer_extra=_answer_extra(answers[case_id]),
            include_post_t_candles=True,
            reveal=True,
            base_dir=base,
        )
        built.append(case_id)
    return built


def ensure_snapshots(
    case_ids: list[str] | None = None,
    *,
    dry_run: bool = False,
    base_dir: str | Path = BENCHMARK_BASE_DIR,
    answers_path: Path | None = None,
) -> dict[str, list[str]]:
    """Ensure all three angles (blind, future_visible, revealed) exist for the set.

    This closes the lookahead generation gap (future_visible) AND keeps the whole
    benchmark snapshot set in one isolated dir, immune to the probe namespace.
    """
    return {
        "blind": ensure_blind_snapshots(
            case_ids, dry_run=dry_run, base_dir=base_dir, answers_path=answers_path
        ),
        "future_visible": ensure_fv_snapshots(
            case_ids, dry_run=dry_run, base_dir=base_dir, answers_path=answers_path
        ),
        "revealed": ensure_revealed_snapshots(
            case_ids, dry_run=dry_run, base_dir=base_dir, answers_path=answers_path
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_csv(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6 benchmark runner")
    parser.add_argument("--dry-run", action="store_true", help="Use stub client (no network)")
    parser.add_argument(
        "--ensure-snapshots",
        action="store_true",
        help="Regenerate missing blind/future_visible/revealed snapshots first",
    )
    parser.add_argument(
        "--ingest",
        type=str,
        default=None,
        metavar="RESULTS_DIR",
        help="Score filled results/<run_id>.json and write report.{md,json}",
    )
    parser.add_argument(
        "--full-controls",
        action="store_true",
        help="Run the controls over the FULL model×effort sweep (default: subset)",
    )
    parser.add_argument(
        "--control-models",
        type=str,
        default=None,
        help="Comma-separated model ids for the controls (default: opus)",
    )
    parser.add_argument(
        "--control-efforts",
        type=str,
        default=None,
        help="Comma-separated effort levels for the controls (default: high)",
    )
    parser.add_argument(
        "--base-dir", type=Path, default=BENCHMARK_BASE_DIR, help="Benchmark base directory"
    )
    args = parser.parse_args()

    from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES  # noqa: PLC0415

    case_ids = [c["case_id"] for c in GROUND_TRUTH_CASES]

    if args.ingest is not None:
        ingest(args.ingest, base_dir=args.base_dir)
        return

    if args.ensure_snapshots:
        built = ensure_snapshots(case_ids, dry_run=args.dry_run, base_dir=args.base_dir)
        for angle, ids in built.items():
            print(f"[benchmark] ensured {len(ids)} {angle} snapshot(s): {ids}")

    if args.full_controls:
        control_models: tuple[str, ...] | None = None
        control_efforts: tuple[str, ...] | None = None
    else:
        control_models = _parse_csv(args.control_models) or DEFAULT_CONTROL_MODELS
        control_efforts = _parse_csv(args.control_efforts) or DEFAULT_CONTROL_EFFORTS

    path = build_matrix_manifest(
        case_ids,
        control_models=control_models,
        control_efforts=control_efforts,
        base_dir=args.base_dir,
    )
    print(f"[benchmark] run matrix written to: {path}")
    if args.dry_run:
        print("[benchmark] dry-run complete — no network calls made")


if __name__ == "__main__":
    main()
