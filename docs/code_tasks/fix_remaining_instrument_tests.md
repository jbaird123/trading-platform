# Implementation Plan: Fix Remaining Instrument Tests

This document lists the remaining test files that are failing due to the new mandatory `instrument` field in `RunConfig`. The previous refactoring updated the core logic and the main backtester tests; this plan covers the rest of the test suite.

The developer must continue working on the `fix/complete-instrument-validation` branch and address the following files. For each file, the task is the same: add the `instrument` parameter to every `RunConfig` instantiation to prevent `ValidationError`.

---

### General Instructions for Each Task:

1.  **Locate `RunConfig(...)`:** Find every instance where `RunConfig` is created.
2.  **Add Instrument:** Add `instrument={"symbol": "EURUSD"}` to the constructor call.
3.  **Helper Function (Optional but Recommended):** If a test file has multiple `RunConfig` instances, add a small helper function at the top of the file to avoid repetition:
    ```python
    def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
        """Helper to create instrument dict for RunConfig."""
        return {"symbol": symbol}
    ```
    And then call it: `RunConfig(..., instrument=_instrument())`.

---

### Task List

- [ ] **1. Fix `tests/backtester/test_backtester.py`**
    - **File:** `tests/backtester/test_backtester.py`
    - **Action:** The `_simulate_counterfactual_exact` calls are missing the new `symbol` keyword argument. Add `symbol="EURUSD"` to these calls.

- [ ] **2. Fix `tests/cli/test_cli_cover_else.py`**
    - **File:** `tests/cli/test_cli_cover_else.py`
    - **Action:** The `cfg` dictionary passed to the CLI command is missing the `instrument` key.

- [ ] **3. Fix `tests/cli/test_cli_more.py`**
    - **File:** `tests/cli/test_cli_more.py`
    - **Action:** The YAML config created in the test is missing the `instrument` key.

- [ ] **4. Fix `tests/cli/test_cli_toy_data_path.py`**
    - **File:** `tests/cli/test_cli_toy_data_path.py`
    - **Action:** The `cfg` dictionary is missing the `instrument` key.

- [ ] **5. Fix `tests/core/test_blackout_policy_in_brief.py`**
    - **File:** `tests/core/test_blackout_policy_in_brief.py`
    - **Action:** The `RunConfig` instantiation is missing the `instrument` parameter.

- [ ] **6. Fix `tests/core/test_golden_brief.py`**
    - **File:** `tests/core/test_golden_brief.py`
    - **Action:** The `assert_briefs_equal` is failing because the symbol is hardcoded in the golden file. Update the golden file `tests/fixtures/golden_run/golden_brief.json` to match the expected output or adjust the test logic.

- [ ] **7. Fix `tests/core/test_monte_carlo_resim.py`**
    - **File:** `tests/core/test_monte_carlo_resim.py`
    - **Action:** The `base_cfg` dictionary used to create a `RunConfig` in `monte_carlo_resimulation` is missing the `instrument` key.

- [ ] **8. Fix `tests/core/test_run.py`**
    - **File:** `tests/core/test_run.py`
    - **Action:** Multiple `RunConfig` instantiations are missing the `instrument` parameter.

- [ ] **9. Fix `tests/core/test_runconfig_warmup.py`**
    - **File:** `tests/core/test_runconfig_warmup.py`
    - **Action:** The `RunConfig` instantiation is missing the `instrument` parameter.

- [ ] **10. Fix `tests/core/test_sweeps.py`**
    - **File:** `tests/core/test_sweeps.py`
    - **Action:** The `base_cfg` dictionary used to create a `RunConfig` in `run_parameter_sweep` is missing the `instrument` key. This affects many tests in this file.

- [ ] **11. Fix `tests/core/test_walk_forward_optimize_and_test.py`**
    - **File:** `tests/core/test_walk_forward_optimize_and_test.py`
    - **Action:** The `base_cfg` dictionary is missing the `instrument` key.

- [ ] **12. Fix `tests/reporting/test_config_snapshot_stability.py`**
    - **File:** `tests/reporting/test_config_snapshot_stability.py`
    - **Action:** The `RunConfig` instantiation is missing the `instrument` parameter.

- [ ] **13. Fix `tests/reporting/test_finalize_saves_trades_csv.py`**
    - **File:** `tests/reporting/test_finalize_saves_trades_csv.py`
    - **Action:** The `RunConfig` instantiation is missing the `instrument` parameter.

### Verification

- [ ] **14. Run Full Test Suite**
    -   **Action:** After fixing all the files listed above, run the full test suite to ensure all tests now pass.
    -   **Command:** `poetry run pytest`
