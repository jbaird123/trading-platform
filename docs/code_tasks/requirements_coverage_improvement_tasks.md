# Requirements Coverage Improvement Tasks

**Created**: 2025-10-02
**Source**: [REQUIREMENTS_CHECK_REPORT.md](../../REQUIREMENTS_CHECK_REPORT.md)
**Goal**: Improve requirement traceability from 28% to 90%+ and address critical gaps

---

## 1. High Priority Tasks

### 1.1 RMM Test Coverage (COMPLETED ✅)
- [x] 1.1.1 Create comprehensive lookahead bias prevention tests
- [x] 1.1.2 Create side mapping fix tests for non-directional labels
- [x] 1.1.3 Update existing test to reflect Bug #1 fix
- [x] 1.1.4 Verify all 4 new tests pass

### 1.2 Entry Window State Management Tests ✅
- [x] 1.2.1 Add explicit tests for PM-5.8.1 (track bar index when entry command received)
- [x] 1.2.2 Add explicit tests for PM-5.8.2 (track entry occurrence to prevent duplicates)
- [x] 1.2.3 Add explicit tests for PM-5.8.3 (configurable entry window policies)
  - [x] 1.2.3.1 Test `entry_window_bars: 0` (exact bar only)
  - [x] 1.2.3.2 Test `entry_window_bars: N` (N-bar window)
  - [x] 1.2.3.3 Test `entry_window_bars: -1` (infinite window)
- [x] 1.2.4 Add explicit tests for PM-5.8.4 (window persistence across None commands)
- [x] 1.2.5 Add explicit tests for PM-5.8.5 (state serialization for live trading)
- [x] 1.2.6 Add `# Validates: [PM-5.8.x]` comments to all entry window tests

### 1.3 Performance Benchmark Tests ✅
- [x] 1.3.1 Create `tests/performance/test_performance_benchmarks.py`
- [x] 1.3.2 Add benchmark for SYS-1.9.1 (vectorized operations on multi-year data)
- [x] 1.3.3 Add benchmark for SYS-1.9.2 (laptop/Colab processing capability)
- [x] 1.3.4 Add memory usage profiling test
- [x] 1.3.5 Add benchmark for indicator computation speed
- [x] 1.3.6 Add benchmark for backtest execution time (1M bars target)
- [x] 1.3.7 Add `# Validates: [SYS-1.9.1], [SYS-1.9.2]` comments

### 1.4 Traceability Comment Audit - System-Wide (SYS) ✅
- [x] 1.4.1 Add `# Validates: [SYS-1.1.1]` to modular separation tests
- [x] 1.4.2 Add `# Validates: [SYS-1.1.2]` to `test_runconfig_*.py`
- [x] 1.4.3 Add `# Validates: [SYS-1.3.5]` to `test_utils.py` (symbol normalization)
- [x] 1.4.4 Add `# Validates: [SYS-1.4.1], [SYS-1.4.2], [SYS-1.4.3]` to comparison tests
- [x] 1.4.5 Add `# Validates: [SYS-1.6.x]` comments where applicable (CI/CD artifacts)
- [x] 1.4.6 Add `# Validates: [SYS-1.8.x]` to forex/timestamp tests
- [x] 1.4.7 Add `# Validates: [SYS-1.11.x]` to quality/tooling tests
- [x] 1.4.8 Add `# Validates: [SYS-1.12.x]` to cost constraint tests
- [x] 1.4.9 Add `# Validates: [SYS-1.13.x]` to security tests

---

## 2. Medium Priority Tasks

### 2.1 Traceability Comment Audit - Data Handler (DH) ✅
- [x] 2.1.1 Add `# Validates: [DH-2.1]` to CSV loading tests
- [x] 2.1.2 Add `# Validates: [DH-2.3]` to schema normalization tests
- [x] 2.1.3 Add `# Validates: [DH-2.4]` to UTC timestamp tests
- [x] 2.1.4 Add `# Validates: [DH-2.7]` to quality_flags tests
- [x] 2.1.5 Add `# Validates: [DH-2.9]` if chunked loading tests exist
- [x] 2.1.6 Add `# Validates: [DH-2.10]` if Parquet caching tests exist
- [x] 2.1.7 Add `# Validates: [DH-2.12]` to DataRequest interface tests
- [x] 2.1.8 Add `# Validates: [DH-2.13]` to golden dataset tests

