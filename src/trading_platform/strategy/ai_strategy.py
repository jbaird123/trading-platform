import logging
from typing import Any, Dict, List

import pandas as pd

from trading_platform.ai.inference_client import AIInferenceClient
from trading_platform.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class AIStrategy(BaseStrategy):
    """A strategy that uses an AI model for signal generation."""

    def __init__(
        self,
        model_name: str = "default_model",
        threshold: float = 0.5,
        base_url: str = "http://localhost:8000",
        timeout: float = 5.0,
        retries: int = 3,
        backoff_factor: float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.model_name = model_name
        self.threshold = threshold
        self.inference_client = AIInferenceClient(
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )

    def _preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transforms raw market data into features for the AI model."""
        # This is a placeholder. In a real scenario, this would involve
        # calling the feature engineering pipeline.
        # For now, let's assume the model expects OHLCV as features directly.
        return data.copy()

    def _interpret_predictions(self, predictions: List[Dict[str, Any]]) -> pd.Series:
        """Interprets raw AI model predictions into trading signals."""
        signals = pd.Series("flat", index=range(len(predictions)))

        if not predictions:
            return signals

        # Assuming predictions is a list of dicts, each with 'long_prob' and 'short_prob'
        # and that the order of predictions matches the order of input features.
        long_probs = pd.Series([p.get("long_prob", 0.0) for p in predictions])
        short_probs = pd.Series([p.get("short_prob", 0.0) for p in predictions])

        signals[long_probs > self.threshold] = "long"
        signals[short_probs > self.threshold] = "short"

        # If both long and short probabilities are above threshold, default to flat
        # or implement a tie-breaking rule.
        signals[(long_probs > self.threshold) & (short_probs > self.threshold)] = (
            "flat"
        )

        return signals

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates trading signals using the AI model.

        Args:
            data: A DataFrame containing OHLCV data.

        Returns:
            A pandas Series with signals ('long', 'short', 'flat').
        """
        # 1. Preprocess data to create features for the AI model
        features = self._preprocess_data(data)

        # 2. Get predictions from the AI model
        predictions = self.inference_client.predict(features)

        # 3. Interpret predictions into trading signals
        signals = self._interpret_predictions(predictions)

        # Ensure the signals Series has the same index as the input data
        if len(signals) == len(data):
            signals.index = data.index
        else:
            # This case should ideally not happen if _preprocess_data maintains index
            # and _interpret_predictions returns series of correct length.
            # Log a warning or raise an error if indices don't match.
            logger.warning(
                "Mismatch between number of signals and input data rows. "
                "Attempting to reindex."
            )
            signals = pd.Series("flat", index=data.index)
            if len(predictions) == len(data):
                # If predictions match data length, re-interpret with correct index
                signals = self._interpret_predictions(predictions)
                signals.index = data.index

        return signals
