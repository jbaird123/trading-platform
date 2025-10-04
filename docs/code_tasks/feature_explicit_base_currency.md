# Explicit Base Currency Implementation Plan

**Objective:** Refactor the `PortfolioManager` to require an explicit `base_currency`. For the MVP, this will be hard-coded to support "USD" only, but the change makes the currency assumption transparent and paves the way for future multi-currency support.

**Branch Name:** `feature/explicit-base-currency`

### Implementation Steps

1.  **[ ] Modify `PortfolioManager` to Require `base_currency`.**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:**
        1.  Modify the `__init__` method signature to accept a new, non-optional string parameter: `base_currency: str`.
        2.  In the body of the `__init__` method, store this parameter as an instance attribute: `self.base_currency = base_currency`.
        3.  Immediately after storing the attribute, add the following assertion to enforce the MVP constraint:
            ```python
            assert self.base_currency == "USD", (
                "MVP only supports USD as the base currency."
            )
            ```
    *   **Reason:** This is the breaking change that makes the `base_currency` requirement explicit throughout the system. All tests that instantiate a `PortfolioManager` will now fail, guiding the refactoring.

2.  **[ ] Run Pytest to Catalog All Failing Tests.**
    *   **Action:** From the terminal, run the command `poetry run pytest`.
    *   **Expected Outcome:** You will see a large number of `TypeError` failures (estimated at 94) across approximately 14 test files. This is expected and confirms the full scope of the necessary updates.

3.  **[ ] Update All Failing `PortfolioManager` Instantiations.**
    *   **Action:** Go through each of the test files that failed in the previous step.
    *   **Logic:** For every line where a `PortfolioManager(...)` is created, add the new required `base_currency="USD"` argument.
    *   **Example:**
        *   **Old Code:** `pm = PortfolioManager(initial_cash=1000.0, instrument=TEST_INSTRUMENT)`
        *   **New Code:** `pm = PortfolioManager(initial_cash=1000.0, instrument=TEST_INSTRUMENT, base_currency="USD")`

4.  **[ ] Final Verification.**
    *   **Action:** Execute `poetry run pytest` one last time.
    *   **Expected Outcome:** All tests should now pass, confirming that the refactoring is complete and no regressions were introduced.
