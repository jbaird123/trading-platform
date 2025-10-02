# Test Failures Analysis

**Generated**: 2025-10-02
**Total Tests**: 1,183
**Passing**: 1,104 (93.3%)
**Failing**: 65 (5.5%)
**Errors**: 14 (1.2%)

## Summary

All test failures fall into two categories:
1. **Mock-based tests awaiting implementation** (61 failures + 8 errors)
2. **Pre-existing failures** (4 RMM failures + 6 CLI errors)

## Category Breakdown

### 1. LLM API Client Tests (8 failures) - Mock Implementation
**File**: `tests/ai/llm_analysis/test_client.py`
**Status**: Tests expect Gemini API, actual implementation may differ

**Failures**:
1. `test_llm_api_client_raises_without_api_key` - Not raising ValueError
2. `test_llm_api_client_initialization_with_api_key` - mock_configure not called
3. `test_get_feedback_success` - mock generate_content not called
4. `test_get_feedback_no_text_attribute` - Getting real response instead of error
5. `test_get_feedback_non_string_text` - Getting real response instead of error
6. `test_get_feedback_api_exception` - Getting real response instead of error
7. `test_get_feedback_timeout_exception` - Getting real response instead of error
8. `test_get_feedback_http_error` - Getting real response instead of error

**Root Cause**: Tests mock Gemini API but actual implementation may use different LLM or different API pattern.

**Fix Options**:
- A) Implement actual Gemini LLM client as tests expect
- B) Update tests to match actual LLM implementation
- C) Skip tests with `@pytest.mark.skip(reason="awaiting LLM implementation")`

### 2. Execution Layer Tests (24 failures) - Missing Module
**Files**:
- `tests/execution/test_connectivity_retries.py` (8 failures)
- `tests/execution/test_live_stream.py` (9 failures)
- `tests/execution/test_structured_logging.py` (7 failures)

**Error**: `ModuleNotFoundError: No module named 'execution'`

**Root Cause**: Tests import from `execution` module which doesn't exist. Should be `trading_platform.execution`.

**Fix**: Update all imports from `from execution import ...` to `from trading_platform.execution import ...`

### 3. CLI Full Coverage Tests (8 errors) - Missing Function
**File**: `tests/cli/test_cli_full_coverage.py`

**Error**: `AttributeError: <module 'trading_platform.cli'> has no attribute 'load_instrument_data'`

**Root Cause**: Test fixture tries to mock `cli.load_instrument_data` which doesn't exist in cli module.

**Fix**:
- A) Implement `load_instrument_data` function in cli module
- B) Update test to mock the correct function
- C) Remove test if functionality moved elsewhere

### 4. Data Sync Service Tests (8 errors) - Missing Class
**File**: `tests/data/test_dukascopy_sync_service.py`

**Error**: `AttributeError: <module 'trading_platform.data.sync'> does not have the attribute 'DukascopySyncService'`

**Root Cause**: Tests expect `DukascopySyncService` class which doesn't exist.

**Fix**:
- A) Implement `DukascopySyncService` class
- B) Skip tests with `@pytest.mark.skip(reason="awaiting implementation")`

### 5. RMM Tests (6 failures) - Pre-existing
**Files**:
- `tests/regime_market_manager/test_engine.py` (4 failures)
- `tests/regime_market_manager/test_hysteresis.py` (2 failures)

**Status**: Pre-existing failures, not from requirements coverage work

**Failures**:
- `test_eval_pred_known_conditions`
- `test_eval_pred_unknown_condition_defaults_false`
- `test_rmm_engine_project_to_index_with_daily_data`
- `test_rmm_engine_classify_daily_end_to_end`
- `test_regime_transition_hysteresis_prevents_flipping`
- `test_confidence_threshold_hysteresis`

**Fix**: Investigate RMM implementation logic

### 6. Import Boundary Tests (10 failures) - Module Structure
**File**: `tests/core/test_import_boundaries.py`

**Error**: `ImportError: cannot import name 'X' from 'trading_platform'`

**Root Cause**: Public API imports missing from `trading_platform/__init__.py`

**Failures**:
- `test_strategy_base_is_public` - StrategyBase not exported
- `test_backtester_is_public` - Backtester not exported
- `test_portfolio_manager_is_public` - PortfolioManager not exported
- `test_data_loader_is_public` - load_instrument_data not exported
- `test_brief_generation_is_public` - save_run_brief not exported
- `test_rmm_is_public` - RMMEngine not exported
- `test_rem_is_public` - RiskExitManager not exported
- `test_yaml_strategy_is_public` - YAMLStrategy not exported
- `test_no_implementation_leakage` - Private modules being imported
- `test_typing_imports_available` - Type hints not exported

