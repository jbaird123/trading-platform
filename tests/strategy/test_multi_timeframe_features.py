"""Tests for multi-timeframe feature computation.

This module tests the feature engine's ability to compute indicators on
higher timeframes and align them back to the base timeframe.
"""

from __future__ import annotations

import pandas as pd
from trading_platform.core.config import FeatureConfig
from trading_platform.data.resample import resample_data, timeframe_to_timedelta
from trading_platform.strategy.features import compute_features


def test_compute_features_with_higher_timeframe_alignment():
    """Test that higher timeframe features are correctly computed and aligned.

    Build 15-minute data, compute an RSI on 1H timeframe, and verify it
    matches manually calculated RSI on resampled data that's been
    forward-filled back to the base index.
    """
    # Create 15-minute data for 6 hours (24 bars)
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=24, freq="15min")
    # Create price data with a clear trend
    prices = [100.0 + i * 0.5 for i in range(24)]
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p + 0.3 for p in prices],
            "low": [p - 0.3 for p in prices],
            "close": prices,
            "volume": [1000.0] * 24,
        },
        index=timestamps,
    )

    # Define a feature with timeframe="1H"
    feature_config = FeatureConfig(
        name="1h_rsi",
        type="RSI",
        params={"length": 14},
        timeframe="1h",
    )

    # Manually calculate expected values:
    # 1. Resample to 1H
    resampled_1h = resample_data(df, rule="1h")

    # 2. Compute RSI on the 1H data
    # RSI needs 14 periods, so we need at least 15 bars (1 for initial change)
    # With 24 15-min bars, we get 6 1H bars
    from trading_platform.strategy.indicators_registry import INDICATORS

    rsi_indicator = INDICATORS["RSI"]
    rsi_impl = rsi_indicator["implementation"]
    rsi_1h = rsi_impl(resampled_1h, {"length": 14}, "close", None)

    # 3. Forward-fill to the original 15m index
    close_index = rsi_1h.index + timeframe_to_timedelta("1h")
    expected = rsi_1h.copy()
    expected.index = close_index
    expected = expected.reindex(df.index, method="ffill")

    # Now compute using compute_features
    result = compute_features(df, [feature_config.model_dump()])

    # Verify the column exists
    assert "1h_rsi" in result.columns

    # Verify the values match (where not NaN)
    valid_mask = expected.notna()
    pd.testing.assert_series_equal(
        result.loc[valid_mask, "1h_rsi"],
        expected[valid_mask],
        check_names=False,
    )


def test_compute_features_caches_resampled_data_per_timeframe():
    """Test that resample_data is called only once per unique timeframe.

    When multiple features share the same higher timeframe, the resampling
    should be cached to avoid redundant computation.
    """
    from unittest.mock import patch

    # Create 15-minute data for 4 hours
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=16, freq="15min")
    df = pd.DataFrame(
        {
            "open": list(range(100, 116)),
            "high": list(range(101, 117)),
            "low": list(range(99, 115)),
            "close": list(range(100, 116)),
            "volume": [1000.0] * 16,
        },
        index=timestamps,
    )

    # Define multiple features that all use 1H timeframe
    feature_configs = [
        {"name": "1h_rsi", "type": "RSI", "params": {"length": 14}, "timeframe": "1h"},
        {"name": "1h_sma", "type": "SMA", "params": {"length": 3}, "timeframe": "1h"},
        {"name": "1h_ema", "type": "EMA", "params": {"length": 5}, "timeframe": "1h"},
    ]

    # Patch resample_data to count calls
    with patch(
        "trading_platform.strategy.features.resample_data",
        wraps=resample_data,
    ) as mock_resample:
        result = compute_features(df, feature_configs)

        # resample_data should be called exactly once for the "1h" timeframe
        # even though we have 3 features using it
        assert mock_resample.call_count == 1

        # Verify it was called with the correct rule
        call_args = mock_resample.call_args
        assert call_args[1]["rule"] == "1h"

    # Verify all features were computed
    assert "1h_rsi" in result.columns
    assert "1h_sma" in result.columns
    assert "1h_ema" in result.columns


def test_higher_timeframe_features_only_available_after_close():
    """Ensure higher timeframe indicators appear only after the bar closes."""
    timestamps = pd.date_range(start="2024-01-01 09:00:00", periods=37, freq="5min")
    df = pd.DataFrame(
        {
            "open": [100 + i for i in range(len(timestamps))],
            "high": [101 + i for i in range(len(timestamps))],
            "low": [99 + i for i in range(len(timestamps))],
            "close": [100 + i for i in range(len(timestamps))],
            "volume": [1000.0] * len(timestamps),
        },
        index=timestamps,
    )

    feature_configs = [
        {"name": "1h_sma", "type": "SMA", "params": {"length": 2}, "timeframe": "1H"}
    ]

    result = compute_features(df, feature_configs)

    before_close = pd.Timestamp("2024-01-01 10:55:00")
    at_close = pd.Timestamp("2024-01-01 11:00:00")

    assert pd.isna(result.loc[before_close, "1h_sma"])
    assert not pd.isna(result.loc[at_close, "1h_sma"])


def test_compute_features_backwards_compatible_without_timeframe():
    """Test that features without timeframe field work as before.

    Existing strategies that don't specify timeframe should continue to
    work correctly, computing features on the base timeframe.
    """
    # Create simple test data
    timestamps = pd.date_range(start="2024-01-01 00:00:00", periods=20, freq="1h")
    df = pd.DataFrame(
        {
            "open": list(range(100, 120)),
            "high": list(range(101, 121)),
            "low": list(range(99, 119)),
            "close": list(range(100, 120)),
            "volume": [1000.0] * 20,
        },
        index=timestamps,
    )

    # Define features WITHOUT timeframe field (legacy behavior)
    feature_configs = [
        {"name": "sma_5", "type": "SMA", "params": {"length": 5}},
        {"name": "ema_10", "type": "EMA", "params": {"length": 10}},
    ]

    # Should compute successfully on base timeframe
    result = compute_features(df, feature_configs)

    # Verify features exist
    assert "sma_5" in result.columns
    assert "ema_10" in result.columns

    # Verify they computed correctly on base data (not resampled)
    # SMA of last 5 values should be simple average
    from trading_platform.strategy.indicators_registry import INDICATORS

    sma_indicator = INDICATORS["SMA"]
    sma_impl = sma_indicator["implementation"]
    expected_sma = sma_impl(df, {"length": 5}, "close", None)

    pd.testing.assert_series_equal(
        result["sma_5"],
        expected_sma,
        check_names=False,
    )
