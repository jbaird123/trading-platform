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
- [18) Pending updates (awaiting approval)](#18-pending-updates-awaiting-approval)

---

## 0) Scope & Definitions
- **Data Handler (DH)**: Loads, normalizes, validates, and serves market data; resampling and feature pipelines.
- **Strategy Engine (SE)**: Purely for signal generation. Computes indicators and applies rules to produce a `long`, `short`, or `flat` signal for each bar. Must be instrument-agnostic.
- **Regime Market Manager (RMM)**: Classifies market state (e.g., `trending`, `ranging`) to be used as a filter.
- **Portfolio Manager (PM)**: The state machine for the portfolio. Manages positions, cash, and equity. Processes orders and calculates PnL based on canonical inputs.
- **Risk & Exit Manager (REM)**: Defines how an open position should be managed. Specifies exit conditions such as stop-loss and take-profit. These rules can be instrument-aware (e.g., using "pips" for Forex).
- **Backtester (BT)**: The simulation engine. Orchestrates all other components for a historical run. Binds a Strategy, a Risk/Exit Model, and an Instrument to generate trades.
- **Execution Layer (EL)**: The live trading engine. Orchestrates components for a live run.
- **Reporting & Visualization (RV)**: Generates JSON briefs, plots, dashboards, exports.
- **AI Lab (AI)**: Consumes briefs to provide analysis and recommendations.
- **Utilities (UTIL)**: Logging, config, serialization, math, validation.

---

## 1) System-Wide Requirements
- **Architecture**
  - Modular separation is paramount. The core components (SE, REM, PM, RMM) must be decoupled.
  - A **Run Configuration** binds these components together for a specific backtest or live trading session. It specifies the instrument, the strategy to use, the risk model to apply, the data source, etc.
- **Inter-Module Communication & Boundaries**
  - To facilitate a future split into multiple repositories, modules must communicate only through well-defined public APIs (e.g., functions and classes exposed in `__init__.py` files).
  - Direct imports of internal sub-modules (e.g., `from trading_platform.data.internal_helpers import ...`) are strictly forbidden.
  - **No circular dependencies** between top-level modules (e.g., `data`, `strategy`, `backtester`) will be permitted. This will be enforced via static analysis tools in the CI pipeline.
  - A `trading_platform.core` module will house shared data structures (e.g., canonical models for `Bar`, `Trade`) and utilities that all other modules can depend on.
- **Instrument Agnostic Architecture**
  - The core engine (Portfolio Manager) must operate on a canonical representation of trades, positions, and performance.
  - An **Instrument Definition** (part of the Data Handler) provides rich metadata for each symbol required for runtime translation (e.g., `point_value`, `tick_size`).
  - User-facing components (e.g., Risk & Exit Manager configuration) may allow inputs in native terms (pips, points), but these **must be translated** into the canonical model by the Backtester or Execution Layer at runtime before being passed to the Portfolio Manager.
  - All core PnL calculations must be performed in a consistent base currency.
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
  - A centralized trading window policy in the core module (TradingWindowPolicy) will enforce blackout rules. Both BT and EL must consult this policy before opening new positions.
  - The platform will support an event/news calendar to populate event-based blackout windows (for example high-impact economic releases), configurable per strategy or run.
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
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**, indicating that the original conditions for the trade are no longer valid.
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.4.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.4.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.4.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.5]** **Declarative Strategies (Low-Code/No-Code)**
  - **[SE-3.5.1]** The system must support defining strategies using a declarative **YAML format**, distinct from Gherkin BDD files.
  - **Strategy Schema**: The YAML files will follow a defined schema representing rules, conditions, and indicators.
  - **Parameterization**: YAML's key-value structure naturally supports parameterization. Parameter sweeps will be orchestrated by the AI Lab, which can easily read, modify, and generate these YAML files.
  - **Execution**: The Strategy Engine will include a parser that loads a strategy definition from a YAML file and executes its logic.
  - **Testing**: The behavior of the YAML strategy parser and execution engine will be tested rigorously using Behavior-Driven Development (BDD) with Gherkin (`.feature` files). This ensures the implementation correctly interprets the strategy definitions.
- **[SE-3.6]** Use indicators from established libraries (e.g., `ta`) where possible to avoid duplication.
- **[SE-3.7]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.8]** The engine must support parameter sweeps orchestrated by the AI Lab.
- **[SE-3.9]** YAML Schema Validation
   - Strategy definitions written in YAML must be validated against the
     JSON Schema in `docs/schemas/strategy.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

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
 - **[RMM-4.9] YAML Schema Validation**
   - RMM configurations written in YAML must be validated against the JSON
     Schema in `docs/schemas/rmm.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

---

## 5) Portfolio Manager (PM)
- **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **[PM-5.1]** The PM works exclusively in **canonical terms**. It does not know about native concepts like "pips".
- **State Management**:
  - **[PM-5.2]** Track cash balance, open positions, and total equity (mark-to-market).
  - **[PM-5.3]** Maintain a log of all executed trades.
