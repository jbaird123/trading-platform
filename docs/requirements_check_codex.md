# Requirements Check (Codex)

_Date: 2025-09-18_

## Method
- Reviewed `docs/project_requirements.md` for numbered requirements.
- Indexed tests/BDD features and mapped "Validates:" tags.
- Inspected key modules for architecture alignment and reporting.

## Summary
- SE vs REM separation is respected. REM is used by BT first per policy.
- Unified `RunConfig` is in use and snapshotted in briefs/CLI.
- Reporting is rich; many brief sections validated by tests.
- Gaps: structured exit context, RunConfig JSON Schema, a few placeholders.

## Coverage Highlights (by area)
- System (SYS): boundaries, blackout policy, compare flows covered by tests.
- Data (DH): schema, resample, feature pipeline tests are present.
- Strategy (SE): schema, indicators, YAML rules, params verified.
- RMM: rule engine + schema validated; daily engine test lacks tag.
- Portfolio (PM): state, PnL, metrics, R multiple, risk caps covered.
- REM: component exists, precedence enforced; no REM schema validation.
- Backtester (BT): core loop, warmup, costs, tie-break, skips/counterfactuals.
- Execution (EL): OANDA adapter stubs, controller, policies under tests.
- Reporting (RV): brief sections, costs, exposure, regimes, HTML compare.

## Discrepancies
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

## Requirements lacking tests (prioritized)
- `[SYS-1.7.3]` RunConfig JSON Schema + validation.
- `[JSON-11.14]` contrasts population logic/tests (or explicit deferral test).
- `[JSON-11.16]` stop_tp_candidates from MFE/MAE (or deferral test).
- REM config schema validation `[REM-6.2]`.

## Orphaned tests (missing "Validates:" tag)
- `tests/backtester/test_rmm_enforcement.py` (RMM gating/BT policy).
- `tests/data/test_data_catalog_loader.py` (DH catalog loading).
- `tests/strategy/test_strategy_parameter_substitution.py` (SE params).
- `tests/regime_market_manager/test_rmm_engine_daily.py` (RMM engine).
- `tests/execution/test_dummy_file.py` (housekeeping or tag/remove).

## Architecture & Invariants
- SE vs REM separation: aligned; strategy contains no risk block.
- Canonical-first: PM/costs use canonical units. No Rule Translator yet.
- Exit precedence `[BT-7.16]`: REM exits checked before strategy exits.

## Recommendations (next steps)
1) Add non-breaking `exit_context` for REM exits; test brief inclusion.
2) Add `docs/schemas/run_config.schema.json` + validation tests.
3) Add `docs/schemas/rem.schema.json` + loader/validation tests.
4) Tag the orphaned tests with matching requirement IDs.
5) Decide on contrasts/stop_tp_candidates: implement or mark deferred.
