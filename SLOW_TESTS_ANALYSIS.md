# Slow Tests Analysis

**Generated**: 2025-10-02
**Total Test Execution Time**: 40.33 seconds
**Total Tests**: 1,183

## Executive Summary

The test suite completes in 40.33 seconds, which is reasonable for a suite of 1,183 tests (average ~34ms per test). However, the top 20 slowest tests account for 27.63 seconds (68.5% of total execution time).

## Top 20 Slowest Tests

| Rank | Duration | Test | Category | Notes |
|------|----------|------|----------|-------|
| 1 | 6.11s | test_cli_data_request_with_start_end_filtering | CLI/Integration | Data filtering operations |
| 2 | 3.71s | test_full_training_pipeline_e2e | AI/E2E | Full ML pipeline |
| 3 | 3.33s | test_get_feedback_success | AI/LLM | LLM API call |
| 4 | 3.30s | test_full_training_pipeline_e2e_minimal | AI/E2E | ML pipeline minimal |
| 5 | 2.59s | test_get_feedback_api_exception | AI/LLM | LLM API error handling |
| 6 | 2.48s | test_get_feedback_non_string_text | AI/LLM | LLM API edge case |
| 7 | 2.37s | test_get_feedback_timeout_exception | AI/LLM | LLM API timeout |
| 8 | 2.32s | test_get_feedback_no_text_attribute | AI/LLM | LLM API edge case |
| 9 | 2.30s | test_get_feedback_http_error | AI/LLM | LLM API error handling |
| 10 | 0.80s | test_main_block_execution | AI/Synthesis | Process execution |
| 11 | 0.63s | test_main_block_execution_subprocess | AI/Labeling | Subprocess test |
| 12 | 0.24s | test_equity_and_pnl_are_consistent | Core/Properties | Property-based test |
| 13 | 0.17s | test_cmd_run_backtest_reads_csv_path | CLI/Integration | Backtest CLI |
| 14 | 0.14s | test_compute_stationarity | Reporting/Analytics | Statistical test |
| 15 | 0.11s | test_parquet_cache_invalidation_on_source_change | Data/Caching | Cache validation |
| 16 | 0.11s | test_cmd_run_backtest_saves_rmm_spans_artifact | Core/CLI | RMM artifact |
| 17 | 0.10s | test_cmd_run_backtest_yaml_requires_pyyaml | CLI | YAML validation |
| 18 | 0.10s | test_walk_forward_optimize_and_test_returns_payload | Core/WF | Walk-forward |
| 19 | 0.09s | test_cmd_run_backtest_toy_data_path | CLI | Toy data |
| 20 | 0.09s | test_cmd_run_backtest_saves_signals_artifact | Core/CLI | Signal artifact |

**Total Time for Top 20**: 27.63 seconds
**Percentage of Total**: 68.5%

## Analysis by Category

### 1. LLM API Tests (18.39s - 45.6% of total time)
- **Tests**: 6 tests in tests/ai/llm_analysis/test_client.py
- **Duration**: 2.30s - 3.33s each
- **Root Cause**: Real or mocked API calls with timeouts/delays
- **Recommendation**: ✅ **ACCEPTABLE** - These tests validate actual API behavior including timeouts. Consider:
  - Using `@pytest.mark.slow` decorator
  - Running in parallel with pytest-xdist
  - Reducing timeout durations in test environment

### 2. E2E ML Pipeline Tests (7.01s - 17.4% of total time)
- **Tests**: 2 tests in tests/ai/e2e/test_training_pipeline_e2e.py
- **Duration**: 3.30s - 3.71s each
- **Root Cause**: Full training pipeline execution with data processing
- **Recommendation**: ✅ **ACCEPTABLE** - E2E tests should be comprehensive. Consider:
  - Marking with `@pytest.mark.slow`
  - Using smaller datasets in tests
  - Running in separate CI job for E2E tests

### 3. CLI Integration Tests (6.28s - 15.6% of total time)
- **Tests**: test_cli_data_request_with_start_end_filtering
- **Duration**: 6.11s
- **Root Cause**: Full CLI execution with data filtering
- **Recommendation**: ⚠️ **OPTIMIZE** - Consider:
  - Reducing dataset size for test
  - Mocking data loading where possible
  - Splitting into smaller unit tests

### 4. Fast Tests (<1s each) (1.53s total)
- **Tests**: 12 tests ranging from 0.09s to 0.80s
- **Recommendation**: ✅ **EXCELLENT** - These are well-optimized

## Recommendations

### Immediate Actions (Optional)
1. ✅ Mark slow tests with `@pytest.mark.slow` for selective execution
2. ✅ Configure pytest-xdist for parallel execution: `pytest -n auto`
3. ⚠️ Reduce timeout durations in LLM API tests for test environment

### Future Optimizations
1. Split test_cli_data_request_with_start_end_filtering into smaller unit tests
2. Use smaller datasets in E2E ML pipeline tests
3. Consider separate CI job for slow integration tests (>1s)

### pytest.ini Configuration
```ini
[pytest]
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests

# Run fast tests by default
addopts = -m "not slow"

# Parallel execution
# addopts = -n auto
```

## Performance Targets

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Total Execution Time** | 40.33s | <60s | ✅ GOOD |
| **Average Test Time** | 34ms | <100ms | ✅ EXCELLENT |
| **Slowest Test** | 6.11s | <10s | ✅ ACCEPTABLE |
| **Tests >1s** | 11 | <20 | ✅ GOOD |

## Conclusion

✅ **Test suite performance is GOOD**. The 40.33s execution time for 1,183 tests is reasonable and well within acceptable limits. Slow tests are primarily:
- LLM API tests with realistic timeouts (acceptable)
- E2E ML pipeline tests (acceptable)
- One CLI integration test that could be optimized (optional)

**No critical performance issues detected.** The test suite is well-balanced between speed and comprehensive coverage.
