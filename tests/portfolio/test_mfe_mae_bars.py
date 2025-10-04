# Validates: [JSON-11.25]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest import approx
from trading_platform.portfolio.portfolio import PortfolioManager

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "TEST",
    "asset_class": "Stock",
    "point_value": 1.0,
    "tick_size": 0.01,
}


def _bar(ts: str, o: float, h: float, lo: float, c: float) -> pd.Series:
    s = pd.Series({"open": o, "high": h, "low": lo, "close": c})
    s.name = pd.Timestamp(ts)
    return s


def test_mfe_mae_and_bars_held_long():
    pm = PortfolioManager(initial_cash=0.0, instrument=TEST_INSTRUMENT)
    pm.create_new_position(
        symbol="X",
        side="long",
        entry_price=100.0,
        size=10.0,
        entry_time=datetime(2024, 1, 1),
    )

    pm.on_bar(
        _bar("2024-01-01 00:00", 100.0, 102.0, 99.5, 101.0), current_signal="long"
    )
    pm.on_bar(_bar("2024-01-01 01:00", 101.0, 101.5, 98.0, 99.0), current_signal="long")
    pm.close_position(
        exit_price=100.0,
        exit_time=datetime(2024, 1, 1, 2),
        context_at_exit=None,
    )

    t = pm.trades[0]
    # Long: MFE = max(high - entry) * size = (102-100)*10 = 20
    #       MAE = max(entry - low) * size = (100-98)*10 = 20
    assert t.mfe_currency == approx(20.0)
    assert t.mae_currency == approx(20.0)
    assert t.bars_held == 2


def test_mfe_mae_and_bars_held_short():
    pm = PortfolioManager(initial_cash=0.0, instrument=TEST_INSTRUMENT)
    pm.create_new_position(
        symbol="X",
        side="short",
        entry_price=100.0,
        size=5.0,
        entry_time=datetime(2024, 1, 1),
    )

    pm.on_bar(
        _bar("2024-01-01 00:00", 100.0, 103.0, 95.0, 97.0), current_signal="short"
    )
    pm.close_position(
        exit_price=99.0, exit_time=datetime(2024, 1, 1, 1), context_at_exit=None
    )

    t = pm.trades[0]
    # Short: favorable = (entry - low) * size = (100-95)*5 = 25
    #        adverse   = (high - entry) * size = (103-100)*5 = 15
    assert t.mfe_currency == approx(25.0)
    assert t.mae_currency == approx(15.0)
    assert t.bars_held == 1
