"""
Consolidated tests for trading_platform.strategy.yaml_strategy.

Combined 100% coverage suite, gap fillers, full coverage, and parser smoke tests.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from trading_platform.ai.inference_client import AIInferenceClient
from trading_platform.strategy import yaml_strategy as ys
from trading_platform.strategy.yaml_strategy import (
    CompiledStrategy,
    _eval_predicate,
    _eval_rule_block,
    _series_for_operand,
    compile_strategy,
    load_strategy_config,
    validate_strategy_config,
)

# --- test_yaml_strategy_100_coverage.py ---

"""
Complete test coverage for yaml_strategy.py - targeting 100% coverage.

This file covers all missing lines identified in the coverage report:
Lines 13-14, 88, 104, 148-152, 156-198, 215->218, 216->218, 223-228
"""


class TestJsonschemaImportFallback:
    """Test lines 13-14: jsonschema import fallback."""

    def test_jsonschema_none_import_fallback(self):
        """Test when jsonschema import fails, it's set to None - covers lines 13-14."""
        # This is already covered by test_validate_strategy_config_missing_jsonschema
        # in test_yaml_strategy_coverage_gaps.py, so we just need a simple test
        # to ensure we can handle the case when jsonschema is None
        with patch("trading_platform.strategy.yaml_strategy.jsonschema", None):
            config = {"strategy_name": "test"}
            # Should not raise when jsonschema is None
            validate_strategy_config(config)


class TestEvalPredicateEdgeCases:
    """Test line 88: _eval_predicate fallback condition."""

    def test_eval_predicate_unknown_condition(self):
        """Test _eval_predicate with unsupported condition - covers line 88."""
        df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0], "sma": [1.1, 1.9, 2.8]},
            index=pd.date_range("2024-01-01", periods=3),
        )

        # Test unsupported condition - should return all False
        predicate = {
            "condition": "unsupported_condition",
            "left": "close",
            "right": "sma",
        }

        result = _eval_predicate(df, predicate)
        expected = pd.Series([False, False, False], index=df.index)
        pd.testing.assert_series_equal(result, expected)


class TestEvalRuleBlockFallback:
    """Test line 104: _eval_rule_block fallback return."""

    def test_eval_rule_block_no_all_of_or_any_of(self):
        """Test _eval_rule_block with neither all_of nor any_of - covers line 104."""
        df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0]}, index=pd.date_range("2024-01-01", periods=3)
        )

        # Block with neither all_of nor any_of
        block = {"some_other_key": "value"}

        result = _eval_rule_block(df, block)
        expected = pd.Series([False, False, False], index=df.index)
        pd.testing.assert_series_equal(result, expected)


