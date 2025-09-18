# Combined Requirements Check (Gemini & Codex)

_Last updated: 2025-09-18_

This document combines the findings from the requirements checks performed by Gemini and Codex.

## Gemini Findings

This section summarizes the findings from the `docs/requirements_check_gemini.md` file.

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

## Codex Findings

This section summarizes the findings from the `docs/requirements_check_codex.md` file.

### Summary
- SE vs REM separation is respected. REM is used by BT first per policy.
- Unified `RunConfig` is in use and snapshotted in briefs/CLI.
- Reporting is rich; many brief sections validated by tests.
- Gaps: structured exit context, RunConfig JSON Schema, a few placeholders.

### Coverage Highlights (by area)
- System (SYS): boundaries, blackout policy, compare flows covered by tests.
- Data (DH): schema, resample, feature pipeline tests are present.
- Strategy (SE): schema, indicators, YAML rules, params verified.
- RMM: rule engine + schema validated; daily engine test lacks tag.
- Portfolio (PM): state, PnL, metrics, R multiple, risk caps covered.
- REM: component exists, precedence enforced; no REM schema validation.
- Backtester (BT): core loop, warmup, costs, tie-break, skips/counterfactuals.
- Execution (EL): OANDA adapter stubs, controller, policies under tests.
- Reporting (RV): brief sections, costs, exposure, regimes, HTML compare.

### Discrepancies
- Structured REM exit context (traceability):
  - Intent: `[JSON-11.25]` requires enhanced trade context.
  - Current: `exit_reason` is a string (e.g., "stop-loss").
  - Impact: Limits AI analysis and provenance.
  - Action: Add `exit_context` dict on Trade + brief, keep string for compat.
- RunConfig JSON Schema:
  - `[SYS-1.7.3]` calls for a formal schema. None present, no tests.
- Brief placeholders not populated:
  - `contrasts` `[JSON-11.14]`, `stop_tp_candidates` `[JSON-11.16]`.
- REM config schema:
  - `[REM-6.2]` requires schema-validated YAML. No `rem.schema.json` yet.

### Requirements lacking tests (prioritized)
- `[SYS-1.7.3]` RunConfig JSON Schema + validation.
- `[JSON-11.14]` contrasts population logic/tests (or explicit deferral test).
- `[JSON-11.16]` stop_tp_candidates from MFE/MAE (or deferral test).
- `[REM-6.2]` REM config schema validation.

### Orphaned tests (missing "Validates:" tag)
- `tests/backtester/test_rmm_enforcement.py` (RMM gating/BT policy).
- `tests/data/test_data_catalog_loader.py` (DH catalog loading).
- `tests/strategy/test_strategy_parameter_substitution.py` (SE params).
- `tests/regime_market_manager/test_rmm_engine_daily.py` (RMM engine).
- `tests/execution/test_dummy_file.py` (housekeeping or tag/remove).

### Architecture & Invariants
- SE vs REM separation: aligned; strategy contains no risk block.
- Canonical-first: PM/costs use canonical units. No Rule Translator yet.
- Exit precedence `[BT-7.16]`: REM exits checked before strategy exits.

### Recommendations (next steps)
1) Add non-breaking `exit_context` for REM exits; test brief inclusion.
2) Add `docs/schemas/run_config.schema.json` + validation tests.
3) Add `docs/schemas/rem.schema.json` + loader/validation tests.
4) Tag the orphaned tests with matching requirement IDs.
5) Decide on contrasts/stop_tp_candidates: implement or mark deferred.

## Disagreements and Analysis

This section highlights the differences between the Gemini and Codex reports.

### 1. Report Format

- **Gemini**: Provided a detailed, requirement-by-requirement breakdown in a tabular format, showing the status, evidence, and notes for each.
- **Codex**: Provided a more narrative, summary-style report, highlighting key findings, discrepancies, and recommendations.

**Analysis**: The Gemini format is more granular and provides a clear traceability link for each requirement. The Codex format is more concise and easier to read for a high-level overview.

### 2. Risk & Exit Manager (REM) Coverage

- **Gemini**: I reported that there are **no tests** for any of the REM requirements, which I identified as a major gap.
- **Codex**: Stated that the "REM component exists, precedence enforced; no REM schema validation." This implies some level of testing for the REM's existence and precedence logic.

**Analysis**: I disagree with Codex's assessment. My search for `REM-` tags in the test files returned no results. While the REM component may exist and its precedence may be enforced by the backtester, there are no specific tests that validate the REM's own requirements (e.g., `[REM-6.1]`, `[REM-6.2]`, `[REM-6.3]`, `[REM-6.4]`). My finding of a major gap in REM test coverage is more accurate.

### 3. Orphaned Tests

- **Gemini**: I did not find any obvious orphaned tests but noted that a more thorough analysis would be needed.
- **Codex**: Identified several specific orphaned tests (tests without a `Validates:` tag).

**Analysis**: Codex's finding is more specific and actionable here. I agree with the assessment that these tests should be tagged with the appropriate requirement IDs.

### 4. Recommendations

- **Gemini**: My recommendations were broader, focusing on prioritizing tests for entire modules (REM, DH) and improving traceability.
- **Codex**: Provided more specific, code-level recommendations, such as adding an `exit_context` dictionary and creating specific JSON schemas.

**Analysis**: The recommendations from both models are valuable. My recommendations are more strategic, while Codex's are more tactical. A combination of both would be ideal.

### 5. Overall Assessment

- **Gemini**: My report is more of a detailed audit of the test coverage against the requirements.
- **Codex**: Codex's report is more of a high-level review with specific, actionable recommendations.

**Conclusion**: Both reports provide value. My detailed, requirement-by-requirement analysis is useful for a comprehensive understanding of test coverage, while Codex's summary and specific recommendations are helpful for prioritizing the next steps. The combined report provides a more complete picture than either report alone.
