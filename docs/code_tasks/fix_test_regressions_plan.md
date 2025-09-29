# Implementation Plan: Fix Test Regressions from Brief Enrichment

**Objective:** To methodically resolve the 5 test failures that occurred after the brief enrichment changes, ensuring the fixes are correct and do not mask underlying problems.

**Branch Name:** `fix/test-regressions-brief-enrichment`

---

## Instructions for Developer

You must create a new branch named `fix/test-regressions-brief-enrichment` before starting these tasks. Complete the tasks in the exact order they are listed. The goal is to fix existing tests, so you will be validating your changes by running the tests and seeing them pass.

---

## Task List

### Part 1: Revert Incorrect Test Fixes & Address Root Cause

*This part reverts the questionable test patches and fixes the underlying logic that caused them to fail.*

1.  **[x] Task: Revert Incorrect Changes in `test_yaml_strategy.py`.**
    *   **File to Modify:** `tests/strategy/test_yaml_strategy.py`
    *   **Action:** Revert the assertions in `TestSignalStateMachine::test_get_context_method` and `test_compiled_strategy_generate_signals_basic` to their original state. The new implementation of `get_context` was incorrect for out-of-bounds lookups.
    *   **Acceptance Criteria:** The lines are reverted. The tests will now fail, but for the correct reason.

2.  **[x] Task: Update `get_context` Tests to Expect an Exception.**
    *   **File to Modify:** `tests/strategy/test_yaml_strategy.py`
    *   **Action:** Modify `test_get_context_method` and `test_compiled_strategy_generate_signals_basic` to assert that an `IndexError` is raised for out-of-bounds lookups. This aligns with the new, stricter design.
    *   **Example Change (in `test_get_context_method`):**
        *   **FROM:**
            ```python
            context_invalid = compiled_strategy.get_context(999)
            assert context_invalid == {}
            ```
        *   **TO:**
            ```python
            import pytest
            with pytest.raises(IndexError):
                compiled_strategy.get_context(999)
            ```
    *   **Acceptance Criteria:** The tests are updated to use `pytest.raises(IndexError)`. They will fail until the implementation is changed in the next step.

3.  **[x] Task: Modify `get_context` to Raise an Exception.**
    *   **File to Modify:** `src/trading_platform/strategy/yaml_strategy.py`
    *   **Action:** Change the implementation of the `get_context` method to "fail fast". If the requested index is out of bounds, it should raise an `IndexError`.
    *   **Logic:** At the beginning of the method, add a check like `if self._feature_df is None or not (0 <= index < len(self._feature_df)): raise IndexError("Context lookup index is out of bounds.")`.
    *   **Acceptance Criteria:** The tests updated in the previous task must now pass.

### Part 2: Fix Data and Reporting Test Failures

4.  **[ ] Task: Fix `field_definitions` Coverage Failure.**
    *   **File to Modify:** `src/trading_platform/reporting/brief.py`
    *   **Action:** The test `test_field_definitions_cover_all_leaf_paths` is failing because `skipped_trades` was added to the brief without a corresponding definition. Add this definition in the `generate_brief` function.
    *   **Implementation:** Find the line `placeholders.update(base)`. Immediately *after* it, add the following code block to ensure the definition is always present:
        ```python
        if "skipped_trades" not in placeholders.get("field_definitions", {}):
            placeholders.setdefault("field_definitions", {})["skipped_trades"] = "A list of trades that were signaled but not executed due to policy constraints (e.g., blackout, caps, RMM)."
        ```
    *   **Acceptance Criteria:** The test `test_field_definitions_cover_all_leaf_paths` must pass.

5.  **[ ] Task: Fix Golden Brief Skipped Trades Failure.**
    *   **File to Modify:** `tests/core/test_golden_brief.py`
    *   **Action:** The test `test_brief_matches_golden_master` now fails because no trades are being skipped. The previous implementation of `get_context` likely caused this regression. Since `get_context` is now fixed, this test may already pass. Run the test individually.
    *   **Command:** `poetry run pytest tests/core/test_golden_brief.py`
    *   **Acceptance Criteria:** The test must pass. If it still fails, you must investigate why the `run_backtest` call in this test is no longer producing skipped trades and report your findings before proceeding.

6.  **[ ] Task: Fix Manual Verification PnL Failure.**
    *   **File to Modify:** `tests/core/test_manual_verification.py`
    *   **Action:** The test `test_core_calculations_match_manual_csv` is failing because the PnL is off (`-4.0` instead of `-5.0`). This indicates a subtle change in execution logic. The most likely cause is the change made to `src/trading_platform/risk_manager/core.py` where an empty config is now allowed. This might be preventing the correct costs from being applied in this specific test.
    *   **Investigation:** You must debug the `run_backtest` call within this test. Verify that the `CostModel` is being initialized and used correctly. The expected PnL of -5.0 implies costs are expected. Report your findings on why the PnL is different before applying a fix.
    *   **Acceptance Criteria:** The test must pass, and the reason for the PnL discrepancy must be documented in the commit message.

### Part 3: Final Verification

7.  **[ ] Task: Run Full Test Suite.**
    *   **Action:** Run the entire test suite to ensure all changes are integrated correctly and no new regressions have been introduced.
    *   **Command:** `poetry run pytest`
    *   **Acceptance Criteria:** 100% of tests must pass.