# Requirement to Test Mapping

**Auto-generated** - Do not edit manually
**Generated**: /Users/jbaird/Documents/personal/trading-platform

## Summary

- **Total Requirements Covered**: 75
- **Total Test Files**: 115

## Coverage by Category

- **SYS**: 14 requirements
- **DH**: 11 requirements
- **SE**: 6 requirements
- **RMM**: 3 requirements
- **PM**: 3 requirements
- **REM**: 2 requirements
- **BT**: 8 requirements
- **EL**: 7 requirements
- **AI**: 4 requirements
- **RV**: 6 requirements
- **JSON**: 10 requirements

---

## Detailed Mapping

### SYS Requirements

#### SYS-1.1.2

- [`tests/core/test_runconfig_symbol_requirement.py`](tests/core/test_runconfig_symbol_requirement.py)

#### SYS-1.10.2

- [`tests/test_core.py`](tests/test_core.py)
- [`tests/smoke/test_end_to_end_smoke.py`](tests/smoke/test_end_to_end_smoke.py)
- [`tests/docs/test_examples_exist.py`](tests/docs/test_examples_exist.py)

#### SYS-1.2.2

- [`tests/core/test_import_boundaries.py`](tests/core/test_import_boundaries.py)

#### SYS-1.2.3

- [`tests/core/test_imports_ok.py`](tests/core/test_imports_ok.py)

#### SYS-1.2.4

- [`tests/core/test_utils.py`](tests/core/test_utils.py)

#### SYS-1.3.1

- [`tests/portfolio/test_canonical_representation.py`](tests/portfolio/test_canonical_representation.py)

#### SYS-1.3.3

- [`tests/risk_manager/test_rem_translation.py`](tests/risk_manager/test_rem_translation.py)

#### SYS-1.4.1

- [`tests/cli/test_cli_compare_and_paths.py`](tests/cli/test_cli_compare_and_paths.py)

#### SYS-1.5.1

- [`tests/core/test_blackout_policy_in_brief.py`](tests/core/test_blackout_policy_in_brief.py)

#### SYS-1.5.2

- [`tests/core/test_calendar.py`](tests/core/test_calendar.py)

#### SYS-1.5.4

- [`tests/core/test_policy.py`](tests/core/test_policy.py)

#### SYS-1.7.2

- [`tests/core/test_cli_commands.py`](tests/core/test_cli_commands.py)
- [`tests/cli/test_cli_toy_data_path.py`](tests/cli/test_cli_toy_data_path.py)
- [`tests/cli/test_cli_more.py`](tests/cli/test_cli_more.py)
- [`tests/cli/test_cli_cover_else.py`](tests/cli/test_cli_cover_else.py)

#### SYS-1.7.3

- [`tests/core/test_run.py`](tests/core/test_run.py)

#### SYS-1.9.1

- [`tests/performance/test_performance_benchmarks.py`](tests/performance/test_performance_benchmarks.py)

### DH Requirements

#### DH-2.1

- [`tests/data/test_loader.py`](tests/data/test_loader.py)

#### DH-2.10

- [`tests/data/test_parquet_caching.py`](tests/data/test_parquet_caching.py)

#### DH-2.11

- [`tests/data/test_golden_datasets.py`](tests/data/test_golden_datasets.py)
- [`tests/strategy/test_features.py`](tests/strategy/test_features.py)
- [`tests/strategy/test_features.py`](tests/strategy/test_features.py)
- [`tests/strategy/test_feature_pipeline.py`](tests/strategy/test_feature_pipeline.py)
- [`tests/strategy/test_more_indicators.py`](tests/strategy/test_more_indicators.py)
- [`tests/strategy/test_hhv_llv_dc.py`](tests/strategy/test_hhv_llv_dc.py)

#### DH-2.13

- [`tests/data/test_golden_datasets.py`](tests/data/test_golden_datasets.py)

#### DH-2.14

- [`tests/data/test_dukascopy_sync_service.py`](tests/data/test_dukascopy_sync_service.py)

#### DH-2.2

- [`tests/data/test_oanda_connector.py`](tests/data/test_oanda_connector.py)

#### DH-2.3

- [`tests/data/test_schema.py`](tests/data/test_schema.py)
- [`tests/data/test_data_normalization.py`](tests/data/test_data_normalization.py)
- [`tests/backtester/test_input_validation.py`](tests/backtester/test_input_validation.py)

#### DH-2.5

- [`tests/data/test_golden_datasets.py`](tests/data/test_golden_datasets.py)
- [`tests/data/test_resample_ohlc.py`](tests/data/test_resample_ohlc.py)

#### DH-2.8

- [`tests/data/test_instrument.py`](tests/data/test_instrument.py)

#### DH-2.9

