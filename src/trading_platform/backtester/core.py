from __future__ import annotations

import pandas as pd

from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade


def run_backtest(
    market_data: pd.DataFrame,
    signals: pd.Series,
    initial_cash: float = 100000.0,
    allow_flip_on_bar: bool = False,
) -> list[Trade]:
    """
    Runs a simple, iterative (bar-by-bar) backtest to generate trades from signals.

    Args:
        market_data: DataFrame with OHLCV data.
        signals: Series with 'long', 'short', and 'flat' signals.
        initial_cash: The starting cash for the portfolio.
        allow_flip_on_bar: If True, allows closing a position and opening a new
                           one on the same bar. Defaults to False.

    Returns:
        A list of completed Trade objects.
    """
    portfolio = PortfolioManager(initial_cash=initial_cash)
    symbol = "EUR_USD"  # Hardcoded for now, will be dynamic later
    trade_size = 10000  # Hardcoded for now

    for i in range(len(market_data)):
        current_signal = signals.iloc[i]
        current_bar = market_data.iloc[i]
        current_time = market_data.index[i]

        # --- Event-driven Logic for each bar ---
        if portfolio.open_position:
            # --- 1. We are in a position, check for an exit ---
            if current_signal != portfolio.open_position.side:
                portfolio.close_position(
                    exit_price=current_bar["close"],
                    exit_time=current_time,
                    exit_reason="signal",
                )
                # If flips are not allowed, we are done with this bar.
                if not allow_flip_on_bar:
                    continue
                # If flips are allowed, we fall through to the entry logic below.

        # --- 2. We are flat, check for an entry ---
        # This block is reached if we were never in a position,
        # or if we just closed one and `allow_flip_on_bar` is True.
        if not portfolio.open_position and current_signal in ["long", "short"]:
            portfolio.create_new_position(
                symbol=symbol,
                side=current_signal,
                entry_price=current_bar["close"],
                size=trade_size,
                entry_time=current_time,
            )

    return portfolio.trades
