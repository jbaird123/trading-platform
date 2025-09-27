# Golden Brief Population Plan

## Objective
The primary goal is to update the `golden_brief.json` file to be a complete representation of the `docs/schemas/brief.schema.json`. This involves modifying the test that generates the brief to activate all features and fix structural discrepancies, ensuring the golden file includes 100% of all possible fields.

## Getting Started
First, create a new branch for this work:
```bash
git checkout -b feature/populate-golden-brief
```

---

## Implementation Steps

The following tasks must be completed in strict sequential order.

### 1. [x] Create a Test to Validate `skipped_trades` Structure
1.  **File to Modify:** `tests/core/test_golden_brief.py`
2.  **Action:** In the `test_brief_matches_golden_master` function, immediately before the final `assert_briefs_equal(actual_brief, golden_brief)` call, add a new assertion block.
3.  **Logic:** This block must verify the structure of the items within the `skipped_trades` list in the `actual_brief`.
    -   Assert that `actual_brief["skipped_trades"]` is a list with at least one element.
    -   Get the first element, e.g., `first_skip = actual_brief["skipped_trades"][0]`.
    -   Assert that `first_skip` contains the following keys:
        -   `symbol`
        -   `side`
        -   `size`
        -   `entry_time`
        -   `skip_reason`
        -   `counterfactual_pnl`
        -   `counterfactual_mfe_currency`
        -   `counterfactual_mae_currency`
4.  **Expected Outcome:** This test will fail until Task 2 is completed.

### 2. [x] Fix `skipped_trades` Generation Logic
1.  **File to Modify:** `trading_platform/backtester/core.py`
2.  **Action:** Locate the logic within the `run_backtest` function where skipped trade dictionaries are created. This is likely where a dictionary with `reason_code` is appended to a list of skips.
3.  **Logic:** Modify the creation of the skipped trade dictionary to conform to the schema.
    -   Rename the `timestamp` key to `entry_time`.
    -   Rename the `reason_code` key to `skip_reason`.
    -   Add the following missing keys, using the signal and instrument context available at that point in the code:
        -   `side`: The intended side of the trade (e.g., from `signals`).
        -   `size`: The intended trade size (this may be a default or calculated value).
        -   `counterfactual_pnl`: Set to `0.0` as a placeholder.
        -   `counterfactual_mfe_currency`: Set to `0.0` as a placeholder.
        -   `counterfactual_mae_currency`: Set to `0.0` as a placeholder.
4.  **Verification:** Run the test from Task 1. It should now pass.

### 3. [x] Add Missing `meta` and `provenance` Fields
1.  **File to Modify:** `tests/core/test_golden_brief.py`
2.  **Action:** Locate the call to `finalize_run` inside `test_brief_matches_golden_master`.
3.  **Logic:** The `run_config` object is already created in the test. Update the `meta` dictionary passed to `finalize_run` to include `git_commit` and `run_seed` by sourcing them from the `run_config` object.
    ```python
    # Example
    meta = {
        "strategy_name": strategy.name,
        "run_id": run_config.run_id,
        "git_commit": run_config.provenance.git_commit, # Add this
        "run_seed": run_config.provenance.run_seed,       # Add this
    }
    ```

### 4. [x] Activate Advanced Analysis Modules
1.  **File to Modify:** `tests/fixtures/golden_run/run_config.yaml`
2.  **Action:** Add configurations for the currently empty analysis sections.
3.  **Logic:** Append the following configurations to the YAML file. Use minimal settings to ensure the test remains fast.
    ```yaml
    monte_carlo:
      trials: 10
      mode: 'bootstrap_trades'

    walk_forward:
      splits:
        - train_start: "2023-01-01"
          train_end: "2023-01-10"
          test_start: "2023-01-11"
          test_end: "2023-01-12"

    parameter_search:
      top:
        params:
          fast: 10
        score: 1.2
      results:
        - params:
            fast: 10
          score: 1.2
    ```

### 5. [x] Regenerate the Golden Brief File
1.  **Action:** Manually delete the existing golden brief file.
    ```bash
    rm tests/fixtures/golden_run/golden_brief.json
    ```
2.  **Action:** Run the `test_golden_brief.py` test. It will fail with an assertion error comparing the new brief to the non-existent golden file. The full path to the newly generated brief will be in the test failure output.
3.  **Action:** Copy the newly generated `brief.json` from the temporary test directory (e.g., `/tmp/pytest-of-user/pytest-0/test_brief_matches_golden_mas0/brief.json`) to overwrite the old golden brief path.
    ```bash
    # Example command, use the actual path from the test output
    cp /tmp/path/from/test/output/brief.json tests/fixtures/golden_run/golden_brief.json
    ```

### 6. [x] Final Verification
1.  **Action:** Run the `test_golden_brief.py` test again.
    ```bash
    pytest tests/core/test_golden_brief.py
    ```
2.  **Expected Outcome:** The test should now pass, comparing the backtest output against the new, fully-populated golden brief.
3.  **Action:** Commit all changed files, including the new `golden_brief.json` and this task list (with checkboxes marked).
