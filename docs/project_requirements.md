# project_requirements

_Last updated: 2025-09-16_

> **Purpose**: Single source of truth for the Trading Engine project. This file captures **all requirements, at every level of detail** — functional, non-functional, system-wide, module-specific, and even small design details. It serves as the **authoritative requirements index** that goes beyond a master spec.

## Table of Contents
- [0) Scope & Definitions](#0-scope--definitions)
- [1) System-Wide Requirements](#1-system-wide-requirements)
- [2) Data Handler (DH)](#2-data-handler-dh)
- [3) Strategy Engine (SE)](#3-strategy-engine-se)
- [4) Regime Market Manager (RMM)](#4-regime-market-manager-rmm)
- [5) Portfolio Manager (PM)](#5-portfolio-manager-pm)
- [6) Risk & Exit Manager (REM)](#6-risk--exit-manager-rem)
- [7) Backtester (BT)](#7-backtester-bt)
- [8) Execution Layer (EL)](#8-execution-layer-el)
- [9) Reporting & Visualization (RV)](#9-reporting--visualization-rv)
- [10) AI Lab (AI)](#10-ai-lab-ai)
- [11) JSON Brief Schema](#11-json-brief-schema)
- [12) MVP Subset](#12-mvp-subset)
- [13) Non-Functional Requirements](#13-non-functional-requirements)
- [14) Detailed Notes & Edge Requirements](#14-detailed-notes--edge-requirements)
- [15) Development Process & Governance](#15-development-process--governance)
- [16) Open TODOs](#16-open-todos)
- [17) Traceability](#17-traceability)

---

## 0) Scope & Definitions
- **Data Handler (DH)**: Loads, normalizes, validates, and serves market data; resampling and feature pipelines.
- **Strategy Engine (SE)**: Purely for signal generation. Computes indicators and applies rules to produce a `long`, `short`, or `flat` signal for each bar. Must be instrument-agnostic.
- **Regime Market Manager (RMM)**: Classifies market state (e.g., `trending`, `ranging`) to be used as a filter.
- **Portfolio Manager (PM)**: The state machine for the portfolio. Manages positions, cash, and equity. Processes orders and calculates PnL based on canonical inputs.
- **Risk & Exit Manager (REM)**: Defines how an open position should be managed. Specifies exit conditions such as stop-loss and take-profit. These rules can be instrument-aware (e.g., using "pips" for Forex).
- **Rule Translator (RT)**: A shared utility that translates native rule definitions (e.g., from the REM) into canonical, executable values for a given instrument.
- **Backtester (BT)**: The simulation engine. Orchestrates all other components for a historical run. Binds a Strategy, a Risk/Exit Model, and an Instrument to generate trades.
- **Execution Layer (EL)**: The live trading engine. Orchestrates components for a live run.
- **Reporting & Visualization (RV)**: Generates JSON briefs, plots, dashboards, exports.
- **AI Lab (AI)**: Consumes briefs to provide analysis and recommendations.
- **Utilities (UTIL)**: Logging, config, serialization, math, validation.

---

## 1) System-Wide Requirements
- **[SYS-1.1] Architecture**:
  - **[SYS-1.1.1]** Modular separation is paramount. The core components (SE, REM, PM, RMM) must be decoupled.
  - **[SYS-1.1.2]** A **Run Configuration** binds these components together for a specific backtest or live trading session. It specifies the instrument, the strategy to use, the risk model to apply, the data source, etc.
- **[SYS-1.2] Inter-Module Communication & Boundaries**:
  - **[SYS-1.2.1]** To facilitate a future split into multiple repositories, modules must communicate only through well-defined public APIs (e.g., functions and classes exposed in `__init__.py` files).
  - **[SYS-1.2.2]** Direct imports of internal sub-modules (e.g., `from trading_platform.data.internal_helpers import ...`) are strictly forbidden.
  - **[SYS-1.2.3]** **No circular dependencies** between top-level modules (e.g., `data`, `strategy`, `backtester`) will be permitted. This will be enforced via static analysis tools in the CI pipeline.
  - **[SYS-1.2.4]** A `trading_platform.core` module will house shared data structures (e.g., canonical models for `Bar`, `Trade`) and utilities that all other modules can depend on.
- **[SYS-1.3] Instrument Agnostic Architecture**:
  - **[SYS-1.3.1]** The core engine (Portfolio Manager) must operate on a canonical representation of trades, positions, and performance.
  - **[SYS-1.3.2]** An **Instrument Definition** (part of the Data Handler) provides rich metadata for each symbol required for runtime translation (e.g., `point_value`, `tick_size`).
  - **[SYS-1.3.3]** User-facing components (e.g., Risk & Exit Manager configuration) may allow inputs in native terms (pips, points), but these **must be translated** into the canonical model by the Backtester or Execution Layer at runtime before being passed to the Portfolio Manager.
  - **[SYS-1.3.4]** All core PnL calculations must be performed in a consistent base currency.
- **[SYS-1.4] Strategy Comparison & A/B Testing**:
  - **[SYS-1.4.1]** The platform must support running comparative analyses between two or more strategy variations.
  - **[SYS-1.4.2]** This includes comparing a baseline strategy against a version with modified parameters, different risk models, or additional signal layers (e.g., with and without an AI-driven event filter).
  - **[SYS-1.4.3]** The results must be presented in a comparative format, highlighting differences in key performance metrics.
- **[SYS-1.5] Trading Sessions & Blackout Periods**:
  - **[SYS-1.5.1]** The system must support the definition of trading blackout periods, during which no new positions can be opened.
  - **[SYS-1.5.2]** These periods can be defined as:
    - **Static Rules**: e.g., "do not trade between 23:00 and 01:00 UTC daily".
    - **Event-Based**: e.g., "pause trading 10 minutes before and 30 minutes after any event with `impact: high`".
  - **[SYS-1.5.3]** This functionality will be managed centrally and applied by the Backtester (BT) and Execution Layer (EL) to ensure consistent behavior. Strategies may choose to override or ignore these blackouts via configuration.
  - **[SYS-1.5.4]** A centralized trading window policy in the core module (TradingWindowPolicy) will enforce blackout rules. Both BT and EL must consult this policy before opening new positions.
  - **[SYS-1.5.5]** The platform will support an event/news calendar to populate event-based blackout windows (for example high-impact economic releases), configurable per strategy or run.
- **[SYS-1.6] Deployment & Operations**:
  - **[SYS-1.6.1]** **Containerization**: The application and its dependencies must be containerizable (e.g., using Docker) to ensure consistent environments from local development to production.
  - **[SYS-1.6.2]** **CI/CD**: A continuous integration pipeline (e.g., GitHub Actions) must be established to automatically run tests, linting, and type-checking on every commit/pull request.
  - **[SYS-1.6.3]** **Dependency Management**: Project dependencies must be explicitly managed via `pyproject.toml` (e.g., using Poetry or PDM) to ensure reproducible builds.
  - **[SYS-1.6.4]** The system must support **cloud-scale CI/CD execution**, enabling distributed parameter sweeps and backtests in CI pipelines.
- **[SYS-1.7] Configuration & Reproducibility**:
  - **[SYS-1.7.1]** All runs reproducible with persisted `run_id` & config snapshot.
  - **[SYS-1.7.2]** Configurable via JSON/YAML; CLI overrides supported.
  - **[SYS-1.7.3]** The system must include explicit **AI interpretability/traceability requirements**, ensuring all AI-driven outputs are reproducible and auditable.
- **[SYS-1.8] Time & Markets**:
  - **[SYS-1.8.1]** Primary focus on Forex (EUR/USD, USD/JPY, AUD/USD, etc.).
  - **[SYS-1.8.2]** Handle 20+ years of minute data.
  - **[SYS-1.8.3]** Store timestamps in UTC; daylight-saving safe.
- **[SYS-1.9] Performance**:
  - **[SYS-1.9.1]** Vectorized core operations; batch I/O; memory-aware iterators.
  - **[SYS-1.9.2]** Able to process multi-year minute data on laptop/Colab.
- **[SYS-1.10] Test & Behavior-Driven Development (TDD/BDD)**:
  - **[SYS-1.10.1]** All new functionality must be developed using Test-Driven Development (TDD). Tests must be written before the implementation code.
  - **[SYS-1.10.2]** Every function, module, and component must have corresponding unit and integration tests. 100% test coverage is the target for all new code.
  - **[SYS-1.10.3]** Behavior-Driven Development (BDD) with Gherkin (`.feature` files) will be used to ensure requirements are directly translated into executable specifications. This provides living documentation and guarantees alignment between requirements and deliverables.
- **[SYS-1.11] Quality & Tooling**:
  - **[SYS-1.11.1]** SonarQube for static analysis.
  - **[SYS-1.11.2]** Cloud free tier limit = ~50k LOC; repo split required beyond ~100k LOC.
  - **[SYS-1.11.3]** Pre-commit hooks for formatting, linting, type-checking.
- **[SYS-1.12] Cost Constraints**:
  - **[SYS-1.12.1]** Must run locally or in free-tier cloud environments.
  - **[SYS-1.12.2]** No paid infra required for MVP.
- **[SYS-1.13] Security**:
  - **[SYS-1.13.1]** API keys stored in environment variables / secret manager.
  - **[SYS-1.13.2]** Never commit credentials.
  - **[SYS-1.13.3]** All external inputs (e.g., API responses, config files) must be validated to prevent injection or corruption issues.

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
  - **[DH-2.12.2]** **Canonical Event Schema**: All event data must be normalized into a canonical format: `{event_id, timestamp, source, type, headline, summary, content, metadata}`.
    - `type`: e.g., 'news', 'economic_report', 'central_bank_speech'.
    - `metadata`: A flexible field for pre-computed sentiment scores, named entities, relevance, etc.
  - **[DH-2.12.3]** **Storage & Retrieval**: Events must be stored efficiently to allow for fast time-range queries.
  - **[DH-2.12.4]** **Alignment**: The Data Handler must provide an interface to retrieve all events that occurred within the timeframe of a given bar or a set of bars. This enables direct alignment with market data for backtesting and analysis, and must work for any bar timeframe (e.g., M1, H1, D1), including those generated through resampling.
  - **[DH-2.12.5]** **Sources**: Initial sources can include public news APIs or RSS feeds for economic calendars.
- **[DH-2.13]** Interfaces:
  - **[DH-2.13.1]** Expose a `DataRequest(symbol, timeframe, start, end, features=[...]) -> DataFrame` interface.
  - **[DH-2.13.2]** Expose a `subscribe_events(callback) -> Subscription` interface for live event streaming.
- **[DH-2.14]** All functionality must be tested using golden dataset fixtures, schema invariants, and resampling correctness checks.
- **[DH-2.15]** The Data Handler must enable **sentiment/NLP features** from event metadata for direct use by the Strategy Engine, RMM, and AI Lab.
- **[DH-2.16]** The Data Handler must support **distributed/scalable pipelines** for large-scale backtests, including parallelized or serverless execution.

---

## 3) Strategy Engine (SE)
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**, indicating that the original conditions for the trade are no longer valid.
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.4.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.4.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.4.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.5]** **Declarative Strategies (Low-Code/No-Code)**
  - **[SE-3.5.1]** The system must support defining strategies using a declarative **YAML format**, distinct from Gherkin BDD files.
  - **[SE-3.5.2]** **Strategy Schema**: The YAML files will follow a defined schema representing rules, conditions, and indicators.
  - **[SE-3.5.3]** **Parameterization**: YAML's key-value structure naturally supports parameterization. Parameter sweeps will be orchestrated by the AI Lab, which can easily read, modify, and generate these YAML files.
  - **[SE-3.5.4]** **Execution**: The Strategy Engine will include a parser that loads a strategy definition from a YAML file and executes its logic.
  - **[SE-3.5.5]** **Testing**: The behavior of the YAML strategy parser and execution engine will be tested rigorously using Behavior-Driven Development (BDD) with Gherkin (`.feature` files). This ensures the implementation correctly interprets the strategy definitions.
