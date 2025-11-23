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

    dt_index = market_data.index.tolist()

    for trade in trades:
        exit_time = getattr(trade, "exit_time", None)
        try:
            exit_idx = dt_index.index(exit_time)
        except ValueError:
            continue

        post_exit_data = market_data.iloc[exit_idx + 1 :]
        if len(post_exit_data) == 0:
            post_exit_analysis = PostExitAnalysis(simulated_holds=[])
            object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)
            continue

        simulated_holds = []
        for horizon in horizons:
            simulation = run_single_trade_simulation(
                trade=trade, price_data=post_exit_data, hold_bars=horizon
            )
            simulated_holds.append(simulation)

        post_exit_analysis = PostExitAnalysis(simulated_holds=simulated_holds)
        object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)
