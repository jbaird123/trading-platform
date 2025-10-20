# Plan to Restore Strict Configuration Validation

This document outlines the plan to address issues identified in the Pydantic migration status report. The goal is to restore lost functionality and ensure all configuration files (REM, RMM, Strategy, RunConfig) are strictly validated using Pydantic models.

---

### Phase 1: Fix RMM Strict Validation (Critical Priority)

The lack of validation on the Regime Market Manager (RMM) is the most significant risk, as it can lead to silent failures. We will fix this first.

1.  **Create Pydantic Models for RMM:** Create `src/trading_platform/regime_market_manager/models.py` and define strict Pydantic models that mirror the structure of `docs/schemas/rmm.schema.json`, ensuring all models reject unknown fields.
2.  **Write Tests for RMM Models:** Create `tests/regime_market_manager/test_models.py` and add tests to ensure valid RMM configs pass and, more importantly, that invalid configs (with typos or unknown fields) are correctly rejected.
3.  **Integrate RMM Validation:** Update the `RMMEngine` to use the new Pydantic models for validation at instantiation, removing the non-functional `validate_config` method and ensuring no RMM can be created with an invalid configuration.

---

### Phase 2: Restore Lost REM Functionality

Next, we will restore the features that were removed from the Risk & Exit Manager (REM) during the faulty migration.

1.  **Enhance REM Pydantic Models:** Update `src/trading_platform/risk_manager/models.py` by re-introducing models for the lost features, using the old `rem.schema.json.backup` and `rem_dynamic.schema.json` files as a reference. This includes adding back support for:
    *   `trailing_stop` (including the logic that requires a `timeframe`)
    *   `breakeven_threshold`
    *   `partial_exits`
    *   `absolute_price` and `price_offset` stops
2.  **Re-implement Core REM Logic:** Investigate the git history to recover the deleted business logic for these features and integrate it back into the `RiskExitManager`.
3.  **Write Targeted Tests:** Add tests to `tests/risk_manager/` that specifically confirm each of the restored features works as expected, including a test that validates the `trailing_stop` using a higher-resolution `timeframe`.

---

### Phase 3: Cleanup and Final Verification

Finally, we will clean up obsolete artifacts and run a full system verification.

1.  **Remove Obsolete JSON Schemas:** Once the Pydantic models are the single source of truth for both REM and RMM, delete the now-redundant `.schema.json` files from `docs/schemas/`.
2.  **Run Full System Checks:** Execute the entire test suite (`pytest`), linter (`ruff`), and type checker (`mypy`) to ensure the system is stable, correct, and adheres to quality standards.
