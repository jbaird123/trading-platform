# Gemini Requirements Check

_Last updated: 2025-09-18_

This document tracks the alignment between the project requirements and the test suite.

## 1) System-Wide Requirements

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[SYS-1.1.1]** | Partially Covered | `tools/check_import_boundaries.py` | Modular separation is a core principle, enforced by import boundary checks. Direct tests for this are not typical. |
| **[SYS-1.1.2]** | Not Covered | - | No specific tests for Run Configuration binding. |
| **[SYS-1.2.1]** | Not Covered | - | No specific tests for public API enforcement. |
| **[SYS-1.2.2]** | Partially Covered | `tools/check_import_boundaries.py` | Enforced by the `check_import_boundaries.py` script, not a direct test. |
| **[SYS-1.2.3]** | **Covered** | `tests/core/test_imports_ok.py` |  |
| **[SYS-1.2.4]** | **Covered** | `tests/core/test_utils.py` |  |
| **[SYS-1.3.1]** | Not Covered | - | No specific tests for canonical representation enforcement in the Portfolio Manager. |
| **[SYS-1.3.2]** | **Covered** | `tests/backtester/test_instrument_arg.py` |  |
| **[SYS-1.3.3]** | Not Covered | - | No specific tests for native-to-canonical translation. |
| **[SYS-1.3.4]** | Not Covered | - | No specific tests for base currency PnL calculations. |
| **[SYS-1.4.1]** | **Covered** | `tests/cli/test_cli_compare_and_paths.py` |  |
| **[SYS-1.4.2]** | Not Covered | - | No specific tests for comparing variations. |
| **[SYS-1.4.3]** | Not Covered | - | No specific tests for the comparative format. |
| **[SYS-1.5.1]** | **Covered** | `tests/backtester/test_blackout_windows.py`, `tests/core/test_blackout_policy_in_brief.py` |  |
| **[SYS-1.5.2]** | **Covered** | `tests/backtester/test_blackout_events.py`, `tests/core/test_calendar.py` |  |
| **[SYS-1.5.3]** | Not Covered | - | No specific tests for central management of blackouts. |
| **[SYS-1.5.4]** | **Covered** | `tests/core/test_policy_branches.py`, `tests/core/test_policy_branches_extra.py`, `tests/execution/test_adapter_policy_blackout.py` |  |
| **[SYS-1.6.1]** | Not Covered | - | No tests for containerization. |
| **[SYS-1.6.2]** | **Covered** | `.github/workflows/ci.yml` | CI pipeline is configured. |
| **[SYS-1.6.3]** | **Covered** | `pyproject.toml`, `poetry.lock` | Dependency management is in place. |
| **[SYS-1.7.1]** | **Covered** | `tests/core/test_finalize_run.py` |  |
| **[SYS-1.7.2]** | **Covered** | `tests/cli/test_cli_compare_and_paths.py`, `tests/cli/test_cli_cover_else.py`, `tests/cli/test_cli_more.py`, `tests/cli/test_cli_toy_data_path.py`, `tests/core/test_cli_commands.py` |  |
| **[SYS-1.7.3]** | Not Covered | - | No specific tests for the Run Configuration Schema. |
| **[SYS-1.7.4]** | Not Covered | - | No specific tests for AI interpretability/traceability. |
| **[SYS-1.8.1]** | N/A | - | Not a testable requirement. |
| **[SYS-1.8.2]** | N/A | - | Not a testable requirement. |
| **[SYS-1.8.3]** | Not Covered | - | No specific tests for UTC timestamp handling. |
| **[SYS-1.9.1]** | N/A | - | Not a testable requirement. |
| **[SYS-1.9.2]** | N/A | - | Not a testable requirement. |
| **[SYS-1.10.1]**| N/A | - | Process requirement, not testable. |
| **[SYS-1.10.2]**| **Covered** | `tests/docs/test_examples_exist.py`, `tests/smoke/test_end_to_end_smoke.py` | Meta-requirement, covered by the existence of a comprehensive test suite. |
| **[SYS-1.10.3]**| **Covered** | `tests/features/` | BDD feature files exist. |
| **[SYS-1.11.1]**| **Covered** | `sonar-project.properties` | SonarQube is configured. |
| **[SYS-1.11.2]**| N/A | - | Not a testable requirement. |
| **[SYS-1.11.3]**| **Covered** | `.pre-commit-config.yaml` | Pre-commit hooks are configured. |
| **[SYS-1.12.1]**| N/A | - | Not a testable requirement. |
| **[SYS-1.12.2]**| N/A | - | Not a testable requirement. |
| **[SYS-1.13.1]**| N/A | - | Not a testable requirement. |
| **[SYS-1.13.2]**| N/A | - | Not a testable requirement. |
| **[SYS-1.13.3]**| Not Covered | - | No specific tests for input validation to prevent injection. |

