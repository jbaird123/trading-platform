"""Test coverage for strategy/features.py missing lines."""

import pytest
import pandas as pd
import numpy as np

from trading_platform.strategy.features import (
    _price_series, ema, adx, bb_width, hhv, llv, donchian_channels, compute_features
)


def test_price_series_fallback():
    """Test _price_series fallback to close when invalid source (line 51)."""
    # DataFrame with OHLC data
    df = pd.DataFrame({
        'open': [1.1000, 1.1020, 1.1040],
        'high': [1.1050, 1.1080, 1.1070],
        'low': [1.0990, 1.1010, 1.1030],
        'close': [1.1030, 1.1050, 1.1060]
    })
    
    # Test with invalid source - should fallback to close (line 51)
    result = _price_series(df, "invalid_source")
    expected = pd.Series([1.1030, 1.1050, 1.1060], dtype="float64", name="close")
    pd.testing.assert_series_equal(result, expected)
    
    # Test ohlc4 source to hit lines 45-50
    result_ohlc4 = _price_series(df, "ohlc4")
    # Should be average of OHLC
    expected_ohlc4 = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0
    expected_ohlc4 = pd.Series(expected_ohlc4, dtype="float64")
    # Remove name for comparison since result doesn't have name
    expected_ohlc4.name = None
    pd.testing.assert_series_equal(result_ohlc4, expected_ohlc4)


def test_adx_short_dataframe():
    """Test adx with DataFrame shorter than 3 bars (lines 85-87)."""
    # Create DataFrame with only 2 bars (less than required minimum of 3)
    df = pd.DataFrame({
        'high': [1.1050, 1.1080],
        'low': [1.1000, 1.1030],
        'close': [1.1025, 1.1070]
    })
    
    result = adx(df, length=14)
    expected = pd.Series([0.0, 0.0], index=df.index, dtype="float64")
    pd.testing.assert_series_equal(result, expected)
    
    # Test with single bar
    df_single = pd.DataFrame({
        'high': [1.1050],
        'low': [1.1000], 
        'close': [1.1025]
    })
    
    result_single = adx(df_single, length=14)
    expected_single = pd.Series([0.0], index=df_single.index, dtype="float64")
    pd.testing.assert_series_equal(result_single, expected_single)


def test_adx_length_clamping():
    """Test adx length parameter clamping (line 89-90)."""
    # Create minimal DataFrame with 3 bars
    df = pd.DataFrame({
        'high': [1.1050, 1.1080, 1.1060],
        'low': [1.1000, 1.1030, 1.1010],
        'close': [1.1025, 1.1070, 1.1045]
    })
    
    # Test with length larger than available data 
    # Should clamp to available length (3)
    result = adx(df, length=100)
    assert len(result) == 3
    assert not result.isna().any()
    
    # Test with length smaller than minimum (3)
    # Should clamp to minimum (3)
    result_small = adx(df, length=1)
    assert len(result_small) == 3
    assert not result_small.isna().any()


def test_bb_width_short_length():
    """Test bb_width with various length parameters."""
    series = pd.Series([1.1000, 1.1050, 1.1025, 1.1080, 1.1040])
    
    # Test normal case
    result = bb_width(series, length=3, ndev=2.0)
    assert len(result) == len(series)
    assert not result.isna().all()  # Should have some non-NaN values


def test_hhv_empty_window():
    """Test hhv with invalid/empty window conditions (lines 164-165)."""
    series = pd.Series([1.1000, 1.1050, 1.1025, 1.1080, 1.1040])
    
    # Test with window length larger than series
    result = hhv(series, length=10)
    # Should handle gracefully without errors
    assert len(result) == len(series)
    
    # Test with zero or negative length
    with pytest.raises((ValueError, Exception)):
        hhv(series, length=0)


def test_llv_empty_window():
    """Test llv with invalid/empty window conditions (line 167)."""
    series = pd.Series([1.1000, 1.1050, 1.1025, 1.1080, 1.1040])
    
    # Test with window length larger than series  
    result = llv(series, length=10)
    # Should handle gracefully without errors
    assert len(result) == len(series)
    
    # Test with zero or negative length
    with pytest.raises((ValueError, Exception)):
        llv(series, length=0)


def test_donchian_channels_short_data():
    """Test donchian_channels with short data."""
    df = pd.DataFrame({
        'high': [1.1050, 1.1080, 1.1060],
        'low': [1.1000, 1.1030, 1.1010],
        'close': [1.1025, 1.1070, 1.1045]
    })
    
    # Test donchian channels
    upper, lower = donchian_channels(df, length=2)
    assert len(upper) == len(df)
    assert len(lower) == len(df)
    assert not upper.isna().all()
    assert not lower.isna().all()


def test_compute_features_error_conditions():
    """Test compute_features with various error conditions."""
    # Minimal DataFrame for testing
    df = pd.DataFrame({
        'close': [1.1000, 1.1050, 1.1025]
    }, index=pd.date_range('2024-01-01', periods=3, freq='1H'))
    
    # Test with empty feature config
    result = compute_features(df, {}, {})
    assert isinstance(result, pd.DataFrame)
    assert len(result) == len(df)


def test_feature_functions_with_nan_data():
    """Test feature functions with NaN data to cover error handling."""
    # Series with NaN values
    series_with_nan = pd.Series([1.1000, np.nan, 1.1025, 1.1080, np.nan])
    
    # Test ema with NaN data
    result_ema = ema(series_with_nan, length=3)
    assert len(result_ema) == len(series_with_nan)
    
    # Test hhv with NaN data
    result_hhv = hhv(series_with_nan, length=3) 
    assert len(result_hhv) == len(series_with_nan)
    
    # Test llv with NaN data
    result_llv = llv(series_with_nan, length=3)
    assert len(result_llv) == len(series_with_nan)