"""
Consolidated tests for trading_platform.strategy.features.

# Validates: [SE-3.6], [SE-3.7], [DH-2.11]

Merged comprehensive coverage, gap, and path-focused suites.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from trading_platform.strategy.features import (
    _price_series,
    _resolve_parameter,
    adx,
    bb_width,
    compute_features,
    donchian_channels,
    ema,
    ema_slope,
    hhv,
    llv,
)

# --- test_features_comprehensive_coverage.py ---

"""Comprehensive test coverage for strategy/features.py to achieve 100% coverage."""


def test_resolve_parameter_not_found():
    """Test _resolve_parameter when parameter is not found (lines 149-152)."""
    strategy_parameters = {"existing_param": 42}

    # Test parameter placeholder that doesn't exist in strategy_parameters
    param_value = "${nonexistent_param}"

    with pytest.raises(
        ValueError,
        match="Parameter 'nonexistent_param' not found in strategy parameters",
    ):
        _resolve_parameter(param_value, strategy_parameters)


def test_resolve_parameter_found():
    """Test _resolve_parameter when parameter is found."""
    strategy_parameters = {"test_param": 25}

    # Test parameter placeholder that exists
    param_value = "${test_param}"
    result = _resolve_parameter(param_value, strategy_parameters)
    assert result == 25


def test_resolve_parameter_non_string():
    """Test _resolve_parameter with non-string values."""
    strategy_parameters = {"test_param": 25}

    # Test with integer
    result = _resolve_parameter(42, strategy_parameters)
    assert result == 42

    # Test with float
    result = _resolve_parameter(3.14, strategy_parameters)
    assert result == 3.14


def test_resolve_parameter_regular_string():
    """Test _resolve_parameter with regular string (not a placeholder)."""
    strategy_parameters = {"test_param": 25}

    # Test with regular string
    result = _resolve_parameter("regular_string", strategy_parameters)
    assert result == "regular_string"


def test_compute_features_none_strategy_parameters():
    """Test compute_features when strategy_parameters is None (line 164)."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020],
            "high": [1.1050, 1.1080],
            "low": [1.1000, 1.1030],
            "close": [1.1030, 1.1070],
            "volume": [100, 200],
        }
    )

    specs = [{"name": "test_ema", "type": "EMA", "params": {"length": 10}}]

    # Pass None as strategy_parameters to trigger line 164
    result = compute_features(df, specs, strategy_parameters=None)

    assert "test_ema" in result.columns
    assert len(result) == len(df)


def test_compute_features_source_ref_handling():
    """Test compute_features with source_ref handling (lines 175-176)."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020],
            "high": [1.1050, 1.1080],
            "low": [1.1000, 1.1030],
            "close": [1.1030, 1.1070],
            "custom_column": [1.1025, 1.1045],
        }
    )

    # Test with source_ref as dict with ref key
    specs = [
        {
            "name": "test_hhv",
            "type": "HHV",
            "params": {"length": 5},
            "source_ref": {"ref": "custom_column"},
        }
    ]

    result = compute_features(df, specs)
    assert "test_hhv" in result.columns

    # Test with source_ref dict with None ref value (line 176)
    specs_none_ref = [
        {
            "name": "test_hhv2",
            "type": "HHV",
            "params": {"length": 5},
            "source_ref": {"ref": None},
        }
    ]

    result2 = compute_features(df, specs_none_ref)
    assert "test_hhv2" in result2.columns


def test_compute_features_empty_name():
    """Test compute_features with empty name to trigger continue (line 178)."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020],
            "high": [1.1050, 1.1080],
            "low": [1.1000, 1.1030],
            "close": [1.1030, 1.1070],
        }
    )

    # Get initial column count
    initial_columns = set(df.columns)

    # Test with empty name - should be skipped
    specs = [
        {
            "name": "",
            "type": "EMA",
            "params": {"length": 10},
        },  # Empty name -> str("") = ""
        {
            "type": "SMA",
            "params": {"length": 20},
        },  # Missing name key -> spec.get("name") = None -> str(None) = "None"
        {"name": "valid_ema", "type": "EMA", "params": {"length": 10}},  # Valid spec
    ]

    result = compute_features(df, specs)

    # Should have the valid feature
    assert "valid_ema" in result.columns

    # The empty name ("") should be skipped due to `if not name: continue`
    # Missing name (None) should also be skipped by the canonical pipeline
    # Let's check that we have the expected columns
    expected_new_columns = {
        "valid_ema",
    }  # Both empty and None names are skipped
    new_columns = set(result.columns) - initial_columns
    assert new_columns == expected_new_columns