## 2) Data Handler (DH)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[DH-2.1]** | Not Covered | - | No specific tests for loading from local CSVs. |
| **[DH-2.2]** | Not Covered | - | No specific tests for OANDA live streaming. |
| **[DH-2.3]** | **Covered** | `tests/backtester/test_input_validation.py`, `tests/data/test_schema_errors.py` |  |
| **[DH-2.4]** | Not Covered | - | No specific tests for timezone-aware UTC timestamps. |
| **[DH-2.5]** | **Covered** | `tests/data/test_resample_ohlc.py` |  |
| **[DH-2.6]** | **Covered** | `tests/backtester/test_input_validation.py`, `tests/data/test_schema_errors.py` |  |
| **[DH-2.7]** | Not Covered | - | No specific tests for `quality_flags` report. |
| **[DH-2.8]** | Not Covered | - | No specific tests for the Instrument Definition. |
| **[DH-2.9]** | Not Covered | - | No specific tests for chunked loading. |
| **[DH-2.10]** | Not Covered | - | No specific tests for caching. |
| **[DH-2.11]** | **Covered** | `tests/strategy/test_feature_pipeline.py`, `tests/strategy/test_features_more_paths.py`, `tests/strategy/test_features_price_sources.py`, `tests/strategy/test_hhv_llv_dc.py`, `tests/strategy/test_more_indicators.py` |  |
| **[DH-2.12]** | Not Covered | - | No specific tests for the `DataRequest` interface. |
| **[DH-2.13]** | Not Covered | - | No specific tests using golden dataset fixtures. |

## 3) Strategy Engine (SE)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[SE-3.1]** | Not Covered | - | No specific tests for signal generation only mandate. |
| **[SE-3.2]** | Not Covered | - | No specific tests for the `BaseStrategy` interface. |
| **[SE-3.3]** | Not Covered | - | No specific tests to prevent trade management logic in strategies. |
| **[SE-3.4]** | **Covered** | `tests/strategy/test_exponential_moving_average.py` |  |
| **[SE-3.5.1]** | **Covered** | `tests/strategy/test_yaml_strategy_parser.py` | Covered by tests for YAML parsing. |
| **[SE-3.5.2]** | Not Covered | - | No specific tests for the YAML schema rules. |
| **[SE-3.5.3]** | **Covered** | `tests/strategy/test_yaml_engine_validation_paths.py`, `tests/strategy/test_yaml_strategy_parser.py` |  |
| **[SE-3.6]** | **Covered** | `tests/strategy/test_indicators_registry_present.py` |  |
| **[SE-3.7]** | Not Covered | - | No specific tests for overlay metadata declaration. |
| **[SE-3.9]** | **Covered** | `tests/strategy/test_strategy_jsonschema.py`, `tests/strategy/test_strategy_schema_validation.py` |  |

## 4) Regime Market Manager (RMM)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[RMM-4.1]** | **Covered** | `tests/regime_market_manager/test_classification_unit.py` |  |
| **[RMM-4.2]** | Not Covered | - | No specific tests for confidence score output. |
| **[RMM-4.3]** | **Covered** | `tests/regime_market_manager/test_classification_unit.py` |  |
| **[RMM-4.6]** | Not Covered | - | No specific tests for the `is_trade_allowed` policy function. |
| **[RMM-4.7]** | Not Covered | - | No specific tests for configurable policies and hysteresis. |
| **[RMM-4.8]** | Not Covered | - | No specific tests using synthetic data sequences. |
| **[RMM-4.9]** | **Covered** | `tests/regime_market_manager/test_config_errors.py`, `tests/regime_market_manager/test_config_valid_any_of.py`, `tests/regime_market_manager/test_rmm_jsonschema.py`, `tests/regime_market_manager/test_rmm_schema_validation.py` |  |

