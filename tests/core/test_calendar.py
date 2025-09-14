from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trading_platform.core.calendar import Release, build_blackout_events


def test_build_blackout_events_converts_releases_to_windows():
    t = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    rels = [Release(time=t, meta={"impact": "high", "name": "CPI"})]
    events = build_blackout_events(
        rels, pre=timedelta(minutes=10), post=timedelta(minutes=30)
    )
    assert len(events) == 1
    e = events[0]
    assert e["start"] == t - timedelta(minutes=10)
    assert e["end"] == t + timedelta(minutes=30)
    assert e["meta"]["impact"] == "high"
