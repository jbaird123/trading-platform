# Fix Defensive Programming Anti-Patterns (Risk-Based Ordering)

This document outlines the systematic remediation of defensive programming patterns that silently hide errors throughout the codebase.

**Context:** Audit revealed 13 files with broad exception catching, 5 files with silent failures, and insufficient error logging that may be hiding bugs.

**Branch:** Create a feature branch for this work:
```bash
git checkout -b fix/defensive-code-antipatterns
```

**IMPORTANT:** Tasks are ordered by risk and impact, not sequential phase numbers. Execute in the order presented for maximum value delivery.

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

## Sprint 1: Critical Risks & Foundation (Days 1-2)

### 1. [X] Create Exception Handling Policy Document
- **Priority:** CRITICAL - Establishes principles for all subsequent work
- **Estimated Time:** 30-60 minutes
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

### 2. [X] INVESTIGATE backtester/core.py exception handling
- **Priority:** CRITICAL - Potential data corruption bug
- **Risk Level:** ⚠️ HIGHEST - Could be hiding data corruption RIGHT NOW
- **Estimated Time:** 1-2 hours investigation
- **Current:** Line with `continue` on exception needs investigation
- **Action:**
  - Locate the exact exception handler in backtester/core.py
  - Determine if this is hiding data corruption bugs
  - Understand what data is being skipped and why
  - Either add validation earlier or log/raise here
  - Document findings before implementing fix
- **Test:** Add test for malformed data handling
- **Acceptance:** No silent data corruption possible

### 3. [X] DECIDE + Fix core/run.py - Monte Carlo failure handling
- **Priority:** HIGH - User-requested feature failing silently
- **Risk Level:** HIGH - Users expecting MC results, getting incomplete analysis
- **Estimated Time:** 1 hour (decision + implementation)
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

### 4. [X] DECIDE + Fix core/run.py - Parameter search failure handling
- **Priority:** HIGH - User-requested feature failing silently
- **Risk Level:** HIGH - Users expecting optimization results, getting incomplete analysis
- **Estimated Time:** 1 hour (decision + implementation)
- **Current:** `except Exception: ps_summary = None` (silent)
- **Question:** If user explicitly requests parameter search in config, should failure be fatal?
- **Option A - FAIL FAST (recommended):** Remove try/catch, let exception propagate
  - Rationale: User requested optimization results, incomplete results are misleading
- **Option B - LOG AND CONTINUE:** Add loud error, return exit code 1
- **Decision Required:** Review with team - default to Option A per "Fail Fast" principle
- **Test:** `tests/core/test_run_error_handling.py::test_parameter_search_failure_handling`
- **Acceptance:** Behavior matches team decision

---

## Sprint 2: Silent Failures - Quick Wins (Days 3-4)

### 5. [X] Fix cli.py - Save prices.csv failure (line ~450)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
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

### 6. [X] Fix cli.py - Save features failure (line ~455)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
- **Current:** Silent `except Exception: pass`
- **Action:** Add `logger.warning(f"Failed to save features: {e}")`
- **Justification:** SAFE - features.json is for charts/debugging, not required for analysis
- **Test:** `tests/cli/test_cli_error_handling.py::test_features_save_failure_logged`
  - Mock feature save to raise exception
  - Verify warning logged
- **Acceptance:** Test passes, warning appears in logs

### 7. [X] Fix cli.py - Signals parquet save failure (line ~470)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
- **Current:** Silent `except Exception: pass` with pragma comment
- **Action:**
  - Add `logger.warning(f"Failed to save signals.parquet for AI Lab: {e}")`
  - Keep as optional (AI Lab can function without it)
