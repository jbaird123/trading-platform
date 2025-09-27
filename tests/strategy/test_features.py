"""
Consolidated tests for trading_platform.strategy.features.

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
    result = compute_features(df, specs, strategy_parameters=None)  # type: ignore[arg-type]

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
    # But str(None) = "None" is truthy, so it would create a "None" column
    # Let's check that we have the expected columns
    expected_new_columns = {
        "valid_ema",
        "None",
    }  # "None" gets created from missing name
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
        {"name": "test_unknown", "type": "UNKNOWN"},  # Unknown type -> pd.NA
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
    """Test _price_series fallback to close when invalid source (line 51)."""
    # DataFrame with OHLC data
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1020, 1.1040],
            "high": [1.1050, 1.1080, 1.1070],
            "low": [1.0990, 1.1010, 1.1030],
            "close": [1.1030, 1.1050, 1.1060],
        }
    )

    # Test with invalid source - should fallback to close (line 51)
    result = _price_series(df, "invalid_source")
    expected = pd.Series([1.1030, 1.1050, 1.1060], dtype="float64", name="close")
    pd.testing.assert_series_equal(result, expected)

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
    expected = pd.Series([0.0, 0.0], index=df.index, dtype="float64")
    pd.testing.assert_series_equal(result, expected)

    # Test with single bar
    df_single = pd.DataFrame({"high": [1.1050], "low": [1.1000], "close": [1.1025]})

    result_single = adx(df_single, length=14)
    expected_single = pd.Series([0.0], index=df_single.index, dtype="float64")
    pd.testing.assert_series_equal(result_single, expected_single)


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
    specs: list[dict[str, object]] = [
        {"name": "dc", "type": "DC", "params": {"length": 2}},
        {"name": "vwap", "type": "VWAP"},
        {"name": "unknown", "type": "UNKNOWN"},
    ]
    out = compute_features(df, specs)
    assert "dc_upper" in out and "dc_lower" in out
    assert "vwap" in out
    assert "unknown" in out  # present (pd.NA)


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
