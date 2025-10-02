"""Additional tests to achieve 100% branch coverage for core/config.py."""

import pytest
from trading_platform.core.config import RunConfig


def test_data_request_without_symbol() -> None:
    """Test RunConfig with data_request that doesn't contain 'symbol' key.

    Validates: Branch 161→167 - False branch when 'symbol' not in data_request
    This should raise a validation error because instrument is required.
    """
    with pytest.raises(ValueError, match="instrument symbol is required"):
        RunConfig(
            user_id="test_user",
            run_seed=42,
            log_level="ERROR",
            initial_cash=10000,
            position_size=1000,
            data_request={"timeframe": "1H"},  # No 'symbol' key
        )


def test_data_request_with_symbol_auto_populates_instrument() -> None:
    """Test RunConfig auto-populates instrument from data_request with symbol.

    Validates: Branch 161→162 - True branch when 'symbol' in data_request
    """
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="ERROR",
        initial_cash=10000,
        position_size=1000,
        data_request={"symbol": "EUR_USD", "timeframe": "1H"},
    )

    # instrument should be auto-populated (symbol gets normalized to remove underscores)
    assert config.instrument is not None
    assert config.instrument["symbol"] == "EURUSD"  # Normalized
    assert config.instrument.get("timeframe") == "1H"
