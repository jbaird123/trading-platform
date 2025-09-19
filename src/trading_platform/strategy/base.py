from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for all strategy implementations."""

    _FORBIDDEN_ATTRIBUTES = [
        "stop_loss_pips",
        "take_profit_pips",
        "trailing_stop_pips",
        "exit_rules",
    ]
    _FORBIDDEN_COLUMNS = ["instrument_type", "commission", "slippage", "point_value"]

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._FORBIDDEN_ATTRIBUTES:
            raise AttributeError(
                f"Strategy cannot define trade management attribute: '{name}'. "
                "Use Risk & Exit Manager (REM) for trade management."
            )
        super().__setattr__(name, value)

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates trading signals from market data.

        Args:
            data: A DataFrame containing OHLCV data.

        Returns:
            A pandas Series with signals ('long', 'short', 'flat').
        """
        # Check for forbidden columns in the input data
        for col in self._FORBIDDEN_COLUMNS:
            if col in data.columns:
                raise ValueError(
                    f"Strategy cannot access instrument-specific column: '{col}'. "
                    "Strategies must be instrument-agnostic."
                )
        raise NotImplementedError