- **Justification:** SAFE - signals.parquet is for AI Lab post-analysis, not required for backtest
- **Test:** `tests/cli/test_cli_error_handling.py::test_signals_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 8. [X] Fix cli.py - RMM spans save failure (line ~690)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
- **Current:** Silent `except Exception: pass` with pragma comment
- **Action:** Add `logger.warning(f"Failed to save RMM spans for chart: {e}")`
- **Justification:** SAFE - RMM spans are for chart visualization only, RMM data is in brief.json
- **Test:** `tests/cli/test_cli_error_handling.py::test_rmm_spans_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 9. [X] Fix cli.py - Processed data parquet save failure (line ~250)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
- **Current:** Silent `except Exception: pass`
- **Action:** Add `logger.warning(f"Failed to save processed_data.parquet: {e}")`
- **Justification:** SAFE - processed_data.parquet is for AI Lab, not required for backtest
- **Test:** `tests/cli/test_cli_error_handling.py::test_processed_data_save_failure_logged`
- **Acceptance:** Test passes, warning logged

### 10. [X] Fix core/run.py - CSV export failure (parameter_search_results.csv)
- **Priority:** MEDIUM - Silent failure, easy fix
- **Estimated Time:** 15 minutes
- **Current:** `except Exception: pass` (silent)
- **Action:** Add `logger.warning(f"Failed to export parameter search CSV: {e}")`
- **Justification:** SAFE - CSV is convenience export, data exists in brief.json
- **Test:** `tests/core/test_run_error_handling.py::test_param_search_csv_export_logged`
- **Acceptance:** Test passes, warning logged

### 11. [X] Fix cli.py - Git commit hash failure handling
- **Priority:** LOW - Metadata only, but should log
- **Estimated Time:** 15 minutes
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

### 12. [X] Fix reporting/chart_export.py - Silent pass
- **Priority:** MEDIUM - Silent failure in reporting
- **Estimated Time:** 30 minutes
- **Location:** Find silent `except: pass` in chart export
- **Action:** Add appropriate logging (likely warning level)
- **Test:** Create test verifying chart export failures are logged
- **Acceptance:** Test passes, no silent failures remain

### 13. [ ] Create Test Utilities for Exception Verification
- **Priority:** MEDIUM - Needed for remaining test development
- **Estimated Time:** 30 minutes
- **File:** `tests/conftest.py` (add fixtures)
- **Content:**
  - `assert_logs_warning(caplog, pattern)` helper
  - `assert_logs_error(caplog, pattern)` helper
  - `assert_prints_to_stderr(capsys, pattern)` helper
- **Acceptance:** Helpers available for use in subsequent tests

---

## Sprint 3: High-Risk File Reviews (Days 5-6)

### 14. [X] Review data/loader.py exception handling
- **Priority:** HIGH - Data loading is critical path
- **Risk Level:** HIGH - Silent data load failures could corrupt results
- **Estimated Time:** 1 hour
- **Action:** Review data loading exception handling
- **Critical:** Data load failures must be visible
- **Apply "Fail Fast" principle:** If ANY doubt about data integrity, must fail
- **Acceptance:** No silent data loading failures

### 15. [ ] Review regime_market_manager/engine.py exception handling
- **Priority:** HIGH - RMM affects trading decisions
- **Risk Level:** HIGH - Silent RMM failures could cause wrong trades
- **Estimated Time:** 1 hour
- **Action:** Review regime classification exception handling
- **Critical:** RMM failures should be visible (affects trading decisions)
- **Apply "Fail Fast" principle:** Trading decisions require certainty
- **Acceptance:** RMM errors are surfaced appropriately

### 16. [ ] Review core/sweeps.py exception handling
- **Priority:** MEDIUM - User-requested analysis features
- **Estimated Time:** 1 hour
- **Action:** Review Monte Carlo/walk-forward exception handling
- **Required:** User-visible errors for requested analyses
- **Acceptance:** All analysis failures are logged/reported

### 17. [ ] Review reporting/analytics.py exception handling
- **Priority:** MEDIUM - Functions returning None on exception
- **Estimated Time:** 45 minutes
- **Focus:** Functions returning None on exception
- **Action:** Ensure all have logging, especially if user-requested
- **Acceptance:** No silent None returns

