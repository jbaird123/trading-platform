from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Position:
    """
    Represents an open position in the market.

    This is an immutable object; any updates (like changing stop-loss)
    would involve creating a new instance.
    """

    symbol: str
    entry_time: datetime
    entry_price: float
    side: str  # "long" or "short"
    size: float
