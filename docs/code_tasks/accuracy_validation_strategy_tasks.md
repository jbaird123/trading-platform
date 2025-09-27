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

*Goal: Prove the core PnL and performance calculations are correct for a simple, hand-calculated scenario that covers long trades, short trades, and skipped trades.*

### 1. [x] Create Crafted Dataset and Strategy Files
1.  **Action:** Create a new data file for the test. This data must be crafted to create clear up-trends and down-trends, and also have at least two consecutive entry signals to test skipping.
    -   **File:** `tests/fixtures/manual_verification/data.csv`
    -   **Content:**
        ```csv
        timestamp,open,high,low,close,volume
        # Add ~25 bars of data that will generate long, short, and skipped trades
        # with the strategy below.
        ```
2.  **Action:** Create a strategy file capable of going long and short.
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
        short_entry_rules:
          - all_of:
              - { condition: cross_below, left: { ref: sma_fast }, right: { ref: sma_slow } }
        short_exit_rules:
          - all_of:
              - { condition: cross_above, left: { ref: sma_fast }, right: { ref: sma_slow } }
        ```

### 2. [x] Manually Calculate Expected Results
1.  **Action:** Create a csv (`docs/manual_calcs/verification.csv`) and manually perform the backtest bar-by-bar using the new, more robust files from Task 1. Assume an initial equity of $100,000 and zero costs.
2.  **Derive and record the exact values for all metrics, ensuring your scenario generates:**
    -   At least one winning and one losing trade.
    -   Both long and short trades.
    -   At least one skipped trade record.

### 3. [x] Implement the Manual Verification Test
1.  **File to Create:** `tests/core/test_manual_verification.py`
2.  **Logic:**
    -   Write a test function `test_core_calculations_match_manual_csv`.
    -   Inside the test, load the strategy and data from `tests/fixtures/manual_verification/`.
    -   Run the backtest using `run_backtest`. The configuration for the run must include a **`blackout_utc` rule for `('08:00', '10:00')`** to ensure the manually calculated skipped trade is triggered.
    -   Generate the performance report and assert that all calculated values exactly match the hardcoded values from your manual calculation in Task 2.

---

## Layer 2: Property-Based Testing for Logical Consistency

*Goal: Use automated, random testing to ensure the relationships between reported metrics are always logically sound.*

### 4. [x] Add `hypothesis` to the Project
1.  **Action:** Add `hypothesis` as a development dependency.
2.  **Command:** Run `poetry add "hypothesis" --group dev`, then `poetry lock && poetry install`.

### 5. [x] Implement Property-Based Tests
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

### 9. [ ] Create Self-Contained Golden Run Configurations
1.  **Action:** Create a new strategy file specifically for the golden run.
    -   **File:** `tests/fixtures/golden_run/strategy.yaml`
    -   **Content:** A simple strategy guaranteed to generate trades.
2.  **Action:** Create a new RMM file for the golden run.
    -   **File:** `tests/fixtures/golden_run/rmm.yaml`
    -   **Content:** A basic RMM configuration.

### 10. [ ] Update Run Config and Activate Analysis Modules
1.  **File to Modify:** `tests/fixtures/golden_run/run_config.yaml`
2.  **Logic:**
    -   Change the `strategy` path to point to the new local file: `./strategy.yaml`.
    -   Add a `regime_market_manager` section pointing to `./rmm.yaml`.
    -   Add a `costs` model to populate cost data.
    -   Append the `monte_carlo`, `walk_forward`, and `parameter_search` configurations as originally planned.

### 11. [ ] Regenerate the Golden Brief File
-   **Action:** This task is identical to **Task 5** from the previous plan. Delete the old file and copy the new one from the test output.

### 12. [ ] Final Verification
-   **Action:** This task is identical to **Task 6** from the previous plan. Run `pytest tests/core/test_golden_brief.py` to confirm it passes against the new, complete, and validated golden brief.
