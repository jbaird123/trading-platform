"""Tests for strategy configuration models."""

import pytest
from pydantic import ValidationError
from trading_platform.strategy.models import StrategyConfig


def test_strategy_feature_cannot_have_timeframe_prefix() -> None:
    """Test that strategy features cannot have timeframe prefix."""
    with pytest.raises(ValidationError) as exc_info:
        StrategyConfig.model_validate(
            {
                "strategy_name": "test_strategy",
                "features": [
                    {
                        "name": "h1_rsi",  # Invalid: has timeframe prefix
                        "type": "RSI",
                        "params": {"length": 14},
                    }
                ],
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"ref": "h1_rsi"},
                                "right": {"value": 50},
                            }
                        ]
                    }
                ],
            }
        )

    error_msg = str(exc_info.value)
    assert "timeframe prefix" in error_msg.lower()
    assert "h1_rsi" in error_msg


def test_strategy_feature_accepts_valid_names() -> None:
    """Test that strategy features accept names without timeframe prefix."""
    valid_feature_names = ["rsi", "ema_fast", "ema_slow", "atr_value"]

    for name in valid_feature_names:
        # Should not raise ValidationError
        config = StrategyConfig.model_validate(
            {
                "strategy_name": "test_strategy",
                "features": [
                    {
                        "name": name,
                        "type": "RSI",
                        "params": {"length": 14},
                    }
                ],
                "long_entry_rules": [
                    {
                        "any_of": [
                            {
                                "condition": "is_above",
                                "left": {"ref": name},
                                "right": {"value": 50},
                            }
                        ]
                    }
                ],
            }
        )
        assert config.features[0].name == name