### 18. [ ] Review reporting/brief.py exception handling
- **Priority:** MEDIUM - Core reporting functionality
- **Estimated Time:** 45 minutes
- **Action:** Review all `except Exception:` blocks
- **Required:** Each must either:
  - Log at appropriate level (error/warning/debug), OR
  - Re-raise with context, OR
  - Have documented justification in comment
- **Test:** Add tests for any new logging added
- **Acceptance:** All exceptions have visible handling

### 19. [ ] Review regime_market_manager/config.py exception handling
- **Priority:** MEDIUM - Config validation is important
- **Estimated Time:** 30 minutes
- **Action:** Review config validation exception handling
- **Apply "Fail Fast" principle:** Invalid config should fail immediately
- **Acceptance:** Config errors are clear and actionable

---

## Sprint 4: Infrastructure & Remaining Reviews (Week 2)

### 20. [ ] Add Linting Configuration for Exception Handling
- **Priority:** MEDIUM - Prevents future violations
- **Estimated Time:** 1 hour
- **File:** `pyproject.toml` (ruff configuration section)
- **Action:** Add rules to warn on:
  - Bare `except:` clauses (already forbidden, verify rule exists)
  - `except Exception:` without logging
  - `pass` in exception handlers without comments
- **Test:** Run linter on codebase, verify new warnings appear
- **Acceptance:** Linting rules configured and documented

### 21. [ ] Create Exception Tracking Utilities
- **Priority:** MEDIUM - Useful for standardization
- **Estimated Time:** 1 hour
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

### 22. [ ] Review core/demo.py exception handling
- **Priority:** LOW - Developer tool, lower impact
- **Estimated Time:** 30 minutes
- **Action:** Review demo generation exception handling
- **Lower priority:** Demo is developer tool, but should still log
- **Acceptance:** No silent failures in demo generation

### 23. [ ] Review reporting/chart_export.py exception handling (comprehensive)
- **Priority:** LOW - Beyond task 12, comprehensive review
- **Estimated Time:** 45 minutes
- **Action:** Review all chart export exception handling beyond task 12
- **Acceptance:** Chart failures degrade gracefully with logging

### 24. [ ] Review reporting/html_export.py exception handling
- **Priority:** LOW - Reporting feature
- **Estimated Time:** 30 minutes
- **Action:** Review HTML report generation exception handling
- **Acceptance:** HTML generation failures are logged

### 25. [ ] Review core/config.py exception handling
- **Priority:** MEDIUM - Config parsing is important
- **Estimated Time:** 30 minutes
- **Action:** Review config parsing exception handling
- **Already has:** 1 logger call, verify coverage complete
- **Apply "Fail Fast" principle:** Config parsing errors should be clear
- **Acceptance:** Config errors are clear

### 26. [ ] Review ai/inference_client.py exception handling
- **Priority:** LOW - Already has logging
- **Estimated Time:** 30 minutes
- **Action:** Review existing logging (already has 10 log calls)
- **Likely:** Already well-handled, verify completeness
- **Acceptance:** AI inference errors are appropriately logged

### 27. [ ] Review ai/serving/app.py and deployment_manager.py
- **Priority:** LOW - Already has logging
- **Estimated Time:** 30 minutes
- **Action:** Review AI serving exception handling
- **Already have:** Multiple logger calls (3-5 each)
- **Likely:** Well-handled, verify completeness
- **Acceptance:** AI serving errors are logged

---

## Sprint 5: Observability & Testing (Week 2)

### 28. [ ] Add exception metrics tracking
- **Priority:** MEDIUM - Enables monitoring
- **Estimated Time:** 1-2 hours
- **File:** `src/trading_platform/core/metrics.py` (or create)
- **Content:**
  - Counter for "optional feature failures" by feature name
  - Counter for "degraded runs" (runs with any optional failures)
- **Integration:** Add to decorators from task 21
- **Acceptance:** Metrics can be queried for monitoring

