# Test Suite Cleanup Plan

This plan outlines the steps to resolve the test failures and errors discovered after re-enabling the full test suite. The tasks are prioritized from most fundamental (architecture) to most specific (component and UI tests).

## Task Checklist

### Phase 1: Architecture & Data Integrity

1.  [x] **Fix Architectural Boundaries:** Resolve all `ImportError` failures in `tests/core/test_import_boundaries.py`. This involves updating the `__init__.py` files for each core module (`strategy`, `backtester`, `portfolio`, etc.) to expose their public APIs correctly.
2.  [x] **Fix Brief Schema and Golden Master:**
    -   [x] Address the `ValidationError` in `tests/reporting/test_brief.py` by ensuring the generated brief includes all required fields (e.g., `avg_win_gross`).
    -   [x] Address the `ValueError` in `tests/core/test_parameter_sweep_consistency.py` by adding the missing schema description for `activity.average_trades_per_day`.
    -   [x] Update the golden brief file (`tests/fixtures/golden_run/golden_brief.json`) to match the current, correct brief structure, resolving the `AssertionError` in `tests/core/test_golden_brief.py`.

### Phase 2: Core Component Bugs

3.  [x] **Fix Cost Calculation Logic:** Debug the `AssertionError` failures in `tests/reporting/test_costs.py` to ensure the `cost_breakdown` field is correctly populated in all scenarios.

### Phase 3: Test Suite Refactoring

4.  [x] **Fix Outdated CLI Tests:**
    -   [x] Resolve the `AttributeError` errors in `tests/cli/test_cli_full_coverage.py` by updating the `monkeypatch` calls to target the correct, refactored locations of functions like `load_instrument_data`.
    -   [x] Fix the related `AttributeError` failures in `tests/cli/test_cli_coverage_gaps.py`.

### Phase 4: Final Verification

5.  [x] **Run Full Test Suite:** After all the above tasks are complete, run the full test suite one final time to ensure all tests pass and the suite is green.
