from __future__ import annotations

from datetime import datetime

from trading_platform.portfolio.trade import Trade


def calculate_equity_curve(
    trades: list[Trade], initial_cash: float
) -> list[tuple[datetime, float]]:
    """
    Calculates the equity curve from a list of trades and initial cash.
    """
    if not trades:
        return []
    # Use first trade's entry time as the starting point for the equity curve
    start_time = trades[0].entry_time
    equity_curve: list[tuple[datetime, float]] = [(start_time, initial_cash)]
    current_equity = initial_cash
    for trade in trades:
        current_equity += trade.pnl
        equity_curve.append((trade.exit_time, current_equity))
    return equity_curve


def calculate_win_rate(trades: list[Trade]) -> float:
    """
    Calculates the win rate from a list of trades.
    """
    if not trades:
        return 0.0

    winning_trades = [trade for trade in trades if trade.pnl > 0]
    return len(winning_trades) / len(trades)
