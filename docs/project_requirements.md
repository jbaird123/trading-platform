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
- **[SYS-1.6] Deployment & Operations**:
  - **[SYS-1.6.1]** **Containerization**: The application and its dependencies must be containerizable (e.g., using Docker) to ensure consistent environments from local development to production.
  - **[SYS-1.6.2]** **CI/CD**: A continuous integration pipeline (e.g., GitHub Actions) must be established to automatically run tests, linting, and type-checking on every commit/pull request.
  - **[SYS-1.6.3]** **Dependency Management**: Project dependencies must be explicitly managed via `pyproject.toml` (e.g., using Poetry or PDM) to ensure reproducible builds.
- **[SYS-1.7] Configuration & Reproducibility**:
  - **[SYS-1.7.1]** All runs reproducible with persisted `run_id` & config snapshot.
  - **[SYS-1.7.2]** Configurable via JSON/YAML; CLI overrides supported.
  - **[SYS-1.7.3]** **Run Configuration Schema**: A formal JSON Schema shall be created for the `Run Configuration`. This configuration will define, at a minimum: a reference to the `Strategy`, `Risk & Exit Manager (REM)` configuration, the `Instrument`(s), the data source and time range, and any other required components like the `Regime Market Manager (RMM)`.
  - **[SYS-1.7.4]** The system must include explicit **AI interpretability/traceability requirements**, ensuring all AI-driven outputs are reproducible and auditable.
- **[SYS-1.8] Time & Markets**:
  - **[SYS-1.8.1]** Primary focus on Forex (EUR/USD, USD/JPY, AUD/USD, etc.).
  - **[SYS-1.8.2]** Handle 20+ years of minute data.
  - **[SYS-1.8.3]** Store timestamps in UTC; daylight-saving safe.
- **[SYS-1.9] Performance**:
  - **[SYS-1.9.1]** Vectorized core operations; batch I/O; memory-aware iterators.
  - **[SYS-1.9.2]** Able to process multi-year minute data on laptop/Colab.
- **[SYS-1.10] Test & Behavior-Driven Development (TDD/BDD)**:
  - **[SYS-1.10.1]** All functionality must be developed using Test-Driven Development (TDD). Tests must be written before the implementation code.
  - **[SYS-1.10.2]** Every function, module, and component must have corresponding unit and integration tests. 100% test coverage is the target for all code.
  - **[SYS-1.10.3]** Behavior-Driven Development (BDD) with Gherkin (`.feature` files) will be used to ensure requirements are directly translated into executable specifications. This provides living documentation and guarantees alignment between requirements and deliverables.
  - **[SYS-1.10.4]** All functions must be tested directly; indirect testing is insufficient. Tests should focus on the specific behavior of the function under test.
  - **[SYS-1.10.5]** Test cases must be written and approved *before* any corresponding code changes are implemented. This enforces a strict Test-Driven Development (TDD) workflow.
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

### Future Enhancements
- **[SYS-F.1]** The system must support **cloud-scale CI/CD execution**, enabling distributed parameter sweeps and backtests in CI pipelines.

---

## 2) Data Handler (DH)

### Core Requirements
- **[DH-2.1]** Load historical market data from local CSV files that are pre-downloaded and conform to the system's normalized schema. (Note: MVP data is sourced from Dukascopy).
- **[DH-2.2]** Implement a live market data streaming connector for OANDA to be used by the Execution Layer during live trading.
- **[DH-2.3]** Normalize data to a schema with columns: `timestamp, open, high, low, close, volume`.
- **[DH-2.4]** The `timestamp` index must be timezone-aware and set to UTC.
- **[DH-2.5]** Resample data safely between timeframes (e.g., M1→H1→D) using correct OHLC aggregation rules.
- **[DH-2.6]** Perform validation checks to detect missing bars, duplicate timestamps, volume outliers, and price spikes.
- **[DH-2.7]** Produce a `quality_flags` report based on validation results.
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
- **[DH-2.12]** Expose a `DataRequest(symbol, timeframe, start, end, features=[...]) -> DataFrame` interface.
- **[DH-2.13]** All functionality must be tested using golden dataset fixtures, schema invariants, and resampling correctness checks.

