from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from trading_platform.backtester.models import ExecutionIntent

from tests.backtester.factories import intent_factory, risk_event_factory


def sample_bars() -> list[dict[str, Any]]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for offset in range(3):
        open_time = base + timedelta(minutes=offset)
        close_time = open_time + timedelta(minutes=1)
        bars.append(
            {
                "open_time": open_time,
                "close_time": close_time,
                "open": 1.0 + offset * 0.01,
                "close": 1.05 + offset * 0.01,
                "high": 1.1 + offset * 0.01,
                "low": 0.9,
            }
        )
    return bars


def sample_intents() -> list[ExecutionIntent]:
    return [intent_factory(side="long"), intent_factory(side="short")]


def sample_risk_events():
    return [risk_event_factory(price=0.97, minute_offset=2)]
