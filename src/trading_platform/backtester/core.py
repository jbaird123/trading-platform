from __future__ import annotations

from typing import Any

import pandas as pd


def run_backtest(market_data: pd.DataFrame, signals: pd.Series) -> list[dict[str, Any]]:
    """
    Runs a simple, iterative (bar-by-bar) backtest to generate trades from signals.

    Args:
        market_data: DataFrame with OHLCV data.
        signals: Series with 'long', 'short', and 'flat' signals.

    Returns:
        A list of trade dictionaries.
    """
    # A simple iterative backtester.
    trades = []
    active_trade: dict[str, Any] | None = None

    for i, current_signal in enumerate(signals):
        # Entry logic: enter if we are flat and a signal appears
        if active_trade and active_trade["side"] == "long":
            # --- We are in a long trade, check for an exit on the CURRENT bar ---
            if current_signal != "long":
                active_trade["exit_price"] = market_data["close"].iloc[i]
                active_trade["exit_bar"] = i
                trades.append(active_trade)
                active_trade = None
        elif not active_trade:
            # --- We are flat, so look for an entry ---
            if current_signal == "long":
                active_trade = {
                    "side": "long",
                    "entry_price": market_data["close"].iloc[i],
                    "entry_bar": i,
                }

    return trades