- **Order Processing**:
  - **[PM-5.4]** `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - **[PM-5.5]** `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **Position Sizing**: Implement sizing logic, including:
  - **[PM-5.6]** Fixed-risk (e.g., risk $100 per trade).
  - **[PM-5.7]** Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **Trade & PnL Logic**:
  - **[PM-5.8]** Generate a canonical `Trade` record upon position closure.
  - **[PM-5.9]** Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - **[PM-5.10]** Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **Portfolio-Level Risk Management**:
  - **[PM-5.11]** Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.

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
- **[BT-7.2]** **Runtime Translation**: The BT is responsible for translating native rules from the REM (e.g., "50 pips") into canonical price levels. It uses the Instrument Definition's metadata to perform this translation at runtime.
- **[BT-7.3]** The primary mechanism will be an event-driven or vectorized loop that iterates through historical data.
- **[BT-7.4]** Support for multiple order types, including: market, stop, and limit.
- **[BT-7.5]** A configurable tie-break mechanism for scenarios where multiple exit conditions are met on the same bar (e.g., stop and take-profit).
- **[BT-7.6]** A configurable cost model to simulate slippage, rollover, commissions, fees, and spreads, driven by the instrument definition.
- **[BT-7.7]** A "warm-up" period to ensure indicators are stable before trading signals are processed.
- **[BT-7.8]** Backtests must be deterministic, producing the same results from the same inputs and configuration.
- **[BT-7.9]** All backtesting logic must be validated, especially for fill logic and stop/TP precedence.
- **[BT-7.10] Counterfactual Skipped Trades (Filters/Policies)**
   - The backtester must record attempted entries that were skipped due to a filter/policy (e.g., blackout window, regime filter, risk cap, user-defined filter).
   - Each skipped item must include: `timestamp`, `symbol`, `reason_code` (e.g., `blackout_static`, `blackout_event`, `regime_filter`, `risk_cap`, `custom`), `policy_snapshot` (minimal), and optional `notes`.
- **[BT-7.11] Counterfactual Outcome Simulation**
   - For each skipped entry, the backtester must simulate a counterfactual trade using the same fill and exit policies configured for the run (entry price convention, stop/tp rules, tie-breaks, costs).
   - The counterfactual must produce canonical outcomes: `cf_exit_time`, `cf_exit_price`, `cf_pnl_currency`, and, when available, `cf_mfe_currency`, `cf_mae_currency`, `cf_bars_held`.
   - Counterfactuals must be clearly flagged as hypothetical and must never affect the main equity/trades results.
- **[BT-7.12] Filter Impact Summary**
   - The backtester must aggregate per-reason summaries (e.g., counts, total/mean/median `cf_pnl_currency`) to quantify the impact of each filter.
   - Summaries must be included in the run brief for downstream analysis and A/B comparisons of filter configurations.
- **[BT-7.13] Live Trading Deviation**
   - The Execution Layer (EL) must not simulate counterfactual outcomes; it may log skipped entries and reasons only. Counterfactual simulation is strictly a backtest-only feature.

---

## 8) Execution Layer (EL)
- **[EL-8.1]** **Runtime Translation**: Like the Backtester, the EL is responsible for performing the same runtime translation of native risk rules from the REM into canonical orders to be sent to the broker.
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

---

## 11) JSON Brief Schema (Instrument-Agnostic)
- **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **overall_performance** (base currency): `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **risk_snapshot** (base currency): `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **equity_stats**: `{equity_curve: [[timestamp, equity], ...], max_drawdown, dd_duration_bars}`.
- **distribution**: `{pnl_mean, pnl_median, pnl_std, p05, p95}` (base currency; placeholders acceptable initially).
- **streaks**: `{longest_win_streak, longest_loss_streak, current_streak}`.
- **holding_time**: `{median_secs}` and optional buckets.
- **activity**: `{trades_per_day}` (optional baseline).
- **timing_buckets**: `{by_hour, by_dow, by_month}` (optional baseline).
- **costs**: `{total_costs, avg_cost_per_trade, breakdown:{spread, commission, fees, slippage}}`.
  - See `docs/examples/brief_costs_section.md` for schema details and examples.
- **exposure**: `{average_gross_exposure, peak_gross_exposure}` (optional baseline).
- **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **regimes**: per-regime performance breakdown.
- **stop_tp_candidates**: configs derived from MFE/MAE (in base currency; instrument-specific conversions occur via Instrument Definition at presentation/export time).
- **monte_carlo**: resampling stats.
- **walk_forward**: rolling OOS stats with instability flags.
- **parameter_search**: top params, robustness notes.
- **stationarity**: ADF, KPSS, drift tests.
- **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
- **data_quality**: loader flags, missing/duplicate bar counts, outlier flags.
- **instrument_definitions**: snapshot per symbol `{tick_size, point_value, base_ccy, quote_ccy, lot_size, min_trade_unit}`.
- **cost_model**: `{spread_model, commission_model, slippage_model, rollover_model, fee_params}`.
- **fill_policy**: `{policy}` and details; **tie_break_policy**: `{policy}`.
 - **blackout_policy**: snapshot of blackout configuration `{blackout_utc, blackout_events}`.
