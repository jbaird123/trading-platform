# Fix Defensive Programming Anti-Patterns

This document outlines the systematic remediation of defensive programming patterns that silently hide errors throughout the codebase.

**Context:** Audit revealed 13 files with broad exception catching, 5 files with silent failures, and insufficient error logging that may be hiding bugs.

**Branch:** Create a feature branch for this work:
```bash
git checkout -b fix/defensive-code-antipatterns
```

Execute tasks in order. Each fix should include tests verifying errors are properly surfaced.

---

## ⚠️ CRITICAL PRINCIPLE: FAIL FAST BY DEFAULT ⚠️

**Golden Rule:** When in doubt, FAIL LOUDLY rather than log/warn.

- **Default action:** Let exceptions propagate (fail fast)
- **Only catch and log/warn when:** You have 100% certainty there is NO adverse effect
- **If ANY doubt exists:** The correct action is to FAIL LOUDLY with a clear error message

**Examples of certainty required for logging instead of failing:**
- ✅ **Safe to log:** Git commit hash for metadata - system works fine without it
- ✅ **Safe to log:** Chart generation - text reports are complete fallback
- ❌ **MUST FAIL:** Strategy compilation - uncertain downstream effects
- ❌ **MUST FAIL:** Data loading - uncertain if partial data corrupts results
- ❌ **MUST FAIL:** Feature calculation - uncertain if NaN propagation breaks logic
- ❌ **MUST FAIL:** Monte Carlo analysis - user explicitly requested it

**When reviewing exception handlers, ask:**
1. "Can the system produce correct results without this feature?"
2. "Is there any scenario where hiding this error causes incorrect behavior?"
3. "Would a user prefer a clear error over silent degradation?"

If the answer to #1 is "uncertain" or #2 is "yes" or #3 is "yes" → **FAIL FAST**

**Burden of proof:** The developer must PROVE it's safe to catch and log. If you cannot prove safety with 100% certainty, you MUST let the exception propagate.

---

## Key Decision Points

The following require team decisions before implementation (default to FAIL FAST):

1. **Task 10 - Monte Carlo Analysis Failure:** Fail fast or degrade gracefully?
   - Recommendation: **FAIL FAST** - user explicitly requested this analysis

2. **Task 11 - Parameter Search Failure:** Fail fast or degrade gracefully?
   - Recommendation: **FAIL FAST** - user explicitly requested optimization

3. **Task 17 - Backtester `continue` on Exception:** Investigate data corruption risk
   - Recommendation: Add validation or **FAIL FAST** if uncertain

All other tasks have clear safety assessments and can proceed without decisions.

---

## Phase 1: Foundation & Policy (4 tasks)

### 1. [ ] Create Exception Handling Policy Document
- **File:** `docs/coding_standards/exception_handling_policy.md`
- **Content:** Define project-wide rules for:
  - **CRITICAL:** "Fail Fast by Default" principle (see above) - this is the foundational rule
  - Burden of proof: Developer must prove 100% certainty of safety to catch exceptions
  - When `except Exception:` is allowed (extremely rare cases only)
  - Required logging for all exception handlers (when catching is justified)
  - Three-question test for determining fail vs log (see above)
  - Examples of PROVED safe patterns (git hash, chart generation)
  - Examples of MUST FAIL patterns (strategy compilation, data loading, user-requested analysis)
  - Rationale: Silent failures cause bugs that are extremely hard to diagnose
- **Acceptance:** Document reviewed and approved, includes "Fail Fast by Default" prominently

### 2. [ ] Add Linting Configuration for Exception Handling
- **File:** `pyproject.toml` (ruff configuration section)
- **Action:** Add rules to warn on:
  - Bare `except:` clauses (already forbidden, verify rule exists)
  - `except Exception:` without logging
  - `pass` in exception handlers without comments
- **Test:** Run linter on codebase, verify new warnings appear
- **Acceptance:** Linting rules configured and documented

### 3. [ ] Create Exception Tracking Utilities
- **File:** `src/trading_platform/core/exceptions.py`
- **Content:**
  - Create `@track_optional_feature(name)` decorator for optional features
  - Create `@require_success(feature_name)` decorator for critical paths
  - Both should log appropriately and integrate with existing logger
- **Test File:** `tests/core/test_exceptions.py`
- **Tests:**
  - Verify decorator logs warnings for optional feature failures
  - Verify decorator propagates exceptions for required features
  - Verify logged messages include feature name and exception details
- **Acceptance:** All tests pass, decorators ready for use

### 4. [ ] Create Test Utilities for Exception Verification
- **File:** `tests/conftest.py` (add fixtures)
- **Content:**
  - `assert_logs_warning(caplog, pattern)` helper
  - `assert_logs_error(caplog, pattern)` helper
  - `assert_prints_to_stderr(capsys, pattern)` helper