def test_compute_features_source_ref_edge_cases():
    """Test additional source_ref edge cases."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020],
            "high": [1.1050, 1.1080],
            "low": [1.1000, 1.1030],
            "close": [1.1030, 1.1070],
        }
    )

    # Test with source_ref that's not a dict
    specs_non_dict = [
        {
            "name": "test_hhv3",
            "type": "HHV",
            "params": {"length": 5},
            "source_ref": "not_a_dict",
        }
    ]

    result = compute_features(df, specs_non_dict)
    assert "test_hhv3" in result.columns

    # Test with source_ref dict without ref key
    specs_no_ref = [
        {
            "name": "test_hhv4",
            "type": "HHV",
            "params": {"length": 5},
            "source_ref": {"other_key": "value"},
        }
    ]

    result2 = compute_features(df, specs_no_ref)
    assert "test_hhv4" in result2.columns


def test_compute_features_llv_with_source_ref():
    """Test LLV with source_ref to cover that branch."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020],
            "high": [1.1050, 1.1080],
            "low": [1.1000, 1.1030],
            "close": [1.1030, 1.1070],
            "custom_low": [1.0990, 1.1020],
        }
    )

    specs = [
        {
            "name": "test_llv",
            "type": "LLV",
            "params": {"length": 5},
            "source_ref": {"ref": "custom_low"},
        }
    ]

    result = compute_features(df, specs)
    assert "test_llv" in result.columns


def test_compute_features_parameter_substitution():
    """Test parameter substitution with strategy_parameters."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1030],
            "high": [1.1050, 1.1080, 1.1090],
            "low": [1.1000, 1.1030, 1.1040],
            "close": [1.1030, 1.1070, 1.1080],
        }
    )

    strategy_parameters = {"ema_length": 10, "rsi_period": 14, "bb_dev": 2.0}

    specs = [
        {"name": "dynamic_ema", "type": "EMA", "params": {"length": "${ema_length}"}},
        {"name": "dynamic_rsi", "type": "RSI", "params": {"length": "${rsi_period}"}},
        {
            "name": "dynamic_bb",
            "type": "BBWidth",
            "params": {"length": 20, "ndev": "${bb_dev}"},
        },
    ]

    result = compute_features(df, specs, strategy_parameters)

    assert "dynamic_ema" in result.columns
    assert "dynamic_rsi" in result.columns
    assert "dynamic_bb" in result.columns


def test_compute_features_all_indicator_types():
    """Test all indicator types to ensure complete coverage."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1030, 1.1040, 1.1050],
            "high": [1.1050, 1.1080, 1.1090, 1.1100, 1.1110],
            "low": [1.1000, 1.1030, 1.1040, 1.1050, 1.1060],
            "close": [1.1030, 1.1070, 1.1080, 1.1090, 1.1100],
            "volume": [100, 200, 150, 300, 250],
        }
    )

    # Test all supported indicator types
    specs: list[dict[str, object]] = [
        {"name": "test_ema", "type": "EMA", "params": {"length": 3}},
        {"name": "test_sma", "type": "SMA", "params": {"length": 3}},
        {"name": "test_wma", "type": "WMA", "params": {"length": 3}},
        {"name": "test_rsi", "type": "RSI", "params": {"length": 3}},
        {"name": "test_atr", "type": "ATR", "params": {"length": 3}},
        {"name": "test_adx", "type": "ADX", "params": {"length": 3}},
        {"name": "test_bb", "type": "BB", "params": {"length": 3, "ndev": 2.0}},
        {
            "name": "test_bbwidth",
            "type": "BBWidth",
            "params": {"length": 3, "ndev": 2.0},
        },
        {
            "name": "test_macd",
            "type": "MACD",
            "params": {"slow": 4, "fast": 2, "signal": 2},
        },
        {"name": "test_psar", "type": "PSAR", "params": {"step": 0.02, "max": 0.2}},
        {"name": "test_stoch", "type": "STOCH", "params": {"length": 3}},
        {"name": "test_cci", "type": "CCI", "params": {"length": 3}},
        {"name": "test_roc", "type": "ROC", "params": {"length": 3}},
        {"name": "test_hhv", "type": "HHV", "params": {"length": 3}},
        {"name": "test_llv", "type": "LLV", "params": {"length": 3}},
        {"name": "test_dc", "type": "DC", "params": {"length": 3}},
        {"name": "test_kc", "type": "KC", "params": {"length": 3}},
        {"name": "test_obv", "type": "OBV"},
        {"name": "test_cmf", "type": "CMF", "params": {"length": 3}},
        {"name": "test_vwap", "type": "VWAP"},
    ]

    result = compute_features(df, specs)

    # Check that all expected columns are present
    for spec in specs:
        name = str(spec["name"])
        typ = str(spec["type"])

        if typ == "BB":
            assert f"{name}_upper" in result.columns
            assert f"{name}_lower" in result.columns
            assert f"{name}_middle" in result.columns
        elif typ == "ADX":
            assert f"{name}_ADX" in result.columns
            assert f"{name}_DI+" in result.columns
            assert f"{name}_DI-" in result.columns
        elif typ == "MACD":
            assert f"{name}_macd" in result.columns
            assert f"{name}_signal" in result.columns
            assert f"{name}_diff" in result.columns
        elif typ == "PSAR":
            assert f"{name}" in result.columns
            assert f"{name}_up" in result.columns
            assert f"{name}_down" in result.columns
        elif typ == "STOCH":
            assert f"{name}" in result.columns
            assert f"{name}_signal" in result.columns
        elif typ == "DC":
            assert f"{name}_upper" in result.columns
            assert f"{name}_lower" in result.columns
        elif typ == "KC":
            assert f"{name}_upper" in result.columns
            assert f"{name}_lower" in result.columns
            assert f"{name}_middle" in result.columns
        else:
            assert name in result.columns


