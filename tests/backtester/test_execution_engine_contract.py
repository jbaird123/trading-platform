from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, cast

import pytest
from trading_platform.backtester.execution_engine import (
    ExecutionEngineError,
    NextBarExecutionEngine,
)
from trading_platform.backtester.models import (
    DecisionSnapshot,
    ExecutionIntent,
    RiskExitEvent,
)


def make_bar(open_time: datetime) -> dict:
    """Helper to build a minimal OHLC bar for testing."""
    close_time = open_time + timedelta(minutes=1)
    return {
        "open_time": open_time,
        "close_time": close_time,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
    }


def make_snapshot(
    side: Literal["long", "short"] = "long", size: float = 1.0
) -> DecisionSnapshot:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return DecisionSnapshot(timestamp=ts, price=1.0, side=side, size=size)


def make_intent(side: Literal["long", "short"] = "long") -> ExecutionIntent:
    snapshot = make_snapshot(side=side)
    intent_type = cast(
        Literal["enter_long", "enter_short"],
        "enter_long" if side == "long" else "enter_short",
    )
    return ExecutionIntent(
        decision=snapshot,
        intent_type=intent_type,
        execution_model="next_bar_open",
    )


def test_no_intents_produces_no_fills() -> None:
    engine = NextBarExecutionEngine()
    bar = make_bar(datetime(2024, 1, 1, tzinfo=timezone.utc))

    fills = list(engine.advance_clock(bar))

    assert fills == []


def test_next_bar_fill_occurs_after_one_clock_advance() -> None:
    engine = NextBarExecutionEngine()
    first_bar = make_bar(datetime(2024, 1, 1, tzinfo=timezone.utc))
    second_bar = make_bar(first_bar["open_time"] + timedelta(minutes=1))
    intent = make_intent("long")

    engine.submit_intent(intent)
    fills = list(engine.advance_clock(first_bar))

    assert len(fills) == 1
    fill = fills[0]
    assert fill.intent == intent
    assert fill.timestamp == first_bar["open_time"]
    assert fill.price == first_bar["open"]

    assert list(engine.advance_clock(second_bar)) == []


def test_multiple_intents_fill_fifo_on_next_bar() -> None:
    engine = NextBarExecutionEngine()
    bar1 = make_bar(datetime(2024, 1, 1, tzinfo=timezone.utc))
    bar2 = make_bar(bar1["open_time"] + timedelta(minutes=1))
    intent_long = make_intent("long")
    intent_short = make_intent("short")

    engine.submit_intent(intent_long)
    engine.submit_intent(intent_short)

    fills = list(engine.advance_clock(bar1))

    assert [f.intent for f in fills] == [intent_long, intent_short]
    assert list(engine.advance_clock(bar2)) == []


def test_risk_event_generates_immediate_fill() -> None:
    engine = NextBarExecutionEngine()
    bar = make_bar(datetime(2024, 1, 1, tzinfo=timezone.utc))
    snapshot = make_snapshot()
    event = RiskExitEvent(
        timestamp=bar["open_time"],
        price=0.99,
        reason="stop_loss",
        decision=snapshot,
    )

    engine.submit_risk_event(event)
    fills = list(engine.advance_clock(bar))

    assert len(fills) == 1
    fill = fills[0]
    assert fill.intent is None
    assert fill.decision == event.decision
    assert fill.timestamp == event.timestamp
    assert fill.price == event.price
    assert fill.reason == "stop_loss"


def test_rejects_unsupported_execution_model() -> None:
    engine = NextBarExecutionEngine()
    bad_intent = ExecutionIntent(
        decision=make_snapshot(),
        intent_type="enter_long",
        execution_model="next_bar_open",
    )
    object.__setattr__(bad_intent, "execution_model", "current_bar_close")

    with pytest.raises(ExecutionEngineError):
        engine.submit_intent(bad_intent)


def test_requires_decision_snapshot() -> None:
    engine = NextBarExecutionEngine()
    snapshot = make_snapshot()
    bad_event = RiskExitEvent(
        timestamp=snapshot.timestamp,
        price=1.0,
        reason="stop_loss",
        decision=None,  # type: ignore[arg-type]
    )

    with pytest.raises(ExecutionEngineError):
        engine.submit_risk_event(bad_event)


def test_bars_must_be_monotonic() -> None:
    engine = NextBarExecutionEngine()
    bar = make_bar(datetime(2024, 1, 1, tzinfo=timezone.utc))

    engine.advance_clock(bar)
    with pytest.raises(ExecutionEngineError):
        engine.advance_clock(bar)  # duplicate timestamp


def test_bar_missing_required_fields_raises() -> None:
    engine = NextBarExecutionEngine()
    bar = {"open_time": datetime(2024, 1, 1, tzinfo=timezone.utc)}

    with pytest.raises(ExecutionEngineError):
        engine.advance_clock(bar)  # missing close_time/open price