### Future Enhancements
- **[DH-F.1]** Implement an automated data synchronization service to connect to Dukascopy's API and regularly update the local historical CSV data, ensuring it remains current.
- **[DH-F.2]** Implement a data versioning strategy (e.g., using DVC) to link backtest results to a specific dataset version.
- **[DH-F.3]** **Unstructured & Event Data (News/Reports)**: Ingest, store, and align time-series event data (news, economic reports) with market data.
- **[DH-F.4]** Enable **sentiment/NLP features** from event metadata for direct use by other components.
- **[DH-F.5]** Support **distributed/scalable pipelines** for large-scale backtests.

---

## 3) Strategy Engine (SE)

### Core Requirements
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**.
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including: SMA Crossover, PSAR with an ADX filter, and Bollinger Bands Mean Reversion.
- **[SE-3.5]** **Declarative Strategies (Low-Code/No-Code)**:
  - **[SE-3.5.1]** Support defining strategies using a declarative **YAML format**.
  - **[SE-3.5.2]** The YAML files will follow a defined schema for rules, conditions, and indicators.
  - **[SE-3.5.3]** The Strategy Engine will include a parser that loads and executes a strategy from a YAML file.
- **[SE-3.6]** Use indicators from established libraries (e.g., `pandas-ta`) where possible.
- **[SE-3.7]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.9]** **YAML Schema Validation**: Strategy YAML files must be validated against `docs/schemas/strategy.schema.json` at load time with actionable error messages.

### Future Enhancements
- **[SE-F.1]** The engine must support parameter sweeps orchestrated by the AI Lab ([SE-3.8]).
- **[SE-F.2]** Support **natural language–driven strategy definition**, allowing AI-assisted generation of strategies beyond YAML ([SE-3.10]).
- **[SE-F.3]** Support **automated feature selection**, where AI recommends or removes indicators/features during testing ([SE-3.11]).

---

## 4) Regime Market Manager (RMM)

### Core Requirements
- **[RMM-4.1]** Classify the market into regimes (e.g., `trend_up`, `trend_down`, `range`).
- **[RMM-4.2]** Each classification must output both a `label` and a `confidence` score (0–1).
- **[RMM-4.3]** The baseline implementation will be rule-based, using indicators such as ADX, MA slope, and ATR %.
- **[RMM-4.6]** The module must expose a policy function to determine if trading is allowed, for example: `is_trade_allowed(strategy, regime_label, confidence) -> bool`.
- **[RMM-4.7]** Policies should be configurable per-strategy and include hysteresis to reduce rapid state changes.
- **[RMM-4.8]** All classification logic must be tested using synthetic data sequences.
- **[RMM-4.9]** **YAML Schema Validation**: RMM YAML configurations must be validated against `docs/schemas/rmm.schema.json` at load time.

### Future Enhancements
- **[RMM-F.1]** The RMM must be extensible to allow for future ML-based classifiers ([RMM-4.4]).
- **[RMM-F.2]** The module must expose a rich API that returns the current regime and its features: `RMMResult(timestamp, label, confidence, features={...})` ([RMM-4.5]).
- **[RMM-F.3]** Support **regime-adaptive portfolio allocation**, dynamically adjusting capital weighting by regime classification ([RMM-4.10]).
- **[RMM-F.4]** Incorporate **event-aware overlays**, integrating economic/news event features into its classification logic ([RMM-4.11]).

---

## 5) Portfolio Manager (PM)

### Core Requirements
- **[PM-5.1]** **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time.
- **[PM-5.2]** The PM works exclusively in **canonical terms** (e.g., it does not know about "pips").
- **[PM-5.3]** **State Management**: Track cash balance, open positions, and total equity (mark-to-market), and maintain a log of all executed trades.
- **[PM-5.4]** **Order Processing**: Process incoming signals to generate orders and update position values based on new market data.
- **[PM-5.5]** **Position Sizing**: Implement fixed-risk and fixed-fraction sizing logic.
- **[PM-5.6]** **Trade & PnL Logic**: Generate a canonical `Trade` record upon position closure and calculate key performance metrics.
- **[PM-5.7]** **Portfolio-Level Risk Management**: Enforce rules like daily loss caps, maximum drawdown limits, and directional position caps.

### Future Enhancements
- **[PM-F.1]** Support **dynamic allocation policies** based on regime signals provided by the RMM ([PM-5.8]).
- **[PM-F.2]** Support **portfolio optimization methods**, including risk parity, Kelly criterion, and volatility targeting ([PM-5.9]).

---

