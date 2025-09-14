from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any


@dataclass
class TradingWindowPolicy:
    """Centralized trading window policy (blackouts and exceptions).

    Supports static daily UTC windows and explicit event-based blackout windows.

    - Static windows: list of ("HH:MM", "HH:MM") strings; wraps past midnight.
    - Event windows: list of dicts with at least "start"/"end" datetimes.

    Methods:
    - can_open(ts): True if opening new positions is allowed at ts.
    - reason(ts): Optional reason string when opening is not allowed.
    """

    static_utc: list[tuple[time, time]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _parse_static_utc(
        windows: list[tuple[str, str]] | None,
    ) -> list[tuple[time, time]]:
        parsed: list[tuple[time, time]] = []
        if not windows:
            return parsed
        for start, end in windows:
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            parsed.append((time(sh, sm), time(eh, em)))
        return parsed

    @classmethod
    def from_config(
        cls,
        *,
        blackout_utc: list[tuple[str, str]] | None = None,
        blackout_events: list[dict[str, Any]] | None = None,
    ) -> TradingWindowPolicy:
        return cls(
            static_utc=cls._parse_static_utc(blackout_utc), events=blackout_events or []
        )

    def _in_static_blackout(self, ts: datetime) -> bool:
        if not self.static_utc:
            return False
        t = ts.time()
        for start_t, end_t in self.static_utc:
            if start_t <= end_t:
                if start_t <= t < end_t:
                    return True
            else:  # wrap past midnight
                if t >= start_t or t < end_t:
                    return True
        return False

    def _in_event_blackout(self, ts: datetime) -> bool:
        if not self.events:
            return False
        for ev in self.events:
            start = ev.get("start")
            end = ev.get("end")
            if isinstance(start, datetime) and isinstance(end, datetime):
                if start <= ts < end:
                    return True
        return False

    def can_open(self, ts: datetime) -> bool:
        return not (self._in_static_blackout(ts) or self._in_event_blackout(ts))

    def reason(self, ts: datetime) -> str | None:
        if self._in_static_blackout(ts):
            return "blackout_static"
        if self._in_event_blackout(ts):
            return "blackout_event"
        return None