### 2.2 Traceability Comment Audit - Strategy Engine (SE) ✅
- [x] 2.2.1 Add `# Validates: [SE-3.2]` to BaseStrategy interface tests
- [x] 2.2.2 Add `# Validates: [SE-3.4]` to built-in strategy tests (SMA, PSAR, BB)
- [x] 2.2.3 Add `# Validates: [SE-3.7]` to strategy metadata/plotting tests
- [x] 2.2.4 Review and update all SE test comments for completeness

### 2.3 Traceability Comment Audit - RMM ✅
- [x] 2.3.1 Add `# Validates: [RMM-4.1]` to `test_classification.py`
- [x] 2.3.2 Add `# Validates: [RMM-4.2]` to label+confidence output tests
- [x] 2.3.3 Add `# Validates: [RMM-4.3]` to rule-based baseline tests
- [x] 2.3.4 Add `# Validates: [RMM-4.6]` to policy function tests in `test_engine.py`
- [x] 2.3.5 Add `# Validates: [RMM-4.8]` to synthetic data tests

### 2.4 Traceability Comment Audit - Portfolio Manager (PM) ✅
- [x] 2.4.1 Add `# Validates: [PM-5.1]` to state management tests
- [x] 2.4.2 Add `# Validates: [PM-5.2]` to canonical terms tests
- [x] 2.4.3 Add `# Validates: [PM-5.3]` to cash/equity tracking tests
- [x] 2.4.4 Add `# Validates: [PM-5.4]` to order processing tests
- [x] 2.4.5 Add `# Validates: [PM-5.5]` to position sizing tests
- [x] 2.4.6 Add `# Validates: [PM-5.7]` to portfolio risk management tests

### 2.5 Traceability Comment Audit - Risk & Exit Manager (REM) ✅
- [x] 2.5.1 Add `# Validates: [REM-6.1]` to core mandate tests
- [x] 2.5.2 Add `# Validates: [REM-6.3]` to multiple exit rule type tests

### 2.6 Traceability Comment Audit - Backtester (BT) ✅
- [x] 2.6.1 Add `# Validates: [BT-7.2]` to rule translation tests
- [x] 2.6.2 Add `# Validates: [BT-7.3]` to iterative loop tests
- [x] 2.6.3 Add `# Validates: [BT-7.5]` to order type tests
- [x] 2.6.4 Add `# Validates: [BT-7.9]` to fill logic validation tests
- [x] 2.6.5 Add `# Validates: [BT-7.12]` to filter impact summary tests
- [x] 2.6.6 Add `# Validates: [BT-7.13]` to live trading deviation tests

### 2.7 Traceability Comment Audit - Execution Layer (EL) ✅
- [x] 2.7.1 Add `# Validates: [EL-8.1]` to rule translation tests
- [x] 2.7.2 Add `# Validates: [EL-8.2]` to OANDA adapter tests
- [x] 2.7.3 Add `# Validates: [EL-8.5]` to Portfolio Manager integration tests
- [x] 2.7.4 Add `# Validates: [EL-8.6]` if live stream tests exist
- [x] 2.7.5 Add `# Validates: [EL-8.7]` if structured logging tests exist

### 2.8 Traceability Comment Audit - AI Lab (AI) ✅
- [x] 2.8.1 Review all `tests/ai/**/*.py` files
- [x] 2.8.2 Add `# Validates: [AI-10.1.x]` to core mandate tests
- [x] 2.8.3 Add `# Validates: [AI-10.2]` to recommendation tests
- [x] 2.8.4 Add `# Validates: [AI-10.3]` to stop-loss/take-profit optimization tests
- [x] 2.8.5 Add `# Validates: [AI-10.5.x]` to integration point tests
- [x] 2.8.6 Add `# Validates: [AI-10.7.x]` to qualitative analysis tests
- [x] 2.8.7 Add `# Validates: [AI-10.8.x]` to orchestration tests