## 5) Portfolio Manager (PM)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[PM-5.1]** | **Covered** | `tests/portfolio/test_portfolio.py` |  |
| **[PM-5.2]** | **Covered** | `tests/portfolio/test_portfolio.py` |  |
| **[PM-5.3]** | **Covered** | `tests/portfolio/test_portfolio.py` |  |
| **[PM-5.4]** | **Covered** | `tests/portfolio/test_portfolio.py` |  |
| **[PM-5.5]** | **Covered** | `tests/portfolio/test_portfolio.py` |  |
| **[PM-5.6]** | **Covered** | `tests/portfolio/test_cost_integration.py`, `tests/portfolio/test_metrics.py`, `tests/portfolio/test_portfolio.py`, `tests/portfolio/test_r_multiple.py` |  |
| **[PM-5.7]** | **Covered** | `tests/backtester/test_daily_loss_cap.py`, `tests/backtester/test_pm_limits_branches.py`, `tests/backtester/test_position_cap_same_direction.py` |  |

## 6) Risk & Exit Manager (REM)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[REM-6.1]** | Not Covered | - | No tests found for REM requirements. |
| **[REM-6.2]** | Not Covered | - | No tests found for REM requirements. |
| **[REM-6.3]** | Not Covered | - | No tests found for REM requirements. |
| **[REM-6.4]** | Not Covered | - | No tests found for REM requirements. |

## 7) Backtester (BT)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[BT-7.1]** | **Covered** | `tests/step_defs/backtester/test_core_backtest_steps.py` |  |
| **[BT-7.2]** | Not Covered | - | No specific tests for rule translation. |
| **[BT-7.3]** | Not Covered | - | No specific tests for the iterative bar-by-bar loop. |
| **[BT-7.4]** | **Covered** | `tests/portfolio/test_cost_integration.py`, `tests/core/test_cost_model.py` |  |
| **[BT-7.5]** | Not Covered | - | No specific tests for multiple order types. |
| **[BT-7.6]** | **Covered** | `tests/backtester/test_tie_break_policy.py` |  |
| **[BT-7.7]** | **Covered** | `tests/backtester/test_warmup_bars.py`, `tests/core/test_runconfig_warmup.py` |  |
| **[BT-7.8]** | **Covered** | `tests/core/test_precision.py` |  |
| **[BT-7.9]** | Not Covered | - | No specific tests for fill logic and stop/TP precedence. |
| **[BT-7.10]** | **Covered** | `tests/backtester/test_return_skips_only.py`, `tests/backtester/test_skipped_logging.py` |  |
| **[BT-7.11]** | **Covered** | `tests/backtester/test_counterfactual_skips.py` |  |
| **[BT-7.12]** | Not Covered | - | No specific tests for filter impact summary. |
| **[BT-7.13]** | Not Covered | - | No specific tests for live trading deviation. |
| **[BT-7.16]** | **Covered** | `tests/step_defs/backtester/test_risk_management_steps.py` |  |

## 8) Execution Layer (EL)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[EL-8.1]** | Not Covered | - | No specific tests for rule translation in EL. |
| **[EL-8.2]** | **Covered** | `tests/execution/test_oanda_stub.py`, `tests/execution/test_oanda_stub_more.py` |  |
| **[EL-8.3]** | **Covered** | `tests/execution/test_oanda_stub.py`, `tests/execution/test_oanda_stub_more.py` |  |
| **[EL-8.4]** | Not Covered | - | No specific tests for API connectivity issues. |
| **[EL-8.5]** | **Covered** | `tests/execution/test_controller_flat_continue.py`, `tests/execution/test_live_controller.py` |  |
| **[EL-8.6]** | Not Covered | - | No specific tests for handling live data streams. |
| **[EL-8.7]** | **Covered** | `tests/execution/test_controller_flat_continue.py`, `tests/execution/test_live_controller.py` |  |
| **[EL-8.8]** | **Covered** | `tests/execution/test_controller_error_severity.py`, `tests/execution/test_controller_reconcile_variants.py`, `tests/execution/test_controller_short_equity_and_reconcile.py`, `tests/execution/test_live_controller.py` |  |
| **[EL-8.9]** | **Covered** | `tests/execution/test_oanda_daily_loss_cap.py`, `tests/execution/test_oanda_position_cap.py` |  |
| **[EL-8.10]** | **Covered** | `tests/execution/test_adapter_policy_blackout.py`, `tests/execution/test_policy_integration_basic.py` |  |

