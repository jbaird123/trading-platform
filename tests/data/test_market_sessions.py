from datetime import time

import pandas as pd
import pytest
from trading_platform.data.market_sessions import (
    SESSION_GROUPS,
    MarketSession,
    SessionService,
)


class TestMarketSession:
    def test_session_definition_is_frozen(self):
        """MarketSession should be immutable."""
        defn = MarketSession("test", time(9, 0), time(17, 0), "UTC")
        with pytest.raises(AttributeError):
            defn.name = "modified"  # type: ignore[misc]

    def test_session_definition_fields(self):
        """MarketSession should have all required fields."""
        defn = MarketSession(
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
                pytest.fail(
                    f"Invalid reference_timezone in {group_name}: "
                    f"{group['reference_timezone']}"
                )

            # Check session timezones
            for session_name, session in group["sessions"].items():
                try:
                    pytz.timezone(session.timezone)
                except pytz.UnknownTimeZoneError:
                    pytest.fail(
                        f"Invalid timezone in {group_name}.{session_name}: "
                        f"{session.timezone}"
                    )


class TestSessionServiceIsSessionOpen:
    def test_london_open_during_winter(self):
        """London session should be open 8 AM - 5 PM GMT in winter."""
        # Jan 15, 2024 - UK is on GMT (UTC+0)
        # 10:00 UTC = 10:00 GMT = within London session
        utc_index = pd.DatetimeIndex(["2024-01-15 10:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] is True

    def test_london_closed_before_open_winter(self):
        """London session should be closed before 8 AM GMT in winter."""
        # Jan 15, 2024 - 07:00 UTC = 07:00 GMT = before London open
        utc_index = pd.DatetimeIndex(["2024-01-15 07:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] is False

    def test_london_open_during_summer_dst(self):
        """London session should be open 8 AM - 5 PM BST in summer."""
        # Jul 15, 2024 - UK is on BST (UTC+1)
        # 10:00 UTC = 11:00 BST = within London session
        utc_index = pd.DatetimeIndex(["2024-07-15 10:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] is True

    def test_london_closed_before_open_summer(self):
        """London session should be closed before 8 AM BST in summer."""
        # Jul 15, 2024 - UK is on BST (UTC+1)
        # 06:00 UTC = 07:00 BST = before London open
        utc_index = pd.DatetimeIndex(["2024-07-15 06:00:00"], tz="UTC")
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert result.iloc[0] is False

    def test_newyork_open_during_winter(self):
        """NY session should be open 8 AM - 5 PM EST in winter."""
        # Jan 15, 2024 - US is on EST (UTC-5)
        # 14:00 UTC = 9:00 AM EST = within NY session
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")
        ny_def = SESSION_GROUPS["forex"]["sessions"]["newyork"]

        result = SessionService.is_session_open(utc_index, ny_def)

        assert result.iloc[0] is True

    def test_newyork_open_during_summer_dst(self):
        """NY session should be open 8 AM - 5 PM EDT in summer."""
        # Jul 15, 2024 - US is on EDT (UTC-4)
        # 13:00 UTC = 9:00 AM EDT = within NY session
        utc_index = pd.DatetimeIndex(["2024-07-15 13:00:00"], tz="UTC")
        ny_def = SESSION_GROUPS["forex"]["sessions"]["newyork"]

        result = SessionService.is_session_open(utc_index, ny_def)

        assert result.iloc[0] is True

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
        assert winter_result.iloc[0] is True
        assert summer_result.iloc[0] is True

    def test_crypto_always_open(self):
        """Crypto 'always' session should be open 24/7."""
        crypto_def = SESSION_GROUPS["crypto"]["sessions"]["always"]

        # Test various times
        utc_index = pd.DatetimeIndex(
            [
                "2024-01-15 00:00:00",
                "2024-01-15 12:00:00",
                "2024-07-15 06:00:00",
                "2024-07-15 23:59:00",
            ],
            tz="UTC",
        )

        result = SessionService.is_session_open(utc_index, crypto_def)

        assert result.all() is True

    def test_returns_series_with_correct_index(self):
        """is_session_open should return Series with same index as input."""
        utc_index = pd.DatetimeIndex(
            [
                "2024-01-15 10:00:00",
                "2024-01-15 11:00:00",
                "2024-01-15 12:00:00",
            ],
            tz="UTC",
        )
        london_def = SESSION_GROUPS["forex"]["sessions"]["london"]

        result = SessionService.is_session_open(utc_index, london_def)

        assert isinstance(result, pd.Series)
        assert result.index.equals(utc_index)


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
            "forex_session_overlap_london_newyork",
        ]
        # Note: logic might produce london_newyork or london_ny dep on naming.
        # My data uses 'newyork', so overlap key is ('london', 'newyork')
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
        assert result["forex_session_overlap_london_newyork"].iloc[0] == 1.0

    def test_forex_no_overlap_when_one_closed(self):
        """Overlap should be 0.0 when only one session is open."""
        # Jan 15, 2024 - 20:00 UTC
        # London: 20:00 GMT = closed (8-17)
        # NY: 15:00 EST = open (8-17)
        utc_index = pd.DatetimeIndex(["2024-01-15 20:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "forex")

        assert result["forex_session_london"].iloc[0] == 0.0
        assert result["forex_session_newyork"].iloc[0] == 1.0
        assert result["forex_session_overlap_london_newyork"].iloc[0] == 0.0

    def test_crypto_returns_always_column(self):
        """get_session_flags for crypto should return always session."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        result = SessionService.get_session_flags(utc_index, "crypto")

        assert "crypto_session_always" in result.columns
        assert result["crypto_session_always"].iloc[0] == 1.0

    def test_invalid_session_group_raises(self):
        """Invalid session group should raise ValueError."""
        utc_index = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")

        with pytest.raises(ValueError, match="Unknown session group"):
            SessionService.get_session_flags(utc_index, "invalid_group")


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

    def test_get_local_day_of_week_forex(self):
        """Forex local day should be NY day of week."""
        # Jan 15, 2024 is Monday
        # 03:00 UTC on Jan 15 = 22:00 EST on Jan 14 (Sunday)
        ts = pd.Timestamp("2024-01-15 03:00:00", tz="UTC")

        result = SessionService.get_local_day_of_week(ts, "forex")

        # In NY it's still Sunday (day 6)
        assert result == 6
