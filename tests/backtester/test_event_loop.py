from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trading_platform.backtester.event_loop import EventLoop
from trading_platform.backtester.telemetry import TelemetryTracker

from tests.backtester.event_loop_fixtures import (
    sample_bars,
    sample_intents,
    sample_risk_events,
)
from tests.backtester.factories import intent_factory, risk_event_factory


def bar_at(minute_offset: int = 0) -> dict:
    open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
        minutes=minute_offset
    )
    close_time = open_time + timedelta(minutes=1)
    return {
        "open_time": open_time,
        "close_time": close_time,
        "open": 1.0 + minute_offset * 0.01,
        "close": 1.05 + minute_offset * 0.01,
        "high": 1.1,
        "low": 0.9,
    }


def test_event_loop_yields_fill_on_next_bar() -> None:
    loop = EventLoop()
    bar1 = bar_at(0)
    bar2 = bar_at(1)
    intent = intent_factory(side="long")

    fills_first = list(loop.on_bar(bar1, intents=[intent]))
    fills_second = list(loop.on_bar(bar2))

    assert fills_first == []
    assert len(fills_second) == 1
    assert fills_second[0].intent == intent
    assert fills_second[0].timestamp == bar2["open_time"]


def test_event_loop_handles_multiple_intents() -> None:
    loop = EventLoop()
    loop.on_bar(
        bar_at(0),
        intents=[intent_factory(side="long"), intent_factory(side="short")],
    )
    fills = list(loop.on_bar(bar_at(1)))

    assert len(fills) == 2
    assert fills[0].intent is not None
    assert fills[0].intent.intent_type == "enter_long"
    assert fills[1].intent is not None
    assert fills[1].intent.intent_type == "enter_short"


def test_event_loop_applies_risk_events_immediately() -> None:
    telemetry = TelemetryTracker()
    loop = EventLoop(telemetry=telemetry)
    bar = bar_at(0)
    event = risk_event_factory(price=0.95)

    fills = list(loop.on_bar(bar, risk_events=[event]))

    assert len(fills) == 1
    fill = fills[0]
    assert fill.intent is None
    assert fill.price == 0.95
    assert telemetry.history
    last = list(telemetry.history)[-1]
    assert last["bars_processed"] == 1
    assert last["fills_generated"] == 1


def test_sample_fixture_matches_expected_behavior() -> None:
    loop = EventLoop()
    bars = sample_bars()
    intents = sample_intents()

    fills_0 = list(loop.on_bar(bars[0], intents=intents))
    fills_1 = list(loop.on_bar(bars[1]))
    fills_2 = list(loop.on_bar(bars[2], risk_events=sample_risk_events()))

    assert fills_0 == []
    assert len(fills_1) == len(intents)
    assert fills_1[0].intent == intents[0]
    assert fills_1[1].intent == intents[1]
    # third bar should only produce the risk-event fill
    assert len(fills_2) == 1
    assert fills_2[0].intent is None
