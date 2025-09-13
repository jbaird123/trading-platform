# project_requirements

_Last updated: 2025-09-09_

> **Purpose**: Single source of truth for the Trading Engine project. This file captures **all requirements, at every level of detail** — functional, non-functional, system-wide, module-specific, and even small design details. It serves as the **authoritative requirements index** that goes beyond a master spec.

## Table of Contents
- [0) Scope & Definitions](#0-scope--definitions)
- [1) System-Wide Requirements](#1-system-wide-requirements)
- [2) Data Handler (DH)](#2-data-handler-dh)
- [3) Strategy Engine (SE)](#3-strategy-engine-se)
- [4) Regime Market Manager (RMM)](#4-regime-market-manager-rmm)
- [5) Portfolio Manager (PM)](#5-portfolio-manager-pm)
- [6) Backtester (BT)](#6-backtester-bt)
- [7) Execution Layer (EL)](#7-execution-layer-el)
- [8) Reporting & Visualization (RV)](#8-reporting--visualization-rv)
- [9) AI Lab (AI)](#9-ai-lab-ai)
- [10) JSON Brief Schema](#10-json-brief-schema)
- [11) MVP Subset](#11-mvp-subset)
- [12) Non-Functional Requirements](#12-non-functional-requirements)
- [13) Detailed Notes & Edge Requirements](#13-detailed-notes--edge-requirements)
- [14) Development Process & Governance](#14-development-process--governance)
- [15) Open TODOs](#15-open-todos)
- [16) Traceability](#16-traceability)
- [17) Pending updates (awaiting approval)](#17-pending-updates-awaiting-approval)

---

## 0) Scope & Definitions
- **Data Handler (DH)**: Loads, normalizes, validates, and serves market data; resampling and feature pipelines.
- **Strategy Engine (SE)**: Strategy lifecycle & interfaces; computes signals using indicators/features.
- **Portfolio Manager (PM)**: Manages state (positions, cash, equity). Processes orders, updates positions, and calculates PnL. Used by both the Backtester and Execution Layer to ensure logical consistency.
- **Backtester (BT)**: The simulation engine. Iterates through time, feeding market data to the Strategy Engine and submitting the resulting signal-based orders to the Portfolio Manager.
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
- **Inter-Module Communication & Boundaries**
  - To facilitate a future split into multiple repositories, modules must communicate only through well-defined public APIs (e.g., functions and classes exposed in `__init__.py` files).
  - Direct imports of internal sub-modules (e.g., `from trading_platform.data.internal_helpers import ...`) are strictly forbidden.
  - **No circular dependencies** between top-level modules (e.g., `data`, `strategy`, `backtester`) will be permitted. This will be enforced via static analysis tools in the CI pipeline.
  - A `trading_platform.core` module will house shared data structures (e.g., canonical models for `Bar`, `Trade`) and utilities that all other modules can depend on.
- **Strategy Comparison & A/B Testing**
  - The platform must support running comparative analyses between two or more strategy variations.
  - This includes comparing a baseline strategy against a version with modified parameters, different risk models, or additional signal layers (e.g., with and without an AI-driven event filter).
  - The results must be presented in a comparative format, highlighting differences in key performance metrics.
- **Trading Sessions & Blackout Periods**
  - The system must support the definition of trading blackout periods, during which no new positions can be opened.
  - These periods can be defined as:
    - **Static Rules**: e.g., "do not trade between 23:00 and 01:00 UTC daily".
    - **Event-Based**: e.g., "pause trading 10 minutes before and 30 minutes after any event with `impact: high`".
  - This functionality will be managed centrally and applied by the Backtester (BT) and Execution Layer (EL) to ensure consistent behavior. Strategies may choose to override or ignore these blackouts via configuration.
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
- **[DH-2.1]** Load historical and live market data (OANDA, Dukascopy).
- **[DH-2.2]** Normalize data to a schema with columns: `timestamp, open, high, low, close, volume`.
- **[DH-2.3]** The `timestamp` index must be timezone-aware and set to UTC.
- **[DH-2.4]** Resample data safely between timeframes (e.g., M1→H1→D) using correct OHLC aggregation rules.
- **[DH-2.5]** Perform validation checks to detect missing bars, duplicate timestamps, volume outliers, and price spikes.
- **[DH-2.6]** Produce a `quality_flags` report based on validation results.
- **[DH-2.7]** Implement a data versioning strategy (e.g., using DVC) to link backtest results to a specific dataset version.
- **[DH-2.8]** **Instrument Definition**: Provide comprehensive symbol metadata to drive the canonical model. This includes, but is not limited to:
  - `asset_class`: (e.g., 'Forex', 'Future', 'Stock').
  - `point_value`: The value of a single full-point move in the base currency (e.g., $1 for most Forex pairs, $50 for ES futures).
  - `tick_size`: The minimum price fluctuation.
  - `commission_model`: A structured object defining costs (e.g., per contract, per share, or spread-based).
  - `margin_requirement`.
  - `sessions`: A definition of the primary trading session (e.g., start/end times and timezone) used for correct daily resampling.
  - `holidays`: A calendar of non-trading days.
- **[DH-2.9]** Support chunked loading for large date ranges to manage memory usage.
- **[DH-2.10]** Cache processed datasets persistently (e.g., in Parquet format) to speed up subsequent loads.
- **[DH-2.11]** Provide feature pipelines for calculating and appending common technical indicators (e.g., ATR, ADX, RSI, BB width).
- **[DH-2.12]** **Unstructured & Event Data (News/Reports)**
  - **[DH-2.12.1]** The system must support the ingestion, storage, and retrieval of time-series event data (e.g., news, economic reports).
  - **Canonical Event Schema**: All event data must be normalized into a canonical format: `{event_id, timestamp, source, type, headline, summary, content, metadata}`.
    - `type`: e.g., 'news', 'economic_report', 'central_bank_speech'.
    - `metadata`: A flexible field for pre-computed sentiment scores, named entities, relevance, etc.
  - **Storage & Retrieval**: Events must be stored efficiently to allow for fast time-range queries.
  - **Alignment**: The Data Handler must provide an interface to retrieve all events that occurred within the timeframe of a given bar or a set of bars. This enables direct alignment with market data for backtesting and analysis, and must work for any bar timeframe (e.g., M1, H1, D1), including those generated through resampling.
  - **Sources**: Initial sources can include public news APIs or RSS feeds for economic calendars.
- Interfaces:
  - **[DH-2.13]** Expose a `DataRequest(symbol, timeframe, start, end, features=[...]) -> DataFrame` interface.
  - **[DH-2.14]** Expose a `subscribe_events(callback) -> Subscription` interface for live event streaming.
- **[DH-2.15]** All functionality must be tested using golden dataset fixtures, schema invariants, and resampling correctness checks.


---

## 3) Strategy Engine (SE)
- **[SE-3.1]** Define a `BaseStrategy` interface with the following methods:
  - **[SE-3.1.1]** `prepare(data)`: To compute indicators and features.
  - **[SE-3.1.2]** `generate_signals(market_data, event_data) -> Series|DataFrame`: To output long/short/flat signals, reacting to both market and event data.
  - **[SE-3.1.3]** `risk_params`: To define stop-loss, take-profit, and position sizing policies.
  - **[SE-3.1.4]** `meta()`: To return strategy name, version, and required inputs.
- **[SE-3.2]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.2.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.2.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.2.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.3]** Strategy names should use common industry abbreviations (e.g., SMA, EMA, BB) for clarity.
- **[SE-3.4]** **Declarative Strategies (Low-Code/No-Code)**
  - **[SE-3.4.1]** The system must support defining strategies using a declarative **YAML format**, distinct from Gherkin BDD files.
  - **Strategy Schema**: The YAML files will follow a defined schema representing rules, conditions, and indicators.
  - **Parameterization**: YAML's key-value structure naturally supports parameterization. Parameter sweeps will be orchestrated by the AI Lab, which can easily read, modify, and generate these YAML files.
  - **Execution**: The Strategy Engine will include a parser that loads a strategy definition from a YAML file and executes its logic.
  - **Testing**: The behavior of the YAML strategy parser and execution engine will be tested rigorously using Behavior-Driven Development (BDD) with Gherkin (`.feature` files). This ensures the implementation correctly interprets the strategy definitions.
  - Example of a declarative strategy file:
    ```yaml
    strategy_name: My Custom RSI Strategy
    description: Go long on oversold condition with confirmation.

    entry_rules:
      - all_of: # All conditions must be true
          - condition: cross_above
            indicator: RSI(period=14)
            value: 30
          - condition: is_above
            indicator: ADX(period=14)
            value: 20

    exit_rules:
      - any_of: # Any condition can trigger an exit
          - condition: cross_below
            indicator: RSI(period=14)
            value: 70

    event_filters:
      - action: suppress_entry
        event_type: economic_report
        metadata_match: { "impact": "high" }
        window: "5 minutes"
    ```