- **Acceptance:** Helpers available for use in subsequent tests

---

## Phase 2: Fix Critical Files (10 tasks)

### 5. [ ] Fix cli.py - Save prices.csv failure (line ~450)
- **Current:** Silent `except Exception: pass`
- **Action:**
  - Add `logger.warning(f"Failed to save prices.csv: {e}")`
  - Document that charts degrade gracefully without prices
- **Justification:** SAFE - prices.csv is only for interactive charts, brief.json has all data
- **Test:** `tests/cli/test_cli_error_handling.py::test_prices_save_failure_logged`
  - Mock `save_prices_csv` to raise IOError
  - Verify warning logged
  - Verify CLI still returns success (0)
- **Acceptance:** Test passes, warning appears in logs

### 6. [ ] Fix cli.py - Save features failure (line ~455)
- **Current:** Silent `except Exception: pass`
- **Action:** Add `logger.warning(f"Failed to save features: {e}")`
- **Justification:** SAFE - features.json is for charts/debugging, not required for analysis
- **Test:** `tests/cli/test_cli_error_handling.py::test_features_save_failure_logged`
  - Mock feature save to raise exception
  - Verify warning logged
- **Acceptance:** Test passes, warning appears in logs

### 7. [ ] Fix cli.py - Signals parquet save failure (line ~470)
- **Current:** Silent `except Exception: pass` with pragma comment
- **Action:**
  - Add `logger.warning(f"Failed to save signals.parquet for AI Lab: {e}")`
  - Keep as optional (AI Lab can function without it)
