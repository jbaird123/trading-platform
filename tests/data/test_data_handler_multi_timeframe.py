"""
Tests for multi-timeframe feature support.

Task 10: Epic 1.3, Feature 1.3
Validates higher-timeframe feature computation and resampling.
"""

from __future__ import annotations

import pandas as pd
from trading_platform.strategy.features import compute_features


def test_get_higher_timeframe_feature():
    """Task 10: Test higher-timeframe feature computation.

    Validates: Epic 1.3, Feature 1.3, Task 10
    Tests that a 15min DataFrame can request a feature like adx_1h
    and the column is correctly resampled and forward-filled.
    """
    # Create sample 15-minute data (need enough for ADX warmup)
    dates = pd.date_range("2024-01-01 09:00", periods=60, freq="15min")
    df = pd.DataFrame(
        {
            "open": range(100, 160),
            "high": range(101, 161),
            "low": range(99, 159),
            "close": range(100, 160),
            "volume": [1000] * 60,
        },
        index=dates,
    )

    # Request a higher-timeframe feature (ADX on 1H timeframe)
    specs = [
        {
            "name": "adx_1h",
            "type": "ADX",
            "params": {"length": 5},  # Short period for testing
            "source": "close",
            "timeframe": "1h",  # Specify higher timeframe
        }
    ]

    result = compute_features(df, specs)

    # Verify the ADX features were added (ADX returns 3 columns: ADX, DI+, DI-)
    assert "adx_1h_ADX" in result.columns
    assert "adx_1h_DI+" in result.columns
    assert "adx_1h_DI-" in result.columns

    # Verify it has the same length as input (forward-filled)
    assert len(result) == len(df)

    # Verify it contains numeric values (may have NaN during warmup)
    assert result["adx_1h_ADX"].dtype == "float64"

    # Verify forward-fill worked (values should repeat within each hour)
    # First hour (4 bars of 15min): should have same value
    valid_values = result["adx_1h_ADX"].dropna()
    if len(valid_values) > 4:
        # Check that within a 1-hour window, values are constant (forward-filled)
        first_hour_values = result["adx_1h_ADX"].iloc[0:4]
        if not first_hour_values.isna().all():
            # Values within the same hour should be identical (forward-filled)
            unique_in_hour = first_hour_values.dropna().nunique()
            assert unique_in_hour <= 1  # Should be 0 or 1 (all same or all NaN)
