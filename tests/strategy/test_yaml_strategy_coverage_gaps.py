"""
Test coverage gaps in YAML strategy parser module.

Targets specific missing lines in strategy/yaml_strategy.py to improve coverage.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from trading_platform.strategy.yaml_strategy import (
    _series_for_operand,
    compile_strategy,
    load_strategy_config,
    validate_strategy_config,
)


def test_validate_strategy_config_missing_jsonschema():
    """Test validate_strategy_config when jsonschema unavailable. Covers lines 13-14."""
    valid_config: dict[str, list[str]] = {"entry_signals": [], "exit_signals": []}

    # Mock jsonschema as None to simulate import error scenario
    with patch("trading_platform.strategy.yaml_strategy.jsonschema", None):
        # Should not raise exception when jsonschema is None
        validate_strategy_config(valid_config)


def test_validate_strategy_config_invalid_type():
    """Test validate_strategy_config with non-dict input. Covers line 34."""
    # Test with string input (invalid)
    with pytest.raises(ValueError, match="strategy must be an object"):
        validate_strategy_config("invalid_string_config")  # type: ignore[arg-type]

    # Test with list input (invalid)
    with pytest.raises(ValueError, match="strategy must be an object"):
        validate_strategy_config([1, 2, 3])  # type: ignore[arg-type]

    # Test with None input (invalid)
    with pytest.raises(ValueError, match="strategy must be an object"):
        validate_strategy_config(None)  # type: ignore[arg-type]


def test_validate_strategy_config_with_jsonschema():
    """Test validate_strategy_config with jsonschema. Covers lines 35->exit, 50-57."""
    valid_config = {
        "entry_signals": [
            {
                "rules": [
                    {"all_of": [{"condition": "gt", "left": "close", "right": 1.0}]}
                ]
            }
        ],
        "exit_signals": [],
    }

    # Test with valid jsonschema available
    with patch("trading_platform.strategy.yaml_strategy.jsonschema") as mock_jsonschema:
        mock_jsonschema.validate.return_value = None  # No exception = valid

        # Create a mock schema file
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.return_value = json.dumps({"type": "object"})

            # Should not raise exception
            validate_strategy_config(valid_config)

            # Verify jsonschema.validate was called
            mock_jsonschema.validate.assert_called_once()


def test_validate_strategy_config_schema_validation_error():
    """Test validate_strategy_config schema validation fails. Covers lines 44->46."""
    invalid_config = {"invalid_field": "value"}

    # Test with jsonschema validation error
    with patch("trading_platform.strategy.yaml_strategy.jsonschema") as mock_jsonschema:
        from jsonschema import ValidationError

        mock_jsonschema.ValidationError = ValidationError
        mock_jsonschema.validate.side_effect = ValidationError("Schema failed")

        # Create a mock schema file
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.return_value = json.dumps({"type": "object"})

            # Should raise ValueError
            with pytest.raises(ValueError, match="Strategy schema validation error"):
                validate_strategy_config(invalid_config)


def test_validate_strategy_config_missing_schema_file():
    """Test validate_strategy_config schema file read fails. Covers error handling."""
    valid_config = {
        "strategy_name": "test",
        "long_entry_rules": [],
        "long_exit_rules": [],
    }

    with patch("trading_platform.strategy.yaml_strategy.jsonschema"):
        # Simulate FileNotFoundError when reading schema - caught and handled
        with patch(
            "pathlib.Path.read_text", side_effect=FileNotFoundError("Schema not found")
        ):
            # Should raise the FileNotFoundError since there's no try/catch around it
            with pytest.raises(FileNotFoundError):
                validate_strategy_config(valid_config)


def test_load_strategy_config_from_dict():
    """Test load_strategy_config with dict input. Covers basic path."""
    config_dict: dict[str, list[str]] = {"entry_signals": [], "exit_signals": []}

    result = load_strategy_config(config_dict)

    assert result == config_dict


def test_load_strategy_config_from_file_path():
    """Test load_strategy_config from file path. Covers lines 88, 104."""
    config_data = {
        "entry_signals": [
            {
                "rules": [
                    {"all_of": [{"condition": "gt", "left": "close", "right": 1.1000}]}
                ]
            }
        ],
        "exit_signals": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        json_path = Path(f.name)

    try:
        # Test loading from Path object
        result = load_strategy_config(json_path)
        assert result == config_data

        # Test loading from string path
        result = load_strategy_config(str(json_path))
        assert result == config_data

    finally:
        # Clean up
        json_path.unlink(missing_ok=True)


def test_series_for_operand_numeric():
    """Test _series_for_operand with numeric values. Covers lines 148-152."""
    # Create sample dataframe
    df = pd.DataFrame(
        {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
    )

    # Test with integer
    result = _series_for_operand(df, 5)
    expected = pd.Series([5.0, 5.0, 5.0], index=df.index)
    pd.testing.assert_series_equal(result, expected)

    # Test with float
    result = _series_for_operand(df, 2.5)
    expected = pd.Series([2.5, 2.5, 2.5], index=df.index)
    pd.testing.assert_series_equal(result, expected)


def test_series_for_operand_string():
    """Test _series_for_operand with string column names. Covers lines 58-65."""
    # Create sample dataframe with multiple columns
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2],
            "high": [1.05, 1.15, 1.25],
            "low": [0.95, 1.05, 1.15],
            "close": [1.02, 1.12, 1.22],
            "volume": [100.0, 200.0, 300.0],  # Use float to match expected dtype
        },
        index=pd.date_range("2024-01-01", periods=3),
    )

    # Test with valid column name
    result = _series_for_operand(df, "close")
    expected = pd.Series(df["close"], dtype="float64")
    pd.testing.assert_series_equal(result, expected)

    # Test with another valid column name
    result = _series_for_operand(df, "volume")
    expected = pd.Series(df["volume"], dtype="float64")
    pd.testing.assert_series_equal(result, expected)

    # Test with invalid column name - should return zeros
    result = _series_for_operand(df, "invalid_column")
    expected = pd.Series([0.0] * len(df), index=df.index)
    pd.testing.assert_series_equal(result, expected)

    # Test with dict ref operand
    result = _series_for_operand(df, {"ref": "close"})
    expected = pd.Series(df["close"], dtype="float64")
    pd.testing.assert_series_equal(result, expected)


def test_compile_strategy_edge_cases():
    """Test compile_strategy with edge cases. Covers lines 233-270."""
    # Simple strategy config
    strategy_config = {
        "strategy_name": "TestStrategy",
        "long_entry_rules": [
            {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
        ],
        "long_exit_rules": [],
        "parameters": {"param1": 1.5},
    }

    # Mock the validation and compilation process
    with patch(
        "trading_platform.strategy.yaml_strategy.validate_strategy_config"
    ) as mock_validate:
        mock_validate.return_value = None

        # Test compile_strategy - takes only one argument (cfg)
        compiled = compile_strategy(strategy_config)

        # Should return a CompiledStrategy object
        assert compiled is not None
        assert hasattr(compiled, "name")
        assert compiled.name == "TestStrategy"

        # Verify validation was called
        mock_validate.assert_called_once_with(strategy_config)


def test_compile_strategy_with_ai_inference():
    """Test compile_strategy with AI filter configuration. Covers AI filter logic."""
    strategy_config = {
        "strategy_name": "AIStrategy",
        "long_entry_rules": [],
        "long_exit_rules": [],
        "ai_filter": {
            "enabled": True,
            "confidence_threshold": 0.7,
            "input_features": ["close", "volume"],
        },
    }

    with patch(
        "trading_platform.strategy.yaml_strategy.validate_strategy_config"
    ) as mock_validate, patch(
        "trading_platform.strategy.yaml_strategy.AIInferenceClient"
    ) as mock_ai_client:
        mock_validate.return_value = None
        mock_ai_client.return_value = Mock()

        # Test compile_strategy with AI filter
        compiled = compile_strategy(strategy_config)

        assert compiled is not None
        assert hasattr(compiled, "ai_filter_enabled")
        assert compiled.ai_confidence_threshold == 0.7


def test_compile_strategy_parameter_defaults():
    """Test compile_strategy with parameter defaults and edge cases."""
    # Test with minimal config - should use defaults
    strategy_config: dict[str, list[str]] = {}

    with patch(
        "trading_platform.strategy.yaml_strategy.validate_strategy_config"
    ) as mock_validate:
        mock_validate.return_value = None

        # Test compile_strategy with minimal config
        compiled = compile_strategy(strategy_config)

        assert compiled is not None
        assert compiled.name == "Strategy"  # Default name
        assert compiled.overlays == []
        assert compiled.features == []
        assert compiled.parameters == {}
        assert compiled.slope_filter is False
        assert compiled.slope_feature == "ema_slow"


def test_compile_strategy_invalid_parameters():
    """Test compile_strategy with non-dict parameters. Covers parameter validation."""
    strategy_config = {
        "strategy_name": "TestStrategy",
        "parameters": "invalid_string_params",  # Should be dict
    }

    with patch(
        "trading_platform.strategy.yaml_strategy.validate_strategy_config"
    ) as mock_validate:
        mock_validate.return_value = None

        # Should handle invalid parameters gracefully by using empty dict
        compiled = compile_strategy(strategy_config)

        assert compiled is not None
        assert compiled.parameters == {}  # Should default to empty dict
