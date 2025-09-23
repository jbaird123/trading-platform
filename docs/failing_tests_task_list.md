# Failing Tests Task List

This document outlines the failing tests, categorized and prioritized for systematic resolution. Each item includes a checkbox for tracking completion.

## Unit Tests

### AI Module
- [x] 1. `tests/ai/evaluation/test_procedure.py::TestAIEvaluationProcedure::test_run_cross_validation_no_cv_config`
- [x] 2. `tests/ai/monitoring/test_performance_monitor.py::test_aib_check_thresholds_above_max`
- [x] 3. `tests/ai/monitoring/test_performance_monitor.py::test_aib_check_thresholds_below_min`
- [x] 4. `tests/ai/monitoring/test_performance_monitor.py::test_aib_check_thresholds_partial_threshold_config`
- [x] 5. `tests/ai/synthesis/test_engine.py::test_dse_run_no_rules`
- [x] 6. `tests/ai/synthesis/test_engine.py::test_dse_run_rules_no_conclusions`
- [x] 7. `tests/ai/synthesis/test_engine.py::test_dse_run_rules_with_conclusions`
- [ ] 8. `tests/ai/synthesis/test_rules.py::test_over_trading_rule_missing_win_rate`
- [ ] 9. `tests/ai/test_data_connectors.py::test_get_data_lineage`
- [ ] 10. `tests/ai/test_data_connectors.py::test_load_training_data_success`
- [ ] 11. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_all_same_price`
- [ ] 12. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_basic`
- [ ] 13. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_custom_look_ahead`
- [ ] 14. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_missing_close_column`
- [ ] 15. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_only_down`
- [ ] 16. `tests/ai/test_data_labeling.py::test_generate_future_price_direction_only_up`
- [ ] 17. `tests/ai/test_inference_client.py::test_send_request_http_status_error`
- [ ] 18. `tests/ai/test_inference_client.py::test_send_request_max_retries_exceeded`
- [ ] 19. `tests/ai/test_inference_client.py::test_send_request_other_exception`
- [ ] 20. `tests/ai/test_inference_client.py::test_send_request_retry_mechanism`
- [ ] 21. `tests/ai/test_inference_client.py::test_send_request_success`
- [ ] 22. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_evaluate_and_log_artifacts`
- [ ] 23. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_load_and_prepare_data`
- [ ] 24. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_load_and_prepare_data_with_nans`
- [ ] 25. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_train_model_lightgbm_import_error`
- [ ] 26. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_train_model_lightgbm_with_tuning`
- [ ] 27. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_train_model_random_forest_no_tuning`
- [ ] 28. `tests/ai/training/test_ai_training_pipeline.py::test_aitp_train_model_random_forest_with_tuning`

### Backtester Module
- [ ] 29. `tests/backtester/test_return_skips_only.py::test_return_skips_without_exposure`

### CLI Module
- [ ] 30. `tests/cli/test_cli_more.py::test_cmd_run_backtest_yaml_requires_pyyaml`

### Strategy Module
- [ ] 31. `tests/strategy/test_strategy_parameter_substitution.py::test_feature_params_resolve_from_named_parameters`

## Integration Tests

### AI Module
- [ ] 32. `tests/ai/integration/test_data_preparation_integration.py::test_data_preparation_integration_flow`
- [ ] 33. `tests/ai/integration/test_serving_integration.py::test_predict_integration_missing_api_key`
- [ ] 34. `tests/ai/integration/test_serving_integration.py::test_predict_integration_success`

### Serving Module
- [ ] 35. `tests/ai/serving/test_app.py::test_get_api_key_missing`
- [ ] 36. `tests/ai/serving/test_app.py::test_health_check_no_api_key`
- [ ] 37. `tests/ai/serving/test_app.py::test_metrics_no_api_key`
- [ ] 38. `tests/ai/serving/test_app.py::test_predict_no_api_key`

## End-to-End Tests

### AI Module
- [ ] 39. `tests/ai/e2e/test_training_pipeline_e2e.py::test_full_training_pipeline_e2e`
