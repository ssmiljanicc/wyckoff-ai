# Faza 3 — Trading Simulation & ML Extensions

## Problem Statement

After Faza 2, the skill can autonomously analyze any crypto chart, but it remains a **single-shot analysis tool**. It cannot:

- Track virtual positions across multiple analysis sessions to measure scenario-quality over time
- Scan multiple assets at once to surface ranked setups (the natural multi-asset workflow Wyckoff practitioners follow)
- Generate explicit buy/sell signals (even simulated) that can be logged and backtested
- Learn from historical labeled examples — every analysis is rule-based via the wiki, with no feedback loop

This makes the skill useful for one-off analysis but limited as a Wyckoff practice and research tool. A user wanting to test "would buying on agent's spring + retest signals over the past 5 years have been profitable?" has no path.

## Evidence

- Faza 1 and Faza 2 deliver capabilities never planned in the original `naiemk/wyckoff-ai` repo — this is explicit internal extension, not upstream contribution
- Existing distilled refs (`crypto_adaptations.md` §10–13, `bruce_fraser_stockcharts.md`) describe campaign-level multi-month logic that benefits from tracking, not single-shot analysis
- Standard time-series ML pipelines (e.g., the `razni-tutorijali/ml-fitness-tracker` reference repo) demonstrate the same data shape (multi-channel time series) can be classified with off-the-shelf scikit-learn — applies directly to OHLCV
- Wyckoff Analytics archives explicitly note that **failed signals are highly informative** (`uncommon_concepts.md` §12) — but the existing skill has no mechanism to track and learn from signal outcomes

## Proposed Solution

Two parallel extensions:

**1. Trading Simulation MCP layer (M5):**
- Virtual portfolio MCP — track simulated positions, cash, P&L per session
- Multi-symbol scanner MCP — scan top-N crypto universe for Wyckoff setups
- Signal logger MCP — record agent's calls with entry/invalidation/target, replay outcomes
- Backtest runner MCP — apply scenario rules to historical OHLCV, report stats

**2. ML pipeline (M6):**
- Historical scenario annotation — label past 5 years of major-asset OHLCV with phase + event tags (LLM-assisted, human-validated)
- Feature engineering pipeline — OHLCV → rolling stats + FFT cycles + volume-relative + body/range ratios
- Baseline classifier — RandomForest / SVM mapping features → phase classification
- Classifier MCP server — expose `classify_phase(symbol, tf)` for the agent

**3. Skill extension:**
- Add fourth mode: **Signal/Trading mode** — output format includes entry zone, invalidation, target, virtual position size
- Existing scenario/concept/diagnostic modes preserved unchanged

## Key Hypothesis

We believe **a trading simulation layer + ML phase classifier** will **transform the skill from a single-shot analyst into a complete Wyckoff research and practice environment** for **practitioners who want to measure their own and the agent's reasoning quality over time**. We'll know we're right when **a user can run a full strategy ("long on spring + retest, short on UTAD + LPSY") backtest against past 3 years of BTC AND the agent surfaces ML-classified phase identifications consistent with manual reads on out-of-sample data**.

## What We're NOT Building

- **Real money trading** — virtual portfolio only, no exchange auth, no order placement
- **High-frequency / intraday signal generation** — agent operates on 1h+ timeframes
- **Multi-asset class beyond crypto** — extension stays crypto-focused
- **Embedding-based similarity search** — text captions and OHLCV features are enough; embeddings are a future optimization, not a Phase 3 requirement
- **Deep learning (LSTM, Transformer)** for classification — baseline RandomForest first; revisit DL only if baseline ceiling is too low
- **Public API / SaaS offering** — internal tool, no productization

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Virtual portfolio P&L tracking | Records every agent signal with entry/exit/SL/TP; reproducible across sessions | MCP state persists in `data/portfolios/<name>.json` |
| Multi-symbol scan throughput | Top 20 alts scanned in < 60s for one timeframe | Benchmark log |
| Annotated training set size | ≥ 500 labeled (symbol, window, phase) tuples across major assets | `data/annotations/manifest.json` |
| ML classifier accuracy (baseline) | ≥ 60% on held-out test set (4-class: A/B/C/D-E) | scikit-learn classification_report |
| Backtest reproducibility | Same input rules + dates produce same P&L over 100 runs | Hash check on output |