class TestSlopeFilterLogic:
    """Test lines 148-152: slope filter logic in generate_signals."""

    def test_generate_signals_with_slope_filter_enabled(self):
        """Test generate_signals with slope filter enabled - covers lines 148-152."""
        # Create test data
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3, 1.0],
                "high": [1.05, 1.15, 1.25, 1.35, 1.05],
                "low": [0.95, 1.05, 1.15, 1.25, 0.95],
                "close": [1.0, 1.1, 1.2, 1.3, 1.0],
                "volume": [100, 200, 300, 400, 500],
            },
            index=pd.date_range("2024-01-01", periods=5),
        )

        # Strategy config with slope filter
        strategy_config = {
            "strategy_name": "SlopeFilterStrategy",
            "features": [
                {
                    "name": "ema_slow",
                    "type": "EMA",
                    "params": {"length": 3},
                    "source": "close",
                }
            ],
            "long_entry_rules": [
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            "long_exit_rules": [
                {"all_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
            ],
            "parameters": {"slope_filter": True, "slope_feature": "ema_slow"},
        }

        with patch("trading_platform.strategy.yaml_strategy.validate_strategy_config"):
            with patch(
                "trading_platform.strategy.features.compute_features"
            ) as mock_compute:
                # Mock feature computation to return df with ema_slow
                feature_df = df.copy()
                feature_df["ema_slow"] = [
                    1.0,
                    1.05,
                    1.1,
                    1.15,
                    1.0,
                ]  # Slope up then down
                mock_compute.return_value = feature_df

                compiled_strategy = compile_strategy(strategy_config)
                signals = compiled_strategy.generate_signals(df)

                # Should generate signals based on slope filter
                assert isinstance(signals, pd.Series)
                assert len(signals) == len(df)

    def test_generate_signals_slope_filter_missing_column(self):
        """Test slope filter when slope_feature column doesn't exist."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        strategy_config = {
            "strategy_name": "MissingSlopeStrategy",
            "features": [],
            "long_entry_rules": [
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            "long_exit_rules": [],
            "parameters": {"slope_filter": True, "slope_feature": "missing_column"},
        }

        with patch("trading_platform.strategy.yaml_strategy.validate_strategy_config"):
            with patch(
                "trading_platform.strategy.features.compute_features"
            ) as mock_compute:
                # Mock feature computation to return df without slope feature
                mock_compute.return_value = df.copy()

                compiled_strategy = compile_strategy(strategy_config)
                signals = compiled_strategy.generate_signals(df)

                # Should still work without the slope column
                assert isinstance(signals, pd.Series)


class TestAIFilterLogic:
    """Test lines 156-198: AI inference filter logic."""

    def test_generate_signals_ai_filter_enabled_with_predictions(self):
        """Test AI filter with successful predictions - covers lines 156-198."""
        # Create CompiledStrategy directly to test the generate_signals method
        mock_ai_client = Mock()
        mock_ai_client.predict.return_value = [
            {"prediction": "long", "confidence": 0.8},
            {"prediction": "long", "confidence": 0.5},  # Below threshold
            {"prediction": "short", "confidence": 0.7},
            {"prediction": "flat", "confidence": 0.9},
        ]

        compiled_strategy = CompiledStrategy(
            name="AIFilterStrategy",
            overlays=[],
            features=[],
            long_entry_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            long_exit_blocks=[],
            short_entry_blocks=[
                {"all_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
            ],
            short_exit_blocks=[],
            parameters={},
            ai_filter_enabled=True,
            ai_inference_client=mock_ai_client,
            ai_confidence_threshold=0.6,
            ai_input_features=["close", "volume"],
        )

        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2, 1.3], "volume": [100, 200, 300, 400]},
            index=pd.date_range("2024-01-01", periods=4),
        )

        with patch(
            "trading_platform.strategy.features.compute_features"
        ) as mock_compute:
            mock_compute.return_value = df.copy()

            signals = compiled_strategy.generate_signals(df)

            # Verify AI client was called
            mock_ai_client.predict.assert_called_once()
            assert isinstance(signals, pd.Series)

    def test_generate_signals_ai_filter_missing_features(self):
        """Test AI filter with missing input features - covers warning path."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        strategy_config = {
            "strategy_name": "AIFilterMissingFeatures",
            "features": [],
            "long_entry_rules": [
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            "long_exit_rules": [],
            "ai_filter": {
                "enabled": True,
                "confidence_threshold": 0.6,
                "input_features": [
                    "close",
                    "missing_feature",
                ],  # missing_feature doesn't exist
            },
        }

        with patch("trading_platform.strategy.yaml_strategy.validate_strategy_config"):
            with patch(
                "trading_platform.strategy.yaml_strategy.jsonschema", spec=object()
            ):
                with patch(
                    "trading_platform.strategy.yaml_strategy.AIInferenceClient"
                ) as mock_ai_client_class:
                    mock_ai_client = Mock()
                    mock_ai_client_class.return_value = mock_ai_client

                    with patch(
                        "trading_platform.strategy.features.compute_features"
                    ) as mock_compute:
                        mock_compute.return_value = df.copy()

                        with patch(
                            "trading_platform.strategy.yaml_strategy.logger"
                        ) as mock_logger:
                            compiled_strategy = compile_strategy(strategy_config)
                            signals = compiled_strategy.generate_signals(df)

                            # Should log warning about missing features
                            mock_logger.warning.assert_called()
                            assert isinstance(signals, pd.Series)

    def test_generate_signals_ai_filter_no_predictions(self):
        """Test AI filter when no predictions returned - covers else branch."""
        mock_ai_client = Mock()
        mock_ai_client.predict.return_value = []  # No predictions

        compiled_strategy = CompiledStrategy(
            name="AIFilterNoPredictions",
            overlays=[],
            features=[],
            long_entry_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            long_exit_blocks=[],
            short_entry_blocks=[],
            short_exit_blocks=[],
            parameters={},
            ai_filter_enabled=True,
            ai_inference_client=mock_ai_client,
            ai_confidence_threshold=0.6,
            ai_input_features=["close"],
        )

        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        with patch(
            "trading_platform.strategy.features.compute_features"
        ) as mock_compute:
            mock_compute.return_value = df.copy()

            with patch("trading_platform.strategy.yaml_strategy.logger") as mock_logger:
                compiled_strategy.generate_signals(df)

                # Should log warning about no predictions
                mock_logger.warning.assert_called_with(
                    "AI inference returned no predictions. Skipping AI filter."
                )

    def test_generate_signals_ai_filter_exception(self):
        """Test AI filter when exception occurs - covers except branch."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        strategy_config = {
            "strategy_name": "AIFilterException",
            "features": [],
            "long_entry_rules": [
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            "long_exit_rules": [],
            "ai_filter": {
                "enabled": True,
                "confidence_threshold": 0.6,
                "input_features": ["close"],
            },
        }

        with patch("trading_platform.strategy.yaml_strategy.validate_strategy_config"):
            with patch(
                "trading_platform.strategy.yaml_strategy.jsonschema", spec=object()
            ):
                with patch(
                    "trading_platform.strategy.yaml_strategy.AIInferenceClient"
                ) as mock_ai_client_class:
                    mock_ai_client = Mock()
                    mock_ai_client.predict.side_effect = RuntimeError(
                        "AI service unavailable"
                    )
                    mock_ai_client_class.return_value = mock_ai_client

                    with patch(
                        "trading_platform.strategy.features.compute_features"
                    ) as mock_compute:
                        mock_compute.return_value = df.copy()

                        with patch(
                            "trading_platform.strategy.yaml_strategy.logger"
                        ) as mock_logger:
                            compiled_strategy = compile_strategy(strategy_config)
                            signals = compiled_strategy.generate_signals(df)

                            # Should log error about AI exception
                            mock_logger.error.assert_called()
                            assert isinstance(signals, pd.Series)

    def test_generate_signals_ai_filter_no_input_features(self):
        """Test AI filter when ai_input_features is None - covers lines 159->171."""
        mock_ai_client = Mock()
        mock_ai_client.predict.return_value = [
            {"prediction": "long", "confidence": 0.8}
        ]

        compiled_strategy = CompiledStrategy(
            name="AIFilterNoFeatures",
            overlays=[],
            features=[],
            long_entry_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            long_exit_blocks=[],
            short_entry_blocks=[],
            short_exit_blocks=[],
            parameters={},
            ai_filter_enabled=True,
            ai_inference_client=mock_ai_client,
            ai_confidence_threshold=0.6,
            ai_input_features=None,  # This should trigger the branch at line 159
        )

        df = pd.DataFrame(
            {"close": [1.1]}, index=pd.date_range("2024-01-01", periods=1)
        )

        with patch(
            "trading_platform.strategy.features.compute_features"
        ) as mock_compute:
            mock_compute.return_value = df.copy()

            signals = compiled_strategy.generate_signals(df)

            # AI client should still be called with full DataFrame
            mock_ai_client.predict.assert_called_once()
            assert isinstance(signals, pd.Series)


class TestSignalStateMachine:
    """Test lines 215-228: signal state machine logic and get_context method."""

    def test_signal_state_transitions_short_exit(self):
        """Test short state exit transition - covers line 215->218."""
        compiled_strategy = CompiledStrategy(
            name="ShortExitStrategy",
            overlays=[],
            features=[],
            long_entry_blocks=[],
            long_exit_blocks=[],
            short_entry_blocks=[
                {"all_of": [{"condition": "is_below", "left": "close", "right": 0.9}]}
            ],
            short_exit_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.1}]}
            ],
            parameters={},
        )

        # Create data that triggers: flat -> short -> flat
        df = pd.DataFrame(
            {
                "close": [0.8, 0.85, 1.2]  # Below 0.9, then above 1.1
            },
            index=pd.date_range("2024-01-01", periods=3),
        )

        with patch(
            "trading_platform.strategy.features.compute_features"
        ) as mock_compute:
            mock_compute.return_value = df.copy()

            signals = compiled_strategy.generate_signals(df)

            # Should transition: flat -> short -> flat
            assert signals.iloc[0] == "short"  # Enter short
            assert signals.iloc[2] == "flat"  # Exit short

    def test_signal_state_transitions_all_states(self):
        """Test all signal state transitions - covers lines 215-228."""
        compiled_strategy = CompiledStrategy(
            name="AllStatesStrategy",
            overlays=[],
            features=[],
            long_entry_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.1}]}
            ],
            long_exit_blocks=[
                {"all_of": [{"condition": "is_below", "left": "close", "right": 1.0}]}
            ],
            short_entry_blocks=[
                {"all_of": [{"condition": "is_below", "left": "close", "right": 0.9}]}
            ],
            short_exit_blocks=[
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            parameters={},
        )

        # Create data that triggers multiple state transitions
        df = pd.DataFrame(
            {
                "close": [
                    1.0,
                    1.2,
                    0.8,
                    0.7,
                    1.1,
                    0.95,
                ]  # flat->long->flat->short->flat
            },
            index=pd.date_range("2024-01-01", periods=6),
        )

        with patch(
            "trading_platform.strategy.features.compute_features"
        ) as mock_compute:
            mock_compute.return_value = df.copy()

            signals = compiled_strategy.generate_signals(df)

            # Check that we get proper state transitions
            assert isinstance(signals, pd.Series)
            assert len(signals) == len(df)

            # All states should be one of: 'flat', 'long', 'short'
            valid_states = {"flat", "long", "short"}
            assert all(state in valid_states for state in signals.values)

    def test_get_context_method(self):
        """Test get_context method - covers lines 223-228."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        strategy_config = {
            "strategy_name": "ContextStrategy",
            "features": [
                {
                    "name": "sma",
                    "type": "SMA",
                    "params": {"length": 2},
                    "source": "close",
                }
            ],
            "long_entry_rules": [
                {"all_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
            "long_exit_rules": [],
        }

        with patch("trading_platform.strategy.yaml_strategy.validate_strategy_config"):
            with patch(
                "trading_platform.strategy.features.compute_features"
            ) as mock_compute:
                feature_df = df.copy()
                feature_df["sma"] = [1.0, 1.05, 1.1]
                mock_compute.return_value = feature_df

                compiled_strategy = compile_strategy(strategy_config)

                # Generate signals first to populate _feature_df
                compiled_strategy.generate_signals(df)

                # Test get_context method
                context = compiled_strategy.get_context(0)
                assert isinstance(context, dict)
                assert "sma" in context

                # Test with invalid index
                with pytest.raises(IndexError):
                    compiled_strategy.get_context(999)

                # Test with no feature df (should raise IndexError)
                compiled_strategy_no_features = CompiledStrategy(
                    name="test",
                    overlays=[],
                    features=[],
                    long_entry_blocks=[],
                    long_exit_blocks=[],
                    short_entry_blocks=[],
                    short_exit_blocks=[],
                    parameters={},
                )
                with pytest.raises(IndexError):
                    compiled_strategy_no_features.get_context(0)


class TestLoadStrategyFromFile:
    """Test lines 50-57: load_strategy_config from file operations."""

    def test_load_strategy_config_file_operations(self):
        """Test load_strategy_config file reading - covers lines 50-57."""
        config_data = {"strategy_name": "FileStrategy", "features": []}

        # Test with temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            # Test loading from string path (covers line 50)
            result = load_strategy_config(str(temp_path))
            assert result == config_data

            # Test loading from Path object (covers line 50)
            result = load_strategy_config(temp_path)
            assert result == config_data

        finally:
            temp_path.unlink(missing_ok=True)


class TestSeriesForOperandEdgeCases:
    """Test edge cases in _series_for_operand function."""

    def test_series_for_operand_dict_without_ref(self):
        """Test _series_for_operand with dict that doesn't have 'ref' key."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        # Dict without 'ref' key should return zeros
        result = _series_for_operand(df, {"other_key": "value"})
        expected = pd.Series([0.0, 0.0, 0.0], index=df.index)
        pd.testing.assert_series_equal(result, expected)

    def test_series_for_operand_other_types(self):
        """Test _series_for_operand with other unsupported types."""
        df = pd.DataFrame(
            {"close": [1.0, 1.1, 1.2]}, index=pd.date_range("2024-01-01", periods=3)
        )

        # List should return zeros (unsupported type)
        result = _series_for_operand(df, [1, 2, 3])
        expected = pd.Series([0.0, 0.0, 0.0], index=df.index)
        pd.testing.assert_series_equal(result, expected)

        # None should return zeros
        result = _series_for_operand(df, None)
        expected = pd.Series([0.0, 0.0, 0.0], index=df.index)
        pd.testing.assert_series_equal(result, expected)


# --- test_yaml_strategy_coverage_gaps.py ---

"""
Test coverage gaps in YAML strategy parser module.

Targets specific missing lines in strategy/yaml_strategy.py to improve coverage.
"""


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


# --- test_yaml_strategy_full_coverage.py ---


def _base_config() -> dict[str, Any]:
    return {
        "strategy_name": "Test",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
    }


def test_validate_strategy_config_jsonschema_failure(monkeypatch):
    cfg = _base_config()

    class DummyValidationError(Exception):
        def __init__(self, msg: str) -> None:
            super().__init__(msg)
            self.message = msg

    def fake_validate(config: dict[str, Any], schema: dict[str, Any]) -> None:
        raise DummyValidationError("bad field")

    fake_jsonschema = SimpleNamespace(
        validate=fake_validate, ValidationError=DummyValidationError
    )
    monkeypatch.setattr(ys, "jsonschema", fake_jsonschema)

    with pytest.raises(ValueError, match="bad field"):
        ys.validate_strategy_config(cfg)


def test_validate_strategy_config_without_jsonschema(monkeypatch):
    cfg = _base_config()
    monkeypatch.setattr(ys, "jsonschema", None)
    ys.validate_strategy_config(cfg)


def test_load_strategy_config_from_path(tmp_path):
    cfg = {"strategy_name": "FileStrategy"}
    file_path = tmp_path / "cfg.json"
    file_path.write_text(json.dumps(cfg))
    loaded = ys.load_strategy_config(file_path)
    assert loaded == cfg


def test_series_for_operand_variants():
    df = pd.DataFrame({"close": [1, 2], "feat": [3, 4]})
    assert list(ys._series_for_operand(df, 5.0)) == [5.0, 5.0]
    assert list(ys._series_for_operand(df, "close")) == [1.0, 2.0]
    assert list(ys._series_for_operand(df, {"ref": "feat"})) == [3.0, 4.0]
    assert list(ys._series_for_operand(df, {"bad": 1})) == [0.0, 0.0]


def test_eval_predicate_all_conditions():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]})
    above = ys._eval_predicate(df, {"condition": "is_above", "left": "b", "right": "a"})
    below = ys._eval_predicate(df, {"condition": "is_below", "left": "a", "right": "b"})
    cross_up = ys._eval_predicate(
        df, {"condition": "cross_above", "left": "a", "right": "b"}
    )
    cross_down = ys._eval_predicate(
        df, {"condition": "cross_below", "left": "b", "right": "a"}
    )
    default = ys._eval_predicate(df, {"condition": "unknown"})
    assert list(above) == [True, False, False]
    assert list(below) == [True, False, False]
    assert list(cross_up) == [False, False, True]
    assert list(cross_down) == [False, False, True]
    assert not default.any()


def test_eval_rule_block_branches():
    df = pd.DataFrame({"x": [2, 3, 4], "y": [0, 1, 2]})
    all_block = {"all_of": [{"condition": "is_above", "left": "x", "right": "y"}]}
    any_block = {"any_of": [{"condition": "is_below", "left": "y", "right": "x"}]}
    none_block: dict[str, Any] = {}
    assert ys._eval_rule_block(df, all_block).all()
    assert ys._eval_rule_block(df, any_block).iloc[0]
    assert not ys._eval_rule_block(df, none_block).any()


class DummyAIClient(AIInferenceClient):
    def __init__(self, responses: list[dict[str, Any]] | Exception):
        super().__init__()
        self._responses = responses
        self.calls = 0

    def predict(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        self.calls += 1
        if isinstance(self._responses, Exception):
            raise self._responses
        return self._responses


def _patch_features(monkeypatch, frame: pd.DataFrame) -> None:
    def fake_features(
        df: pd.DataFrame,
        feats: list[dict],
        params: dict,
    ) -> pd.DataFrame:
        return frame.reset_index(drop=True).copy()

    monkeypatch.setattr(ys, "compute_features", fake_features)


def test_compiled_strategy_generate_signals_basic(monkeypatch):
    base = pd.DataFrame({"close": [1, 2, 1], "feat": [0, 1, 0]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="basic",
        overlays=[],
        features=[{"name": "feat"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        long_exit_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
        ],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["flat", "long", "flat"]
    assert strat.get_context(1) == {"feat": 1}
    with pytest.raises(IndexError):
        strat.get_context(10)


def test_compiled_strategy_short_exit_branch(monkeypatch):
    base = pd.DataFrame({"close": [12, 8, 7, 11]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="short-exit",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": "close",
                        "right": 9,
                    }
                ]
            }
        ],
        short_exit_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": "close",
                        "right": 10,
                    }
                ]
            }
        ],
        parameters={},
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["flat", "short", "short", "flat"]


def test_compiled_strategy_short_exit_never_triggers(monkeypatch):
    base = pd.DataFrame({"close": [12, 8, 7, 6]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="short-stick",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": "close",
                        "right": 9,
                    }
                ]
            }
        ],
        short_exit_blocks=[],
        parameters={},
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["flat", "short", "short", "short"]


def test_compiled_strategy_slope_and_ai_filter(monkeypatch):
    base = pd.DataFrame(
        {
            "close": [1.0, 2.0, 3.0, 4.0],
            "ema_slow": [1.0, 1.1, 1.2, 1.3],
            "fast": [0.0, 1.0, 0.0, 1.0],
        }
    )
    _patch_features(monkeypatch, base)
    predictions = [
        {"prediction": "long", "confidence": 0.8},
        {"prediction": "long", "confidence": 0.2},
        {"prediction": "short", "confidence": 0.9},
        {"prediction": "flat", "confidence": 0.9},
    ]
    ai_client = DummyAIClient(predictions)
    strat = ys.CompiledStrategy(
        name="ai",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
        ],
        long_exit_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 3.5}]}
        ],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 3.5}]}
        ],
        short_exit_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 3.5}]}
        ],
        parameters={"slope_filter": True, "slope_feature": "ema_slow"},
        slope_filter=True,
        slope_feature="ema_slow",
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=[],
    )
    sig = strat.generate_signals(base)
    values = list(sig)
    assert ai_client.calls == 1
    assert len(values) == 4
    assert set(values).issubset({"flat", "long", "short"})


def test_compiled_strategy_slope_filter_missing_column(monkeypatch):
    base = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="slope-missing",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 5}]}
        ],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={"slope_filter": True, "slope_feature": "ema_missing"},
        slope_filter=True,
        slope_feature="ema_missing",
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["long", "flat", "long"]


def test_compiled_strategy_ai_filter_missing_features(monkeypatch, caplog):
    base = pd.DataFrame({"close": [1, 2], "fast": [1, 1]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="missing-ai",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["missing"],
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["long", "long"]
    assert "Missing AI input features" in caplog.text


def test_compiled_strategy_ai_filter_exception(monkeypatch, caplog):
    base = pd.DataFrame({"close": [1, 2]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="ai-error",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient(Exception("boom")),
        ai_confidence_threshold=0.5,
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["long", "long"]
    assert "Error during AI inference" in caplog.text


def test_compiled_strategy_ai_filter_with_inputs(monkeypatch):
    base = pd.DataFrame({"close": [1, 2], "fast": [0.5, 0.6]})
    _patch_features(monkeypatch, base)
    original_getitem = pd.DataFrame.__getitem__

    def safe_getitem(self: pd.DataFrame, key):
        if isinstance(key, list):
            data = {col: original_getitem(self, col) for col in key}
            return pd.DataFrame(data, index=self.index)
        return original_getitem(self, key)

    monkeypatch.setattr(pd.DataFrame, "__getitem__", safe_getitem)
    ai_client = DummyAIClient(
        [
            {"prediction": "long", "confidence": 0.9},
            {"prediction": "flat", "confidence": 0.9},
        ]
    )
    strat = ys.CompiledStrategy(
        name="ai-inputs",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    sig = strat.generate_signals(base)
    assert ai_client.calls == 1
    assert list(sig) == ["long", "long"]


def test_compile_strategy_ai_enabled(monkeypatch):
    cfg = {
        "strategy_name": "compile",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
        "features": [],
        "parameters": {"slope_filter": True, "slope_feature": "custom"},
        "ai_filter": {
            "enabled": True,
            "confidence_threshold": 0.3,
            "input_features": ["fast"],
        },
    }

    class DummyValidationError(Exception):
        pass

    fake_jsonschema = SimpleNamespace(
        validate=lambda cfg, schema: None,
        ValidationError=DummyValidationError,
    )
    monkeypatch.setattr(ys, "jsonschema", fake_jsonschema)
    strat = ys.compile_strategy(cfg)
    assert strat.slope_filter is True
    assert strat.slope_feature == "custom"
    assert strat.ai_filter_enabled is True
    assert strat.ai_inference_client is not None


def test_compile_strategy_ai_disabled_without_jsonschema(monkeypatch):
    cfg = {
        "strategy_name": "no-ai",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
        "ai_filter": {"enabled": True},
        "parameters": "not-a-dict",
    }
    monkeypatch.setattr(ys, "jsonschema", None)
    strat = ys.compile_strategy(cfg)
    assert strat.ai_filter_enabled is False
    assert strat.parameters == {}


def test_reload_without_jsonschema(monkeypatch):
    import builtins
    import importlib

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "jsonschema":
            raise ImportError
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    module = importlib.reload(ys)
    assert module.jsonschema is None
    monkeypatch.setattr(builtins, "__import__", original_import)
    module = importlib.reload(module)
    globals()["ys"] = module
    target = globals()["ys"]

    df = pd.DataFrame({"close": [0.0, 0.2, 1.0], "fast": [1.0, 1.5, 2.0]})
    monkeypatch.setattr(
        target,
        "compute_features",
        lambda frame, feats, params: df.copy(),
    )
    ai_client = DummyAIClient(
        [
            {"prediction": "short", "confidence": 0.9},
            {"prediction": "short", "confidence": 0.9},
            {"prediction": "flat", "confidence": 0.9},
        ]
    )
    strat = target.CompiledStrategy(
        name="reload",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
        short_exit_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
        ],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    strat.generate_signals(df)
    target._series_for_operand(df, "fast")
    target._series_for_operand(df, "missing")
    no_ai = target.CompiledStrategy(
        name="branch-no-ai",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    no_ai.generate_signals(df)
    half_ai = target.CompiledStrategy(
        name="branch-half",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=None,
    )
    half_ai.generate_signals(df)

    empty_ai = target.CompiledStrategy(
        name="branch-empty",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": -1}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    empty_ai.generate_signals(df)

    missing_ai = target.CompiledStrategy(
        name="branch-missing",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": -1}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["missing"],
    )
    missing_ai.generate_signals(df)


def test_load_strategy_config_returns_dict():
    cfg = {"name": "inline"}
    out = ys.load_strategy_config(cfg)
    assert out is cfg


# --- test_yaml_strategy_parser.py ---

# Validates: [SE-3.5.3]


def test_yaml_strategy_compile_and_signals_is_above_below():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "overlays": ["ema_fast", "ema_slow"],
        "features": [],
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
        ],
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 2.0, 1.0],
            "high": [1.0, 2.0, 3.0, 2.0, 1.0],
            "low": [1.0, 2.0, 3.0, 2.0, 1.0],
            "close": [1.0, 2.0, 3.0, 2.0, 1.0],
            "volume": [1, 1, 1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(5)],
    )
    sig = strat.generate_signals(df)
    # Expect: flat at 1.0, enter long at 2.0, remain long at 3.0 and 2.0, exit at 1.0
    assert list(sig) == ["flat", "long", "long", "long", "flat"]


def test_yaml_strategy_cross_above_below():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "features": [
            {"name": "ema_fast", "type": "EMA", "params": {"length": 2}},
            {"name": "ema_slow", "type": "EMA", "params": {"length": 4}},
        ],
        "long_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "cross_below",
                        "left": {"ref": "ema_fast"},
                        "right": {"ref": "ema_slow"},
                    }
                ]
            }
        ],
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1, 1, 1, 1, 1],
            "high": [1, 1, 1, 1, 1],
            "low": [1, 1, 1, 1, 1],
            "close": [100, 101, 102, 101, 100],
            "volume": [1, 1, 1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(5)],
    )
    sig = strat.generate_signals(df)
    # Signals will be flat until indicators are warm
    assert sig.iloc[-1] == "flat" or sig.iloc[-1] == "short"


def test_yaml_strategy_all_of_and_short_side():
    cfg = {
        "strategy_name": "TestStrat",
        "parameters": {},
        "short_entry_rules": [
            {
                "all_of": [
                    {"condition": "is_below", "left": "close", "right": 1.5},
                    {"condition": "is_above", "left": "close", "right": 0},
                ]
            }
        ],
        "short_exit_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
    }
    strat = compile_strategy(cfg)
    df = pd.DataFrame(
        {
            "open": [1, 2, 1],
            "high": [1, 2, 1],
            "low": [1, 2, 1],
            "close": [1, 2, 1],
            "volume": [1, 1, 1],
        },
        index=[datetime(2024, 1, 1, i) for i in range(3)],
    )
    sig = strat.generate_signals(df)
    # flat, exit short, enter short
    assert list(sig) == ["short", "flat", "short"]