- [`tests/data/test_chunked_loading.py`](tests/data/test_chunked_loading.py)

#### DH-F.1

- [`tests/data/test_sync.py`](tests/data/test_sync.py)
- [`tests/data/test_sync_service.py`](tests/data/test_sync_service.py)

### SE Requirements

#### SE-3.2

- [`tests/strategy/test_base_strategy.py`](tests/strategy/test_base_strategy.py)

#### SE-3.3

- [`tests/strategy/test_strategy_purity.py`](tests/strategy/test_strategy_purity.py)

#### SE-3.4

- [`tests/strategy/test_exponential_moving_average.py`](tests/strategy/test_exponential_moving_average.py)
- [`tests/strategy/test_yaml_strategy.py`](tests/strategy/test_yaml_strategy.py)

#### SE-3.5.3

- [`tests/strategy/test_yaml_strategy.py`](tests/strategy/test_yaml_strategy.py)
- [`tests/strategy/test_yaml_engine_validation_paths.py`](tests/strategy/test_yaml_engine_validation_paths.py)

#### SE-3.6

- [`tests/strategy/test_features.py`](tests/strategy/test_features.py)
- [`tests/strategy/test_indicators_registry_present.py`](tests/strategy/test_indicators_registry_present.py)

#### SE-3.9

- [`tests/strategy/test_strategy_jsonschema.py`](tests/strategy/test_strategy_jsonschema.py)
- [`tests/strategy/test_strategy_schema_validation.py`](tests/strategy/test_strategy_schema_validation.py)

### RMM Requirements

#### RMM-4.1

- [`tests/regime_market_manager/test_classification.py`](tests/regime_market_manager/test_classification.py)

#### RMM-4.7

- [`tests/regime_market_manager/test_hysteresis.py`](tests/regime_market_manager/test_hysteresis.py)

#### RMM-4.9

- [`tests/regime_market_manager/test_rmm_schema_validation.py`](tests/regime_market_manager/test_rmm_schema_validation.py)
- [`tests/regime_market_manager/test_rmm_jsonschema.py`](tests/regime_market_manager/test_rmm_jsonschema.py)

### PM Requirements

#### PM-5.1

- [`tests/portfolio/test_portfolio.py`](tests/portfolio/test_portfolio.py)

#### PM-5.6

- [`tests/portfolio/test_portfolio_metrics.py`](tests/portfolio/test_portfolio_metrics.py)
- [`tests/portfolio/test_cost_integration.py`](tests/portfolio/test_cost_integration.py)
- [`tests/portfolio/test_r_multiple.py`](tests/portfolio/test_r_multiple.py)

#### PM-5.8.1

- [`tests/portfolio/test_entry_window_management.py`](tests/portfolio/test_entry_window_management.py)

### REM Requirements

#### REM-6.1

- [`tests/risk_manager/test_rem.py`](tests/risk_manager/test_rem.py)
- [`tests/risk_manager/test_rem.py`](tests/risk_manager/test_rem.py)

#### REM-6.2

- [`tests/risk_manager/test_rem_schema.py`](tests/risk_manager/test_rem_schema.py)

### BT Requirements

#### BT-7.1

- [`tests/backtester/test_backtester.py`](tests/backtester/test_backtester.py)
- [`tests/step_defs/backtester/test_core_backtest_steps.py`](tests/step_defs/backtester/test_core_backtest_steps.py)

#### BT-7.10

- [`tests/backtester/test_return_skips_only.py`](tests/backtester/test_return_skips_only.py)
- [`tests/backtester/test_skipped_logging.py`](tests/backtester/test_skipped_logging.py)

#### BT-7.11

- [`tests/backtester/test_counterfactual_skips.py`](tests/backtester/test_counterfactual_skips.py)

#### BT-7.16

- [`tests/step_defs/backtester/test_risk_management_steps.py`](tests/step_defs/backtester/test_risk_management_steps.py)

#### BT-7.4

- [`tests/core/test_cost_model.py`](tests/core/test_cost_model.py)

#### BT-7.6

- [`tests/backtester/test_tie_break_policy.py`](tests/backtester/test_tie_break_policy.py)

#### BT-7.7

- [`tests/core/test_runconfig_warmup.py`](tests/core/test_runconfig_warmup.py)
- [`tests/backtester/test_warmup_guards.py`](tests/backtester/test_warmup_guards.py)

#### BT-7.8

- [`tests/core/test_precision.py`](tests/core/test_precision.py)

### EL Requirements

#### EL-8.10

- [`tests/execution/test_policy_integration_basic.py`](tests/execution/test_policy_integration_basic.py)
- [`tests/execution/test_adapter_policy_blackout.py`](tests/execution/test_adapter_policy_blackout.py)

#### EL-8.2