- **[SE-3.5]** Use indicators from established libraries (e.g., `ta`) where possible to avoid duplication.
- **[SE-3.6]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.7]** The engine must support parameter sweeps orchestrated by the AI Lab.

---

## 4) Regime Market Manager (RMM)
- **[RMM-4.1]** Classify the market into regimes, including but not limited to: `trend_up`, `trend_down`, `range`, `volatile`, `quiet`.
- **[RMM-4.2]** Each classification must output both a `label` and a `confidence` score (0–1).
- **[RMM-4.3]** The baseline implementation will be rule-based, using indicators such as ADX, MA slope, ATR %, and Bollinger Band Width.
- **[RMM-4.4]** The RMM must be extensible to allow for future ML-based classifiers.
- **[RMM-4.5]** The module must expose an API that returns the current regime, for example: `RMMResult(timestamp, label, confidence, features={...})`.
- **[RMM-4.6]** The module must expose a policy function to determine if trading is allowed, for example: `is_trade_allowed(strategy, regime_label, confidence) -> bool`.
- **[RMM-4.7]** Policies should be configurable per-strategy and include hysteresis to reduce rapid state changes (flip-flopping).
- **[RMM-4.8]** All classification logic must be tested using synthetic data sequences that cover edge cases for each regime.

---

## 5) Portfolio Manager (PM)
- **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **State Management**:
  - **[PM-5.1]** Track cash balance, open positions, and total equity (mark-to-market).
  - **[PM-5.2]** Maintain a log of all executed trades.
