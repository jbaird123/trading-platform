"""
Consolidated tests for TradingWindowPolicy blackout logic.
"""

from __future__ import annotations

from datetime import datetime, time, timezone

from trading_platform.core.policy import TradingWindowPolicy

# Validates: [SYS-1.5.4]


def test_static_blackout_wrap_midnight_true() -> None:
    """Blackout window that wraps midnight should flag timestamps inside the window."""
    policy = TradingWindowPolicy(static_utc=[(time(23, 0), time(1, 0))])
    ts = datetime(2023, 1, 1, 23, 30, tzinfo=timezone.utc)
    assert policy._in_static_blackout(ts) is True


def test_event_blackout_true_and_invalid_event_ignored() -> None:
    """Valid blackout events apply while malformed entries are ignored."""
    start = datetime(2023, 1, 1, 10, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 11, tzinfo=timezone.utc)
    policy = TradingWindowPolicy(
        static_utc=[], events=[{"start": start, "end": end}, {"foo": 1}]
    )
    ts = datetime(2023, 1, 1, 10, 30, tzinfo=timezone.utc)
    assert policy._in_event_blackout(ts) is True


def test_reason_none_outside_blackouts() -> None:
    """Reason is None when outside any blackout windows."""
    policy = TradingWindowPolicy(static_utc=[], events=[])
    ts = datetime(2023, 1, 1, 12, tzinfo=timezone.utc)
    assert policy.reason(ts) is None


def test_reason_static_wrap_and_non_wrap_and_event() -> None:
    """Ensure reason prioritises blackout types correctly for static and event windows."""
    policy = TradingWindowPolicy.from_config(
        blackout_utc=[("10:00", "11:00"), ("23:00", "01:00")], blackout_events=[]
    )
    assert policy.reason(datetime(2024, 1, 1, 10, 30)) == "blackout_static"
    assert policy.reason(datetime(2024, 1, 2, 0, 30)) == "blackout_static"
    assert policy.reason(datetime(2024, 1, 2, 2, 0)) is None

    policy_events = TradingWindowPolicy.from_config(
        blackout_utc=[],
        blackout_events=[
            {"start": "bad", "end": "bad"},
            {"start": datetime(2024, 1, 1, 9), "end": datetime(2024, 1, 1, 10)},
        ],
    )
    assert policy_events.reason(datetime(2024, 1, 1, 9, 30)) == "blackout_event"
    assert policy_events.reason(datetime(2024, 1, 1, 10, 30)) is None
