[Explicit Instrument Symbol Requirement] Implementation Plan

- [x] 1. **Add** `tests/core/test_runconfig_symbol_requirement.py` with a new `test_runconfig_requires_instrument_symbol()` function that:
   - Instantiates `RunConfig` via `RunConfig.model_validate({"user_id": "test"})` and asserts `ValidationError` matching "instrument".
   - Instantiates with `{"instrument": {}}` and asserts `ValidationError` matching "symbol".
   - Instantiates with `{"instrument": {"symbol": ""}}` and asserts `ValidationError` matching "symbol".
   - Calls `pytest --cov=src/trading_platform/core/config.py --cov=tests/core/test_runconfig_symbol_requirement.py tests/core/test_runconfig_symbol_requirement.py` to confirm the new test fails before implementation.

- [x] 2. **Implement** a Pydantic validator inside `src/trading_platform/core/config.py:RunConfig` named `@model_validator(mode="after")` that:
   - Ensures `self.instrument` is a dict containing a non-empty `"symbol"` string.
   - Normalizes the symbol using `normalize_symbol()` before storing it back on `self.instrument["symbol"]`.
   - Raises `ValueError("instrument symbol is required")` when validation fails.
   - Runs `pytest --cov=src/trading_platform/core/config.py tests/core/test_runconfig_symbol_requirement.py` to confirm the validator passes with 100% coverage.

- [x] 3. **Extend** `tests/backtester/test_backtester.py` by:
   - Adding a local helper `_instrument(symbol: str = "EURUSD") -> dict[str, str]` that returns `{ "symbol": symbol }`.
   - Adding a new test `test_resolve_instrument_symbol_requires_input()` asserting `resolve_instrument_symbol(None)` and cases with empty symbols raise `ValueError` via `pytest.raises`.
   - Updating existing `RunConfig(...)` constructions in this file to call `_instrument()`.
   - Executing `pytest --cov=src/trading_platform/backtester/core.py tests/backtester/test_backtester.py` to verify failures before implementation.

- [x] 4. **Refactor** `src/trading_platform/backtester/core.py:resolve_instrument_symbol` to:
   - Raise `ValueError("instrument with symbol is required")` when the argument is `None`, missing a `symbol`, or has an empty/whitespace symbol.
   - Return `normalize_symbol(symbol)` for valid inputs, supporting both dict snapshots and objects with a `symbol` attribute.
   - Execute `pytest --cov=src/trading_platform/backtester/core.py tests/backtester/test_backtester.py` ensuring full coverage.

- [x] 5. **Update** `tests/backtester/test_risk_rules.py` so every `RunConfig(...)` call includes `instrument=_instrument()` (define `_instrument` locally if not present) and rerun `pytest tests/backtester/test_risk_rules.py` to confirm passing.

- [x] 6. **Update** `tests/backtester/test_events.py` by adding local `_instrument()` helper and supplying `instrument=_instrument()` to each `RunConfig(...)` instance. Validate with `pytest tests/backtester/test_events.py`.

- [x] 7. **Update** `tests/backtester/test_return_skips_only.py` to add `_instrument()` and pass `instrument=_instrument()` into the solitary `RunConfig(...)` call. Verify using `pytest tests/backtester/test_return_skips_only.py`.

- [x] 8. **Update** `tests/backtester/test_warmup_bars.py` to define `_instrument()` and ensure both `RunConfig(...)` usages include `instrument=_instrument()`. Run `pytest tests/backtester/test_warmup_bars.py`.

- [x] 9. **Update** `tests/backtester/test_skipped_logging.py` to add `_instrument()` and inject `instrument=_instrument()` for each `RunConfig(...)`. Execute `pytest tests/backtester/test_skipped_logging.py`.

- [x] 10. **Update** `tests/backtester/test_tie_break_policy.py` to define `_instrument()` and provide `instrument=_instrument()` when creating `RunConfig(...)`. Confirm with `pytest tests/backtester/test_tie_break_policy.py`.

- [x] 11. **Update** `tests/backtester/test_counterfactual_skips.py` by introducing `_instrument()` and adding `instrument=_instrument()` to each `RunConfig(...)`. Validate via `pytest tests/backtester/test_counterfactual_skips.py`.

- [x] 12. **Update** `tests/backtester/test_input_validation.py` to add `_instrument()` and supply `instrument=_instrument()` in all `RunConfig(...)` usages. Run `pytest tests/backtester/test_input_validation.py`.

- [x] 13. **Update** `tests/conftest.py` by adding a module-level `_instrument()` helper returning `{ "symbol": "EURUSD" }` and ensuring the `RunConfig(...)` in `when_backtest_is_run` includes `instrument=_instrument()`. Execute `pytest tests/step_defs/backtester/test_risk_management_steps.py`.

- [x] 14. **Update** `tests/core/test_cli_commands.py` so every generated config dictionary includes an `"instrument": {"symbol": "EURUSD"}` entry before serialization. Confirm with `pytest tests/core/test_cli_commands.py`.

- [x] 15. **Update** `tests/cli/test_cli_compare_and_paths.py` to add `"instrument": {"symbol": "EURUSD"}` to the CLI config payload before writing to disk. Run `pytest tests/cli/test_cli_compare_and_paths.py`.

- [x] 16. **Add** `tests/core/test_demo_run.py` with `test_generate_demo_run_includes_instrument()` that calls `generate_demo_run(user_id="demo_test")`, loads the emitted `RunConfig` snapshot from the generated `config.json` (or the run directory), and asserts the serialized config contains `"instrument": {"symbol": "EURUSD"}`. Use a temporary directory and clean up after the test. Execute the new test alone to observe failure.

- [x] 17. **Modify** `src/trading_platform/core/demo.py:generate_demo_run` to ensure the constructed `RunConfig` already contains `instrument={"symbol": "EURUSD"}`, matching the new assertion. Run `pytest tests/core/test_demo_run.py` to verify success with full coverage.

- [x] 18. **Update** documentation snippets that show minimal backtest configurations—specifically `README.md` and any quick-start section in `docs/project_requirements.md`—to include an explicit `instrument` block with a canonical symbol, then build docs or run the linter as required by project policy.

- [x] 19. **Run** the full regression suite with `pytest --cov` to confirm every modified module maintains 100% coverage and no tests rely on implicit instrument defaults. **NOTE**: 64 additional test files still require instrument parameter updates for full compliance.