- **Order Processing**:
  - **[PM-5.3]** `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - **[PM-5.4]** `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **Position Sizing**: Implement sizing logic, including:
  - **[PM-5.5]** Fixed-risk (e.g., risk $100 per trade).
  - **[PM-5.6]** Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **Trade & PnL Logic**:
  - **[PM-5.7]** Generate a canonical `Trade` record upon position closure.
  - **[PM-5.8]** Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - **[PM-5.9]** Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **Portfolio-Level Risk Management**:
  - **[PM-5.10]** Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.

---

## 6) Backtester (BT)
- **[BT-6.1]** **Core Responsibility**: To simulate the passage of time and orchestrate the interaction between the Data Handler, Strategy Engine, and Portfolio Manager.
- **[BT-6.2]** The primary mechanism will be an event-driven or vectorized loop that iterates through historical data.
- **[BT-6.3]** Support for multiple order types, including: market, stop, and limit.
- **[BT-6.4]** Support for risk management orders, including ATR-based stops/take-profits and trailing stops.
- **[BT-6.5]** A configurable tie-break mechanism for scenarios where multiple exit conditions are met on the same bar (e.g., stop and take-profit).
- **[BT-6.6]** A configurable cost model to simulate slippage, rollover, commissions, fees, and spreads, driven by the instrument definition.
- **[BT-6.7]** A "warm-up" period to ensure indicators are stable before trading signals are processed.
- **[BT-6.8]** Backtests must be deterministic, producing the same results from the same inputs and configuration.
- **[BT-6.9]** All backtesting logic must be validated, especially for fill logic and stop/TP precedence.

