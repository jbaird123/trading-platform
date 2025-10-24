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
    *   **File to Modify**: (legacy) `docs/schemas/run_config.schema.json` – now superseded by the `RunConfig` Pydantic model.
    *   **Action**: Add a `default` key to the `contextual_features` property in the schema to document this behavior for users. The value should be an array of objects matching the default indicators you defined.

---

### 2. Always Include Raw Volume

3.  [ ] Task: Create a test to verify that raw `volume` is always included in the trade context.
    *   **File to Modify**: `tests/backtester/test_contextual_features.py`
    *   **Action**: Add a new test function `test_trade_context_always_includes_volume`.
    *   **Logic**:
        1.  Run a backtest using a minimal configuration that does **not** specify `volume` in any strategy or contextual features list.
        2.  Ensure the backtest produces at least one trade.
        3.  Assert that the `context_at_entry` dictionary of the first trade contains a key named `volume`.
        4.  Assert that the value of this key matches the `volume` from the market data for the entry bar of that trade.

4.  [x] Task: Modify the `Backtester` to always inject `volume` into the trade context.
    *   **File to Modify**: `src/trading_platform/backtester/core.py`
    *   **Action**: In the `run_backtest` function, locate the main `for` loop where the `context` dictionary is assembled for each bar.
    *   **Logic**: After the existing context is created (from the strategy and contextual features), explicitly add the raw volume from the current bar to it. The line should be similar to: `context['volume'] = current_bar['volume']`. This ensures volume is always available for analysis in the final brief.