- [`tests/execution/test_oanda_stub.py`](tests/execution/test_oanda_stub.py)

#### EL-8.4

- [`tests/execution/test_connectivity_retries.py`](tests/execution/test_connectivity_retries.py)

#### EL-8.5

- [`tests/execution/test_live_controller.py`](tests/execution/test_live_controller.py)

#### EL-8.6

- [`tests/execution/test_live_stream.py`](tests/execution/test_live_stream.py)

#### EL-8.7

- [`tests/execution/test_structured_logging.py`](tests/execution/test_structured_logging.py)

#### EL-8.9

- [`tests/execution/test_oanda_position_cap.py`](tests/execution/test_oanda_position_cap.py)
- [`tests/execution/test_oanda_daily_loss_cap.py`](tests/execution/test_oanda_daily_loss_cap.py)

### AI Requirements

#### AI-10.1

- [`tests/cli/test_cli_ai_diagnose.py`](tests/cli/test_cli_ai_diagnose.py)

#### AI-10.2

- [`tests/ai/synthesis/test_recommendations.py`](tests/ai/synthesis/test_recommendations.py)

#### AI-10.6.1

- [`tests/ai/synthesis/test_engine.py`](tests/ai/synthesis/test_engine.py)

#### AI-F.2.1

- [`tests/core/test_monte_carlo_wfe_paramsearch.py`](tests/core/test_monte_carlo_wfe_paramsearch.py)
- [`tests/core/test_robustness_more.py`](tests/core/test_robustness_more.py)

### RV Requirements

#### RV-9.1

- [`tests/reporting/test_save_run_brief.py`](tests/reporting/test_save_run_brief.py)
- [`tests/reporting/test_brief.py`](tests/reporting/test_brief.py)
- [`tests/core/test_run.py`](tests/core/test_run.py)

#### RV-9.2

- [`tests/reporting/test_compare.py`](tests/reporting/test_compare.py)

#### RV-9.3

- [`tests/reporting/test_html_multisymbol_legend.py`](tests/reporting/test_html_multisymbol_legend.py)
- [`tests/reporting/test_html_overlays_section.py`](tests/reporting/test_html_overlays_section.py)
- [`tests/reporting/test_html_sparkline.py`](tests/reporting/test_html_sparkline.py)

#### RV-9.4

- [`tests/reporting/test_exports.py`](tests/reporting/test_exports.py)
- [`tests/reporting/test_html_export.py`](tests/reporting/test_html_export.py)
- [`tests/reporting/test_finalize_saves_trades_csv.py`](tests/reporting/test_finalize_saves_trades_csv.py)
- [`tests/cli/test_cli_open_chart.py`](tests/cli/test_cli_open_chart.py)

#### RV-9.6

- [`tests/reporting/test_field_definitions.py`](tests/reporting/test_field_definitions.py)
- [`tests/reporting/test_field_definitions_coverage.py`](tests/reporting/test_field_definitions_coverage.py)

#### RV-9.7

- [`tests/reporting/test_trade_context_snapshots.py`](tests/reporting/test_trade_context_snapshots.py)

### JSON Requirements

#### JSON-11.12

- [`tests/reporting/test_costs.py`](tests/reporting/test_costs.py)

#### JSON-11.13

- [`tests/reporting/test_exposure_metrics.py`](tests/reporting/test_exposure_metrics.py)

#### JSON-11.17

- [`tests/reporting/test_data_quality.py`](tests/reporting/test_data_quality.py)

#### JSON-11.18

- [`tests/core/test_run.py`](tests/core/test_run.py)

#### JSON-11.22

- [`tests/reporting/test_provenance_env.py`](tests/reporting/test_provenance_env.py)

#### JSON-11.24

- [`tests/reporting/test_config_snapshot_stability.py`](tests/reporting/test_config_snapshot_stability.py)
- [`tests/reporting/test_provenance_checksums.py`](tests/reporting/test_provenance_checksums.py)

#### JSON-11.25

- [`tests/reporting/test_r_multiple_serialization.py`](tests/reporting/test_r_multiple_serialization.py)
- [`tests/reporting/test_mfe_mae_serialization.py`](tests/reporting/test_mfe_mae_serialization.py)
- [`tests/portfolio/test_mfe_mae_bars.py`](tests/portfolio/test_mfe_mae_bars.py)

#### JSON-11.26

- [`tests/reporting/test_skips_in_brief.py`](tests/reporting/test_skips_in_brief.py)

#### JSON-11.5

- [`tests/reporting/test_analytics.py`](tests/reporting/test_analytics.py)

#### JSON-F.1

- [`tests/reporting/test_mc_wf_placeholders.py`](tests/reporting/test_mc_wf_placeholders.py)
- [`tests/core/test_run.py`](tests/core/test_run.py)