## 6) Risk & Exit Manager (REM)
- **[REM-6.1]** **Core Mandate**: To define the rules for managing an open position's risk and exits. It is the single source of truth for stop-loss and take-profit logic.
- **[REM-6.2]** REM configurations will be defined in a declarative YAML format, validated against a JSON Schema.
- **[REM-6.3]** The REM must support multiple types of exit rules, including static (e.g., fixed pips) and dynamic (e.g., ATR-based) rules.
- **[REM-6.4]** The REM must be a pluggable component, allowing different risk models to be tested with the same strategy.

---

## 7) Backtester (BT)

### Core Requirements
- **[BT-7.1]** **Core Responsibility**: To simulate the passage of time and orchestrate the interaction between other components.
- **[BT-7.2]** **Rule Translation**: The Backtester **uses the shared Rule Translator** to convert native REM rules (e.g., "50 pips") into canonical price levels.
- **[BT-7.3]** The primary mechanism will be an **iterative, bar-by-bar loop**. A fully vectorized implementation is a potential future performance enhancement.
- **[BT-7.4]** The Backtester must **accept a configurable cost model at initialization and pass it to the Portfolio Manager**.
- **[BT-7.5]** Support for multiple order types, including: market, stop, and limit.
- **[BT-7.6]** A configurable tie-break mechanism for scenarios where multiple exit conditions from the REM are met on the same bar (e.g., stop and take-profit).
- **[BT-7.7]** A "warm-up" period to ensure indicators are stable before trading signals are processed.
- **[BT-7.8]** Backtests must be deterministic.
- **[BT-7.9]** All backtesting logic must be validated, especially for fill logic and stop/TP precedence.
- **[BT-7.10]** **Counterfactual Skipped Trades**: Record attempted entries that were skipped due to any filter/policy (e.g., blackout, regime, risk cap).
- **[BT-7.11]** **Counterfactual Outcome Simulation**: For each skipped entry, simulate a counterfactual trade to produce hypothetical outcomes (PnL, MFE/MAE, etc.).
- **[BT-7.12]** **Filter Impact Summary**: Aggregate and summarize the impact of each filter based on counterfactual outcomes.
- **[BT-7.13]** **Live Trading Deviation**: The Execution Layer (EL) must not simulate counterfactual outcomes.
- **[BT-7.16]** **Exit Precedence Policy**: On any given bar, exit conditions shall be evaluated in the following order: 1. Risk-based exits from the REM (stop-loss and take-profit). 2. Strategic exits from the SE (a `flat` signal). The first valid exit condition encountered is the one that is executed and recorded. This policy must be applied identically by both the Backtester and the Execution Layer.

### Future Enhancements
- **[BT-F.1]** Support **distributed/parallel execution**, enabling large-scale parameter sweeps and portfolio simulations ([BT-7.14]).
- **[BT-F.2]** Provide **scenario stress testing**, allowing simulation of market shocks like volatility spikes ([BT-7.15]).

---

## 8) Execution Layer (EL)
- **[EL-8.1]** **Rule Translation**: Like the Backtester, the EL **uses the shared Rule Translator** to perform the same runtime translation of native risk rules.
- **[EL-8.2]** Implement a broker adapter for OANDA as the initial target.
- **[EL-8.3]** The adapter must map the internal canonical order format to the broker's specific API format.
- **[EL-8.4]** The adapter must handle API connectivity issues, including retries and rate-limit management.
- **[EL-8.5]** **Portfolio Interaction**: The EL must use the same `PortfolioManager` component as the backtester.
- **[EL-8.6]** The EL must handle live streams of both market data and event data.
- **[EL-8.7]** All actions, orders, and broker responses must be captured via structured logging.
- **[EL-8.8]** Implement a reconciliation process to check for discrepancies between the internal portfolio state and the broker's state.
- **[EL-8.9]** Enforce live risk management as defined in the Portfolio Manager.
- **[EL-8.10]** **Exit Precedence Policy**: The EL must adhere to the same Exit Precedence Policy defined in [BT-7.16] to ensure logical parity with the backtester.

---

## 9) Reporting & Visualization (RV)

### Core Requirements
- **[RV-9.1]** Generate a machine-readable **JSON Brief** for each run, conforming to the schema in section 11.
- **[RV-9.2]** Generate **Comparison Reports** for A/B tests, presenting key metrics side-by-side.
- **[RV-9.3]** Generate plots with auto-detected overlays, separate panels for non-overlay indicators, and markers for trades.
- **[RV-9.4]** Support exporting reports to JSON, CSV, and a self-contained HTML file.
- **[RV-9.6]** **Field Definitions Section**: The brief must include a `field_definitions` section describing each field.
- **[RV-9.7]** **Trade Context Snapshots**: For each trade, include context at both entry and exit (regime, indicators, etc.).

