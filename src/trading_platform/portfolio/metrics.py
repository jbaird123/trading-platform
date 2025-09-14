from __future__ import annotations

from datetime import datetime

from trading_platform.portfolio.trade import Trade


def calculate_equity_curve(
    trades: list[Trade], initial_cash: float
) -> list[tuple[datetime, float]]:
    """
    Calculates the equity curve from a list of trades and initial cash.
    """
    equity_curve = [(datetime(1, 1, 1), initial_cash)]  # Placeholder for initial equity
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
