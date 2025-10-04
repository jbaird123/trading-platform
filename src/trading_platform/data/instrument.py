from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel, model_validator

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
    pip_location: float | None = None  # Required for Forex, forbidden for others
    commission_model: dict
    sessions: list[SessionDefinition]
    symbol: str | None = None
    base_ccy: str | None = None
    quote_ccy: str | None = None

    @model_validator(mode="after")
    def validate_pip_location_by_asset_class(self) -> InstrumentDefinition:
        """Enforce pip_location rules based on asset class."""
        if self.asset_class == "Forex":
            if self.pip_location is None:
                raise ValueError(
                    f"Forex instrument {self.symbol} MUST have pip_location"
                )
        else:
            if self.pip_location is not None:
                raise ValueError(
                    f"{self.asset_class} instrument {self.symbol} MUST NOT "
                    f"have pip_location (pips are Forex-only)"
                )
        return self

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
        "pip_location": 0.0001,  # Default for most forex pairs (4 decimal places)
        "commission_model": {"type": "spread"},
        "sessions": _FOREX_SESSION,
    }
}

# Define instrument-specific overrides and properties.
# Keys use canonical normalized format (e.g., "EURUSD" not "EUR/USD" or "EUR_USD")
_INSTRUMENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "AUDUSD": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "EURGBP": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "EURJPY": {
        "asset_class": "Forex",
        "tick_size": 0.001,
        "pip_location": 0.01,  # JPY pairs: 2 decimal places
    },
    "EURUSD": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "GBPJPY": {
        "asset_class": "Forex",
        "tick_size": 0.001,
        "pip_location": 0.01,  # JPY pairs: 2 decimal places
    },
    "GBPUSD": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "NZDUSD": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "USDCAD": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "USDCHF": {
        "asset_class": "Forex",
        "tick_size": 0.00001,
        "pip_location": 0.0001,
    },
    "USDJPY": {
        "asset_class": "Forex",
        "tick_size": 0.001,
        "pip_location": 0.01,  # JPY pairs: 2 decimal places
    },
}


def get_instrument_definition(symbol: str) -> InstrumentDefinition:
    """Retrieves the instrument definition for a given symbol."""
    # Normalize the symbol to canonical format for lookup
    canonical_symbol = normalize_symbol(symbol)

    instrument_overrides = _INSTRUMENT_DEFINITIONS.get(canonical_symbol)
    if not instrument_overrides:
        raise ValueError(f"No instrument definition found for symbol: {symbol}")

    # Get asset class from the instrument definition (not hardcoded)
    asset_class = instrument_overrides.get("asset_class")
    if not asset_class:
        raise ValueError(f"Instrument {symbol} missing required 'asset_class' field")

    defaults = _ASSET_CLASS_DEFAULTS.get(asset_class, {})

    # Merge defaults with instrument-specific overrides.
    # Use the canonical symbol in the returned object
    merged_props = {**defaults, **instrument_overrides, "symbol": canonical_symbol}

    return InstrumentDefinition(**merged_props)
