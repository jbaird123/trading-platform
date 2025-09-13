from __future__ import annotations

from datetime import datetime
from typing import cast

import pandas as pd

from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade


def run_backtest(
    market_data: pd.DataFrame,
    signals: pd.Series,
    initial_cash: float = 100000.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    allow_flip_on_bar: bool = False,
    instrument: dict | None = None,
) -> list[Trade]:
    """
    Runs a simple, iterative (bar-by-bar) backtest to generate trades from signals.

    Args:
        market_data: DataFrame with OHLCV data.
        signals: Series with 'long', 'short', and 'flat' signals.
        initial_cash: The starting cash for the portfolio.
        stop_loss: Optional stop-loss price for new positions.
        take_profit: Optional take-profit price for new positions.
        allow_flip_on_bar: If True, allows closing a position and opening a new
                           one on the same bar. Defaults to False.

    Returns:
        A list of completed Trade objects.
    """
    # --- Input validation (fail fast) ---
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols.difference(set(market_data.columns))
    if missing:
        raise ValueError(f"market_data missing required columns: {sorted(missing)}")

    if len(signals) != len(market_data):
        msg = (
            f"signals length ({len(signals)}) must equal "
            f"market_data length ({len(market_data)})"
        )
        raise ValueError(msg)

    allowed = {"long", "short", "flat"}
    invalid_values = set(pd.Series(signals).astype(str).unique()) - allowed
    if invalid_values:
        raise ValueError(f"signals contain invalid values: {sorted(invalid_values)}")

    if market_data["close"].isna().any():
        first_bad = market_data[market_data["close"].isna()].index[0]
        raise ValueError(f"market_data.close has NaNs; first at index: {first_bad}")

    # Accept optional instrument snapshot; do not change PnL behavior yet.
    portfolio = PortfolioManager(initial_cash=initial_cash, instrument=instrument)

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

        if not portfolio.current_position and current_signal in ["long", "short"]:
            # Sizing and symbol are still hardcoded, to be fixed next.
            portfolio.create_new_position(
                symbol="EUR_USD",
                side=current_signal,
                entry_price=current_bar["close"],
                size=10000,
                entry_time=cast(datetime, current_bar.name),
                stop_loss=stop_loss,
                take_profit=take_profit,
                instrument=instrument,
            )

    return portfolio.trades