- **Justification:** SAFE - signals.parquet is for AI Lab post-analysis, not required for backtest
- **Test:** `tests/cli/test_cli_error_handling.py::test_signals_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 8. [ ] Fix cli.py - RMM spans save failure (line ~690)
- **Current:** Silent `except Exception: pass` with pragma comment
- **Action:** Add `logger.warning(f"Failed to save RMM spans for chart: {e}")`
- **Justification:** SAFE - RMM spans are for chart visualization only, RMM data is in brief.json
- **Test:** `tests/cli/test_cli_error_handling.py::test_rmm_spans_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 9. [ ] Fix cli.py - Processed data parquet save failure (line ~250)
- **Current:** Silent `except Exception: pass`
- **Action:** Add `logger.warning(f"Failed to save processed_data.parquet: {e}")`
- **Justification:** SAFE - processed_data.parquet is for AI Lab, not required for backtest
- **Test:** `tests/cli/test_cli_error_handling.py::test_processed_data_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 10. [ ] Fix core/run.py - Monte Carlo failure handling ⚠️ NEEDS DECISION
- **Current:** `except Exception: mc_summary = None` (silent)
- **Question:** If user explicitly requests Monte Carlo in config, should failure be fatal?
- **Option A - FAIL FAST (recommended):** Remove try/catch, let exception propagate
  - Rationale: User requested this analysis, they expect complete results
  - If MC fails, results are incomplete and potentially misleading
- **Option B - LOG AND CONTINUE:** Keep catch but add loud error notification
  - Add `logger.error(f"Monte Carlo analysis failed: {e}")`
  - Add `print(f"⚠️  Monte Carlo requested but failed: {e}", file=sys.stderr)`
  - Return exit code 1 to signal degraded run
- **Decision Required:** Review with team - default to Option A per "Fail Fast" principle
- **Test:** `tests/core/test_run_error_handling.py::test_monte_carlo_failure_handling`
  - Verify behavior matches chosen option
- **Acceptance:** Behavior matches team decision, thoroughly tested

### 11. [ ] Fix core/run.py - Parameter search failure handling ⚠️ NEEDS DECISION
- **Current:** `except Exception: ps_summary = None` (silent)
- **Question:** If user explicitly requests parameter search in config, should failure be fatal?
- **Option A - FAIL FAST (recommended):** Remove try/catch, let exception propagate
  - Rationale: User requested optimization results, incomplete results are misleading
- **Option B - LOG AND CONTINUE:** Add loud error, return exit code 1
- **Decision Required:** Review with team - default to Option A per "Fail Fast" principle
- **Test:** `tests/core/test_run_error_handling.py::test_parameter_search_failure_handling`
- **Acceptance:** Behavior matches team decision

### 12. [ ] Fix core/run.py - CSV export failure (parameter_search_results.csv)
- **Current:** `except Exception: pass` (silent)
- **Action:** Add `logger.warning(f"Failed to export parameter search CSV: {e}")`
- **Justification:** SAFE - CSV is convenience export, data exists in brief.json
- **Test:** `tests/core/test_run_error_handling.py::test_param_search_csv_export_logged`
- **Acceptance:** Test passes, warning logged

### 13. [ ] Fix cli.py - Git commit hash failure handling
- **Current:** `except Exception: return None` (silent)
- **Action:**
  - Add `logger.debug(f"Git commit hash unavailable: {e}")`
  - Return None (acceptable for this metadata)
- **Justification:** SAFE - git commit hash is metadata for provenance, system works without it
- **Test:** `tests/cli/test_cli_error_handling.py::test_git_commit_unavailable_logged`
  - Mock subprocess to raise exception
  - Verify debug log entry
  - Verify None returned
- **Acceptance:** Test passes, debug logged

### 14. [ ] Fix reporting/chart_export.py - Silent pass
- **Location:** Find silent `except: pass` in chart export
- **Action:** Add appropriate logging (likely warning level)
- **Test:** Create test verifying chart export failures are logged
- **Acceptance:** Test passes, no silent failures remain

---

## Phase 3: Review Broad Exception Catching (13 tasks)

For each file with `except Exception:`, review and add logging where missing.

### 15. [ ] Review reporting/brief.py exception handling
- **Action:** Review all `except Exception:` blocks
- **Required:** Each must either:
  - Log at appropriate level (error/warning/debug), OR
  - Re-raise with context, OR
  - Have documented justification in comment
- **Test:** Add tests for any new logging added
- **Acceptance:** All exceptions have visible handling

### 16. [ ] Review reporting/analytics.py exception handling
- **Focus:** Functions returning None on exception
- **Action:** Ensure all have logging, especially if user-requested
- **Acceptance:** No silent None returns

### 17. [ ] Review backtester/core.py exception handling
- **Critical:** Line with `continue` on exception needs investigation
- **Action:**
  - Determine if this is hiding data corruption bugs
  - Either add validation earlier or log/raise here
- **Test:** Add test for malformed data handling
- **Acceptance:** No silent data corruption possible

### 18. [ ] Review core/sweeps.py exception handling
- **Action:** Review Monte Carlo/walk-forward exception handling
- **Required:** User-visible errors for requested analyses
- **Acceptance:** All analysis failures are logged/reported

### 19. [ ] Review core/demo.py exception handling
- **Action:** Review demo generation exception handling
- **Lower priority:** Demo is developer tool, but should still log
- **Acceptance:** No silent failures in demo generation

### 20. [ ] Review regime_market_manager/engine.py exception handling
- **Action:** Review regime classification exception handling
- **Critical:** RMM failures should be visible (affects trading decisions)
- **Acceptance:** RMM errors are surfaced appropriately

### 21. [ ] Review data/loader.py exception handling
- **Action:** Review data loading exception handling
- **Critical:** Data load failures must be visible
- **Acceptance:** No silent data loading failures

### 22. [ ] Review regime_market_manager/config.py exception handling
- **Action:** Review config validation exception handling
- **Acceptance:** Config errors are clear and actionable

### 23. [ ] Review ai/inference_client.py exception handling
- **Action:** Review existing logging (already has 10 log calls)
- **Likely:** Already well-handled, verify completeness
- **Acceptance:** AI inference errors are appropriately logged

### 24. [ ] Review reporting/chart_export.py exception handling (continued)
- **Action:** Review all chart export exception handling beyond task 14
- **Acceptance:** Chart failures degrade gracefully with logging

### 25. [ ] Review reporting/html_export.py exception handling
- **Action:** Review HTML report generation exception handling
- **Acceptance:** HTML generation failures are logged

### 26. [ ] Review core/config.py exception handling
- **Action:** Review config parsing exception handling
- **Already has:** 1 logger call, verify coverage complete
- **Acceptance:** Config errors are clear

### 27. [ ] Review ai/serving/app.py and deployment_manager.py
- **Action:** Review AI serving exception handling
- **Already have:** Multiple logger calls (3-5 each)
- **Likely:** Well-handled, verify completeness
- **Acceptance:** AI serving errors are logged

---

## Phase 4: Add Observability (3 tasks)

### 28. [ ] Add exception metrics tracking
- **File:** `src/trading_platform/core/metrics.py` (or create)
- **Content:**
  - Counter for "optional feature failures" by feature name
  - Counter for "degraded runs" (runs with any optional failures)
- **Integration:** Add to decorators from task 3
- **Acceptance:** Metrics can be queried for monitoring

### 29. [ ] Create exception summary in brief.json
- **File:** `src/trading_platform/reporting/brief.py`
- **Action:** Add optional `degraded_features` field to brief
  - List of features that failed during run
  - Allows post-analysis of run quality
- **Test:** `tests/reporting/test_brief.py::test_degraded_features_tracked`
- **Acceptance:** Failed optional features appear in brief.json

### 30. [ ] Add development mode strict checking
- **File:** `src/trading_platform/core/config.py`
- **Action:** Add `STRICT_MODE` environment variable
  - When set, optional feature failures become errors
  - Helps developers catch issues early
- **Test:** Verify strict mode converts warnings to exceptions
- **Acceptance:** `STRICT_MODE=1` makes all failures visible

---

## Phase 5: Documentation & Guidelines (3 tasks)

### 31. [ ] Update CONTRIBUTING.md with exception handling guidelines
- **File:** `CONTRIBUTING.md` (or create)
- **Content:**
  - Link to exception handling policy (task 1)
  - Quick reference for common patterns
  - Examples of good vs bad exception handling
- **Acceptance:** Guidelines documented for contributors

### 32. [ ] Add exception handling section to testing guide
- **File:** `docs/testing_guide.md`
- **Action:** Add section on testing error paths
  - How to verify errors are surfaced
  - How to test degraded functionality
  - Examples using test utilities from task 4
- **Acceptance:** Testing guide includes error testing

### 33. [ ] Create migration guide for existing exception handlers
- **File:** `docs/code_tasks/exception_handler_migration_guide.md`
- **Content:**
  - Checklist for reviewing existing exception handlers
  - Before/after examples for each pattern
  - Common pitfalls to avoid
- **Acceptance:** Guide helps future refactoring

---

## Phase 6: Validation & Cleanup (4 tasks)

### 34. [ ] Run comprehensive test suite
- **Action:** Execute `poetry run pytest` with all new tests
- **Required:** All 1307+ tests pass
- **Required:** New error handling tests pass
- **Acceptance:** Full test suite green

### 35. [ ] Run linter with new rules
- **Action:** Execute `poetry run ruff check src/`
- **Required:** No new exception handling violations
- **Action:** Fix any violations found
- **Acceptance:** Linter clean

### 36. [ ] Manual verification of critical paths
- **Action:** Run backtest with intentional failures:
  - Invalid strategy file → should fail fast with clear error
  - Missing data file → should fail fast with clear error
  - Invalid REM config → should fail fast with clear error
  - Chart export failure → should warn but continue
- **Acceptance:** Error messages are clear and actionable

### 37. [ ] Update changelog and documentation
- **File:** `CHANGELOG.md` (or equivalent)
- **Action:** Document exception handling improvements
- **File:** `docs/project_requirements.md`
- **Action:** Add error handling requirements if not present
- **Acceptance:** Changes documented for users

---

## Phase 7: Future Improvements (Optional, 3 tasks)

These are enhancements beyond the immediate remediation:

### 38. [ ] Add structured logging for errors
- **Action:** Use structured logging (JSON) for errors
- **Benefit:** Machine-parseable error tracking
- **Acceptance:** Errors can be queried programmatically

### 39. [ ] Add error recovery suggestions
- **Action:** Enhance error messages with "how to fix" suggestions
- **Example:** "FileNotFoundError: strategy.yaml → Check 'strategy_path' in config"
- **Acceptance:** Error messages include actionable guidance

### 40. [ ] Create error catalog
- **File:** `docs/troubleshooting/error_catalog.md`
- **Content:** Common errors and solutions
- **Benefit:** Self-service troubleshooting for users
- **Acceptance:** Top 20 errors documented with solutions

---

## Summary Statistics

- **Total Tasks:** 40 (37 required, 3 optional)
- **Estimated Effort:**
  - Phase 1-2: 2-3 days (foundation + critical fixes)
  - Phase 3: 2-3 days (review all exception handlers)
  - Phase 4-7: 1-2 days (observability + documentation)
- **High Priority:** Tasks 5-14 (critical file fixes)
- **Medium Priority:** Tasks 15-27 (review existing handlers)
- **Low Priority:** Tasks 38-40 (future enhancements)

## Success Criteria

1. ✅ Zero silent `except: pass` statements without logging
2. ✅ All `except Exception:` blocks have logging or justification
3. ✅ User-requested features (MC, WF, PS) report failures visibly
4. ✅ Critical paths (strategy load, data load) fail fast with clear errors
5. ✅ Optional features (charts, exports) degrade gracefully with warnings
6. ✅ All tests pass (1307+ existing + new error handling tests)
7. ✅ Exception handling policy documented and enforced by linting

## Rollout Plan

1. Complete Phase 1 (foundation) first - establishes patterns
2. Tackle Phase 2 (critical fixes) next - highest user impact
3. Phase 3 (reviews) can be done incrementally, file by file
4. Phases 4-6 provide long-term maintainability
5. Phase 7 is optional but valuable for production systems

---

**Note:** This is a systematic refactoring affecting error handling across the entire codebase. Each change should be small, tested, and committed independently to facilitate review and potential rollback if needed.
