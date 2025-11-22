from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from trading_platform.backtester.event_loop import EventLoop
from trading_platform.backtester.portfolio_manager import PortfolioManager

from tests.backtester.factories import intent_factory, risk_event_factory


def _bar(minute: int) -> dict:
    open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute)
    close_time = open_time + timedelta(minutes=1)
    return {
        "open_time": open_time,
        "close_time": close_time,
        "open": 1.0000,
        "high": 1.0020,
        "low": 0.9990,
        "close": 1.0010,
        "bar": pd.Series(
            {"open": 1.0, "high": 1.002, "low": 0.999, "close": 1.001},
            name=open_time,
        ),
    }


def test_event_loop_routes_fills_through_portfolio() -> None:
    pm = PortfolioManager(
        instrument={"symbol": "EURUSD", "lot_size": 100000},
        cost_model={"spread_per_unit": 0.0002},
        default_position_size=10_000.0,
    )
    loop = EventLoop(portfolio=pm)
    intent = intent_factory(bar_index=0)

    fills = list(loop.on_bar(_bar(0), intents=[intent]))
    assert len(fills) == 1
    assert len(pm.active_positions) == 1

    loop.on_bar(_bar(1))

    risk_event = risk_event_factory(decision=intent.decision, price=0.9950)
    loop.on_bar(_bar(2), risk_events=[risk_event])

    assert not pm.active_positions
    assert pm.trades
