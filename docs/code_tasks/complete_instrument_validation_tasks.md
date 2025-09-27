# Implementation Plan: Complete Instrument Validation

This document outlines the precise, ordered steps required to complete the refactoring for explicit instrument symbols. It addresses the incomplete items from the last code review and will ensure the core logic is correct and fully tested before we address the remaining test failures across the suite.

The developer must create a new branch for this fix named `fix/complete-instrument-validation` and follow these tasks in the specified sequence.

---

### 1. Add Tests for the `RunConfig` Validator

- [ ] **1.1. Create the Test File and Failing Tests**
    -   **File:** `tests/core/test_runconfig_symbol_requirement.py` (create this new file).
    -   **Action:** Add a new test function `test_runconfig_requires_instrument_symbol`.
    -   **Logic:** This test must validate the failure modes of the Pydantic validator in `RunConfig`.
        ```python
        import pytest
        from pydantic import ValidationError
        from trading_platform.core.config import RunConfig

        def test_runconfig_requires_instrument_symbol():
            # Test that a missing 'instrument' key fails
            with pytest.raises(ValidationError, match="instrument symbol is required"):
                RunConfig.model_validate({"user_id": "test"})

            # Test that an empty instrument dict fails
            with pytest.raises(ValidationError, match="instrument symbol is required"):
                RunConfig.model_validate({"user_id": "test", "instrument": {}})

            # Test that an instrument with an empty symbol string fails
            with pytest.raises(ValidationError, match="instrument symbol is required"):
                RunConfig.model_validate({"user_id": "test", "instrument": {"symbol": ""}})

            # Test that a valid instrument passes
            config = RunConfig.model_validate({
                "user_id": "test",
                "instrument": {"symbol": "EUR/USD"}
            })
            assert config.instrument["symbol"] == "EURUSD"
        ```

### 2. Integrate the Instrument Symbol in the Backtester

- [ ] **2.1. Add a Failing Test for Hardcoded Symbols**
    -   **File:** `tests/backtester/test_instrument_arg.py` (create this new file).
    -   **Action:** Add a test to prove the backtester is ignoring the config and using a hardcoded symbol.
    -   **Logic:**
        ```python
        from datetime import datetime
        import pandas as pd
        from trading_platform.core.config import RunConfig
        from trading_platform.backtester.core import run_backtest
        from trading_platform.risk_manager.core import RiskExitManager
        from tests.backtester.dummy_objects import dummy_strategy

        def test_backtester_uses_provided_instrument_symbol():
            # This test will fail until the backtester logic is fixed
            idx = [datetime(2024, 1, 1, h) for h in range(2)]
            df = pd.DataFrame({
                "open": [1.0] * 2, "high": [1.0] * 2,
                "low": [1.0] * 2, "close": [1.0] * 2, "volume": [1] * 2
            }, index=idx)
            signals = pd.Series(["long", "long"], index=df.index)
            config = RunConfig(
                user_id="test",
                initial_cash=1000.0,
                position_size=1.0,
                pm_limits={"max_open_long": 0}, # Force a skip
                instrument={"symbol": "GBPUSD"} # Use a non-default symbol
            )
            rem = RiskExitManager(config={})

            _, _, skipped = run_backtest(
                market_data=df,
                signals=signals,
                strategy=dummy_strategy(),
                config=config,
                rem=rem,
                return_skips=True
            )

            assert len(skipped) > 0
            # This assertion will fail because the symbol is hardcoded to EURUSD
            assert skipped[0]["symbol"] == "GBPUSD"
        ```

- [ ] **2.2. Refactor `run_backtest` to Use the Instrument Symbol**
    -   **File:** `src/trading_platform/backtester/core.py`
    -   **Action:** Refactor `run_backtest` and its helpers to use the symbol from the `RunConfig`.
    -   **Logic:**
        1.  At the top of `run_backtest`, get the canonical symbol: `symbol = resolve_instrument_symbol(config.instrument)`.
        2.  Find every instance of a hardcoded `"EURUSD"` within the `run_backtest` function and its helpers (`_simulate_counterfactual_exact`, etc.) and replace it with the `symbol` variable.
        3.  Ensure the `symbol` variable is passed down into any helper function that needs it.

### 3. Add Test for Demo Generation

- [ ] **3.1. Create the Test File for Demo Generation**
    -   **File:** `tests/core/test_demo_run.py` (create this new file).
    -   **Action:** Add the `test_generate_demo_run_includes_instrument` test.
    -   **Logic:**
        ```python
        import json
        from pathlib import Path
        import tempfile
        import shutil
        from trading_platform.core.demo import generate_demo_run

        def test_generate_demo_run_includes_instrument():
            temp_dir = Path(tempfile.mkdtemp())
            try:
                run_path = generate_demo_run(user_id="demo_test")
                # Move generated run to temp_dir to avoid clutter
                shutil.move(str(run_path), str(temp_dir / run_path.name))
                config_path = temp_dir / run_path.name / "config.json"
                assert config_path.exists()

                with open(config_path, 'r') as f:
                    config_data = json.load(f)

                assert "instrument" in config_data
                assert "symbol" in config_data["instrument"]
                assert config_data["instrument"]["symbol"] == "EURUSD"
            finally:
                shutil.rmtree(temp_dir)
        ```

### 4. Verification

- [ ] **4.1. Run All Modified Tests**
    -   **Action:** Run all the tests for the backtester and the new core tests together to ensure everything passes and coverage is maintained.
    -   **Command:** `poetry run pytest tests/backtester/ tests/core/test_runconfig_symbol_requirement.py tests/core/test_demo_run.py`