### 29. [ ] Create exception summary in brief.json
- **Priority:** MEDIUM - Provides run quality tracking
- **Estimated Time:** 1 hour
- **File:** `src/trading_platform/reporting/brief.py`
- **Action:** Add optional `degraded_features` field to brief
  - List of features that failed during run
  - Allows post-analysis of run quality
- **Test:** `tests/reporting/test_brief.py::test_degraded_features_tracked`
- **Acceptance:** Failed optional features appear in brief.json

### 30. [ ] Add development mode strict checking
- **Priority:** LOW - Developer convenience
- **Estimated Time:** 1 hour
- **File:** `src/trading_platform/core/config.py`
- **Action:** Add `STRICT_MODE` environment variable
  - When set, optional feature failures become errors
  - Helps developers catch issues early
- **Test:** Verify strict mode converts warnings to exceptions
- **Acceptance:** `STRICT_MODE=1` makes all failures visible

### 31. [ ] Run comprehensive test suite
- **Priority:** HIGH - Validates all changes
- **Estimated Time:** 30 minutes (runtime + fixes)
- **Action:** Execute `poetry run pytest` with all new tests
- **Required:** All 1307+ tests pass
- **Required:** New error handling tests pass
- **Acceptance:** Full test suite green

### 32. [ ] Run linter with new rules
- **Priority:** HIGH - Validates compliance
- **Estimated Time:** 30 minutes (runtime + fixes)
- **Action:** Execute `poetry run ruff check src/`
- **Required:** No new exception handling violations
- **Action:** Fix any violations found
- **Acceptance:** Linter clean

### 33. [ ] Manual verification of critical paths
- **Priority:** HIGH - Real-world validation
- **Estimated Time:** 1 hour
- **Action:** Run backtest with intentional failures:
  - Invalid strategy file → should fail fast with clear error
  - Missing data file → should fail fast with clear error
  - Invalid REM config → should fail fast with clear error
  - Chart export failure → should warn but continue
- **Acceptance:** Error messages are clear and actionable

---

## Sprint 6: Documentation (Week 2-3)

### 34. [ ] Update CONTRIBUTING.md with exception handling guidelines
- **Priority:** MEDIUM - Helps future contributors
- **Estimated Time:** 30 minutes
- **File:** `CONTRIBUTING.md` (or create)
- **Content:**
  - Link to exception handling policy (task 1)
  - Quick reference for common patterns
  - Examples of good vs bad exception handling
- **Acceptance:** Guidelines documented for contributors

### 35. [ ] Add exception handling section to testing guide
- **Priority:** MEDIUM - Improves test quality
- **Estimated Time:** 45 minutes
- **File:** `docs/testing_guide.md`
- **Action:** Add section on testing error paths
  - How to verify errors are surfaced
  - How to test degraded functionality
  - Examples using test utilities from task 13
- **Acceptance:** Testing guide includes error testing

### 36. [ ] Create migration guide for existing exception handlers
- **Priority:** LOW - Reference material
- **Estimated Time:** 45 minutes
- **File:** `docs/code_tasks/exception_handler_migration_guide.md`
- **Content:**
  - Checklist for reviewing existing exception handlers
  - Before/after examples for each pattern
  - Common pitfalls to avoid
- **Acceptance:** Guide helps future refactoring

### 37. [ ] Update changelog and documentation
- **Priority:** MEDIUM - User communication
- **Estimated Time:** 30 minutes
- **File:** `CHANGELOG.md` (or equivalent)
- **Action:** Document exception handling improvements
- **File:** `docs/project_requirements.md`
- **Action:** Add error handling requirements if not present
- **Acceptance:** Changes documented for users

---

## Future Improvements (Optional)

These are enhancements beyond the immediate remediation:

### 38. [ ] Add structured logging for errors
- **Priority:** OPTIONAL - Nice to have
- **Estimated Time:** 2-3 hours
- **Action:** Use structured logging (JSON) for errors
- **Benefit:** Machine-parseable error tracking
- **Acceptance:** Errors can be queried programmatically

