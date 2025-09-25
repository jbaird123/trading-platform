import logging
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from trading_platform.strategy.ai_strategy import AIStrategy


class TestAIStrategy:
    """Test cases for AIStrategy class."""

    def test_init_with_defaults(self):
        """Test AIStrategy.__init__() with default parameters."""
        strategy = AIStrategy()

        assert strategy.model_name == "default_model"
        assert strategy.threshold == 0.5
        assert strategy.inference_client is not None
        assert strategy.inference_client.base_url == "http://localhost:8000"
        assert strategy.inference_client.timeout == 5.0
        assert strategy.inference_client.retries == 3
        assert strategy.inference_client.backoff_factor == 0.5

    def test_init_with_custom_parameters(self):
        """Test AIStrategy.__init__() with custom parameters."""
        strategy = AIStrategy(
            model_name="custom_model",
            threshold=0.7,
            base_url="http://api.example.com",
            timeout=10.0,
            retries=5,
            backoff_factor=1.0,
        )

        assert strategy.model_name == "custom_model"
        assert strategy.threshold == 0.7
        assert strategy.inference_client.base_url == "http://api.example.com"
        assert strategy.inference_client.timeout == 10.0
        assert strategy.inference_client.retries == 5
        assert strategy.inference_client.backoff_factor == 1.0

    def test_init_with_kwargs(self):
        """Ensure AIStrategy rejects extra kwargs not supported by BaseStrategy."""
        # BaseStrategy doesn't have __init__ method, so kwargs should be rejected
        with pytest.raises(TypeError, match="takes exactly one argument"):
            AIStrategy(name="TestAI", some_param="test_value")

    def test_preprocess_data(self):
        """Test _preprocess_data() method with OHLCV DataFrame."""
        strategy = AIStrategy()

        # Create sample OHLCV data
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2],
                "high": [1.05, 1.15, 1.25],
                "low": [0.95, 1.05, 1.15],
                "close": [1.02, 1.12, 1.22],
                "volume": [100, 200, 150],
            }
        )

        result = strategy._preprocess_data(data)

        # Should return a copy of the data
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, data)
        # Ensure it's a copy, not the same object
        assert result is not data

    def test_interpret_predictions_empty_list(self):
        """Test _interpret_predictions() with empty predictions list."""
        strategy = AIStrategy()

        predictions: List[Dict[str, Any]] = []
        result = strategy._interpret_predictions(predictions)

        assert isinstance(result, pd.Series)
        assert len(result) == 0
        assert result.dtype == "object"

    def test_interpret_predictions_long_signals(self):
        """Test _interpret_predictions() with long signal predictions."""
        strategy = AIStrategy(threshold=0.6)

        predictions = [
            {"long_prob": 0.8, "short_prob": 0.2},
            {"long_prob": 0.7, "short_prob": 0.1},
            {"long_prob": 0.3, "short_prob": 0.4},
        ]

        result = strategy._interpret_predictions(predictions)

        assert len(result) == 3
        assert result.iloc[0] == "long"  # 0.8 > 0.6
        assert result.iloc[1] == "long"  # 0.7 > 0.6
        assert result.iloc[2] == "flat"  # 0.3 < 0.6

    def test_interpret_predictions_short_signals(self):
        """Test _interpret_predictions() with short signal predictions."""
        strategy = AIStrategy(threshold=0.6)

        predictions = [
            {"long_prob": 0.2, "short_prob": 0.8},
            {"long_prob": 0.1, "short_prob": 0.7},
            {"long_prob": 0.4, "short_prob": 0.3},
        ]

        result = strategy._interpret_predictions(predictions)

        assert len(result) == 3
        assert result.iloc[0] == "short"  # 0.8 > 0.6
        assert result.iloc[1] == "short"  # 0.7 > 0.6
        assert result.iloc[2] == "flat"  # 0.3 < 0.6

    def test_interpret_predictions_both_above_threshold(self):
        """Both long and short above threshold should yield flat signals."""
        strategy = AIStrategy(threshold=0.5)

        predictions = [
            {"long_prob": 0.7, "short_prob": 0.8},  # Both above threshold
            {"long_prob": 0.6, "short_prob": 0.6},  # Both above threshold
            {"long_prob": 0.3, "short_prob": 0.2},  # Both below threshold
        ]

        result = strategy._interpret_predictions(predictions)

        assert len(result) == 3
        assert result.iloc[0] == "flat"  # Default when both above threshold
        assert result.iloc[1] == "flat"  # Default when both above threshold
        assert result.iloc[2] == "flat"  # Both below threshold

    def test_interpret_predictions_missing_probabilities(self):
        """Test _interpret_predictions() with missing probability keys."""
        strategy = AIStrategy(threshold=0.5)

        predictions = [
            {"long_prob": 0.8},  # Missing short_prob
            {"short_prob": 0.7},  # Missing long_prob
            {},  # Missing both
        ]

        result = strategy._interpret_predictions(predictions)

        assert len(result) == 3
        assert result.iloc[0] == "long"  # long_prob 0.8 > 0.5, short defaults to 0.0
        assert result.iloc[1] == "short"  # short_prob 0.7 > 0.5, long defaults to 0.0
        assert result.iloc[2] == "flat"  # Both default to 0.0

    def test_threshold_boundary_conditions(self):
        """Test threshold boundary conditions (0.0, 0.5, 1.0)."""
        # Test threshold = 0.0
        strategy_zero = AIStrategy(threshold=0.0)
        predictions = [{"long_prob": 0.1, "short_prob": 0.0}]
        result = strategy_zero._interpret_predictions(predictions)
        assert result.iloc[0] == "long"  # 0.1 > 0.0

        # Test threshold = 0.5
        strategy_half = AIStrategy(threshold=0.5)
        predictions = [{"long_prob": 0.5, "short_prob": 0.4}]
        result = strategy_half._interpret_predictions(predictions)
        assert result.iloc[0] == "flat"  # 0.5 == 0.5, not greater

        # Test threshold = 1.0
        strategy_one = AIStrategy(threshold=1.0)
        predictions = [{"long_prob": 0.99, "short_prob": 0.95}]
        result = strategy_one._interpret_predictions(predictions)
        assert result.iloc[0] == "flat"  # Neither 0.99 nor 0.95 > 1.0

    @patch("trading_platform.strategy.ai_strategy.AIInferenceClient")
    def test_generate_signals_successful_flow(self, mock_client_class):
        """Test generate_signals() end-to-end successful flow."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.predict.return_value = [
            {"long_prob": 0.8, "short_prob": 0.2},
            {"long_prob": 0.3, "short_prob": 0.7},
        ]

        strategy = AIStrategy(threshold=0.6)

        # Create input data
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="h"),
        )

        result = strategy.generate_signals(data)

        # Verify the flow
        mock_client.predict.assert_called_once()
        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert result.iloc[0] == "long"  # 0.8 > 0.6
        assert result.iloc[1] == "short"  # 0.7 > 0.6
        pd.testing.assert_index_equal(result.index, data.index)

    @patch("trading_platform.strategy.ai_strategy.AIInferenceClient")
    def test_generate_signals_with_index_mismatch(self, mock_client_class, caplog):
        """Test generate_signals() when predictions length doesn't match data length."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.predict.return_value = [
            {"long_prob": 0.8, "short_prob": 0.2}  # Only 1 prediction for 2 data rows
        ]

        strategy = AIStrategy(threshold=0.6)

        # Create input data with 2 rows
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="h"),
        )

        with caplog.at_level(logging.WARNING):
            result = strategy.generate_signals(data)

        # Should log warning and return flat signals
        assert "Mismatch between number of signals and input data rows" in caplog.text
        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert all(result == "flat")
        pd.testing.assert_index_equal(result.index, data.index)

    @patch("trading_platform.strategy.ai_strategy.AIInferenceClient")
    def test_generate_signals_predictions_match_after_reindex(self, mock_client_class):
        """Predictions should align with data index after a retry."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.predict.return_value = [
            {"long_prob": 0.8, "short_prob": 0.2},
            {"long_prob": 0.3, "short_prob": 0.7},
        ]

        strategy = AIStrategy(threshold=0.6)

        # Create input data
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="h"),
        )

        # Mock _interpret_predictions to return wrong length initially
        with patch.object(strategy, "_interpret_predictions") as mock_interpret:
            # First call returns wrong length, second call returns correct length
            mock_interpret.side_effect = [
                pd.Series(["flat"], index=[0]),  # Wrong length (1 vs 2)
                pd.Series(
                    ["long", "short"], index=[0, 1]
                ),  # Correct length after reinterpret
            ]

            result = strategy.generate_signals(data)

            # Should call _interpret_predictions twice due to length mismatch
            assert mock_interpret.call_count == 2
            assert len(result) == 2
            pd.testing.assert_index_equal(result.index, data.index)

    @patch("trading_platform.strategy.ai_strategy.AIInferenceClient")
    def test_generate_signals_ai_client_error(self, mock_client_class):
        """Test error handling when AI inference client fails."""
        # Setup mock to raise an exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.predict.side_effect = Exception("AI service unavailable")

        strategy = AIStrategy()

        # Create input data
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
            }
        )

        # Should raise the exception from the AI client
        with pytest.raises(Exception, match="AI service unavailable"):
            strategy.generate_signals(data)

    @patch("trading_platform.strategy.ai_strategy.AIInferenceClient")
    def test_generate_signals_empty_dataframe(self, mock_client_class):
        """Test generate_signals() with empty DataFrame."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.predict.return_value = []

        strategy = AIStrategy()

        # Create empty data
        data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = strategy.generate_signals(data)

        assert isinstance(result, pd.Series)
        assert len(result) == 0
        pd.testing.assert_index_equal(result.index, data.index)

    def test_preprocess_data_preserves_index(self):
        """Test _preprocess_data() preserves DataFrame index."""
        strategy = AIStrategy()

        # Create data with custom index
        index = pd.date_range("2023-01-01", periods=3, freq="h")
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2],
                "high": [1.05, 1.15, 1.25],
                "low": [0.95, 1.05, 1.15],
                "close": [1.02, 1.12, 1.22],
                "volume": [100, 200, 150],
            },
            index=index,
        )

        result = strategy._preprocess_data(data)

        pd.testing.assert_index_equal(result.index, data.index)

    def test_interpret_predictions_with_extreme_values(self):
        """Test _interpret_predictions() with extreme probability values."""
        strategy = AIStrategy(threshold=0.5)

        predictions = [
            {"long_prob": 1.0, "short_prob": 0.0},  # Maximum long
            {"long_prob": 0.0, "short_prob": 1.0},  # Maximum short
            {"long_prob": -0.1, "short_prob": 1.2},  # Invalid values
        ]

        result = strategy._interpret_predictions(predictions)

        assert len(result) == 3
        assert result.iloc[0] == "long"  # 1.0 > 0.5
        assert result.iloc[1] == "short"  # 1.0 > 0.5
        assert result.iloc[2] == "short"  # 1.2 > 0.5 (handles invalid negative value)
