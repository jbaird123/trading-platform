# Validates: [DH-2.8]
from __future__ import annotations

from datetime import time

import pytest
from pydantic import ValidationError
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
    # Currency codes are now populated in instrument definitions
    assert result["base_ccy"] == "EUR"
    assert result["quote_ccy"] == "USD"


def test_instrument_definition_currency_codes():
    """Test that all forex instruments have proper currency codes."""
    # USD-quoted pairs
    for symbol in ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]:
        definition = get_instrument_definition(symbol)
        assert definition.quote_ccy == "USD"
        assert definition.base_ccy == symbol[:3]

    # USD-based pairs
    for symbol in ["USDJPY", "USDCAD", "USDCHF"]:
        definition = get_instrument_definition(symbol)
        assert definition.base_ccy == "USD"
        assert definition.quote_ccy == symbol[3:]

    # Cross pairs
    eurjpy = get_instrument_definition("EURJPY")
    assert eurjpy.base_ccy == "EUR"
    assert eurjpy.quote_ccy == "JPY"

    gbpjpy = get_instrument_definition("GBPJPY")
    assert gbpjpy.base_ccy == "GBP"
    assert gbpjpy.quote_ccy == "JPY"

    eurgbp = get_instrument_definition("EURGBP")
    assert eurgbp.base_ccy == "EUR"
    assert eurgbp.quote_ccy == "GBP"


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
        session_group="forex",
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


def test_forex_instrument_has_session_group():
    """Forex instruments should have session_group='forex' by default."""
    instrument = get_instrument_definition("EURUSD")
    assert instrument.session_group == "forex"


def test_all_forex_instruments_have_session_group():
    """All defined forex instruments should inherit session_group from defaults."""
    forex_symbols = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURGBP",
        "EURJPY",
        "GBPJPY",
    ]
    for symbol in forex_symbols:
        instrument = get_instrument_definition(symbol)
        assert instrument.session_group == "forex", f"{symbol} missing session_group"


def test_session_group_is_required():
    """InstrumentDefinition should require session_group field."""
    with pytest.raises(ValidationError):
        InstrumentDefinition(  # type: ignore[call-arg]
            asset_class="Forex",
            point_value=1.0,
            tick_size=0.00001,
            pip_location=0.0001,
            commission_model={"type": "spread"},
            sessions=[
                SessionDefinition(
                    close_time=time(17, 0), close_timezone="America/New_York"
                )
            ],
            # session_group intentionally omitted
        )