## 9) Reporting & Visualization (RV)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[RV-9.1]** | **Covered** | `tests/core/test_cli_commands.py`, `tests/core/test_finalize_run.py`, `tests/reporting/test_brief.py`, `tests/reporting/test_brief_edge_cases.py`, `tests/reporting/test_save_run_brief.py` |  |
| **[RV-9.2]** | **Covered** | `tests/reporting/test_compare_briefs.py`, `tests/reporting/test_compare_defaults.py`, `tests/reporting/test_compare_non_numeric.py` |  |
| **[RV-9.3]** | **Covered** | `tests/reporting/test_html_multisymbol_legend.py`, `tests/reporting/test_html_overlays_section.py`, `tests/reporting/test_html_sparkline.py` |  |
| **[RV-9.4]** | **Covered** | `tests/reporting/test_compare_html.py`, `tests/reporting/test_compare_html_enhanced.py`, `tests/reporting/test_compare_report_io.py`, `tests/reporting/test_finalize_saves_trades_csv.py`, `tests/reporting/test_html_export.py`, `tests/reporting/test_html_export_edges.py`, `tests/reporting/test_html_export_variants.py`, `tests/reporting/test_trades_csv_export.py` |  |
| **[RV-9.6]** | **Covered** | `tests/reporting/test_field_definitions.py`, `tests/reporting/test_field_definitions_coverage.py` |  |
| **[RV-9.7]** | **Covered** | `tests/reporting/test_trade_context_snapshots.py` |  |

## 10) AI Lab (AI)

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[AI-10.1]** | Not Covered | - | No specific tests for the AI Lab's core mandate. |
| **[AI-10.2.3]**| Not Covered | - | No specific tests for recommending filters. |
| **[AI-10.2.4]**| Not Covered | - | No specific tests for recommending stop-loss/take-profit. |
| **[AI-F.2.1]** | **Covered** | `tests/core/test_monte_carlo_wfe_paramsearch.py`, `tests/core/test_robustness_more.py` |  |
| **[AI-F.2.2]** | **Covered** | `tests/core/test_monte_carlo_wfe_paramsearch.py`, `tests/core/test_robustness_more.py` |  |

## 11) JSON Brief Schema

