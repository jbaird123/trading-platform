from __future__ import annotations

from datetime import datetime

from trading_platform.core.policy import TradingWindowPolicy


def test_reason_static_wrap_and_non_wrap_and_event():
    # Static non-wrap window (10:00-11:00) and wrap window (23:00-01:00)
    pol = TradingWindowPolicy.from_config(
        blackout_utc=[("10:00", "11:00"), ("23:00", "01:00")], blackout_events=[]
    )
    assert pol.reason(datetime(2024, 1, 1, 10, 30)) == "blackout_static"  # non-wrap
    assert pol.reason(datetime(2024, 1, 2, 0, 30)) == "blackout_static"  # wrap
    assert pol.reason(datetime(2024, 1, 2, 2, 0)) is None

    # Event blackout with a non-datetime event ignored
    pol2 = TradingWindowPolicy.from_config(
        blackout_utc=[],
        blackout_events=[
            {"start": "bad", "end": "bad"},
            {"start": datetime(2024, 1, 1, 9), "end": datetime(2024, 1, 1, 10)},
        ],
    )
    assert pol2.reason(datetime(2024, 1, 1, 9, 30)) == "blackout_event"
    assert pol2.reason(datetime(2024, 1, 1, 10, 30)) is None
