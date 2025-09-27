# Accuracy Validation Strategy Implementation Plan

## Objective
To implement a three-layer testing strategy that ensures the numerical accuracy and logical consistency of the backtesting engine's output. This plan goes beyond checking for code regressions and validates that the calculations in the `brief.json` are fundamentally correct.

## Getting Started
First, create a new branch for this work. This plan supersedes the previous `populate_golden_brief_tasks.md`.
```bash
git checkout -b feature/accuracy-validation-strategy
```

---

## Layer 1: Manual Verification for Foundational Accuracy

*Goal: Prove the core PnL and performance calculations are correct for a simple, hand-calculated scenario.*

### 1. [ ] Create Crafted Dataset and Strategy Files
1.  **Action:** Create a new data file for the test.
    -   **File:** `tests/fixtures/manual_verification/data.csv`
    -   **Content:**
        ```csv
        timestamp,open,high,low,close,volume
        2023-01-01T00:00:00Z,100,101,99,100,1000
        2023-01-01T01:00:00Z,100,102,100,101,1000
        2023-01-01T02:00:00Z,101,103,101,102,1000
        2023-01-01T03:00:00Z,102,102,100,101,1000
        2023-01-01T04:00:00Z,101,101,99,100,1000
        2023-01-01T05:00:00Z,100,100,98,99,1000
        2023-01-01T06:00:00Z,99,100,98,99,1000
        2023-01-01T07:00:00Z,99,101,99,100,1000
        2023-01-01T08:00:00Z,100,102,100,101,1000
        2023-01-01T09:00:00Z,101,103,101,102,1000
        2023-01-01T10:00:00Z,102,104,102,103,1000
        2023-01-01T11:00:00Z,103,103,101,102,1000
        2023-01-01T12:00:00Z,102,102,100,101,1000
        2023-01-01T13:00:00Z,101,101,99,100,1000
        2023-01-01T14:00:00Z,100,100,98,99,1000
        ```
2.  **Action:** Create a simple strategy file that will interact with this data.
    -   **File:** `tests/fixtures/manual_verification/strategy.yaml`
    -   **Content:**
        ```yaml
        strategy_name: Manual_Verification_Strategy
        features:
          - name: sma_fast
            type: SMA
            params:
              length: 3
          - name: sma_slow
            type: SMA
            params:
              length: 8
        long_entry_rules:
          - all_of:
              - { condition: cross_above, left: { ref: sma_fast }, right: { ref: sma_slow } }
        long_exit_rules:
          - all_of:
              - { condition: cross_below, left: { ref: sma_fast }, right: { ref: sma_slow } }
        ```

### 2. [ ] Manually Calculate Expected Results
1.  **Action:** Create a spreadsheet (`docs/manual_calcs/verification.xlsx`) and manually perform the backtest bar-by-bar using the files from Task 1. Assume an initial equity of $100,000 and zero costs.
2.  **Derive and record the following exact values:**
    -   `n_trades`
    -   `total_pnl`
    -   `final_equity`
    -   `win_rate`
    -   `max_drawdown`
    -   `longest_win_streak`
    -   `longest_loss_streak`

### 3. [ ] Implement the Manual Verification Test
1.  **File to Create:** `tests/core/test_manual_verification.py`
2.  **Logic:**
    -   Write a test function `test_core_calculations_match_manual_spreadsheet`.
    -   Inside the test, load the strategy and data from `tests/fixtures/manual_verification/`.
    -   Run the backtest using `run_backtest`.
    -   Generate the performance report using the backtest results.
    -   Assert that the values in the performance report exactly match the hardcoded values you derived in your spreadsheet from Task 2.

---

## Layer 2: Property-Based Testing for Logical Consistency

*Goal: Use automated, random testing to ensure the relationships between reported metrics are always logically sound.*

### 4. [ ] Add `hypothesis` to the Project
1.  **Action:** Add `hypothesis` as a development dependency.
2.  **Command:** Run `poetry add "hypothesis" --group dev`, then `poetry lock && poetry install`.

### 5. [ ] Implement Property-Based Tests
1.  **File to Create:** `tests/core/test_properties.py`
2.  **Logic for `test_equity_and_pnl_are_consistent`:**
    -   Use `@given` from `hypothesis` to generate a float for `initial_equity` and a list of mock `Trade` objects.
    -   Calculate the expected `final_equity` by summing the PnL of the mock trades and adding it to `initial_equity`.
    -   Pass the mock trades and initial equity to the reporting function that generates `overall_performance`.
    -   Assert that the `final_equity` in the report equals your calculated `final_equity`.
3.  **Logic for `test_win_rate_is_always_valid`:**
    -   Use `@given` to generate a list of mock `Trade` objects with varying PnL (positive, negative, and zero).
    -   Pass the mock trades to the reporting function.
    -   Assert that the returned `win_rate` is always `>= 0.0` and `<= 1.0`.

---

## Layer 3: Complete the Golden Brief for Regression Testing

*Goal: Update the `golden_brief.json` to be a complete, accurate, and verified artifact for detecting future regressions.*

### 6. [ ] Create a Test to Validate `skipped_trades` Structure
-   **Action:** This task is identical to **Task 1** from the `populate_golden_brief_tasks.md` plan. Implement the test in `tests/core/test_golden_brief.py` to validate the keys of a `skipped_trades` object.

### 7. [ ] Fix `skipped_trades` Generation Logic
-   **Action:** This task is identical to **Task 2** from the previous plan. Fix the logic in `trading_platform/backtester/core.py`.

### 8. [ ] Add Missing `meta` and `provenance` Fields
-   **Action:** This task is identical to **Task 3** from the previous plan. Update the `finalize_run` call in `tests/core/test_golden_brief.py`.

### 9. [ ] Activate Advanced Analysis Modules
-   **Action:** This task is identical to **Task 4** from the previous plan. Update `tests/fixtures/golden_run/run_config.yaml` to enable `monte_carlo`, etc.

### 10. [ ] Regenerate the Golden Brief File
-   **Action:** This task is identical to **Task 5** from the previous plan. Delete the old file and copy the new one from the test output.

### 11. [ ] Final Verification
-   **Action:** This task is identical to **Task 6** from the previous plan. Run `pytest tests/core/test_golden_brief.py` to confirm it passes against the new, complete, and validated golden brief.
