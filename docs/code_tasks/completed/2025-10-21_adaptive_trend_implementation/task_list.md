# Adaptive Trend Enhancements Implementation Plan (Revised)

This document provides a detailed, step-by-step plan for implementing the adaptive trend enhancements. All tasks must be completed in the specified order.

**Branch:** `feature/adaptive-trend-enhancements` (created from `dev`)

**Final Status: 37 of 37 tasks completed (100%)** 🎉
- ✅ Epic 1: Signal Confirmation Enhancements (Tasks 1-11) - COMPLETE
- ✅ Epic 2: Exit & Risk Model Adaptation (Tasks 12-21) - COMPLETE
- ✅ Epic 3: Regime Feature Expansion (Tasks 22-29) - COMPLETE
- ✅ Epic 4: Diagnostics & Data Plumbing (Tasks 30-36) - COMPLETE
- ✅ Epic 5: Performance Validation (Task 37) - COMPLETE

---

## Epic 1: Signal Confirmation Enhancements

### Feature 1.1: Extend Indicator Registry

1.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_load_strategy_with_new_indicators` to load a YAML with `ema_slope`, `rsi`, and `roc` features and assert it parses correctly.
2.  **[X] IMPLEMENT:** In `src/trading_platform/strategy/indicators_registry.py`, add `ema_slope`, `rsi`, and `roc` to the `INDICATORS` dictionary **and** implement the corresponding computation helpers in `src/trading_platform/strategy/features.py`.
3.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_new_indicator_schema_validation` to validate a strategy YAML with the new indicators via the `StrategyConfig` Pydantic model. Include targeted tests in `tests/strategy/test_features.py` (or equivalent) for the `ema_slope`, `rsi`, and `roc` computations.
4.  **[X] IMPLEMENT:** Add the new indicators to `INDICATORS` in `src/trading_platform/strategy/indicators_registry.py` (validation now reads directly from the registry).

### Feature 1.2: Add New Strategy Predicates

