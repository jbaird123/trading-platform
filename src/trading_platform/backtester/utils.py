from __future__ import annotations

from typing import Any

from trading_platform.core.utils import normalize_symbol


def resolve_instrument_symbol(instrument: Any) -> str:
    """
    Resolve and normalize the instrument symbol from various input formats.
    Raises ValueError when missing/empty.
    """
    if instrument is None:
        raise ValueError("instrument with symbol is required")
    if isinstance(instrument, dict):
        symbol = instrument.get("symbol", "")
    elif hasattr(instrument, "symbol"):
        symbol = getattr(instrument, "symbol", "")
    else:
        raise ValueError("instrument with symbol is required")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("instrument symbol is missing or empty")
    return normalize_symbol(symbol)
