"""Tests for JSON schema validation.

This module tests that Pydantic models and JSON schemas correctly validate
configurations including the timeframe field for multi-timeframe features.
"""

from __future__ import annotations

import json
from pathlib import Path

from trading_platform.core.config import FeatureConfig


def test_feature_config_schema_includes_timeframe():
    """Test that the generated FeatureConfig schema includes timeframe field.

    Verify the JSON schema generated from FeatureConfig Pydantic model
    includes the optional timeframe field with correct type and description.
    """
    # Load the generated schema
    schema_path = (
        Path(__file__).parent.parent.parent
        / "docs"
        / "schemas"
        / "feature_config.schema.json"
    )

    assert schema_path.exists(), f"Schema file not found at {schema_path}"

    with open(schema_path) as f:
        schema = json.load(f)

    # Verify timeframe field exists in properties
    assert "timeframe" in schema["properties"], "timeframe field missing from schema"

    # Verify it's optional (nullable)
    timeframe_schema = schema["properties"]["timeframe"]
    assert "anyOf" in timeframe_schema or "type" in timeframe_schema

    # Check it allows string or null
    if "anyOf" in timeframe_schema:
        types = [item.get("type") for item in timeframe_schema["anyOf"]]
        assert "string" in types, "timeframe should allow string type"
        assert "null" in types, "timeframe should be nullable"

    # Verify description mentions resampling
    description = timeframe_schema.get("description", "")
    assert (
        "resamp" in description.lower()
    ), "timeframe description should mention resampling"


def test_campaign_validate_accepts_timeframe_field():
    """Test that campaign YAML with timeframe field validates correctly.

    Load a sample campaign YAML file that includes contextual_features
    with the timeframe field and verify it can be parsed and validated.
    """
    # Create a sample configuration with contextual features using timeframe
    sample_config = {
        "name": "h1_rsi",
        "type": "RSI",
        "params": {"length": 14},
        "timeframe": "1h",
    }

    # Validate using Pydantic model
    feature = FeatureConfig.model_validate(sample_config)

    # Verify all fields are correctly set
    assert feature.name == "h1_rsi"
    assert feature.type == "RSI"
    assert feature.params == {"length": 14}
    assert feature.timeframe == "1h"


def test_feature_config_validates_without_timeframe():
    """Test backwards compatibility - features without timeframe validate.

    Existing feature configurations that don't specify timeframe should
    still validate successfully.
    """
    # Legacy config without timeframe
    legacy_config = {
        "name": "ema_20",
        "type": "EMA",
        "params": {"length": 20},
    }

    # Should validate successfully
    feature = FeatureConfig.model_validate(legacy_config)

    assert feature.name == "ema_20"
    assert feature.type == "EMA"
    assert feature.params == {"length": 20}
    assert feature.timeframe is None  # Default is None


def test_feature_config_validates_multiple_timeframes():
    """Test that different timeframe strings validate correctly.

    Common pandas offset aliases like '1h', '4h', '1D' should all validate.
    """
    timeframes = ["1h", "4h", "1D", "1W", "1M"]

    for tf in timeframes:
        config = {
            "name": f"test_{tf}",
            "type": "SMA",
            "params": {"length": 5},
            "timeframe": tf,
        }

        feature = FeatureConfig.model_validate(config)
        assert feature.timeframe == tf