- **[SE-3.6]** Use indicators from established libraries (e.g., `ta`) where possible to avoid duplication.
- **[SE-3.7]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.8]** The engine must support parameter sweeps orchestrated by the AI Lab.
- **[SE-3.9]** **YAML Schema Validation**
   - **[SE-3.9.1]** Strategy definitions written in YAML must be validated against the JSON Schema in `docs/schemas/strategy.schema.json` at load time.
   - **[SE-3.9.2]** Validation errors must fail fast with actionable messages (field name, expected type/enum, location path).
   - **[SE-3.9.3]** Unit tests must include at least one valid and one invalid YAML sample to verify the validator catches schema violations.
- **[SE-3.10]** The Strategy Engine must support **natural language–driven strategy definition**, allowing AI-assisted generation of strategies beyond YAML.
- **[SE-3.11]** The Strategy Engine must support **automated feature selection**, where AI recommends or removes indicators/features during testing.

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
- **[RMM-4.9]** **YAML Schema Validation**
   - **[RMM-4.9.1]** RMM configurations written in YAML must be validated against the JSON Schema in `docs/schemas/rmm.schema.json` at load time.
   - **[RMM-4.9.2]** Validation errors must fail fast with actionable messages (field name, expected type/enum, location path).
   - **[RMM-4.9.3]** Unit tests must include at least one valid and one invalid YAML sample to verify the validator catches schema violations.
