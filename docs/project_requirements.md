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
- **Strategy Comparison & A/B Testing**
  - The platform must support running comparative analyses between two or more strategy variations.
  - This includes comparing a baseline strategy against a version with modified parameters, different risk models, or additional signal layers (e.g., with and without an AI-driven event filter).
  - The results must be presented in a comparative format, highlighting differences in key performance metrics.
- **Instrument Agnostic Architecture**
  - The core engine (Backtester, Risk Manager) must operate on a canonical representation of trades, positions, and performance, independent of the asset class (Forex, Futures, Stocks, etc.).
  - An **Instrument Definition** module (part of the Data Handler) will provide rich metadata for each symbol (e.g., `point_value`, `tick_size`, `commission_structure`, `margin_requirement`).
  - User-facing components (e.g., Strategy configuration) may allow inputs in native terms (pips, points), but these must be translated into the canonical model before core processing.
  - All core PnL calculations must be performed in a consistent base currency, with performance metrics (e.g., PnL, MFE/MAE) expressed in that currency.
- **Deployment & Operations**
  - **Containerization**: The application and its dependencies must be containerizable (e.g., using Docker) to ensure consistent environments from local development to production.
  - **CI/CD**: A continuous integration pipeline (e.g., GitHub Actions) must be established to automatically run tests, linting, and type-checking on every commit/pull request.
  - **Dependency Management**: Project dependencies must be explicitly managed via `pyproject.toml` (e.g., using Poetry or PDM) to ensure reproducible builds.
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
- **Test & Behavior-Driven Development (TDD/BDD)**
  - All new functionality must be developed using Test-Driven Development (TDD). Tests must be written before the implementation code.
  - Every function, module, and component must have corresponding unit and integration tests. 100% test coverage is the target for all new code.
  - Behavior-Driven Development (BDD) with Gherkin (`.feature` files) will be used to ensure requirements are directly translated into executable specifications. This provides living documentation and guarantees alignment between requirements and deliverables.
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
  - All external inputs (e.g., API responses, config files) must be validated to prevent injection or corruption issues.

---

## 2) Data Handler (DH)
- Load historical and live market data (OANDA, Dukascopy).
- Normalize schema: `timestamp, open, high, low, close, volume`.
- Index must be UTC `timestamp`.
- Resample safely (M1→H1→D) with OHLC rules.
- Validation: detect missing/duplicate bars, zero volumes, outliers.
- Produce `quality_flags`.
- Data Governance: A strategy for versioning datasets (e.g., using DVC - Data Version Control) should be in place to link backtest results to a specific version of the data.
- **Instrument Definition**: Provide comprehensive symbol metadata to drive the canonical model. This includes, but is not limited to:
  - `asset_class`: (e.g., 'Forex', 'Future', 'Stock').
  - `point_value`: The value of a single full-point move in the base currency (e.g., $1 for most Forex pairs, $50 for ES futures).
  - `tick_size`: The minimum price fluctuation.
  - `commission_model`: A structured object defining costs (e.g., per contract, per share, or spread-based).
  - `margin_requirement`.
  - `sessions` & `holidays`.
- Chunked loading for large ranges; memory cap awareness.
- Cache datasets persistently (parquet/feather) keyed by params.
- Feature pipelines for computed cols (ATR, ADX, RSI, BB width, etc.).
- **Unstructured & Event Data (News/Reports)**
  - The system must support the ingestion, storage, and retrieval of time-series event data, such as historical news articles and economic reports, for use in AI-driven analysis.
  - **Canonical Event Schema**: All event data must be normalized into a canonical format: `{event_id, timestamp, source, type, headline, summary, content, metadata}`.
    - `type`: e.g., 'news', 'economic_report', 'central_bank_speech'.
    - `metadata`: A flexible field for pre-computed sentiment scores, named entities, relevance, etc.
  - **Storage & Retrieval**: Events must be stored efficiently to allow for fast time-range queries.
  - **Alignment**: The Data Handler must provide an interface to retrieve all events that occurred within the timeframe of a given bar or a set of bars, enabling direct alignment with market data for backtesting and analysis.
  - **Sources**: Initial sources can include public news APIs or RSS feeds for economic calendars.
- Interfaces:
  - `DataRequest(symbol, timeframe, start, end, features=[...]) -> DataFrame`.
  - `subscribe_events(callback) -> Subscription`: For live event streaming to the Execution Layer.
- Testing: golden dataset fixtures; schema invariants; resampling correctness.

---

## 3) Strategy Engine (SE)
- **Base Interface** (`BaseStrategy`)
  - `prepare(data)`: compute indicators/features.
  - `generate_signals(market_data, event_data) -> Series|DataFrame`: outputs long/short/flat signals, reacting to both market and event data streams.
  - `risk_params`: stop/TP config, position sizing policy.
  - `meta()`: name, version, required inputs/indicators.
- **Built-in Strategies**
  - These will be implemented in Python as reference examples and for performance-critical components.
  - SMA crossover (fast/slow).
  - PSAR with ADX filter (avoid whipsaws in ranges).
  - Turtle breakout.
