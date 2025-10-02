# CLI Coverage Analysis

**Current Coverage:** 69.6% (105 of 345 lines uncovered)
**Target:** 100%
**Estimated Effort:** 6-8 hours
**Complexity:** High (deep integration testing)

---

## Challenge Summary

The CLI module presents unique testing challenges:

1. **Deep Integration**: Commands invoke full backtesting pipeline (strategy compilation, data loading, execution, reporting)
2. **External Dependencies**: File I/O, subprocess calls, environment variables
3. **RunConfig Validation**: Pydantic validation requires complete, valid configurations
4. **State Management**: Multiple mocks must maintain consistency across call chain

---

## Missing Coverage Breakdown

### 1. Exception Handling (15 lines)
- Lines 91-92: Git command failure
- Lines 138-139: Parquet save exception
- Lines 231, 233-234: Signal persistence save errors
- Lines 239-240, 245-246: Feature/RMM persistence save errors

**Testing Approach:**
- Mock file operations to raise exceptions
- Verify graceful degradation
- **Effort:** 1 hour

### 2. Configuration Loading Paths (30 lines)
- Lines 179-181: strategy_path loading
- Lines 183-184: strategy_params override
- Lines 186: strategy_overrides application
- Lines 196-199: strategy_params validation
- Lines 214-220: strategy_overrides.features merge
- Lines 278-310: _round_feature precision logic

**Testing Approach:**
- Test configuration variants with mocked dependencies
- Isolate parameter merging logic
- **Effort:** 2 hours

### 3. RMM Integration (20 lines)
- Lines 302-340: RMM config processing
- Lines 278-296: Feature value rounding
- RMM span generation

**Testing Approach:**
- Mock RMMEngine and DataHandler
- Test RMM context caching
- **Effort:** 1.5 hours

### 4. Command Functions (40 lines)
- cmd_ai_diagnose paths (lines 521-591)
- cmd_run_live paths (lines 594-627)
- cmd_compare paths (lines 628-689)

**Testing Approach:**
- Mock file loading and external APIs
- Test argument validation
- Test error paths
- **Effort:** 2.5 hours

---

## Recommended Approach

### Phase 1: Low-Hanging Fruit (2 hours)
1. **Helper function tests**
   - Git commit handling
   - Config loading edge cases
   - _find_last_briefs variations
   - **Lines covered:** ~10

2. **Exception handling tests**
   - File I/O exceptions
   - Parquet save errors
   - **Lines covered:** ~15

### Phase 2: Configuration Tests (2 hours)
3. **Parameter merging**
   - strategy_path loading
   - strategy_params override
   - strategy_overrides application
   - **Lines covered:** ~20

4. **Feature rounding**
   - _round_feature for various indicator types
   - **Lines covered:** ~15

### Phase 3: Command Tests (3 hours)
5. **cmd_ai_diagnose**
   - Brief loading
   - Error handling
   - **Lines covered:** ~15

6. **cmd_compare**
   - Last N briefs
   - Path validation
   - **Lines covered:** ~15

7. **Integration paths**
   - RMM context building
   - Signal persistence
   - **Lines covered:** ~15

---

## Why CLI is Hard to Test

### Problem 1: RunConfig Validation Chain

```python
# CLI creates RunConfig
cfg = RunConfig.model_validate(cfg_raw)  # Requires full valid config

# Valid config needs:
- instrument: {"symbol": "EURUSD", "timeframe": "1H"}
- strategy: {complete schema-valid strategy}
- initial_cash, position_size, etc.
- Optional: RMM, REM, features
```

**Solution:** Create fixture factory for valid configs

### Problem 2: Deep Call Chains

```python
cmd_run_backtest()
  → initialize_run()
  → load_instrument_data()
  → compile_strategy()
    → validate strategy schema
    → build features
  → run_backtest()
    → execute trades
  → finalize_run()
    → save brief, report, trades
```

**Solution:** Mock at module boundaries (initialize_run, run_backtest)

### Problem 3: File System State

Tests create actual files in tmp directories, requiring cleanup and isolation.

**Solution:** Use pytest tmp_path fixtures consistently

---

## Alternative: Integration Test Suite

Instead of unit testing CLI commands, consider:

1. **End-to-end integration tests**
   - Test full command execution with minimal configs
   - Use actual file system (tmp_path)
   - Accept longer runtime (5-10s per test)

2. **Focused unit tests**
   - Test pure functions (_round_feature, _load_config)
   - Test helper utilities (_find_last_briefs)
   - Mock only at service boundaries

3. **Manual acceptance testing**
   - Document expected CLI behavior
   - Test against real backtest runs
   - Verify output artifacts

---

## Coverage Impact Analysis

**Current:** 69.6% CLI coverage (94.42% overall)
**Target:** 100% CLI coverage (~96.5% overall)

**Improvement:** +2% overall coverage for ~8 hours of work

**Value Assessment:**
- Low ROI: CLI is integration glue, not business logic
- High maintenance: Tests break on any schema/config change
- Better investment: Focus on backtester core, sweeps, other modules

---

## Recommendation

**Do Not Pursue 100% CLI Coverage**

Reasons:
1. **Diminishing returns**: 8 hours for 2% overall improvement
2. **Brittle tests**: Deep mocking makes tests fragile
3. **Better targets**: backtester/core.py, sweeps.py have higher business logic value
4. **CLI stability**: Module is mature, rarely changes

**Alternative Plan:**
1. Add 10-15 high-value tests for pure functions (2 hours, +15 lines)
2. Document expected CLI behavior
3. Focus effort on backtester core logic (higher ROI)
4. Maintain current 69.6% CLI coverage as acceptable

**Net Result:**
- Reach ~95% overall coverage (vs 94.42%)
- Save 6 hours for higher-value testing
- Reduce test maintenance burden

---

## Pure Function Test Opportunities

These functions CAN be easily tested without deep mocking:

1. **_load_config** ✅ (already tested)
2. **_get_git_commit** ✅ (already tested)
3. **_find_last_briefs** ✅ (already tested)
4. **_round_feature** ❌ (not tested, pure function)
5. **_to_rmm_spans** ❌ (not tested, but requires DataFrame input)

**Actionable:** Add _round_feature tests (30 min, +30 lines coverage)

---

## Conclusion

Achieving 100% CLI coverage is **technically feasible but strategically inadvisable**:

- **Time cost:** 8 hours
- **Maintenance cost:** High (brittle mocks)
- **Business value:** Low (integration glue)
- **Alternative value:** Focus on backtester/core, sweeps, analytics

**Recommended Path:**
1. Add _round_feature tests (30 min)
2. Document CLI behavior
3. Accept 70-75% CLI coverage
4. Focus on higher-value modules

This maximizes testing ROI while maintaining overall project coverage above 95%.
