# Requirements Check — Combined (Gemini + Codex)

_Date: 2025-09-18_

## Purpose
- Merge findings from `docs/requirements_check_gemini.md` and
  `docs/requirements_check_codex.md` into a single view.
- Highlight consensus, fill gaps, and call out disagreements (with evidence).

## Combined Summary
- Architecture: Strategy (SE) and Risk & Exit Manager (REM) are decoupled;
  Backtester (BT) consults REM first per exit precedence. Unified `RunConfig`
  is used across CLI and core. Boundaries and blackout policy are enforced.
- Reporting: The JSON brief is comprehensive; many sections are validated by
  tests (overall performance, risk snapshot, equity, distribution, streaks,
  holding time, costs, exposure, regimes, skipped_trades/filter_impact,
  provenance, checksums, HTML/compare outputs).
- Gaps: Missing structured exit context for REM exits; no formal RunConfig
  JSON Schema; placeholders for `contrasts` and `stop_tp_candidates` remain;
  no standalone REM schema validation. Some tests lack `Validates:` tags.

## Agreements (both reports)
- Strong coverage across BT/PM/EL/RV; consistent use of `# Validates:` tags
  but not universal.
- Several non-functional/system-ops requirements are out-of-scope for tests
  (e.g., containerization, performance targets).
- Important test gaps remain for REM-specific schema/config validation and
  for populating certain brief sections (e.g., `contrasts`).

## Additional Findings from Codex
- Many JSON brief core sections are directly tested by
  `tests/reporting/test_brief.py:1` (overall_performance, risk_snapshot,
  equity_stats, distribution, streaks, holding_time) — these should be
  considered Covered.
- Compare (A/B) capabilities are exercised by multiple tests and CLI:
  - `tests/cli/test_cli_compare_and_paths.py:1`
  - `tests/reporting/test_compare_defaults.py:1`
  - `tests/reporting/test_compare_report_io.py:1`
  - `tests/reporting/test_compare_html.py:1`
  - `tests/reporting/test_compare_html_enhanced.py:1`
- Exit precedence policy `[BT-7.16]` is validated by BDD steps:
  `tests/step_defs/backtester/test_risk_management_steps.py:1`.
- Orphan/missing tags (should add `Validates:`):
  - `tests/backtester/test_rmm_enforcement.py`
  - `tests/data/test_data_catalog_loader.py`
  - `tests/strategy/test_strategy_parameter_substitution.py`
  - `tests/regime_market_manager/test_rmm_engine_daily.py`
  - `tests/execution/test_dummy_file.py`

## Additional Findings from Gemini
- CI present: `.github/workflows/ci.yml` backs `[SYS-1.6.2]`.
- Notes several System and Data Handler requirements as Not Covered; many are
  either non-testable or not yet implemented in this repo (e.g., live streams,
  caching), which is reasonable for MVP scope.

## Consolidated Coverage Calls (selected)
- [SYS-1.1.1] Modular separation — Partially Covered
  - Enforced by import boundaries tooling and module design; limited direct
    tests. See `tools/check_import_boundaries.py`.
- [SYS-1.1.2] Run Configuration binds components — Partially Covered
  - Unified `RunConfig` used in BT/CLI, with tests for CLI/config flows
    (`tests/core/test_cli_commands.py:1`), but no single test that asserts
    the binding of Strategy/REM/Instrument as a contract.
- [SYS-1.2.3] No circular deps — Covered by `tests/core/test_imports_ok.py:1`.
- [SYS-1.5.*] Blackout policy centralization — Covered via
  `tests/core/test_policy_branches.py:1`, `tests/core/test_blackout_policy_in_brief.py:1`,
  `tests/backtester/test_blackout_events.py:1`, `tests/core/test_calendar.py:1`.
- [SYS-1.6.2] CI — Covered by `.github/workflows/ci.yml`.
- [SYS-1.7.1/1.7.2] Reproducibility/CLI config — Covered by
  `tests/core/test_finalize_run.py:1` and CLI tests.