- **[RMM-4.10]** The RMM must support **regime-adaptive portfolio allocation**, dynamically adjusting capital weighting by regime classification.
- **[RMM-4.11]** The RMM must incorporate **event-aware overlays**, integrating economic/news event features into its classification logic.

---

## 5) Portfolio Manager (PM)
- **[PM-5.1]** **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **[PM-5.2]** The PM works exclusively in **canonical terms**. It does not know about native concepts like "pips".
- **[PM-5.3]** **State Management**:
  - **[PM-5.3.1]** Track cash balance, open positions, and total equity (mark-to-market).
  - **[PM-5.3.2]** Maintain a log of all executed trades.
- **[PM-5.4]** **Order Processing**:
  - **[PM-5.4.1]** `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - **[PM-5.4.2]** `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **[PM-5.5]** **Position Sizing**: Implement sizing logic, including:
  - **[PM-5.5.1]** Fixed-risk (e.g., risk $100 per trade).
  - **[PM-5.5.2]** Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **[PM-5.6]** **Trade & PnL Logic**:
  - **[PM-5.6.1]** Generate a canonical `Trade` record upon position closure.
  - **[PM-5.6.2]** Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - **[PM-5.6.3]** Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **[PM-5.7]** **Portfolio-Level Risk Management**:
  - **[PM-5.7.1]** Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.
  - **[PM-5.7.2]** **Directional Position Caps**: Enforce a configurable limit on simultaneously open positions per direction (long/short) with a default of 1. When limits would be exceeded, the attempted entry must be skipped. Configuration example:
    ```yaml
    pm_limits:
      max_open_long: 1
      max_open_short: 1
    ```
