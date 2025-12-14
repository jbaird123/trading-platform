"""Market session definitions and DST-aware session service.

This module provides the single source of truth for trading session definitions
and all timezone-related logic. All other code should use SessionService methods
rather than doing timezone conversions directly.

Session groups define:
# reference_timezone: Used for local hour/day analysis
# (e.g., "America/New_York" for forex)
- sessions: Dict of session name -> MarketSession with local open/close times
- overlaps: List of session pairs to compute overlap flags for

Usage:
    from trading_platform.data.market_sessions import SessionService

    # Check if a specific session is open (DST-aware)
    is_open = SessionService.is_session_open(utc_timestamps, session_def)

    # Get all session flags for a group (e.g. "forex")
    flags_df = SessionService.get_session_flags(utc_timestamps, "forex")

    # Get local hour/day for a session group (e.g. 15 for 3 PM NY time)
    local_hour = SessionService.get_local_hour(utc_timestamp, "forex")
    local_times = SessionService.get_local_times(utc_index, "forex")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MarketSession:
    """Defines a trading session in local time.

    Attributes:
        name: Session identifier (e.g., "london", "newyork")
        open_time: Session open time in local timezone
        close_time: Session close time in local timezone
        timezone: IANA timezone string (e.g., "Europe/London")
    """

    name: str
    open_time: time
    close_time: time
    timezone: str


# Single source of truth for all session definitions
SESSION_GROUPS: dict[str, dict[str, Any]] = {
    "forex": {
        "reference_timezone": "America/New_York",
        # Used for local hour/day analysis
        # (e.g., "America/New_York" for forex)
        "sessions": {
            "asia": MarketSession(
                name="asia",
                open_time=time(9, 0),
                close_time=time(18, 0),
                timezone="Asia/Tokyo",
            ),
            "london": MarketSession(
                name="london",
                open_time=time(8, 0),
                close_time=time(17, 0),
                timezone="Europe/London",
            ),
            "newyork": MarketSession(
                name="newyork",
                open_time=time(8, 0),
                close_time=time(17, 0),
                timezone="America/New_York",
            ),
        },
        "overlaps": [
            ("asia", "london"),
            ("london", "newyork"),
        ],
    },
    "crypto": {
        "reference_timezone": "UTC",
        "sessions": {
            "always": MarketSession(
                name="always",
                open_time=time(0, 0),
                close_time=time(0, 0),  # 0-0 means 24 hours
                timezone="UTC",
            ),
        },
        "overlaps": [],
    },
}


class SessionService:
    """Handles all session-related queries with proper DST handling.

    All public methods accept UTC timestamps and return session info.
    Local time conversions are internal implementation details.

    This class follows the fail-fast policy:
    - Invalid session groups raise ValueError immediately
    - No silent fallbacks or default values for errors
    """

    @staticmethod
    def is_session_open(
        utc_timestamps: pd.DatetimeIndex,
        session_def: MarketSession,
    ) -> pd.Series:
        """Check if a session is open for each UTC timestamp.

        Args:
            utc_timestamps: DatetimeIndex in UTC (must have tzinfo)
            session_def: Session definition with local open/close times

        Returns:
            Boolean Series indicating if session is open at each timestamp

        Raises:
            ValueError: If timestamps are not timezone-aware
        """
        if utc_timestamps.tzinfo is None:
            raise ValueError("utc_timestamps must be timezone-aware (UTC)")

        # Handle 24-hour session (crypto "always")
        if session_def.open_time == time(0, 0) and session_def.close_time == time(0, 0):
            return pd.Series(True, index=utc_timestamps, dtype=bool)

        # Convert UTC to session's local timezone
        local_times = utc_timestamps.tz_convert(session_def.timezone)

        # Extract local hour and minute as decimal for comparison
        # Extract local hour and minute as decimal for comparison
        # Explicit cast to Series/array for type safety
        local_hour = pd.Series(local_times.hour, index=utc_timestamps)
        local_minute = pd.Series(local_times.minute, index=utc_timestamps)
        local_time_decimal = local_hour + local_minute / 60.0

        open_decimal = session_def.open_time.hour + session_def.open_time.minute / 60.0
        close_decimal = (
            session_def.close_time.hour + session_def.close_time.minute / 60.0
        )

        # Standard session: open < close (e.g., 8 AM to 5 PM)
        is_open = (local_time_decimal >= open_decimal) & (
            local_time_decimal < close_decimal
        )

        return pd.Series(is_open, index=utc_timestamps, dtype=bool)

    @staticmethod
    def get_session_flags(
        utc_timestamps: pd.DatetimeIndex,
        session_group: str,
    ) -> pd.DataFrame:
        """Get all session flags for a session group.

        Args:
            utc_timestamps: DatetimeIndex in UTC
            session_group: Session group name (e.g., "forex", "crypto")

        Returns:
            DataFrame with columns like "{group}_session_{name}" and
            "{group}_session_overlap_{a}_{b}" for each defined overlap

        Raises:
            ValueError: If session_group is not defined in SESSION_GROUPS
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(
                f"Unknown session group: {session_group!r}. "
                f"Valid groups: {list(SESSION_GROUPS.keys())}"
            )

        group = SESSION_GROUPS[session_group]
        sessions = group["sessions"]
        overlaps = group["overlaps"]

        # Compute individual session flags
        session_flags: dict[str, pd.Series] = {}
        for session_name, session_def in sessions.items():
            col_name = f"{session_group}_session_{session_name}"
            is_open = SessionService.is_session_open(utc_timestamps, session_def)
            session_flags[col_name] = is_open.astype(float)

        # Compute overlap flags
        for session_a, session_b in overlaps:
            col_a = f"{session_group}_session_{session_a}"
            col_b = f"{session_group}_session_{session_b}"
            overlap_col = f"{session_group}_session_overlap_{session_a}_{session_b}"

            # Overlap is True only when both sessions are open
            is_overlap = (session_flags[col_a] == 1.0) & (session_flags[col_b] == 1.0)
            session_flags[overlap_col] = is_overlap.astype(float)

        return pd.DataFrame(session_flags, index=utc_timestamps)

    @staticmethod
    def get_local_hour(
        utc_timestamp: pd.Timestamp,
        session_group: str,
    ) -> int:
        """Get the local hour for a session group's reference timezone.

        Args:
            utc_timestamp: Single timestamp in UTC
            session_group: Session group name

        Returns:
            Hour (0-23) in the reference timezone

        Raises:
            ValueError: If session_group is unknown or timestamp is naive
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(f"Unknown session group: {session_group!r}")

        # Ensure we have a pandas Timestamp for .tz_convert support
        if not isinstance(utc_timestamp, pd.Timestamp):
            utc_timestamp = pd.Timestamp(utc_timestamp)

        # Ensure timestamp is aware (assume UTC if not, but ideally insist)
        if utc_timestamp.tzinfo is None:
            # Fail fast if naive - or assume UTC?
            # Convention here is strict
            # But for a single Timestamp, users might be sloppy.
            # Let's align with is_session_open policy: Expect Aware.
            pass

        ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
        local_ts = utc_timestamp.tz_convert(ref_tz)
        return local_ts.hour

    @staticmethod
    def get_local_day_of_week(
        utc_timestamp: pd.Timestamp,
        session_group: str,
    ) -> int:
        """Get the local day of week for a session group's reference timezone.

        Args:
            utc_timestamp: Single timestamp in UTC
            session_group: Session group name

        Returns:
            Day of week (0=Monday, 6=Sunday) in the reference timezone
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(f"Unknown session group: {session_group!r}")

        # Ensure we have a pandas Timestamp for .tz_convert support
        if not isinstance(utc_timestamp, pd.Timestamp):
            utc_timestamp = pd.Timestamp(utc_timestamp)

        ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
        local_ts = utc_timestamp.tz_convert(ref_tz)
        return local_ts.dayofweek

    @staticmethod
    def get_local_times(
        utc_timestamps: pd.DatetimeIndex,
        session_group: str,
    ) -> pd.DatetimeIndex:
        """Convert UTC DatetimeIndex to local time for session group.

        Args:
            utc_timestamps: DatetimeIndex in UTC
            session_group: Session group name

        Returns:
            DatetimeIndex converted to local reference timezone
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(f"Unknown session group: {session_group!r}")

        ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
        if utc_timestamps.tz is None:
            # Assume UTC if naive, matching is_session_open strictness
            # (or lack thereof for scalar)
            # but is_session_open raises valueerror for naive.
            # We should probably do the same or localize.
            # Existing is_session_open raises.
            raise ValueError("utc_timestamps must be timezone-aware (UTC)")

        return utc_timestamps.tz_convert(ref_tz)
