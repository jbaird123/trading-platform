# Multi-Timeframe Contextual Features Implementation Plan

1.  [ ] **Create** a new branch named `feature/multi-timeframe-context` from the latest `main` branch.

## Phase 1 – Resampling Utility Foundation

2.  [ ] **Create** a new test module `tests/data/test_resample.py`. Import `pandas as pd`, `pytest`, and the (not yet created) `resample_data` function from `src.trading_platform.data.resample`.
3.  [ ] **Add** a new test `test_resample_data_correctly_aggregates_ohlc` to `tests/data/test_resample.py`. This test must:
    *   Build a 15-minute pandas DataFrame covering 1 hour with known OHLCV values.
    *   Call `resample_data(df, rule="1H")`.
    *   Assert the output is a single row with the first open, max high, min low, last close, and summed volume.
4.  [ ] **Add** a new test `test_resample_data_handles_multiple_bins_and_partial_tail` to `tests/data/test_resample.py`. This test must:
    *   Create 15-minute data covering 2.5 hours.
    *   Assert that the output contains two full 1-hour rows and that the partial final row is dropped by `.dropna()`.
5.  [ ] **Add** a new test `test_resample_data_preserves_timezone_and_index_type` to `tests/data/test_resample.py`. This test must confirm the output index retains its timezone awareness and `DatetimeIndex` type.
6.  [ ] **Add** a new test `test_resample_data_errors_on_non_datetime_index` to `tests/data/test_resample.py`. This test must use `pytest.raises(TypeError)` to assert that a `TypeError` is raised if the input DataFrame's index is not a `pd.DatetimeIndex`.
7.  [ ] **Add** a new test `test_resample_data_errors_on_invalid_timeframe_rule` to `tests/data/test_resample.py`. This test must use `pytest.raises(ValueError)` to assert that a `ValueError` is raised when an invalid rule (e.g., "5Q") is passed.
8.  [ ] **Add** a new test `test_resample_data_warns_on_sparse_resampling` to `tests/data/test_resample.py`. This test should pass a 1H DataFrame to be resampled to "1D" and use `pytest.warns(UserWarning)` to check for a warning about potential NaN propagation.
9.  [ ] **Create** a new module `src/trading_platform/data/resample.py` and implement the `resample_data` function. This function must:
    *   Validate the input `data.index` is a `pd.DatetimeIndex`, raising a `TypeError` otherwise.
    *   Define the aggregation logic: `{"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}`.
    *   Execute the resampling using `data.resample(rule, label="right", closed="right").agg(agg_logic)`.
    *   If the resampled output is entirely NaN, issue a `UserWarning`.
    *   Return the result after calling `.dropna(how="all")`.
10. [ ] **Run** `poetry run pytest tests/data/test_resample.py` and confirm all Phase 1 tests pass with 100% coverage for `src/trading_platform/data/resample.py`.

## Phase 2 – Feature Engine Multi-Timeframe Support

11. [ ] **Modify** the `FeatureConfig` Pydantic model in `src/trading_platform/core/config.py` by adding a new optional field: `timeframe: str | None = Field(default=None, description="The timeframe to resample data to before computing the feature, e.g., '1H'.")`.
12. [ ] **Create** a new test module `tests/strategy/test_multi_timeframe_features.py`.
13. [ ] **Add** a test `test_compute_features_with_higher_timeframe_alignment` to the new module. This test must:
    *   Define a `FeatureConfig` with `timeframe="1H"`.
    *   Manually calculate the expected indicator values on a 1H resampled frame and then forward-fill them to the original 15m index.
    *   Assert that the output of `compute_features` matches the manually calculated Series.
