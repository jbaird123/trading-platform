from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.portfolio.portfolio import PortfolioManager


def _bar(ts: datetime, o: float, h: float, lo: float, c: float) -> pd.Series:
    s = pd.Series({"open": o, "high": h, "low": lo, "close": c})
    s.name = ts
    return s


def test_short_position_triggers_stop_loss_then_take_profit():
    pm = PortfolioManager(initial_cash=0.0)
    ts = datetime(2023, 1, 1, 0)
    # Open short with SL=101 and TP=99 (offsets from entry 100 implied)
    pm.create_new_position(
        symbol="X",
        side="short",
        entry_price=100.0,
        size=1.0,
        entry_time=ts,
        stop_loss=1.0,
        take_profit=1.0,
    )
    # Bar hits stop (high >= 101)
    pm.on_bar(_bar(ts, 100.0, 101.5, 99.5, 100.5), current_signal="short")
    assert pm.current_position is None
    assert pm.trades and pm.trades[-1].exit_reason == "stop-loss"

    # Re-open and hit TP (low <= 99)
    pm.create_new_position(
        symbol="X",
        side="short",
        entry_price=100.0,
        size=1.0,
        entry_time=ts,
        stop_loss=1.0,
        take_profit=1.0,
    )
    pm.on_bar(_bar(ts, 100.0, 100.1, 98.9, 99.5), current_signal="short")
    assert pm.current_position is None
    assert pm.trades and pm.trades[-1].exit_reason == "take-profit"


def test_signal_change_respects_allow_flip_flag():
    pm = PortfolioManager()
    ts = datetime(2023, 1, 1)
    pm.create_new_position(
        symbol="X", side="long", entry_price=10.0, size=1.0, entry_time=ts
    )
    # Different signal with allow_flip_on_bar=False should just close and return
    pm.on_bar(
        _bar(ts, 10.0, 10.0, 10.0, 10.0),
        current_signal="short",
        allow_flip_on_bar=False,
    )
    assert pm.current_position is None
