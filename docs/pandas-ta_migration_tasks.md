# Migration Plan: `ta` to `pandas-ta`

This document tracks the tasks required to migrate the project from the `ta` library to `pandas-ta`.

---

### Phase 1: Setup and Inventory

- [x] **1.1: Add Dependency**: Add `pandas-ta` to the `[tool.poetry.dependencies]` section in `pyproject.toml`.
- [x] **1.2: Inventory Current Indicators**: Read `src/trading_platform/strategy/indicators_registry.py` to identify all `ta` indicators in use.
- [x] **1.3: Create Migration Mapping Document**: Create `docs/technical/pandas_ta_migration_map.md` with a detailed mapping of `ta` to `pandas-ta` indicators, including parameter and output differences.

### Phase 2: Implement the Adapter

- [x] **2.1: Create the Adapter Module**: Create the file `src/trading_platform/strategy/pandas_ta_adapter.py`.
- [x] **2.2: Implement Adapter Functions**: Populate the adapter with wrapper functions that call `pandas-ta` and normalize the output (e.g., naming).
- [x] **2.3: Add Unit Tests for the Adapter**: Create `tests/strategy/test_pandas_ta_adapter.py` and add tests for key indicators (SMA, EMA, etc.) to ensure the adapter works as expected.

### Phase 3: The "Flip the Switch"

- [x] **3.1: Update the Indicator Registry**: Modify `src/trading_platform/strategy/indicators_registry.py` to point to the new adapter functions instead of the `ta` library.
- [x] **3.2: Run All Tests and Analyze Failures**: Execute the full test suite and save the output of failing tests for the next phase.

### Phase 4: Stabilize and Fix Tests

- [x] **4.1: Systematically Fix Failing Tests**: Work through the test failures from the previous step. This will likely involve multiple commits.
    - [x] Fix tests in `tests/strategy/`.
    - [x] Fix tests in `tests/backtester/`.
    - [x] Fix tests in `tests/core/`.
    - [x] Fix tests in `tests/reporting/`.
    - [x] Fix any other failing tests.
- [x] **4.2: Ensure Full Test Suite Passes**: Run `poetry run pytest -q` until all tests are green.

### Phase 5: Finalize and Clean Up

- [x] **5.1: Remove Old Dependency**: Remove the `ta` library from `pyproject.toml` and run `poetry lock`.
- [x] **5.2: Enforce Migration**: Add a CI check or pre-commit hook to block new imports from the `ta` library.
- [x] **5.3: Update Documentation**: Update `docs/project_requirements.md` and other relevant developer docs to reflect the change.
