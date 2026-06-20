"""Crash-safe end-to-end orchestrator for the Phase 4 eval benchmark."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import shutil
import signal
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterable

from jsonschema import validate as validate_json

from scripts.eval import benchmark, scoring
from scripts.eval.ground_truth_cases import GROUND_TRUTH_CASES, load_answer_key, validate_event_coverage
from scripts.eval.runtime_adapters import (
    ClaudeRuntimeAdapter,
    RuntimeAdapter,
    RuntimeRequest,
    RuntimeExecutionError,
    RuntimeUnavailable,
    adapter_for_model,
)

SCHEMA_VERSION = 1
SCHEMA_DIR = Path(__file__).with_name("schemas")
ANALYSIS_SCHEMA = SCHEMA_DIR / "analysis_output.schema.json"
JUDGE_SCHEMA = SCHEMA_DIR / "judge_verdict.schema.json"
JUDGE_MODEL = "claude-opus-4-8"
CANDLES_FILENAME = "candles.json"
STATUSES = {"pending", "running", "succeeded", "failed", "skipped"}
EXIT_OK, EXIT_CONFIG, EXIT_PARTIAL, EXIT_INTERRUPT = 0, 2, 3, 130


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def file_lock(path: Path) -> Generator[None, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path.with_suffix(path.suffix + ".lock")), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def manifest_fingerprint(specs: Iterable[benchmark.RunSpec]) -> str:
    stable = [{key: spec[key] for key in sorted(spec) if key != "missing_snapshot"} for spec in specs]
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid_result(path: Path) -> tuple[bool, bool]:
    """Return (valid analyst checkpoint, complete result)."""
    try:
        raw = json.loads(path.read_text())
        validate_json(raw["analysis_output"], json.loads(ANALYSIS_SCHEMA.read_text()))
        analyst = True
        verdict = raw.get("judge_verdict")
        if verdict is None:
            return analyst, False
        validate_json(verdict, json.loads(JUDGE_SCHEMA.read_text()))
        return analyst, True
    except (OSError, KeyError, TypeError, ValueError):
        return False, False
    except Exception:  # jsonschema.ValidationError without exposing payload
        return False, False


class StateStore:
    def __init__(self, path: Path, results_dir: Path):
        self.path = path
        self.results_dir = results_dir

    def initialize(
        self,
        specs: list[benchmark.RunSpec],
        *,
        reset: bool = False,
        fingerprint_specs: list[benchmark.RunSpec] | None = None,
    ) -> None:
        fingerprint = manifest_fingerprint(fingerprint_specs or specs)
        with file_lock(self.path):
            current = json.loads(self.path.read_text()) if self.path.exists() and not reset else None
            if current and current.get("manifest_fingerprint") != fingerprint:
                raise ValueError("manifest fingerprint mismatch; use --reset-state after reviewing the new matrix")
            runs = current.get("runs", {}) if current else {}
            for spec in specs:
                runs.setdefault(spec["run_id"], self._new_record(spec))
            state = {
                "schema_version": SCHEMA_VERSION,
                "manifest_fingerprint": fingerprint,
                "updated_at": _now(),
                "runs": runs,
            }
            atomic_write_json(self.path, state)
        self.reconcile(specs)

    @staticmethod
    def _new_record(spec: benchmark.RunSpec) -> dict[str, Any]:
        return {
            "status": "pending", "stage": "analyst", "next_stage": "analyst", "attempt": 0,
            "provider": "codex" if spec["model"] == "codex" else "claude",
            "started_at": None, "finished_at": None, "error": None,
        }

    def read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

    def reconcile(self, specs: Iterable[benchmark.RunSpec]) -> None:
        with file_lock(self.path):
            state = self.read()
            for spec in specs:
                record = state["runs"][spec["run_id"]]
                result_path = self.results_dir / f'{spec["run_id"]}.json'
                analyst, complete = _valid_result(result_path) if result_path.exists() else (False, False)
                if complete:
                    record.update(status="succeeded", stage="judge", next_stage=None, finished_at=record.get("finished_at") or _now(), error=None)
                elif analyst:
                    record.update(status="pending", stage="judge", next_stage="judge", error=None)
                elif result_path.exists():
                    record.update(status="failed", error={"type": "corrupt_result", "message": "result checkpoint is invalid"}, finished_at=_now())
                elif record["status"] == "running":
                    record.update(status="pending", next_stage=record.get("stage", "analyst"), error={"type": "stale_running", "message": "recovered interrupted run"})
            state["updated_at"] = _now()
            atomic_write_json(self.path, state)

    def claim(self, run_id: str, max_attempts: int) -> str | None:
        with file_lock(self.path):
            state = self.read()
            record = state["runs"][run_id]
            if record["status"] in {"succeeded", "skipped", "running"} or record["attempt"] >= max_attempts:
                return None
            stage = record.get("next_stage") or record.get("stage") or "analyst"
            record.update(status="running", stage=stage, attempt=record["attempt"] + 1, started_at=_now(), finished_at=None, error=None)
            state["updated_at"] = _now()
            atomic_write_json(self.path, state)
            return str(stage)

    def update(self, run_id: str, **changes: Any) -> None:
        if "status" in changes and changes["status"] not in STATUSES:
            raise ValueError(f'invalid state status: {changes["status"]}')
        with file_lock(self.path):
            state = self.read()
            state["runs"][run_id].update(changes)
            state["updated_at"] = _now()
            atomic_write_json(self.path, state)


def _safe_copy(source: Path, destination: Path) -> None:
    root = source.resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"snapshot root must be a real directory: {source}")
    for item in source.rglob("*"):
        if item.is_symlink() or not item.resolve().is_relative_to(root):
            raise ValueError(f"snapshot contains symlink/path escape: {item.name}")
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


@contextmanager
def analyst_root(spec: benchmark.RunSpec) -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix="wyckoff-analyst-") as raw:
        root = Path(raw)
        _safe_copy(Path(spec["snapshot_dir"]), root)
        shutil.copy2(ANALYSIS_SCHEMA, root / ANALYSIS_SCHEMA.name)
        yield root


@contextmanager
def judge_root() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix="wyckoff-judge-") as raw:
        root = Path(raw)
        shutil.copy2(JUDGE_SCHEMA, root / JUDGE_SCHEMA.name)
        yield root


def analyst_prompt(spec: benchmark.RunSpec, root: Path) -> str:
    # The isolated analyst runs with NO tools (Claude `--tools ""` disables EVERY
    # built-in tool, Read included; Codex runs in a read-only sandbox and performs
    # no read step), so it cannot open snapshot files itself. Embedding candles.json
    # directly in the prompt is the only provider-neutral way to hand every model
    # the SAME input — a bare filename list leaves the analyst with nothing to
    # analyze. chart.png is deliberately NOT delivered: it is binary, has no fair
    # cross-provider prompt-attach path, and feeding it to only one provider would
    # break model comparability; candles.json carries the identical OHLCV the chart
    # renders.
    candles_path = root / CANDLES_FILENAME
    if not candles_path.is_file():
        raise RuntimeExecutionError(f"snapshot missing {CANDLES_FILENAME} under {root}")
    candles = candles_path.read_text().strip()
    instruction = spec.get("instruction") or "Analyze only the frozen as-of snapshot."
    return (
        "You are an isolated Wyckoff analyst with NO tools and NO network access. "
        "Analyze ONLY the anonymized OHLCV data embedded below. Describe price/volume "
        "behavior before labels; return one scenario with direction, numeric or null "
        "trigger/invalidation, confidence 0..1, structure, phase, and event. Do not "
        "infer identity or calendar date. " + instruction
        + f"\n\nOHLCV candles ({CANDLES_FILENAME}):\n" + candles
    )


class StartLimiter:
    def __init__(self, interval: float):
        self.interval = max(0.0, interval)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self.interval - (time.monotonic() - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


def _sum_usage(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    return {key: int(first.get(key, 0)) + int(second.get(key, 0)) for key in ("input_tokens", "output_tokens")}


def _error_record(exc: Exception) -> dict[str, Any]:
    record: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    if isinstance(exc, RuntimeExecutionError):
        record["exit_code"] = exc.exit_code
        record["stderr_tail"] = exc.stderr_tail[-2000:]
    return record


async def execute_run(
    spec: benchmark.RunSpec, store: StateStore, results_dir: Path, *, adapters: dict[str, RuntimeAdapter],
    limiter: StartLimiter, timeout: float, max_attempts: int, stop: asyncio.Event | None = None,
) -> None:
    # max_attempts is spent WITHIN this call: a non-terminal failure re-claims and
    # retries the run in-process (re-using the analyst checkpoint when the judge is
    # the only thing left), so a single invocation honours the configured attempt
    # budget and only leaves `pending` behind on interrupt/crash — not as a hidden
    # "retry on next run". claim() increments attempt and refuses to re-claim once
    # the budget is exhausted, so the loop is bounded.
    run_id = spec["run_id"]
    result_path = results_dir / f"{run_id}.json"
    while True:
        if stop is not None and stop.is_set():
            return
        stage = store.claim(run_id, max_attempts)
        if stage is None:
            return
        try:
            existing = json.loads(result_path.read_text()) if stage == "judge" and result_path.exists() else None
            if existing is None:
                with analyst_root(spec) as root:
                    await limiter.wait()
                    response = await adapters[spec["model"]].run(RuntimeRequest(
                        analyst_prompt(spec, root), root, root / ANALYSIS_SCHEMA.name,
                        spec["model"], spec["effort"], timeout,
                    ))
                    validate_json(response.output, json.loads(ANALYSIS_SCHEMA.read_text()))
                    existing = {"analysis_output": response.output, "usage": response.usage, "usage_by_stage": {"analyst": response.usage}, "judge_verdict": None}
                    atomic_write_json(result_path, existing)
                    store.update(run_id, stage="judge", next_stage="judge")
            answer = json.loads(Path(spec["answer_key_path"]).read_text())
            payload = scoring.prepare_judge_input(existing["analysis_output"], answer)
            with judge_root() as root:
                await limiter.wait()
                response = await adapters["__judge__"].run(RuntimeRequest(
                    json.dumps(payload, separators=(",", ":")), root, root / JUDGE_SCHEMA.name,
                    JUDGE_MODEL, "high", timeout,
                ))
                validate_json(response.output, json.loads(JUDGE_SCHEMA.read_text()))
            analyst_usage = existing.get("usage_by_stage", {}).get("analyst", existing.get("usage", {}))
            existing.update(judge_verdict=response.output, usage_by_stage={"analyst": analyst_usage, "judge": response.usage}, usage=_sum_usage(analyst_usage, response.usage))
            atomic_write_json(result_path, existing)
            store.update(run_id, status="succeeded", stage="judge", next_stage=None, finished_at=_now(), error=None)
            return
        except Exception as exc:
            record = store.read()["runs"][run_id]
            terminal = record["attempt"] >= max_attempts
            store.update(run_id, status="failed" if terminal else "pending", next_stage=record.get("stage", stage), finished_at=_now() if terminal else None, error=_error_record(exc))
            if terminal:
                return
            # non-terminal: loop re-claims (attempt++) and retries this run in-process


def _csv(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    return {part.strip() for value in values for part in value.split(",") if part.strip()}


def select_specs(specs: list[benchmark.RunSpec], *, cases: set[str] | None, models: set[str] | None, efforts: set[str] | None) -> list[benchmark.RunSpec]:
    return [spec for spec in specs if (not cases or spec["case_id"] in cases) and (not models or spec["model"] in models) and (not efforts or spec["effort"] in efforts)]


async def orchestrate(args: argparse.Namespace, *, injected_adapters: dict[str, RuntimeAdapter] | None = None) -> int:
    answers = load_answer_key(args.answers_path)
    validate_event_coverage(answers=answers)
    case_ids = [str(case["case_id"]) for case in GROUND_TRUTH_CASES]
    in_memory = benchmark.build_run_matrix(case_ids, base_dir=args.base_dir)
    selected = select_specs(in_memory, cases=_csv(args.case), models=_csv(args.model), efforts=_csv(args.effort))
    if not selected:
        raise ValueError("selectors produced an empty run scope")

    adapters = injected_adapters or {model: adapter_for_model(model) for model in {spec["model"] for spec in selected}}
    adapters["__judge__"] = adapters.get("__judge__", ClaudeRuntimeAdapter())
    unavailable: dict[str, str] = {}
    for model in sorted({spec["model"] for spec in selected}):
        try:
            await adapters[model].preflight(model, next(spec["effort"] for spec in selected if spec["model"] == model))
        except RuntimeUnavailable as exc:
            unavailable[model] = str(exc)
    try:
        await adapters["__judge__"].preflight(JUDGE_MODEL, "high")
    except RuntimeUnavailable as exc:
        unavailable["__judge__"] = str(exc)

    if args.dry_run:
        counts = Counter("unavailable" if spec["model"] in unavailable else "planned" for spec in selected)
        print(json.dumps({"scope": len(selected), "counts": counts, "unavailable": unavailable}, indent=2, default=dict))
        return EXIT_OK

    available_cases = sorted({
        spec["case_id"]
        for spec in selected
        if spec["model"] not in unavailable and "__judge__" not in unavailable
    })
    if available_cases:
        benchmark.ensure_snapshots(available_cases, base_dir=args.base_dir, answers_path=args.answers_path)
    manifest_path = benchmark.build_matrix_manifest(case_ids, base_dir=args.base_dir)
    manifest = json.loads(manifest_path.read_text())
    all_specs = [{key: run[key] for key in benchmark._SPEC_KEYS} for run in manifest["runs"]]
    selected = select_specs(all_specs, cases=_csv(args.case), models=_csv(args.model), efforts=_csv(args.effort))
    for spec in selected:
        if spec["model"] in unavailable or "__judge__" in unavailable:
            continue
        if not Path(spec["snapshot_dir"]).is_dir():
            raise FileNotFoundError(f'missing snapshot directory for {spec["run_id"]}')
        if not Path(spec["answer_key_path"]).is_file():
            raise FileNotFoundError(f'missing angle answer key for {spec["run_id"]}')
    benchmark_dir = args.base_dir / "_benchmark"
    results_dir = benchmark_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    store = StateStore(benchmark_dir / "orchestrator_state.json", results_dir)
    store.initialize(selected, reset=args.reset_state, fingerprint_specs=all_specs)
    for spec in selected:
        if spec["model"] in unavailable or "__judge__" in unavailable:
            store.update(spec["run_id"], status="skipped", finished_at=_now(), error={"type": "unavailable", "message": unavailable.get(spec["model"], unavailable.get("__judge__"))})

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    semaphore = asyncio.Semaphore(args.max_concurrency)
    limiter = StartLimiter(args.min_start_interval)

    async def worker(spec: benchmark.RunSpec) -> None:
        if spec["model"] in unavailable:
            return
        async with semaphore:
            if stop.is_set():
                return
            await execute_run(spec, store, results_dir, adapters=adapters, limiter=limiter, timeout=args.timeout, max_attempts=args.max_attempts, stop=stop)

    await asyncio.gather(*(worker(spec) for spec in selected), return_exceptions=True)
    if stop.is_set():
        return EXIT_INTERRUPT
    ingest_error: str | None = None
    if not args.no_ingest and any(_valid_result(path)[1] for path in results_dir.glob("*.json")):
        try:
            benchmark.ingest(results_dir, base_dir=args.base_dir)
        except Exception as exc:
            ingest_error = f"{type(exc).__name__}: {str(exc)[:1000]}"
    state = store.read()["runs"]
    scoped = {spec["run_id"]: state[spec["run_id"]] for spec in selected}
    counts = Counter(record["status"] for record in scoped.values())
    failures = [{"run_id": run_id, "stage": record["stage"]} for run_id, record in scoped.items() if record["status"] in {"failed", "pending"}]
    print(json.dumps({"scope": len(scoped), "counts": counts, "attempts": sum(record["attempt"] for record in scoped.values()), "state": str(store.path), "results": str(results_dir), "report": str(benchmark_dir / "report.md"), "failures": failures, "ingest_error": ingest_error}, indent=2, default=dict))
    return EXIT_PARTIAL if failures or ingest_error else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 4 end-to-end eval orchestrator")
    parser.add_argument("--answers-path", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, default=benchmark.BENCHMARK_BASE_DIR)
    parser.add_argument("--case", action="append")
    parser.add_argument("--model", action="append")
    parser.add_argument("--effort", action="append")
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--min-start-interval", type=float, default=1.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-ingest", action="store_true")
    parser.add_argument("--reset-state", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.max_concurrency < 1 or args.max_attempts < 1 or args.timeout <= 0 or args.min_start_interval < 0:
        parser.error("concurrency/attempts/timeout must be positive and interval non-negative")
    try:
        raise SystemExit(asyncio.run(orchestrate(args)))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
        raise SystemExit(EXIT_CONFIG) from exc


if __name__ == "__main__":
    main()
