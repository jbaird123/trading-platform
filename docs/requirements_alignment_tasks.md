# Requirements Alignment Task List

This document lists the tasks required to bring the current project implementation into alignment with its architectural requirements and MVP goals.

---

## Task List

- [ ] **Task 1: Implement Strategy-Defined Exit Logic**
  - [ ] Refactor the backtester's core loop in `src/trading_platform/backtester/core.py` to correctly parse and execute the `stop_loss` and `take_profit` rules now defined in the strategy schema.
  - [ ] Add specific unit tests to `tests/backtester/` that create strategies with these rules and verify that they trigger exits correctly under various market conditions.

- [ ] **Task 2: Implement Rich InstrumentDefinition Model**
  - [ ] Create a new Pydantic model for `InstrumentDefinition` in `src/trading_platform/data/instrument.py` that includes all fields specified in requirement [DH-2.8] (e.g., `asset_class`, `sessions`, `holidays`).
  - [ ] Refactor the `PortfolioManager` and `Backtester` to use this new class instead of a generic dictionary.
  - [ ] Update the run configuration loading to correctly parse and instantiate this object.

- [ ] **Task 3: Implement Advanced Analysis Modules**
  - [ ] **Monte Carlo**: Replace the placeholder logic in `src/trading_platform/core/robustness.py` with a full implementation of the Monte Carlo simulation as described in [AI-9.3.4].
  - [ ] **Walk-Forward Evaluation**: Replace the placeholder logic with a full implementation of WFE as described in [AI-9.3.2].
  - [ ] **Parameter Search**: Replace the placeholder logic with a full implementation of Grid/Random search as described in [AI-9.3.1].
  - [ ] Ensure the results of these analyses are correctly populated into the `brief.json` file and add tests to verify the output.

- [ ] **Task 4: Establish Golden Dataset Testing**
  - [ ] Create a `tests/fixtures/` directory to store a small, verified "golden" dataset (e.g., a short CSV file with known characteristics).
  - [ ] Refactor at least one key end-to-end test (e.g., `tests/smoke/test_end_to_end_smoke.py`) to use this golden dataset instead of synthetically generated data.
  - [ ] Document the process for using golden datasets in the project's testing guidelines.
