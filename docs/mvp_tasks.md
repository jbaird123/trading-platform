# MVP Implementation Task List

This document breaks down the `mvp_roadmap.md` into a granular, actionable checklist. Mark items as complete as you finish them.

## Phase 1: Foundations

- [x] **Task 0: Codebase Cleanup**
  - [x] Delete the outdated `tests/test_sanity.py` file. Its functionality is replaced by `tests/test_core.py`.

- [x] **Task 0.5: Verify Project Skeleton**
  - [x] Run `poetry run python -m trading_platform.core.run` to confirm the `initialize_run` function creates a run directory and `config.json`.
  - [x] Run `poetry run pytest` to confirm the `test_core.py` test for `initialize_run` passes.

- [x] **Task 1: Initialize Development Environment**
  - [x] Run `poetry install` to create the virtual environment and install all dependencies listed in `pyproject.toml`.

- [x] **Task 2: Set Up Pre-commit Hooks**
  - [x] Add `pre-commit` to the development dependencies in `pyproject.toml`.
  - [x] Run `poetry lock` to update the `poetry.lock` file with the new dependency.
  - [x] Run `poetry install` to install the packages from the updated lock file.
  - [x] Run `poetry run pre-commit install` to activate the hooks for your local git repository.
  - [x] Make a test commit to verify the hooks (e.g., `ruff`, `mypy`) run automatically.

- [x] **Task 3: Create Initial CI/CD Workflow & SonarCloud Integration**
  - [x] Create the `.github/workflows/ci.yml` file and define the `name` and `on` triggers.
  - [x] Add steps to install dependencies with caching.
  - [x] Add steps to run linter (Ruff), type checker (MyPy), and tests (Pytest).
  - [x] Push a commit to a new branch and open a Pull Request to `main` to verify that the GitHub Actions workflow is triggered and passes.
  - [x] Add SonarCloud secrets to GitHub and add the SonarCloud analysis step to `ci.yml`.

- [x] **Task 4: Implement Data Schema Contract (BDD/TDD)**
  - [x] Create the feature file: `tests/features/data_schema.feature`.
  - [x] Create the test file: `tests/step_defs/test_data_schema_steps.py`.
  - [x] Run `pytest` and see the BDD tests fail with "step definition not found" errors.
  - [x] Implement the step definition skeletons in `test_data_schema_steps.py`.
  - [x] Run `pytest` again and see the tests fail with `NotImplementedError` or assertion errors.
  - [x] Create the implementation file: `src/trading_platform/data/schema.py`.
  - [x] Write the code for loading and normalizing data to make the tests pass.

- [x] **Task 5: Implement Basic Strategy Logic (BDD/TDD)**
  - [x] Create the feature file: `tests/features/strategy_engine/signal_generation.feature`.
  - [x] Create the test file: `tests/step_defs/strategy_engine/test_signal_generation_steps.py`.
  - [x] Run `pytest` and see tests fail with "step not implemented".
  - [x] Implement the step definition skeletons to call the (not-yet-implemented) strategy code.
  - [x] Create the implementation file: `src/trading_platform/strategy/exponential_moving_average.py`.
  - [x] Write the strategy logic to make the tests pass.

- [ ] **Task 6: Implement Baseline Regime Market Manager (BDD/TDD)**
  - [x] Create the feature file: `tests/features/regime_market_manager/market_regime_classification.feature`.
  - [x] Create the test file: `tests/step_defs/regime_market_manager/test_market_regime_classification_steps.py`.
  - [x] Run `pytest` and see tests fail with assertion errors.
  - [x] Create the implementation file: `src/trading_platform/regime_market_manager/classification.py`.
  - [x] Write the RMM logic to make the tests pass.

- [x] **Task 7: Implement Backtester Core Logic (BDD/TDD)**
  - [x] Create the feature file: `tests/features/backtester/core_backtest.feature`.
  - [x] Create the test file: `tests/step_defs/backtester/test_core_backtest_steps.py`.
  - [x] Run `pytest` and see tests fail with assertion errors due to BDD parsing.
  - [x] Create the implementation file: `src/trading_platform/backtester/core.py`.
  - [x] Write the backtester logic to make the tests pass.

- [x] **Task 8: Implement Core Portfolio Manager (TDD)**
  - [x] Create `src/trading_platform/portfolio/position.py` and `trade.py` data classes.
  - [x] Create `src/trading_platform/portfolio/portfolio.py` with a `PortfolioManager` class to open/close positions.
  - [x] Create `tests/step_defs/portfolio/test_portfolio.py` with unit tests for the `PortfolioManager`.

