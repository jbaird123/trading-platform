# Adaptive Trend Enhancements Implementation Plan (Revised)

This document provides a detailed, step-by-step plan for implementing the adaptive trend enhancements. All tasks must be completed in the specified order.

**Branch:** Before starting, create a new feature branch from the `main` branch:
`git checkout -b feature/adaptive-trend-enhancements`

---

## Epic 1: Signal Confirmation Enhancements

### Feature 1.1: Extend Indicator Registry

1.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_load_strategy_with_new_indicators` to load a YAML with `ema_slope`, `rsi`, and `roc` features and assert it parses correctly.
2.  **[X] IMPLEMENT:** In `src/trading_platform/strategy/indicators_registry.py`, add `ema_slope`, `rsi`, and `roc` to the `INDICATORS` dictionary **and** implement the corresponding computation helpers in `src/trading_platform/strategy/features.py`.
3.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_new_indicator_schema_validation` to validate a strategy YAML with the new indicators against `docs/schemas/strategy.schema.json`. Include targeted tests in `tests/strategy/test_features.py` (or equivalent) for the `ema_slope`, `rsi`, and `roc` computations.
4.  **[X] IMPLEMENT:** In `docs/schemas/strategy.schema.json`, update the indicator definitions to include `ema_slope`, `rsi`, and `roc` and their parameters.

### Feature 1.2: Add New Strategy Predicates

5.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add `test_predicate_slope_is_above` using a `YamlStrategy` with the rule `{ feature: "ema_slope_14", predicate: "slope_is_above", value: 0.5 }` and assert it generates the correct command.
6.  **[X] IMPLEMENT:** In `src/trading_platform/strategy/yaml_strategy.py`, add logic for the `slope_is_above` predicate.
7.  **[X] TEST:** In `tests/strategy/test_yaml_strategy.py`, add a test to validate that `slope_is_above` and `roc_is_above` are valid predicate enums in `docs/schemas/strategy.schema.json`.
8.  **[X] IMPLEMENT:** In `docs/schemas/strategy.schema.json`, add `slope_is_above` and `roc_is_above` to the `definitions/predicate` enum.
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

22. **[DEFERRED] TEST:** In `tests/regime_market_manager/test_rmm_engine.py`, add tests for new feature calculations: `test_calculates_atr_percentile`, `test_calculates_realized_volatility`, and `test_calculates_volume_zscore`. (Skeleton added)
23. **[DEFERRED] IMPLEMENT:** In `src/trading_platform/regime_market_manager/rmm_engine.py`, implement the logic for `atr_percentile`, `realized_volatility`, and `volume_zscore` within `compute_features`.
24. **[DEFERRED] TEST:** Update the `rmm.schema.json` validation test to ensure the new feature names are valid.
25. **[DEFERRED] IMPLEMENT:** In `docs/schemas/rmm.schema.json`, add the new feature names to the list of allowed features.

### Feature 3.2: Add New RMM Predicates

26. **[DEFERRED] TEST:** In `tests/regime_market_manager/test_rmm_engine.py`, add tests for new predicates: `test_predicate_percentile_is_above` and `test_predicate_volatility_is_between`.
27. **[DEFERRED] IMPLEMENT:** In the RMM evaluation logic, implement the `percentile_is_above` and `volatility_is_between` predicates.
28. **[DEFERRED] TEST:** Update the `rmm.schema.json` validation test to ensure the new predicate names are valid enums.
29. **[DEFERRED] IMPLEMENT:** In `docs/schemas/rmm.schema.json`, add the new predicate names to the `predicate` enum definition.

---

## Epic 4: Diagnostics & Data Plumbing

### Feature 4.1: Log All New Contextual Features

30. **[ ] TEST:** In `tests/reporting/test_brief.py`, add `test_trade_context_includes_all_new_features`. Run a backtest using a strategy with the new signal and RMM features. Assert that the `entry_context` in `brief.json` contains values for `ema_slope`, `adx_1h`, and `atr_percentile`.
31. **[ ] IMPLEMENT:** In the `Backtester`, ensure all strategy and RMM features are captured on the `Trade` object's `entry_context`.
32. **[ ] IMPLEMENT:** In the `Reporting` module, update serialization logic to include all `entry_context` items in both `brief.json` and `trades.csv`.

### Feature 4.2: Integrate Dynamic REM Metrics into Brief

33. **[ ] TEST:** In `tests/reporting/test_brief.py`, add `test_brief_contains_dynamic_rem_metrics`. Run a backtest with the `DynamicREM`. Assert that `brief.json` contains a `dynamic_rem_metrics` section with fields like `partial_exit_pnl_contribution` and `breakeven_saves`.
34. **[ ] IMPLEMENT:** In `DynamicREM` and/or `PortfolioManager`, collect statistics on partial exits and break-even moves. Store these on a results object.
35. **[ ] IMPLEMENT:** In the `Reporting` module, add the new `dynamic_rem_metrics` section to the `brief.json` output, populated from the backtest results.

### Feature 4.3: Final Integration Test

36. **[ ] TEST:** Create `tests/integration/test_adaptive_trend_full.py`. This test will configure and run a backtest using a strategy that combines: a higher-timeframe feature (`adx_1h`), a new predicate (`slope_is_above`), the `DynamicREM` with volatility awareness, and a new RMM filter (`atr_percentile`). Assert that the backtest completes successfully and produces a valid `brief.json` with all the new sections.

---

## Epic 5: Performance Validation

### Feature 5.1: Profile New Features

37. **[ ] BENCHMARK:** Run the integration test from task #36 under a profiler (e.g., `cProfile`). Document the runtime cost of the new features, particularly the multi-timeframe data handling. If any single feature adds more than 20% to the total runtime, flag it for optimization.