- **Declarative Strategies (Low-Code/No-Code)**
  - The system must support defining strategies using a Gherkin (`.feature` file) syntax. This allows for low-code/no-code strategy creation.
  - The Strategy Engine will parse these `.feature` files and execute them as strategies.
  - A comprehensive library of BDD step definitions for common trading conditions (e.g., "Given the indicator X crosses above Y", "And the feature Z is less than value V") must be developed and maintained to empower non-programmers.
  - Example of a declarative strategy file:
    ```gherkin
    Feature: My Custom RSI Strategy

    Scenario: Go long on oversold condition with confirmation
      Given the indicator "RSI(14)" on the previous bar was below 30
      And the indicator "RSI(14)" on the current bar is above 30
      And the indicator "ADX(14)" on the current bar is above 20
      When the strategy generates signals
      Then a "long" signal should be produced

    Scenario: Avoid entering trades during high-impact news
      Given a "long" signal is generated
      And an event of type "economic_report" with metadata "impact: high" occurred within the last 5 minutes
      When the strategy filters signals
      Then the "long" signal should be suppressed
    ```
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
- **Multi-Strategy & Comparative Runs**: The backtester must be able to execute multiple strategy configurations within a single "comparison run" to facilitate A/B testing.
- Orders: market, stop, limit; ATR-based stops/TP; trailing stops; tie-breaks.
- Models: slippage, rollover, and a canonical cost model driven by the instrument definition (commission, fees, spread).
- Position sizing: fixed risk (in base currency) or fixed fraction.
- Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
- Metrics: equity curve (in base currency), drawdowns, hit rate, expectancy.
- Risk: daily loss caps, per-trade caps, circuit breakers.
- Monte Carlo resampling for trades/equity.
- Warm-up window for indicators.
- Testing: deterministic fills; stop/TP precedence validation.

---

## 6) Execution Layer (EL)
- Broker adapter: OANDA (initial).
- Map internal → broker API; handle retries, backoff, rate-limits.
- Paper trading mode (same interface as live).
- Must handle live streams of both market data and event data, forwarding them to the active strategy for signal generation.
- Structured logging; reconciliation of positions.
- Risk: daily caps, circuit breakers.

---

## 7) Reporting & Visualization (RV)
- **JSON Briefs** generated per run.
- **Comparison Reports**: For A/B tests, the system must generate a consolidated report that presents key metrics side-by-side for each strategy variation.
- Plots:
  - Overlays (EMA/SMA) auto-detected from strategy metadata.
  - Overlays: distinct colors, thinner lines.
  - Non-overlays (ATR, RSI, ADX, BB width, Volume) each in separate panels.
  - Entry/exit markers, stop/TP markers.
  - Optional regime shading.
  - For comparison reports, equity curves from all variations should be plotted on the same chart.
- Exports: JSON, CSV, HTML reports.
- Interactive controls: hide/show overlays; export to PNG/HTML.

---

## 8) AI Lab (AI)
- Inputs: JSON briefs + artifacts.
- **Core Mandate**: The AI Lab is the central analysis component of the system. It must consume the rich data from the JSON brief to function as an intelligent partner to the user.
- **Analysis & Recommendations**:
  - Identify losing clusters (features, regimes).
  - In comparison reports, quantify the statistical significance of performance differences between variations.
  - Recommend specific, machine-readable filters to improve performance (e.g., `{"feature": "ADX", "op": ">", "value": 25}`).
  - Recommend optimized stop-loss and take-profit configurations based on MFE/MAE analysis.
  - Highlight distributional drift, stationarity warnings.
- **Advanced Testing Orchestration**:
  - Orchestrate parameter searches (grid, random) to find optimal parameter sets.
  - Perform walk-forward evaluation (WFE) to test strategy robustness on out-of-sample data.
  - Conduct regime analysis to show how the strategy performs in different market conditions (trending, ranging, etc.).
- **Outputs**: All findings must be available as both machine-readable JSON and human-readable summaries.

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
- **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
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
- **Monitoring & Alerting**: For the Execution Layer (EL), a mechanism for health checks and alerts (e.g., for excessive errors, downtime, or large losses) must be implemented.
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

## 13) Development Process & Governance
- **Branching Strategy**: A standardized branching model (e.g., GitFlow or GitHub Flow) will be used.
- **Code Reviews**: All code must be submitted via Pull Requests and requires at least one approval before merging to the main branch.
- **Issue Tracking**: All work should be tracked in an issue tracker, with issue numbers referenced in commit messages.

---

## 14) Open TODOs
- [ ] Decide pandas vs Polars for long-run performance.
- [ ] Finalize baseline RMM thresholds and hysteresis.
- [ ] Define standard slippage/spread models.
- [ ] Publish example JSON brief under `/docs/examples/`.
- [ ] Add walk-forward eval and Monte Carlo to briefs.
- [ ] Execution Layer parity checks vs backtester.
- [ ] Decide repo split strategy for SonarQube.
- [ ] Plotting theme + interactive controls.

---

## 15) Traceability
- Each requirement in this document will be linked to a corresponding BDD `.feature` file.
- The Gherkin scenarios within these feature files will serve as the direct, automated mapping between the high-level requirement and the code that implements it.

---

## 16) Pending updates (awaiting approval)
> Proposed requirement changes I’ve flagged during design discussions. I will keep this list up to date and move items into the appropriate sections once you approve them.

- _None yet._

---

This document is the **comprehensive requirements index** for the Trading Engine project — all details captured, no matter how granular.
