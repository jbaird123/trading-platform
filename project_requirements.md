# project_requirements

_Last updated: 2025-09-09_

> **Purpose**: Single source of truth for the Trading Engine project. This file captures **all requirements, at every level of detail** — functional, non-functional, system-wide, module-specific, and even small design details. It serves as the **authoritative requirements index** that goes beyond a master spec.

---

## 0) Scope & Definitions
- **Data Handler (DH)**: Loads, normalizes, validates, and serves market data; resampling and feature pipelines.
- **Strategy Engine (SE)**: Strategy lifecycle & interfaces; computes signals using indicators/features.
- **Backtester (BT)**: Vectorized simulation of orders/fills, PnL, risk, and analytics over historical data.
- **Regime Market Manager (RMM)**: Classifies regimes (trending, ranging, volatile, quiet, etc.) with confidence; used for filtering.
- **Execution Layer (EL)**: Live trading adapter (OANDA first); order routing, risk controls, brokerage mapping.
- **Reporting & Visualization (RV)**: JSON briefs, plots, dashboards, exports.
- **AI Lab (AI)**: Consumes briefs; recommends filters/params; supports walk-forward eval (WFE), parameter search, regime summaries, stationarity checks.
- **Utilities (UTIL)**: Logging, config, serialization, math, validation.

---

## 1) System-Wide Requirements
- **Architecture**
  - Modular separation between DH, SE, BT, RMM, EL, RV, AI.
  - Pluggable components (dependency injection / registry pattern).
- **Configuration & Reproducibility**
  - All runs reproducible with persisted `run_id` & config snapshot.
  - Configurable via JSON/YAML; CLI overrides supported.
- **Time & Markets**
  - Primary focus on Forex (EUR/USD, USD/JPY, AUD/USD, etc.).
  - Handle 20+ years of minute data.
  - Store timestamps in UTC; daylight-saving safe.
- **Performance**
  - Vectorized core operations; batch I/O; memory-aware iterators.
  - Able to process multi-year minute data on laptop/Colab.
- **Test-Driven Development**
  - Unit tests, integration tests, synthetic fixtures.
  - Design specs must be verifiable through automated tests.
  - Optionally behavior-driven (Cucumber/Gherkin).
- **Quality & Tooling**
  - SonarQube for static analysis.
  - Cloud free tier limit = ~50k LOC; repo split required beyond ~100k LOC.
  - Pre-commit hooks for formatting, linting, type-checking.
- **Cost Constraints**
  - Must run locally or in free-tier cloud environments.
  - No paid infra required for MVP.
- **Security**
  - API keys stored in environment variables / secret manager.
  - Never commit credentials.

---

## 2) Data Handler (DH)
- Load historical and live market data (OANDA, Dukascopy).
- Normalize schema: `timestamp, open, high, low, close, volume`.
- Index must be UTC `timestamp`.
- Resample safely (M1→H1→D) with OHLC rules.
- Validation: detect missing/duplicate bars, zero volumes, outliers.
- Produce `quality_flags`.
- Provide symbol metadata (pip size, tick size, sessions, holidays).
- Chunked loading for large ranges; memory cap awareness.
- Cache datasets persistently (parquet/feather) keyed by params.
- Feature pipelines for computed cols (ATR, ADX, RSI, BB width, etc.).
- Interfaces:
  - `DataRequest(symbol, timeframe, start, end, features=[...]) -> DataFrame`.
- Testing: golden dataset fixtures; schema invariants; resampling correctness.

---

## 3) Strategy Engine (SE)
- **Base Interface** (`BaseStrategy`)
  - `prepare(data)`: compute indicators/features.
  - `generate_signals(data) -> Series|DataFrame`: outputs long/short/flat signals.
  - `risk_params`: stop/TP config, position sizing policy.
  - `meta()`: name, version, required inputs/indicators.
- **Built-in Strategies**
  - SMA crossover (fast/slow).
  - PSAR with ADX filter (avoid whipsaws in ranges).
  - Turtle breakout.
- **Requirements**
  - Use `ta` library indicators when possible; avoid duplicating.
  - Strategy metadata must declare required overlays for plotting.
  - Parameter sweeps supported.

---

## 4) Regime Market Manager (RMM)
- Classify market regime: `trend_up`, `trend_down`, `range`, `volatile`, `quiet`, etc.
- Must output both **label** and **confidence (0–1)**.
- Inputs: ADX, MA slope, ATR pct, BB width, slope of EMA/price, Hurst exponent optional.
- API:
  - `RMMResult(timestamp, label, confidence, features={...})`.
  - `is_trade_allowed(strategy, regime_label, confidence) -> bool`.
- Policies: per-strategy filter config; hysteresis to reduce flip-flops.
- Extensible: rule-based baseline, ML classifiers later.
- Testing: synthetic sequences for edge cases.

