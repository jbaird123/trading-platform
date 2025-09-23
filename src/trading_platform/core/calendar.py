from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class Release:
    """Represents a scheduled event (e.g., high-impact news release)."""

    time: datetime
    meta: dict[str, Any]


def build_blackout_events(
    releases: Iterable[Release], pre: timedelta, post: timedelta
) -> list[dict[str, Any]]:
    """Convert point-in-time releases to blackout event windows.

    Each release becomes a dict: {"start": t-pre, "end": t+post, "meta": meta}.
    """
    events: list[dict[str, Any]] = []
    for r in releases:
        events.append({"start": r.time - pre, "end": r.time + post, "meta": r.meta})
    return events
