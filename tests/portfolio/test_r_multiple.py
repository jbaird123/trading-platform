# Validates: [PM-5.6]
from __future__ import annotations

from datetime import datetime

from pytest import approx
from trading_platform.portfolio.portfolio import PortfolioManager


def test_r_multiple_long_with_stop():
    pm = PortfolioManager(initial_cash=0.0)
    pm.create_new_position(
        symbol="X",
        side="long",
        entry_price=100.0,
        size=10.0,
        entry_time=datetime(2024, 1, 1),
        initial_risk_ccy=20.0,  # (100 - 98) * 10
    )
    pm.close_position(
        exit_price=101.0, exit_time=datetime(2024, 1, 1, 1), context_at_exit=None
    )
    t = pm.trades[0]
    # pnl = (101-100)*10 = 10; initial risk = 20; r = 0.5
    assert t.r_multiple == approx(0.5)


def test_r_multiple_short_with_stop():
    pm = PortfolioManager(initial_cash=0.0)
    pm.create_new_position(
        symbol="X",
        side="short",
        entry_price=100.0,
        size=2.0,
        entry_time=datetime(2024, 1, 1),
        initial_risk_ccy=10.0,  # (105 - 100) * 2
    )
    pm.close_position(
        exit_price=90.0, exit_time=datetime(2024, 1, 1, 1), context_at_exit=None
    )
    t = pm.trades[0]
    # pnl = (100-90)*2 = 20; initial risk = 10; r = 2.0
    assert t.r_multiple == approx(2.0)


def test_r_multiple_none_without_stop():
    pm = PortfolioManager(initial_cash=0.0)
    pm.create_new_position(
        symbol="X",
        side="long",
        entry_price=100.0,
        size=1.0,
        entry_time=datetime(2024, 1, 1),
        # no stop
    )
    pm.close_position(
        exit_price=110.0, exit_time=datetime(2024, 1, 1, 1), context_at_exit=None
    )
    t = pm.trades[0]
    assert t.r_multiple is None