---

## 7) Execution Layer (EL)
- **[EL-7.1]** Implement a broker adapter for OANDA as the initial target.
- **[EL-7.2]** The adapter must map the internal canonical order format to the broker's specific API format.
- **[EL-7.3]** The adapter must handle API connectivity issues, including retries, exponential backoff, and rate-limit management.
- **[EL-7.4]** **Portfolio Interaction**: The EL must use the same `PortfolioManager` component as the backtester to ensure logical parity between simulation and live trading.
- **[EL-7.5]** The EL must handle live streams of both market data and event data, forwarding them to the active strategy for signal generation.
- **[EL-7.6]** All actions, orders, and broker responses must be captured via structured logging.
- **[EL-7.7]** Implement a reconciliation process to periodically check for discrepancies between the internal portfolio state and the broker's state.
- **[EL-7.8]** Enforce live risk management, including daily loss caps and other circuit breakers, as defined in the Portfolio Manager.

---

## 8) Reporting & Visualization (RV)
- **[RV-8.1]** Generate a machine-readable **JSON Brief** for each run, conforming to the schema in section 10.
- **[RV-8.2]** Generate **Comparison Reports** for A/B tests, presenting key metrics side-by-side for each variation.
- **[RV-8.3]** Generate plots with the following characteristics:
  - **[RV-8.3.1]** Overlays (e.g., EMAs, SMAs) must be auto-detected from strategy metadata.
  - **[RV-8.3.2]** Plotted lines for overlays must have distinct colors and be thinner than the primary price series.
  - **[RV-8.3.3]** Non-overlay indicators (e.g., ATR, RSI, Volume) must each be rendered in a separate panel below the main price chart.
  - **[RV-8.3.4]** The chart must include markers for trade entries, exits, stop-losses, and take-profits.
  - **[RV-8.3.5]** The chart must support optional shading to indicate different market regimes.
  - **[RV-8.3.6]** For comparison reports, the equity curves from all variations must be plotted on the same chart for easy comparison.
- **[RV-8.4]** Support exporting reports to multiple formats, including JSON, CSV, and a self-contained HTML file.
- **[RV-8.5]** Interactive controls for plots are desirable but not an MVP requirement, including toggling overlays and exporting the current view to PNG.

---

## 9) AI Lab (AI)
- **[AI-9.1]** **Core Mandate**: The AI Lab must function as the central analysis component, consuming JSON briefs and other run artifacts to provide intelligent insights.
- **[AI-9.2]** **Analysis & Recommendations**:
  - **[AI-9.2.1]** Identify performance clusters (both winning and losing) based on features, regimes, and other trade attributes.
  - **[AI-9.2.2]** In comparison reports, quantify the statistical significance of performance differences between variations.
  - **[AI-9.2.3]** Recommend specific, machine-readable filters to improve performance (e.g., `{"feature": "ADX", "op": ">", "value": 25}`).
  - **[AI-9.2.4]** Recommend optimized stop-loss and take-profit configurations based on MFE/MAE analysis from the backtest.
  - **[AI-9.2.5]** Highlight potential data issues such as distributional drift and non-stationarity.
- **[AI-9.3]** **Advanced Testing Orchestration**:
  - **[AI-9.3.1]** Orchestrate parameter searches (e.g., grid search, random search) to find optimal parameter sets for a given strategy. This will be driven by a sweep configuration file.
  - **[AI-9.3.2]** Perform walk-forward evaluation (WFE) to test strategy robustness on out-of-sample data.
  - **[AI-9.3.3]** Conduct detailed regime analysis to break down strategy performance by market condition (e.g., trending, ranging).
  - **[AI-9.3.4]** The standard validation workflow will be a two-stage process: 1) Use parameter sweeps to discover optimal parameter sets. 2) Use Monte Carlo analysis on the best-performing set to validate its robustness.
