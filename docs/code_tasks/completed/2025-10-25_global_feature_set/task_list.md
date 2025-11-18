# Global Feature Set Implementation Plan

This document outlines the tasks required to implement a global, mandatory feature set that will be automatically included in every backtest and live trading session. This ensures feature consistency for ML models. The implementation will be validation-first, use a shared utility to ensure backtest/live parity, and intelligently filter features based on the execution timeframe.

## Implementation Status

**Branch**: `feature/global-feature-set`
**Status**: Core infrastructure complete (Sections 1-6). Backtester/Live integration pending.

### Completed (Commits d4e79e7, d78566d)
- ✅ Namespace separation via Pydantic validators
- ✅ Global configuration file and model
- ✅ Timeframe comparison utility
- ✅ Feature resolver with filtering
- ✅ Comprehensive test coverage (20 tests)
- ✅ Complete documentation

### Pending
- ⏳ Backtester integration (Section 7, steps 1-2)
- ⏳ Live engine integration (Section 7, steps 3-4)
- ⏳ Integration tests (Section 7, step 5)
- ⏳ Final verification (Section 9)

The core utilities are production-ready. Backtester/live integration requires deeper understanding of existing feature computation logic and is marked with TODO comments in the codebase.

---

## Architecture: Namespace Separation via Naming Conventions

To prevent feature name collisions between global features and strategy features, we enforce strict naming conventions:

1. **Global features** (defined in `config/features/global.yaml`) **MUST** have timeframe prefixes:
   - Valid: `5min_rsi_14`, `15min_ema_9`, `1h_atr_14`, `4h_rsi`, `1d_volume_sma_20`
   - Invalid: `rsi_14`, `ema_9`, `atr_14` (missing timeframe prefix)

2. **Strategy features** (defined in strategy YAML configs) **MUST NOT** have timeframe prefixes:
   - Valid: `rsi`, `ema_fast`, `ema_slow`, `atr`
   - Invalid: `1h_rsi`, `15min_ema_fast` (has timeframe prefix)

3. **`contextual_features` is removed** from `RunConfig` entirely. All non-strategy features must be defined in `global.yaml`.

This ensures that feature names in `context_at_entry` and `context_at_exit` can never collide, as they come from separate namespaces. The naming convention is enforced via Pydantic validators, making it impossible to instantiate invalid configurations.

---

### 1. Initial Setup

1.  [ ] Create and switch to a new git branch named `feature/global-feature-set`.

### 2. Create the Global Feature Configuration

