# Code Review: Changes Required

**Date:** 2025-09-26
**Subject:** Explicit Instrument Symbol Requirement

Excellent progress has been made on this critical architectural improvement. The effort to update the numerous test files is acknowledged and appreciated. The core change to enforce the instrument symbol at the `RunConfig` level is the correct approach.

However, the implementation is incomplete. The new validation logic is not fully tested, and more importantly, the backtester has not been updated to use the symbol from the config, which undermines the goal of this refactor. The following changes are required to complete this work.

---

### **Required Changes**

1.  **Task 1 - Add Validator Tests:**
    -   **File:** Create `tests/core/test_runconfig_symbol_requirement.py`.
    -   **Action:** Add the `test_runconfig_requires_instrument_symbol` function as described in the task list. It must test the failure modes: missing `instrument`, empty `instrument` dict, and an empty `symbol` string. This is critical for ensuring the validator is robust.

2.  **Task 4 & Others - Integrate Symbol into Backtester Logic:**
    -   **File:** `src/trading_platform/backtester/core.py`
    -   **Action:** The `run_backtest` function and its internal helpers (`_simulate_counterfactual_exact`, etc.) must be refactored to remove all hardcoded `"EURUSD"` strings.
    -   **Details:**
        -   At the beginning of `run_backtest`, call a helper function (like the `resolve_instrument_symbol` you wrote) to get the canonical symbol from `config.instrument`.
        -   Pass this symbol variable to all places that currently use a hardcoded string (e.g., logging skipped trades, creating positions in the portfolio manager).

3.  **Task 17 - Add Demo Test:**
    -   **File:** Create `tests/core/test_demo_run.py`.
    -   **Action:** Add the `test_generate_demo_run_includes_instrument` test as described in the task list to ensure the demo generation logic remains compliant.

4.  **Create Follow-up Plan:**
    -   Once the above fixes are implemented and the backtester suite is passing, the next step is to address the 64 failing tests. Please create a new task list file in `docs/code_tasks/` named `fix_remaining_instrument_tests.md` that lists all the failing test files that need to be updated.
