"""
Tests for time-based regime classification in RMM.

This module verifies that the RMM engine correctly handles time-based
predicates like hour_is_in, day_of_week_is_in, etc.
"""

from __future__ import annotations

import pandas as pd
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.regime_market_manager.models import RMMConfig


def test_hour_is_in_predicate() -> None:
    """Test that hour_is_in condition correctly filters by hour."""
    # Create sample data covering a full day (24 hours)
    dates = pd.date_range("2024-01-01 00:00", "2024-01-01 23:00", freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0] * len(dates),
            "high": [101.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [100.5] * len(dates),
            "volume": [1000] * len(dates),
        },
        index=dates,
    )

    # Define RMM config that uses hour_is_in for hours 9, 10, 11
    config = {
        "regimes": [
            {
                "label": "trading_hours",
                "confidence": 1.0,
                "conditions": {
                    "all_of": [{"condition": "hour_is_in", "values": [9, 10, 11]}]
                },
            }
        ]
    }

    engine = RMMEngine(config=RMMConfig(**config))  # type: ignore[arg-type]
    # Use crypto (UTC) so input UTC hours match local hours
    result = engine.classify_regime(df, already_resampled=True, session_group="crypto")

    # Assert that only hours 9, 10, 11 have the trading_hours label
    # Note: RMM shifts by 1 bar to prevent lookahead bias, so the index starts
    # at 01:00 (not 00:00), but the hour check uses the shifted index's hour.
    assert (
        result.loc[pd.Timestamp("2024-01-01 09:00", tz="UTC"), "label"]
        == "trading_hours"
    )
    assert (
        result.loc[pd.Timestamp("2024-01-01 10:00", tz="UTC"), "label"]
        == "trading_hours"
    )
    assert (
        result.loc[pd.Timestamp("2024-01-01 11:00", tz="UTC"), "label"]
        == "trading_hours"
    )

    # All other hours should be "unknown"
    assert result.loc[pd.Timestamp("2024-01-01 08:00", tz="UTC"), "label"] == "unknown"
    assert result.loc[pd.Timestamp("2024-01-01 12:00", tz="UTC"), "label"] == "unknown"
    assert result.loc[pd.Timestamp("2024-01-01 01:00", tz="UTC"), "label"] == "unknown"
    assert result.loc[pd.Timestamp("2024-01-01 23:00", tz="UTC"), "label"] == "unknown"


def test_day_of_week_is_in_predicate() -> None:
    """Test that day_of_week_is_in filters by day (Mon=0, Sun=6)."""
    # Create sample data covering a full week
    dates = pd.date_range(
        "2024-01-01", "2024-01-07", freq="1D", tz="UTC"
    )  # Jan 1, 2024 is a Monday
    df = pd.DataFrame(
        {
            "open": [100.0] * len(dates),
            "high": [101.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [100.5] * len(dates),
            "volume": [1000] * len(dates),
        },
        index=dates,
    )

    # Define RMM config that uses day_of_week_is_in for Mon(0), Wed(2)
    config = {
        "regimes": [
            {
                "label": "weekday_trading",
                "confidence": 1.0,
                "conditions": {
                    "all_of": [{"condition": "day_of_week_is_in", "values": [0, 2]}]
                },
            }
        ]
    }

    engine = RMMEngine(config=RMMConfig(**config))  # type: ignore[arg-type]
    # Use crypto (UTC) so we don't worry about timezone offsets changing the day
    result = engine.classify_regime(df, already_resampled=True, session_group="crypto")

    # Assert Mon (day_of_week=0) and Wed (day_of_week=2) have weekday_trading label
    # Note: RMM shifts by 1 bar. Jan 1 2024 is Monday (day 0).
    # After shift: Jan 1 (Mon) data appears at Jan 2 index, etc.
    # But the day_of_week check is on the shifted row's actual day value.
    # So Jan 3 (Wed) shows weekday_trading because Wed is day_of_week=2.
    assert (
        result.loc[pd.Timestamp("2024-01-03", tz="UTC"), "label"] == "weekday_trading"
    )  # Wed

    # All other days should be "unknown" (shifted, so Jan 1 Mon is not in result)
    assert result.loc[pd.Timestamp("2024-01-02", tz="UTC"), "label"] == "unknown"  # Tue
    assert result.loc[pd.Timestamp("2024-01-04", tz="UTC"), "label"] == "unknown"  # Thu
    assert result.loc[pd.Timestamp("2024-01-05", tz="UTC"), "label"] == "unknown"  # Fri
    assert result.loc[pd.Timestamp("2024-01-06", tz="UTC"), "label"] == "unknown"  # Sat
    assert result.loc[pd.Timestamp("2024-01-07", tz="UTC"), "label"] == "unknown"  # Sun


def test_combined_time_and_indicator_regime() -> None:
    """Test combining time-based and indicator-based conditions."""
    # Create sample data with a simple custom column
    dates = pd.date_range("2024-01-01 00:00", "2024-01-01 23:00", freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [100.0] * len(dates),
            "high": [101.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [100.5] * len(dates),
            "volume": [1000] * len(dates),
        },
        index=dates,
    )

    # Add a simple indicator column directly
    # Hours 0-11 have strength < 50, hours 12-23 have strength > 50
    df["strength"] = [40.0] * 12 + [60.0] * 12

    # Define RMM config combining hour_is_in with strength > 50
    # No features computation needed - just use the raw column
    config = {
        "regimes": [
            {
                "label": "strong_trend_hours",
                "confidence": 1.0,
                "conditions": {
                    "all_of": [
                        {"condition": "hour_is_in", "values": [14, 15, 16]},
                        {
                            "condition": "is_above",
                            "left": {"ref": "strength"},
                            "right": 50,
                        },
                    ]
                },
            }
        ],
    }

    engine = RMMEngine(config=RMMConfig(**config))  # type: ignore[arg-type]
    result = engine.classify_regime(df, already_resampled=True, session_group="crypto")

    # Hours 14, 15, 16 with strength > 50 should be labeled
    assert (
        result.loc[pd.Timestamp("2024-01-01 14:00", tz="UTC"), "label"]
        == "strong_trend_hours"
    )
    assert (
        result.loc[pd.Timestamp("2024-01-01 15:00", tz="UTC"), "label"]
        == "strong_trend_hours"
    )
    assert (
        result.loc[pd.Timestamp("2024-01-01 16:00", tz="UTC"), "label"]
        == "strong_trend_hours"
    )

    # Hour 10 has low strength, so should be unknown
    assert result.loc[pd.Timestamp("2024-01-01 10:00", tz="UTC"), "label"] == "unknown"

    # Hour 20 has high strength but wrong time, so should be unknown
    assert result.loc[pd.Timestamp("2024-01-01 20:00", tz="UTC"), "label"] == "unknown"