### 2.9 Traceability Comment Audit - JSON Brief Schema ✅
- [x] 2.9.1 Add `# Validates: [JSON-11.1]` to meta field tests
- [x] 2.9.2 Add `# Validates: [JSON-11.2]` to strategy_params tests
- [x] 2.9.3 Add `# Validates: [JSON-11.3]` to overall_performance tests
- [x] 2.9.4 Add `# Validates: [JSON-11.5]` to equity_stats tests
- [x] 2.9.5 Add `# Validates: [JSON-11.6]` to distribution tests
- [x] 2.9.6 Add `# Validates: [JSON-11.7]` to streaks tests
- [x] 2.9.7 Add `# Validates: [JSON-11.8]` to holding_time tests
- [x] 2.9.8 Add `# Validates: [JSON-11.9]` to costs tests
- [x] 2.9.9 Add `# Validates: [JSON-11.10]` to exposure tests
- [x] 2.9.10 Add `# Validates: [JSON-11.11]` to regimes tests
- [x] 2.9.11 Add `# Validates: [JSON-11.12]` to data_quality tests
- [x] 2.9.12 Add `# Validates: [JSON-11.14]` to environment tests
- [x] 2.9.13 Add `# Validates: [JSON-11.15]` to trades array tests
- [x] 2.9.14 Add `# Validates: [JSON-11.16]` to skipped_trades tests
- [x] 2.9.15 Add `# Validates: [JSON-11.18]` to monte_carlo tests
- [x] 2.9.16 Add `# Validates: [JSON-11.19]` to walk_forward tests
- [x] 2.9.17 Add `# Validates: [JSON-11.26]` to checksums tests
- [x] 2.9.18 Add `# Validates: [JSON-11.28]` to artifacts tests
- [x] 2.9.19 Add `# Validates: [JSON-11.29]` to signal_quality_analysis tests
- [x] 2.9.20 Add `# Validates: [JSON-11.30]` to trade object schema tests

### 2.10 Data Sync Service Tests (DH-2.14-2.19) ✅
- [x] 2.10.1 Create `tests/data/test_dukascopy_sync_service.py`
- [x] 2.10.2 Add test for DH-2.14 (core sync functionality)
- [x] 2.10.3 Add test for DH-2.15 (executable interface with CLI args)
- [x] 2.10.4 Add test for DH-2.16.1 (automatic date range detection)
- [x] 2.10.5 Add test for DH-2.16.2 (end date = yesterday UTC)
- [x] 2.10.6 Add test for DH-2.17.1 (incremental file storage)
- [x] 2.10.7 Add test for DH-2.17.2 (filename convention)
- [x] 2.10.8 Add test for DH-2.18.1 (unified data loading)
- [x] 2.10.9 Add test for DH-2.18.2 (no duplicate entries)
- [x] 2.10.10 Add test for DH-2.19 (service logging)
- [x] 2.10.11 Add all `# Validates: [DH-2.x]` comments

### 2.11 Public API Import Enforcement ✅
- [x] 2.11.1 Create `tests/core/test_import_boundaries.py`
- [x] 2.11.2 Add test for SYS-1.2.2 (no direct sub-module imports)
- [x] 2.11.3 Implement static analysis to check import patterns
- [x] 2.11.4 Create allowlist for legitimate internal imports
- [x] 2.11.5 Add `# Validates: [SYS-1.2.2]` comment
- [x] 2.11.6 Add to pre-commit hooks

---

## 3. Low Priority Tasks

### 3.1 Missing Explicit Tests

#### 3.1.1 Data Handler
- [ ] 3.1.1.1 Create explicit test for DH-2.9 (chunked loading) if not exists
- [ ] 3.1.1.2 Create explicit test for DH-2.10 (Parquet caching) if not exists

#### 3.1.2 RMM
- [ ] 3.1.2.1 Create explicit test for RMM-4.7 (hysteresis)
- [ ] 3.1.2.2 Add test for regime transition smoothing
- [ ] 3.1.2.3 Add test for confidence threshold hysteresis

#### 3.1.3 Execution Layer
- [ ] 3.1.3.1 Create test for EL-8.4 (API connectivity/retries)
- [ ] 3.1.3.2 Create test for EL-8.6 (live stream handling)
- [ ] 3.1.3.3 Create test for EL-8.7 (structured logging)

### 3.2 Documentation Updates
- [ ] 3.2.1 Update `docs/testing_guide.md` with traceability best practices
- [ ] 3.2.2 Create `docs/requirement_to_test_map.md` (auto-generated)
- [ ] 3.2.3 Update `CONTRIBUTING.md` with requirement validation rules
- [ ] 3.2.4 Create `docs/coverage_dashboard.md` template

### 3.3 Test Infrastructure Improvements
- [ ] 3.3.1 Create test registry database (SQLite)
- [ ] 3.3.2 Build requirement → test mapping tool
- [ ] 3.3.3 Create CI job to validate all requirements have tests
- [ ] 3.3.4 Create coverage report generator
- [ ] 3.3.5 Add requirement coverage badge to README

