from __future__ import annotations

from datetime import datetime

import pytest
from trading_platform.portfolio.trade import Trade


def test_calculate_equity_curve_simple():
    """
    Tests the calculation of a simple equity curve from a list of trades.
    """
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2023, 1, 1),
            exit_time=datetime(2023, 1, 2),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=10000,
            pnl=100.0,
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2023, 1, 3),
            exit_time=datetime(2023, 1, 4),
            entry_price=1.0,
            exit_price=0.9,
            side="short",
            size=10000,
            pnl=100.0,  # Profit of 100
        ),
    ]
    initial_cash = 1000.0
    # Expected equity curve:
    #   [1000.0 (initial), 1100.0 (after trade 1),
    #    1200.0 (after trade 2)]
    # Note: Equity curve typically includes initial capital and then cumulative PnL
    # We'll define the equity curve as a series of (timestamp, equity) points.
    # For simplicity, we'll assume equity is updated at exit_time.

    # This test will fail until calculate_equity_curve is implemented.
    from trading_platform.portfolio.metrics import calculate_equity_curve

    equity_curve = calculate_equity_curve(trades, initial_cash)

    assert len(equity_curve) == len(trades) + 1
    assert equity_curve[0][1] == initial_cash
    assert equity_curve[1][1] == initial_cash + trades[0].pnl
    assert equity_curve[2][1] == initial_cash + trades[0].pnl + trades[1].pnl


def test_calculate_win_rate_simple():
    """
    Tests the calculation of win rate from a list of trades.
    """
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2023, 1, 1),
            exit_time=datetime(2023, 1, 2),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=10000,
            pnl=100.0,  # Win
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2023, 1, 3),
            exit_time=datetime(2023, 1, 4),
            entry_price=1.0,
            exit_price=0.9,
            side="short",
            size=10000,
            pnl=-50.0,  # Loss
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2023, 1, 5),
            exit_time=datetime(2023, 1, 6),
            entry_price=1.0,
            exit_price=1.05,
            side="long",
            size=10000,
            pnl=50.0,  # Win
        ),
    ]

    # This test will fail until calculate_win_rate is implemented.
    from trading_platform.portfolio.metrics import calculate_win_rate

    win_rate = calculate_win_rate(trades)

    assert win_rate == pytest.approx(2 / 3)  # 2 wins out of 3 trades
