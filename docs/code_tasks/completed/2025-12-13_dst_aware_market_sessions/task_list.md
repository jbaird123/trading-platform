# DST-Aware Market Sessions Implementation Plan

## Overview

Move session features out of the cached global feature pipeline into a separate, DST-aware system that computes session flags on-the-fly based on instrument type. All timezone logic will be consolidated in a new `SessionService` class.

## Branch

Create a new branch: `feature/dst-aware-market-sessions`

---

### **Developer Mandates**

-   **No Bypassing Checks:** You must **never** bypass `mypy` or `ruff` checks. Using `--no-verify` or similar flags to circumvent pre-commit hooks is strictly forbidden. All code must pass all static analysis and linting checks.
-   **No Deferrals:** You must **never** mark any task as "deferred" or flag it for "future work." If a task is in the plan, it must be implemented.
-   **Full Implementation:** All tasks must be **completely implemented** as described. Do not leave placeholders or incomplete logic.

In addition, every task you define must explicitly enforce the **fail-fast exception handling policy** documented in `docs/coding_standards/exception_handling_policy.md`. Any plan that allows silent failures, defensive exception swallowing, or retries that contradict that policy is automatically invalid. Make the policy a first-class acceptance criterion for each implementation item.

---

## Known Limitations (Documented, Not Solved)

These are accepted tradeoffs for this implementation:

- Asia session hour analysis drifts by 1 hour between US DST/standard time
- ~4-5 weeks/year of London/NY DST mismatch not accounted for
- Both acceptable for London/NY focused trading

---

## Task List

### Part 1: Schema Changes to InstrumentDefinition

#### 1. [ ] Write tests for `session_group` field in `InstrumentDefinition`

**File:** `tests/data/test_instrument.py`

**Description:** Add tests to verify the new `session_group` field on `InstrumentDefinition`.

**Test cases to add:**

```python
def test_forex_instrument_has_session_group():
    """Forex instruments should have session_group='forex' by default."""
    instrument = get_instrument_definition("EURUSD")
    assert instrument.session_group == "forex"

def test_all_forex_instruments_have_session_group():
    """All defined forex instruments should inherit session_group from defaults."""
    forex_symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"]
    for symbol in forex_symbols:
        instrument = get_instrument_definition(symbol)
        assert instrument.session_group == "forex", f"{symbol} missing session_group"

def test_session_group_is_required():
    """InstrumentDefinition should require session_group field."""
    with pytest.raises(ValidationError):
        InstrumentDefinition(
            asset_class="Forex",
            point_value=1.0,
            tick_size=0.00001,
            pip_location=0.0001,
            commission_model={"type": "spread"},
            sessions=[SessionDefinition(close_time=time(17, 0), close_timezone="America/New_York")],
            # session_group intentionally omitted
        )
```

**Acceptance criteria:**
- All tests fail before implementation (TDD)
- Tests cover default inheritance, all forex symbols, and required field validation
- No exception swallowing - tests verify exceptions are raised when expected

---

#### 2. [ ] Add `session_group` field to `InstrumentDefinition`

**File:** `src/trading_platform/data/instrument.py`

**Description:** Add the required `session_group` field to `InstrumentDefinition` and update defaults.

**Changes:**

1. Add field to `InstrumentDefinition` class:
```python
class InstrumentDefinition(BaseModel):
    """Defines the metadata for a financial instrument."""

    asset_class: str
    session_group: str  # Required: "forex", "crypto", "us_equity", etc.
    point_value: float
    tick_size: float
    pip_location: float | None = None
    commission_model: dict
    sessions: list[SessionDefinition]
    symbol: str | None = None
    base_ccy: str | None = None
    quote_ccy: str | None = None
```

2. Update `_ASSET_CLASS_DEFAULTS` to include `session_group`:
```python
_ASSET_CLASS_DEFAULTS: dict[str, dict[str, Any]] = {
    "Forex": {
        "asset_class": "Forex",
        "session_group": "forex",  # Add this line
        "point_value": 1.0,
        "pip_location": 0.0001,
        "commission_model": {"type": "spread"},
        "sessions": _FOREX_SESSION,
    }
}
```

**Acceptance criteria:**
- All tests from task 1 pass
- `mypy` passes with no errors
- `ruff` passes with no errors
- Field is required (no default value on the model itself)
- Default is provided via `_ASSET_CLASS_DEFAULTS` for Forex

---

### Part 2: Create Market Sessions Module

#### 3. [ ] Write tests for `SessionDefinition` dataclass and `SESSION_GROUPS` registry

**File:** `tests/data/test_market_sessions.py` (new file)

**Description:** Create comprehensive tests for the session definitions and registry structure.

**Test cases:**

```python
import pytest
from datetime import time
from trading_platform.data.market_sessions import (
    SessionDefinition,
    SESSION_GROUPS,
)

class TestSessionDefinition:
    def test_session_definition_is_frozen(self):
        """SessionDefinition should be immutable."""
        defn = SessionDefinition("test", time(9, 0), time(17, 0), "UTC")
        with pytest.raises(AttributeError):
            defn.name = "modified"

    def test_session_definition_fields(self):
        """SessionDefinition should have all required fields."""
        defn = SessionDefinition(
            name="london",
            open_time=time(8, 0),
            close_time=time(17, 0),
            timezone="Europe/London",
        )
        assert defn.name == "london"
        assert defn.open_time == time(8, 0)
        assert defn.close_time == time(17, 0)
        assert defn.timezone == "Europe/London"


class TestSessionGroups:
    def test_forex_session_group_exists(self):
        """SESSION_GROUPS should contain 'forex' key."""
        assert "forex" in SESSION_GROUPS

    def test_forex_has_required_sessions(self):
        """Forex session group should have asia, london, newyork sessions."""
        forex = SESSION_GROUPS["forex"]
        assert "asia" in forex["sessions"]
        assert "london" in forex["sessions"]
        assert "newyork" in forex["sessions"]

    def test_forex_has_reference_timezone(self):
        """Forex session group should have reference_timezone."""
        forex = SESSION_GROUPS["forex"]
        assert forex["reference_timezone"] == "America/New_York"

    def test_forex_has_overlaps(self):
        """Forex session group should define overlaps."""
        forex = SESSION_GROUPS["forex"]
        assert ("asia", "london") in forex["overlaps"]
        assert ("london", "newyork") in forex["overlaps"]

    def test_forex_asia_session_definition(self):
        """Forex asia session should be Tokyo hours."""
        asia = SESSION_GROUPS["forex"]["sessions"]["asia"]
        assert asia.open_time == time(9, 0)
        assert asia.close_time == time(18, 0)
        assert asia.timezone == "Asia/Tokyo"

    def test_forex_london_session_definition(self):
        """Forex london session should be London hours."""
        london = SESSION_GROUPS["forex"]["sessions"]["london"]
        assert london.open_time == time(8, 0)
        assert london.close_time == time(17, 0)
        assert london.timezone == "Europe/London"

    def test_forex_newyork_session_definition(self):
        """Forex newyork session should be NY hours."""
        ny = SESSION_GROUPS["forex"]["sessions"]["newyork"]
        assert ny.open_time == time(8, 0)
        assert ny.close_time == time(17, 0)
        assert ny.timezone == "America/New_York"

    def test_crypto_session_group_exists(self):
        """SESSION_GROUPS should contain 'crypto' key."""
        assert "crypto" in SESSION_GROUPS

    def test_crypto_has_always_session(self):
        """Crypto session group should have 24/7 'always' session."""
        crypto = SESSION_GROUPS["crypto"]
        assert "always" in crypto["sessions"]
        always = crypto["sessions"]["always"]
        assert always.open_time == time(0, 0)
        assert always.close_time == time(0, 0)
        assert always.timezone == "UTC"

    def test_crypto_reference_timezone_is_utc(self):
        """Crypto should use UTC as reference timezone."""
        crypto = SESSION_GROUPS["crypto"]
        assert crypto["reference_timezone"] == "UTC"

    def test_all_session_timezones_are_valid(self):
        """All session timezones should be valid IANA timezone names."""
        import pytz
        for group_name, group in SESSION_GROUPS.items():
            # Check reference timezone
            try:
                pytz.timezone(group["reference_timezone"])
            except pytz.UnknownTimeZoneError:
                pytest.fail(f"Invalid reference_timezone in {group_name}: {group['reference_timezone']}")

            # Check session timezones
            for session_name, session in group["sessions"].items():
                try:
                    pytz.timezone(session.timezone)
                except pytz.UnknownTimeZoneError:
                    pytest.fail(f"Invalid timezone in {group_name}.{session_name}: {session.timezone}")
```

