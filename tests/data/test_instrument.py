# Validates: [DH-2.8]
from __future__ import annotations

import pytest

from trading_platform.data.instrument import get_instrument_definition


def test_get_instrument_definition_success():
    """Tests that a valid symbol returns the correct definition object."""
    eur_usd_def = get_instrument_definition("EUR_USD")
    assert eur_usd_def.asset_class == "Forex"
    assert eur_usd_def.tick_size == 0.00001

    gbp_jpy_def = get_instrument_definition("GBP_JPY")
    assert gbp_jpy_def.asset_class == "Forex"
    assert gbp_jpy_def.tick_size == 0.001


def test_get_instrument_definition_not_found():
    """Tests that an invalid symbol raises a ValueError."""
    with pytest.raises(
        ValueError, match="No instrument definition found for symbol: FAKE"
    ):
        get_instrument_definition("FAKE")
