# project_requirements

_Last updated: 2025-09-09_

> **Purpose**: Single source of truth for the Trading Engine project. This file captures **all requirements, at every level of detail** — functional, non-functional, system-wide, module-specific, and even small design details. It serves as the **authoritative requirements index** that goes beyond a master spec.

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
  - `sessions`: A definition of the primary trading session (e.g., start/end times and timezone) used for correct daily resampling.
  - `holidays`: A calendar of non-trading days.
- Chunked loading for large ranges; memory cap awareness.
- Cache datasets persistently (parquet/feather) keyed by params.
- Feature pipelines for computed cols (ATR, ADX, RSI, BB width, etc.).
- **Unstructured & Event Data (News/Reports)**
  - The system must support the ingestion, storage, and retrieval of time-series event data, such as historical news articles and economic reports, for use in AI-driven analysis.
  - **Canonical Event Schema**: All event data must be normalized into a canonical format: `{event_id, timestamp, source, type, headline, summary, content, metadata}`.
    - `type`: e.g., 'news', 'economic_report', 'central_bank_speech'.
    - `metadata`: A flexible field for pre-computed sentiment scores, named entities, relevance, etc.
  - **Storage & Retrieval**: Events must be stored efficiently to allow for fast time-range queries.
  - **Alignment**: The Data Handler must provide an interface to retrieve all events that occurred within the timeframe of a given bar or a set of bars. This enables direct alignment with market data for backtesting and analysis, and must work for any bar timeframe (e.g., M1, H1, D1), including those generated through resampling.
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
  - Strategy names should use common industry abbreviations (e.g., SMA, EMA, BB) for clarity and brevity.
  - SMA crossover (fast/slow).
  - PSAR with ADX filter (avoid whipsaws in ranges).
  - BB (Bollinger Bands) Mean Reversion.
- **Declarative Strategies (Low-Code/No-Code)**
  - The system must support defining strategies using a declarative **YAML format**. This provides a clean, machine-readable, and low-code method for strategy creation that is distinct from the Gherkin used for BDD testing.
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

## 5) Portfolio Manager (PM)
- **Core Responsibility**: To be the single source of truth for the portfolio's state at any given time. This component must be used identically by both the Backtester and the Execution Layer.
- **State Management**:
  - Track cash balance, open positions, and total equity (mark-to-market).
  - Maintain a log of all executed trades.
- **Order Processing**:
  - `on_signal(signal)`: A method to process an incoming signal and generate the appropriate order (e.g., market, stop, limit).
  - `update_positions(bar)`: A method to update the value of open positions based on the latest market data.
- **Position Sizing**: Implement sizing logic, including:
  - Fixed-risk (e.g., risk $100 per trade).
  - Fixed-fraction (e.g., risk 1% of portfolio equity per trade).
- **Trade & PnL Logic**:
  - Generate a canonical `Trade` record upon position closure.
  - Trades table schema: `entry_time, exit_time, side, entry_price, exit_price, pnl_currency, mfe_currency, mae_currency, r_multiple, notes`.
  - Calculate equity curve, drawdowns, hit rate, and other key performance metrics.
- **Portfolio-Level Risk Management**:
  - Enforce rules like daily loss caps, maximum drawdown limits, and other circuit breakers.

---

## 6) Backtester (BT)
- **Core Responsibility**: To simulate the passage of time and orchestrate the interaction between the Data Handler, Strategy Engine, and Portfolio Manager.
- **Event-Driven Loop**: The primary mechanism will be an event-driven loop that iterates bar-by-bar through historical data.
- Orders: market, stop, limit; ATR-based stops/TP; trailing stops; tie-breaks.
- Models: slippage, rollover, and a canonical cost model driven by the instrument definition (commission, fees, spread).
- Monte Carlo resampling for trades/equity.
- Warm-up window for indicators.
- Testing: deterministic fills; stop/TP precedence validation.

---

## 7) Execution Layer (EL)
- Broker adapter: OANDA (initial).
- Map internal → broker API; handle retries, backoff, rate-limits.
- **Portfolio Interaction**: The EL manages live trading by processing signals and submitting orders to the same `PortfolioManager` component used by the backtester, ensuring logical parity.
- Must handle live streams of both market data and event data, forwarding them to the active strategy for signal generation.
- Structured logging; reconciliation of positions.
- Risk: daily caps, circuit breakers.

---

## 8) Reporting & Visualization (RV)
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

## 9) AI Lab (AI)
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
    - This is driven by a sweep configuration file that points to a strategy template and defines the parameter values/ranges to test.
  - Perform walk-forward evaluation (WFE) to test strategy robustness on out-of-sample data, using the same templating mechanism.
  - Conduct regime analysis to show how the strategy performs in different market conditions (trending, ranging, etc.).
  - **Workflow Integration**: The standard validation workflow will be a two-stage process: 1) Use parameter sweeps to discover optimal parameter sets. 2) Use Monte Carlo analysis on the best-performing set to validate its robustness.
- **Outputs**: All findings must be available as both machine-readable JSON and human-readable summaries.

---

## 10) JSON Brief Schema
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