- **[PM-5.8]** The Portfolio Manager must support **dynamic allocation policies** based on regime signals provided by the RMM.
- **[PM-5.9]** The Portfolio Manager must support **portfolio optimization methods**, including risk parity, Kelly criterion, and volatility targeting.

---

## 6) Risk & Exit Manager (REM)
- **[REM-6.1]** **Core Mandate**: To define the rules for managing an open position's risk and exits. It is the single source of truth for stop-loss and take-profit logic.
- **[REM-6.2]** REM configurations will be defined in a declarative YAML format, validated against a JSON Schema.
- **[REM-6.3]** The REM must support multiple types of exit rules, including:
  - **[REM-6.3.1]** **Static Rules**: Rules based on fixed values, such as a stop-loss or take-profit defined in native terms (e.g., `{ value: 50, type: pips }`) or universal terms (e.g., `{ value: 2.5, type: percent }`).
  - **[REM-6.3.2]** **Dynamic Rules**: Rules that derive their value from market data at the time of a trade's entry, such as referencing a feature value (e.g., `{ value: 2, type: atr }`).
- **[REM-6.4]** The REM must be a pluggable component, allowing different risk models to be tested with the same strategy without changing the strategy's definition.

---

## 7) Backtester (BT)
- **[BT-7.1]** **Core Responsibility**: To simulate the passage of time and orchestrate the interaction between the Data Handler, Strategy Engine, Portfolio Manager, and the Risk & Exit Manager.
- **[BT-7.2]** **Rule Translation**: The Backtester **uses the shared Rule Translator** to convert native REM rules (e.g., "50 pips") into canonical price levels, using metadata from the Instrument Definition.
- **[BT-7.3]** The primary mechanism will be an **iterative, bar-by-bar loop** that simulates the passage of time. A fully vectorized implementation is a potential future performance enhancement.
- **[BT-7.4]** The Backtester must **accept a configurable cost model at initialization and pass it to the Portfolio Manager**, which is responsible for all financial calculations.
- **[BT-7.5]** Support for multiple order types, including: market, stop, and limit.
- **[BT-7.6]** A configurable tie-break mechanism for scenarios where multiple exit conditions are met on the same bar (e.g., stop and take-profit).
- **[BT-7.7]** A "warm-up" period to ensure indicators are stable before trading signals are processed.
- **[BT-7.8]** Backtests must be deterministic, producing the same results from the same inputs and configuration.
- **[BT-7.9]** All backtesting logic must be validated, especially for fill logic and stop/TP precedence.
- **[BT-7.10]** **Counterfactual Skipped Trades (Filters/Policies)**:
   - **[BT-7.10.1]** The backtester must record attempted entries that were skipped due to a filter/policy (e.g., blackout window, regime filter, risk cap, position cap, user-defined filter).
   - **[BT-7.10.2]** Each skipped item must include: `timestamp`, `symbol`, `reason_code` (e.g., `blackout_static`, `blackout_event`, `regime_filter`, `risk_cap`, `position_cap`, `custom`), `policy_snapshot` (minimal), and optional `notes`.
