# Validates: [DH-2.8]
from __future__ import annotations

import pytest
from trading_platform.data.instrument import get_instrument_definition


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
    assert result["symbol"] == "EUR/USD"
    assert result["base_ccy"] is None and result["quote_ccy"] is None


def test_instrument_definition_to_dict_with_overrides():
    definition = get_instrument_definition("EUR/USD")
    definition.base_ccy = "EUR"
    definition.quote_ccy = "USD"
    result = definition.to_dict()
    assert result["base_ccy"] == "EUR"
    assert result["quote_ccy"] == "USD"
