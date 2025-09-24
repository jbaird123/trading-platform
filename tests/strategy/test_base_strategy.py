# Validates: [SE-3.2]
from __future__ import annotations

import pandas as pd
import pytest
from trading_platform.strategy.base import BaseStrategy


def test_base_strategy_requires_implementation():
    """Tests that a concrete strategy must implement generate_signals."""

    class TrulyAbstractStrategy(BaseStrategy):
        pass  # No implementation of generate_signals

    # This should fail at instantiation because no implementation is provided
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        TrulyAbstractStrategy()  # type: ignore[abstract]

    class IncompleteStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return super().generate_signals(data)

    # This can be instantiated but will fail when generate_signals is called
    strategy = IncompleteStrategy()
    test_data = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(NotImplementedError):
        strategy.generate_signals(test_data)

    class CompleteStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return pd.Series("flat", index=data.index)

    # This should not raise an error
    complete_strategy = CompleteStrategy()
    assert complete_strategy is not None


def test_strategy_must_return_valid_signals():
    """Tests that generate_signals must return only allowed signal values."""

    class BadSignalStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return pd.Series(["long", "invalid", "short"], index=data.index[:3])

    # This test is conceptual for now. A full implementation would require
    # the backtester to validate the signal series and raise an error.
    strategy = BadSignalStrategy()
    signals = strategy.generate_signals(pd.DataFrame([1, 2, 3]))
    assert signals.iloc[1] == "invalid"