14. [ ] **Add** a test `test_compute_features_caches_resampled_data_per_timeframe` to the same module. Use `unittest.mock.patch` to spy on `resample_data` and assert it is called exactly once per timeframe when multiple features share the same higher timeframe.
15. [ ] **Add** a test `test_compute_features_backwards_compatible_without_timeframe` to the same module. This test must pass a `FeatureConfig` without the `timeframe` field and assert that it computes correctly on the base data, ensuring existing strategies are not affected.
16. [ ] **Modify** the `compute_features` function in `src/trading_platform/strategy/features.py`. The logic must:
    *   Group feature configurations by their `timeframe`.
    *   Maintain a cache dictionary `resampled_frames` scoped to the single `compute_features` call.
    *   For each group of features on a higher timeframe, resample the data *once*, compute all features for that group, and store the resampled data in the cache.
    *   Use `.reindex(base.index, method="ffill")` to align the computed higher-timeframe features back to the base index.
    *   Concatenate all feature Series (both base and higher timeframe) and return the result.
17. [ ] **Run** `poetry run pytest tests/strategy/test_multi_timeframe_features.py` and confirm all Phase 2 tests pass with 100% coverage for the modified code paths.

## Phase 3 – Schema and Validation

18. [ ] **Update** the relevant JSON schema file in `tests/validation/schemas/` to reflect the addition of the optional `timeframe` field in `FeatureConfig`.
19. [ ] **Add** a new test `test_campaign_validate_accepts_timeframe_field` to `tests/validation/test_schemas.py`. This test must:
    *   Load a sample campaign YAML file that includes a `contextual_features` entry with the new `timeframe` field.
    *   Run the validation logic from `scripts/validate_requirements_coverage.py` (or similar validation script) against it.
    *   Assert that the validation passes.
20. [ ] **Run** `poetry run pytest tests/validation/test_schemas.py` and confirm the new test passes.

## Phase 4 – End-to-End Integration

21. [ ] **Add** a test `test_backtester_trade_context_with_multi_timeframe_at_entry_and_exit` to `tests/backtester/test_contextual_features.py`. This test must:
    *   Configure a `RunConfig` with a `contextual_features` entry that uses `timeframe="1H"`.
    *   Run a backtest that generates at least one trade.
    *   Assert that `trade.context_at_entry` and `trade.context_at_exit` both contain the correctly calculated higher-timeframe feature.
22. [ ] **Add** a test `test_campaign_runner_preserves_timeframe_in_run_config` to a new test file `tests/cli/test_campaign_runner.py`. This test should check that the `RunConfig` object created from a campaign YAML correctly includes the `timeframe` string.
23. [ ] **Add** a test `test_rich_trade_export_includes_multi_timeframe_features` to `tests/cli/test_export.py`. This test must run a campaign and assert that the final exported `rich_trades.csv` file includes columns for the higher-timeframe contextual features.
24. [ ] **Modify** the backtester and trade models in `src/trading_platform/backtester/core.py` and `src/trading_platform/backtester/models.py`. Ensure that the logic for capturing contextual features is executed for both trade entry and exit, and that the results are correctly stored.
25. [ ] **Modify** the campaign execution logic (likely in `src/trading_platform/cli/commands.py` and `src/trading_platform/cli/export.py`) to ensure the higher-timeframe features are present in the final data exports.
26. [ ] **Run** `poetry run pytest tests/backtester/` and `poetry run pytest tests/cli/` and confirm all Phase 4 tests pass with 100% coverage for modified files.

## Phase 5 – Documentation and Final Verification

27. [ ] **Update** the documentation in `docs/ai/05_ml_data_curation_guide.md`. The changes must include:
    *   An example of a `campaign.yaml` file using the `timeframe` field in `contextual_features`.
    *   A note in a new "Migration" section explaining how to add multi-timeframe features to existing campaigns.
    *   A brief discussion of the performance implications (memory and computation time) of using multiple higher timeframes.
28. [ ] **Run** `poetry run pytest --cov --cov-report=term-missing` across the entire project to ensure 100% test coverage is maintained for all modified modules.
29. [ ] **Update** the `CHANGELOG.md` file under the "Unreleased" section to describe the new multi-timeframe contextual feature capability.
30. [ ] **Open** a pull request, referencing this implementation plan and attaching the coverage report.
