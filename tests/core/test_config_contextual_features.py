"""Tests for contextual features in RunConfig."""

from __future__ import annotations

from trading_platform.core.config import RunConfig


def test_run_config_loads_contextual_features() -> None:
    """Test that RunConfig can load contextual_features field."""
    # Define a sample run configuration with contextual_features
    config_dict = {
        "user_id": "test_user",
        "run_id": "test_run_001",
        "instrument": {
            "symbol": "EURUSD",
            "asset_class": "Forex",
            "point_value": 1.0,
            "tick_size": 0.0001,
        },
        "contextual_features": [
            {"name": "atr", "type": "ATR", "params": {"length": 14}},
            {
                "name": "adx",
                "type": "ADX",
                "params": {"length": 14},
                "source": "close",
            },
        ],
    }

    # Parse the dictionary using RunConfig
    config = RunConfig.model_validate(config_dict)

    # Assert that contextual_features attribute exists
    assert hasattr(config, "contextual_features")
    assert config.contextual_features is not None

    # Assert that it's a list with correct length
    assert isinstance(config.contextual_features, list)
    assert len(config.contextual_features) == 2

    # Assert that each item is a FeatureConfig and matches input
    first_feature = config.contextual_features[0]
    assert first_feature.name == "atr"
    assert first_feature.type == "ATR"
    assert first_feature.params == {"length": 14}

    second_feature = config.contextual_features[1]
    assert second_feature.name == "adx"
    assert second_feature.type == "ADX"
    assert second_feature.params == {"length": 14}
    assert second_feature.source == "close"