### Future Enhancements
- **[RV-F.1]** Support optional shading on plots to indicate different market regimes ([RV-9.3.5]).
- **[RV-F.2]** Plot equity curves from all variations on the same chart for comparison reports ([RV-9.3.6]).
- **[RV-F.3]** Add interactive plot controls (e.g., toggling overlays) ([RV-9.5]).
- **[RV-F.4]** Support **interactive visual analytics**, including trade clustering and dynamic filtering ([RV-9.8]).
- **[RV-F.5]** Support **Monte Carlo equity overlays**, displaying robustness bands on equity curves ([RV-9.9]).

---

## 10) AI Lab (AI)

### Core Requirements
- **[AI-10.1]** **Core Mandate**: The AI Lab must function as the central analysis component, consuming JSON briefs to provide intelligent insights.
- **[AI-10.1.1] Primary Objectives & Use Cases:** The AI Lab serves two distinct, high-level use cases with different requirements and priorities.

    - **Use Case #1: Offline Backtest Analysis & Diagnosis (Immediate Priority)**
        - **Goal:** To perform deep, post-hoc analysis of backtest results (`brief.json`) to uncover structural flaws, understand the drivers of P&L, and generate actionable insights for strategy improvement. This moves beyond simple parameter optimization to fundamental strategy diagnosis (e.g., identifying an inappropriate exit strategy).
        - **Requirements:** Analytical depth and model interpretability are the highest priorities. Inference speed is not a concern.
        - **Appropriate Models:** This use case allows for complex, computationally expensive models. Strong candidates include Gradient Boosting models (LightGBM, XGBoost), RandomForest, and model ensembles. More advanced techniques like sequential models (LSTMs, Transformers) or even Reinforcement Learning can be explored for deep research. Extensive use of interpretability libraries (e.g., SHAP) is expected.

    - **Use Case #2: Real-Time Decision Making (Future Goal)**
        - **Goal:** To provide a live, low-latency "second opinion" or filter for trading decisions made by the `StrategyEngine` or `ExecutionLayer`.
        - **Requirements:** Low-latency inference (e.g., sub-100ms) is the primary constraint.
        - **Appropriate Models:** Models must be lightweight and highly optimized for speed. Candidates include smaller Gradient Boosting models, simpler models like Logistic Regression on powerful features, or models "distilled" from the more complex analysis models developed in Use Case #1.
- **[AI-10.1.2] Input Data Required:**
    - **Backtest Briefs (`brief.json`):** Full backtest results, including trade logs, performance metrics (Sharpe, Sortino, PnL, drawdowns), MFE/MAE analysis, skipped trades with counterfactuals, and environment/provenance data.
    - **Strategy Definitions (YAML):** The raw strategy configuration, including indicator parameters and predicate logic.
    - **Historical Market Data (OHLCV):** Access to the same historical data used for backtesting, to allow for deeper analysis and visualization of problematic trade sequences.
    - **Technical Indicators:** Pre-computed or on-demand computation of various technical indicators relevant to the strategy and market analysis.
    - **Market Regime Classifications:** (If available from RMM) Current and historical market regime labels.
- **[AI-10.1.3] Output Data Produced:**
    - **Diagnostic Reports:** Detailed analysis of strategy weaknesses, including identified patterns of false signals, over-trading, or specific market conditions where the strategy fails.
    - **Actionable Recommendations:** Concrete suggestions for strategy modification (e.g., adding filters, adjusting parameters, changing indicator types, suggesting alternative entry/exit conditions).
    - **Risk Factor Identification:** Highlighting specific risk exposures or vulnerabilities in the strategy.
    - **Performance Predictions/Confidence Scores:** (For adaptive signal generation) Probability scores for trade success, confidence in signals, or predicted future performance.
    - **Visualizations:** Charts and graphs illustrating problematic areas, trade clusters, and proposed changes.
- **[AI-10.1.4] Constraints & Non-Functional Requirements:**
    - **Interpretability:** Recommendations and diagnoses must be human-readable and explainable, allowing developers to understand and implement changes.
    - **Latency (Diagnosis):** Offline processing is acceptable for detailed diagnosis.
    - **Latency (Adaptive Signals):** Low-latency inference (sub-100ms) required if used for real-time signal refinement.
    - **Throughput:** Capable of processing multiple backtest briefs concurrently.
    - **Scalability:** Ability to scale with increasing number of strategies and backtest runs.
