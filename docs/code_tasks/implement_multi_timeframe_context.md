# Implementation Plan: Multi-Timeframe Contextual Features

**Objective:** This implementation is the foundational technical step for our AI/ML strategy. Its purpose is to enable the feature computation engine to calculate indicators on higher timeframes relative to a backtest's primary execution timeframe (e.g., using a 1-hour RSI in a 15-minute backtest).

This capability is essential for creating the "rich trade" records that will power both the **Diagnostic Engine** (for analyzing past performance) and the future **Predictive Engine** (for real-time decision making).

**Instructions for Developer:**
Please create and switch to a new branch named `feature/multi-timeframe-context` before starting these tasks. You must follow the tasks in the exact order they are listed below. Every implementation task is preceded by a test-writing task.

---

### Phase 1: Create a Reusable Data Resampling Utility

*First, we need a robust, tested function to convert data from a lower timeframe to a higher one (e.g., 15min -> 1H).*

1.  **[ ] Create Test File for Resampling Logic.**
    -   **File to Create:** `tests/data/test_resample.py`
    -   **Action:** Create this new file and add the basic imports (`pandas`, `pytest`).

2.  **[ ] Write Test for OHLC Resampling.**
    -   **File to Modify:** `tests/data/test_resample.py`
    -   **Action:** Add a new test function `test_resample_data_correctly_aggregates_ohlc`.
    -   **Logic:**
        1.  Create a sample pandas DataFrame with a 15-minute frequency `DatetimeIndex` and columns for `open`, `high`, `low`, `close`, `volume`.
        2.  The data should span at least one hour (e.g., 4-5 bars).
        3.  Import a (not-yet-created) function `resample_data` from `trading_platform.data.resample`.
        4.  Call `resample_data(df, rule='1H')`.
        5.  Assert that the resulting DataFrame has a single row.
        6.  Assert that the `open` of the result is the `open` of the first 15m bar.
        7.  Assert that the `high` of the result is the maximum of the `high`s of the 15m bars.
        8.  Assert that the `low` of the result is the minimum of the `low`s of the 15m bars.
        9.  Assert that the `close` of the result is the `close` of the last 15m bar.
        10. Assert that the `volume` of the result is the sum of the `volume`s of the 15m bars.

3.  **[ ] Implement the Resampling Utility.**
    -   **File to Create:** `src/trading_platform/data/resample.py`
    -   **Action:** Create the function `resample_data(data: pd.DataFrame, rule: str) -> pd.DataFrame`.
    -   **Logic:**
        1.  Define the aggregation logic dictionary: `agg_logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}`.
        2.  Return `data.resample(rule).apply(agg_logic).dropna()`.

4.  **[ ] Verify Phase 1 Implementation.**
    -   **Action:** Run the tests for the new module.
    -   **Command:** `poetry run pytest tests/data/test_resample.py`
    -   **Acceptance Criteria:** The test `test_resample_data_correctly_aggregates_ohlc` must pass.

---

### Phase 2: Enhance Feature Engine for Multi-Timeframe Calculation

*Now, we will modify the core feature computation logic to use the new resampling utility.*

5.  **[ ] Update FeatureConfig Model with Timeframe.**
    -   **File to Modify:** `src/trading_platform/core/config.py`
    -   **Action:** In the `FeatureConfig` Pydantic model, add a new optional field: `timeframe: str | None = Field(default=None, description="The timeframe on which to calculate this feature, e.g., '1H', '4H', '1D'.")`
    -   **Acceptance Criteria:** The model is updated. No tests should break yet.

6.  **[ ] Write Test for Multi-Timeframe Indicator Calculation.**
    -   **File to Create:** `tests/strategy/test_multi_timeframe_features.py`
    -   **Action:** Add a new test function `test_compute_features_with_higher_timeframe`.
    -   **Logic:**
        1.  Create a sample 15-minute DataFrame spanning several hours.
        2.  Define a `FeatureConfig` for a 1-hour RSI: `FeatureConfig(name='h1_rsi', type='RSI', params={'length': 14}, timeframe='1H')`.
        3.  Manually calculate the expected result:
            a. Resample the 15m data to 1H.
            b. Calculate RSI(14) on the 1H data.
            c. Forward-fill this result onto the original 15m index.
        4.  Call the `compute_features` function from `trading_platform.strategy.features` with the 15m data and the list containing your `h1_rsi` config.
        5.  Assert that the returned DataFrame contains a column named `h1_rsi`.
        6.  Assert that the values in this column are equal to your manually calculated (and forward-filled) expected values.

7.  **[ ] Implement Multi-Timeframe Logic in `compute_features`.**
    -   **File to Modify:** `src/trading_platform/strategy/features.py`
    -   **Action:** Modify the `compute_features` function.
    -   **Logic:**
        1.  At the beginning of the function, create a dictionary to group features by their `timeframe` attribute. The default key should be the base timeframe of the input data.
        2.  Iterate through the input `features` list, populating this dictionary.
        3.  Create an empty list to hold the calculated feature Series, e.g., `all_features_series = []`.
        4.  Loop through the grouped features dictionary (by timeframe).
        5.  Inside the loop, if the timeframe is the base timeframe, calculate the features as before.
        6.  If the timeframe is a higher timeframe (e.g., '1H'), first call our new `resample_data` utility on the input data.
        7.  Calculate the indicators on this new, resampled DataFrame.
        8.  For each resulting indicator Series, use `.reindex(base_data.index, method='ffill')` to align it back to the original, lower-frequency index.
        9.  Add the aligned Series to your `all_features_series` list.
        10. After the loop, concatenate all the Series in `all_features_series` and join them to the original input DataFrame.

8.  **[ ] Verify Phase 2 Implementation.**
    -   **Action:** Run the tests for the new feature.
    -   **Command:** `poetry run pytest tests/strategy/test_multi_timeframe_features.py`
    -   **Acceptance Criteria:** The test `test_compute_features_with_higher_timeframe` must pass.

---

### Phase 3: End-to-End Verification

*Finally, we ensure the Backtester correctly uses this new capability to enrich trade context.*

9.  **[ ] Write End-to-End Integration Test.**
    -   **File to Modify:** `tests/backtester/test_contextual_features.py`
    -   **Action:** Add a new test function `test_backtester_trade_context_with_multi_timeframe_feature`.
    -   **Logic:**
        1.  Define a `RunConfig` that includes a `contextual_features` list with one multi-timeframe feature, e.g., `{'name': 'h1_atr', 'type': 'ATR', 'params': {'length': 14}, 'timeframe': '1H'}`.
        2.  Run a simple backtest that generates at least one trade.
        3.  Manually calculate the expected value of the 1H ATR for the bar where the trade was entered.
        4.  Get the first `Trade` object from the backtest result.
        5.  Assert that the key `h1_atr` exists in the `trade.context_at_entry` dictionary.
        6.  Assert that its value matches your manually calculated expected value.

10. **[ ] Verify Final Integration.**
    -   **Action:** Run the tests for the backtester.
    -   **Command:** `poetry run pytest tests/backtester/test_contextual_features.py`
    -   **Acceptance Criteria:** All tests, including the new integration test, must pass. This confirms the entire pipeline is working as designed.