### 3.4 Test Organization Refactoring
- [ ] 3.4.1 Align test directory structure with requirements modules
- [ ] 3.4.2 Create subdirectories for each requirement category
- [ ] 3.4.3 Move orphaned tests to appropriate locations
- [ ] 3.4.4 Update import paths after reorganization

### 3.5 Orphaned Test Review
- [ ] 3.5.1 Identify all tests without `# Validates:` comments
- [ ] 3.5.2 Map each to a requirement or mark as utility test
- [ ] 3.5.3 Document utility tests separately
- [ ] 3.5.4 Archive or remove truly orphaned tests

### 3.6 Coverage Measurement
- [ ] 3.6.1 Run pytest-cov to measure current coverage percentage
- [ ] 3.6.2 Generate coverage report for each module
- [ ] 3.6.3 Identify functions with 0% coverage
- [ ] 3.6.4 Create action plan for 100% coverage
- [ ] 3.6.5 Add coverage gates to CI/CD

### 3.7 Pre-existing Test Failures
- [ ] 3.7.1 Fix `test_eval_pred_known_conditions` (cross_above support)
- [ ] 3.7.2 Fix `test_eval_pred_unknown_condition_defaults_false`
- [ ] 3.7.3 Fix `test_rmm_engine_project_to_index_with_daily_data`
- [ ] 3.7.4 Fix `test_rmm_engine_classify_daily_end_to_end`

---

## 4. Verification & Validation

### 4.1 Final Requirements Check
- [ ] 4.1.1 Re-run full requirements check
- [ ] 4.1.2 Verify traceability rate > 90%
- [ ] 4.1.3 Verify all high-priority gaps addressed
- [ ] 4.1.4 Update REQUIREMENTS_CHECK_REPORT.md with final results

### 4.2 Test Suite Health
- [ ] 4.2.1 Run full test suite and verify all pass
- [ ] 4.2.2 Measure total test execution time
- [ ] 4.2.3 Identify and fix slow tests
- [ ] 4.2.4 Ensure no flaky tests exist

### 4.3 Documentation
- [ ] 4.3.1 Update README with test coverage metrics
- [ ] 4.3.2 Document any deprecated requirements
- [ ] 4.3.3 Update architecture diagrams if needed
- [ ] 4.3.4 Create requirements traceability matrix

---

## Progress Tracking

**Overall Progress**: 106 / 150+ tasks completed (70.7%)

**By Priority**:
- High Priority: 35 / 35 completed (100%) ✅
- Medium Priority: 71 / 75 completed (94.7%) ✅
- Low Priority: 0 / 35 completed (0%)
- Verification: 0 / 10 completed (0%)

**Last Updated**: 2025-10-02

## Summary of Completed Work

### ✅ High Priority Tasks (ALL COMPLETE)

**1.1 RMM Test Coverage** - COMPLETED
- Created comprehensive lookahead bias prevention tests
- Created side mapping fix tests for non-directional labels
- Updated existing test to reflect Bug #1 fix
- All 4 new tests passing

**1.2 Entry Window State Management Tests** - COMPLETED
- Created `tests/portfolio/test_entry_window_management.py`
- 14 comprehensive tests covering all PM-5.8.x requirements
- Validates bar index tracking, entry occurrence, window policies, persistence
- Validates state serialization for live trading
- All tests passing

**1.3 Performance Benchmark Tests** - COMPLETED
- Created `tests/performance/test_performance_benchmarks.py`
- Benchmarks for vectorized operations (SYS-1.9.1)
- Benchmarks for laptop/Colab processing (SYS-1.9.2)
- Memory profiling tests (conditional on psutil)
- Indicator computation speed tests
- Backtest execution time tests (1M bars target)
- All validation comments added

**1.4 Traceability Comment Audit - System-Wide** - COMPLETED
- Added validation comments to runconfig tests (SYS-1.1.2, SYS-1.7.3)
- Added validation comments to utils tests (SYS-1.3.5)
- Added validation comments to comparison tests (SYS-1.4.x)
- Added validation comments to forex/timestamp tests (SYS-1.8.x)
- All System-Wide requirements now have traceability

---

## Notes

- Tasks marked with ✅ in section 1.1 were completed during initial requirements check
- Focus on high-priority tasks first (Sections 1.2-1.4)
- Medium-priority tasks (Section 2) are primarily traceability comment additions
- Low-priority tasks (Section 3) are infrastructure and quality-of-life improvements
- All tasks should include running tests to verify no regressions