- **environment**: `{python_version, dependency_versions, platform, timezone}`.
- **provenance**: `{app_version, git_commit, run_seed, data_start, data_end, symbols}`.
- **checksums**: `{config_snapshot_hash, instrument_defs_hash}`.
- **trades**: enhanced entries with `{r_multiple, mfe_currency, mae_currency, bars_held, holding_time_sec, features_at_entry, regime_label_at_entry, exit_reason, cost_breakdown}`.
  - For any trade closed by an REM rule, the brief must record the original **native rule** that triggered the exit (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`).
  - See `docs/examples/trades_cost_breakdown.md` for `cost_breakdown` semantics and how it rolls up to `costs`.
  - New: context snapshots at entry/exit (see [RV-8.9]).
 - **skipped_trades**: list of counterfactuals for filtered entries `[{timestamp, symbol, reason_code, policy_snapshot, cf_exit_time, cf_exit_price, cf_pnl_currency, cf_mfe_currency, cf_mae_currency, cf_bars_held}]`.
 - **filter_impact**: per-reason aggregates `{reason_code: {n_skipped, total_cf_pnl, mean_cf_pnl, median_cf_pnl}}`.
- Pure JSON types only (convert pandas objects).

Notes:
- The brief is canonical and instrument-agnostic. Any UI/export layer may render instrument-native units (e.g., pips, ticks) by translating the canonical brief via the Instrument Definition (e.g., `tick_size`, `point_value`).

---

## 12) MVP Subset
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

## 13) Non-Functional Requirements
- **Performance**: Efficient with multi-year data.
- **Reliability**: Deterministic backtests.
- **Maintainability**: Clean modular package.
- **Observability**: Structured logging; per-run artifact storage.
- **Monitoring & Alerting**: For the Execution Layer (EL), a mechanism for health checks and alerts (e.g., for excessive errors, downtime, or large losses) must be implemented.
- **Security**: Env var secrets; safe credential handling.

---

## 14) Detailed Notes & Edge Requirements
- Plots: overlays must not share identical colors; lines thinner than default.
- ATR and Volume must be plotted in separate panels (not combined).
- Each non-overlay indicator gets its own panel.
- Strategy plotting is auto-detected (don’t plot unused indicators).
- Backtester tie-break rule: `stop_then_tp` default.
- Repo may need splitting to satisfy SonarQube LOC cap.
- JSON serialization: `Timestamp` → ISO8601; `Timedelta` → seconds.
- AI briefs must include recommendations in machine-readable JSON.

- Cost Model Canonical Shape (applies to BT & EL)
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

## 9) Reporting & Visualization (RV) — Additions
- **[RV-9.9] Field Definitions Section**
  - The brief must include a top-level `field_definitions` section describing each field that appears anywhere in the brief. Each definition includes:
    - `description`: what the field means,
    - `why_useful`: why it matters for analysis/decision-making,
    - `how_to_use`: guidance for downstream tools and humans.
  - This section is auto-generated from a central registry to ensure consistency and versioned with the app.
- **[RV-9.10] Trade Context Snapshots**
  - For each trade, include context at both entry and exit:
    - `context_at_entry`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
    - `context_at_exit`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
  - These snapshots capture the values of indicators/features actually used by the strategy at decision time.
  - Downstream usage: performance slicing by regime/indicator ranges; explanation overlays in reports.

---

## 5) Portfolio Manager (PM) — Additions
- **[PM-5.11] Directional Position Caps**
  - Configurable limit on simultaneously open positions per direction (long/short) with a default of 1.
  - Enforced identically in BT and EL. Configuration example:
    ```yaml
    pm_limits:
      max_open_long: 1
      max_open_short: 1
    ```
  - When limits would be exceeded, the attempted entry must be skipped.

---

## 7) Backtester (BT) — Additions
- Extend skipped-trade logging requirements:
  - Add `position_cap` to the allowed `reason_code` set in [BT-7.10].
  - Ensure these skips are included in `skipped_trades` and summarized in `filter_impact` ([BT-7.12]).


---

## 15) Development Process & Governance
- **Branching Strategy**: A standardized branching model (e.g., GitFlow or GitHub Flow) will be used.
- **Code Reviews**: All code must be submitted via Pull Requests and requires at least one approval before merging to the main branch.
- **Issue Tracking**: All work should be tracked in an issue tracker, with issue numbers referenced in commit messages.

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
- Each requirement in this document will be linked to a corresponding BDD `.feature` file.
- The Gherkin scenarios within these feature files will serve as the direct, automated mapping between the high-level requirement and the code that implements it.

---

## 18) Pending updates (awaiting approval)

> Proposed requirement changes identified during gap analysis (Sept 2025). Once approved, these will be merged into their respective module sections.

### AI Lab
- **[AI-10.x]** The AI Lab must support **automated hypothesis generation**, producing candidate entry/exit rules or strategy variants based on JSON briefs.
- **[AI-10.x]** The AI Lab must provide **explainability outputs** (e.g., feature attribution, importance scores) to justify AI recommendations.

### Regime Market Manager (RMM)
- **[RMM-4.x]** The RMM must support **regime-adaptive portfolio allocation**, dynamically adjusting capital weighting by regime classification.
- **[RMM-4.x]** The RMM must incorporate **event-aware overlays**, integrating economic/news event features into its classification logic.

### Data Handler
- **[DH-2.x]** The Data Handler must enable **sentiment/NLP features** from event metadata for direct use by the Strategy Engine, RMM, and AI Lab.
- **[DH-2.x]** The Data Handler must support **distributed/scalable pipelines** for large-scale backtests, including parallelized or serverless execution.

### Backtester
- **[BT-7.x]** The Backtester must support **distributed/parallel execution**, enabling large-scale parameter sweeps and portfolio simulations.
- **[BT-7.x]** The Backtester must provide **scenario stress testing**, allowing simulation of market shocks (e.g., volatility spikes, liquidity droughts).

### Portfolio Manager
- **[PM-5.x]** The Portfolio Manager must support **dynamic allocation policies** based on regime signals provided by the RMM.
- **[PM-5.x]** The Portfolio Manager must support **portfolio optimization methods**, including risk parity, Kelly criterion, and volatility targeting.

### Strategy Engine
- **[SE-3.x]** The Strategy Engine must support **natural language–driven strategy definition**, allowing AI-assisted generation of strategies beyond YAML.
- **[SE-3.x]** The Strategy Engine must support **automated feature selection**, where AI recommends or removes indicators/features during testing.

### Reporting & Visualization
- **[RV-9.x]** The Reporting module must support **interactive visual analytics**, including trade clustering, dynamic filtering, and zoomable regime overlays.
- **[RV-9.x]** The Reporting module must support **Monte Carlo equity overlays**, displaying robustness bands on equity curves.

### JSON Brief Schema
- **[JSON-11.x]** The JSON Brief must include **explainability fields**, such as feature importances and attribution scores linked to AI insights.
- **[JSON-11.x]** The JSON Brief must include **portfolio allocation rationale** whenever regime-based or optimization-driven allocation is applied.

### System / DevOps
- **[SYS-1.x]** The system must support **cloud-scale CI/CD execution**, enabling distributed parameter sweeps and backtests in CI pipelines.
- **[SYS-1.x]** The system must include explicit **AI interpretability/traceability requirements**, ensuring all AI-driven outputs are reproducible and auditable.

---

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
- [12) Non-Functional Requirements](#12-non-functional-requirements)
- [13) Detailed Notes & Edge Requirements](#13-detailed-notes--edge-requirements)
- [14) Development Process & Governance](#14-development-process--governance)
- [15) Open TODOs](#15-open-todos)
- [16) Traceability](#16-traceability)
- [17) Pending updates (awaiting approval)](#17-pending-updates-awaiting-approval)

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
- **Architecture**
  - Modular separation is paramount. The core components (SE, REM, PM, RMM) must be decoupled.
  - A **Run Configuration** binds these components together for a specific backtest or live trading session. It specifies the instrument, the strategy to use, the risk model to apply, the data source, etc.
- **Inter-Module Communication & Boundaries**
  - To facilitate a future split into multiple repositories, modules must communicate only through well-defined public APIs (e.g., functions and classes exposed in `__init__.py` files).
  - Direct imports of internal sub-modules (e.g., `from trading_platform.data.internal_helpers import ...`) are strictly forbidden.
  - **No circular dependencies** between top-level modules (e.g., `data`, `strategy`, `backtester`) will be permitted. This will be enforced via static analysis tools in the CI pipeline.
  - A `trading_platform.core` module will house shared data structures (e.g., canonical models for `Bar`, `Trade`) and utilities that all other modules can depend on.
- **Instrument Agnostic Architecture**
  - The core engine (Portfolio Manager) must operate on a canonical representation of trades, positions, and performance.
  - An **Instrument Definition** (part of the Data Handler) provides rich metadata for each symbol required for runtime translation (e.g., `point_value`, `tick_size`).
  - User-facing components (e.g., Risk & Exit Manager configuration) may allow inputs in native terms (pips, points), but these **must be translated** into the canonical model by the Backtester or Execution Layer at runtime before being passed to the Portfolio Manager.
  - All core PnL calculations must be performed in a consistent base currency.
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
  - A centralized trading window policy in the core module (TradingWindowPolicy) will enforce blackout rules. Both BT and EL must consult this policy before opening new positions.
  - The platform will support an event/news calendar to populate event-based blackout windows (for example high-impact economic releases), configurable per strategy or run.
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
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**, indicating that the original conditions for the trade are no longer valid.
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.4.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.4.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.4.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.5]** **Declarative Strategies (Low-Code/No-Code)**
  - **[SE-3.5.1]** The system must support defining strategies using a declarative **YAML format**, distinct from Gherkin BDD files.
  - **Strategy Schema**: The YAML files will follow a defined schema representing rules, conditions, and indicators.
  - **Parameterization**: YAML's key-value structure naturally supports parameterization. Parameter sweeps will be orchestrated by the AI Lab, which can easily read, modify, and generate these YAML files.
  - **Execution**: The Strategy Engine will include a parser that loads a strategy definition from a YAML file and executes its logic.
  - **Testing**: The behavior of the YAML strategy parser and execution engine will be tested rigorously using Behavior-Driven Development (BDD) with Gherkin (`.feature` files). This ensures the implementation correctly interprets the strategy definitions.
- **[SE-3.6]** Use indicators from established libraries (e.g., `ta`) where possible to avoid duplication.
- **[SE-3.7]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.8]** The engine must support parameter sweeps orchestrated by the AI Lab.
- **[SE-3.9]** YAML Schema Validation
   - Strategy definitions written in YAML must be validated against the
     JSON Schema in `docs/schemas/strategy.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

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
 - **[RMM-4.9] YAML Schema Validation**
   - RMM configurations written in YAML must be validated against the JSON
     Schema in `docs/schemas/rmm.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

---

## 5) Portfolio Manager (PM)
- **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **[PM-5.1]** The PM works exclusively in **canonical terms**. It does not know about native concepts like "pips".
- **State Management**:
  - **[PM-5.2]** Track cash balance, open positions, and total equity (mark-to-market).
  - **[PM-5.3]** Maintain a log of all executed trades.
- **Order Processing**:
  - **[PM-5.4]** `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - **[PM-5.5]** `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **Position Sizing**: Implement sizing logic, including:
  - **[PM-5.6]** Fixed-risk (e.g., risk $100 per trade).
  - **[PM-5.7]** Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **Trade & PnL Logic**:
  - **[PM-5.8]** Generate a canonical `Trade` record upon position closure.
  - **[PM-5.9]** Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - **[PM-5.10]** Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **Portfolio-Level Risk Management**:
  - **[PM-5.11]** Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.

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
- **[BT-7.10] Counterfactual Skipped Trades (Filters/Policies)**
   - The backtester must record attempted entries that were skipped due to a filter/policy (e.g., blackout window, regime filter, risk cap, user-defined filter).
   - Each skipped item must include: `timestamp`, `symbol`, `reason_code` (e.g., `blackout_static`, `blackout_event`, `regime_filter`, `risk_cap`, `custom`), `policy_snapshot` (minimal), and optional `notes`.
- **[BT-7.11] Counterfactual Outcome Simulation**
   - For each skipped entry, the backtester must simulate a counterfactual trade using the same fill and exit policies configured for the run (entry price convention, stop/tp rules, tie-breaks, costs).
   - The counterfactual must produce canonical outcomes: `cf_exit_time`, `cf_exit_price`, `cf_pnl_currency`, and, when available, `cf_mfe_currency`, `cf_mae_currency`, `cf_bars_held`.
   - Counterfactuals must be clearly flagged as hypothetical and must never affect the main equity/trades results.
- **[BT-7.12] Filter Impact Summary**
   - The backtester must aggregate per-reason summaries (e.g., counts, total/mean/median `cf_pnl_currency`) to quantify the impact of each filter.
   - Summaries must be included in the run brief for downstream analysis and A/B comparisons of filter configurations.
- **[BT-7.13] Live Trading Deviation**
   - The Execution Layer (EL) must not simulate counterfactual outcomes; it may log skipped entries and reasons only. Counterfactual simulation is strictly a backtest-only feature.

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

---

## 11) JSON Brief Schema (Instrument-Agnostic)
- **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **overall_performance** (base currency): `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **risk_snapshot** (base currency): `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **equity_stats**: `{equity_curve: [[timestamp, equity], ...], max_drawdown, dd_duration_bars}`.
- **distribution**: `{pnl_mean, pnl_median, pnl_std, p05, p95}` (base currency; placeholders acceptable initially).
- **streaks**: `{longest_win_streak, longest_loss_streak, current_streak}`.
- **holding_time**: `{median_secs}` and optional buckets.
- **activity**: `{trades_per_day}` (optional baseline).
- **timing_buckets**: `{by_hour, by_dow, by_month}` (optional baseline).
- **costs**: `{total_costs, avg_cost_per_trade, breakdown:{spread, commission, fees, slippage}}`.
  - See `docs/examples/brief_costs_section.md` for schema details and examples.
- **exposure**: `{average_gross_exposure, peak_gross_exposure}` (optional baseline).
- **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **regimes**: per-regime performance breakdown.
- **stop_tp_candidates**: configs derived from MFE/MAE (in base currency; instrument-specific conversions occur via Instrument Definition at presentation/export time).
- **monte_carlo**: resampling stats.
- **walk_forward**: rolling OOS stats with instability flags.
- **parameter_search**: top params, robustness notes.
- **stationarity**: ADF, KPSS, drift tests.
- **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
- **data_quality**: loader flags, missing/duplicate bar counts, outlier flags.
- **instrument_definitions**: snapshot per symbol `{tick_size, point_value, base_ccy, quote_ccy, lot_size, min_trade_unit}`.
- **cost_model**: `{spread_model, commission_model, slippage_model, rollover_model, fee_params}`.
- **fill_policy**: `{policy}` and details; **tie_break_policy**: `{policy}`.
 - **blackout_policy**: snapshot of blackout configuration `{blackout_utc, blackout_events}`.
- **environment**: `{python_version, dependency_versions, platform, timezone}`.
- **provenance**: `{app_version, git_commit, run_seed, data_start, data_end, symbols}`.
- **checksums**: `{config_snapshot_hash, instrument_defs_hash}`.
- **trades**: enhanced entries with `{r_multiple, mfe_currency, mae_currency, bars_held, holding_time_sec, features_at_entry, regime_label_at_entry, exit_reason, cost_breakdown}`.
  - For any trade closed by an REM rule, the brief must record the original **native rule** that triggered the exit (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`).
  - See `docs/examples/trades_cost_breakdown.md` for `cost_breakdown` semantics and how it rolls up to `costs`.
  - New: context snapshots at entry/exit (see [RV-8.9]).
 - **skipped_trades**: list of counterfactuals for filtered entries `[{timestamp, symbol, reason_code, policy_snapshot, cf_exit_time, cf_exit_price, cf_pnl_currency, cf_mfe_currency, cf_mae_currency, cf_bars_held}]`.
 - **filter_impact**: per-reason aggregates `{reason_code: {n_skipped, total_cf_pnl, mean_cf_pnl, median_cf_pnl}}`.