- **[AI-10.1.5] Performance Metrics & Success Criteria:**
    - **Diagnosis Accuracy:** Ability to correctly identify known strategy flaws in a test suite of problematic strategies (e.g., 90% accuracy in identifying over-trading).
    - **Recommendation Efficacy:** Improvement in key performance metrics (Sharpe, PnL, drawdown) when recommendations are applied and re-backtested (e.g., average 10% improvement in Sharpe ratio for identified problematic strategies).
    - **False Positive Rate:** Low rate of incorrect diagnoses or unhelpful recommendations.
    - **Coverage:** Ability to diagnose a wide range of common strategy issues.
- **[AI-10.1.6] Data Granularity & Frequency:**
    - **Input Briefs:** Per backtest run.
    - **Historical Data:** OHLCV data at the same granularity as the strategy (e.g., 1-minute, 1-hour, daily).
    - **Output Recommendations:** Per strategy, after analysis.
- **[AI-10.2]** Recommend specific, machine-readable filters to improve performance.
- **[AI-10.3]** Recommend optimized stop-loss and take-profit configurations based on MFE/MAE analysis from the backtest.
- **[AI-10.4]** **Signal-Level Analysis**:
    - **[AI-10.4.1] Signal Characterization**: The AI Lab must be capable of analyzing the raw signal series (`long`, `short`, `flat`) produced by the Strategy Engine during a backtest.
    - **[AI-10.4.2] Signal Meta-Features**: It must compute quantitative meta-features to characterize the signal's behavior, including but not limited to:
        - `signal_persistence_pct`: The percentage of bars with an active `long` or `short` signal.
        - `avg_signal_duration_bars`: The average number of consecutive bars a signal remains active.
    - **[AI-10.4.3] Architectural Flaw Detection**: The AI Lab must be able to correlate these signal meta-features against the overall backtest performance to identify architectural flaws, such as a signal being a persistent state rather than a discrete event.
    - **[AI-10.4.4] Machine-Readable Critique**: The findings from this analysis must be included in the `brief.json` in a new `signal_quality_analysis` section.

- **[AI-10.5] Integration Points with Existing Platform Components:**
    - **[AI-10.5.1] DataHandler (DH):**
        - **Interaction:** The AI module will request historical OHLCV data and technical indicators from the `DataHandler` for training, feature engineering, and diagnostic analysis.
        - **Data Flow:** AI module -> `DataHandler` (request for data); `DataHandler` -> AI module (DataFrame of market data/features).
        - **Protocol:** Direct function calls or a well-defined API within the Python environment.
        - **Data Format:** Pandas DataFrames.
        - **Error Handling:** `DataHandler` exceptions (e.g., `DataNotFound`, `InvalidTimeframe`) should be caught by the AI module, leading to logging and graceful degradation or retry mechanisms.
        - **Security:** Data access within the platform's internal boundaries is assumed to be secure.
    - **[AI-10.5.2] StrategyEngine (SE):**
        - **Interaction:** The AI module will consume strategy YAML definitions from the `StrategyEngine` for analysis. In future phases, the AI module might provide refined signals or modified strategy parameters back to the `StrategyEngine`.
        - **Data Flow:** AI module -> `StrategyEngine` (request for strategy definition); `StrategyEngine` -> AI module (YAML string or parsed object).
        - **Protocol:** Direct function calls.
        - **Data Format:** YAML string or Python dictionary/object.
        - **Error Handling:** Invalid strategy definitions or parsing errors from `StrategyEngine` should be handled by the AI module, leading to diagnostic reports.
        - **Security:** Internal data exchange.
    - **[AI-10.5.3] Backtester (BT):**
        - **Interaction:** The AI module will primarily consume `brief.json` outputs from the `Backtester` for performance diagnosis. It may also trigger new backtest runs with modified strategy parameters.
        - **Data Flow:** `Backtester` -> AI module (`brief.json` file path or content); AI module -> `Backtester` (trigger new run with `RunConfig`).
        - **Protocol:** File system access for `brief.json`; direct function calls for triggering runs.
        - **Data Format:** JSON for briefs; Python objects for `RunConfig`.
        - **Error Handling:** Missing or malformed `brief.json` files should be logged. Backtester execution errors triggered by the AI module should be reported back.
        - **Security:** Internal file system access and function calls.
    - **[AI-10.5.4] Reporting & Visualization (RV):**
        - **Interaction:** The AI module will provide diagnostic reports, actionable recommendations, and potentially new visualizations to the `Reporting` module for inclusion in the final output.
        - **Data Flow:** AI module -> `Reporting` (JSON/Python objects for reports/recommendations/visualizations).
        - **Protocol:** Direct function calls.
        - **Data Format:** JSON or Python objects.
        - **Error Handling:** `Reporting` module errors during report generation should be logged by the AI module.
        - **Security:** Internal data exchange.
    - **[AI-10.5.5] Regime Market Manager (RMM) (Optional/Future):**
        - **Interaction:** The AI module may consume market regime classifications from the `RMM` as an input feature for its diagnostic or signal generation models.
        - **Data Flow:** `RMM` -> AI module (regime labels and confidence scores).
        - **Protocol:** Direct function calls.
        - **Data Format:** Python objects (e.g., `RMMResult`).
        - **Error Handling:** Handle cases where RMM data is unavailable or malformed.
        - **Security:** Internal data exchange.
    - **[AI-10.5.6] Execution Layer (EL) (Future):**
        - **Interaction:** In future live trading scenarios, the AI module might provide real-time signal refinements or risk adjustments to the `ExecutionLayer`.
        - **Data Flow:** AI module -> `ExecutionLayer` (real-time signals/adjustments).
        - **Protocol:** Message queue (e.g., Kafka) or low-latency REST API.
        - **Data Format:** JSON or custom binary format for performance.
        - **Error Handling:** Critical: Implement robust retry mechanisms, circuit breakers, and fallback strategies. Alerts for AI module failures.
        - **Security:** Authentication, authorization, and encryption for real-time data streams.