| Requirement ID | Status | Evidence | Notes |
| --- | --- | --- | --- |
| **[JSON-11.1]** | Not Covered | - | No specific tests for the `meta` section. |
| **[JSON-11.2]** | Not Covered | - | No specific tests for the `strategy_params` section. |
| **[JSON-11.3]** | Not Covered | - | No specific tests for the `rem_config` section. |
| **[JSON-11.4]** | Not Covered | - | No specific tests for the `overall_performance` section. |
| **[JSON-11.5]** | Not Covered | - | No specific tests for the `risk_snapshot` section. |
| **[JSON-11.6]** | Not Covered | - | No specific tests for the `equity_stats` section. |
| **[JSON-11.7]** | Not Covered | - | No specific tests for the `distribution` section. |
| **[JSON-11.8]** | Not Covered | - | No specific tests for the `streaks` section. |
| **[JSON-11.9]** | Not Covered | - | No specific tests for the `holding_time` section. |
| **[JSON-11.10]**| Not Covered | - | No specific tests for the `activity` section. |
| **[JSON-11.11]**| Not Covered | - | No specific tests for the `timing_buckets` section. |
| **[JSON-11.12]**| **Covered** | `tests/reporting/test_brief_cost_inclusion.py`, `tests/reporting/test_cost_placeholders.py`, `tests/reporting/test_costs_aggregate_and_snapshot.py`, `tests/reporting/test_costs_mixed_breakdown_defaults.py`, `tests/reporting/test_save_run_brief_costs.py` |  |
| **[JSON-11.13]**| **Covered** | `tests/backtester/test_exposure_curve.py`, `tests/reporting/test_exposure_metrics.py` |  |
| **[JSON-11.14]**| Not Covered | - | No specific tests for the `contrasts` section. |
| **[JSON-11.15]**| Not Covered | - | No specific tests for the `regimes` section. |
| **[JSON-11.16]**| Not Covered | - | No specific tests for the `stop_tp_candidates` section. |
| **[JSON-11.17]**| **Covered** | `tests/reporting/test_data_quality.py` |  |
| **[JSON-11.18]**| **Covered** | `tests/reporting/test_brief_edge_cases.py`, `tests/core/test_finalize_run_config_injection.py`, `tests/reporting/test_brief_instruments.py` |  |
| **[JSON-11.19]**| **Covered** | `tests/core/test_finalize_run_config_injection.py`, `tests/reporting/test_costs_aggregate_and_snapshot.py`, `tests/reporting/test_save_run_brief_costs.py` |  |
| **[JSON-11.20]**| **Covered** | `tests/core/test_finalize_run_config_injection.py` |  |
| **[JSON-11.21]**| **Covered** | `tests/core/test_blackout_policy_in_brief.py` |  |
| **[JSON-11.22]**| **Covered** | `tests/reporting/test_provenance_env.py` |  |
| **[JSON-11.23]**| **Covered** | `tests/reporting/test_provenance_env.py` |  |
| **[JSON-11.24]**| **Covered** | `tests/reporting/test_config_snapshot_stability.py`, `tests/reporting/test_provenance_checksums.py` |  |
| **[JSON-11.25]**| **Covered** | `tests/portfolio/test_mfe_mae_bars.py`, `tests/reporting/test_mfe_mae_serialization.py`, `tests/reporting/test_r_multiple_serialization.py` |  |
| **[JSON-11.26]**| **Covered** | `tests/reporting/test_skips_in_brief.py` |  |
| **[JSON-11.27]**| **Covered** | `tests/reporting/test_skips_in_brief.py` |  |
| **[JSON-11.28]**| Not Covered | - | No specific tests for pure JSON types. |
| **[JSON-F.1]** | **Covered** | `tests/core/test_finalize_run_mc_wfe_paramsearch.py`, `tests/reporting/test_mc_wf_placeholders.py` |  |
| **[JSON-F.2]** | **Covered** | `tests/core/test_finalize_run_mc_wfe_paramsearch.py`, `tests/reporting/test_mc_wf_placeholders.py` |  |
| **[JSON-F.3]** | **Covered** | `tests/core/test_finalize_run_mc_wfe_paramsearch.py` |  |

## Summary of Findings

### High-Level Observations
- The project has a substantial number of tests, and many requirements are traceable to specific test files.
- The use of `# Validates: [ID]` comments is a good practice but is not consistently applied across all test files.
- The `tests/portfolio/test_portfolio.py` file uses a `@requires` decorator, which is another good way to link tests to requirements.

### Key Gaps
- **Risk & Exit Manager (REM)**: There are no tests for any of the REM requirements. This is a major gap.
- **Data Handler (DH)**: Several core data handling requirements are not covered by tests, including data loading, live streaming, and caching.
- **JSON Brief Schema**: While many of the newer JSON brief fields are covered, the foundational sections (meta, performance, etc.) do not have specific validation tests.
- **Architectural Principles**: Many of the high-level architectural requirements (e.g., modular separation, canonical models) are not directly testable and rely on code reviews and static analysis.

### Orphaned Tests
- I did not find any obvious orphaned tests (tests that do not correspond to any requirement). However, without a more thorough analysis of each test's content, it's possible that some tests are not fully aligned with their stated requirements.

### Recommendations
1.  **Prioritize REM Tests**: Add tests for the Risk & Exit Manager (REM) module to cover the existing requirements.
2.  **Increase DH Test Coverage**: Add tests for the Data Handler (DH) to cover data loading, streaming, and other uncovered requirements.
3.  **Add JSON Schema Validation Tests**: Implement tests that validate the full JSON brief against a schema to ensure all fields are present and correctly formatted.
4.  **Enforce Requirement Tagging**: Encourage the consistent use of `# Validates: [ID]` comments in all new test files to improve traceability.