**Acceptance criteria:**
- All tests fail before implementation (TDD)
- Tests cover all session groups and their structure
- Tests validate timezone strings are valid IANA names
- No exception swallowing in tests

---

#### 4. [ ] Write tests for `SessionService.is_session_open()`

**File:** `tests/data/test_market_sessions.py` (append to file from task 3)

**Description:** Add tests for the core session-open detection logic, including DST handling.

**Test cases:**

```python
import pandas as pd
from trading_platform.data.market_sessions import SessionService, SESSION_GROUPS

class TestSessionServiceIsSessionOpen:
    def test_london_open_during_winter(self):
        """London session should be open 8 AM - 5 PM GMT in winter."""
        # Jan 15, 2024 - UK is on GMT (UTC+0)
        # 10:00 UTC = 10:00 GMT = within London session
        utc_index = pd.DatetimeIndex(["2024-01-15 10:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] == True

    def test_london_closed_before_open_winter(self):
        """London session should be closed before 8 AM GMT in winter."""
        # Jan 15, 2024 - 07:00 UTC = 07:00 GMT = before London open
        utc_index = pd.DatetimeIndex(["2024-01-15 07:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] == False

    def test_london_open_during_summer_dst(self):
        """London session should be open 8 AM - 5 PM BST in summer."""
        # Jul 15, 2024 - UK is on BST (UTC+1)
        # 10:00 UTC = 11:00 BST = within London session
        utc_index = pd.DatetimeIndex(["2024-07-15 10:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] == True

    def test_london_closed_before_open_summer(self):
        """London session should be closed before 8 AM BST in summer."""
        # Jul 15, 2024 - UK is on BST (UTC+1)
        # 06:00 UTC = 07:00 BST = before London open
        utc_index = pd.DatetimeIndex(["2024-07-15 06:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] == False

    def test_newyork_open_during_winter(self):
        """NY session should be open 8 AM - 5 PM EST in winter."""
        # Jan 15, 2024 - US is on EST (UTC-5)
        # 14:00 UTC = 9:00 AM EST = within NY session
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")
        ny_def = SESSION_GROUPS["forex"]["sessions"]["newyork"]

        result = SessionService.is_session_open(utc_index, ny_def)

        assert result.iloc[0] == True

    def test_newyork_open_during_summer_dst(self):
        """NY session should be open 8 AM - 5 PM EDT in summer."""
        # Jul 15, 2024 - US is on EDT (UTC-4)
        # 13:00 UTC = 9:00 AM EDT = within NY session
        utc_index = pd.DatetimeIndex(["2024-07-15 13:00:00"], tz="UTC")
        ny_def = SESSION_GROUPS["forex"]["sessions"]["newyork"]

        result = SessionService.is_session_open(utc_index, ny_def)

        assert result.iloc[0] == True

    def test_asia_tokyo_no_dst(self):
        """Tokyo session should not change between summer and winter (no DST)."""
        # Tokyo is always JST (UTC+9)
        # 01:00 UTC = 10:00 JST = within Asia session (9 AM - 6 PM)
        asia_def = SESSION_GROUPS["forex"]["sessions"]["asia"]

        winter_index = pd.DatetimeIndex(["2024-01-15 01:00:00"], tz="UTC")
        summer_index = pd.DatetimeIndex(["2024-07-15 01:00:00"], tz="UTC")

        winter_result = SessionService.is_session_open(winter_index, asia_def)
        summer_result = SessionService.is_session_open(summer_index, asia_def)

        # Both should be True - Tokyo doesn't observe DST
        assert winter_result.iloc[0] == True
        assert summer_result.iloc[0] == True

    def test_crypto_always_open(self):
        """Crypto 'always' session should be open 24/7."""
        crypto_def = SESSION_GROUPS["crypto"]["sessions"]["always"]

        # Test various times
        utc_index = pd.DatetimeIndex([
            "2024-01-15 00:00:00",
            "2024-01-15 12:00:00",
            "2024-07-15 06:00:00",
            "2024-07-15 23:59:00",
        ], tz="UTC")

        result = SessionService.is_session_open(utc_index, crypto_def)

        assert result.all() == True

    def test_returns_series_with_correct_index(self):
        """is_session_open should return Series with same index as input."""
        utc_index = pd.DatetimeIndex([
            "2024-01-15 10:00:00",
            "2024-01-15 11:00:00",
            "2024-01-15 12:00:00",
        ], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert isinstance(result, pd.Series)
        assert result.index.equals(utc_index)
```

**Acceptance criteria:**
- All tests fail before implementation (TDD)
- Tests cover winter/summer DST transitions for London and NY
- Tests verify Tokyo (no DST) behaves consistently
- Tests verify crypto 24/7 session
- Tests verify return type and index alignment

---

#### 5. [ ] Write tests for `SessionService.get_session_flags()`

**File:** `tests/data/test_market_sessions.py` (append)

**Description:** Add tests for the main public method that returns all session flags for a session group.

**Test cases:**

