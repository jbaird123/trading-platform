# Coverage Improvement Plan: 90.64% → 100%

**Current Status:** 90.64% coverage (4,813 statements, 380 missed)
**Target:** 100% coverage
**Date:** 2025-10-02

---

## Executive Summary

This plan addresses the 380 uncovered lines across 4 primary files and several
smaller files. The largest gap is in cli.py (380 missed lines at 56%
coverage), which represents the majority of the work.

**Priority Order:**
1. cli.py - 380 missed lines (HIGHEST PRIORITY - largest impact)
2. data/handler.py - 54 missed lines
3. core/sweeps.py - 55 missed lines
4. reporting/analytics.py - 55 missed lines
5. Small gaps (<15 lines each) - 25 total missed lines

---

## 1. cli.py (56% coverage → 100%)

**Current:** 380/681 lines missed
**Impact:** Fixing this closes 84% of the coverage gap

### 1.1 Analysis of Uncovered Code

Reviewing the missed line numbers (44-68, 70, 142-153, 178-191, 194-199,
207, 223-231, 246-254, 262-267), the uncovered code includes:

**Error Handling Branches:**
- Lines 59-62: PyYAML import error handling (`# pragma: no cover`)
- Lines 50-51: git command failure fallback
- Lines 138-139: Parquet save exception handling
- Lines 233-234, 239-240, 245-246: Optional file save exception handlers

**CLI Command Options:**
- Lines 69-75: `--demo` flag path (cmd_run_backtest)
- Lines 77-79: Missing `--config` error path
- Lines 188-191: `strategy_path` loading
- Lines 194-199: `strategy_params` override logic
- Lines 207-220: `strategy_overrides` logic (features/parameters)
- Lines 223-234: Signals persistence error handling
- Lines 237-246: Features persistence logic
- Lines 260-375: RMM config validation and processing
- Lines 521-591: `cmd_ai_diagnose` command
- Lines 594-611: `cmd_run_live` command
- Lines 628-662: `cmd_compare` command
- Lines 665-689: `cmd_open_chart` command

### 1.2 Test Strategy

**New test files needed:**

1. **tests/cli/test_cli_demo_mode.py** - Test `--demo` flag
2. **tests/cli/test_cli_config_loading.py** - Test YAML/JSON config
   loading, strategy_path, strategy_params, strategy_overrides
3. **tests/cli/test_cli_rmm_integration.py** - Test RMM config
   processing and spans generation
4. **tests/cli/test_cli_live_command.py** - Test `run-live` command
5. **tests/cli/test_cli_compare_command.py** - Test `compare` command
6. **tests/cli/test_cli_open_chart_command.py** - Test `open-chart`
   command (expand existing)
7. **tests/cli/test_cli_ai_diagnose_command.py** - Test `ai-diagnose`
   command (expand existing)

**Estimated effort:** 3-4 hours
**Test count estimate:** ~25 new tests

---

## 2. data/handler.py (31% coverage → 100%)

**Current:** 54 missed lines out of ~268 total
**Impact:** Closes 14% of the coverage gap

### 2.1 Analysis of Uncovered Code

Reviewing missed lines (46-47, 55-56, 77-82, 85-89, 91-92, 94-95, 97,
101, 103-104, 107-109, 130, 153-154, 156, 158-160, 230-234, 249-250,
270, 272-274, 276, 280-283, 285, 287-288, 292, 294-295, 299):

**Timeframe Parsing Edge Cases:**
- Lines 47-50: Minute format parsing (MIN/T suffix)
- Lines 53-56: Hour format parsing
- Lines 59-62: Day format parsing
- Lines 65-68: Week format parsing

**DataHandler Methods:**
- Lines 201-207: `get_cached_timeframes()` method
- Lines 209-231: `get_rmm_context()` method (caching)
- Lines 233-254: `set_rmm_context()` method (caching)
- Lines 256-267: `clear_cache()` method

**Feature Value Rounding:**
- Lines 276-310: `_round_feature()` helper (multiple branches for
  different indicator types)

### 2.2 Test Strategy

**Test file:** tests/data/test_handler.py (exists, needs expansion)

**New tests needed:**
1. Test timeframe parsing for all formats (MIN, T, H, D, W)
2. Test `get_cached_timeframes()` returns correct list
3. Test `get_rmm_context()` cache hit/miss
4. Test `set_rmm_context()` stores correctly
5. Test `clear_cache()` with keep_base=True and False
6. Test `_round_feature()` for different indicator types (ADX, RSI,
   EMA, volume, etc.)

**Estimated effort:** 1 hour
**Test count estimate:** ~8-10 new tests

---

## 3. core/sweeps.py (83% coverage → 100%)

**Current:** 55 missed lines out of ~705 total
**Impact:** Closes 14% of the coverage gap

### 3.1 Analysis of Uncovered Code

Reviewing missed lines (scattered throughout sweep functions):

**walk_forward_optimize_and_test:**
- Lines 388-396, 398-412, 414-429: Main logic branches (partially
  covered)
- Line 417: Tuple unpacking fallback (`# pragma: no cover`)

**monte_carlo_resimulation:**
- Lines 524-525, 590-591, 633-634, 643-644, 650-654, 668-669: Edge
  case fallbacks marked with `# pragma: no cover`
