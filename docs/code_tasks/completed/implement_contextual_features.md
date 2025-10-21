### Contextual Features Implementation Plan

**Branch Name:** `feature/contextual-features` ✅

**Instructions for the developer:**
Please create and switch to a new branch named `feature/contextual-features` before starting these tasks. Follow the tasks in the exact order provided.

---

#### I. Update Configuration Schema and Model

1.  [x] Task: Create a test for the `RunConfig` model with `contextual_features`.
    *   **File to Create**: `tests/core/test_config_contextual_features.py`
    *   **Action**: Add a new test function `test_run_config_loads_contextual_features`.
    *   **Logic**:
        1.  Define a sample run configuration as a dictionary, including a `contextual_features` key. This key should hold a list of feature dictionaries (e.g., `[{ "name": "atr", "type": "ATR", "params": { "length": 14 } }]`).
        2.  Import `RunConfig` from `src.trading_platform.core.config`.
        3.  Use `RunConfig.model_validate()` to parse the dictionary.
        4.  Assert that the resulting `RunConfig` object has a `contextual_features` attribute.
        5.  Assert that this attribute is a list of `FeatureConfig` objects (you will define this model in the next step) and that its contents match the input dictionary.

2.  [x] Task: Update the `RunConfig` model and `run_config.schema.json`.
    *   **File to Modify**: `src/trading_platform/core/config.py`
    *   **Action**:
        1.  At the top of the file, add a new Pydantic model `FeatureConfig` that mirrors the structure of a feature (validated via the indicator registry). It should have fields: `name: str`, `type: str`, `params: dict[str, Any] | None = None`, `source: str | None = None`, and `source_ref: dict[str, Any] | None = None`.
        2.  In the `RunConfig` class, add the new optional field: `contextual_features: list[FeatureConfig] | None = Field(default=None, description="A list of indicators to compute for context, even if not used in strategy rules.")`.
    *   **File to Modify**: `docs/schemas/run_config.schema.json`
    *   **Action**:
        1.  Add a new optional property `contextual_features` to the top-level `properties` object.
        2.  The schema for this property should be:
            ```json
            "contextual_features": {
              "type": "array",
              "description": "A list of indicators to compute for context, even if not used in strategy rules.",
              "items": {
                "type": "object",
                "properties": {
                  "name": { "type": "string" },
                  "type": { "type": "string" },
                  "params": { "type": "object" },
                  "source": { "type": "string" },
                  "source_ref": { "type": "object" }
                },
                "required": ["name", "type"]
              }
            }
            ```

#### II. Integrate Feature Calculation into Backtester

3.  [x] Task: Create a test to ensure the `Backtester` computes and uses contextual features.
    *   **File to Create**: `tests/backtester/test_contextual_features.py`
    *   **Action**: Add a new test function `test_backtester_adds_contextual_features_to_trade_context`.
    *   **Logic**:
        1.  Set up a simple `RunConfig` that defines one `contextual_features` (e.g., ATR with length 14, named `ctx_atr`).
        2.  Create mock `market_data` (DataFrame) and `signals` (Series). The signals should produce at least one trade.
        3.  In the test, manually calculate the expected ATR on the mock data.
        4.  Call `run_backtest` from `src.trading_platform.backtester.core`.
        5.  The function will return a list of `Trade` objects. Get the first trade.
        6.  Assert that `trade.context_at_entry` is a dictionary.
        7.  Assert that the key `ctx_atr` exists in `trade.context_at_entry['strategy_features']`.
        8.  Assert that its value matches the pre-calculated ATR value for the entry bar.

4.  [x] Task: Modify the `Backtester` to calculate and inject contextual features.
    *   **File to Modify**: `src/trading_platform/backtester/core.py`
    *   **Action**: Modify the `run_backtest` function.
    *   **Logic**:
        1.  After the initial input validation, add a new block of code.
        2.  Check if `config.contextual_features` is present and not empty.
        3.  If it is, import `compute_features` from `src.trading_platform.strategy.features`.
        4.  Call `compute_features` with the `market_data`, the list of `config.contextual_features`, and an empty dictionary for parameters. This will return a new DataFrame with the contextual features added as columns.
        5.  Store this enriched DataFrame in a new variable, e.g., `data_with_context`.
        6.  In the main `for` loop, when building the `context` dictionary, you currently have `context = strategy.get_context(i)`. After this line, update the context by pulling the values of the contextual features from the `data_with_context` DataFrame for the current bar `i`.
        7.  Specifically, iterate through `config.contextual_features`, get each feature's `name`, and update the `context` dictionary like so: `context[feature.name] = data_with_context[feature.name].iloc[i]`.
        8.  Ensure this enriched `context` is what gets passed to `portfolio.close_position` and `portfolio.create_new_position`. *Self-correction: The `context` is already passed. The key is to enrich it correctly before it's used.* The logic should be to merge the strategy context with the new contextual feature values. A good way is to get the strategy context first, then update it with the contextual feature values from the enriched dataframe at the current index `i`.

#### III. Final Verification

5.  [ ] Task: Write an end-to-end integration test.
    *   **File to Modify**: `tests/smoke/test_end_to_end_smoke.py`
    *   **Action**: Add a new test case `test_e2e_run_with_contextual_features`.
    *   **Logic**:
        1.  Create a minimal `run_config.yaml` file in a temporary directory for the test. This config should specify a simple strategy and include a `contextual_features` section with at least one indicator (e.g., `ATR(14)` named `ctx_atr`).
        2.  Execute a full backtest run using this configuration file (you can look at other tests in this file for examples of how to orchestrate a run).
        3.  After the run completes, load the `brief.json` file from the run's output directory.
        4.  Assert that the `trades` array in the brief is not empty.
        5.  Access the first trade in the array.
        6.  Assert that `entry_context['strategy_features']['ctx_atr']` exists and is a number.