5.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_predicate_slope_is_above` using a `YamlStrategy` with the rule `{ feature: "ema_slope_14", predicate: "slope_is_above", value: 0.5 }` and assert it generates the correct command.
6.  **[X] IMPLEMENT:** In `src/trading_platform/strategy/yaml_strategy.py`, add logic for the `slope_is_above` predicate.
7.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add a test to validate that `slope_is_above` and `roc_is_above` are accepted by `StrategyConfig`.
8.  **[X] IMPLEMENT:** Extend predicate handling in `src/trading_platform/strategy/models.py` / `yaml_strategy.py` to recognise `slope_is_above` and `roc_is_above`.
9.  **[X] IMPLEMENT:** In `src/trading_platform/strategy/yaml_strategy.py`, add logic for the `roc_is_above` predicate.

### Feature 1.3: Add Higher-Timeframe Feature Support

10. **[X] TEST:** Create `tests/data/test_data_handler_multi_timeframe.py`. Add `test_get_higher_timeframe_feature` that requests a 15min DataFrame and a feature like `adx_1h` and asserts the new column is correctly resampled and forward-filled.
11. **[X] IMPLEMENT:** In `src/trading_platform/strategy/features.py`, modify `compute_features` to detect if `spec['timeframe']` is present. If so, resample `df` to that TF, compute the feature, then `reindex` + `ffill` to the original bars.

---

## Epic 2: Exit & Risk Model Adaptation

### Feature 2.1: Implement Dynamic REM Module

12. **[X] TEST:** Create `tests/risk_manager/test_dynamic_rem.py`. Add `test_breakeven_trigger` to simulate a trade reaching +0.75R and assert the REM updates the stop-loss to the entry price.
13. **[X] IMPLEMENT:** Create `src/trading_platform/risk_manager/dynamic_rem.py`. Implement a `DynamicREM` class. Add logic to check `trade.get_current_r_multiple()` and adjust `trade.stop_loss` if a `breakeven_threshold` is crossed.
14. **[X] TEST:** In `test_dynamic_rem.py`, add `test_partial_profit_trigger` to simulate a trade hitting a profit target and assert the REM generates an order to close half the position.
15. **[X] IMPLEMENT:** In `dynamic_rem.py`, add logic to handle partial profit-taking, yielding an `Order` to reduce position size.
16. **[X] TEST:** In `test_dynamic_rem.py`, add `test_atr_trailing_stop_after_partial_exit`. After a partial exit, assert that the stop-loss for the remaining position begins trailing at the specified ATR multiple.
17. **[X] IMPLEMENT:** In `dynamic_rem.py`, add the ATR-based trailing stop logic that activates for the remainder of the position after a partial exit occurs.
18. **[X] TEST:** Create a schema `docs/schemas/rem_dynamic.schema.json` and a test to validate a full configuration for the `DynamicREM` against it.
19. **[X] IMPLEMENT:** Update the REM factory in `src/trading_platform/risk_manager/__init__.py` to instantiate `DynamicREM`, and ensure the new schema is wired into the existing REM validation flow so misconfigurations fail fast.

### Feature 2.2: Implement Volatility-Aware Trailing

20. **[X] TEST:** In `test_dynamic_rem.py`, add `test_stop_tightens_on_falling_adx`. Simulate an open position where the `adx` value (passed in context) falls below a threshold, and assert that the REM tightens the trailing stop distance.
21. **[X] IMPLEMENT:** In `dynamic_rem.py`, modify `manage_position` to accept `context`. Add logic to adjust the trailing stop multiple if `context['adx']` drops below a configured `volatility_threshold`.

---

## Epic 3: Regime Feature Expansion

### Feature 3.1: Add New RMM Features

22. **[X] TEST:** In `tests/regime_market_manager/test_engine.py`, add tests for new feature calculations: `test_calculates_atr_percentile`, `test_calculates_realized_volatility`, and `test_calculates_volume_zscore`.
23. **[X] IMPLEMENT:** In `src/trading_platform/strategy/features.py`, implement the logic for `atr_percentile`, `realized_volatility`, and `volume_zscore` and integrate into `compute_features`.
24. **[X] TEST:** Update the `rmm.schema.json` validation test to ensure the new feature names are valid.
25. **[X] IMPLEMENT:** In `docs/schemas/rmm.schema.json`, add the new feature names (`ATRPercentile`, `RealizedVolatility`, `VolumeZScore`) to the list of allowed features.

### Feature 3.2: Add New RMM Predicates

26. **[X] TEST:** In `tests/regime_market_manager/test_engine.py`, add tests for new predicates: `test_predicate_percentile_is_above` and `test_predicate_volatility_is_between`.
27. **[X] IMPLEMENT:** In `src/trading_platform/regime_market_manager/engine.py`, implement the `percentile_is_above` and `volatility_is_between` predicates in `_eval_pred`.
28. **[X] TEST:** Update the `rmm.schema.json` validation test to ensure the new predicate names are valid enums.
29. **[X] IMPLEMENT:** In `docs/schemas/rmm.schema.json`, add the new predicate names (`percentile_is_above`, `volatility_is_between`) to the `predicate` enum definition.

---

## Epic 4: Diagnostics & Data Plumbing

### Feature 4.1: Log All New Contextual Features

30. **[X] TEST:** Created comprehensive tests in tests/reporting/test_context_in_outputs.py verifying that new Epic 1 features (ema_slope_fast, adx_4h) and Epic 3 features (atr_pct, rvol, vol_z) appear correctly in both brief.json and trades.csv outputs. All 3 tests passing.
31. **[X] IMPLEMENT:** Updated save_trades_csv() in reporting/csv_export.py to flatten context_at_entry into columns with 'ctx_' prefix. Added _flatten_context_keys() and _flatten_context() helper functions. CSV now dynamically includes all context fields (e.g., ctx_strategy_features_ema_slope_fast, ctx_regime_atr_pct).
32. **[X] IMPLEMENT:** Verified context serialization in brief.json works correctly via _serialize_trade(). Context appears in trades array with nested structure preserved (strategy_features and regime subsections).

### Feature 4.2: Integrate Dynamic REM Metrics into Brief

33. **[X] TEST:** Created `test_brief_contains_dynamic_rem_metrics` and `test_brief_dynamic_rem_metrics_defaults_to_empty` in tests/reporting/test_brief.py. Tests verify dynamic_rem_metrics section in brief.json with breakeven_triggers, partial_exits_triggered, trailing_stop_activations, and volatility_tightenings.
34. **[X] IMPLEMENT:** Added statistics tracking to DynamicREM class with self.stats dict tracking all four metric types. Added tracking at each trigger point: breakeven, partial exits, trailing stops, and volatility tightenings. Added get_stats() method to retrieve metrics.
35. **[X] IMPLEMENT:** Added dynamic_rem_metrics parameter to generate_brief() function and included in base brief dict (reporting/brief.py:682,851). Updated docs/schemas/brief.schema.json with dynamic_rem_metrics section containing all four metric fields with descriptions.

### Feature 4.3: Final Integration Test

36. **[X] TEST:** Created `tests/integration/test_adaptive_trend_full.py`. This test validates all adaptive trend features work together: EMASlope with slope predicates, higher-timeframe features, DynamicREM, and new RMM features/predicates. All epics integrated successfully.

---

## Epic 5: Performance Validation

### Feature 5.1: Profile New Features

37. **[X] BENCHMARK:** Run the integration test from task #36 under a profiler (e.g., `cProfile`). Document the runtime cost of the new features, particularly the multi-timeframe data handling. If any single feature adds more than 20% to the total runtime, flag it for optimization.


    **Implementation Notes:**
    - Created tests/performance/test_adaptive_trend_performance.py with cProfile-based performance tests
    - Profiled on 1000-bar test dataset
    - **⚠️ PERFORMANCE FLAGS RAISED:**
      - **Epic 1 (Strategy Features + Higher-Timeframe):** 0.37s (70% of total time) - **EXCEEDS 20% THRESHOLD**
      - **Epic 3 (RMM Features):** 0.16s (30% of total time) - **EXCEEDS 20% THRESHOLD**
      - Combined total: 0.53s
      - DynamicREM instantiation overhead: negligible (<0.001ms)
    - **Architect Review Required:** Both Epic 1 and Epic 3 exceed the 20% threshold and should be flagged for optimization consideration
