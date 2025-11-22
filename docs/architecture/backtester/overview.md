# Current Backtester System Overview

This document summarizes what the existing modules do today so we have a shared baseline before rewriting. Each section lists the primary responsibilities, key files/classes, and notable behaviors or gotchas that must be preserved (or intentionally changed) in the new architecture.

---

## 1. Data Layer (`trading_platform.data`)

**Purpose:** Centralized loading, normalization, session-aware resampling, and caching of OHLCV data and derived features.

**Key Components**
- **`handler.DataHandler`**
  - Singleton-style cache keyed by `(symbol, data_root)` storing raw data, resampled frames, regime context, and detected base timeframe.
  - Exposes `get_data(timeframe, start, end)` which:
    - Loads raw CSVs via `loader.load_instrument_data` (supports full/incremental folders).
    - Chooses the best cached timeframe for resampling (`_find_best_resample_source`) and resamples with `schema.resample_ohlc`.
    - Annotates each frame with session metadata (`session_metadata.annotate_session`) and ensures `open_time`/`close_time` columns exist (`_ensure_time_columns` uses `timeframe_to_timedelta` as fallback).
  - Keeps an `_rmm_cache` for regime market manager contexts so repeated sweeps do not recompute features.
  - Applies fail-fast validation (raises if missing OHLC, timeframe detection fails, etc.).
- **`instrument.py`**
  - Defines `InstrumentDefinition`/`SessionDefinition` dataclasses and helpers for session clocks, pip sizes, and commission models.
  - `get_instrument_definition` loads metadata from config files; used throughout to know sessions and point values.
- **`loader.py` & `schema.py`**
  - `load_instrument_data` normalizes CSVs through `schema.load_and_normalize_data` and aggregates incremental files.
  - `schema.resample_ohlc` is the low-level Pandas resampler used by tests; handles canonical OHLC aggregation semantics.
- **`resample.py`**
  - Adds session-aware resampling (`_session_resample`) aligning buckets to session close, re-labels indexes, and drops partial buckets.
  - Provides `timeframe_to_timedelta` and `_timeframe_to_offset` for consistent cadence math across the codebase.
- **Supporting utilities**
  - `session_metadata` attaches/reads session info from DataFrame `.attrs`.
  - `timeframe_aliases` canonicalizes timeframe strings (e.g., `"H1"` → `"1h"`).

**Observations / Constraints**
- Many downstream modules rely on DataHandler injecting `open_time` and `close_time`; any rewrite must keep these columns authoritative.
- Session alignment flags (attr `_aligned_to_close`) are used by the global-feature cache logic to determine whether values are already shifted to bar close.
- Data quality flags returned from `load_instrument_data` are surfaced in briefs/reporting; plan for that output path.

---

## 2. Strategy Layer (`trading_platform.strategy`)

**Purpose:** Parse YAML/JSON strategies, compute overlays/features, and emit bar-by-bar signals (`Signal` objects) with optional AI gating metadata.

**Key Components**
- **`yaml_strategy.CompiledStrategy`**
  - Built by `compile_strategy(strategy_config)` after Pydantic validation (`StrategyConfig`).
  - Holds feature specs, entry/exit rule blocks, metadata (e.g., `ai_filter_enabled`, `parameters`).
  - `generate_signals(df)` computes features via `features.compute_features`, evaluates rule blocks (`_eval_rule_block`), and produces `Signal` instances with `command` plus optional `context`.
- **`features.compute_features`**
  - Delegates to `core.global_feature_pipeline.build_global_feature_frame` to compute multi-timeframe indicators.
  - Supports parameter placeholders via `_resolve_parameter` and exposes helper wrappers (EMA, ATR, RSI, Donchian, etc.) for older strategies/tests.
- **Indicator Registries**
  - `indicator_implementations.py` contains the actual TA logic functions; `indicators_registry.py` registers them for declarative configs.
  - `ai_strategy.py` integrates optional AI filters (via `AIInferenceClient`) but still produces canonical `Signal` objects.

**Observations / Constraints**
- Strategies expect the DataFrame they operate on to contain both raw OHLC columns and any precomputed global features. The current backtester sometimes replaces/offsets indexes to match cache alignment; this needs to be explicit in the rewrite.
- Rule evaluation intentionally “fails loudly” for unknown operands/conditions—carry this fail-fast behavior forward.
- AI gating currently happens inside the strategy (returning `Signal` with metadata) and again later in the backtester; clarify where that logic belongs in the new design.

---

## 3. Backtester Core (`trading_platform.backtester`)

**Purpose:** Orchestrate market data, strategies, risk management, gating, and portfolio state to produce finalized `Trade` objects, briefs, and diagnostics.