- **[BT-7.11]** **Counterfactual Outcome Simulation**:
   - **[BT-7.11.1]** For each skipped entry, the backtester must simulate a counterfactual trade using the same fill and exit policies configured for the run (entry price convention, stop/tp rules, tie-breaks, costs).
   - **[BT-7.11.2]** The counterfactual must produce canonical outcomes: `cf_exit_time`, `cf_exit_price`, `cf_pnl_currency`, and, when available, `cf_mfe_currency`, `cf_mae_currency`, `cf_bars_held`.
   - **[BT-7.11.3]** Counterfactuals must be clearly flagged as hypothetical and must never affect the main equity/trades results.
- **[BT-7.12]** **Filter Impact Summary**:
   - **[BT-7.12.1]** The backtester must aggregate per-reason summaries (e.g., counts, total/mean/median `cf_pnl_currency`) to quantify the impact of each filter.
   - **[BT-7.12.2]** Summaries must be included in the run brief for downstream analysis and A/B comparisons of filter configurations.
- **[BT-7.13]** **Live Trading Deviation**: The Execution Layer (EL) must not simulate counterfactual outcomes; it may log skipped entries and reasons only. Counterfactual simulation is strictly a backtest-only feature.
- **[BT-7.14]** The Backtester must support **distributed/parallel execution**, enabling large-scale parameter sweeps and portfolio simulations.
- **[BT-7.15]** The Backtester must provide **scenario stress testing**, allowing simulation of market shocks (e.g., volatility spikes, liquidity droughts).

---

## 8) Execution Layer (EL)
- **[EL-8.1]** **Rule Translation**: Like the Backtester, the EL **uses the shared Rule Translator** to perform the same runtime translation of native risk rules from the REM into canonical orders to be sent to the broker.
- **[EL-8.2]** Implement a broker adapter for OANDA as the initial target.
- **[EL-8.3]** The adapter must map the internal canonical order format to the broker's specific API format.
- **[EL-8.4]** The adapter must handle API connectivity issues, including retries, exponential backoff, and rate-limit management.
- **[EL-8.5]** **Portfolio Interaction**: The EL must use the same `PortfolioManager` component as the backtester to ensure logical parity between simulation and live trading.
- **[EL-8.6]** The EL must handle live streams of both market data and event data, forwarding them to the active strategy for signal generation.
- **[EL-8.7]** All actions, orders, and broker responses must be captured via structured logging.
- **[EL-8.8]** Implement a reconciliation process to periodically check for discrepancies between the internal portfolio state and the broker's state.
- **[EL-8.9]** Enforce live risk management, including daily loss caps and other circuit breakers, as defined in the Portfolio Manager.

---