```python
class TestSessionServiceGetSessionFlags:
    def test_forex_returns_all_session_columns(self):
        """get_session_flags for forex should return all expected columns."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        expected_columns = [
            "forex_session_asia",
            "forex_session_london",
            "forex_session_newyork",
            "forex_session_overlap_asia_london",
            "forex_session_overlap_london_ny",
        ]
        assert list(result.columns) == expected_columns

    def test_forex_overlap_london_ny(self):
        """Overlap should be 1.0 only when both sessions are open."""
        # Jan 15, 2024 - 14:00 UTC
        # London: 14:00 GMT = open (8-17)
        # NY: 09:00 EST = open (8-17)
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        assert result["forex_session_london"].iloc[0] == 1.0
        assert result["forex_session_newyork"].iloc[0] == 1.0
        assert result["forex_session_overlap_london_ny"].iloc[0] == 1.0

    def test_forex_no_overlap_when_one_closed(self):
        """Overlap should be 0.0 when only one session is open."""
        # Jan 15, 2024 - 20:00 UTC
        # London: 20:00 GMT = closed (8-17)
        # NY: 15:00 EST = open (8-17)
        utc_index = pd.DatetimeIndex(["2024-01-15 20:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        assert result["forex_session_london"].iloc[0] == 0.0
        assert result["forex_session_newyork"].iloc[0] == 1.0
        assert result["forex_session_overlap_london_ny"].iloc[0] == 0.0

    def test_forex_overlap_asia_london(self):
        """Asia/London overlap during handoff period."""
        # Jan 15, 2024 - 08:30 UTC
        # Asia (Tokyo): 17:30 JST = open (9-18)
        # London: 08:30 GMT = open (8-17)
        utc_index = pd.DatetimeIndex(["2024-01-15 08:30:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        assert result["forex_session_asia"].iloc[0] == 1.0
        assert result["forex_session_london"].iloc[0] == 1.0
        assert result["forex_session_overlap_asia_london"].iloc[0] == 1.0

    def test_crypto_returns_always_column(self):
        """get_session_flags for crypto should return always session."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "crypto")

        assert "crypto_session_always" in result.columns
        assert result["crypto_session_always"].iloc[0] == 1.0

    def test_returns_float_dtype(self):
        """All session flag columns should be float64 dtype."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        for col in result.columns:
            assert result[col].dtype == "float64"

    def test_invalid_session_group_raises(self):
        """Invalid session group should raise ValueError."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        with pytest.raises(ValueError, match="Unknown session group"):
            SessionService.get_session_flags(utc_index, "invalid_group")

    def test_handles_large_index(self):
        """Should efficiently handle large DatetimeIndex."""
        # 1 year of hourly data
        utc_index = pd.date_range("2024-01-01", "2024-12-31", freq="h", tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        assert len(result) == len(utc_index)
        assert result.index.equals(utc_index)
```

**Acceptance criteria:**
- All tests fail before implementation (TDD)
- Tests verify correct column names with session group prefix
- Tests verify overlap logic (AND of two sessions)
- Tests verify float64 dtype
- Tests verify error handling for invalid session group
- Tests verify performance with large index

---

#### 6. [ ] Write tests for `SessionService.get_local_hour()` and `get_local_day_of_week()`

**File:** `tests/data/test_market_sessions.py` (append)

**Description:** Add tests for local time conversion methods.

**Test cases:**

```python
class TestSessionServiceLocalTime:
    def test_get_local_hour_forex_winter(self):
        """Forex local hour should be NY time (EST in winter)."""
        # Jan 15, 2024 - 14:00 UTC = 09:00 EST
        ts = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")

        result = SessionService.get_local_hour(ts, "forex")

        assert result == 9

    def test_get_local_hour_forex_summer(self):
        """Forex local hour should be NY time (EDT in summer)."""
        # Jul 15, 2024 - 14:00 UTC = 10:00 EDT
        ts = pd.Timestamp("2024-07-15 14:00:00", tz="UTC")

        result = SessionService.get_local_hour(ts, "forex")

        assert result == 10

    def test_get_local_hour_crypto_is_utc(self):
        """Crypto local hour should be UTC (no conversion)."""
        ts = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")

        result = SessionService.get_local_hour(ts, "crypto")

        assert result == 14

    def test_get_local_day_of_week_forex(self):
        """Forex local day should be NY day of week."""
        # Jan 15, 2024 is Monday
        # 03:00 UTC on Jan 15 = 22:00 EST on Jan 14 (Sunday)
        ts = pd.Timestamp("2024-01-15 03:00:00", tz="UTC")

        result = SessionService.get_local_day_of_week(ts, "forex")

        # In NY it's still Sunday (day 6)
        assert result == 6

    def test_get_local_day_of_week_utc_is_monday(self):
        """Verify the same timestamp is Monday in UTC."""
        ts = pd.Timestamp("2024-01-15 03:00:00", tz="UTC")

        # In UTC it's Monday (day 0)
        assert ts.dayofweek == 0

        # But in NY it's Sunday
        result = SessionService.get_local_day_of_week(ts, "forex")
        assert result == 6

    def test_get_local_hour_invalid_session_group_raises(self):
        """Invalid session group should raise ValueError."""
        ts = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")

        with pytest.raises(ValueError, match="Unknown session group"):
            SessionService.get_local_hour(ts, "invalid_group")

    def test_get_local_day_of_week_invalid_session_group_raises(self):
        """Invalid session group should raise ValueError."""
        ts = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")

        with pytest.raises(ValueError, match="Unknown session group"):
            SessionService.get_local_day_of_week(ts, "invalid_group")
```

**Acceptance criteria:**
- All tests fail before implementation (TDD)
- Tests verify DST-aware hour conversion for forex
- Tests verify day-of-week boundary crossing (UTC Monday = NY Sunday)
- Tests verify crypto uses UTC
- Tests verify error handling

---

#### 7. [ ] Implement `SessionDefinition` dataclass and `SESSION_GROUPS` registry

**File:** `src/trading_platform/data/market_sessions.py` (new file)

**Description:** Create the new market sessions module with session definitions.

**Implementation:**

```python
"""Market session definitions and DST-aware session service.

This module provides the single source of truth for trading session definitions
and all timezone-related logic. All other code should use SessionService methods
rather than doing timezone conversions directly.

Session groups define:
- reference_timezone: Used for local hour/day analysis (e.g., "America/New_York" for forex)
- sessions: Dict of session name -> SessionDefinition with local open/close times
- overlaps: List of session pairs to compute overlap flags for
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SessionDefinition:
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
        "sessions": {
            "asia": SessionDefinition(
                name="asia",
                open_time=time(9, 0),
                close_time=time(18, 0),
                timezone="Asia/Tokyo",
            ),
            "london": SessionDefinition(
                name="london",
                open_time=time(8, 0),
                close_time=time(17, 0),
                timezone="Europe/London",
            ),
            "newyork": SessionDefinition(
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
            "always": SessionDefinition(
                name="always",
                open_time=time(0, 0),
                close_time=time(0, 0),  # 0-0 means 24 hours
                timezone="UTC",
            ),
        },
        "overlaps": [],
    },
}
```

