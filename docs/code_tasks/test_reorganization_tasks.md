# Test Suite Reorganization Tasks

This document tracks the effort to refactor and reorganize the test suite for better clarity and maintainability. The goal is to consolidate test files based on the component they test, rather than why the test was written (e.g., for coverage).

It is of vital importance that no test coverage gets lost in this process.  Migrate tests from one file to another as needed, but do not rewrite or delete any.  We must maintain 100% test coverage.

For each consolidation task, proceed as follows:
1. Concatenate the files inot the new single file specified in the instructions.
2. Clean up the new file - deduping imports, etc.
3. Delete the hold files.
4. Do not change any functionality.  This is purely a reorganization of tests into different files.


## Phase 1: File Consolidation

### `tests/execution`
- [x] Consolidate `test_controller_*` files into a single `test_controller.py`.
- [x] Consolidate `test_oanda_stub_*` files into a single `test_oanda_stub.py`.
- [x] Consolidate remaining `test_execution_*` files into `test_execution.py`.

### `tests/backtester`
- [x] Consolidate core backtester logic from `test_backtester_*` files into `test_backtester.py`.
- [x] Consolidate risk rule tests (`test_daily_loss_cap.py`, `test_exposure_curve.py`, etc.) into a new `test_risk_rules.py`.
- [x] Consolidate event-related tests (`test_blackout_events.py`, `test_blackout_windows.py`) into a new `test_events.py`.

### `tests/reporting`
- [x] Consolidate all `test_brief_*.py` files into `test_brief.py`.
- [x] Consolidate all `test_compare_*.py` files into `test_compare.py`.
- [x] Consolidate all `test_html_export_*.py` files into `test_html_export.py`.
- [x] Consolidate all cost-related reporting tests into `test_costs.py`.
- [x] Consolidate remaining export-related tests (`test_trades_csv_export.py`, etc.) into `test_exports.py`.

### `tests/core`
- [x] Consolidate `test_sweeps_*` and `test_parameter_sweep_*` files into `test_sweeps.py`.
- [x] Consolidate `test_run_*` and `test_finalize_run_*` files into `test_run.py`.
- [x] Consolidate `test_policy_branches_*` into `test_policy.py`.

### `tests/strategy`
- [x] Consolidate `test_base_strategy_*` files into `test_base_strategy.py`.
- [x] Consolidate `test_features_*` files into `test_features.py`.
- [x] Consolidate `test_yaml_strategy_*` files into `test_yaml_strategy.py`.

### `tests/ai`
- [ ] Consolidate `test_inference_client_*` files into `test_inference_client.py`.
- [ ] Consolidate `test_training_pipeline_*` files into `test_training_pipeline.py`.
- [ ] Review and consolidate other `*_coverage_gaps.py` files into their corresponding component test files.

### `tests/data`
- [ ] Consolidate `test_loader_*` files into `test_loader.py`.
- [ ] Consolidate `test_schema_*` files into `test_schema.py`.
- [ ] Consolidate `test_instrument_*` files into `test_instrument.py`.

### `tests/regime_market_manager`
- [ ] Consolidate `test_classification_*` files into `test_classification.py`.
- [ ] Consolidate `test_config_*` files into `test_config.py`.
- [ ] Consolidate `test_rmm_engine_*` files into `test_engine.py`.
