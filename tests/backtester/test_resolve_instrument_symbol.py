from __future__ import annotations

import pytest
from trading_platform.backtester.utils import resolve_instrument_symbol


class _InstrumentObj:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


def test_resolve_instrument_symbol_from_dict_normalizes() -> None:
    result = resolve_instrument_symbol({"symbol": "eur/usd"})
    assert result == "EURUSD"


def test_resolve_instrument_symbol_from_object_attribute() -> None:
    inst = _InstrumentObj("gbp usd")
    assert resolve_instrument_symbol(inst) == "GBPUSD"


def test_resolve_instrument_symbol_none_raises_value_error() -> None:
    with pytest.raises(ValueError, match="instrument with symbol is required"):
        resolve_instrument_symbol(None)


def test_resolve_instrument_symbol_empty_symbol_raises() -> None:
    with pytest.raises(ValueError, match="instrument symbol is missing or empty"):
        resolve_instrument_symbol({"symbol": "   "})


def test_resolve_instrument_symbol_missing_symbol_attribute_raises() -> None:
    with pytest.raises(ValueError, match="instrument with symbol is required"):
        resolve_instrument_symbol(object())