- [SYS-1.7.3] RunConfig JSON Schema — Not Covered (no schema/tests yet).
- [SYS-1.3.3] Native→canonical translation — Not Covered (Rule Translator TBD).
- [BT-7.1/7.4/7.6/7.7/7.8/7.10/7.11/7.16] — Covered across BT tests including
  core loop, costs, tie-break, warmup, determinism, skips/counterfactuals,
  and exit precedence.
- [PM-5.6/5.7] R multiple and portfolio-level limits — Covered.
- [EL-8.2/8.3/8.5/8.7/8.8/8.9/8.10] — Covered by execution tests.
- [RV-9.1] Brief generation — Covered (`tests/reporting/test_brief.py:1`).
- [JSON-11.4..11.9] Performance/risk/equity/distribution/streaks/holding —
  Covered (`tests/reporting/test_brief.py:1`).
- [JSON-11.12/11.13/11.17–11.24/11.26/11.27] — Covered by respective tests.
- [JSON-11.14] contrasts — Not Covered (still placeholder).
- [JSON-11.15] regimes — Covered via
  `tests/reporting/test_brief.py:1` (regimes breakdown test).
- [JSON-11.16] stop_tp_candidates — Not Covered (placeholder).
- [JSON-11.28] pure JSON types — Not Covered by an explicit test.

## Combined Recommendations
1) Add non-breaking structured REM exit context
   - Add `exit_context` to `Trade` and include in `reporting/brief.py`.
   - Populate when exits originate from REM (keep `exit_reason` string
     for backward compatibility). Add tests that assert presence in brief.
2) Add formal schema and validation for RunConfig
   - Create `docs/schemas/run_config.schema.json`; validate in CLI/Core.
   - Add tests covering typical/edge cases.
3) Add REM config JSON Schema and validation tests
   - Provide `docs/schemas/rem.schema.json`; unit tests for validation
     and simple REM behavior in isolation from BT.
4) Decide on `contrasts` and `stop_tp_candidates`
   - Implement minimal, deterministic logic or add explicit tests to
     document intentional placeholders for current MVP.
5) Improve traceability
   - Tag orphaned tests with `# Validates: [...]` to close trace gaps.

## Disagreements with Gemini Report (with evidence)
- JSON Brief core sections coverage
  - Gemini marks `[JSON-11.4]`–`[JSON-11.9]` as Not Covered. Disagree.
    `tests/reporting/test_brief.py:1` asserts presence and types for
    `overall_performance`, `risk_snapshot`, `equity_stats`, `distribution`,
    `streaks`, and `holding_time`.
- Compare (A/B) requirements
  - Gemini marks `[SYS-1.4.2]` and `[SYS-1.4.3]` as Not Covered. Disagree.
    Compare is exercised by CLI and report/HTML comparisons:
    `tests/cli/test_cli_compare_and_paths.py:1`,
    `tests/reporting/test_compare_defaults.py:1`,
    `tests/reporting/test_compare_report_io.py:1`,
    `tests/reporting/test_compare_html.py:1`,
    `tests/reporting/test_compare_html_enhanced.py:1`.
- Regimes section
  - Gemini marks `[JSON-11.15]` as Not Covered. Disagree. Regime breakdown is
    validated in `tests/reporting/test_brief.py:1` (regimes breakdown test).
- Run Configuration binding
  - Gemini marks `[SYS-1.1.2]` Not Covered. We assess Partially Covered:
    unified `RunConfig` is used and tested through CLI/finalize flows,
    though a singular binding-contract test does not exist yet.
- REM test gap severity
  - Gemini states "no tests for REM". We agree direct REM module tests are
    missing; however, REM-driven exit precedence is validated via BT BDD
    steps (`tests/step_defs/backtester/test_risk_management_steps.py:1`).
    Action remains to add dedicated REM unit tests and schema validation.

## Closing Notes
- This combined view should be used to drive the next iteration of tasks in
  `docs/alignment_tasks.md`, prioritizing REM exit context, schemas (RunConfig
  and REM), and improved traceability.
