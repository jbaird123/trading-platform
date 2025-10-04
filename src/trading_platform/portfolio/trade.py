from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


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
    pnl: float  # Net PnL after all costs
    exit_reason: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    pnl_movement: float = 0.0  # PnL from mid-price movement
    cost_currency: float = 0.0  # Total costs (spread + commission + slippage)
    cost_breakdown: dict | None = None  # {"spread": X, "commission": Y, "slippage": Z}
    r_multiple: float | None = None
    initial_risk_ccy: float | None = None
    mfe_currency: float | None = None
    mae_currency: float | None = None
    bars_held: int | None = None
    context_at_entry: dict[str, Any] | None = None
    context_at_exit: dict[str, Any] | None = None
    post_exit_analysis: dict[str, dict[str, float]] | None = None
    # Structure: {"10": {"mfe": 125.0, "mae": -20.0}, "20": {...}, "50": {...}}