- **[AI-10.6] Dual-Engine Analysis Architecture**: The AI Lab will employ a hybrid analysis model consisting of two distinct engines:
    - **[AI-10.6.1] Quantitative Engine (`DiagnosticSynthesisEngine`)**: This engine is deterministic and rule-based. It is responsible for executing a series of pre-defined checks to identify specific, known anti-patterns and quantitative flaws in a backtest. Its output must be structured, machine-readable (JSON), and 100% reproducible.
    - **[AI-10.6.2] Qualitative Engine (`LLMAnalysisEngine`)**: This engine is responsible for providing high-level, narrative feedback on strategy structure and performance. It will use an external Large Language Model (LLM) to analyze the backtest brief and generate human-readable, qualitative insights that are not easily captured by deterministic rules.
    - **[AI-10.6.3] Separation of Concerns**: The outputs of the two engines must be strictly separated. The quantitative engine produces a deterministic `ai_diagnostic_report.json`, while the qualitative engine produces a non-deterministic `ai_qualitative_report.md`.

- **[AI-10.7] Optional, User-Initiated Qualitative Analysis**:
    - **[AI-10.7.1]** The qualitative analysis performed by the `LLMAnalysisEngine` must be an optional, user-initiated feature. It shall be triggered via a dedicated command-line flag (e.g., `--qualitative-report`) in the `ai-diagnose` command.
    - **[AI-10.7.2]** This feature may incur external API costs and introduce network latency. This directly relates to `[SYS-12.1]` and `[SYS-12.2]`, and the user must opt-in to use it.
    - **[AI-10.7.3]** The CLI help text for this feature must include a clear warning that it sends backtest data to a third-party API and may incur costs.
    - **[AI-10.7.4]** API credentials for the LLM service must be managed securely via environment variables, in accordance with `[SYS-13.1]`.

### Future Enhancements
- **[AI-F.1]** **Analysis & Recommendations**:
  - **[AI-F.1.1]** Identify performance clusters (winning and losing) based on features, regimes, etc. ([AI-10.2.1]).
  - **[AI-F.1.2]** In comparison reports, quantify the statistical significance of performance differences ([AI-10.2.2]).
  - **[AI-F.1.3]** Highlight potential data issues such as distributional drift and non-stationarity ([AI-10.2.5]).