## 9) Reporting & Visualization (RV)
- **[RV-9.1]** Generate a machine-readable **JSON Brief** for each run, conforming to the schema in section 11.
- **[RV-9.2]** Generate **Comparison Reports** for A/B tests, presenting key metrics side-by-side for each variation.
- **[RV-9.3]** Generate plots with the following characteristics:
  - **[RV-9.3.1]** Overlays (e.g., EMAs, SMAs) must be auto-detected from strategy metadata.
  - **[RV-9.3.2]** Plotted lines for overlays must have distinct colors and be thinner than the primary price series.
  - **[RV-9.3.3]** Non-overlay indicators (e.g., ATR, RSI, Volume) must each be rendered in a separate panel below the main price chart.
  - **[RV-9.3.4]** The chart must include markers for trade entries, exits, stop-losses, and take-profits.
  - **[RV-9.3.5]** The chart must support optional shading to indicate different market regimes.
  - **[RV-9.3.6]** For comparison reports, the equity curves from all variations must be plotted on the same chart for easy comparison.
- **[RV-9.4]** Support exporting reports to multiple formats, including JSON, CSV, and a self-contained HTML file.
- **[RV-9.5]** Interactive controls for plots are desirable but not an MVP requirement, including toggling overlays and exporting the current view to PNG.
- **[RV-9.6]** **Field Definitions Section**:
  - **[RV-9.6.1]** The brief must include a top-level `field_definitions` section describing each field that appears anywhere in the brief. Each definition includes: `description`, `why_useful`, and `how_to_use`.
  - **[RV-9.6.2]** This section is auto-generated from a central registry to ensure consistency and versioned with the app.
- **[RV-9.7]** **Trade Context Snapshots**:
  - **[RV-9.7.1]** For each trade, include context at both entry and exit: `context_at_entry` and `context_at_exit`, containing regime, indicators, and notes.
  - **[RV-9.7.2]** These snapshots capture the values of indicators/features actually used by the strategy at decision time for downstream analysis.
- **[RV-9.8]** The Reporting module must support **interactive visual analytics**, including trade clustering, dynamic filtering, and zoomable regime overlays.
- **[RV-9.9]** The Reporting module must support **Monte Carlo equity overlays**, displaying robustness bands on equity curves.

---

## 10) AI Lab (AI)
- **[AI-10.1]** **Core Mandate**: The AI Lab must function as the central analysis component, consuming JSON briefs and other run artifacts to provide intelligent insights.
- **[AI-10.2]** **Analysis & Recommendations**:
  - **[AI-10.2.1]** Identify performance clusters (both winning and losing) based on features, regimes, and other trade attributes.
  - **[AI-10.2.2]** In comparison reports, quantify the statistical significance of performance differences between variations.
  - **[AI-10.2.3]** Recommend specific, machine-readable filters to improve performance (e.g., `{"feature": "ADX", "op": ">", "value": 25}`).
  - **[AI-10.2.4]** Recommend optimized stop-loss and take-profit configurations based on MFE/MAE analysis from the backtest.
  - **[AI-10.2.5]** Highlight potential data issues such as distributional drift and non-stationarity.
- **[AI-10.3]** **Advanced Testing Orchestration**:
  - **[AI-10.3.1]** Orchestrate parameter searches (e.g., grid search, random search) to find optimal parameter sets for a given strategy. This will be driven by a sweep configuration file.
  - **[AI-10.3.2]** Perform walk-forward evaluation (WFE) to test strategy robustness on out-of-sample data.
  - **[AI-10.3.3]** Conduct detailed regime analysis to break down strategy performance by market condition (e.g., trending, ranging).
  - **[AI-10.3.4]** The standard validation workflow will be a two-stage process: 1) Use parameter sweeps to discover optimal parameter sets. 2) Use Monte Carlo analysis on the best-performing set to validate its robustness.
- **[AI-10.4]** All findings and recommendations must be available in two formats:
  - **[AI-10.4.1]** A machine-readable JSON format for consumption by other tools.
  - **[AI-10.4.2]** A human-readable summary for direct user review.
- **[AI-10.5]** The AI Lab must support **automated hypothesis generation**, producing candidate entry/exit rules or strategy variants based on JSON briefs.
- **[AI-10.6]** The AI Lab must provide **explainability outputs** (e.g., feature attribution, importance scores) to justify AI recommendations.

---