**Acceptance criteria:**
- Tests from task 3 pass
- `mypy` passes with no errors
- `ruff` passes with no errors
- `SessionDefinition` is frozen (immutable)
- All timezones are valid IANA names

---

#### 8. [ ] Implement `SessionService` class

**File:** `src/trading_platform/data/market_sessions.py` (append to file from task 7)

**Description:** Implement the SessionService class with all public methods.

**Implementation:**

```python
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
        session_def: SessionDefinition,
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
        local_hour = local_times.hour
        local_minute = local_times.minute
        local_time_decimal = local_hour + local_minute / 60.0

        open_decimal = session_def.open_time.hour + session_def.open_time.minute / 60.0
        close_decimal = session_def.close_time.hour + session_def.close_time.minute / 60.0

        # Standard session: open < close (e.g., 8 AM to 5 PM)
        is_open = (local_time_decimal >= open_decimal) & (local_time_decimal < close_decimal)

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
            ValueError: If session_group is not defined
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(
                f"Unknown session group: {session_group!r}. "
                f"Valid groups: {list(SESSION_GROUPS.keys())}"
            )

        ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
        local_time = utc_timestamp.tz_convert(ref_tz)
        return local_time.hour

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
            Day of week (Monday=0, Sunday=6) in the reference timezone

        Raises:
            ValueError: If session_group is not defined
        """
        if session_group not in SESSION_GROUPS:
            raise ValueError(
                f"Unknown session group: {session_group!r}. "
                f"Valid groups: {list(SESSION_GROUPS.keys())}"
            )

        ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
        local_time = utc_timestamp.tz_convert(ref_tz)
        return local_time.dayofweek
```

**Acceptance criteria:**
- All tests from tasks 4, 5, 6 pass
- `mypy` passes with no errors
- `ruff` passes with no errors
- All methods raise `ValueError` for invalid inputs (fail-fast)
- No silent fallbacks or exception swallowing

---

### Part 3: Remove Sessions from Global Feature Cache

#### 9. [ ] Write test to verify calendar features are not in global.yaml

**File:** `tests/core/test_global_features.py` (add to existing file)

**Description:** Add a test that verifies calendar session features are not defined in global.yaml.

**Test case:**

```python
def test_calendar_sessions_not_in_global_yaml():
    """Calendar session features should not be in global.yaml (computed at runtime)."""
    import yaml
    from trading_platform.core.paths import PROJECT_ROOT

    config_path = PROJECT_ROOT / "config" / "features" / "global.yaml"
    config = yaml.safe_load(config_path.read_text())

    feature_names = [f["name"] for f in config.get("features", [])]

    # These should NOT exist - sessions are computed at runtime
    calendar_features = [f for f in feature_names if "calendar" in f.lower()]

    assert calendar_features == [], (
        f"Calendar features should not be in global.yaml: {calendar_features}. "
        "Session features are computed at runtime by SessionService."
    )
```

**Acceptance criteria:**
- Test fails before removing calendar features from global.yaml
- Test passes after removal

---

#### 10. [ ] Remove calendar session features from `global.yaml`

**File:** `config/features/global.yaml`

**Description:** Remove all `*_calendar` feature definitions from global.yaml.

**Changes:** Delete the following entries:

- `5min_calendar` (around line 105-108)
- `15min_calendar` (around line 217-220)
- `1h_calendar` (around line 326-329)
- `4h_calendar` (around line 445-448)
- `1d_calendar` (around line 554-557)
- `1w_calendar` (around line 654-657)

Each entry looks like:
```yaml
  - name: "5min_calendar"
    type: "CalendarSessions"
    params: {}
    timeframe: "5min"
```