- **[AI-F.2]** **Advanced Testing Orchestration**:
  - **[AI-F.2.1]** Orchestrate parameter searches (grid search, random search) ([AI-10.3.1]).
  - **[AI-F.2.2]** Perform walk-forward evaluation (WFE) ([AI-10.3.2]).
  - **[AI-F.2.3]** Conduct detailed regime analysis ([AI-10.3.3]).
  - **[AI-F.2.4]** Implement the standard two-stage validation workflow (sweep then Monte Carlo) ([AI-10.3.4]).
- **[AI-F.3]** All findings and recommendations must be available in both machine-readable JSON and human-readable summaries ([AI-10.4]).
- **[AI-F.4]** Support **automated hypothesis generation**, producing candidate entry/exit rules or strategy variants ([AI-10.5]).
- **[AI-F.5]** Provide **explainability outputs** (e.g., feature attribution, importance scores) to justify AI recommendations ([AI-10.6]).

---

## 11) JSON Brief Schema (Instrument-Agnostic)
- **[JSON-11.1]** **meta**: High-level metadata including `run_id`, `strategy_name`, `git_commit`, and `run_seed`.
- **[JSON-11.2]** **strategy_params**: A snapshot of the parameters used by the Strategy Engine.
- **[JSON-11.3]** **overall_performance**: `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **[JSON-11.4]** **risk_snapshot**: `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **[JSON-11.5]** **equity_stats**: `{equity_curve, drawdown_curve, max_drawdown, dd_duration_bars}`.
- **[JSON-11.6]** **distribution**: Statistical distribution of PnL including `{pnl_mean, pnl_median, pnl_std, p05, p95}`.
- **[JSON-11.7]** **streaks**: `{longest_win_streak, longest_loss_streak, current_streak}`.
- **[JSON-11.8]** **holding_time**: `{median_secs}`.
- **[JSON-11.9]** **costs**: `{total_costs, avg_cost_per_trade, breakdown: {spread, commission, slippage}}`.
- **[JSON-11.10]** **exposure**: `{average_gross_exposure, peak_gross_exposure}`.
- **[JSON-11.11]** **regimes**: A dictionary mapping each regime label to its performance breakdown.
- **[JSON-11.12]** **data_quality**: `{loader_flags, index_monotonic_increasing, duplicate_bars_count, nan_counts, has_nans, quality_score}`.
# - **[JSON-11.31]** **recommendations**: An array of recommendation objects, each with:
#   - `title`: The actionable recommendation title.
#   - `summary`: Description of the recommendation.
#   - `category`: Category (e.g., "Entry Logic", "Exit Logic", "Risk Management").
#   - `confidence`: Float between 0.0 and 1.0 indicating confidence in the recommendation.
- **[JSON-11.13]** **provenance**: `{run_id, strategy_name, data_start, data_end, symbols, app_version, git_commit, run_seed}`.
- **[JSON-11.14]** **environment**: `{python_version, platform, timezone, dependency_versions}`.
- **[JSON-11.15]** **trades**: An array of trade objects, each with full details including `pnl`, `entry_time`, `exit_time`, `mfe_currency`, `mae_currency`, etc. See [JSON-11.30] for the detailed trade object schema.
- **[JSON-11.16]** **skipped_trades**: An array of counterfactual trade objects that were skipped by a filter.
- **[JSON-11.17]** **filter_impact**: An object mapping each filter reason to its aggregated impact metrics.
- **[JSON-11.18]** **monte_carlo**: Placeholder for Monte Carlo simulation results.
- **[JSON-11.19]** **walk_forward**: Placeholder for walk-forward analysis results.
- **[JSON-11.20]** **parameter_search**: Placeholder for parameter search results.
- **[JSON-11.21]** **instrument_definitions**: A snapshot of the instrument metadata used in the run.
- **[JSON-11.22]** **cost_model**: A snapshot of the cost model configuration.
- **[JSON-11.23]** **fill_policy**: A snapshot of the fill policy configuration.
- **[JSON-11.24]** **tie_break_policy**: A snapshot of the exit tie-break policy.
- **[JSON-11.25]** **blackout_policy**: A snapshot of the blackout policy configuration.
- **[JSON-11.26]** **checksums**: `{config_snapshot_hash, instrument_defs_hash}`.
- **[JSON-11.27]** **field_definitions**: Auto-generated descriptions for all fields in the brief.
- **[JSON-11.28]** **artifacts**: A new top-level object to store paths to supplementary run artifacts, such as `{ "signals_path": "path/to/signals.parquet" }`.
- **[JSON-11.29]** **signal_quality_analysis**: A new top-level object to store the output from the Signal-Level Analysis, including the calculated meta-features and a summary critique.
- **[JSON-11.30]** **Trade Object Schema**: The `trades` array ([JSON-11.15]) shall contain objects with a detailed structure. Each trade object must include, in addition to core fields (pnl, times, etc.), the following context objects:
    - `entry_context`: An object containing indicator values, regime, etc., at the time of entry.
    - `exit_context`: An object containing indicator values, regime, etc., at the time of exit.
    - `sequential_context`: An object containing `bars_since_last_exit`, `pnl_of_last_trade`, and `exit_reason_of_last_trade`.
    - `risk_management_context`: An object containing `initial_stop_loss_price` and `initial_take_profit_price`.