## Open Questions

- [ ] Backtest fidelity: simple bar-close fill assumption, or model slippage/spread? (Probably start simple)
- [ ] Annotation source: LLM-only labels, or LLM + manual spot-check + book examples?
- [ ] ML feature scope: just OHLCV-derived, or include caption embeddings from Faza 1 Vision pass?
- [ ] Portfolio scope: single session, or multi-session with persistence and reset commands?
- [ ] Should this entire phase live in a separate repo (clean "no upstream contribution") or stay in this repo after the unfork?

---

## Users & Context

**Primary User**
- **Who**: Same Wyckoff practitioner as Faza 1+2, now also operating in **research mode**
- **Current behavior** (post-Faza-2): asks for single-symbol analysis on demand
- **Trigger**: Wants to test a strategy idea across history, or scan dozens of alts before deep-diving on one
- **Success state**: Runs `Scan top 30 alts for accumulation setups, then for the top 3, build full scenarios with backtest stats`

**Job to Be Done**

When **I want to test or scale Wyckoff analysis**, I want to **let the agent scan multiple markets and simulate trades**, so I can **iterate on my methodology with concrete P&L feedback instead of subjective recall**.

**Non-Users**
- Faza 1+2 users who only ever do one-off analysis (Phase 3 is opt-in via new mode)
- Anyone wanting actual money trading (explicit non-goal)
- Bot framework developers (this isn't a signal-feed SaaS)

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Virtual portfolio MCP (state per named portfolio) | Foundation for all measurement |
| Must | Signal logger MCP (record agent calls with metadata) | Without log, no learning loop |
| Must | Multi-symbol scanner MCP (parallelized OHLCV pulls + lightweight pattern checks) | Multi-asset workflow is the unlock |
| Must | Skill extension: Signal/Trading mode + output contract | Tells agent how to behave when user wants signals |
| Must | Historical annotation pipeline (LLM + manual validation) | Training data is the bottleneck |
| Must | Baseline RandomForest classifier on phase tags | Validates the ML thesis cheaply |
| Should | Backtest runner MCP (rule-based, deterministic) | Adds research dimension |
| Should | Classifier MCP exposing `classify_phase()` | Agent uses ML predictions as additional evidence |
| Could | Caption-embedding similarity search (find historical analogs) | Powerful but defer until baseline is in place |
| Could | Sector-level scanner (DeFi index, exchange tokens) | Extends scanner; depends on sector index data sources |
| Won't | Real-money exchange integration | Hard non-goal |
| Won't | Deep learning models | Premature; baseline first |

### MVP Scope

Minimum viable Phase 3:

1. Virtual portfolio MCP — supports open/close/list positions, persistent state
2. Signal logger MCP — records every signal with metadata, supports replay
3. Scanner MCP — scans top 20 alts on one timeframe, returns ranked list of candidates by simple rule (e.g., "in a range for ≥4 weeks")
4. Annotation set of ≥ 100 labeled windows from major-asset historical data
5. Baseline classifier with ≥ 60% accuracy on 4-class phase task
6. Skill update: Signal/Trading mode contract documented and integrated

### User Flow

```
User → "Scan top 20 alts for accumulation setups in last 8 weeks"
       ↓
Skill enters Signal mode, calls scanner MCP
       ↓
Scanner pulls OHLCV for 20 symbols → applies lightweight rule (range > 4w, declining volume)
       ↓
Returns ranked list with each symbol's classifier score
       ↓
For top 3: agent fetches full chart + runs scenario mode + logs signal in portfolio MCP
       ↓
Output: 3 full scenarios + portfolio state updated with virtual positions tagged "candidate"
```

---

## Technical Approach

**Feasibility**: MEDIUM (highest complexity phase)

**Architecture Notes**

```
Trading MCP layer (new):
  - portfolio_server.py    → state in data/portfolios/<name>.json
  - signal_logger.py       → append-only log in data/signals/<date>.jsonl
  - scanner.py             → parallelizes OHLCV calls from Faza-2 MCP
  - backtest_runner.py     → reads signals + OHLCV, computes P&L stats

ML pipeline (new):
  - data/annotations/      ← labeled training data
  - scripts/ml/
    - annotate.py          ← LLM-assisted labeling with manual review
    - features.py          ← OHLCV → engineered features (rolling, FFT, etc.)
    - train.py             ← scikit-learn classifier
    - classifier_mcp.py    ← serves predictions

Skill update:
  - SKILL.md adds §"Signal mode workflow"
  - scenarios/signal-mode-contract.md (new wiki page)
```

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Annotation set too small for reliable ML | High | Start with LLM-assisted labeling; iterate; baseline accuracy may be modest at MVP |
| Class imbalance (Phase B vastly more common than Phase C) | Medium | Use balanced loss, oversampling, or per-class metrics |
| Scanner false-positive rate too high | Medium | Layer ML classifier on top of rule-based filter |
| Backtest leakage (using future data to confirm past signals) | Medium | Strict walk-forward validation; document boundaries clearly |
| Virtual portfolio state corruption across MCP restarts | Low | JSON state with file lock; atomic writes |
| Skill mode confusion (user asks for signal, agent gives scenario) | Medium | Strict mode discriminator in SKILL.md; test prompts |

---

## Implementation Phases

| # | Phase | Milestone | Description | Status |
|---|-------|-----------|-------------|--------|
| 1 | Virtual portfolio MCP | M5 | Open/close/list/persistent state | pending |
| 2 | Signal logger MCP | M5 | Append-only log + replay | in-progress — [plan](../../../PRPs/plans/signal-logger-mcp.plan.md) |
| 3 | Scanner MCP | M5 | Multi-symbol OHLCV + lightweight rule filter | pending (depends on Faza-2 OHLCV) |
| 4 | Skill Signal mode | M5 | New mode + output contract | pending (depends on Faza-1 mode discriminator) |
| 5 | Backtest runner MCP | M5 | Rule-based, deterministic backtest with stats | pending (depends on signal logger) |
| 6 | Annotation pipeline | M6 | LLM-assisted labeling of historical windows | pending (depends on Faza-1 wiki for phase definitions) |
| 7 | Feature engineering | M6 | OHLCV → rolling + FFT + volume features | pending |
| 8 | Baseline classifier | M6 | RandomForest train + eval | pending (depends on #6 + #7) |
| 9 | Classifier MCP server | M6 | Serve predictions to agent | pending (depends on #8) |

### Phase Details

**Phase 1: Virtual portfolio MCP**
- **Goal**: Persistent virtual portfolio with open/close/list operations, virtual cash, position tagging
- **New issue**: "Trading MCP — virtual portfolio server"
- **Success signal**: `open_position(symbol="BTC/USDT", side="long", size=0.1, sl=40000, tp=50000)` writes to disk and is retrievable across MCP restarts

**Phase 2: Signal logger MCP**
- **Goal**: Append-only log of every signal generated by the agent, with metadata for later replay
- **New issue**: "Trading MCP — signal logger"
- **Success signal**: Signals from a session can be replayed against past OHLCV to compute would-have outcomes

**Phase 3: Scanner MCP**
- **Goal**: Scan N symbols in parallel, apply lightweight rule filter, return ranked list
- **New issue**: "Trading MCP — multi-symbol scanner"
- **Success signal**: `scan_universe(["BTC", "ETH", "SOL", ...], "1d", rule="range>4w")` returns ranked list

**Phase 4: Skill Signal mode**
- **Goal**: Skill recognizes signal-mode queries; new output contract for signal/trade outputs
- **New issue**: "Skill: add Signal/Trading mode"
- **Success signal**: Signal-mode prompt produces output with entry/invalidation/target/virtual-position section

**Phase 5: Backtest runner MCP**
- **Goal**: Deterministic backtest of a signal set or rule against historical OHLCV
- **New issue**: "Trading MCP — backtest runner"
- **Success signal**: Same input rules + dates produce same P&L output across runs

**Phase 6: Annotation pipeline**
- **Goal**: Build labeled dataset of (symbol, window_start, window_end, phase) tuples
- **New issue**: "ML — historical scenario annotation pipeline"
- **Success signal**: ≥ 500 annotations in `data/annotations/manifest.json` with at least 4-way phase coverage

**Phase 7: Feature engineering**
- **Goal**: Pipeline OHLCV → feature vector (rolling stats, FFT cycles, volume-relative, body/range)
- **New issue**: "ML — feature engineering pipeline"
- **Success signal**: `make_features(symbol, end_date, window=200)` returns ≥ 30 features as fixed-shape vector

**Phase 8: Baseline classifier**
- **Goal**: Train RandomForest baseline, evaluate on held-out test, report per-class metrics
- **New issue**: "ML — baseline classifier training"
- **Success signal**: ≥ 60% balanced accuracy on 4-class test set; documented in `reports/baseline-2026.md`

**Phase 9: Classifier MCP server**
- **Goal**: Expose `classify_phase(symbol, timeframe)` returning {phase, confidence, similar_historical}
- **New issue**: "ML — classifier MCP server"
- **Success signal**: Agent calls MCP, integrates prediction into scenario analysis

### Parallelism Notes

- M5 work (phases 1–5) and M6 work (phases 6–9) are largely independent — annotation/ML can start while trading MCP is built
- Within M5: phase 4 (skill mode) can develop in parallel with phases 1–3; phase 5 (backtest) needs phase 2 (signal logger)
- Within M6: phase 7 (features) can develop in parallel with phase 6 (annotation); both feed into phase 8

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| ML model family | Off-the-shelf scikit-learn (RandomForest baseline first) | XGBoost, neural nets, transformers | Cheap baseline first; iterate only if ceiling demands it |
| Annotation strategy | LLM-assisted + human spot-check | Pure manual, pure automatic | Manual doesn't scale; pure auto risks label noise |
| Backtest fidelity | Simple bar-close fill, no slippage at MVP | Tick-level slippage, market impact | Sufficient for relative strategy comparison |
| Portfolio state storage | File-based JSON | SQLite, in-memory only | Simplest; debuggable; portable |
| ML feature inputs | OHLCV-derived only (Faza 3 MVP) | + caption embeddings | Captions add complexity; defer to evaluation phase |
| Repo separation | Stay in same repo, but after Faza 1 PR upstream + unfork | Spin off into new repo | Less friction; existing infra already here |

---

## Research Summary

**Market Context**
- Wyckoff trading practice typically combines scanning (universe-level) + deep-dive (single-asset) workflows — the existing skill only handles deep-dive
- ML-assisted trading is mature in TradFi but uncommon in retail crypto — most retail tools are indicator-based, not phase-classified
- Reference repo `razni-tutorijali/ml-fitness-tracker` demonstrates the same multi-channel-time-series ML approach is well-suited (PCA, FFT, RandomForest)

**Technical Context**
- Faza 1 + Faza 2 infrastructure (wiki, MCP layer, raw data) is enough scaffolding for Faza 3 — no new external dependencies beyond scikit-learn and pandas
- Annotation labor is the budget driver — must be planned, not assumed

---

## Linked GitHub Issues (all NEW — to be created)

| New Issue Title | Milestone | Phase | Model | Depends on |
|---|---|---|---|---|
| Trading MCP — virtual portfolio server | M5 | 1 | Sonnet | — |
| Trading MCP — signal logger | M5 | 2 | Sonnet | — |
| Trading MCP — multi-symbol scanner | M5 | 3 | Sonnet | Faza-2 OHLCV (#9) |
| Skill — add Signal/Trading mode | M5 | 4 | Opus | Faza-1 #8 (mode discriminator) |
| Trading MCP — backtest runner | M5 | 5 | Sonnet | signal logger |
| ML — historical scenario annotation pipeline | M6 | 6 | Opus (high cognition for labels) | Faza-1 wiki (#7) |
| ML — feature engineering pipeline | M6 | 7 | Sonnet | OHLCV available |
| ML — baseline classifier training | M6 | 8 | Sonnet | annotation + features |
| ML — classifier MCP server | M6 | 9 | Sonnet | trained model |
| M5 tracking issue | M5 | — | — | — |
| M6 tracking issue | M6 | — | — | — |

---

*Generated: 2026-05-24*
*Status: PLANNED — depends on Faza-2 completion (or partial: ML can start once Faza-1 wiki is done)*
