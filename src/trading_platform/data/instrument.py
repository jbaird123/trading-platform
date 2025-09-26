from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel

from trading_platform.core.utils import normalize_symbol


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
# Keys use canonical normalized format (e.g., "EURUSD" not "EUR/USD" or "EUR_USD")
_INSTRUMENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "AUDUSD": {"tick_size": 0.00001},
    "EURGBP": {"tick_size": 0.00001},
    "EURJPY": {"tick_size": 0.001},
    "EURUSD": {"tick_size": 0.00001},
    "GBPJPY": {"tick_size": 0.001},
    "GBPUSD": {"tick_size": 0.00001},
    "NZDUSD": {"tick_size": 0.00001},
    "USDCAD": {"tick_size": 0.00001},
    "USDCHF": {"tick_size": 0.00001},
    "USDJPY": {"tick_size": 0.001},
}


def get_instrument_definition(symbol: str) -> InstrumentDefinition:
    """Retrieves the instrument definition for a given symbol."""
    # Normalize the symbol to canonical format for lookup
    canonical_symbol = normalize_symbol(symbol)

    instrument_overrides = _INSTRUMENT_DEFINITIONS.get(canonical_symbol)
    if not instrument_overrides:
        raise ValueError(f"No instrument definition found for symbol: {symbol}")

    # For now, all defined instruments are Forex. This can be expanded later.
    asset_class = "Forex"
    defaults = _ASSET_CLASS_DEFAULTS.get(asset_class, {})

    # Merge defaults with instrument-specific overrides.
    # Use the canonical symbol in the returned object
    merged_props = {**defaults, **instrument_overrides, "symbol": canonical_symbol}

    return InstrumentDefinition(**merged_props)
