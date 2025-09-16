# project_requirements

_Last updated: 2025-09-12_

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
  - The core engine (Backtester, Portfolio Manager) must operate on a canonical representation of trades, positions, and performance.
  - An **Instrument Definition** module (part of the Data Handler) will provide rich metadata for each symbol required for the runtime translation of native terms (e.g., `point_value`, `tick_size`, `pip_value`).
  - User-facing components or configuration files may allow inputs in native terms (pips, points), but these must be translated into the canonical model by the Backtester or Execution Layer at runtime.

---

## 3) Strategy Engine (SE)
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, `flat`).
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the responsibility of the Risk & Exit Manager (REM).
- **[SE-3.4]** Provide built-in, performance-critical strategies implemented in Python, including:
  - **[SE-3.4.1]** SMA (Simple Moving Average) Crossover.
  - **[SE-3.4.2]** PSAR (Parabolic SAR) with an ADX filter.
  - **[SE-3.4.3]** BB (Bollinger Bands) Mean Reversion.
- **[SE-3.5]** Strategies will be defined in a declarative YAML format, validated against a JSON schema.

---

## 5) Portfolio Manager (PM)
- **[PM-5.1]** **Core Mandate**: Act as the state machine for the portfolio, tracking cash, positions, and equity.
- **[PM-5.2]** The PM works exclusively in **canonical terms**. It does not know about native concepts like "pips".
- **[PM-5.3]** It processes orders to open and close positions and logs all executed trades.
- **[PM-5.4]** Enforce portfolio-level risk rules like daily loss caps and maximum drawdown limits.

---

## 6) Risk & Exit Manager (REM)
- **[REM-6.1]** **Core Mandate**: Define the rules for managing an open position.
- **[REM-6.2]** REM configurations will be defined in a declarative YAML format, validated against a JSON schema.
- **[REM-6.3]** The REM defines exit conditions such as `stop_loss` and `take_profit`.
- **[REM-6.4]** These rules can be defined in **native terms** (e.g., `{ value: 50, type: pips }`) or universal terms (e.g., `{ value: 2.5, type: percent }` or `{ value: 2, type: atr }`).

---

## 7) Backtester (BT)
- **[BT-7.1]** **Core Mandate**: Orchestrate all components for a historical simulation.
- **[BT-7.2]** At runtime, the BT loads the `Instrument`, `Strategy`, and `Risk & Exit Model` specified in the Run Configuration.
- **[BT-7.3]** **Runtime Translation**: The BT is responsible for translating native rules from the REM into canonical price levels. For example, it will use the Instrument's metadata to convert a "50 pip" stop-loss into a specific price offset.
- **[BT-7.4]** The BT feeds market data to the SE to get signals, and uses the translated REM rules to manage open positions via the PM.
- **[BT-7.5]** The primary mechanism will be an event-driven or vectorized loop that iterates through historical data.
- **[BT-7.6]** A configurable cost model to simulate slippage, rollover, commissions, fees, and spreads, driven by the instrument definition.
- **[BT-7.7]** A "warm-up" period to ensure indicators are stable before trading signals are processed.
- **[BT-7.8]** Backtests must be deterministic.
- **[BT-7.9]** All backtesting logic must be validated, especially for fill logic and stop/TP precedence.
- **[BT-7.10] Counterfactual Skipped Trades (Filters/Policies)**
   - The backtester must record attempted entries that were skipped due to a filter/policy (e.g., blackout window, regime filter, risk cap).
   - Each skipped item must include: `timestamp`, `symbol`, `reason_code`, and a `policy_snapshot`.
- **[BT-7.11] Counterfactual Outcome Simulation**
   - For each skipped entry, the backtester must simulate a hypothetical trade using the run's configured policies.
   - The counterfactual must produce canonical outcomes: `cf_pnl_currency`, `cf_mfe_currency`, `cf_mae_currency`, etc.
- **[BT-7.12] Filter Impact Summary**
   - The backtester must aggregate per-reason summaries to quantify the impact of each filter and include them in the run brief.

---

## 8) Execution Layer (EL)
- **[EL-8.1]** **Core Mandate**: Orchestrate all components for a live trading session.
- **[EL-8.2]** Like the Backtester, the EL is responsible for loading all components and performing the same **runtime translation** of native risk rules into canonical orders to be sent to the broker.
- **[EL-8.3]** The adapter must map the internal canonical order format to the broker's specific API format.
- **[EL-8.4]** The EL must use the same `PortfolioManager` component as the backtester to ensure logical parity.

---

## 11) JSON Brief Schema
- **[BRIEF-11.1]** The `trades` object within the brief must be enhanced.
- **[BRIEF-11.2]** For any trade closed by an REM rule, the brief must record the original **native rule** that triggered the exit (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`). This ensures full traceability.