---

## 5) Backtester (BT)
- Vectorized core with event-driven fallback.
- Multi-strategy runs supported.
- Orders: market, stop, limit; ATR-based stops/TP; trailing stops; tie-breaks.
- Models: slippage, spread, commissions, rollover.
- Position sizing: fixed risk or fixed fraction in **pips**.
- Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pips, mfe_pips, mae_pips, atr_pips@entry, r_multiple, notes`.
- Metrics: equity curve, drawdowns, hit rate, expectancy, per-side totals.
- Risk: daily loss caps, per-trade caps, circuit breakers.
- Monte Carlo resampling for trades/equity.
- Warm-up window for indicators.
- Testing: deterministic fills; stop/TP precedence validation.

---

## 6) Execution Layer (EL)
- Broker adapter: OANDA (initial).
- Map internal → broker API; handle retries, backoff, rate-limits.
- Paper trading mode (same interface as live).
- Structured logging; reconciliation of positions.
- Risk: daily caps, circuit breakers.

---

## 7) Reporting & Visualization (RV)
- **JSON Briefs** generated per run.
- Plots:
  - Overlays (EMA/SMA) auto-detected from strategy metadata.
  - Overlays: distinct colors, thinner lines.
  - Non-overlays (ATR, RSI, ADX, BB width, Volume) each in separate panels.
  - Entry/exit markers, stop/TP markers.
  - Optional regime shading.
- Exports: JSON, CSV, HTML reports.
- Interactive controls: hide/show overlays; export to PNG/HTML.

---

## 8) AI Lab (AI)
- Inputs: JSON briefs + artifacts.
- Must:
  - Identify losing clusters (features, regimes).
  - Suggest filters (ADX > 20, etc.).
  - Suggest stop/TP optimizations.
  - Highlight distributional drift, stationarity warnings.
- Future: walk-forward eval, parameter search, regime analysis.
- Outputs: JSON + human-readable summaries.

---

## 9) JSON Brief Schema
- **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **overall_pips**: `{n_trades, mean_pips, median_pips, total_pips, by_side_total_pips}`.
- **risk_snapshot**: `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **stop_tp_candidates**: configs derived from MFE/MAE (in pips).
- **monte_carlo**: resampling stats.
- **walk_forward**: rolling OOS stats with instability flags.
- **regimes**: per-regime performance breakdown.
- **parameter_search**: top params, robustness notes.
- **stationarity**: ADF, KPSS, drift tests.
- Pure JSON types only (convert pandas objects).

---

## 10) MVP Subset
- Data Handler with normalization, quality checks, caching.
- Strategy Engine with SMA, PSAR+ADX, Turtle.
- RMM baseline (rule-based).
- Backtester with ATR stops/TP, spreads/fees, trades table, equity.
- JSON Brief v1 (meta, params, overall, contrasts, risk, stop/tp).
- Reporting: auto-plot overlays & separate panels.
- AI Lab v1: consume briefs, suggest filters/params.
- Tests: unit + small e2e fixtures.

---

## 11) Non-Functional Requirements
- **Performance**: Efficient with multi-year data.
- **Reliability**: Deterministic backtests.
- **Maintainability**: Clean modular package.
- **Observability**: Structured logging; per-run artifact storage.
- **Security**: Env var secrets; safe credential handling.

---

## 12) Detailed Notes & Edge Requirements
- Plots: overlays must not share identical colors; lines thinner than default.
- ATR and Volume must be plotted in separate panels (not combined).
- Each non-overlay indicator gets its own panel.
- Strategy plotting is auto-detected (don’t plot unused indicators).
- Backtester tie-break rule: `stop_then_tp` default.
- Repo may need splitting to satisfy SonarQube LOC cap.
- JSON serialization: `Timestamp` → ISO8601; `Timedelta` → seconds.
- AI briefs must include recommendations in machine-readable JSON.

---

## 13) Open TODOs
- [ ] Decide pandas vs Polars for long-run performance.
- [ ] Finalize baseline RMM thresholds and hysteresis.
- [ ] Define standard slippage/spread models.
- [ ] Publish example JSON brief under `/docs/examples/`.
- [ ] Add walk-forward eval and Monte Carlo to briefs.
- [ ] Execution Layer parity checks vs backtester.
- [ ] Decide repo split strategy for SonarQube.
- [ ] Plotting theme + interactive controls.

---

## 14) Traceability
- Each requirement maps to:
  - **Code**: module/class/function.
  - **Test**: test case name.
  - **Status**: Planned / In Progress / Done.

---

## 15) Pending updates (awaiting approval)
> Proposed requirement changes I’ve flagged during design discussions. I will keep this list up to date and move items into the appropriate sections once you approve them.

- _None yet._

---

This document is the **comprehensive requirements index** for the Trading Engine project — all details captured, no matter how granular.

