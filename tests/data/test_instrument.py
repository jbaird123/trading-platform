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
    eur_usd_def = get_instrument_definition("EUR/USD")
    assert eur_usd_def.asset_class == "Forex"
    assert eur_usd_def.tick_size == 0.00001

    gbp_jpy_def = get_instrument_definition("GBP/JPY")
    assert gbp_jpy_def.asset_class == "Forex"
    assert gbp_jpy_def.tick_size == 0.001


def test_get_instrument_definition_not_found():
    """Tests that an invalid symbol raises a ValueError."""
    with pytest.raises(
        ValueError, match="No instrument definition found for symbol: FAKE"
    ):
        get_instrument_definition("FAKE")


def test_instrument_definition_to_dict_defaults():
    definition = get_instrument_definition("EUR/USD")
    result = definition.to_dict()
    assert result["asset_class"] == "Forex"
    assert result["tick_size"] == 0.00001
    assert result["symbol"] == "EURUSD"  # Now expects normalized symbol
    assert result["base_ccy"] is None and result["quote_ccy"] is None


def test_instrument_definition_to_dict_with_overrides():
    definition = get_instrument_definition("EUR/USD")
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
        InstrumentDefinition(
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

    # Test EUR_USD
    eur_usd_def = get_instrument_definition("EUR_USD")
    assert eur_usd_def.sessions[0].close_time == expected_close_time
    assert eur_usd_def.sessions[0].close_timezone == expected_timezone

    # Test GBP_JPY
    gbp_jpy_def = get_instrument_definition("GBP_JPY")
    assert gbp_jpy_def.sessions[0].close_time == expected_close_time
    assert gbp_jpy_def.sessions[0].close_timezone == expected_timezone


def test_get_instrument_definition_with_normalization():
    """Test that instrument definitions work with symbol normalization."""
    # Test that EUR/USD returns the correct definition without raising an error
    eur_usd_slash = get_instrument_definition("EUR/USD")
    assert eur_usd_slash.asset_class == "Forex"
    assert eur_usd_slash.tick_size == 0.00001

    # Test that EUR_USD returns the exact same definition object
    eur_usd_underscore = get_instrument_definition("EUR_USD")
    assert eur_usd_underscore.asset_class == "Forex"
    assert eur_usd_underscore.tick_size == 0.00001

    # For each of the calls above, assert that the returned InstrumentDefinition
    # object has its symbol attribute set to the canonical value: "EURUSD"
    assert eur_usd_slash.symbol == "EURUSD"
    assert eur_usd_underscore.symbol == "EURUSD"

    # Verify they are functionally equivalent
    assert eur_usd_slash.asset_class == eur_usd_underscore.asset_class
    assert eur_usd_slash.tick_size == eur_usd_underscore.tick_size
    assert eur_usd_slash.point_value == eur_usd_underscore.point_value


def test_get_instrument_definition_uses_asset_class_defaults():
    """Test that instrument definitions correctly use asset class defaults."""
    # Call get_instrument_definition for "EUR/USD"
    eur_usd = get_instrument_definition("EUR/USD")

    # Assert that the returned object's asset_class is "Forex"
    assert eur_usd.asset_class == "Forex"

    # Assert that the sessions property is not empty
    assert eur_usd.sessions is not None
    assert len(eur_usd.sessions) > 0

    # Assert that the tick_size is 0.00001 (the instrument-specific override)
    assert eur_usd.tick_size == 0.00001

    # Call get_instrument_definition for "EUR/JPY" and assert its tick_size
    eur_jpy = get_instrument_definition("EUR/JPY")
    assert eur_jpy.tick_size == 0.001
