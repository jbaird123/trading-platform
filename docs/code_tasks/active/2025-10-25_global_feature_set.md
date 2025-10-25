# Global Feature Set Implementation Plan

This document outlines the tasks required to implement a global, mandatory feature set that will be automatically included in every backtest. This ensures feature consistency for ML models across training, analysis, and live trading environments.

---

### 1. Initial Setup

1.  [ ] Create and switch to a new git branch named `feature/global-feature-set`.

### 2. Create the Global Feature Configuration

1.  [ ] Create a new directory `config/features/`.
2.  [ ] Inside `config/features/`, create a new file named `global.yaml`.
3.  [ ] Populate `config/features/global.yaml` with the following content. This file will serve as the single source of truth for the core feature set.

    ```yaml
    # Global features that are ALWAYS included in every backtest context.
    # This ensures ML models have a consistent baseline of information.

    features:
      # --- 15-minute Timeframe Features ---
      - name: "rsi_14_15m"
        type: "RSI"
        params: { "length": 14 }
        timeframe: "15min"

      - name: "atr_14_15m"
        type: "ATR"
        params: { "length": 14 }
        timeframe: "15min"

      # --- 1-hour Timeframe Features ---
      - name: "ema_50_1h"
        type: "EMA"
        params: { "length": 50 }
        timeframe: "1H"

      # --- Daily Timeframe Features ---
      - name: "volume_sma_20_1d"
        type: "SMA"
        params: { "length": 20 }
        source: "volume"
        timeframe: "1D"
    ```

### 3. Fix and Enhance Feature Source Logic

1.  [ ] **Add Test for Volume Source:** Open `tests/strategy/test_features.py`. Add a new test function that specifically tests the internal `_price_series` function from `src/trading_platform/strategy/indicator_implementations.py`. The test must:
    *   Create a sample DataFrame with `open`, `high`, `low`, `close`, and `volume` columns.
    *   Call `_price_series(df, source="volume")`.
    *   Assert that the returned pandas Series is identical to the `volume` column of the original DataFrame.

2.  [ ] **Implement Volume Source Fix:** Open `src/trading_platform/strategy/indicator_implementations.py`. Modify the `_price_series` function to correctly handle `"volume"` as a source. The updated function should look like this:

    ```python
    def _price_series(df: pd.DataFrame, source: str) -> pd.Series:
        """Convert source string to price series."""
        if source in ("open", "high", "low", "close", "volume"):
            return pd.Series(df[source], dtype="float64")
        if source == "hl2":
            return (pd.Series(df["high"]) + pd.Series(df["low"])) / 2.0
        if source == "ohlc4":
            return (
                pd.Series(df["open"])
                + pd.Series(df["high"])
                + pd.Series(df["low"])
                + pd.Series(df["close"])
            ) / 4.0
        return pd.Series(df["close"], dtype="float64")
    ```

### 4. Add Test Coverage for Global Feature Loading

1.  [ ] Open the test file `tests/backtester/test_core.py`.
2.  [ ] Add a new test function `test_run_backtest_with_global_and_run_specific_features`. In this test:
    *   Create a mock `RunConfig` that includes a `contextual_features` list with one or two strategy-specific features.
    *   Mock the loading of the `config/features/global.yaml` file to return the feature set defined above.
    *   Call `run_backtest`.
    *   Assert that the call to the `compute_features` function (you will need to mock this function using `unittest.mock.patch`) receives a merged list containing **both** the global features and the run-specific features.
3.  [ ] Add a new test function `test_run_backtest_handles_duplicate_features`. In this test:
    *   Define a global feature set and a run-specific `contextual_features` set that contains one duplicate feature (e.g., both define `rsi_14_15m`).
    *   Assert that the run-specific feature definition overrides the global one in the final merged list passed to `compute_features`.
    *   Assert that a warning is logged, e.g., `logging.warning("Duplicate feature '...' found in RunConfig, overriding global definition.")`.
4.  [ ] Add a new test function `test_run_backtest_with_global_features_only`. In this test:
    *   Create a `RunConfig` with `contextual_features` being `None` or empty.
    *   Assert that `compute_features` is called with only the features from `global.yaml`.
5.  [ ] Add a new test function `test_run_backtest_gracefully_handles_missing_global_config`. In this test:
    *   Mock the loading of `config/features/global.yaml` to raise a `FileNotFoundError`.
    *   Assert that `run_backtest` executes without error and that `compute_features` is called with only the run-specific features (if any).

### 5. Implement the Feature Loading and Merging Logic

1.  [ ] Open `src/trading_platform/backtester/core.py`.
2.  [ ] At the top of the `run_backtest` function, add logic to load and parse the `config/features/global.yaml` file. This should be wrapped in a `try...except FileNotFoundError` block to handle the file not existing.
3.  [ ] Before the existing call to `compute_features`, implement the merging logic:
    *   Start with the global features as the base list.
    *   Iterate through the `config.contextual_features` (if any).
    *   If a feature from the run config already exists in the global list (checked by `name`), replace the one in the global list and log a warning about the override.
    *   If it doesn't exist, append it to the list.
    *   The final merged list of features should be used in the call to `compute_features`.

### 6. Final Verification

1.  [ ] Run the entire test suite using `pytest`.
2.  [ ] Confirm that all new and existing tests pass.
3.  [ ] Run `pytest --cov` and ensure that the code you added or modified has 100% test coverage.
