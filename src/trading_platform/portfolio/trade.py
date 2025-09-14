from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trade:
    """
    Represents a completed trade with entry and exit details.

    This is an immutable record of a transaction.
    """

    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    side: str  # "long" or "short"
    size: float
    pnl: float
    exit_reason: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    cost_currency: float = 0.0
    cost_breakdown: dict[str, float] | None = None
    # 'mfe' and 'mae' will be added later.
