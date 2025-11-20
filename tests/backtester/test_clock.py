from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from trading_platform.backtester.clock import BarClock
from trading_platform.backtester.execution_engine import ExecutionEngineError


def bar_at(minute_offset: int = 0) -> dict:
    open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
        minutes=minute_offset
    )
    close_time = open_time + timedelta(minutes=1)
    return {
        "open_time": open_time,
        "close_time": close_time,
        "open": 1.0,
        "close": 1.1,
    }


def test_clock_returns_decision_and_entry_times() -> None:
    clock = BarClock()
    frame = clock.advance(bar_at(0))

    assert frame.open_time == frame.entry_open_time == frame.bar["open_time"]
    assert frame.close_time == frame.decision_time == frame.bar["close_time"]
    assert frame.decision_time > frame.entry_open_time


def test_clock_enforces_monotonic_bars() -> None:
    clock = BarClock()
    clock.advance(bar_at(0))

    with pytest.raises(ExecutionEngineError):
        clock.advance(bar_at(0))  # duplicate time not allowed


def test_clock_requires_open_and_close_times() -> None:
    clock = BarClock()
    bad_bar = {"open": 1.0}

    with pytest.raises(ExecutionEngineError):
        clock.advance(bad_bar)
