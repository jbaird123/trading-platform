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

    for i in range(len(market_data)):
        current_signal = signals.iloc[i]
        current_bar = market_data.iloc[i]

        # The backtester's job is to orchestrate, not to decide.
        # It passes the current state to the PortfolioManager, which
        # contains the actual position management logic.
        portfolio.on_bar(
            current_bar=current_bar,
            current_signal=current_signal,
            allow_flip_on_bar=allow_flip_on_bar,
        )

    return portfolio.trades
