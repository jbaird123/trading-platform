from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pytest
from trading_platform.backtester.clock import ClockFrame
from trading_platform.backtester.models import DecisionSnapshot
from trading_platform.backtester.portfolio_manager import ActivePosition
from trading_platform.backtester.risk import RiskExitAdapter
from trading_platform.core.types import BarData
from trading_platform.portfolio.position import Position


def _make_frame(minute: int = 0) -> ClockFrame:
    open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute)
    close_time = open_time + timedelta(minutes=1)
    series = pd.Series(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05},
        name=open_time,
    )
    bar: dict[str, Any] = {"series": series}
    return ClockFrame(
        bar=bar,
        open_time=open_time,
        close_time=close_time,
        entry_open_time=open_time,
        decision_time=close_time,
    )


class DummyREM:
    def __init__(self, response: dict[str, Any] | None) -> None:
        self.response = response
        self.calls: list[tuple[Position, BarData]] = []

    def check_exits(
        self, position: Position, current_bar: BarData, *args: Any, **_: Any
    ) -> dict[str, Any] | None:
        self.calls.append((position, current_bar))
        return self.response


def _active_position(
    side: str = "long", position: Position | None = None
) -> ActivePosition:
    decision = DecisionSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        price=1.0,
        side=side,  # type: ignore[arg-type]
        size=10000.0,
    )
    if position is None:
        position = Position(
            symbol="EURUSD",
            entry_time=decision.timestamp,
            entry_price=1.0,
            entry_mid_price=1.0,
            side=side,
            size=10000.0,
            context_at_entry={"foo": "bar"},
        )
    return ActivePosition(
        position_id="pos-1",
        decision=decision,
        position=position,
        entry_cost=0.0,
        entry_cost_breakdown={"spread": 0.0, "commission": 0.0, "slippage": 0.0},
    )


def test_risk_adapter_returns_event_with_clock_timestamp() -> None:
    adapter = RiskExitAdapter(rem=DummyREM({"exit_price": 0.99, "reason": "stop_loss"}))
    frame = _make_frame()
    events = adapter.evaluate(
        frame=frame,
        positions=[_active_position()],
        current_bar=frame.bar["series"],
    )

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == frame.open_time
    assert event.price == pytest.approx(0.99)
    assert event.reason == "stop_loss"


def test_risk_adapter_validates_reason() -> None:
    adapter = RiskExitAdapter(rem=DummyREM({"exit_price": 1.01, "reason": "weird"}))
    frame = _make_frame()

    with pytest.raises(ValueError):
        adapter.evaluate(
            frame=frame,
            positions=[_active_position()],
            current_bar=frame.bar["series"],
        )


def test_risk_adapter_passes_through_real_rem() -> None:
    from trading_platform.risk_manager.core import REMConfig, RiskExitManager
    from trading_platform.risk_manager.models import AbsoluteLevelRule

    config = REMConfig(stop_loss=AbsoluteLevelRule(type="absolute", price=0.99))
    rem = RiskExitManager(config=config, instrument={"pip_location": 0.0001})
    active = _active_position(
        position=Position(
            symbol="EURUSD",
            entry_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            entry_price=1.0,
            entry_mid_price=1.0,
            side="long",
            size=10000.0,
            context_at_entry={"strategy_features": {}},
        )
    )
    frame = _make_frame()
    frame.bar["low"] = 0.98  # trigger stop
    adapter = RiskExitAdapter(rem=rem)

    events = adapter.evaluate(
        frame=frame, positions=[active], current_bar=frame.bar["series"]
    )

    assert len(events) == 1
    assert events[0].reason == "stop_loss"
