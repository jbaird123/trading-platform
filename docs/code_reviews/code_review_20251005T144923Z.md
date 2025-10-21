# Code Review: Changes Required

**Review of:** `docs/code_tasks/add_default_contextual_features.md` & `docs/code_tasks/implement_contextual_features.md`
**Date:** 2025-10-05T14:49:23Z

The implementation is incomplete and non-compliant. The following changes are required before this can be approved. Address every item on this list precisely.

---

### Consolidated List of Required Changes

1.  **Missing End-to-End Test:** ✅ **COMPLETE**
    *   **Task:** III.5
    *   **File:** `tests/smoke/test_end_to_end_smoke.py`
    *   **Action:** Implement the `test_e2e_run_with_contextual_features` test case as specified in the task list. This test is critical to verify that contextual features are correctly processed from a YAML configuration file and appear in the final `brief.json`.
    *   **Resolution:** Implemented end-to-end test that creates market data, runs backtest with default contextual features, and verifies `entry_context['strategy_features']['ctx_atr']` exists and is a number in the final brief.json.

2.  **Trade Context Schema Alignment:** ✅ **COMPLETE**
    *   **Requirement:** `[JSON-11.30]`
    *   **File:** `src/trading_platform/backtester/core.py`
    *   **Issue:** The current implementation adds contextual features directly to the `context` dictionary. The project requirements specify a nested structure within the final trade object (e.g., `trade.entry_context.strategy_features`).
    *   **Action:** Adjust the backtester and portfolio manager logic to ensure the context dictionary passed upon position creation/closure is structured to match the brief's schema requirements. The final `Trade` object in the brief should have a clear separation between `entry_context`, `exit_context`, and their sub-fields like `strategy_features` and `regime`.
    *   **Resolution:** Restructured backtester to ALWAYS use nested `{"strategy_features": {...}}` structure for consistency. Updated REM's `_get_context_value` to access values inside `strategy_features`. All 1355 tests passing.

3.  **Schema Updates (Historical Note):**
    *   **Tasks:** I.2 and 2
    *   **Status:** The standalone JSON schema has been retired; validation now resides entirely in the `RunConfig` Pydantic model (`src/trading_platform/core/config.py`).
    *   **Action:** No further schema file updates required. Documentation should reference the Pydantic model for field definitions and defaults.