## 11) JSON Brief Schema (Instrument-Agnostic)
- **[JSON-11.1]** **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **[JSON-11.2]** **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **[JSON-11.3]** **overall_performance** (base currency): `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **[JSON-11.4]** **risk_snapshot** (base currency): `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **[JSON-11.5]** **equity_stats**: `{equity_curve: [[timestamp, equity], ...], max_drawdown, dd_duration_bars}`.
- **[JSON-11.6]** **distribution**: `{pnl_mean, pnl_median, pnl_std, p05, p95}` (base currency; placeholders acceptable initially).
- **[JSON-11.7]** **streaks**: `{longest_win_streak, longest_loss_streak, current_streak}`.
- **[JSON-11.8]** **holding_time**: `{median_secs}` and optional buckets.
- **[JSON-11.9]** **activity**: `{trades_per_day}` (optional baseline).
- **[JSON-11.10]** **timing_buckets**: `{by_hour, by_dow, by_month}` (optional baseline).
- **[JSON-11.11]** **costs**: `{total_costs, avg_cost_per_trade, breakdown:{spread, commission, fees, slippage}}`.
- **[JSON-11.12]** **exposure**: `{average_gross_exposure, peak_gross_exposure}` (optional baseline).
- **[JSON-11.13]** **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **[JSON-11.14]** **regimes**: per-regime performance breakdown.
- **[JSON-11.15]** **stop_tp_candidates**: configs derived from MFE/MAE (in base currency; instrument-specific conversions occur via Instrument Definition at presentation/export time).
- **[JSON-11.16]** **monte_carlo**: resampling stats.
- **[JSON-11.17]** **walk_forward**: rolling OOS stats with instability flags.
- **[JSON-11.18]** **parameter_search**: top params, robustness notes.
- **[JSON-11.19]** **stationarity**: ADF, KPSS, drift tests.
- **[JSON-11.20]** **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
- **[JSON-11.21]** **data_quality**: loader flags, missing/duplicate bar counts, outlier flags.
- **[JSON-11.22]** **instrument_definitions**: snapshot per symbol `{tick_size, point_value, base_ccy, quote_ccy, lot_size, min_trade_unit}`.
- **[JSON-11.23]** **cost_model**: `{spread_model, commission_model, slippage_model, rollover_model, fee_params}`.
- **[JSON-11.24]** **fill_policy**: `{policy}` and details; **tie_break_policy**: `{policy}`.
- **[JSON-11.25]** **blackout_policy**: snapshot of blackout configuration `{blackout_utc, blackout_events}`.
- **[JSON-11.26]** **environment**: `{python_version, dependency_versions, platform, timezone}`.
- **[JSON-11.27]** **provenance**: `{app_version, git_commit, run_seed, data_start, data_end, symbols}`.
- **[JSON-11.28]** **checksums**: `{config_snapshot_hash, instrument_defs_hash}`.
- **[JSON-11.29]** **trades**: enhanced entries with `{r_multiple, mfe_currency, mae_currency, bars_held, holding_time_sec, features_at_entry, regime_label_at_entry, exit_reason, cost_breakdown}`.
  - For any trade closed by an REM rule, the brief must record the original **native rule** that triggered the exit (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`).
  - Include context snapshots at entry/exit (see [RV-9.7]).
- **[JSON-11.30]** **skipped_trades**: list of counterfactuals for filtered entries `[{timestamp, symbol, reason_code, policy_snapshot, cf_exit_time, cf_exit_price, cf_pnl_currency, cf_mfe_currency, cf_mae_currency, cf_bars_held}]`.
- **[JSON-11.31]** **filter_impact**: per-reason aggregates `{reason_code: {n_skipped, total_cf_pnl, mean_cf_pnl, median_cf_pnl}}`.
- **[JSON-11.32]** The JSON Brief must include **explainability fields**, such as feature importances and attribution scores linked to AI insights.
- **[JSON-11.33]** The JSON Brief must include **portfolio allocation rationale** whenever regime-based or optimization-driven allocation is applied.
- **[JSON-11.34]** All objects must be pure JSON types (convert pandas objects).

---

## 12) MVP Subset
- **Data Handler**: Core functionality including normalization, quality checks, and caching ([DH-2.1] through [DH-2.10]).
- **Strategy Engine**: Implement baseline strategies: SMA Crossover, PSAR+ADX, and BB Mean Reversion ([SE-3.4]).
- **RMM**: Baseline rule-based implementation ([RMM-4.1] through [RMM-4.3]).
- **Backtester**: Core simulation loop with ATR-based stops/TP, basic cost model, and generation of trades table and equity curve.
- **JSON Brief v1**: Initial brief generation covering `meta`, `params`, `overall_performance`, `risk_snapshot`, `contrasts`, and `stop_tp_candidates` ([JSON-11.1], [JSON-11.2], [JSON-11.3], [JSON-11.4], [JSON-11.13], [JSON-11.15]).
- **Reporting**: Auto-plotting of strategy overlays and indicators in separate panels below the main chart ([RV-9.3]).
- **AI Lab v1**: Initial analysis capabilities to consume briefs and suggest filters or parameters ([AI-10.2.3], [AI-10.2.4]).
- **Tests**: Unit test coverage for all components and a small end-to-end test fixture.

---

## 13) Non-Functional Requirements
- **[NFR-13.1]** **Performance**: Efficient with multi-year data.
- **[NFR-13.2]** **Reliability**: Deterministic backtests.
- **[NFR-13.3]** **Maintainability**: Clean modular package.
- **[NFR-13.4]** **Observability**: Structured logging; per-run artifact storage.
- **[NFR-13.5]** **Monitoring & Alerting**: For the Execution Layer (EL), a mechanism for health checks and alerts (e.g., for excessive errors, downtime, or large losses) must be implemented.
- **[NFR-13.6]** **Security**: Env var secrets; safe credential handling.

---

## 14) Detailed Notes & Edge Requirements
- **[NOTE-14.1]** Plots: overlays must not share identical colors; lines thinner than default.
- **[NOTE-14.2]** ATR and Volume must be plotted in separate panels (not combined).
- **[NOTE-14.3]** Each non-overlay indicator gets its own panel.
- **[NOTE-14.4]** Strategy plotting is auto-detected (don’t plot unused indicators).
- **[NOTE-14.5]** Backtester tie-break rule: `stop_then_tp` default.
- **[NOTE-14.6]** Repo may need splitting to satisfy SonarQube LOC cap.
- **[NOTE-14.7]** JSON serialization: `Timestamp` → ISO8601; `Timedelta` → seconds.
- **[NOTE-14.8]** AI briefs must include recommendations in machine-readable JSON.
- **[NOTE-14.9]** **Cost Model Canonical Shape** (applies to BT & EL):
  - The platform uses a single, canonical cost model shape. Legacy keys like `commission_per_unit` are not supported.
  - Canonical config (JSON/YAML equivalent):
    ```yaml
    cost_model:
      spread_per_unit: 0.0        # base-currency per unit, per side
      slippage_per_unit: 0.0      # base-currency per unit, per side
      commission:
        type: per_unit            # one of: per_unit | per_trade_flat | bps_notional
        value: 0.0                # float; meaning depends on type
    ```
  - Semantics:
    - `per_unit`: commission = `value * size`
    - `per_trade_flat`: commission = `value` per side
    - `bps_notional`: commission = `(price * size) * (value / 10_000)`
  - Spread and slippage are applied per side on both entry and exit.

---

## 15) Development Process & Governance
- **[GOV-15.1]** **Branching Strategy**: A standardized branching model (e.g., GitFlow or GitHub Flow) will be used.
- **[GOV-15.2]** **Code Reviews**: All code must be submitted via Pull Requests and requires at least one approval before merging to the main branch.
- **[GOV-15.3]** **Issue Tracking**: All work should be tracked in an issue tracker, with issue numbers referenced in commit messages.

---

## 16) Open TODOs
- [ ] Decide pandas vs Polars for long-run performance.
- [ ] Finalize baseline RMM thresholds and hysteresis.
- [ ] Define standard slippage/spread models.
- [ ] Publish example JSON brief under `/docs/examples/`.
- [ ] Add walk-forward eval and Monte Carlo to briefs.
- [ ] Execution Layer parity checks vs backtester.
- [ ] Decide repo split strategy for SonarQube.
- [ ] Plotting theme + interactive controls.

---

## 17) Traceability
- **[TRACE-17.1]** Each requirement in this document will be linked to a corresponding BDD `.feature` file.
- **[TRACE-17.2]** The Gherkin scenarios within these feature files will serve as the direct, automated mapping between the high-level requirement and the code that implements it.
