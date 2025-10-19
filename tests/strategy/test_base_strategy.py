"""
Consolidated tests for trading_platform.strategy.base.

# Validates: [SE-3.2]

Merged original behavioural checks with coverage-gap tests.
"""

from __future__ import annotations

import pandas as pd
import pytest
from trading_platform.strategy.base import BaseStrategy

# --- test_base_strategy.py (original) ---


def test_base_strategy_requires_implementation() -> None:
    """Concrete strategies must override generate_signals."""

    class TrulyAbstractStrategy(BaseStrategy):
        pass  # No implementation of generate_signals

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        TrulyAbstractStrategy()

    class IncompleteStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return super().generate_signals(data)  # type: ignore[no-any-return]

    strategy = IncompleteStrategy()
    test_data = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(NotImplementedError):
        strategy.generate_signals(test_data)

    class CompleteStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return pd.Series("flat", index=data.index, dtype=object)

    complete_strategy = CompleteStrategy()
    assert complete_strategy is not None


def test_strategy_must_return_valid_signals() -> None:
    """Signal values are not coerced; invalid values surface for callers."""

    class BadSignalStrategy(BaseStrategy):
        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            return pd.Series(["long", "invalid", "short"], index=data.index[:3])

    strategy = BadSignalStrategy()
    signals = strategy.generate_signals(pd.DataFrame([1, 2, 3]))
    assert signals.iloc[1] == "invalid"


# --- test_base_strategy_coverage_gaps.py ---


class DummyStrategy(BaseStrategy):
    """Concrete implementation for testing BaseStrategy validation."""

    def __init__(self) -> None:
        super().__init__()
        self.allowed_param: float = 0.0

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(["flat"] * len(data), index=data.index)


class TestStrategyWithParentCall(BaseStrategy):
    """Strategy that intentionally calls the parent for validation coverage."""

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        try:
            super().generate_signals(data)
        except NotImplementedError:
            pass
        return pd.Series(["flat"] * len(data), index=data.index)


def test_base_strategy_forbidden_attributes() -> None:
    """Assigning trade management attributes should raise AttributeError."""
    strategy = DummyStrategy()
    for attr in [
        "stop_loss_pips",
        "take_profit_pips",
        "trailing_stop_pips",
        "exit_rules",
    ]:
        with pytest.raises(
            AttributeError,
            match=f"Strategy cannot define trade management attribute: '{attr}'",
        ):
            setattr(strategy, attr, 10.0)


def test_base_strategy_forbidden_columns() -> None:
    """Generating signals with forbidden instrument columns should fail."""
    strategy = TestStrategyWithParentCall()
    forbidden_columns = ["instrument_type", "commission", "slippage", "point_value"]
    for col in forbidden_columns:
        data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.05, 1.15],
                "low": [0.95, 1.05],
                "close": [1.02, 1.12],
                "volume": [100, 200],
                col: [1, 2],
            }
        )
        with pytest.raises(
            ValueError,
            match=f"Strategy cannot access instrument-specific column: '{col}'",
        ):
            strategy.generate_signals(data)


def test_base_strategy_valid_operations() -> None:
    """Valid attributes and clean data should pass without errors."""
    strategy = DummyStrategy()
    strategy.allowed_param = 5.0
    assert strategy.allowed_param == 5.0

    data = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2],
            "high": [1.05, 1.15, 1.25],
            "low": [0.95, 1.05, 1.15],
            "close": [1.02, 1.12, 1.22],
            "volume": [100, 200, 300],
        }
    )
    signals = strategy.generate_signals(data)
    assert len(signals) == 3
    assert all(signals == "flat")