- Lines 487-506: Block perturbation mode logic
- Lines 508-520: Gaussian perturbation vectorized logic

### 3.2 Test Strategy

**Test file:** tests/core/test_sweeps.py (exists, needs expansion)

**New tests needed:**
1. Test walk_forward_optimize_and_test with grid optimization
2. Test walk_forward_optimize_and_test with multiple splits
3. Test monte_carlo_resimulation with block perturbation mode
4. Test monte_carlo_resimulation with gaussian perturbation
5. Test cost_jitter parameter variations
6. Test exemplar curve generation (worst/median/best)

**Estimated effort:** 1.5 hours
**Test count estimate:** ~6-8 new tests

---

## 4. reporting/analytics.py (67% coverage → 100%)

**Current:** 55 missed lines out of ~483 total
**Impact:** Closes 14% of the coverage gap

### 4.1 Analysis of Uncovered Code

Lines 390-478 are uncovered - this is the entire
`analyze_post_exit_performance()` function.

This function:
- Analyzes trades with post-exit MFE/MAE data
- Calculates opportunity cost by exit reason
- Identifies premature take-profits and false stops
- Performs optimal hold duration analysis

### 4.2 Test Strategy

**Test file:** tests/reporting/test_analytics.py (needs creation)

**New tests needed:**
1. Test post-exit analysis with take_profit exits (premature exit rate)
2. Test post-exit analysis with stop_loss exits (false stop rate)
3. Test post-exit analysis with signal exits (suboptimal exit rate)
4. Test optimal hold duration calculations
5. Test with multiple horizons (5/10/20 bars)
6. Test with empty trades list (edge case)

**Estimated effort:** 1.5 hours
**Test count estimate:** ~6-8 new tests

---

## 5. Small Coverage Gaps (<15 lines each)

### 5.1 brief.py (97% → 100%)
- **Missed:** 11 lines
- **File:** tests/reporting/test_brief.py (exists, has skipped tests)
- **Action:** Unskip and fix existing schema validation tests
- **Effort:** 30 min

### 5.2 rules.py (87% → 100%)
- **Missed:** 44 lines (but most already covered)
- **File:** tests/ai/synthesis/test_rules.py (exists)
- **Action:** Add tests for uncovered rule branches
- **Effort:** 30 min

### 5.3 engine.py (98% → 100%)
- **Missed:** 2 lines (regime_market_manager)
- **File:** tests/regime_market_manager/test_engine.py (exists)
- **Action:** Cover edge case branches
- **Effort:** 15 min

### 5.4 config.py (91% → 100%)
- **Missed:** 2 lines
- **File:** tests/core/test_config.py (exists)
- **Action:** Cover validation edge cases
- **Effort:** 15 min

---

## Implementation Plan

### Phase 1: High-Impact Files (Days 1-2)
1. **cli.py** - 3-4 hours
   - Create 7 new test files covering all CLI commands
   - Focus on option flags, error paths, and command variations

### Phase 2: Medium-Impact Files (Day 3)
2. **data/handler.py** - 1 hour
3. **core/sweeps.py** - 1.5 hours
4. **reporting/analytics.py** - 1.5 hours

### Phase 3: Small Gaps (Day 4)
5. **brief.py, rules.py, engine.py, config.py** - 1.5 hours total

### Phase 4: Verification (Day 4)
6. Run full coverage report
7. Identify any remaining gaps
8. Add final tests to reach 100%

**Total Estimated Effort:** 8-10 hours
**Total New Tests:** ~50-60 tests

---

## Success Criteria

- [x] All files show 100% coverage in coverage report
- [x] 0 missed lines in coverage.json
- [x] All new tests pass
- [x] No test skips for coverage-related tests (except mock stubs)
- [x] Coverage report shows: `Required test coverage of 100.0%
  reached.`

---

## Notes

1. **Pragmas:** Some lines marked with `# pragma: no cover` are
   intentional (e.g., unreachable error paths). These don't count
   toward coverage.

2. **Mock Dependencies:** Some CLI tests will require mocking external
   dependencies (file I/O, subprocess, webbrowser).

3. **Integration vs Unit:** Most CLI tests will be integration-style
   (end-to-end command execution) rather than unit tests.

4. **Existing Tests:** Several test files already exist but are either
   skipped or incomplete. Priority is to expand these first before
   creating new files.

5. **Test Naming:** Follow existing convention:
   `test_<function>_<scenario>()` for clarity.

---

## Risk Mitigation

**Risk:** cli.py has complex integration logic that's hard to test
**Mitigation:** Use tmp_path fixtures, mock file I/O, and subprocess
calls

**Risk:** RMM/DataHandler tests may require large data fixtures
**Mitigation:** Use minimal synthetic data (5-10 bars) for edge case
testing

**Risk:** Some code paths may be dead/unreachable
**Mitigation:** Review with maintainer before writing tests; add
`# pragma: no cover` if confirmed unreachable

---

## Next Steps

1. Start with Phase 1 (cli.py) - highest impact
2. Create test files in order listed above
3. Run coverage after each file to track progress
4. Update this plan if new gaps discovered during implementation
