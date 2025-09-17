# Requirements Alignment Task List

This document provides a checklist of tasks required to bring the codebase into alignment with the core architectural principles and requirements defined in `docs/project_requirements.md`. The tasks are derived from the findings in `docs/requirements_compliance_check.md`.

---

## 1. New Module: Risk & Exit Manager (REM)

*These tasks address the critical architectural violation of mixing risk logic into the backtester and strategy modules.*

- [ ] Create the new module directory: `src/trading_platform/risk_manager/`.
- [ ] Create an `__init__.py` file within the new module.
- [ ] Define a `RiskExitManager` class within the module. This class will be responsible for loading and interpreting REM configurations as defined in the project requirements.

---

## 2. Strategy Module (`src/trading_platform/strategy/`)

*These tasks decouple risk management from strategy definitions.*

- [ ] In `yaml_strategy.py`, refactor the `compile_strategy` function to no longer load the `risk` block from strategy YAML files.
- [ ] In `yaml_strategy.py`, remove the `risk` attribute from the `CompiledStrategy` dataclass.

---

## 3. Backtester Module (`src/trading_platform/backtester/`)

*These tasks refactor the backtester to use the new REM module and a unified run configuration.*

- [ ] In `core.py`, refactor the `run_backtest` function signature to accept a single `RunConfig` object and a `RiskExitManager` object, removing the multiple ad-hoc arguments.
- [ ] In `core.py`, remove all hard-coded stop-loss and take-profit logic from the main `run_backtest` loop.
- [ ] In the `run_backtest` loop, add a call to the `RiskExitManager` instance (e.g., `rem.check_exits()`) to determine if a risk-based exit should occur for the current position and bar.
- [ ] When a risk exit is triggered by the REM, ensure the backtester constructs the detailed, structured `exit_reason` dictionary (as required by `[JSON-11.25]`) to be passed to the portfolio.

---

## 4. CLI Module (`src/trading_platform/cli.py`)

*This task ensures the CLI adheres to the unified run configuration principle.*

- [ ] In `cmd_run_backtest`, update the call to `run_backtest` to pass the single, validated `RunConfig` object instead of multiple individual arguments.

---

## 5. Portfolio Module (`src/trading_platform/portfolio/`)

*This task enables detailed exit reason tracking.*

- [ ] In `portfolio.py`, modify the `PortfolioManager.close_position` method to accept a structured dictionary for the `exit_reason` argument, not just a simple string.

---

## 6. Reporting Module (`src/trading_platform/reporting/`)

*This task ensures the final report contains the required level of detail for trade exits.*

- [ ] In `brief.py`, update the `_serialize_trade` function to handle the new structured `exit_reason` object, ensuring it is serialized as a dictionary in the final JSON brief and not flattened into a string.