- Pure JSON types only (convert pandas objects).

Notes:
- The brief is canonical and instrument-agnostic. Any UI/export layer may render instrument-native units (e.g., pips, ticks) by translating the canonical brief via the Instrument Definition (e.g., `tick_size`, `point_value`).

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

- Cost Model Canonical Shape (applies to BT & EL)
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

## 9) Reporting & Visualization (RV) — Additions
- **[RV-9.9] Field Definitions Section**
  - The brief must include a top-level `field_definitions` section describing each field that appears anywhere in the brief. Each definition includes:
    - `description`: what the field means,
    - `why_useful`: why it matters for analysis/decision-making,
    - `how_to_use`: guidance for downstream tools and humans.
  - This section is auto-generated from a central registry to ensure consistency and versioned with the app.
- **[RV-9.10] Trade Context Snapshots**
  - For each trade, include context at both entry and exit:
    - `context_at_entry`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
    - `context_at_exit`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
  - These snapshots capture the values of indicators/features actually used by the strategy at decision time.
  - Downstream usage: performance slicing by regime/indicator ranges; explanation overlays in reports.

---

## 5) Portfolio Manager (PM) — Additions
- **[PM-5.11] Directional Position Caps**
  - Configurable limit on simultaneously open positions per direction (long/short) with a default of 1.
  - Enforced identically in BT and EL. Configuration example:
    ```yaml
    pm_limits:
      max_open_long: 1
      max_open_short: 1
    ```
  - When limits would be exceeded, the attempted entry must be skipped.