- **[AI-9.4]** All findings and recommendations must be available in two formats:
  - **[AI-9.4.1]** A machine-readable JSON format for consumption by other tools.
  - **[AI-9.4.2]** A human-readable summary for direct user review.

---

## 10) JSON Brief Schema (Instrument-Agnostic)
- **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **overall_performance** (base currency): `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **risk_snapshot** (base currency): `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **stop_tp_candidates**: configs derived from MFE/MAE (in base currency; instrument-specific conversions occur via Instrument Definition at presentation/export time).
- **monte_carlo**: resampling stats.
- **walk_forward**: rolling OOS stats with instability flags.
- **regimes**: per-regime performance breakdown.
- **parameter_search**: top params, robustness notes.
- **stationarity**: ADF, KPSS, drift tests.
- **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
- Pure JSON types only (convert pandas objects).

Notes:
- The brief is canonical and instrument-agnostic. Any UI/export layer may render instrument-native units (e.g., pips, ticks) by translating the canonical brief via the Instrument Definition (e.g., `tick_size`, `point_value`).

---

## 11) MVP Subset
- Data Handler with normalization, quality checks, caching.
- Strategy Engine with SMA, PSAR+ADX, BB Mean Reversion, ATR Channel Breakout.
- Strategy Engine with SMA, PSAR+ADX, BB Mean Reversion.
- RMM baseline (rule-based).
- Backtester with ATR stops/TP, spreads/fees, trades table, equity.
- JSON Brief v1 (meta, params, overall, contrasts, risk, stop/tp).
- Reporting: auto-plot overlays & separate panels.
- AI Lab v1: consume briefs, suggest filters/params.
- Tests: unit + small e2e fixtures.

---

## 12) Non-Functional Requirements
- **Performance**: Efficient with multi-year data.
- **Reliability**: Deterministic backtests.
- **Maintainability**: Clean modular package.
- **Observability**: Structured logging; per-run artifact storage.
- **Monitoring & Alerting**: For the Execution Layer (EL), a mechanism for health checks and alerts (e.g., for excessive errors, downtime, or large losses) must be implemented.
- **Security**: Env var secrets; safe credential handling.

---

## 13) Detailed Notes & Edge Requirements
- Plots: overlays must not share identical colors; lines thinner than default.
- ATR and Volume must be plotted in separate panels (not combined).
- Each non-overlay indicator gets its own panel.
- Strategy plotting is auto-detected (don’t plot unused indicators).
- Backtester tie-break rule: `stop_then_tp` default.
- Repo may need splitting to satisfy SonarQube LOC cap.
- JSON serialization: `Timestamp` → ISO8601; `Timedelta` → seconds.
- AI briefs must include recommendations in machine-readable JSON.

---

## 14) Development Process & Governance
- **Branching Strategy**: A standardized branching model (e.g., GitFlow or GitHub Flow) will be used.
- **Code Reviews**: All code must be submitted via Pull Requests and requires at least one approval before merging to the main branch.
- **Issue Tracking**: All work should be tracked in an issue tracker, with issue numbers referenced in commit messages.

---

## 15) Open TODOs
- [ ] Decide pandas vs Polars for long-run performance.
- [ ] Finalize baseline RMM thresholds and hysteresis.
- [ ] Define standard slippage/spread models.
- [ ] Publish example JSON brief under `/docs/examples/`.
- [ ] Add walk-forward eval and Monte Carlo to briefs.
- [ ] Execution Layer parity checks vs backtester.
- [ ] Decide repo split strategy for SonarQube.
- [ ] Plotting theme + interactive controls.

---

## 16) Traceability
- Each requirement in this document will be linked to a corresponding BDD `.feature` file.
- The Gherkin scenarios within these feature files will serve as the direct, automated mapping between the high-level requirement and the code that implements it.

---

## 17) Pending updates (awaiting approval)
> Proposed requirement changes I’ve flagged during design discussions. I will keep this list up to date and move items into the appropriate sections once you approve them.

- _None yet._

---

This document is the **comprehensive requirements index** for the Trading Engine project — all details captured, no matter how granular.
