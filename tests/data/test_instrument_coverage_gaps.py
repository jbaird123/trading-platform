# Coverage gaps for instrument.py - missing line 21 (to_dict method)
from __future__ import annotations

from trading_platform.data.instrument import get_instrument_definition


def test_instrument_definition_to_dict():
    """Test the to_dict method to achieve 100% coverage."""
    # Get an instrument definition
    eur_usd_def = get_instrument_definition("EUR_USD")

    # Call the to_dict method (line 21)
    result = eur_usd_def.to_dict()

    # Verify it returns the expected dictionary
    expected_dict = {
        "asset_class": "Forex",
        "point_value": 1.0,
        "tick_size": 0.00001,
        "commission_model": {"type": "spread"},
        "sessions": [("00:00", "23:59")],
        "symbol": None,
        "base_ccy": None,
        "quote_ccy": None,
    }

    assert result == expected_dict
    assert isinstance(result, dict)


def test_instrument_definition_to_dict_with_optional_fields():
    """Test the to_dict method with optional fields set."""
    # Get an instrument definition and set optional fields
    eur_usd_def = get_instrument_definition("EUR_USD")
    eur_usd_def.symbol = "EUR_USD"
    eur_usd_def.base_ccy = "EUR"
    eur_usd_def.quote_ccy = "USD"

    # Call the to_dict method (line 21)
    result = eur_usd_def.to_dict()

    # Verify optional fields are included
    assert result["symbol"] == "EUR_USD"
    assert result["base_ccy"] == "EUR"
    assert result["quote_ccy"] == "USD"
    assert result["asset_class"] == "Forex"