**Key Components**
- **`orchestrator.run_backtest`**
  - Public entry point used by CLI, sweeps, and tests.
  - Steps:
    1. Load/compile the strategy (or accept `CompiledStrategy`).
    2. Merge strategy parameter overrides, warmup requirements (`warmup.calculate_warmup_start_date`), and data request bounds to extend/resample market data via `DataHandler`.
    3. Resolve global feature definitions (`core.feature_resolver.resolve_global_features`) and build `data_with_global_features`.
    4. Instantiate `PortfolioManager`, `RiskExitManager`, and optional gating engine (`regime_market_manager`).
    5. Call `_execute_backtest_loop` with market data, signals, REM, gating metadata, etc.
    6. Assemble `equity_curve`, propagate skip records/exposure curves, and return a dict for reporting.
- **`core._execute_backtest_loop`**
  - Massive loop responsible for:
    - Validating inputs (signals length, allowed commands, NaN checks).
    - Creating fast row views (`_make_bar_factory`) for performance.
    - Building decision contexts each bar via `_build_context_snapshot` (injects strategy features, global features, optional regime information, and the ISO decision timestamp).
    - Managing `pending_entry`/`pending_exit` dicts for `next_bar_open` execution models, capturing snapshots of feature bars, contexts, and decision timestamps/prices.
    - Running gating (`ProfitabilityGatingEngine`) before opening positions (records gating metadata into context and skip lists).
    - Invoking REM each bar (`rem.check_exits_intrabar`) with optional 1-minute zoom to detect stop/tp hits.
    - Delegating actual entry/exit decisions to `PortfolioManager.process_command`, then acting on returned descriptors (enter now vs. defer to next open vs. close immediately).
    - Recording exposure points, skipped trades, counterfactual simulations, and post-exit analyses.
  - Handles context re-alignment for deferred actions via `_update_context_for_timestamp`.
  - Contains simulation utilities (`_simulate_counterfactual_fast/_exact`) used by validation tooling.
- **`warmup.py`**
  - Calculates how many bars to prepend based on feature lookbacks and global feature configs; used both by orchestrator and tests.
- **`backtester/analysis`**
  - Post-processing utilities (exit simulations, metrics) invoked after the main loop to enrich trade records.

**Observations / Constraints**
- `_execute_backtest_loop` is the current “god function.” Responsibilities (data alignment, context capture, risk handling, gating, portfolio state) need to be split across smaller components in the rewrite.
- Decision timestamps and the `context_at_entry` payload are critical for briefs and cache validation; their current shape (strategy + global features + `decision_time`) must stay traceable.
- The pending entry/exit structures assume a single in-flight action per side and embed copies of feature rows—this is brittle and expensive; new design should stream well-defined events instead.

---

## 4. Portfolio & Trade Modules (`trading_platform.portfolio`)

**Purpose:** Track open position(s), manage entry windows, apply costs, and produce immutable `Trade` records with performance metrics.

**Key Components**
- **`portfolio.PortfolioManager`**
  - Maintains cash, current open position (`Position` dataclass), trade ledger, and entry window state.
  - `process_command` handles warmup gating, entry windows, flips, min-hold enforcement, and returns action descriptors (`open_entry_window`, `window_active`, `should_close`, etc.).
  - `create_new_position` and `close_position` apply cost model adjustments (spreads, commissions) and produce `Trade` objects with context snapshots.
  - `_update_position_metrics` updates bars held, MFE/MAE, and unrealized PnL each bar; uses `CostModel` to price exposures.
- **`position.Position` / `trade.Trade`**
  - Frozen dataclasses representing the open state and completed trades, respectively.
  - Store context snapshots (`context_at_entry`/`context_at_exit`), stop/tp levels, R multiples, and post-exit analyses.
- **`metrics.py`**
  - Utility functions for computing equity curves, win rates, and other aggregated metrics consumed by reporting.

**Observations / Constraints**
- PortfolioManager assumes a single open position at a time (per current strategies). If we plan multi-position support, this is a key area to refactor.
- Entry window bookkeeping is central to how signals map to actual fills; the rewrite should decide whether to keep this pattern or replace it with an explicit “intent + policy” workflow.
- Costs are handled through `core.costs.CostModel`—any new execution engine must keep cost application centralized to avoid divergence between backtests and live trading.

---

## 5. Risk & Exit Manager (`trading_platform.risk_manager`)

**Purpose:** Interpret REM configs (fixed stops, trailing stops, take profits, indicator-driven exits) and determine if/when a position should be closed based on price action.

**Key Components**
- **`risk_manager.core.RiskExitManager`**
  - Accepts `REMConfig` (validated via Pydantic in `models.py`) plus instrument metadata.
  - `calculate_initial_stop_price` / `calculate_initial_take_profit_price` resolve rules into concrete levels when a position opens (used for R-multiple calculations and gating context).
  - `check_exits`:
    - Builds a combined stop landscape (fixed stop, take profit, trailing stop) and determines if either level is hit within the current bar (uses `exit_utils.is_fixed_stops_ambiguous` for gap cases).
    - Can zoom into 1-minute data using `trailing_stop_utils` and `exit_utils` when ambiguity arises (both stop & TP hit same bar, or trailing stop updates intrabar).
    - Applies `exit_tie_break` policy to prioritize stop vs. take-profit when both trigger.
    - Returns `{exit_price, reason}` or `None`.
  - `check_exits_intrabar` is a thin wrapper that formats the result for the backtester (`{"action": "should_close", ...}`).