---

## 7) Backtester (BT) — Additions
- Extend skipped-trade logging requirements:
  - Add `position_cap` to the allowed `reason_code` set in [BT-7.10].
  - Ensure these skips are included in `skipped_trades` and summarized in `filter_impact` ([BT-7.12]).


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

> Proposed requirement changes identified during gap analysis (Sept 2025). Once approved, these will be merged into their respective module sections.

### AI Lab
- **[AI-10.x]** The AI Lab must support **automated hypothesis generation**, producing candidate entry/exit rules or strategy variants based on JSON briefs.
- **[AI-10.x]** The AI Lab must provide **explainability outputs** (e.g., feature attribution, importance scores) to justify AI recommendations.

### Regime Market Manager (RMM)
- **[RMM-4.x]** The RMM must support **regime-adaptive portfolio allocation**, dynamically adjusting capital weighting by regime classification.
- **[RMM-4.x]** The RMM must incorporate **event-aware overlays**, integrating economic/news event features into its classification logic.

### Data Handler
- **[DH-2.x]** The Data Handler must enable **sentiment/NLP features** from event metadata for direct use by the Strategy Engine, RMM, and AI Lab.
- **[DH-2.x]** The Data Handler must support **distributed/scalable pipelines** for large-scale backtests, including parallelized or serverless execution.

