from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for all strategy implementations."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates trading signals from market data.

        Args:
            data: A DataFrame containing OHLCV data.

        Returns:
            A pandas Series with signals ('long', 'short', 'flat').
        """
        raise NotImplementedError