### Future Enhancements
- **[JSON-F.4]** Add **stationarity** test results (ADF, KPSS, etc.).
- **[JSON-F.5]** Add **feature_analysis** (correlation matrix, importance scores).
- **[JSON-F.6]** Add **explainability fields** (feature attribution, etc.).
- **[JSON-F.7]** Add **portfolio allocation rationale**.

---

## 12) MVP Subset
- **Data Handler**: Core functionality including normalization, quality checks, and caching ([DH-2.1] through [DH-2.10]).
- **Strategy Engine**: Implement baseline strategies: SMA Crossover, PSAR+ADX, and BB Mean Reversion ([SE-3.4]).
- **RMM**: Baseline rule-based implementation ([RMM-4.1], [RMM-4.3]).
- **Backtester**: Core simulation loop with ATR-based stops/TP, basic cost model, and generation of trades table and equity curve.
- **JSON Brief v1**: Initial brief generation covering `meta`, `strategy_params`, `rem_config`, `overall_performance`, `risk_snapshot`, `contrasts`, and `stop_tp_candidates`.
- **Reporting**: Auto-plotting of strategy overlays and indicators in separate panels ([RV-9.3]).
- **AI Lab v1**: Initial analysis to suggest filters or parameters ([AI-10.2.3], [AI-10.2.4]).
- **Tests**: Unit test coverage for all components and a small end-to-end test fixture.

---

## 13) Non-Functional Requirements
- **[NFR-13.1]** **Performance**: Efficient with multi-year data.
- **[NFR-13.2]** **Reliability**: Deterministic backtests.
- **[NFR-13.3]** **Maintainability**: Clean modular package.
- **[NFR-13.4]** **Observability**: Structured logging; per-run artifact storage.
- **[NFR-13.5]** **Monitoring & Alerting**: For the Execution Layer (EL), a mechanism for health checks and alerts must be implemented.
- **[NFR-13.6]** **Security**: Env var secrets; safe credential handling.

---

## 14) Detailed Notes & Edge Requirements
- **[NOTE-14.1]** Plots: overlays must not share identical colors; lines thinner than default.
- **[NOTE-14.2]** ATR and Volume must be plotted in separate panels (not combined).
- **[NOTE-14.3]** Each non-overlay indicator gets its own panel.
- **[NOTE-14.4]** Strategy plotting is auto-detected (don’t plot unused indicators).
- **[NOTE-14.5]** Backtester tie-break rule for REM exits: `stop_then_tp` default.
- **[NOTE-14.6]** Repo may need splitting to satisfy SonarQube LOC cap.
- **[NOTE-14.7]** JSON serialization: `Timestamp` → ISO8601; `Timedelta` → seconds.
- **[NOTE-14.8]** AI briefs must include recommendations in machine-readable JSON. See [JSON-11.31] for schema.
- **[NOTE-14.9]** **Cost Model Canonical Shape** (applies to BT & EL):
  - The platform uses a single, canonical cost model shape.
  - See definition for `spread_per_unit`, `slippage_per_unit`, and `commission`.

---

## 15) Development Process & Governance
- **[GOV-15.1]** **Branching Strategy**: A standardized branching model will be used.
- **[GOV-15.2]** **Code Reviews**: All code must be submitted via Pull Requests and requires at least one approval.
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
- **[TRACE-17.1]** Each requirement must be traceable to one or more automated tests.
- **[TRACE-17.2]** For requirements validated by **BDD**, this link is achieved through corresponding `.feature` files and Gherkin scenarios.
- **[TRACE-17.3]** For requirements validated by **TDD**, the corresponding unit or integration test files must include a comment referencing the requirement ID(s) they satisfy (e.g., `# Validates: [SYS-1.10.2]`).
