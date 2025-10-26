# Global Feature Set Implementation Plan

This document outlines the tasks required to implement a global, mandatory feature set that will be automatically included in every backtest and live trading session. This ensures feature consistency for ML models. The implementation will be validation-first, use a shared utility to ensure backtest/live parity, and intelligently filter features based on the execution timeframe.

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

3.  [ ] **Add Strictness Test for `_price_series`:** In `tests/strategy/test_features.py`, add a test for the internal `_price_series` function that calls it with an invalid source string and asserts that it raises a `ValueError`.

4.  [ ] **Implement Strict `_price_series` Logic:** In `src/trading_platform/strategy/indicator_implementations.py`, modify the `_price_series` function to be strict. It must no longer default to `"close"` and must raise a `ValueError` if the `source` is not recognized.

### 4. Create Shared Feature Resolver Utility

1.  [ ] **Define Type-Safe `ResolvedFeature`:** In the new file for the resolver, define a `dataclass` or `pydantic.BaseModel` named `ResolvedFeature` to ensure type-safe return values.

    ```python
    from dataclasses import dataclass
    from typing import Any, str | None

    @dataclass
    class ResolvedFeature:
        name: str
        type: str
        params: dict[str, Any]
        timeframe: str | None
        source: str
    ```

2.  [ ] **Add Tests for Feature Resolver:** Create a new test file `tests/core/test_feature_resolver.py`. Add test functions for the new `resolve_feature_set` utility that cover the following cases:
    *   It returns a list of `ResolvedFeature` objects.
    *   It raises a `FileNotFoundError` if `config/features/global.yaml` does not exist.
    *   It raises a `ValueError` if a feature name exists in both the global and run-specific configurations.
    *   It correctly includes features with a timeframe greater than or equal to the `execution_timeframe`.
    *   It correctly filters out features with a timeframe smaller than the `execution_timeframe` and logs a warning.
    *   It correctly includes features that have no `timeframe` specified, assuming they belong to the execution timeframe.

3.  [ ] **Implement Feature Resolver Utility:** Create a new file `src/trading_platform/core/feature_resolver.py`. In this file, create a function `resolve_feature_set(config: RunConfig) -> list[ResolvedFeature]`. This function will contain all the logic for:
    *   Loading the `global.yaml` file. If the file does not exist, raise a `FileNotFoundError`.
    *   Loading the `contextual_features` from the `config` object.
    *   Checking for duplicate feature names between the two lists and raising a `ValueError` if any are found.
    *   Merging the lists.
    *   Filtering the merged list: keep a feature if its `timeframe` is not set (implicit to execution timeframe) or if its `timeframe` is greater than or equal to the `config.execution_timeframe`.
    *   Returning the final list as `ResolvedFeature` objects.

### 5. Integrate Feature Resolver into Backtester and Live Engine

1.  [ ] **Refactor Backtester:** In `src/trading_platform/backtester/core.py`, modify the `run_backtest` function to call the new `resolve_feature_set(config)` utility and use its output. Update `tests/backtester/test_core.py` to mock the resolver utility and assert it is called correctly.

2.  [ ] **Refactor Live Trading Engine:** Locate the feature computation logic in the live trading engine (e.g., `src/trading_platform/execution/controller.py`). Modify it to also call the same `resolve_feature_set(config)` utility. This ensures backtest/live parity.

3.  [ ] **Add Parity Integration Test:** Create a new integration test that configures a `RunConfig`, calls `resolve_feature_set` as the backtester would, and then calls it again as the live engine would. Assert that the returned list of `ResolvedFeature` objects is identical in both cases.

### 6. Update Documentation

1.  [ ] Create a new documentation file at `docs/features/global_feature_set.md`.
2.  [ ] In this file, explain the purpose of the `global.yaml` file, the timeframe filtering rules, and the strict error handling for duplicates and missing files.

### 7. Final Verification

1.  [ ] Run the entire test suite using `pytest`.
2.  [ ] Confirm that all new and existing tests pass.
3.  [ ] Run `pytest --cov` and ensure that all code you added or modified has 100% test coverage.
