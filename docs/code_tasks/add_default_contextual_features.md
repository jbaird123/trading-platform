# Implementation Plan: Add Default Contextual Features

**Objective:** This task follows the work in `implement_contextual_features.md`. After the mechanism for contextual features is in place, this task adds a *default set* of indicators that will be computed on every run unless explicitly overridden by the user.

---

### 1. Update Configuration to Include Defaults

1.  [x] Task: Create robust tests for the default and override behavior of `contextual_features`.
    *   **File to Modify**: `tests/core/test_config_contextual_features.py` (This file should have been created in the previous task list).
    *   **Action**: Add a new test function `test_run_config_default_and_override_contextual_features`.
    *   **Logic**: This test should cover three distinct scenarios:
        1.  **Default Case**: Instantiate `RunConfig` from a config dictionary where the `contextual_features` key is **missing**. Assert that the resulting `run_config.contextual_features` attribute is a non-empty list containing the default indicators (e.g., check for one with `name="ctx_atr"`).
        2.  **Empty Override Case**: Instantiate `RunConfig` from a config dictionary where `contextual_features` is an **empty list (`[]`)**. Assert that the resulting `run_config.contextual_features` is an empty list.
        3.  **Custom Override Case**: Instantiate `RunConfig` from a config dictionary where `contextual_features` is a **custom list** with a unique indicator (e.g., `[{ "name": "my_custom_feature", "type": "SMA", "params": {"length": 5} }]`). Assert that the resulting `run_config.contextual_features` contains *only* the custom indicator and none of the defaults.

2.  [x] Task: Update the `RunConfig` model to provide a default set of contextual features.
    *   **File to Modify**: `src/trading_platform/core/config.py`
    *   **Action**:
        1.  At the top of the file, define a module-level constant `DEFAULT_CONTEXTUAL_FEATURES` as a list of `FeatureConfig` objects. This list should include `ATR(14)` named `ctx_atr`, `RSI(14)` named `ctx_rsi`, and `EMA(200)` named `ctx_ema_slow`.
        2.  Modify the `contextual_features` field in the `RunConfig` class. Instead of `default=None`, use `default_factory=list`.
        3.  Add a `@model_validator(mode='before')` to the `RunConfig` class. In this validator, check if `contextual_features` is missing from the input data (`None`). If it is, inject the `DEFAULT_CONTEXTUAL_FEATURES` into the data dictionary. This method correctly handles cases where a user explicitly provides an empty list `[]` to override the default.
    *   **File to Modify**: `docs/schemas/run_config.schema.json`
    *   **Action**: Add a `default` key to the `contextual_features` property in the schema to document this behavior for users. The value should be an array of objects matching the default indicators you defined.