**Acceptance criteria:**
- Test from task 9 passes
- No `CalendarSessions` type features remain in global.yaml
- `ruff` and `mypy` still pass (YAML changes don't affect Python checks)

---

### Part 4: Integrate Session Features at Cache Load Time

#### 11. [ ] Write tests for session feature injection in `load_cached_global_features`

**File:** `tests/core/test_global_features_cache.py` (add to existing file)

**Description:** Add tests verifying that session features are injected when loading cached features.

**Test cases:**

```python
def test_load_cached_global_features_includes_session_flags(
    tmp_path: Path,
    sample_global_config: Path,
):
    """Loading cached features should include session flags from SessionService."""
    # Setup: Create a minimal cache
    # ... (use existing test fixtures)

    result, mapping = load_cached_global_features(
        symbol="EURUSD",
        cache_root=tmp_path,
        config_path=sample_global_config,
        timeframe="1H",
        feature_names=["1h_ema_50"],
        session_group="forex",  # New parameter
    )

    # Session columns should be present
    assert "forex_session_asia" in result.columns
    assert "forex_session_london" in result.columns
    assert "forex_session_newyork" in result.columns
    assert "forex_session_overlap_asia_london" in result.columns
    assert "forex_session_overlap_london_ny" in result.columns


def test_load_cached_global_features_session_group_required(
    tmp_path: Path,
    sample_global_config: Path,
):
    """session_group parameter should be required."""
    # This test verifies the signature change
    with pytest.raises(TypeError, match="session_group"):
        load_cached_global_features(
            symbol="EURUSD",
            cache_root=tmp_path,
            config_path=sample_global_config,
            timeframe="1H",
            feature_names=["1h_ema_50"],
            # session_group intentionally omitted
        )


def test_load_cached_global_features_invalid_session_group_raises(
    tmp_path: Path,
    sample_global_config: Path,
):
    """Invalid session_group should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown session group"):
        load_cached_global_features(
            symbol="EURUSD",
            cache_root=tmp_path,
            config_path=sample_global_config,
            timeframe="1H",
            feature_names=["1h_ema_50"],
            session_group="invalid_group",
        )
```

**Acceptance criteria:**
- Tests fail before implementation
- Tests verify session columns are present in output
- Tests verify session_group is required
- Tests verify invalid session_group raises ValueError

---

#### 12. [ ] Update `load_cached_global_features` to inject session features

**File:** `src/trading_platform/core/global_features_cache.py`

**Description:** Modify `load_cached_global_features` to add session features at load time.

**Changes:**

1. Add `session_group` parameter to function signature:
```python
def load_cached_global_features(
    *,
    symbol: str,
    cache_root: Path | None = None,
    config_path: Path,
    timeframe: str,
    feature_names: Sequence[str],
    session_group: str,  # New required parameter
) -> tuple[pd.DataFrame, dict[str, list[str]]] | None:
```

2. Add import at top of file:
```python
from trading_platform.data.market_sessions import SessionService
```

3. Before the `return` statement (around line 620), add session feature injection:
```python
    # Inject session features (computed at runtime, not cached)
    session_flags = SessionService.get_session_flags(df.index, session_group)
    df = pd.concat([df, session_flags], axis=1)

    return df, mapping
```

**Acceptance criteria:**
- Tests from task 11 pass
- `mypy` passes with no errors
- `ruff` passes with no errors
- Session features are computed fresh on each load (not cached)
- ValueError raised for invalid session_group (fail-fast)

---

#### 13. [ ] Update all callers of `load_cached_global_features` to pass `session_group`

**File:** Multiple files (search for all usages)

**Description:** Find and update all call sites to pass the new required `session_group` parameter.

**Steps:**

1. Search for all usages:
```bash
rg "load_cached_global_features" --type py
```

2. For each call site, determine the appropriate session_group:
   - If the caller has access to `instrument`, use `instrument.session_group`
   - If the caller knows the symbol, get the instrument first
   - For tests, use appropriate test values

**Expected files to update (verify with search):**
- `src/trading_platform/backtester/engine.py`
- `src/trading_platform/backtester/warmup.py`
- Various test files in `tests/`

**For each file, the pattern is:**
```python
# Before
result = load_cached_global_features(
    symbol=symbol,
    config_path=config_path,
    timeframe=timeframe,
    feature_names=feature_names,
)

# After
result = load_cached_global_features(
    symbol=symbol,
    config_path=config_path,
    timeframe=timeframe,
    feature_names=feature_names,
    session_group=instrument.session_group,  # or appropriate value
)
```

**Acceptance criteria:**
- All existing tests pass
- No `TypeError` for missing `session_group` argument
- `mypy` passes with no errors
- Each call site uses the correct session_group for the instrument

---

### Part 5: Update Hour/Day References to Use SessionService

#### 14. [ ] Write tests for local hour/day in RMM gating

**File:** `tests/regime_market_manager/test_gating.py` (add to existing file)

**Description:** Add tests verifying that gating uses local time, not UTC.

**Test cases:**

```python
def test_gating_uses_local_hour_not_utc():
    """Gating should filter by local hour (NY time for forex), not UTC."""
    # Jan 15, 2024 - 14:00 UTC = 09:00 EST
    # If allowed_hours=[9], this should PASS with local time
    # but would FAIL if using UTC hour (14)

    context = {
        "entry_time": "2024-01-15T14:00:00Z",
        "symbol": "EURUSD",
        # ... other required fields
    }

    gating_config = RMMGatingContext(
        timeframe="1H",
        archetype="trend_following",
        allowed_hours=[9],  # 9 AM local (NY) time
    )

    # Should pass because 14:00 UTC = 09:00 EST
    result = gating.check_entry(context, gating_config, session_group="forex")

    assert result.allowed == True


def test_gating_uses_local_day_not_utc():
    """Gating should filter by local day of week, not UTC."""
    # 2024-01-15 03:00 UTC = 2024-01-14 22:00 EST (Sunday)
    # If allowed_days=[6] (Sunday), this should PASS with local time
    # but would FAIL if using UTC day (Monday=0)

    context = {
        "entry_time": "2024-01-15T03:00:00Z",
        "symbol": "EURUSD",
    }

    gating_config = RMMGatingContext(
        timeframe="1H",
        archetype="trend_following",
        allowed_days=[6],  # Sunday only
    )

    # Should pass because in NY it's still Sunday
    result = gating.check_entry(context, gating_config, session_group="forex")

    assert result.allowed == True
```

**Acceptance criteria:**
- Tests fail before implementation (currently uses UTC)
- Tests pass after updating to use SessionService

---

#### 15. [ ] Update `regime_market_manager/gating.py` to use `SessionService`

**File:** `src/trading_platform/regime_market_manager/gating.py`

**Description:** Replace UTC hour/day extraction with SessionService methods.

**Changes:**

1. Add import:
```python
from trading_platform.data.market_sessions import SessionService
```

2. Update the `_build_feature_row` method (around line 197-202):

**Before:**
```python
ts = pd.Timestamp(entry_time)
if ts.tzinfo is None:
    ts = ts.tz_localize("UTC")
flat["entry_time"] = ts
flat["hour_of_day"] = ts.tz_convert("UTC").hour
flat["day_of_week"] = ts.tz_convert("UTC").dayofweek
```

**After:**
```python
ts = pd.Timestamp(entry_time)
if ts.tzinfo is None:
    ts = ts.tz_localize("UTC")
flat["entry_time"] = ts
flat["local_hour"] = SessionService.get_local_hour(ts, session_group)
flat["local_day_of_week"] = SessionService.get_local_day_of_week(ts, session_group)
```

3. Update `_check_time_filters` method to use new column names:

**Before:**
```python
hour = row.iloc[0].get("hour_of_day")
...
dow = row.iloc[0].get("day_of_week")
```

**After:**
```python
hour = row.iloc[0].get("local_hour")
...
dow = row.iloc[0].get("local_day_of_week")
```

4. Add `session_group` parameter to relevant methods in the call chain.

**Acceptance criteria:**
- Tests from task 14 pass
- Existing gating tests still pass
- `mypy` passes with no errors
- Feature names changed from `hour_of_day` to `local_hour`
- Feature names changed from `day_of_week` to `local_day_of_week`

---

#### 16. [ ] Update `regime_market_manager/engine.py` to use `SessionService`

**File:** `src/trading_platform/regime_market_manager/engine.py`

**Description:** Update hour predicates to use local time.

**Changes to `_evaluate_predicate` function (around lines 52-68):**

This requires passing `session_group` through the predicate evaluation. The predicates `hour_is_in` and `hour_is_not_in` need to convert timestamps to local time before extracting hour.

**Before:**
```python
if cond == "hour_is_in":
    values = set(pred.get("values", []))
    dt_index = pd.DatetimeIndex(df.index)
    return pd.Series(dt_index.hour.isin(values), index=df.index)
if cond == "hour_is_not_in":
    values = set(pred.get("values", []))
    dt_index = pd.DatetimeIndex(df.index)
    return pd.Series(~dt_index.hour.isin(values), index=df.index)
```

**After:**
```python
if cond == "hour_is_in":
    values = set(pred.get("values", []))
    dt_index = pd.DatetimeIndex(df.index)
    ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
    local_hours = dt_index.tz_convert(ref_tz).hour
    return pd.Series(local_hours.isin(values), index=df.index)
if cond == "hour_is_not_in":
    values = set(pred.get("values", []))
    dt_index = pd.DatetimeIndex(df.index)
    ref_tz = SESSION_GROUPS[session_group]["reference_timezone"]
    local_hours = dt_index.tz_convert(ref_tz).hour
    return pd.Series(~local_hours.isin(values), index=df.index)
```

Also update `day_of_week_is_in` and `day_of_week_is_not_in` similarly.

**Acceptance criteria:**
- Existing RMM engine tests pass (may need updates)
- `mypy` passes with no errors
- Hour/day predicates use local time based on session_group

---

#### 17. [ ] Update `reporting/analytics.py` to use `SessionService`

**File:** `src/trading_platform/reporting/analytics.py`

**Description:** Update hour/day analysis to use local time.

**Changes (around lines 183-191):**

1. Add import:
```python
from trading_platform.data.market_sessions import SessionService
```

2. Update the loop that extracts hour/day:

**Before:**
```python
for trade in trades:
    hour = trade.entry_time.hour
    day_of_week = trade.entry_time.weekday()
```

**After:**
```python
for trade in trades:
    ts = pd.Timestamp(trade.entry_time)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    hour = SessionService.get_local_hour(ts, session_group)
    day_of_week = SessionService.get_local_day_of_week(ts, session_group)
```

3. Add `session_group` parameter to the function containing this code.

**Acceptance criteria:**
- Analytics tests pass
- Brief hour/day breakdowns now show local time
- `mypy` passes with no errors

---

#### 18. [ ] Update ML model feature extraction to use `SessionService`

**Files:**
- `src/trading_platform/ai/models/profitability.py`
- `src/trading_platform/ai/models/profitability_classifier.py`
- `src/trading_platform/ai/models/performance_diagnostic.py`

**Description:** Update all ML models to use local hour instead of UTC hour.

**Changes for each file:**

1. Add import:
```python
from trading_platform.data.market_sessions import SessionService
```

2. Find the line that extracts `hour_of_day` and update:

**Before (example from profitability.py:383):**
```python
df["hour_of_day"] = pd.to_datetime(df["entry_time"]).dt.hour
```

**After:**
```python
# Convert to local hour based on session group
entry_times = pd.to_datetime(df["entry_time"])
if entry_times.dt.tz is None:
    entry_times = entry_times.dt.tz_localize("UTC")
df["local_hour"] = entry_times.apply(
    lambda ts: SessionService.get_local_hour(ts, session_group)
)
```

3. Add `session_group` parameter to the training/prediction methods.

4. Update any references from `hour_of_day` to `local_hour`.

**Acceptance criteria:**
- ML model tests pass
- Feature name is `local_hour` not `hour_of_day`
- Models use DST-aware local time
- `mypy` passes with no errors

---

### Part 6: Deprecate Old Implementation

#### 19. [ ] Mark `compute_calendar_sessions` as deprecated

**File:** `src/trading_platform/strategy/indicator_implementations.py`

**Description:** Add deprecation warning to the old implementation.

**Changes (around line 850):**

```python
import warnings

def compute_calendar_sessions(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Encode trading sessions (Asia/London/New York) based on entry_time.

    .. deprecated::
        This function uses fixed UTC hours and does not handle DST correctly.
        Use SessionService.get_session_flags() instead for DST-aware session detection.
    """
    warnings.warn(
        "compute_calendar_sessions is deprecated and does not handle DST correctly. "
        "Use SessionService.get_session_flags() from trading_platform.data.market_sessions instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # ... rest of existing implementation unchanged
```

**Acceptance criteria:**
- DeprecationWarning is raised when function is called
- Existing functionality preserved for backward compatibility
- Docstring explains why it's deprecated and what to use instead

---

### Part 7: Documentation and Cleanup

#### 20. [ ] Add module docstring and usage examples to `market_sessions.py`

**File:** `src/trading_platform/data/market_sessions.py`

**Description:** Add comprehensive documentation at the top of the file.

**Add after the existing module docstring:**

```python
"""Market session definitions and DST-aware session service.

This module provides the single source of truth for trading session definitions
and all timezone-related logic. All other code should use SessionService methods
rather than doing timezone conversions directly.

Session Groups
--------------
Each instrument type belongs to a session group that defines:

- reference_timezone: The timezone used for local hour/day analysis
- sessions: Dict of session definitions with local open/close times
- overlaps: List of session pairs to compute overlap flags for

Currently supported groups:

- "forex": Uses America/New_York as reference; defines asia, london, newyork sessions
- "crypto": Uses UTC as reference; defines 24/7 "always" session

Usage Examples
--------------

Get session flags for a DataFrame index:

    >>> from trading_platform.data.market_sessions import SessionService
    >>> import pandas as pd
    >>> index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")
    >>> flags = SessionService.get_session_flags(index, "forex")
    >>> flags.columns.tolist()
    ['forex_session_asia', 'forex_session_london', 'forex_session_newyork',
     'forex_session_overlap_asia_london', 'forex_session_overlap_london_ny']

Get local hour for filtering:

    >>> ts = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")
    >>> SessionService.get_local_hour(ts, "forex")  # 14:00 UTC = 9:00 EST
    9

Known Limitations
-----------------
- Asia session analysis drifts by 1 hour between US DST/standard time
- ~4-5 weeks/year of London/NY DST mismatch not specifically handled
- Both acceptable for London/NY focused forex trading

Adding New Session Groups
-------------------------
To add support for a new asset class (e.g., US equities):

1. Add entry to SESSION_GROUPS dict with reference_timezone, sessions, and overlaps
2. Add session_group value to relevant instruments in instrument.py
3. SessionService methods will automatically support the new group

See Also
--------
- docs/coding_standards/exception_handling_policy.md for error handling requirements
- src/trading_platform/data/instrument.py for session_group field on instruments
"""
```

**Acceptance criteria:**
- Module docstring provides clear usage examples
- Known limitations are documented
- Instructions for adding new session groups are included

---

### Part 8: Update RMM Analysis Scripts

#### 21. [ ] Update `two_stage_threshold_analysis.py` session column references

**File:** `src/trading_platform/rmm_analysis/two_stage_threshold_analysis.py`

**Description:** Update hardcoded session column names to use new format.

**Changes (lines 96, 102, 126-130):**

**Before:**
```python
TwoStageRule(
    "tau60_session",
    0.70,
    0.60,
    "session_london or session_newyork",
),
TwoStageRule(
    "tau55_atr70_session",
    0.70,
    0.55,
    "(atr_percentile >= 70) and (session_london or session_newyork)",
),
# ...
"session_london": (
    df["context_at_entry_global_features_15min_calendar_session_london"] > 0.0
),
"session_newyork": (
    df["context_at_entry_global_features_15min_calendar_session_newyork"] > 0.0
),
```

**After:**
```python
TwoStageRule(
    "tau60_session",
    0.70,
    0.60,
    "session_london or session_newyork",
),
TwoStageRule(
    "tau55_atr70_session",
    0.70,
    0.55,
    "(atr_percentile >= 70) and (session_london or session_newyork)",
),
# ...
"session_london": (
    df["forex_session_london"] > 0.0
),
"session_newyork": (
    df["forex_session_newyork"] > 0.0
),
```

**Acceptance criteria:**
- Script runs without KeyError on session columns
- `mypy` passes with no errors
- `ruff` passes with no errors

---

#### 22. [ ] Update `portfolio_threshold_replay.py` session column references

**File:** `src/trading_platform/rmm_analysis/portfolio_threshold_replay.py`

**Description:** Update session column name construction to use new format.

**Changes (lines 197-198, 214-218, 230-235):**

**Before:**
```python
"session_london": [],
"session_newyork": [],
# ...
session_london_col = (
    f"context_at_entry_global_features_{prefix}_calendar_session_london"
)
session_newyork_col = (
    f"context_at_entry_global_features_{prefix}_calendar_session_newyork"
)
# ...
"session_london": _series_or_default(df, session_london_col, default_value=0.0)
> 0.0,
"session_newyork": _series_or_default(
    df, session_newyork_col, default_value=0.0
)
> 0.0,
```

**After:**
```python
"session_london": [],
"session_newyork": [],
# ...
session_london_col = "forex_session_london"
session_newyork_col = "forex_session_newyork"
# ...
"session_london": _series_or_default(df, session_london_col, default_value=0.0)
> 0.0,
"session_newyork": _series_or_default(
    df, session_newyork_col, default_value=0.0
)
> 0.0,
```

**Acceptance criteria:**
- Script runs without KeyError on session columns
- `mypy` passes with no errors
- `ruff` passes with no errors

---

#### 23. [ ] Update `evaluate_5min_model_variants.py` docstring references

**File:** `src/trading_platform/rmm_analysis/evaluate_5min_model_variants.py`

**Description:** Update docstring/comments that reference old session column format.

**Change (line 85):**

**Before:**
```python
"alignment_full, session_london, session_newyork."
```

**After:**
```python
"alignment_full, forex_session_london, forex_session_newyork."
```

**Acceptance criteria:**
- Documentation accurately reflects new column names
- `ruff` passes with no errors

---

#### 24. [ ] Update `grid_feature_pattern_search.py` to use `SessionService`

**File:** `src/trading_platform/rmm_analysis/grid_feature_pattern_search.py`

**Description:** Update hour/day extraction to use SessionService.

**Changes (lines 170-171):**

1. Add import:
```python
from trading_platform.data.market_sessions import SessionService
```

2. Update feature extraction:

**Before:**
```python
feature_frame["hour_of_day"] = df["entry_time"].dt.hour
feature_frame["day_of_week"] = df["entry_time"].dt.dayofweek
```

**After:**
```python
entry_times = pd.to_datetime(df["entry_time"])
if entry_times.dt.tz is None:
    entry_times = entry_times.dt.tz_localize("UTC")
feature_frame["local_hour"] = entry_times.apply(
    lambda ts: SessionService.get_local_hour(ts, session_group)
)
feature_frame["local_day_of_week"] = entry_times.apply(
    lambda ts: SessionService.get_local_day_of_week(ts, session_group)
)
```

3. Add `session_group` parameter to relevant functions.

**Acceptance criteria:**
- Script uses local time for hour/day features
- `mypy` passes with no errors
- `ruff` passes with no errors

---

#### 25. [ ] Update `evaluate_profitability_engineered_only.py` to use `SessionService`

**File:** `scripts/rmm_analysis/evaluate_profitability_engineered_only.py`

**Description:** Update hour/day extraction to use SessionService.

**Changes (lines 118-119):**

1. Add import:
```python
from trading_platform.data.market_sessions import SessionService
```

2. Update feature extraction:

**Before:**
```python
features["hour_of_day"] = df["entry_time"].dt.hour
features["day_of_week"] = df["entry_time"].dt.dayofweek
```

**After:**
```python
entry_times = pd.to_datetime(df["entry_time"])
if entry_times.dt.tz is None:
    entry_times = entry_times.dt.tz_localize("UTC")
features["local_hour"] = entry_times.apply(
    lambda ts: SessionService.get_local_hour(ts, session_group)
)
features["local_day_of_week"] = entry_times.apply(
    lambda ts: SessionService.get_local_day_of_week(ts, session_group)
)
```

**Acceptance criteria:**
- Script uses local time for hour/day features
- `mypy` passes with no errors
- `ruff` passes with no errors

---

### Part 9: Update Feature Groups

#### 26. [ ] Update `feature_groups.py` calendar patterns

**File:** `src/trading_platform/ai/models/feature_groups.py`

**Description:** Update the calendar group patterns to match new feature names.

**Changes (lines 39-42):**

**Before:**
```python
"calendar": [
    "calendar",
    "day_of_week",
],
```

**After:**
```python
"calendar": [
    "forex_session",
    "local_day_of_week",
],
```

**Acceptance criteria:**
- Feature group patterns match new feature names
- `mypy` passes with no errors
- `ruff` passes with no errors

---

### Part 10: Update Test Files for Mock InstrumentDefinition

#### 27. [ ] Update `tests/data/test_schema.py` mock InstrumentDefinitions

**File:** `tests/data/test_schema.py`

**Description:** Add `session_group` to all mock `InstrumentDefinition` instantiations.

**Lines to update:** 180, 245, 283, 322, 357, 400

**Pattern for each:**

**Before:**
```python
mock_instrument = InstrumentDefinition(
    asset_class="Forex",
    point_value=1.0,
    tick_size=0.00001,
    pip_location=0.0001,
    commission_model={"type": "spread"},
    sessions=[...],
)
```

**After:**
```python
mock_instrument = InstrumentDefinition(
    asset_class="Forex",
    session_group="forex",  # Add this line
    point_value=1.0,
    tick_size=0.00001,
    pip_location=0.0001,
    commission_model={"type": "spread"},
    sessions=[...],
)
```

**Acceptance criteria:**
- All tests in `test_schema.py` pass
- No ValidationError for missing `session_group`

---

#### 28. [ ] Update `tests/reporting/test_brief.py` mock InstrumentDefinition

**File:** `tests/reporting/test_brief.py`

**Description:** Add `session_group` to mock `InstrumentDefinition` at line 291.

**Also update expected timing bucket keys (lines 1016-1017, 1030-1033):**

**Before:**
```python
"timing_buckets.hour_of_day": "Performance metrics by hour of day",
"timing_buckets.day_of_week": "Performance metrics by day of week",
# ...
assert "hour_of_day" in timing
assert "day_of_week" in timing
```

**After:**
```python
"timing_buckets.local_hour": "Performance metrics by local hour",
"timing_buckets.local_day_of_week": "Performance metrics by local day of week",
# ...
assert "local_hour" in timing
assert "local_day_of_week" in timing
```

**Acceptance criteria:**
- All tests in `test_brief.py` pass
- Expected keys match new feature names

---

#### 29. [ ] Update `tests/core/test_parameter_sweep_consistency.py` mock InstrumentDefinition

**File:** `tests/core/test_parameter_sweep_consistency.py`

**Description:** Add `session_group` to mock `InstrumentDefinition` at line 57.

**Before:**
```python
lambda symbol: InstrumentDefinition(
    asset_class="Forex",
    point_value=1.0,
    # ...
)
```

**After:**
```python
lambda symbol: InstrumentDefinition(
    asset_class="Forex",
    session_group="forex",  # Add this line
    point_value=1.0,
    # ...
)
```

**Acceptance criteria:**
- All tests in `test_parameter_sweep_consistency.py` pass

---

#### 30. [ ] Update `tests/cli/test_cli_full_coverage.py` mock InstrumentDefinition

**File:** `tests/cli/test_cli_full_coverage.py`

**Description:** Add `session_group` to mock `InstrumentDefinition` at line 62.

**Acceptance criteria:**
- All tests in `test_cli_full_coverage.py` pass

---

### Part 11: Update Test Files for Renamed Features

#### 31. [ ] Update `tests/reporting/test_analytics.py` expected feature names

**File:** `tests/reporting/test_analytics.py`

**Description:** Update expected keys from `hour_of_day`/`day_of_week` to `local_hour`/`local_day_of_week`.

**Lines to update:** 282-283, 286, 301, 520-521, 534-535

**Pattern:**

**Before:**
```python
assert "hour_of_day" in result
assert "day_of_week" in result
```

**After:**
```python
assert "local_hour" in result
assert "local_day_of_week" in result
```

**Acceptance criteria:**
- All tests in `test_analytics.py` pass
- Expected keys match new feature names

---

#### 32. [ ] Update `tests/ai/models/test_profitability.py` expected feature names

**File:** `tests/ai/models/test_profitability.py`

**Description:** Update expected feature names at lines 102-103.

**Before:**
```python
"hour_of_day",
"day_of_week",
```

**After:**
```python
"local_hour",
"local_day_of_week",
```

**Acceptance criteria:**
- All tests in `test_profitability.py` pass

---

#### 33. [ ] Update `tests/regime_market_manager/test_gating.py` expected feature names

**File:** `tests/regime_market_manager/test_gating.py`

**Description:** Update expected feature names at lines 124, 131-132, 145.

**Changes:**
- `"hour_of_day"` → `"local_hour"`
- `"day_of_week"` → `"local_day_of_week"`
- Update any `15min_day_of_week_dow_*` references if present

**Acceptance criteria:**
- All tests in `test_gating.py` pass

---

#### 34. [ ] Update `tests/regime_market_manager/test_time_based_regimes.py` for local time

**File:** `tests/regime_market_manager/test_time_based_regimes.py`

**Description:** Update tests to account for local time behavior instead of UTC.

The test at line 69 (`test_day_of_week_is_in_predicate`) may need updates to verify local day of week behavior. Review and update assertions to reflect that predicates now use local time.

**Acceptance criteria:**
- All tests in `test_time_based_regimes.py` pass
- Tests verify local time behavior correctly

---

#### 35. [ ] Update `tests/strategy/test_features.py` expected session column names

**File:** `tests/strategy/test_features.py`

**Description:** Update expected column names at lines 886-888.

**Before:**
```python
"session_features_session_asia",
"session_features_session_london",
"session_features_session_newyork",
```

**After (if test still uses CalendarSessions):**
Either update to new names or convert test to use `SessionService` directly. If the test is specifically for `compute_calendar_sessions`, it may need to be updated to test the deprecated function with a `pytest.warns(DeprecationWarning)` context.

**Acceptance criteria:**
- All tests in `test_features.py` pass
- Deprecation warning is properly tested if applicable

---

### Part 12: Final Validation

#### 36. [ ] Run full test suite and verify no regressions

**Description:** Execute the complete test suite to verify all changes work together.

**Steps:**

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/trading_platform --cov-report=term-missing

# Run mypy
poetry run mypy src/trading_platform

# Run ruff
poetry run ruff check src/trading_platform
```

**Acceptance criteria:**
- All tests pass
- No decrease in test coverage for modified files
- `mypy` reports no errors
- `ruff` reports no errors

---

#### 37. [ ] Rebuild feature cache

**Description:** Rebuild the global feature cache since `global.yaml` changed.

**Steps:**

```bash
./scripts/rebuild_live_feature_cache.sh
```

**Acceptance criteria:**
- Script completes successfully
- New cache does not contain calendar session columns
- Cache can be loaded successfully with session_group parameter

---

## Summary

**Total Tasks: 37**

### Parts Overview:
- **Part 1** (Tasks 1-2): Schema changes to `InstrumentDefinition`
- **Part 2** (Tasks 3-8): Create `market_sessions.py` module
- **Part 3** (Tasks 9-10): Remove sessions from global feature cache
- **Part 4** (Tasks 11-13): Integrate session features at cache load time
- **Part 5** (Tasks 14-18): Update hour/day references to use `SessionService`
- **Part 6** (Task 19): Deprecate old `compute_calendar_sessions`
- **Part 7** (Task 20): Documentation
- **Part 8** (Tasks 21-25): Update RMM analysis scripts
- **Part 9** (Task 26): Update feature groups
- **Part 10** (Tasks 27-30): Update test files for mock `InstrumentDefinition`
- **Part 11** (Tasks 31-35): Update test files for renamed features
- **Part 12** (Tasks 36-37): Final validation and cache rebuild

### This implementation:

1. Adds `session_group` field to instruments (forex defaults to "forex")
2. Creates `SessionService` as single source of truth for timezone logic
3. Removes cached session features (computed at runtime instead)
4. Updates all hour/day references to use DST-aware local time
5. Renames features from `hour_of_day`/`day_of_week` to `local_hour`/`local_day_of_week`
6. Updates session column names from `{tf}_calendar_session_*` to `forex_session_*`
7. Deprecates the old `compute_calendar_sessions` function
8. Updates all RMM analysis scripts, ML models, and tests

### Files Changed Summary:

| Category | Count | Key Files |
|----------|-------|-----------|
| Core Implementation | 7 | `instrument.py`, `market_sessions.py` (new), `global_features_cache.py`, `indicator_implementations.py`, `indicators_registry.py`, `feature_groups.py`, `global.yaml` |
| RMM | 3 | `gating.py`, `engine.py`, `models.py` |
| Reporting | 1 | `analytics.py` |
| ML Models | 3 | `profitability.py`, `profitability_classifier.py`, `performance_diagnostic.py` |
| RMM Analysis Scripts | 4 | `two_stage_threshold_analysis.py`, `portfolio_threshold_replay.py`, `grid_feature_pattern_search.py`, `evaluate_5min_model_variants.py` |
| Other Scripts | 1 | `evaluate_profitability_engineered_only.py` |
| Test Files | ~15 | Various test files for updated signatures and renamed features |

All timezone conversions are consolidated in `SessionService`, making future improvements (e.g., session-relative hours) easier to implement.
