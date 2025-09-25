"""
Complete test coverage for yaml_strategy.py - targeting 100% coverage.

This file covers all missing lines identified in the coverage report:
Lines 13-14, 88, 104, 148-152, 156-198, 215->218, 216->218, 223-228
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from trading_platform.strategy.yaml_strategy import (
    CompiledStrategy,
    _eval_predicate,
    _eval_rule_block,
    _series_for_operand,
    compile_strategy,
    load_strategy_config,
    validate_strategy_config,
)


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
                context_invalid = compiled_strategy.get_context(999)
                assert context_invalid == {}

                # Test with no feature df (should return empty dict)
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
                context_no_features = compiled_strategy_no_features.get_context(0)
                assert context_no_features == {}


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
