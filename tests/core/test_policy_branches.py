# Validates: [SYS-1.5.4]
from __future__ import annotations

from datetime import datetime, time, timezone

from trading_platform.core.policy import TradingWindowPolicy


def test_static_blackout_wrap_midnight_true():
    # Blackout 23:00 to 01:00 should wrap midnight; 23:30 is inside
    p = TradingWindowPolicy(static_utc=[(time(23, 0), time(1, 0))])
    ts = datetime(2023, 1, 1, 23, 30, tzinfo=timezone.utc)
    assert p._in_static_blackout(ts) is True


def test_event_blackout_true_and_invalid_event_ignored():
    # One valid event window, one invalid dict should be ignored
    start = datetime(2023, 1, 1, 10, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 11, tzinfo=timezone.utc)
    p = TradingWindowPolicy(
        static_utc=[], events=[{"start": start, "end": end}, {"foo": 1}]
    )
    assert (
        p._in_event_blackout(datetime(2023, 1, 1, 10, 30, tzinfo=timezone.utc)) is True
    )


def test_reason_none_outside_blackouts():
    p = TradingWindowPolicy(static_utc=[], events=[])
    ts = datetime(2023, 1, 1, 12, tzinfo=timezone.utc)
    assert p.reason(ts) is None