### 39. [ ] Add error recovery suggestions
- **Priority:** OPTIONAL - Improves UX
- **Estimated Time:** 2-3 hours
- **Action:** Enhance error messages with "how to fix" suggestions
- **Example:** "FileNotFoundError: strategy.yaml → Check 'strategy_path' in config"
- **Acceptance:** Error messages include actionable guidance

### 40. [ ] Create error catalog
- **Priority:** OPTIONAL - Long-term value
- **Estimated Time:** 3-4 hours
- **File:** `docs/troubleshooting/error_catalog.md`
- **Content:** Common errors and solutions
- **Benefit:** Self-service troubleshooting for users
- **Acceptance:** Top 20 errors documented with solutions

---

## Execution Strategy

### Sprint Breakdown:

**Sprint 1 (Days 1-2): Critical Risks**
- Tasks 1-4: Policy + highest risk items (backtester, MC, PS)
- **Goal:** Stop potential data corruption, fix user-visible failures
- **Deliverable:** Policy doc + 3-4 critical fixes with tests

**Sprint 2 (Days 3-4): Silent Failures**
- Tasks 5-13: All silent pass/return None patterns
- **Goal:** Visibility into all degraded runs
- **Deliverable:** 8-9 logging additions with tests

**Sprint 3 (Days 5-6): High-Risk Reviews**
- Tasks 14-19: Data loader, RMM, sweeps, analytics
- **Goal:** Review critical-path exception handling
- **Deliverable:** 6 file reviews with fixes/tests as needed

**Sprint 4 (Week 2): Infrastructure + Remaining**
- Tasks 20-27: Linting, decorators, lower-priority reviews
- **Goal:** Systematize and complete coverage
- **Deliverable:** Linting rules + 8 file reviews

**Sprint 5 (Week 2): Observability**
- Tasks 28-33: Metrics, brief.json, validation
- **Goal:** Make errors observable and validate all changes
- **Deliverable:** Metrics + full test suite passing

**Sprint 6 (Week 2-3): Documentation**
- Tasks 34-37: CONTRIBUTING, testing guide, changelog
- **Goal:** Document learnings and patterns
- **Deliverable:** Complete documentation

**Future (As Needed):**
- Tasks 38-40: Optional enhancements

### Key Differences from Sequential Ordering:

1. **Task 2 (backtester) moved from Phase 3 → Sprint 1** (potential data corruption)
2. **Tasks 3-4 (MC/PS) moved from Phase 2 → Sprint 1** (high user impact)
3. **Task 13 (test utilities) moved from Phase 1 → Sprint 2** (needed after first tests written)
4. **Tasks 20-21 (linting/decorators) moved from Phase 1 → Sprint 4** (patterns clear after fixes)
5. **High-risk reviews (data, RMM) prioritized** over low-risk reviews (AI serving)

### Success Criteria:

1. ✅ Zero silent `except: pass` statements without logging
2. ✅ All `except Exception:` blocks have logging or justification
3. ✅ User-requested features (MC, WF, PS) report failures visibly
4. ✅ Critical paths (strategy load, data load) fail fast with clear errors
5. ✅ Optional features (charts, exports) degrade gracefully with warnings
6. ✅ All tests pass (1307+ existing + new error handling tests)
7. ✅ Exception handling policy documented and enforced by linting

### Total Effort Estimate:

- **Sprint 1-2:** 3-4 days (critical + quick wins)
- **Sprint 3-4:** 3-4 days (reviews + infrastructure)
- **Sprint 5-6:** 2-3 days (observability + docs)
- **Total:** 8-11 days for tasks 1-37
- **Optional:** 1-2 additional days for tasks 38-40

---

**Note:** This is a systematic refactoring affecting error handling across the entire codebase. Each change should be small, tested, and committed independently to facilitate review and potential rollback if needed.

**The risk-based ordering ensures maximum value delivery in minimum time, addressing critical bugs and user-visible failures first, then systematizing the approach.**