- [x] **Task 9: Enhance Backtester with Risk Management (Stops/TP)**
  - [x] Create/update feature file: `tests/features/backtester/risk_management.feature`.
  - [x] Add scenarios for stop-loss and take-profit exits based on fixed prices.
  - [x] Update backtester logic to check for stop/tp triggers on each bar by interacting with the Portfolio Manager.
  - [x] Write tests to confirm correct exit reasons and prices.

- [x] **Task 10: Implement Portfolio Metrics**
  - [x] Create `src/trading_platform/portfolio/metrics.py`.
  - [x] Implement functions to calculate equity curve and win rate from a list of trades. (Drawdowns: TODO)
  - [x] Create `tests/portfolio/test_metrics.py` with unit tests for these calculations.

- [ ] **Task 11: Generate JSON Brief v1**
  - [x] Create `src/trading_platform/reporting/brief.py`.
  - [x] Implement aggregation into the JSON Brief (instrument-agnostic):
    - [x] overall_performance (currency-based)
    - [x] risk_snapshot
    - [x] equity_stats (equity_curve, drawdown)
    - [x] distribution (mean/median/std, p05/p95)
    - [x] streaks (longest/current)
    - [x] regimes breakdown (per-regime performance)
  - [x] Add micro-tests to validate section presence and basic types (`tests/reporting/test_brief.py`).
  - [x] Add a step to the run flow to generate and save `runs/{run_id}/brief.json`.
  - [x] Populate `data_quality` section (missing/duplicate bars, NaNs, monotonic index).
  - [x] Populate `provenance` and `environment` (python/platform/timezone; data range, symbols). (Git/app/deps: TODO)
  - [x] Add `instrument_definitions` snapshot (per symbol metadata) and `cost_model`/`fill_policy`/`tie_break_policy` placeholders.

- [ ] **Task 12: Backtester Input Validation & Guards**
  - [x] Validate required columns exist and have no NaNs (e.g., `close`).
  - [x] Validate `len(signals) == len(market_data)` and signal values in {long, short, flat}.
  - [x] Raise `ValueError` on invalid inputs (fail-fast), with actionable messages.

*This task list will be expanded as we complete each phase.*

---

## Phase 6: Complete MVP Features

- [ ] **Task 13: Instrument Definitions & Cost Model (Scaffold)**
  - [x] Create `src/trading_platform/data/instrument.py` with `InstrumentDefinition` (e.g., `symbol, tick_size, point_value, base_ccy, quote_ccy, lot_size, min_trade_unit, commission_structure, spread_model, slippage_model`).
  - [x] Add `instrument_definitions` snapshot to the brief (per-symbol JSON-serializable dict).
  - [x] Wire PM/BT to accept an `instrument` arg, but keep PnL in base currency (no behavior change yet).
  - [x] Tests: instrument dataclass creation + brief serialization.

- [ ] **Task 14: Fill Policy, Tie-Break, and Cost Placeholders**
  - [x] Record `fill_policy` and `tie_break_policy` in the brief from run/config.
  - [x] Add per-trade `cost_breakdown` placeholder in brief (e.g., `{spread, commission, slippage}` defaulting to 0.0).
  - [x] Tests: brief contains policies and cost placeholders.

- [ ] **Task 15: Reporting – HTML Export (Skeleton)**
  - [x] Add `reporting/html_export.py` to generate a minimal HTML report (skeleton with entries/exits table).
  - [x] Save to `runs/{run_id}/report.html` in finalize step.
  - [x] Tests: file is written; contains basic sections.

- [ ] **Task 16: Execution Layer (EL) – MVP Interface**
  - [ ] Create `src/trading_platform/execution/__init__.py` and `adapter_base.py` defining a minimal interface.
  - [ ] Add `oanda_stub.py` (no network) that logs order placement attempts and uses PM for state.
  - [ ] Tests: stub accepts a signal and produces a loggable action.

- [ ] **Task 17: Monte Carlo + Walk-Forward Scaffolds**
  - [ ] Add `monte_carlo` config + placeholder summary (e.g., seed, n_paths) to brief.
  - [ ] Add `walk_forward` config + placeholder split metadata to brief.
  - [ ] Tests: brief sections present with expected fields.

- [ ] **Task 18: Docs & QA Sweep**
  - [ ] README quickstart updates (run → brief → report).
  - [ ] Ensure CI green; ruff/mypy tidy; re-run `pytest -q` locally.
  - [ ] Add example brief under `docs/examples/brief.json`.
