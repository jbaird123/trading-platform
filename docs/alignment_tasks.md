# Project Alignment Tasks

_Last updated: 2025-09-18_

This document outlines the tasks required to bring the project into alignment with its requirements, based on the combined analysis from the Gemini and Codex requirements checks.

## High Priority

- [ ] **Add comprehensive tests for the Risk & Exit Manager (REM) module.**
    - `[REM-6.1]` Test core mandate: stop-loss and take-profit logic.
    - `[REM-6.2]` Test REM configuration loading and validation from YAML.
    - `[REM-6.3]` Test support for multiple exit rule types (static and dynamic).
    - `[REM-6.4]` Test that REM is a pluggable component.

- [ ] **Create and validate the REM configuration schema.**
    - `[REM-6.2]` Create `docs/schemas/rem.schema.json`.
    - Add a loader and validation tests for the REM schema.

- [ ] **Create and validate the RunConfig JSON Schema.**
    - `[SYS-1.7.3]` Create `docs/schemas/run_config.schema.json`.
    - Add validation tests for the RunConfig schema.

## Medium Priority

- [ ] **Increase Data Handler (DH) test coverage.**
    - `[DH-2.1]` Test loading historical market data from local CSV files.
    - `[DH-2.2]` Test the live market data streaming connector for OANDA.
    - `[DH-2.4]` Test that timestamps are timezone-aware and set to UTC.
    - `[DH-2.7]` Test the production of the `quality_flags` report.
    - `[DH-2.8]` Test the Instrument Definition provider.

- [ ] **Tag orphaned tests.**
    - `tests/backtester/test_rmm_enforcement.py`
    - `tests/data/test_data_catalog_loader.py`
    - `tests/strategy/test_strategy_parameter_substitution.py`
    - `tests/regime_market_manager/test_rmm_engine_daily.py`
    - `tests/execution/test_dummy_file.py`

- [ ] **Implement structured REM exit context.**
    - `[JSON-11.25]` Add a structured `exit_context` dictionary to the `Trade` object and the brief, in addition to the existing `exit_reason` string.

- [ ] **Add JSON Schema validation tests for the main brief sections.**
    - `[JSON-11.1]` `meta`
    - `[JSON-11.2]` `strategy_params`
    - `[JSON-11.4]` `overall_performance`
    - `[JSON-11.5]` `risk_snapshot`

## Low Priority

- [ ] **Implement or defer placeholder brief sections.**
    - `[JSON-11.14]` `contrasts`
    - `[JSON-11.16]` `stop_tp_candidates`

- [ ] **Add tests for architectural principles where feasible.**
    - `[SYS-1.3.1]` Test canonical representation in the Portfolio Manager.
    - `[SYS-1.3.3]` Test native-to-canonical translation.

- [ ] **Improve Strategy Engine (SE) test coverage.**
    - `[SE-3.1]` Test signal generation only mandate.
    - `[SE-3.2]` Test the `BaseStrategy` interface.