### Backtester
- **[BT-7.x]** The Backtester must support **distributed/parallel execution**, enabling large-scale parameter sweeps and portfolio simulations.
- **[BT-7.x]** The Backtester must provide **scenario stress testing**, allowing simulation of market shocks (e.g., volatility spikes, liquidity droughts).

### Portfolio Manager
- **[PM-5.x]** The Portfolio Manager must support **dynamic allocation policies** based on regime signals provided by the RMM.
- **[PM-5.x]** The Portfolio Manager must support **portfolio optimization methods**, including risk parity, Kelly criterion, and volatility targeting.

### Strategy Engine
- **[SE-3.x]** The Strategy Engine must support **natural language–driven strategy definition**, allowing AI-assisted generation of strategies beyond YAML.
- **[SE-3.x]** The Strategy Engine must support **automated feature selection**, where AI recommends or removes indicators/features during testing.

### Reporting & Visualization
- **[RV-9.x]** The Reporting module must support **interactive visual analytics**, including trade clustering, dynamic filtering, and zoomable regime overlays.
- **[RV-9.x]** The Reporting module must support **Monte Carlo equity overlays**, displaying robustness bands on equity curves.

### JSON Brief Schema
- **[JSON-11.x]** The JSON Brief must include **explainability fields**, such as feature importances and attribution scores linked to AI insights.
- **[JSON-11.x]** The JSON Brief must include **portfolio allocation rationale** whenever regime-based or optimization-driven allocation is applied.

### System / DevOps
- **[SYS-1.x]** The system must support **cloud-scale CI/CD execution**, enabling distributed parameter sweeps and backtests in CI pipelines.
- **[SYS-1.x]** The system must include explicit **AI interpretability/traceability requirements**, ensuring all AI-driven outputs are reproducible and auditable.

---

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
- [12) Non-Functional Requirements](#12-non-functional-requirements)
- [13) Detailed Notes & Edge Requirements](#13-detailed-notes--edge-requirements)
- [14) Development Process & Governance](#14-development-process--governance)
- [15) Open TODOs](#15-open-todos)
- [16) Traceability](#16-traceability)
- [17) Pending updates (awaiting approval)](#17-pending-updates-awaiting-approval)

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
- **Architecture**
  - Modular separation is paramount. The core components (SE, REM, PM, RMM) must be decoupled.
  - A **Run Configuration** binds these components together for a specific backtest or live trading session. It specifies the instrument, the strategy to use, the risk model to apply, the data source, etc.
- **Inter-Module Communication & Boundaries**
  - To facilitate a future split into multiple repositories, modules must communicate only through well-defined public APIs (e.g., functions and classes exposed in `__init__.py` files).
  - Direct imports of internal sub-modules (e.g., `from trading_platform.data.internal_helpers import ...`) are strictly forbidden.
  - **No circular dependencies** between top-level modules (e.g., `data`, `strategy`, `backtester`) will be permitted. This will be enforced via static analysis tools in the CI pipeline.
  - A `trading_platform.core` module will house shared data structures (e.g., canonical models for `Bar`, `Trade`) and utilities that all other modules can depend on.
- **Instrument Agnostic Architecture**
  - The core engine (Portfolio Manager) must operate on a canonical representation of trades, positions, and performance.
  - An **Instrument Definition** (part of the Data Handler) provides rich metadata for each symbol required for runtime translation (e.g., `point_value`, `tick_size`).
  - User-facing components (e.g., Risk & Exit Manager configuration) may allow inputs in native terms (pips, points), but these **must be translated** into the canonical model by the Backtester or Execution Layer at runtime before being passed to the Portfolio Manager.
  - All core PnL calculations must be performed in a consistent base currency.
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
  - A centralized trading window policy in the core module (TradingWindowPolicy) will enforce blackout rules. Both BT and EL must consult this policy before opening new positions.
  - The platform will support an event/news calendar to populate event-based blackout windows (for example high-impact economic releases), configurable per strategy or run.
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
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**, indicating that the original conditions for the trade are no longer valid.
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.4.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.4.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.4.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.5]** **Declarative Strategies (Low-Code/No-Code)**
  - **[SE-3.5.1]** The system must support defining strategies using a declarative **YAML format**, distinct from Gherkin BDD files.
  - **Strategy Schema**: The YAML files will follow a defined schema representing rules, conditions, and indicators.
  - **Parameterization**: YAML's key-value structure naturally supports parameterization. Parameter sweeps will be orchestrated by the AI Lab, which can easily read, modify, and generate these YAML files.
  - **Execution**: The Strategy Engine will include a parser that loads a strategy definition from a YAML file and executes its logic.
  - **Testing**: The behavior of the YAML strategy parser and execution engine will be tested rigorously using Behavior-Driven Development (BDD) with Gherkin (`.feature` files). This ensures the implementation correctly interprets the strategy definitions.
