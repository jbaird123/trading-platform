# Multi-Timeframe Contextual Features Implementation Plan

1. [ ] **Create** branch `feature/multi-timeframe-context` from the latest `main`.

## Phase 1 – Resampling Utility Foundation

2. [ ] **Create** test module `tests/data/test_resample.py` with imports for
   `pandas as pd`, `pytest`, and
   `resample_data` (to be implemented in Phase 1).
3. [ ] **Add** test `test_resample_data_correctly_aggregates_ohlc` in
   `tests/data/test_resample.py` that:
   - Builds a 15-minute DataFrame covering 1 hour with deterministic OHLCV values.
   - Calls `resample_data(df, rule="1H")`.
   - Asserts single-row output with first-open, max-high, min-low, last-close, and
     summed volume.
4. [ ] **Add** test `test_resample_data_handles_multiple_bins_and_partial_tail` in
   `tests/data/test_resample.py` that:
   - Creates 15-minute data covering 2.5 hours.
   - Verifies two full 1H rows plus a partial row trimmed by `.dropna()`.
5. [ ] **Add** test `test_resample_data_preserves_timezone_and_index_type` in
   `tests/data/test_resample.py` that confirms output index retains tz-awareness
   and frequency metadata when starting from a UTC-indexed DataFrame.
6. [ ] **Add** test `test_resample_data_errors_on_non_datetime_index` in
   `tests/data/test_resample.py` that expects a `TypeError` when the index is not
   a `DatetimeIndex`.
7. [ ] **Implement** `resample_data` in new module
   `src/trading_platform/data/resample.py` to:
   - Validate `data.index` is a `pd.DatetimeIndex`, raising `TypeError` otherwise.
   - Apply aggregation logic
     `{"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}`.
   - Return `data.resample(rule, label="right", closed="right")`
     `.agg(agg_logic).dropna(how="any")`, preserving timezone information.
8. [ ] **Run** `poetry run pytest tests/data/test_resample.py` and confirm all
   Phase 1 tests pass with 100% coverage for `resample_data.py`.

## Phase 2 – Feature Engine Multi-Timeframe Support

9. [ ] **Add** field `timeframe: str | None = Field(...)` with descriptive docstring
   to `FeatureConfig` inside `src/trading_platform/core/config.py`.
10. [ ] **Create** test module `tests/strategy/test_multi_timeframe_features.py`
    importing `FeatureConfig` and `compute_features`.
11. [ ] **Add** test `test_compute_features_with_higher_timeframe_alignment` that:
    - Builds granular 15-minute OHLC data for 6 hours.
    - Defines `FeatureConfig(name="h1_rsi", type="RSI", params={"length": 14},
      timeframe="1H")`.
    - Manually resamples to 1H, computes RSI, forward-fills, and asserts equality
      with `compute_features` output.
12. [ ] **Add** test `test_compute_features_caches_resampled_data_per_timeframe`
    using `monkeypatch` to spy on `resample_data` ensuring it is called exactly
    once per distinct timeframe even when multiple features share it.
13. [ ] **Add** test `test_compute_features_supports_mixed_timeframes_and_sources`
    that mixes base timeframe features, higher timeframe ATR, and a feature using
    `source_ref`; assert all columns exist and retain monotonic indices.
14. [ ] **Modify** `src/trading_platform/strategy/features.py` to:
    - Group feature specs by `timeframe` (key `None` or base) before computation.
    - Maintain a cache `resampled_frames[timeframe]` so each higher timeframe is
      resampled only once.
    - For each higher timeframe group:
      1. Call `resample_data`.
      2. Compute indicators on the resampled frame.
      3. Forward-fill onto the base index using `.reindex(base.index, method="ffill")`.
    - Concatenate all resulting Series and join them to the original DataFrame.
15. [ ] **Run** `poetry run pytest tests/strategy/test_multi_timeframe_features.py`
    and confirm all Phase 2 tests pass with full coverage of modified paths.

## Phase 3 – Backtester and Brief Integration

16. [ ] **Update** `tests/backtester/test_contextual_features.py` by adding test
    `test_backtester_trade_context_with_multi_timeframe_feature` that:
    - Constructs deterministic OHLC data and a minimal strategy producing one
      trade.
    - Configures `RunConfig` with `contextual_features` containing
      `{"name": "h1_atr", "type": "ATR", "params": {"length": 14}, "timeframe": "1H"}`.
    - Runs the backtester and asserts:
      1. `trade.context_at_entry["h1_atr"]` matches manually calculated
         resampled ATR (reuse utility from Phase 1).
      2. The same value appears inside the generated `brief.json` under
         `context.strategy_features`.
17. [ ] **Add** test `test_backtester_brief_serializes_multi_timeframe_context`
    in the same file to ensure the enriched context survives serialization when
    multiple trades and features exist.
18. [ ] **Implement** any required adjustments in
    `src/trading_platform/backtester/core.py` (or related modules) to pass the
    above tests, ensuring multi-timeframe contextual features populate both trade
    objects and briefs without redundant recomputation.
19. [ ] **Run** `poetry run pytest tests/backtester/test_contextual_features.py`
    and confirm all Phase 3 tests pass.

## Phase 4 – Documentation and Final Verification

20. [ ] **Update** `docs/ai/05_ml_data_curation_guide.md` (Contextual Features
    section) and `docs/architecture.md` to reference the new `timeframe` field and
    resampling workflow.
21. [ ] **Run** `poetry run pytest --cov --cov-report=term-missing` to ensure
    100% coverage is maintained for all modified modules.
22. [ ] **Prepare** a short summary in `docs/CHANGELOG.md` under the “Unreleased”
    section describing the multi-timeframe contextual feature capability and new
    tests.
23. [ ] **Open** a PR following team guidelines, referencing this plan and
    attaching test results.

Completion requires every checkbox to be checked in order, verifying that tests
precede implementations, documentation is updated, and coverage remains at 100%.