- **`rem_indicators.py` / `indicator_implementations`**
  - Register indicator-based stop calculators (e.g., ATR channels, Bollinger, Donchian).
- **`trailing_stop_utils.py` / `exit_utils.py`**
  - Provide helper functions to process 1-minute slices and detect ambiguous stop/TP order, ensuring deterministic results for golden tests.

**Observations / Constraints**
- REM currently mixes business logic (resolving stops) with execution-time assumptions (e.g., returning a price but expecting the caller to handle gap behavior). In the rewrite we should make the contract explicit—either REM returns the final fill price or the execution engine decides, but not both.
- Ambiguity handling requires access to high-resolution data via `DataHandler`; future modules need a clean API to request “zoomed” bars without reaching back into DataHandler directly.

---

## 6. Reporting & Briefs (`trading_platform.reporting`)

**Purpose:** Turn trades, configs, and diagnostics into human-readable reports, JSON briefs, and analytics used downstream (validation, sweeps, dashboards).

**Key Components**
- **`reporting/brief.py`**
  - Central generator for `brief.json`. Collects trades, exposure curves, config snapshots, AI metadata, and analytics.
  - Validates output against JSON Schema (`schemas/brief.schema.json`) and ensures reproducibility via environment hash (Python version, git commit, etc.).
  - Calls into `reporting.analytics` (timing buckets, stationarity, stop/TP candidates), `portfolio.metrics` (equity curve, win rate), and writes attachments (signals CSV, skip reasons, counterfactuals).
  - Includes helper functions to extract RMM/REM policy summaries for AI explainability.
- **`reporting/csv_export.py`, `compare.py`, `compare_html.py`**
  - Produce CSV/HTML comparison artifacts for validation (platform vs TradingView).
- **`reporting/models`**
  - Dataclasses and Pydantic models describing serialized structures (e.g., `PostExitAnalysis`).

**Observations / Constraints**
- Brief generation assumes the backtester already set `context_at_entry["decision_time"]`, gating metadata, and risk info; any rewrite must keep those fields stable or bump the schema/version.
- Validation tooling reads `workspace/comparison_exports/*.csv` generated by `tests/validation`. Those exporters rely on consistent `Trade` objects (fields like `entry_time`, `exit_reason`, `context_at_entry`).

---

## 7. Validation Harness (`tests/validation` & supporting tools)

**Purpose:** Ensure platform output matches frozen “golden” TradingView runs and produce diagnostics for discrepancies.

**Key Components**
- **`tests/validation/conftest.py`**
  - Provides fixtures (`shared_data_handler`, `platform_trades_*`) that run backtests once per strategy using the real DataHandler and REM configs.
  - Loads golden metadata (date ranges, run configs) from `data/dvc/golden`.
- **Comparison tests**
  - `test_export_exit_price_comparison.py`, `test_export_exit_time_comparison.py`, `test_strategy_validation.py`, etc., call `create_analyzer_for_strategy`, export CSVs, and assert that mismatches are either explained or hashes match golden references.
  - `tests/validation/golden_utils.py` contains helpers to align platform trades with TradingView CSVs (`load_and_prepare_trade_data`).
- **`tests/backtester`**
  - Unit-level tests for context handling, gating, warmup, etc., which rely on current module boundaries.

**Observations / Constraints**
- Any rewrite must either maintain backward compatibility for these tests or provide a migration path (new goldens) while documenting behavior changes.
- Golden fixtures expect 1-minute TradingView data accessible via `DataHandler`; make sure the new execution engine can still consume that data deterministically.

---

## Takeaways for the Rewrite
1. **Everything is intertwined.** Data loading, feature alignment, REM, gating, and portfolio logic currently live in a single loop. The rewrite must introduce explicit data contracts to decouple these concerns.
2. **Decision metadata is critical.** `context_at_entry` carries `strategy_features`, `global_features`, regime snapshots, risk info, and `decision_time`. Downstream tooling (briefs, validations, AI annotations) depends on this exact payload.
3. **Validation infrastructure is strict.** Exit-price/time comparison tests and golden hashes will immediately expose behavioral changes; plan incremental rollouts or toggles while specs are solidified.
4. **Fail-fast philosophy already exists.** Many modules intentionally raise exceptions for misconfigurations. Preserve this behavior to avoid silent divergence between live and backtest environments.

Use this overview alongside `plan.md` and `principles.md` to drive the rewrite discussions and design reviews.