- **[SE-3.6]** Use indicators from established libraries (e.g., `ta`) where possible to avoid duplication.
- **[SE-3.7]** Strategy metadata must declare required overlays for automatic plotting in the RV module.
- **[SE-3.8]** The engine must support parameter sweeps orchestrated by the AI Lab.
- **[SE-3.9]** YAML Schema Validation
   - Strategy definitions written in YAML must be validated against the
     JSON Schema in `docs/schemas/strategy.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

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
 - **[RMM-4.9] YAML Schema Validation**
   - RMM configurations written in YAML must be validated against the JSON
     Schema in `docs/schemas/rmm.schema.json` at load time.
   - Validation errors must fail fast with actionable messages (field name,
     expected type/enum, location path).
   - Unit tests must include at least one valid and one invalid YAML sample
     to verify the validator catches schema violations.

---

## 5) Portfolio Manager (PM)
- **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **[PM-5.1]** The PM works exclusively in **canonical terms**. It does not know about native concepts like "pips".
- **State Management**:
  - **[PM-5.2]** Track cash balance, open positions, and total equity (mark-to-market).
  - **[PM-5.3]** Maintain a log of all executed trades.
- **Order Processing**:
  - **[PM-5.4]** `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - **[PM-5.5]** `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **Position Sizing**: Implement sizing logic, including:
  - **[PM-5.6]** Fixed-risk (e.g., risk $100 per trade).
  - **[PM-5.7]** Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **Trade & PnL Logic**:
  - **[PM-5.8]** Generate a canonical `Trade` record upon position closure.
  - **[PM-5.9]** Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - **[PM-5.10]** Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **Portfolio-Level Risk Management**:
  - **[PM-5.11]** Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.

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
- **[BT-7.10] Counterfactual Skipped Trades (Filters/Policies)**
   - The backtester must record attempted entries that were skipped due to a filter/policy (e.g., blackout window, regime filter, risk cap, user-defined filter).
   - Each skipped item must include: `timestamp`, `symbol`, `reason_code` (e.g., `blackout_static`, `blackout_event`, `regime_filter`, `risk_cap`, `custom`), `policy_snapshot` (minimal), and optional `notes`.
- **[BT-7.11] Counterfactual Outcome Simulation**
   - For each skipped entry, the backtester must simulate a counterfactual trade using the same fill and exit policies configured for the run (entry price convention, stop/tp rules, tie-breaks, costs).
   - The counterfactual must produce canonical outcomes: `cf_exit_time`, `cf_exit_price`, `cf_pnl_currency`, and, when available, `cf_mfe_currency`, `cf_mae_currency`, `cf_bars_held`.
   - Counterfactuals must be clearly flagged as hypothetical and must never affect the main equity/trades results.
- **[BT-7.12] Filter Impact Summary**
   - The backtester must aggregate per-reason summaries (e.g., counts, total/mean/median `cf_pnl_currency`) to quantify the impact of each filter.
   - Summaries must be included in the run brief for downstream analysis and A/B comparisons of filter configurations.
- **[BT-7.13] Live Trading Deviation**
   - The Execution Layer (EL) must not simulate counterfactual outcomes; it may log skipped entries and reasons only. Counterfactual simulation is strictly a backtest-only feature.

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

---

## 11) JSON Brief Schema (Instrument-Agnostic)
- **meta**: `{strategy_name, timeframe, universe, version, run_id, timestamp}`.
- **params**: `{fast, slow, stop_type, stop_value, tp_type, tp_value, trail_type, trail_value, atr_length, tie_break}`.
- **overall_performance** (base currency): `{n_trades, total_pnl, mean_pnl, median_pnl, by_side_total_pnl, win_rate, initial_equity, final_equity}`.
- **risk_snapshot** (base currency): `{win_rate, avg_win, avg_loss, max_win, max_loss}`.
- **equity_stats**: `{equity_curve: [[timestamp, equity], ...], max_drawdown, dd_duration_bars}`.
- **distribution**: `{pnl_mean, pnl_median, pnl_std, p05, p95}` (base currency; placeholders acceptable initially).
- **streaks**: `{longest_win_streak, longest_loss_streak, current_streak}`.
- **holding_time**: `{median_secs}` and optional buckets.
- **activity**: `{trades_per_day}` (optional baseline).
- **timing_buckets**: `{by_hour, by_dow, by_month}` (optional baseline).
- **costs**: `{total_costs, avg_cost_per_trade, breakdown:{spread, commission, fees, slippage}}`.
  - See `docs/examples/brief_costs_section.md` for schema details and examples.
- **exposure**: `{average_gross_exposure, peak_gross_exposure}` (optional baseline).
- **contrasts**: feature-at-entry bins (RSI, ADX, ATR, BB width, etc.).
- **regimes**: per-regime performance breakdown.
- **stop_tp_candidates**: configs derived from MFE/MAE (in base currency; instrument-specific conversions occur via Instrument Definition at presentation/export time).
- **monte_carlo**: resampling stats.
- **walk_forward**: rolling OOS stats with instability flags.
- **parameter_search**: top params, robustness notes.
- **stationarity**: ADF, KPSS, drift tests.
- **feature_analysis**: `{correlation_matrix, feature_importance_scores}`.
- **data_quality**: loader flags, missing/duplicate bar counts, outlier flags.
- **instrument_definitions**: snapshot per symbol `{tick_size, point_value, base_ccy, quote_ccy, lot_size, min_trade_unit}`.
- **cost_model**: `{spread_model, commission_model, slippage_model, rollover_model, fee_params}`.
- **fill_policy**: `{policy}` and details; **tie_break_policy**: `{policy}`.
 - **blackout_policy**: snapshot of blackout configuration `{blackout_utc, blackout_events}`.
- **environment**: `{python_version, dependency_versions, platform, timezone}`.
- **provenance**: `{app_version, git_commit, run_seed, data_start, data_end, symbols}`.
- **checksums**: `{config_snapshot_hash, instrument_defs_hash}`.
- **trades**: enhanced entries with `{r_multiple, mfe_currency, mae_currency, bars_held, holding_time_sec, features_at_entry, regime_label_at_entry, exit_reason, cost_breakdown}`.
  - For any trade closed by an REM rule, the brief must record the original **native rule** that triggered the exit (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`).
  - See `docs/examples/trades_cost_breakdown.md` for `cost_breakdown` semantics and how it rolls up to `costs`.
  - New: context snapshots at entry/exit (see [RV-8.9]).
 - **skipped_trades**: list of counterfactuals for filtered entries `[{timestamp, symbol, reason_code, policy_snapshot, cf_exit_time, cf_exit_price, cf_pnl_currency, cf_mfe_currency, cf_mae_currency, cf_bars_held}]`.
 - **filter_impact**: per-reason aggregates `{reason_code: {n_skipped, total_cf_pnl, mean_cf_pnl, median_cf_pnl}}`.
