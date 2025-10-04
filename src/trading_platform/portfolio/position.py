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
    entry_mid_price: float
    side: str  # "long" or "short"
    size: float
    initial_risk_ccy: float | None = None
    # Tracking fields updated as new bars arrive
    bars_held: int = 0
    mfe_currency: float = 0.0
    mae_currency: float = 0.0
    unrealized_pnl: float = 0.0
    context_at_entry: dict | None = None
