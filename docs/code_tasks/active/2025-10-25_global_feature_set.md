# Global Feature Set Implementation Plan

This document outlines the tasks required to implement a global, mandatory feature set that will be automatically included in every backtest. This ensures feature consistency for ML models across training, analysis, and live trading environments. The implementation will be validation-first, use a shared utility to ensure backtest/live parity, and intelligently filter features based on the execution timeframe.

---

### 1. Initial Setup

1.  [ ] Create and switch to a new git branch named `feature/global-feature-set`.

### 2. Create the Global Feature Configuration

1.  [ ] Create a new directory `config/features/`.
2.  [ ] Inside `config/features/`, create a new file named `global.yaml`.
3.  [ ] Populate `config/features/global.yaml` with the following content:

    ```yaml
    # Global features that are ALWAYS included in every backtest context.
    features:
      - name: "rsi_14_15m"
        type: "RSI"
        params: { "length": 14 }
        timeframe: "15min"

      - name: "atr_14_1h"
        type: "ATR"
        params: { "length": 14 }
        timeframe: "1H"

      - name: "volume_sma_20_1d"
        type: "SMA"
        params: { "length": 20 }
        source: "volume"
        timeframe: "1D"
    ```

### 3. Strengthen Feature Configuration and Validation

1.  [ ] **Add Pydantic Validation Test:** Locate the file containing the `FeatureConfig` Pydantic model (likely `src/trading_platform/core/config.py`). In the corresponding test file, add a new test that attempts to create a `FeatureConfig` instance with an invalid `source` (e.g., `source="invalid_source"`) and asserts that a `pydantic.ValidationError` is raised.

2.  [ ] **Implement Pydantic Validation:** In the `FeatureConfig` Pydantic model, modify the `source` field from `str` to a `typing.Literal` to enforce a strict set of allowed values, including `"volume"`.

    ```python
    source: Literal["open", "high", "low", "close", "volume", "hl2", "ohlc4"] = "close"
    ```

3.  [ ] **Add Strictness Test for `_price_series`:** In `tests/strategy/test_features.py`, add a test for the internal `_price_series` function that calls it with an invalid source string and asserts that it raises a `ValueError`.

4.  [ ] **Implement Strict `_price_series` Logic:** In `src/trading_platform/strategy/indicator_implementations.py`, modify the `_price_series` function to be strict. It must no longer default to `"close"` and must raise a `ValueError` if the `source` is not recognized.

### 4. Create Shared Feature Resolver Utility

1.  [ ] **Add Tests for Feature Resolver:** Create a new test file `tests/core/test_feature_resolver.py`. Add test functions for the new `resolve_feature_set` utility that cover the following cases:
    *   It correctly merges features from `global.yaml` and the `RunConfig`.
    *   It correctly filters out features with a timeframe smaller than the `execution_timeframe`.
    *   It logs a warning when a feature is filtered out due to its timeframe.
    *   It correctly handles overrides (run-specific features replace global ones) and logs a warning.
    *   It functions correctly when `global.yaml` is missing or when `contextual_features` is empty.

2.  [ ] **Implement Feature Resolver Utility:** Create a new file `src/trading_platform/core/feature_resolver.py`. In this file, create a function `resolve_feature_set(config: RunConfig) -> list[dict]`. This function will contain all the logic for:
    *   Loading the `global.yaml` file.
    *   Loading the `contextual_features` from the `config` object.
    *   Merging the two lists.
    *   Filtering the merged list based on the `config.execution_timeframe`.
    *   Returning the final, clean list of feature specifications.

### 5. Integrate Feature Resolver into Backtester

1.  [ ] **Update Backtester Tests:** Open `tests/backtester/test_core.py`. Modify the tests related to feature computation. Instead of mocking file loading or checking the list manually, you should now mock the new `resolve_feature_set` utility. Assert that `run_backtest` calls it once with the correct `config`, and that the return value from the mock is what gets passed to `compute_features`.

2.  [ ] **Refactor Backtester:** Open `src/trading_platform/backtester/core.py`. In the `run_backtest` function, remove all the feature loading, merging, and filtering logic you would have added. Replace it with a single call to the new `resolve_feature_set(config)` utility. The result of this call is the feature list that will be passed to `compute_features`.

### 6. Final Verification

1.  [ ] Run the entire test suite using `pytest`.
2.  [ ] Confirm that all new and existing tests pass.
3.  [ ] Run `pytest --cov` and ensure that all code you added or modified has 100% test coverage.