# --- test_features_coverage_gaps.py ---

"""Test coverage for strategy/features.py missing lines."""


def test_price_series_fallback():
    """Test _price_series raises ValueError for invalid source (strict validation)."""
    # DataFrame with OHLC data
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1040],
            "high": [1.1050, 1.1080, 1.1070],
            "low": [1.0990, 1.1010, 1.1030],
            "close": [1.1030, 1.1050, 1.1060],
        }
    )

    # Test with invalid source - should raise ValueError (strict validation)
    with pytest.raises(ValueError, match="Unrecognized source: invalid_source"):
        _price_series(df, "invalid_source")


def test_price_series_volume():
    """Test _price_series correctly handles volume source."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1040],
            "high": [1.1050, 1.1080, 1.1070],
            "low": [1.0990, 1.1010, 1.1030],
            "close": [1.1030, 1.1050, 1.1060],
            "volume": [1000.0, 2000.0, 1500.0],
        }
    )

    # Test volume source
    result = _price_series(df, "volume")
    expected = pd.Series([1000.0, 2000.0, 1500.0], dtype="float64", name="volume")
    pd.testing.assert_series_equal(result, expected)


def test_price_series_ohlc4():
    """Test _price_series ohlc4 source."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1040],
            "high": [1.1050, 1.1080, 1.1070],
            "low": [1.0990, 1.1010, 1.1030],
            "close": [1.1030, 1.1050, 1.1060],
        }
    )

    # Test ohlc4 source to hit lines 45-50
    result_ohlc4 = _price_series(df, "ohlc4")
    # Should be average of OHLC
    expected_ohlc4 = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    expected_ohlc4 = pd.Series(expected_ohlc4, dtype="float64")
    # Remove name for comparison since result doesn't have name
    expected_ohlc4.name = None
    pd.testing.assert_series_equal(result_ohlc4, expected_ohlc4)


def test_adx_short_dataframe():
    """Test adx with DataFrame shorter than 3 bars (lines 85-87)."""
    # Create DataFrame with only 2 bars (less than required minimum of 3)
    df = pd.DataFrame(
        {"high": [1.1050, 1.1080], "low": [1.1000, 1.1030], "close": [1.1025, 1.1070]}
    )

    result = adx(df, length=14)
    # Should return NaN for insufficient data (DataFrame with all NaN values)
    assert result.isna().all().all()

    # Test with single bar
    df_single = pd.DataFrame({"high": [1.1050], "low": [1.1000], "close": [1.1025]})

    result_single = adx(df_single, length=14)
    # Single bar also insufficient - should be NaN
    assert result_single.isna().all().all()


