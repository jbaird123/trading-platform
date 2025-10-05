# Implementation Plan: Enhance RMM with Time-Based Filters

This document outlines the specific, step-by-step tasks required to enhance the Regime Market Manager (RMM) with time-based filtering capabilities.

**Objective:** Integrate time-based conditions (hour, day of week) directly into the RMM engine, making it the single source of truth for all regime definitions and eliminating the need for a separate `BlackoutPolicy`.

---

### 0. Setup

1.  [x] **Create a new branch:** Create and check out a new feature branch for this work.
    ```bash
    git checkout -b feature/RMM-time-filters
    ```

### 1. Update the RMM JSON Schema

1.  [x] **Modify `docs/schemas/rmm.schema.json`:** Add new time-based conditions to the `predicate` definition.
    -   **File:** `docs/schemas/rmm.schema.json`
    -   **Action:** Find the `predicate` definition within `$defs`.
    -   Locate the `enum` for the `condition` property.
    -   **Add** the following new conditions to the `enum` list:
        -   `hour_is_in`
        -   `hour_is_not_in`
        -   `day_of_week_is_in`
        -   `day_of_week_is_not_in`
    -   **Action:** Add a new property `values` to the `predicate` properties.
    -   The `values` property should be an array of strings or numbers. This will be used by the new time-based conditions.

    The updated `predicate` definition should look similar to this:
    ```json
    "predicate": {
      "type": "object",
      "properties": {
        "condition": {
          "type": "string",
          "enum": [
            "is_above",
            "is_below",
            "cross_above",
            "cross_below",
            "hour_is_in",
            "hour_is_not_in",
            "day_of_week_is_in",
            "day_of_week_is_not_in"
          ]
        },
        "left": { "$ref": "#/$defs/operand" },
        "right": { "$ref": "#/$defs/operand" },
        "values": {
            "type": "array",
            "items": {
                "anyOf": [
                    { "type": "string" },
                    { "type": "integer" }
                ]
            }
        }
      },
      "required": ["condition"]
    }
    ```

### 2. Create Tests for Time-Based Conditions

1.  [x] **Create a new test file:** `tests/regime_market_manager/test_time_based_regimes.py`.
    -   **File:** `tests/regime_market_manager/test_time_based_regimes.py`
    -   **Content:** Add the basic structure for a Pytest file, including necessary imports.

2.  [x] **Add a test for the `hour_is_in` condition.**
    -   **File:** `tests/regime_market_manager/test_time_based_regimes.py`
    -   **Action:** Write a test function `test_hour_is_in_predicate`.
    -   Inside the test, create a sample DataFrame with a `pd.DatetimeIndex` covering a full day.
    -   Define an RMM configuration dictionary that uses the `hour_is_in` condition (e.g., `values: [9, 10, 11]`).
    -   Instantiate the `RMMEngine` with this config.
    -   Call `engine.classify_regime()` on the sample data.
    -   **Assert** that the returned `label` is correct only for the hours specified (9, 10, 11) and 'unknown' for all other hours.
    -   **Validation:** Run `pytest tests/regime_market_manager/test_time_based_regimes.py`. **Expect this test to fail** with a `ValueError` because `hour_is_in` is not yet implemented in the engine.

3.  [x] **Add a test for the `day_of_week_is_in` condition.**
    -   **File:** `tests/regime_market_manager/test_time_based_regimes.py`
    -   **Action:** Write a test function `test_day_of_week_is_in_predicate`.
    -   Create a sample DataFrame with a `pd.DatetimeIndex` covering a full week.
    -   Define an RMM config that uses `day_of_week_is_in` (e.g., `values: [0, 2]` for Monday and Wednesday).
    -   Call `engine.classify_regime()`.
    -   **Assert** that the `label` is correct only for Mondays and Wednesdays.
    -   **Validation:** Run `pytest tests/regime_market_manager/test_time_based_regimes.py`. **Expect this test to fail.**

### 3. Implement Time-Based Logic in RMM Engine

1.  [x] **Modify `src/trading_platform/regime_market_manager/engine.py`:** Implement the logic for the new time-based predicates.
    -   **File:** `src/trading_platform/regime_market_manager/engine.py`
    -   **Action:** Navigate to the `_eval_pred` function.
    -   Add `if/elif` blocks to handle the new conditions. The logic should be similar to this:

    ```python
    # Inside _eval_pred function

    if cond == "hour_is_in":
        values = set(pred.get("values", []))
        return df.index.hour.isin(values)

    if cond == "hour_is_not_in":
        values = set(pred.get("values", []))
        return ~df.index.hour.isin(values)

    if cond == "day_of_week_is_in":
        # Monday=0, Sunday=6
        values = set(pred.get("values", []))
        return df.index.dayofweek.isin(values)

    if cond == "day_of_week_is_not_in":
        values = set(pred.get("values", []))
        return ~df.index.dayofweek.isin(values)

    # Update the final ValueError message to include the new conditions
    raise ValueError(
        f"Unrecognized RMM condition: '{cond}'. "
        f"Supported: is_above, is_below, cross_above, cross_below, "
        f"hour_is_in, hour_is_not_in, day_of_week_is_in, day_of_week_is_not_in"
    )
    ```
    -   **Validation:** Run `pytest tests/regime_market_manager/test_time_based_regimes.py`. **All tests in this file should now pass.**

2.  [x] **Add a test for combining time and indicator conditions.**
    -   **File:** `tests/regime_market_manager/test_time_based_regimes.py`
    -   **Action:** Write a test function `test_combined_time_and_indicator_regime`.
    -   Define an RMM config that uses `all_of` to combine an `hour_is_in` condition with an `is_above` indicator condition (e.g., ADX > 25).
    -   **Assert** that the regime label is applied only when BOTH conditions are true.
    -   **Validation:** Run `pytest tests/regime_market_manager/test_time_based_regimes.py`. The new test should pass.

### 4. Update Documentation

1.  [x] **Modify `docs/project_requirements.md`:** Update the system requirements to reflect the new unified regime management approach.
    -   **File:** `docs/project_requirements.md`
    -   **Action:** Locate section **[SYS-1.5] Trading Sessions & Blackout Periods**.
    -   **Modify** the text to state that blackout periods and trading windows are now configured directly within the RMM using time-based predicates.
    -   **Deprecate** the concept of a separate `BlackoutPolicy` in favor of the more powerful RMM. You can add a note like: `(Legacy Note: This functionality was previously handled by a separate BlackoutPolicy but has been consolidated into the RMM for greater flexibility)`.

### 5. Final Review

1.  [x] **Run all tests:** Ensure that no existing tests have been broken by the changes.
    ```bash
    poetry run pytest
    ```
    - **Assert:** All tests must pass. (Note: 1 pre-existing golden brief test failure due to sharpe_ratio field addition - unrelated to this work. 1310 tests passed.)

2.  [ ] **Commit and push the changes.**
    ```bash
    git add .
    git commit -m "feat(rmm): Enhance RMM with time-based filter conditions"
    git push origin feature/RMM-time-filters
    ```
