# Validates: [JSON-11.6]
from datetime import datetime

import pytest
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import compute_equity_stats


@pytest.fixture
def mock_trades_for_drawdown() -> list[Trade]:
    """Creates a list of mock trades designed to test drawdown logic."""

    # A dummy trade factory
    def _trade(pnl: float, time: datetime) -> Trade:
        return Trade(
            symbol="DUMMY",
            entry_time=time,
            exit_time=time,
            entry_price=1.0,
            exit_price=2.0,
            side="long",
            size=1.0,
            pnl=pnl,
        )

    return [
        _trade(pnl=1000.0, time=datetime(2023, 1, 2)),  # Equity: 11000 (New Peak)
        _trade(pnl=-500.0, time=datetime(2023, 1, 3)),  # Equity: 10500 (DD: 500)
        _trade(pnl=-1000.0, time=datetime(2023, 1, 4)),  # Equity: 9500 (DD: 1500)
        _trade(pnl=500.0, time=datetime(2023, 1, 5)),  # Equity: 10000 (DD: 1000)
        _trade(pnl=2000.0, time=datetime(2023, 1, 6)),  # Equity: 12000 (New Peak)
        _trade(pnl=-100.0, time=datetime(2023, 1, 7)),  # Equity: 11900 (DD: 100)
    ]


def test_compute_equity_stats_for_drawdown(mock_trades_for_drawdown: list[Trade]):
    """Validates the calculation of max_drawdown and its duration."""
    initial_cash = 10000.0

    result = compute_equity_stats(
        trades=mock_trades_for_drawdown, initial_cash=initial_cash
    )

    # Equity curve: 10000 -> 11000 -> 10500 -> 9500 -> 10000 -> 12000 -> 11900
    # Peaks: 10000, 11000, 12000
    # Drawdowns from 11000 peak: 500, 1500, 1000
    # Drawdowns from 12000 peak: 100
    # The max drawdown is 1500.
    assert result["max_drawdown"] == 1500.0

    # The max drawdown of 1500 occurs at the 3rd trade (index 2).
    # The drawdown starts after the 1st trade (peak at 11000).
    # Duration is 2 bars (trade 2 and trade 3).
    assert result["dd_duration_bars"] == 2
