# Requirements Compliance Check Findings (2025-09-16)

This document details discrepancies between the implemented code in `src/trading_platform/` and the core requirements defined in `docs/project_requirements.md`.

The focus is on implemented functionality that conflicts with the requirements. Items marked as "Future Enhancements" in the requirements document are not considered here.

---

## 1. Critical Discrepancy: Violation of Architectural Separation

### Discrepancy
The most critical architectural principle is the separation of the Strategy Engine (SE) from the Risk & Exit Manager (REM). The SE should only generate signals, and the REM should be the sole source of truth for stop-loss and take-profit logic.

The current implementation violates this principle. The backtester (`run_backtest`) directly processes risk management rules (stop-loss/take-profit) that are loaded as part of the `CompiledStrategy` object. The concept of a pluggable, separate REM component is not used; its responsibilities have been incorrectly absorbed by the backtester and the strategy definition.

### Requirement Conflict
- **`[SE-3.3]`**: "Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM)."
- **`[REM-6.1]`**: "Core Mandate: To define the rules for managing an open position's risk and exits. It is the single source of truth for stop-loss and take-profit logic."
- **`[SYS-1.1.1]`**: "Modular separation is paramount. The core components (SE, REM, PM, RMM) must be decoupled."

### Implementation Evidence
- **`src/trading_platform/strategy/yaml_strategy.py`**: The `compile_strategy` function loads a `risk` block from the strategy's YAML configuration.
- **`src/trading_platform/backtester/core.py`**: The `run_backtest` function iterates through `strategy.long_exit_blocks` and `strategy.short_exit_blocks` and contains explicit `if "stop_loss" in rule:` and `if "take_profit" in rule:` logic.

### Impact
- **Critical.** This tight coupling breaks the core architecture, making it impossible to test different risk management models with the same strategy without altering the strategy definition. It prevents the development of a reusable REM module.

### Resolution Tasks
1.  **Create REM Module**: Create a new `src/trading_platform/risk_manager/` module.
2.  **Define REM Class**: Implement a `RiskExitManager` class that can be initialized with a risk configuration (as defined in `[REM-6.2]` and `[REM-6.3]`).
3.  **Refactor Backtester**: Modify the `run_backtest` function in `src/trading_platform/backtester/core.py`.
    - It should accept a `RiskExitManager` instance as an argument.
    - Remove all hard-coded stop-loss and take-profit logic from the backtester's main loop.
4.  **Update Backtester Loop**: In the loop, after processing signals, the backtester should call a method on the `RiskExitManager` instance (e.g., `rem.check_exits(portfolio.current_position, current_bar)`) to see if a risk-based exit should occur.
5.  **Refactor Strategy Loading**: Remove the `risk` block from the `CompiledStrategy` object in `src/trading_platform/strategy/yaml_strategy.py`. Strategy definitions should no longer contain any risk management rules.

---

## 2. Medium Discrepancy: Insufficient Exit Reason in JSON Brief

### Discrepancy
The JSON brief is required to provide detailed traceability for analysis. For any trade closed by a risk rule, it must record the specific native rule configuration that triggered the exit.

The current implementation only records a simple string (e.g., "stop-loss") as the `exit_reason`, failing to capture the full context.

### Requirement Conflict
- **`[JSON-11.25]`**: The `trades` object in the brief must record the original native rule for REM-triggered exits (e.g., `{ "triggered_by": "stop_loss", "rule": { "value": 50, "type": "pips" } }`).

### Implementation Evidence
- **`src/trading_platform/backtester/core.py`**: The `run_backtest` function calls `portfolio.close_position(...)` with a simple string, for example: `exit_reason="stop-loss"`.
- **`src/trading_platform/reporting/brief.py`**: The `_serialize_trade` function directly uses this simple string: `"exit_reason": t.exit_reason`.

### Impact
- **Medium.** This prevents analysts and the AI Lab from understanding *why* a stop-loss or take-profit was triggered. It's impossible to tell if a trade was closed by a 50-pip rule or a 2-ATR rule, making automated optimization and analysis difficult.

### Resolution Tasks
1.  **Update `close_position` Method**: Modify the `PortfolioManager.close_position` method to accept a structured dictionary for the `exit_reason` instead of just a string.
2.  **Update Backtester Call Site**: When the backtester (or future REM) determines an exit is needed, it must construct the required dictionary (e.g., `{"triggered_by": "stop_loss", "rule": sl_rule}`) and pass it to `close_position`. The `sl_rule` variable containing the native rule is already available in the backtester's scope.
3.  **Update `_serialize_trade` Function**: Ensure the `_serialize_trade` function in `src/trading_platform/reporting/brief.py` correctly serializes the new structured `exit_reason` object into the JSON brief without flattening it.

---

## 3. Low Discrepancy: Ad-hoc Run Configuration

### Discrepancy
The system architecture is designed to be driven by a single, unified `Run Configuration` object that binds all components of a run together.

The current implementation in `cli.py` does not adhere to this. It loads a configuration file and then passes numerous individual arguments (`initial_cash`, `warmup_bars`, `blackout_utc`, etc.) to the `run_backtest` function. This makes the interface between the CLI and the backtesting core brittle and ad-hoc.

### Requirement Conflict
- **`[SYS-1.1.2]`**: "A **Run Configuration** binds these components together for a specific backtest or live trading session."
- **`[SYS-1.7.3]`**: Implies the existence of a singular configuration object for which a schema will be created.

### Implementation Evidence
- **`src/trading_platform/cli.py`**: The `cmd_run_backtest` function calls `run_backtest` with many individual arguments extracted from the raw config dictionary (`cfg_raw`), rather than passing a single, validated `RunConfig` object.

### Impact
- **Low.** The system works, but this implementation detail introduces fragility. If a new parameter is added, it must be manually threaded through the `cli.py` function call, which is error-prone. It also deviates from the architectural intent of having a single object define a run.

### Resolution Tasks
1.  **Refactor `run_backtest` Signature**: Modify the `run_backtest` function in `src/trading_platform/backtester/core.py` to accept a single `RunConfig` object as its primary argument instead of multiple individual parameters.
2.  **Update `run_backtest` Implementation**: Inside `run_backtest`, access parameters from the `config` object (e.g., `config.initial_cash`, `config.warmup_bars`).
3.  **Update `cli.py` Call Site**: In `cmd_run_backtest`, after validating the raw config into a `RunConfig` object (`cfg`), pass this single `cfg` object to the `run_backtest` function.
