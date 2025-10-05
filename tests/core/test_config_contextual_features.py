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


def test_run_config_default_and_override_contextual_features() -> None:
    """Test default contextual features and override behavior."""
    # Scenario 1: Default Case - contextual_features key is missing
    config_dict_default = {
        "user_id": "test_user",
        "run_id": "test_run_default",
        "instrument": {
            "symbol": "EURUSD",
            "asset_class": "Forex",
            "point_value": 1.0,
            "tick_size": 0.0001,
        },
        # contextual_features key is intentionally missing
    }

    config_default = RunConfig.model_validate(config_dict_default)

    # Assert that contextual_features is populated with defaults
    assert config_default.contextual_features is not None
    assert isinstance(config_default.contextual_features, list)
    assert len(config_default.contextual_features) > 0

    # Check for specific default indicators
    feature_names = [f.name for f in config_default.contextual_features]
    assert "ctx_atr" in feature_names, "Expected ctx_atr in defaults"
    assert "ctx_rsi" in feature_names, "Expected ctx_rsi in defaults"
    assert "ctx_ema_slow" in feature_names, "Expected ctx_ema_slow in defaults"

    # Scenario 2: Empty Override Case - explicit empty list
    config_dict_empty = {
        "user_id": "test_user",
        "run_id": "test_run_empty",
        "instrument": {
            "symbol": "EURUSD",
            "asset_class": "Forex",
            "point_value": 1.0,
            "tick_size": 0.0001,
        },
        "contextual_features": [],  # Explicitly empty
    }

    config_empty = RunConfig.model_validate(config_dict_empty)

    # Assert that contextual_features is empty (user override)
    assert config_empty.contextual_features == []

    # Scenario 3: Custom Override Case - custom indicator list
    config_dict_custom = {
        "user_id": "test_user",
        "run_id": "test_run_custom",
        "instrument": {
            "symbol": "EURUSD",
            "asset_class": "Forex",
            "point_value": 1.0,
            "tick_size": 0.0001,
        },
        "contextual_features": [
            {"name": "my_custom_feature", "type": "SMA", "params": {"length": 5}}
        ],
    }

    config_custom = RunConfig.model_validate(config_dict_custom)

    # Assert that only custom feature is present
    assert config_custom.contextual_features is not None
    assert len(config_custom.contextual_features) == 1
    assert config_custom.contextual_features[0].name == "my_custom_feature"
    assert config_custom.contextual_features[0].type == "SMA"
    assert config_custom.contextual_features[0].params == {"length": 5}

    # Ensure defaults are NOT present
    custom_names = [f.name for f in config_custom.contextual_features]
    assert "ctx_atr" not in custom_names
    assert "ctx_rsi" not in custom_names
    assert "ctx_ema_slow" not in custom_names
