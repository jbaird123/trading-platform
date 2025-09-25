# Coverage Tasks

1. [ ] Address missing coverage in `src/trading_platform/ai/data_connectors.py` (lines 99-111).
2. [ ] Address missing coverage in `src/trading_platform/ai/data_labeling.py` (lines 54-81).
3. [ ] Address missing coverage in `src/trading_platform/ai/synthesis/engine.py` (lines 98-100, 106-107, 223-252).
4. [ ] Address missing coverage in `src/trading_platform/ai/synthesis/rules.py` (lines 38, 86-104).
5. [ ] Address missing coverage in `src/trading_platform/ai/training/pipeline.py` (lines 31-32, 129, 164-173, 262).
6. [ ] Address missing coverage in `src/trading_platform/backtester/core.py` (lines 149-174, 283, 299, 386-440).
7. [ ] Address missing coverage in `src/trading_platform/cli.py` (lines 89, 109-110, 144-182, 192, 194-207, 213, 223, 251, 253, 255, 269-288, 291-292, 315-316, 331-336, 342, 366-368, 388-390, 445-453, 477-478, 508-571).
8. [ ] Address missing coverage in `src/trading_platform/core/robustness.py` (lines 36, 43, 83).
9. [ ] Address missing coverage in `src/trading_platform/core/run.py` (lines 117, 121-130, 149, 200-215).
10. [ ] Address missing coverage in `src/trading_platform/core/sweeps.py` (lines 114-115, 147, 161, 165, 172-174, 200, 234, 286-289, 302, 324-325, 331, 337, 364, 387, 432, 442, 467).
11. [ ] Address missing coverage in `src/trading_platform/execution/controller.py` (lines 95, 99, 134, branch 147→125).
12. [ ] Address missing coverage in `src/trading_platform/execution/oanda_stub.py` (branch 103→119).
13. [ ] Address missing coverage in `src/trading_platform/reporting/brief.py` (lines 60, 510-544, 581-596).
14. [ ] Address missing coverage in `src/trading_platform/reporting/html_export.py` (lines 140-148).
15. [ ] Address missing coverage in `src/trading_platform/risk_manager/core.py` (lines 51, 59-61, 82-95, 107, 120, 124).
16. [ ] Address missing coverage in `src/trading_platform/strategy/features.py` (lines 149-152, 164, 175-176, 178).
17. [ ] Address missing coverage in `src/trading_platform/strategy/yaml_strategy.py` (lines 13-14, 88, 104, 148-152, 156-198, 215-218).
18. [ ] Address missing coverage in `tests/ai/llm_analysis/test_llm_engine.py` (line 41).
19. [ ] Address missing coverage in `tests/ai/synthesis/test_rules.py` (lines 219-220).
20. [ ] Address missing coverage in `tests/ai/test_data_connectors.py` (lines 255-256, 275-278).
21. [ ] Address missing coverage in `tests/ai/test_feature_engineering_coverage_gaps.py` (lines 25, 35-41, 44-45, 50, 56-60).
22. [ ] Address missing coverage in `tests/ai/test_monitoring_retraining_coverage_gaps.py` (lines 345-349, 372, 375-379).
23. [ ] Address missing coverage in `tests/ai/test_training_pipeline_coverage_gaps.py` (lines 103, 137-139, 200, 239).
24. [ ] Address missing coverage in `tests/ai/training/test_ai_training_pipeline.py` (lines 19-44, 72, 592).
25. [ ] Address missing coverage in `tests/cli/test_cli_ai_diagnose.py` (lines 66, 78, 92).
26. [ ] Address missing coverage in `tests/cli/test_cli_compare_and_paths.py` (lines 14, 92-94).
27. [ ] Address missing coverage in `tests/cli/test_cli_cover_else.py` (lines 13, 55-57).
28. [ ] Address missing coverage in `tests/cli/test_cli_error_handling.py` (lines 53, 177-178).
29. [ ] Address missing coverage in `tests/cli/test_cli_more.py` (lines 14, 62-68).
30. [ ] Address missing coverage in `tests/cli/test_cli_toy_data_path.py` (lines 13, 45-47).
31. [ ] Address missing coverage in `tests/conftest.py` (lines 163, 219-220, 232, 295-306, 319-322, 379-380).
32. [ ] Address missing coverage in `tests/core/test_cli_commands.py` (lines 13, 67-69, 99-101, 152-154).
33. [ ] Address missing coverage in `tests/core/test_cost_model.py` (line 41).
34. [ ] Address missing coverage in `tests/core/test_finalize_run_config_injection.py` (line 14).
35. [ ] Address missing coverage in `tests/core/test_finalize_run_mc_wfe_paramsearch.py` (line 13).
36. [ ] Address missing coverage in `tests/core/test_golden_brief.py` (lines 68, 134-138).
37. [ ] Address missing coverage in `tests/core/test_run_config_schema.py` (lines 57-58).
38. [ ] Address missing coverage in `tests/data/test_data_catalog_loader.py` (line 52).
39. [ ] Address missing coverage in `tests/data/test_schema_errors.py` (line 41).
40. [ ] Address missing coverage in `tests/execution/test_controller_reconcile_variants.py` (line 14).
41. [ ] Address missing coverage in `tests/execution/test_controller_short_equity_and_reconcile.py` (line 13).
42. [ ] Address missing coverage in `tests/execution/test_oanda_position_cap.py` (line 12).
43. [ ] Address missing coverage in `tests/reporting/test_brief_schema.py` (lines 73-74).
44. [ ] Address missing coverage in `tests/reporting/test_field_definitions_coverage.py` (lines 20-21).
45. [ ] Address missing coverage in `tests/risk_manager/test_rem_schema.py` (lines 52-53).
46. [ ] Address missing coverage in `tests/step_defs/backtester/test_core_backtest_steps.py` (lines 10-12, 18-20).
47. [ ] Address missing coverage in `tests/step_defs/backtester/test_risk_management_steps.py` (lines 19-20, 26-51, 56-58).
48. [ ] Address missing coverage in `tests/step_defs/backtester/test_signal_steps.py` (lines 7-12).
49. [ ] Address missing coverage in `tests/step_defs/data_handler/test_data_schema_steps.py` (lines 6-7, 12, 17-18).
50. [ ] Address missing coverage in `tests/step_defs/data_handler/test_data_steps.py` (lines 6-7).
51. [ ] Address missing coverage in `tests/step_defs/regime_market_manager/test_classification_steps.py` (line 6).
52. [ ] Address missing coverage in `tests/step_defs/regime_market_manager/test_market_regime_classification_steps.py` (line 6).
53. [ ] Address missing coverage in `tests/step_defs/strategy_engine/test_signal_generation_steps.py` (lines 16-17).
54. [ ] Address missing coverage in `tests/step_defs/strategy_engine/test_strategy_steps.py` (lines 13-14).
55. [ ] Address missing coverage in `tests/strategy/test_base_strategy.py` (line 31).
56. [ ] Address missing coverage in `tests/strategy/test_base_strategy_coverage_gaps.py` (lines 35-36).
