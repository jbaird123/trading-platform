"""Tests for RunConfig symbol requirement validation.

# Validates: [SYS-1.1.2], [SYS-1.7.3]
"""

import pytest
from pydantic import ValidationError
from trading_platform.core.config import RunConfig


def test_runconfig_requires_instrument_symbol():
    """Test that RunConfig validation enforces instrument symbol requirements."""
    # Test that a missing 'instrument' key fails
    with pytest.raises(ValidationError, match="instrument symbol is required"):
        RunConfig.model_validate({"user_id": "test"})

    # Test that an empty instrument dict fails
    with pytest.raises(ValidationError, match="instrument symbol is required"):
        RunConfig.model_validate({"user_id": "test", "instrument": {}})

    # Test that an instrument with an empty symbol string fails
    with pytest.raises(ValidationError, match="instrument symbol is required"):
        RunConfig.model_validate({"user_id": "test", "instrument": {"symbol": ""}})

    # Test that a valid instrument passes and the symbol is normalized
    config = RunConfig.model_validate(
        {"user_id": "test", "instrument": {"symbol": "eurusd"}}
    )
    assert config.instrument is not None
    assert config.instrument["symbol"] == "EURUSD"