**Fix**: Update `trading_platform/__init__.py` to export public API

### 7. AI Synthesis Tests (3 failures) - Implementation Details
**Files**:
- `tests/ai/synthesis/test_rules.py` (1 failure)
- `tests/ai/llm_analysis/test_llm_engine.py` (1 failure)
- `tests/cli/test_cli_ai_diagnose.py` (1 failure)

**Failures**:
1. `test_signal_persistence_rule_triggered` - Expects "85%" got "0.8%"
2. `test_llm_engine_run` - JSON formatting in prompt differs
3. `test_cmd_ai_diagnose_triggers_specific_rule` - Percentage format issue

**Root Cause**: Signal persistence percentage formatting (85 vs 0.85 vs "85%")

**Fix**: Standardize percentage formatting in rules/prompts

### 8. Cost/Reporting Tests (4 failures) - Schema Validation
**Files**:
- `tests/reporting/test_brief.py` (2 failures)
- `tests/reporting/test_costs.py` (2 failures)

**Failures**:
- `test_save_run_brief_schema_validation_enabled`
- `test_brief_schema_accepts_mc_wf_ps_enumerated_fields`
- `test_trades_include_cost_breakdown_placeholders`
- `test_mixed_trades_breakdown_and_defaults`

**Root Cause**: Brief schema validation or cost breakdown implementation differs from tests

**Fix**: Align implementation with test expectations

### 9. Parameter Sweep Tests (2 failures) - Implementation Mismatch
**File**: `tests/core/test_parameter_sweep_consistency.py`

**Failures**:
- `test_parameter_sweep_matches_standalone`
- `test_strategy_params_override_file_defaults`

**Root Cause**: Parameter sweep behavior differs from test expectations

**Fix**: Investigate parameter sweep implementation

### 10. CLI Coverage Gap Tests (2 failures) - Pre-existing
**File**: `tests/cli/test_cli_coverage_gaps.py`

**Failures**:
- `test_cli_data_request_with_all_filters`
- `test_cli_no_data_request_uses_toy_data`

**Root Cause**: CLI data request functionality

**Fix**: Update CLI or tests

### 11. Golden Brief Test (1 failure) - Snapshot Mismatch
**File**: `tests/core/test_golden_brief.py`

**Failure**: `test_brief_matches_golden_master`

**Root Cause**: Brief output differs from golden master

**Fix**: Update golden master or fix brief generation

## Recommended Fix Priority

### High Priority (Critical Path)
1. **RMM Tests (6)** - Core functionality, pre-existing failures
2. **Import Boundary Tests (10)** - Public API critical for usability
3. **Golden Brief Test (1)** - End-to-end validation

### Medium Priority (Implementation Gaps)
4. **Execution Layer Imports (24)** - Quick fix: update import paths
5. **AI Synthesis Formatting (3)** - Simple formatting fix
6. **Cost/Reporting Tests (4)** - Schema validation issues

### Low Priority (Mock/Stub Tests)
7. **LLM API Client (8)** - Skip or update to match implementation
8. **CLI Full Coverage (8)** - Missing function, needs investigation
9. **Data Sync Service (8)** - Skip until implementation planned
10. **Parameter Sweep (2)** - Investigation needed
11. **CLI Coverage Gaps (2)** - Investigation needed

## Quick Wins (Can Fix Immediately)

### 1. Execution Layer Import Fix
Change all occurrences in test files:
```python
# From:
from execution import ...
# To:
from trading_platform.execution import ...
```

### 2. AI Synthesis Percentage Format
Standardize to show "85%" instead of "0.85" in rule summaries.

### 3. Skip Mock Tests
Add `@pytest.mark.skip` to incomplete implementation tests:
- LLM API client tests
- Data sync service tests

## Tests Requiring Investigation

1. **RMM Logic** - Why are predicate evaluation and hysteresis tests failing?
2. **Import Boundaries** - What should be in public API?
3. **CLI load_instrument_data** - Where did this function go?
4. **Parameter Sweep** - Why do results differ from standalone?
5. **Golden Brief** - What changed in brief generation?

## Next Steps

1. Create a detailed fix plan for high-priority failures
2. Quick fix: Execution layer import paths (24 tests)
3. Quick fix: AI synthesis percentage formatting (3 tests)
4. Skip incomplete mock tests (16 tests)
5. Investigate RMM failures (6 tests)
6. Update public API exports (10 tests)
