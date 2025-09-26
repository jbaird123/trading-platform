"""Comprehensive test coverage for strategy/features.py to achieve 100% coverage."""

from __future__ import annotations

import pandas as pd
import pytest
from trading_platform.strategy.features import _resolve_parameter, compute_features


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
