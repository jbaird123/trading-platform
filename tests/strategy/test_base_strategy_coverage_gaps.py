"""
Test coverage gaps in Strategy Base module.

Targets specific missing lines in strategy/base.py to improve coverage.
"""
import pandas as pd
import pytest

from trading_platform.strategy.base import BaseStrategy


class TestStrategy(BaseStrategy):
    """Concrete implementation for testing BaseStrategy."""
    
    def __init__(self):
        super().__init__()
        self.allowed_param: float = 0.0  # Add test attribute
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Simple test implementation."""
        # Just return signals - the validation happens in parent's abstract method
        return pd.Series(['flat'] * len(data), index=data.index)


class TestStrategyWithParentCall(BaseStrategy):
    """Test strategy that calls parent validation."""
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Implementation that calls parent to trigger validation."""
        # This will trigger the validation in the parent abstract method
        try:
            super().generate_signals(data)
        except NotImplementedError:
            # Expected - continue with our implementation
            pass
        return pd.Series(['flat'] * len(data), index=data.index)


def test_base_strategy_forbidden_attributes():
    """Test BaseStrategy forbidden attribute assignment. Covers line 22."""
    strategy = TestStrategy()
    
    # Test each forbidden attribute
    forbidden_attrs = [
        "stop_loss_pips",
        "take_profit_pips", 
        "trailing_stop_pips",
        "exit_rules"
    ]
    
    for attr in forbidden_attrs:
        with pytest.raises(AttributeError, match=f"Strategy cannot define trade management attribute: '{attr}'"):
            setattr(strategy, attr, 10.0)


def test_base_strategy_forbidden_columns():
    """Test BaseStrategy forbidden column detection. Covers line 42."""
    strategy = TestStrategyWithParentCall()
    
    # Create test data with forbidden columns
    forbidden_columns = [
        "instrument_type",
        "commission", 
        "slippage",
        "point_value"
    ]
    
    for col in forbidden_columns:
        # Create DataFrame with forbidden column
        data = pd.DataFrame({
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [100, 200],
            col: [1, 2]  # Add forbidden column
        })
        
        # Should raise ValueError when trying to generate signals
        with pytest.raises(ValueError, match=f"Strategy cannot access instrument-specific column: '{col}'"):
            strategy.generate_signals(data)


def test_base_strategy_valid_operations():
    """Test BaseStrategy with valid operations (no forbidden attributes/columns)."""
    strategy = TestStrategy()
    
    # Test setting allowed attributes
    strategy.allowed_param = 5.0
    assert strategy.allowed_param == 5.0
    
    # Test with valid data (no forbidden columns)
    data = pd.DataFrame({
        "open": [1.0, 1.1, 1.2],
        "high": [1.05, 1.15, 1.25],
        "low": [0.95, 1.05, 1.15],
        "close": [1.02, 1.12, 1.22],
        "volume": [100, 200, 300]
    })
    
    # Should work without errors
    signals = strategy.generate_signals(data)
    assert len(signals) == 3
    assert all(signals == 'flat')