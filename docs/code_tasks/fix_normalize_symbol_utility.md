# Prerequisite: Fix Symbol Normalization Utility

This document outlines the precise, ordered steps required to fix a critical bug in the `normalize_symbol` utility. This is a prerequisite and must be completed before proceeding with the tasks in `docs/code_tasks/explicit_instrument_symbol_requirement_tasks.md`.

The developer must create a new branch for this fix named `fix/normalize-symbol-bug` and follow these tasks in the specified sequence. All changes must be accompanied by tests to ensure 100% coverage is maintained for the modified code.

---

### 1. Correct the Test for the `normalize_symbol` Utility

- [x] **1.1. Update the Test for `normalize_symbol`**
    -   **File:** `tests/core/test_utils.py`
    -   **Action:** Modify the `@pytest.mark.parametrize` block in the `test_normalize_symbol` function.
    -   **Logic:**
        1.  Remove the incorrect test case: `("USD123CAD", "USDCAD")`.
        2.  Add a new test case to verify that numbers are correctly preserved in a symbol. For example: `("ESZ24", "ESZ24")`.
        3.  Add another test case to verify that numbers are preserved even with separators: `("CLV24/NYM", "CLV24NYM")`.

### 2. Implement the Fix for the `normalize_symbol` Utility

- [x] **2.1. Update the `normalize_symbol` Implementation**
    -   **File:** `src/trading_platform/core/utils.py`
    -   **Action:** Modify the `normalize_symbol` function to correctly preserve alphanumeric characters.
    -   **Logic:** Change the implementation to filter by `str.isalnum` instead of `str.isalpha`.
        ```python
        # Current (Incorrect)
        return "".join(filter(str.isalpha, symbol)).upper()

        # Required (Correct)
        return "".join(filter(str.isalnum, symbol)).upper()
        ```

### 3. Verification

- [x] **3.1. Run Tests and Verify Coverage**
    -   **Action:** Run the tests to ensure they pass and that 100% test coverage for the modified files is maintained.
    -   **Command:** `pytest --cov=src/trading_platform/core/utils.py tests/core/test_utils.py`
