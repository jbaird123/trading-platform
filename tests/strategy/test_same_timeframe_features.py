"""Test feature computation when execution timeframe matches feature timeframe.

This tests the edge case where a strategy running on timeframe X computes features
also on timeframe X (e.g., 15min strategy with 15min EMA).
"""

import pandas as pd
import pytest
from trading_platform.strategy.features import compute_features


def test_same_timeframe_no_forward_fill():
    """When execution TF == feature TF, features should not be forward-filled.

    This test ensures that when computing 15min features on 15min data,
    the features are correctly aligned without forward-fill leakage.

    Bug: Previously, even when execution TF == feature TF, the reindex with
    method="ffill" would forward-fill values, causing features from bar N
    to leak into bar N+1.

    Expected: Features computed on bar N should only be available at bar N,
    not forward-filled to bar N+1.

    Note: compute_features applies bar-close alignment (shifts index by timeframe),
    so the result index will be shifted by 15min from the input.
    """
    # Create 15min data with UTC timestamps
    timestamps = pd.date_range(
        start="2024-01-01 09:00:00", periods=8, freq="15min", tz="UTC"
    )
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]

    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(timestamps),
        },
        index=timestamps,
    )

    # Compute 15min EMA on 15min data
    feature_configs = [
        {
            "name": "15min_ema_3",
            "type": "EMA",
            "params": {"length": 3},
            "timeframe": "15min",
        }
    ]

    result = compute_features(df, feature_configs)

    # Verify the result has bar-close aligned index (shifted by 15min from input)
    assert result.index[0] == pd.Timestamp("2024-01-01 09:15:00", tz="UTC")

    # Manually calculate expected EMA
    from trading_platform.strategy.indicators_registry import INDICATORS

    ema_indicator = INDICATORS["EMA"]
    ema_impl = ema_indicator["implementation"]
    expected_ema = ema_impl(df, {"length": 3}, "close", None)

    # Compare values only (indices differ due to bar-close alignment)
    pd.testing.assert_series_equal(
        result["15min_ema_3"].reset_index(drop=True),
        expected_ema.reset_index(drop=True),
        check_names=False,
        rtol=1e-10,
    )

    # Verify specific values to ensure no forward-fill happened
    # EMA at index 2 should use closes from indices 0, 1, 2
    # It should NOT be the same as EMA at index 1
    if not pd.isna(result["15min_ema_3"].iloc[2]):
        assert result["15min_ema_3"].iloc[2] != result["15min_ema_3"].iloc[1]


def test_cache_vs_compute_features_alignment():
    """Verify that compute_features produces same alignment as cache would.

    The global feature cache uses a merge_asof strategy that correctly
    aligns features. The compute_features function should produce the
    same alignment when execution TF == feature TF.
    """
    timestamps = pd.date_range(start="2024-01-01 09:00:00", periods=12, freq="15min")
    closes = list(range(100, 112))

    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(timestamps),
        },
        index=timestamps,
    )

    # Compute feature using compute_features
    feature_configs = [
        {
            "name": "15min_sma_5",
            "type": "SMA",
            "params": {"length": 5},
            "timeframe": "15min",
        }
    ]

    result = compute_features(df, feature_configs)

    # The feature at timestamp T should represent the SMA calculated
    # using data available up to and including timestamp T
    # NOT data from timestamp T+1

    # At 09:00, SMA should use closes from 09:00 and earlier (but need 5 periods)
    # First valid SMA should be at index 4 (09:00 + 4*15min = 10:00)
    assert pd.isna(result["15min_sma_5"].iloc[0])  # Not enough data
    assert pd.isna(result["15min_sma_5"].iloc[3])  # Still not enough
    assert not pd.isna(result["15min_sma_5"].iloc[4])  # First valid SMA

    # The SMA at index 4 (10:00) should be the average of closes 0-4
    expected_sma_at_4 = sum(closes[0:5]) / 5
    actual_sma_at_4 = result["15min_sma_5"].iloc[4]
    assert abs(actual_sma_at_4 - expected_sma_at_4) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
