from __future__ import annotations

from typing import Any

import pandas as pd


def enrich_trades_with_post_exit_analysis(
    trades: list[Any], market_data: pd.DataFrame, horizons: list[int]
) -> None:
    """
    Enrich trades with realistic post-exit simulations.

    For each trade, simulates holding the position for N additional bars
    after exit, accounting for stop-loss and take-profit triggers.
    Mutates the Trade objects in-place by attaching post_exit_analysis.
    """
    from trading_platform.backtester.analysis.exit_simulation import (
        run_single_trade_simulation,
    )
    from trading_platform.reporting.models.exit_analysis import (
        PostExitAnalysis,
    )

    if not trades or not horizons:
        return

    dt_index = market_data.index
    max_horizon = max(horizons)

    for trade in trades:
        exit_time = getattr(trade, "exit_time", None)
        try:
            loc = dt_index.get_loc(exit_time)
            # get_loc can return int, slice, or boolean array
            if isinstance(loc, int):
                exit_idx = loc
            elif isinstance(loc, slice):
                # If duplicate timestamps, take the first occurrence
                exit_idx = loc.start if loc.start is not None else 0
            else:
                # Boolean array case - find first True
                import numpy as np

                exit_idx = int(np.where(loc)[0][0])
        except (KeyError, TypeError, ValueError, IndexError):
            continue

        start = exit_idx + 1
        if start >= len(market_data):
            # No bars after exit; still attach empty analysis for consistency.
            post_exit_analysis = PostExitAnalysis(simulated_holds=[])
            object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)
            continue

        # Only slice the maximum horizon needed instead of the full tail;
        # ensure at least one row is available for horizon=0 cases.
        slice_len = max(max_horizon, 1)
        post_exit_data = market_data.iloc[start : start + slice_len]

        simulated_holds = []
        for horizon in horizons:
            simulation = run_single_trade_simulation(
                trade=trade, price_data=post_exit_data, hold_bars=horizon
            )
            simulated_holds.append(simulation)

        post_exit_analysis = PostExitAnalysis(simulated_holds=simulated_holds)
        object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)
