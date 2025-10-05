"""
Exit simulation logic for realistic post-exit analysis.

This module provides functionality to simulate what would have happened
if a trade was held longer after its actual exit, accounting for
stop-loss and take-profit triggers.
"""

from typing import Literal

import pandas as pd

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.models.exit_analysis import SimulatedHold


def run_single_trade_simulation(
    trade: Trade, price_data: pd.DataFrame, hold_bars: int
) -> SimulatedHold:
    """
    Simulate holding a trade for N additional bars after exit.

    This function takes a closed trade and simulates what would have
    happened if the position was held for `hold_bars` additional bars,
    accounting for stop-loss and take-profit triggers.

    Args:
        trade: The completed trade to simulate extending.
        price_data: Price data starting AFTER the trade's exit time.
                    Must have OHLC columns and datetime index.
        hold_bars: Number of bars to simulate holding.

    Returns:
        SimulatedHold object containing the simulation results.

    Logic:
        1. Get the trade's stop-loss and take-profit levels
        2. Slice price_data to get hold_bars of data
        3. Iterate bar-by-bar, checking for SL/TP breaches
        4. Track MFE/MAE during the simulation
        5. Calculate PnL at exit (breach or end of period)
        6. Return fully populated SimulatedHold object
    """
    # Get the original exit levels
    stop_loss = trade.stop_loss
    take_profit = trade.take_profit

    # Re-entry price is the trade's exit price
    # (we're simulating continuing to hold from that point)
    reentry_price = trade.exit_price

    # Slice the data to the desired hold period
    # If insufficient data, use what's available
    actual_bars_available = min(hold_bars, len(price_data))
    simulation_data = price_data.iloc[:actual_bars_available]

    # Initialize tracking variables
    mfe = 0.0
    mae = 0.0
    mfe_bar_offset = 0
    mae_bar_offset = 0
    simulated_exit_bar_offset = max(0, actual_bars_available - 1)
    simulated_exit_reason: Literal["stop_loss", "take_profit", "held_full_period"] = (
        "held_full_period"
    )
    simulated_exit_price = (
        simulation_data.iloc[-1]["close"] if len(simulation_data) > 0 else reentry_price
    )

    # Iterate through each bar and check for breaches
    for i, (timestamp, bar) in enumerate(simulation_data.iterrows()):
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]

        # Calculate current PnL based on high/low excursions
        if trade.side == "long":
            # For long: profit when price goes up
            current_mfe = (high - reentry_price) * trade.size
            current_mae = (low - reentry_price) * trade.size

            # Check stop-loss (price drops below SL)
            if stop_loss is not None and low <= stop_loss:
                simulated_exit_reason = "stop_loss"
                simulated_exit_price = stop_loss
                simulated_exit_bar_offset = i
                break

            # Check take-profit (price rises above TP)
            if take_profit is not None and high >= take_profit:
                simulated_exit_reason = "take_profit"
                simulated_exit_price = take_profit
                simulated_exit_bar_offset = i
                break

        else:  # short
            # For short: profit when price goes down
            current_mfe = (reentry_price - low) * trade.size
            current_mae = (reentry_price - high) * trade.size

            # Check stop-loss (price rises above SL)
            if stop_loss is not None and high >= stop_loss:
                simulated_exit_reason = "stop_loss"
                simulated_exit_price = stop_loss
                simulated_exit_bar_offset = i
                break

            # Check take-profit (price drops below TP)
            if take_profit is not None and low <= take_profit:
                simulated_exit_reason = "take_profit"
                simulated_exit_price = take_profit
                simulated_exit_bar_offset = i
                break

        # Update MFE/MAE tracking
        if current_mfe > mfe:
            mfe = current_mfe
            mfe_bar_offset = i

        if current_mae < mae:
            mae = current_mae
            mae_bar_offset = i

        # If we reach the end without trigger, use final close
        if i == len(simulation_data) - 1:
            simulated_exit_price = close

    # Calculate final PnL for the simulated hold
    if trade.side == "long":
        simulated_pnl_movement = (simulated_exit_price - reentry_price) * trade.size
    else:  # short
        simulated_pnl_movement = (reentry_price - simulated_exit_price) * trade.size

    # For simplicity, assume costs remain same as original trade
    # (we're just extending the hold, not re-entering)
    simulated_pnl = simulated_pnl_movement + trade.pnl

    # Calculate PnL change vs actual
    pnl_change_vs_actual = simulated_pnl - trade.pnl

    return SimulatedHold(
        hold_bars=hold_bars,
        simulated_pnl=simulated_pnl,
        pnl_change_vs_actual=pnl_change_vs_actual,
        simulated_exit_reason=simulated_exit_reason,
        simulated_exit_bar_offset=simulated_exit_bar_offset,
        mfe_during_hold=mfe,
        mfe_bar_offset=mfe_bar_offset,
        mae_during_hold=mae,
        mae_bar_offset=mae_bar_offset,
    )