- Pure JSON types only (convert pandas objects).

Notes:
- The brief is canonical and instrument-agnostic. Any UI/export layer may render instrument-native units (e.g., pips, ticks) by translating the canonical brief via the Instrument Definition (e.g., `tick_size`, `point_value`).

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

- Cost Model Canonical Shape (applies to BT & EL)
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

## 9) Reporting & Visualization (RV) — Additions
- **[RV-9.9] Field Definitions Section**
  - The brief must include a top-level `field_definitions` section describing each field that appears anywhere in the brief. Each definition includes:
    - `description`: what the field means,
    - `why_useful`: why it matters for analysis/decision-making,
    - `how_to_use`: guidance for downstream tools and humans.
  - This section is auto-generated from a central registry to ensure consistency and versioned with the app.
- **[RV-9.10] Trade Context Snapshots**
  - For each trade, include context at both entry and exit:
    - `context_at_entry`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
    - `context_at_exit`: `{regime: {label, confidence}, indicators: {<name>: <value>, ...}, notes}`
  - These snapshots capture the values of indicators/features actually used by the strategy at decision time.
  - Downstream usage: performance slicing by regime/indicator ranges; explanation overlays in reports.

---

## 5) Portfolio Manager (PM) — Additions
- **[PM-5.11] Directional Position Caps**
  - Configurable limit on simultaneously open positions per direction (long/short) with a default of 1.
  - Enforced identically in BT and EL. Configuration example:
    ```yaml
    pm_limits:
      max_open_long: 1
      max_open_short: 1
    ```
  - When limits would be exceeded, the attempted entry must be skipped.

---

## 7) Backtester (BT) — Additions
- Extend skipped-trade logging requirements:
  - Add `position_cap` to the allowed `reason_code` set in [BT-7.10].
  - Ensure these skips are included in `skipped_trades` and summarized in `filter_impact` ([BT-7.12]).


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

> Proposed requirement changes identified during gap analysis (Sept 2025). Once approved, these will be merged into their respective module sections.

### AI Lab
- **[AI-10.x]** The AI Lab must support **automated hypothesis generation**, producing candidate entry/exit rules or strategy variants based on JSON briefs.
- **[AI-10.x]** The AI Lab must provide **explainability outputs** (e.g., feature attribution, importance scores) to justify AI recommendations.

### Regime Market Manager (RMM)
- **[RMM-4.x]** The RMM must support **regime-adaptive portfolio allocation**, dynamically adjusting capital weighting by regime classification.
- **[RMM-4.x]** The RMM must incorporate **event-aware overlays**, integrating economic/news event features into its classification logic.

### Data Handler
- **[DH-2.x]** The Data Handler must enable **sentiment/NLP features** from event metadata for direct use by the Strategy Engine, RMM, and AI Lab.
- **[DH-2.x]** The Data Handler must support **distributed/scalable pipelines** for large-scale backtests, including parallelized or serverless execution.

### Backtester
- **[BT-7.x]** The Backtester must support **distributed/parallel execution**, enabling large-scale parameter sweeps and portfolio simulations.
- **[BT-7.x]** The Backtester must provide **scenario stress testing**, allowing simulation of market shocks (e.g., volatility spikes, liquidity droughts).

### Portfolio Manager
- **[PM-5.x]** The Portfolio Manager must support **dynamic allocation policies** based on regime signals provided by the RMM.
- **[PM-5.x]** The Portfolio Manager must support **portfolio optimization methods**, including risk parity, Kelly criterion, and volatility targeting.

### Strategy Engine
- **[SE-3.x]** The Strategy Engine must support **natural language–driven strategy definition**, allowing AI-assisted generation of strategies beyond YAML.
- **[SE-3.x]** The Strategy Engine must support **automated feature selection**, where AI recommends or removes indicators/features during testing.

### Reporting & Visualization
- **[RV-9.x]** The Reporting module must support **interactive visual analytics**, including trade clustering, dynamic filtering, and zoomable regime overlays.
- **[RV-9.x]** The Reporting module must support **Monte Carlo equity overlays**, displaying robustness bands on equity curves.

### JSON Brief Schema
- **[JSON-11.x]** The JSON Brief must include **explainability fields**, such as feature importances and attribution scores linked to AI insights.
- **[JSON-11.x]** The JSON Brief must include **portfolio allocation rationale** whenever regime-based or optimization-driven allocation is applied.

### System / DevOps
- **[SYS-1.x]** The system must support **cloud-scale CI/CD execution**, enabling distributed parameter sweeps and backtests in CI pipelines.
- **[SYS-1.x]** The system must include explicit **AI interpretability/traceability requirements**, ensuring all AI-driven outputs are reproducible and auditable.

---

This document is the **comprehensive requirements index** for the Trading Engine project — all details captured, no matter how granular.
