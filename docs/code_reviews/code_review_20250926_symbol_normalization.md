# Code Review: Changes Required

**Date:** 2025-09-26
**Subject:** Symbol Normalization Implementation

The implementation of the symbol normalization utility and its integration into the data loading pipeline is well-executed. However, the utility itself is flawed, and the subsequent refactoring to make the rest of the application instrument-agnostic is incomplete. Critical components still contain hardcoded `"EURUSD"` symbols, which prevents the system from running with other instruments.

The following changes are required before this can be approved. Address every item on this list precisely.

---

### **Required Changes**

1.  **Task 1.1 & 1.2 - Correct the `normalize_symbol` Implementation and Test:**
    -   **File:** `src/trading_platform/core/utils.py`
    -   **Action:** The implementation of `normalize_symbol` is incorrect. It must be changed to preserve numbers, not just letters.
    -   **Current (Incorrect):** `return "".join(filter(str.isalpha, symbol)).upper()`
    -   **Required (Correct):** `return "".join(filter(str.isalnum, symbol)).upper()`
    -   **File:** `tests/core/test_utils.py`
    -   **Action:** The test case that asserts `normalize_symbol("USD123CAD")` should be `"USDCAD"` is incorrect and validates the wrong behavior.
    -   **Details:**
        -   Remove the `("USD123CAD", "USDCAD")` case from the `@pytest.mark.parametrize` block.
        -   Add a new test case to ensure numbers are preserved, such as `("ESZ24", "ESZ24")` or asserting that `normalize_symbol("USD123CAD")` returns `"USD123CAD"`.

2.  **Task 4.2, 4.3, 6.2 - Complete Backtester Refactoring:**
    -   **File:** `src/trading_platform/backtester/core.py`
    -   **Action:** Remove all hardcoded `"EURUSD"` strings.
    -   **Details:**
        -   In `run_backtest`, the `symbol` for skipped trades must not be hardcoded. It should be retrieved from the `RunConfig`'s instrument definition.
        -   In `_simulate_counterfactual_exact`, the call to `pm.create_new_position` must use a symbol passed as a parameter, not a hardcoded value.
        -   Create a helper function within the module, like `_get_symbol(config: RunConfig) -> str`, to safely get the canonical symbol from the config to avoid repetition.

3.  **Task 6.4 - Complete AI Data Connector Refactoring:**
    -   **File:** `src/trading_platform/ai/data_connectors.py`
    -   **Action:** The `get_available_symbols` method must be refactored to dynamically read symbols from the instrument registry (`src/trading_platform/data/instrument.py`), not return a hardcoded list.
    -   **Action:** The `if __name__ == "__main__"` block should be updated to accept a symbol from the command line to demonstrate the new flexibility, as described in the task.

4.  **Task 6.6 - Complete Execution Controller Refactoring:**
    -   **File:** `src/trading_platform/execution/controller.py`
    -   **Action:** Modify the `run_live_controller` function to accept a `symbol: str` parameter.
    -   **Action:** Use this `symbol` parameter in the call to `adapter.place_order` instead of the hardcoded `"EURUSD"`.

5.  **Tasks 6.1, 6.3, 6.5 - Implement Missing Tests:**
    -   **Action:** For every refactoring change listed above, implement the corresponding test described in the task list (`symbol_normalization_tasks.md`). For example:
        -   Add `test_run_live_controller_should_accept_custom_symbol` to `tests/execution/test_controller.py`.
        -   Add the required tests to `tests/ai/test_data_connectors.py`.
        -   Ensure tests in `tests/backtester/test_backtester.py` verify that the counterfactual simulations can be run with a symbol other than "EURUSD".

6.  **Task 7.1 - Update Docstrings:**
    -   **Action:** After implementing the function signature changes (e.g., in `run_live_controller`), update the docstrings to reflect the new `symbol` parameters.