def test_adx_length_clamping():
    """Test adx length parameter clamping (line 89-90)."""
    # Create minimal DataFrame with 3 bars
    df = pd.DataFrame(
        {
            "high": [1.1050, 1.1080, 1.1060],
            "low": [1.1000, 1.1030, 1.1010],
            "close": [1.1025, 1.1070, 1.1045],
        }
    )

    # Test with length larger than available data
    # Should clamp to available length (3)
    result = adx(df, length=100)
    assert len(result) == 3
    # With only 3 bars, ADX may have NaN values
    # Check it returns a DataFrame with 3 columns
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["ADX", "DI+", "DI-"]

    # Test with length smaller than minimum (3)
    # Should clamp to minimum (3)
    result_small = adx(df, length=1)
    assert len(result_small) == 3
    # With minimal data, may still have NaN - just check it returns correctly
    assert isinstance(result_small, pd.DataFrame)
    assert list(result_small.columns) == ["ADX", "DI+", "DI-"]


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
    df = pd.DataFrame(
        {
            "high": [1.1050, 1.1080, 1.1060],
            "low": [1.1000, 1.1030, 1.1010],
            "close": [1.1025, 1.1070, 1.1045],
        }
    )

    # Test donchian channels
    upper, lower = donchian_channels(df, length=2)
    assert len(upper) == len(df)
    assert len(lower) == len(df)
    assert not upper.isna().all()
    assert not lower.isna().all()


def test_compute_features_error_conditions():
    """Test compute_features with various error conditions."""
    # Minimal DataFrame for testing
    df = pd.DataFrame(
        {"close": [1.1000, 1.1050, 1.1025]},
        index=pd.date_range("2024-01-01", periods=3, freq="1h"),
    )

    # Test with empty feature config
    result = compute_features(df, [], {})
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


# --- test_features_more_paths.py ---

# Validates: [DH-2.11]


def test_dc_vwap_and_unknown_type():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4],
            "high": [2, 3, 4, 5],
            "low": [1, 2, 2, 3],
            "close": [1.5, 2.5, 3.5, 4.5],
            "volume": [10, 10, 10, 10],
        },
        index=[datetime(2024, 1, 1, i) for i in range(4)],
    )

    # Test valid indicators work
    specs: list[dict[str, object]] = [
        {"name": "dc", "type": "DC", "params": {"length": 2}},
        {"name": "vwap", "type": "VWAP"},
    ]
    out = compute_features(df, specs)
    assert "dc_upper" in out and "dc_lower" in out
    assert "vwap" in out

    # Test that unknown indicators raise KeyError (fail-fast)
    specs_with_unknown: list[dict[str, object]] = [
        {"name": "unknown", "type": "UNKNOWN"},
    ]
    with pytest.raises(KeyError, match="Indicator type 'UNKNOWN' not found"):
        compute_features(df, specs_with_unknown)


# --- test_features_price_sources.py ---

# Validates: [DH-2.11]


def test_price_sources_hl2_ohlc4_and_source_ref():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "high": [3, 4, 5],
            "low": [1, 2, 3],
            "close": [2, 3, 4],
            "volume": [1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(3)],
    )
    specs = [
        {"name": "ema_hl2", "type": "EMA", "params": {"length": 1}, "source": "hl2"},
        {
            "name": "ema_ohlc4",
            "type": "EMA",
            "params": {"length": 1},
            "source": "ohlc4",
        },
    ]
    out = compute_features(df, specs)
    assert "ema_hl2" in out and "ema_ohlc4" in out


def test_ema_slope_computation():
    """Task 3: Test EMASlope indicator computation.

    Validates: Epic 1.1, Feature 1.1, Task 3
    """

    # Create test data with known trend
    df = pd.DataFrame(
        {"close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]},
        index=pd.date_range("2024-01-01", periods=6),
    )

    # Test with slope_period=1 (default)
    slope = ema_slope(df["close"], length=3, slope_period=1)

    # Verify slope series is returned
    assert isinstance(slope, pd.Series)
    assert len(slope) == len(df)

    # First value should be NaN (no previous value for diff)
    assert pd.isna(slope.iloc[0])

    # Subsequent non-NaN values should be positive (uptrend)
    # Slopes should be non-negative for uptrending price
    valid_slopes = slope.dropna()
    assert len(valid_slopes) > 0
    assert all(valid_slopes >= 0)


def test_ema_slope_in_compute_features():
    """Task 3: Test EMASlope integration in compute_features.

    Validates: Epic 1.1, Feature 1.1, Task 3
    """
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "close": [10, 11, 12, 13, 14],
            "volume": [100, 100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=5),
    )

    specs = [
        {
            "name": "ema_slope_14",
            "type": "EMASlope",
            "params": {"length": 3, "slope_period": 1},
            "source": "close",
        }
    ]

    result = compute_features(df, specs)

    # Verify column was added
    assert "ema_slope_14" in result.columns

    # Verify it contains numeric values (NaN or float)
    assert result["ema_slope_14"].dtype == "float64"

    # First value should be NaN
    assert pd.isna(result["ema_slope_14"].iloc[0])


