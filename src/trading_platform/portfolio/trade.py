from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trading_platform.reporting.models.exit_analysis import (
        PostExitAnalysis,
    )


@dataclass(frozen=True)
class Trade:
    """
    Represents a completed trade with entry and exit details.

    This is an immutable record of a transaction.

    Currency fields:
        pnl: Net P&L converted to reference currency (USD by default)
        pnl_native: Net P&L in native (quote) currency before conversion
        pnl_currency: Currency code for pnl field (e.g., "USD")
        native_currency: Currency code for pnl_native (e.g., "JPY")
    """

    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    side: str  # "long" or "short"
    size: float
    pnl: float  # Net PnL after all costs, in reference currency (USD)
    exit_reason: str | None = None
    pnl_native: float | None = None  # Net PnL in native (quote) currency
    pnl_currency: str | None = None  # Currency of pnl field (e.g., "USD")
    native_currency: str | None = None  # Currency of pnl_native (e.g., "JPY")
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
    post_exit_analysis: PostExitAnalysis | None = None
