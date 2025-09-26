from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel


class SessionDefinition(BaseModel):
    """Defines a trading session with close time and timezone."""

    close_time: time
    close_timezone: str


class InstrumentDefinition(BaseModel):
    """Defines the metadata for a financial instrument."""

    asset_class: str
    point_value: float
    tick_size: float
    commission_model: dict
    sessions: list[SessionDefinition]
    symbol: str | None = None
    base_ccy: str | None = None
    quote_ccy: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


# Standard Forex session constant
_FOREX_SESSION = [
    SessionDefinition(close_time=time(17, 0), close_timezone="America/New_York")
]

# Define default properties for asset classes to reduce repetition.
_ASSET_CLASS_DEFAULTS: dict[str, dict[str, Any]] = {
    "Forex": {
        "asset_class": "Forex",
        "point_value": 1.0,
        "commission_model": {"type": "spread"},
        "sessions": _FOREX_SESSION,
    }
}

# Define instrument-specific overrides and properties.
_INSTRUMENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "AUD/USD": {"tick_size": 0.00001},
    "EUR/GBP": {"tick_size": 0.00001},
    "EUR/JPY": {"tick_size": 0.001},
    "EUR/USD": {"tick_size": 0.00001},
    "EUR_USD": {"tick_size": 0.00001, "sessions": _FOREX_SESSION},
    "GBP/JPY": {"tick_size": 0.001},
    "GBP_JPY": {"tick_size": 0.001, "sessions": _FOREX_SESSION},
    "GBP/USD": {"tick_size": 0.00001},
    "NZD/USD": {"tick_size": 0.00001},
    "USD/CAD": {"tick_size": 0.00001},
    "USD/CHF": {"tick_size": 0.00001},
    "USD/JPY": {"tick_size": 0.001},
}


def get_instrument_definition(symbol: str) -> InstrumentDefinition:
    """Retrieves the instrument definition for a given symbol."""
    instrument_overrides = _INSTRUMENT_DEFINITIONS.get(symbol)
    if not instrument_overrides:
        raise ValueError(f"No instrument definition found for symbol: {symbol}")

    # For now, all defined instruments are Forex. This can be expanded later.
    asset_class = "Forex"
    defaults = _ASSET_CLASS_DEFAULTS.get(asset_class, {})

    # Merge defaults with instrument-specific overrides.
    merged_props = {**defaults, **instrument_overrides, "symbol": symbol}

    return InstrumentDefinition(**merged_props)