def test_ema_trend_alignment_in_compute_features():
    """Verify EMATrendAlignment produces alignment metrics."""
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14, 15, 16, 17],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5],
            "close": [10, 11, 12, 13, 14, 15, 16, 17],
            "volume": [100] * 8,
        },
        index=pd.date_range("2024-01-01", periods=8, freq="1h"),
    )

    specs = [
        {
            "name": "trend_alignment",
            "type": "EMATrendAlignment",
            "params": {
                "timeframes": ["1H", "4H"],
                "length": 3,
                "slope_period": 1,
            },
            "source": "close",
        }
    ]

    result = compute_features(df, specs)

    stack_col = "trend_alignment_stack_score"
    align_col = "trend_alignment_full_alignment"
    nonzero_col = "trend_alignment_nonzero_fraction"

    for column in (stack_col, align_col, nonzero_col):
        assert column in result.columns
        assert result[column].dtype == "float64"

    stack_values = result[stack_col].dropna()
    assert all((stack_values >= -1.0) & (stack_values <= 1.0))


def test_ema_slope_confluence_in_compute_features():
    """Verify EMASlopeConfluence emits spread/ratio/alignment columns."""

    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14, 15, 16, 17],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5],
            "close": [10, 11, 12, 13, 14, 15, 16, 17],
            "volume": [100] * 8,
        },
        index=pd.date_range("2024-01-01", periods=8, freq="1h"),
    )

    specs = [
        {
            "name": "slope_confluence",
            "type": "EMASlopeConfluence",
            "params": {
                "base_timeframe": "1H",
                "compare_timeframes": ["4H"],
                "length": 3,
                "slope_period": 1,
            },
            "source": "close",
        }
    ]

    result = compute_features(df, specs)

    spread_col = "slope_confluence_spread_4H"
    ratio_col = "slope_confluence_ratio_4H"
    align_col = "slope_confluence_alignment_4H"

    for column in (spread_col, ratio_col, align_col):
        assert column in result.columns
        assert result[column].dtype == "float64"

    # Alignment should only take values in [-1, 1]
    alignment_values = result[align_col].dropna()
    assert all((alignment_values >= -1.0) & (alignment_values <= 1.0))


def test_rsi_in_compute_features():
    """Task 3: Test RSI indicator (already exists, verify it works).

    Validates: Epic 1.1, Feature 1.1, Task 3
    """
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14, 15, 14, 13, 12],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 14.5, 13.5, 12.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 13.5, 12.5, 11.5],
            "close": [10, 11, 12, 13, 14, 15, 14, 13, 12],
            "volume": [100, 100, 100, 100, 100, 100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=9),
    )

    specs = [
        {
            "name": "rsi_14",
            "type": "RSI",
            "params": {"length": 5},
            "source": "close",
        }
    ]

    result = compute_features(df, specs)

    # Verify column was added
    assert "rsi_14" in result.columns

    # RSI should be between 0 and 100 (where not NaN)
    valid_values = result["rsi_14"].dropna()
    assert all((valid_values >= 0) & (valid_values <= 100))


def test_roc_in_compute_features():
    """Task 3: Test ROC indicator (already exists, verify it works).

    Validates: Epic 1.1, Feature 1.1, Task 3
    """
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "close": [10, 11, 12, 13, 14],
            "volume": [100, 100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=5),
    )

    specs = [
        {
            "name": "roc_12",
            "type": "ROC",
            "params": {"length": 2},
            "source": "close",
        }
    ]

    result = compute_features(df, specs)

    # Verify column was added
    assert "roc_12" in result.columns

    # ROC should be numeric
    assert result["roc_12"].dtype == "float64"


def test_prior_return_indicator():
    """Ensure PriorReturn indicator produces expected column."""

    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13],
            "high": [10.5, 11.5, 12.5, 13.5],
            "low": [9.5, 10.5, 11.5, 12.5],
            "close": [10, 11, 12, 13],
            "volume": [100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="15min"),
    )

    specs = [
        {
            "name": "prior_return_1",
            "type": "PriorReturn",
            "params": {"window": 1},
        }
    ]

    result = compute_features(df, specs)
    assert "prior_return_1" in result.columns


def test_calendar_sessions_indicator():
    """Ensure CalendarSessions indicator yields session columns."""

    df = pd.DataFrame(
        {
            "open": [10, 11, 12],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10, 11, 12],
            "volume": [100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="1h"),
    )

    specs = [
        {
            "name": "session_features",
            "type": "CalendarSessions",
            "params": {},
        }
    ]

    result = compute_features(df, specs)

    expected = [
        "session_features_session_asia",
        "session_features_session_london",
        "session_features_session_newyork",
    ]
    for column in expected:
        assert column in result.columns