1.  [ ] Create a new directory `config/features/`.
2.  [ ] Inside `config/features/`, create a new file named `global.yaml`.
3.  [ ] Populate `config/features/global.yaml` with the following content (note timeframe prefix naming):

    ```yaml
    # Global features that are ALWAYS included in every backtest context.
    # Feature names MUST have timeframe prefix (1min_, 5min_, 15min_, 1h_, 4h_, 1d_)
    features:
      - name: "15min_rsi_14"
        type: "RSI"
        params: { "length": 14 }
        timeframe: "15min"

      - name: "1h_atr_14"
        type: "ATR"
        params: { "length": 14 }
        timeframe: "1H"

      - name: "1d_volume_sma_20"
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

5.  [ ] **Add Test for Global Feature Name Validation:** In `tests/core/test_config.py`, add a new test `test_feature_config_global_requires_timeframe_prefix` that attempts to create a `FeatureConfig` instance with validation context `{"is_global": True}` and a name without a timeframe prefix (e.g., `name="rsi_14"`). Assert that a `pydantic.ValidationError` is raised with a message about missing timeframe prefix.

6.  [ ] **Add Test for Global Feature Valid Names:** In `tests/core/test_config.py`, add a test `test_feature_config_global_accepts_valid_prefix` that creates `FeatureConfig` instances with validation context `{"is_global": True}` and valid timeframe-prefixed names (e.g., `"1min_rsi"`, `"5min_ema"`, `"15min_atr"`, `"1h_rsi"`, `"4h_ema"`, `"1d_sma"`). Assert that no validation error is raised.

7.  [ ] **Implement Global Feature Name Validator:** In `src/trading_platform/core/config.py`, add a `@field_validator("name")` to the `FeatureConfig` model. Use `info: ValidationInfo` to check if `info.context.get("is_global", False)` is True. If so, validate that the name matches the regex pattern `^(m1|m5|m15|h1|h4|d1)_[a-z0-9_]+$`. If validation fails, raise a `ValueError` with message: `"Global features must have timeframe prefix (1min_, 5min_, 15min_, 1h_, 4h_, 1d_). Got: {v}"`.

8.  [ ] **Add Test for Strategy Feature Name Validation:** In `tests/strategy/test_models.py`, add a test `test_strategy_feature_cannot_have_timeframe_prefix` that attempts to create a strategy config with a feature that has a timeframe prefix (e.g., `name="1h_rsi"`). Assert that a `pydantic.ValidationError` is raised with a message about forbidden timeframe prefix.

9.  [ ] **Add Test for Strategy Feature Valid Names:** In `tests/strategy/test_models.py`, add a test `test_strategy_feature_accepts_valid_names` that creates strategy configs with features that have valid names without timeframe prefixes (e.g., `"rsi"`, `"ema_fast"`, `"ema_slow"`, `"atr_value"`). Assert that no validation error is raised.

10. [ ] **Implement Strategy Feature Name Validator:** In `src/trading_platform/strategy/models.py`, modify the `StrategyConfig` model to add a `@model_validator(mode='after')` that iterates through `self.features` and validates that each feature name does NOT match the pattern `^(m1|m5|m15|h1|h4|d1)_`. If any feature name has a timeframe prefix, raise a `ValueError` with message: `"Strategy features must NOT have timeframe prefix. Found: {feature.name}"`.

11. [ ] **Remove Contextual Features from RunConfig:** In `src/trading_platform/core/config.py`, remove the `contextual_features` field from the `RunConfig` model. Ensure no default value or optional field remains.

12. [ ] **Add Test for RunConfig Contextual Features Removal:** In `tests/core/test_config.py`, add a test `test_run_config_has_no_contextual_features_field` that verifies the `RunConfig` model does not have a `contextual_features` field. Attempt to instantiate `RunConfig` with `contextual_features=[]` and assert that a `ValidationError` is raised (indicating the field doesn't exist).

### 4. Create Timeframe Comparison Utility

1.  [ ] **Add Test for Timeframe Comparison:** Create a new test file `tests/core/test_timeframes.py`. Add test functions for a new `compare_timeframes` utility that cover the following cases:
    *   `compare_timeframes("1min", "1H")` returns a negative value (1min < 1H)
    *   `compare_timeframes("1H", "1min")` returns a positive value (1H > 1min)
    *   `compare_timeframes("15min", "15min")` returns 0 (equal)
    *   `compare_timeframes("5min", "1D")` returns a negative value (5min < 1D)
    *   It raises `ValueError` for unrecognized timeframe strings

2.  [ ] **Implement Timeframe Comparison Utility:** Create a new file `src/trading_platform/core/timeframes.py`. Implement a function `compare_timeframes(tf1: str, tf2: str) -> int` that:
    *   Defines a mapping of timeframe strings to integer ranks: `{"1min": 1, "5min": 5, "15min": 15, "1H": 60, "4H": 240, "1D": 1440}`
    *   Returns `rank1 - rank2` (negative if tf1 < tf2, positive if tf1 > tf2, zero if equal)
    *   Raises `ValueError` with message `"Unrecognized timeframe: {tf}"` if either timeframe is not in the mapping

### 5. Create Global Feature Set Configuration Model

1.  [ ] **Add Test for GlobalFeatureSetConfig:** In `tests/core/test_config.py`, add a test `test_global_feature_set_config_validates_names` that:
    *   Creates a `GlobalFeatureSetConfig` with valid feature names (all with timeframe prefix)
    *   Attempts to create a `GlobalFeatureSetConfig` with invalid feature names (missing timeframe prefix) and asserts `ValidationError` is raised
    *   Verifies that the validation context `{"is_global": True}` is automatically applied to all features

2.  [ ] **Implement GlobalFeatureSetConfig Model:** In `src/trading_platform/core/config.py`, create a new Pydantic model:
    ```python
    class GlobalFeatureSetConfig(BaseModel):
        """Configuration for the global feature set loaded from global.yaml."""

        features: list[FeatureConfig] = Field(
            default_factory=list,
            description="List of global features with timeframe prefixes"
        )

        @model_validator(mode='after')
        def validate_all_features_have_prefix(self) -> Self:
            """Ensure all features have timeframe prefix by validating with is_global context."""
            # Re-validate each feature with is_global context
            for feature in self.features:
                # Trigger re-validation with context
                FeatureConfig.model_validate(
                    feature.model_dump(),
                    context={"is_global": True}
                )
            return self
    ```

### 6. Create Shared Feature Resolver Utility

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

2.  [ ] **Add Tests for Feature Resolver:** Create a new test file `tests/core/test_feature_resolver.py`. Add test functions for the new `resolve_global_features` utility that cover the following cases:
    *   It returns a list of `ResolvedFeature` objects when `global.yaml` exists.
    *   It raises a `FileNotFoundError` if `config/features/global.yaml` does not exist.
    *   It correctly includes features with a timeframe greater than or equal to the `execution_timeframe` (e.g., a 1-min execution timeframe includes h1 and d1 features).
    *   It correctly filters out features with a timeframe smaller than the `execution_timeframe` (e.g., a 1-hour execution timeframe excludes m15 and m5 features).
    *   It correctly includes features that have no `timeframe` specified, treating them as belonging to the execution timeframe.

3.  [ ] **Implement Feature Resolver Utility:** Create a new file `src/trading_platform/core/feature_resolver.py`. In this file, create a function `resolve_global_features(execution_timeframe: str) -> list[ResolvedFeature]`. This function will contain all the logic for:
    *   Loading the `config/features/global.yaml` file. If the file does not exist, raise a `FileNotFoundError` with message: `"Global feature configuration not found at config/features/global.yaml"`.
    *   Parsing the YAML content into a `GlobalFeatureSetConfig` object (which automatically enforces timeframe prefix naming via its validator).
    *   Filtering the features list: keep a feature if its `timeframe` is not set (implicit to execution timeframe) OR if `compare_timeframes(feature.timeframe, execution_timeframe) >= 0` (feature timeframe >= execution timeframe).
    *   Converting filtered `FeatureConfig` objects to `ResolvedFeature` objects and returning the list.

### 7. Integrate Global Feature Resolution into Backtester and Live Engine

1.  [ ] **Add Backtester Test for Global Features:** In `tests/backtester/test_core.py`, add a test that mocks `resolve_global_features` to return a list of `ResolvedFeature` objects. Run a backtest and verify that the global features are computed and included in `context_at_entry` alongside strategy features. Assert that feature names from global (with timeframe prefix) and strategy (without prefix) do not collide.

2.  [ ] **Refactor Backtester to Use Global Features:** In `src/trading_platform/backtester/core.py`, modify the `run_backtest` function to:
    *   Call `resolve_global_features(config.execution_timeframe)` at the start of the backtest.
    *   Compute global features on the appropriate timeframes using the existing indicator computation logic.
    *   Merge global feature values into `context_at_entry` and `context_at_exit` dictionaries before trade execution. Since global features have timeframe prefixes and strategy features don't, there will be no name collisions.
    *   Remove any logic related to `config.contextual_features` (which no longer exists).

3.  [ ] **Add Live Engine Test for Global Features:** Locate the test file for the live trading engine (e.g., `tests/execution/test_controller.py`). Add a test similar to the backtester test that verifies global features are computed and included in context.

4.  [ ] **Refactor Live Trading Engine to Use Global Features:** Locate the feature computation logic in the live trading engine (e.g., `src/trading_platform/execution/controller.py`). Modify it to:
    *   Call `resolve_global_features(config.execution_timeframe)` during initialization.
    *   Compute global features on the appropriate timeframes.
    *   Merge global feature values into context dictionaries, ensuring backtest/live parity.
    *   Remove any logic related to `config.contextual_features`.

5.  [ ] **Add Integration Test for Backtest/Live Parity:** Create a new integration test in `tests/integration/test_global_features_parity.py` that:
    *   Defines a strategy with features (without timeframe prefix).
    *   Creates a `global.yaml` with features (with timeframe prefix).
    *   Calls `resolve_global_features("5min")` and verifies the returned features.
    *   Simulates computing context in both backtester and live engine modes.
    *   Asserts that the context dictionaries are identical in structure and contain both global and strategy features without name collisions.

### 8. Update Documentation

1.  [ ] Create a new documentation file at `docs/features/global_feature_set.md`.
2.  [ ] In this file, document the following:
    *   **Purpose**: Explain that `global.yaml` defines mandatory features for ML model consistency across all backtests and live trading.
    *   **Namespace Separation**: Document the naming convention (global features MUST have timeframe prefix, strategy features MUST NOT).
    *   **Timeframe Filtering**: Explain that features are filtered based on `execution_timeframe`, keeping features where `feature.timeframe >= execution_timeframe`. Provide examples (1-min chart includes h1 and d1 features; 1-hour chart excludes m15 and m5 features).
    *   **Validation Rules**: Document that Pydantic validators enforce naming conventions at config instantiation time.
    *   **Error Handling**: Explain that missing `global.yaml` raises `FileNotFoundError`, and invalid naming raises `ValidationError`.
    *   **Removal of contextual_features**: Document that `RunConfig.contextual_features` has been removed; all non-strategy features must be in `global.yaml`.
    *   **Timeframe Comparison**: Document the `compare_timeframes` utility and how it's used for filtering.

### 9. Final Verification

1.  [ ] Run the entire test suite using `pytest`.
2.  [ ] Confirm that all new and existing tests pass.
3.  [ ] Run `pytest --cov` and ensure that all code you added or modified has 100% test coverage.
