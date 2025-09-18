from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class InstrumentDefinition(BaseModel):
    """Defines the metadata for a financial instrument."""

    asset_class: str
    point_value: float
    tick_size: float
    commission_model: dict
    sessions: list[tuple[str, str]]
    symbol: str | None = None
    base_ccy: str | None = None
    quote_ccy: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


# Placeholder for a more robust instrument definition provider.
_INSTRUMENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "EUR_USD": {
        "asset_class": "Forex",
        "point_value": 1.0,  # Canonical value, not lot-specific
        "tick_size": 0.00001,
        "commission_model": {"type": "spread"},
        "sessions": [("00:00", "23:59")],
    },
    "GBP_JPY": {
        "asset_class": "Forex",
        "point_value": 1.0,
        "tick_size": 0.001,
        "commission_model": {"type": "spread"},
        "sessions": [("00:00", "23:59")],
    },
}


def get_instrument_definition(symbol: str) -> InstrumentDefinition:
    """Retrieves the instrument definition for a given symbol."""
    if symbol not in _INSTRUMENT_DEFINITIONS:
        raise ValueError(f"No instrument definition found for symbol: {symbol}")
    return InstrumentDefinition(**_INSTRUMENT_DEFINITIONS[symbol])
