# Validates: [DH-2.8]
from __future__ import annotations

from datetime import time

import pytest
from trading_platform.data.instrument import (
    InstrumentDefinition,
    SessionDefinition,
    get_instrument_definition,
)


def test_get_instrument_definition_success():
    """Tests that a valid symbol returns the correct definition object."""
    eurusd_def = get_instrument_definition("EURUSD")
    assert eurusd_def.asset_class == "Forex"
    assert eurusd_def.tick_size == 0.00001

    gbpjpy_def = get_instrument_definition("GBPJPY")
    assert gbpjpy_def.asset_class == "Forex"
    assert gbpjpy_def.tick_size == 0.001


def test_get_instrument_definition_not_found():
    """Tests that an invalid symbol raises a ValueError."""
    with pytest.raises(
        ValueError, match="No instrument definition found for symbol: FAKE"
    ):
        get_instrument_definition("FAKE")


def test_instrument_definition_to_dict_defaults():
    definition = get_instrument_definition("EURUSD")
    result = definition.to_dict()
    assert result["asset_class"] == "Forex"
    assert result["tick_size"] == 0.00001
    assert result["symbol"] == "EURUSD"  # Now expects normalized symbol
    assert result["base_ccy"] is None and result["quote_ccy"] is None


def test_instrument_definition_to_dict_with_overrides():
    definition = get_instrument_definition("EURUSD")
    definition.base_ccy = "EUR"
    definition.quote_ccy = "USD"
    result = definition.to_dict()
    assert result["base_ccy"] == "EUR"
    assert result["quote_ccy"] == "USD"


def test_instrument_and_session_models():
    """Test new SessionDefinition model and updated InstrumentDefinition."""
    from pydantic import ValidationError

    # Test that SessionDefinition can be created successfully
    session = SessionDefinition(
        close_time=time(17, 0), close_timezone="America/New_York"
    )
    assert session.close_time == time(17, 0)
    assert session.close_timezone == "America/New_York"

    # Test that InstrumentDefinition can be created with SessionDefinition
    valid_sessions = [session]
    instrument = InstrumentDefinition(
        asset_class="Forex",
        point_value=1.0,
        tick_size=0.00001,
        pip_location=0.0001,
        commission_model={"type": "spread"},
        sessions=valid_sessions,
        symbol="TEST/USD",
    )
    assert len(instrument.sessions) == 1
    assert instrument.sessions[0].close_time == time(17, 0)

    # Test that InstrumentDefinition cannot be created without sessions field
    with pytest.raises(ValidationError):
        InstrumentDefinition(  # type: ignore[call-arg]
            asset_class="Forex",
            point_value=1.0,
            tick_size=0.00001,
            commission_model={"type": "spread"},
            symbol="TEST/USD",
            # Missing sessions field - should raise ValidationError
        )


def test_forex_instruments_use_standard_session():
    """Test that forex instruments use the standard session."""
    # Define the expected session
    expected_close_time = time(17, 0)
    expected_timezone = "America/New_York"

    # Test EURUSD
    eurusd_def = get_instrument_definition("EURUSD")
    assert eurusd_def.sessions[0].close_time == expected_close_time
    assert eurusd_def.sessions[0].close_timezone == expected_timezone

    # Test GBPJPY
    gbpjpy_def = get_instrument_definition("GBPJPY")
    assert gbpjpy_def.sessions[0].close_time == expected_close_time
    assert gbpjpy_def.sessions[0].close_timezone == expected_timezone


def test_get_instrument_definition_with_strict_validation():
    """Test that instrument definitions enforce strict symbol validation."""
    # Test that EURUSD (uppercase) works
    eurusd_upper = get_instrument_definition("EURUSD")
    assert eurusd_upper.asset_class == "Forex"
    assert eurusd_upper.tick_size == 0.00001
    assert eurusd_upper.symbol == "EURUSD"

    # Test that eurusd (lowercase) works and gets uppercased
    eurusd_lower = get_instrument_definition("eurusd")
    assert eurusd_lower.asset_class == "Forex"
    assert eurusd_lower.tick_size == 0.00001
    assert eurusd_lower.symbol == "EURUSD"

    # Verify they are functionally equivalent
    assert eurusd_upper.asset_class == eurusd_lower.asset_class
    assert eurusd_upper.tick_size == eurusd_lower.tick_size
    assert eurusd_upper.point_value == eurusd_lower.point_value

    # Test that EUR/USD (with separator) is rejected
    with pytest.raises(ValueError, match="Invalid symbol.*must contain only letters"):
        get_instrument_definition("EUR/USD")

    # Test that EUR_USD (with underscore) is rejected
    with pytest.raises(ValueError, match="Invalid symbol.*must contain only letters"):
        get_instrument_definition("EUR_USD")


def test_get_instrument_definition_uses_asset_class_defaults():
    """Test that instrument definitions correctly use asset class defaults."""
    # Call get_instrument_definition for "EURUSD"
    eurusd = get_instrument_definition("EURUSD")

    # Assert that the returned object's asset_class is "Forex"
    assert eurusd.asset_class == "Forex"

    # Assert that the sessions property is not empty
    assert eurusd.sessions is not None
    assert len(eurusd.sessions) > 0

    # Assert that the tick_size is 0.00001 (the instrument-specific override)
    assert eurusd.tick_size == 0.00001

    # Call get_instrument_definition for "EURJPY" and assert its tick_size
    eurjpy = get_instrument_definition("EURJPY")
    assert eurjpy.tick_size == 0.001
