import json
from pathlib import Path

import jsonschema  # type: ignore
import pytest

# Validates: [REM-6.2]

SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs/schemas/rem.schema.json"


@pytest.fixture(scope="module")
def rem_schema():
    """Loads the REM JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_schema_is_valid_json(rem_schema):
    """Ensure the schema itself is a valid JSON document."""
    assert isinstance(rem_schema, dict)


def test_valid_rem_configs(rem_schema):
    """Test that valid REM configurations validate successfully."""
    valid_configs = [
        # Static pips-based stop-loss only
        {"stop_loss": {"type": "static", "pips": 50}},
        # Static price-offset-based stop-loss and take-profit
        {
            "stop_loss": {"type": "static", "price_offset": 0.0050},
            "take_profit": {"type": "static", "price_offset": 0.0100},
        },
        # Dynamic ATR-based stop-loss and take-profit
        {
            "stop_loss": {"type": "dynamic", "atr_multiplier": 2.5},
            "take_profit": {"type": "dynamic", "atr_multiplier": 5.0},
        },
        # Mixed static and dynamic
        {
            "stop_loss": {"type": "static", "pips": 100},
            "take_profit": {"type": "dynamic", "atr_multiplier": 3.0},
        },
    ]

    for config in valid_configs:
        try:
            jsonschema.validate(instance=config, schema=rem_schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"Valid config failed validation: {config}\n{e}")


def test_invalid_rem_configs(rem_schema):
    """Test that invalid REM configurations fail validation."""
    invalid_configs = [
        # Missing stop_loss
        {},
        # Invalid stop_loss type
        {"stop_loss": {"type": "invalid_type", "pips": 50}},
        # Missing required field for static stop (pips or price_offset)
        {"stop_loss": {"type": "static"}},
        # Missing required field for dynamic stop (atr_multiplier)
        {"stop_loss": {"type": "dynamic"}},
        # Extra unknown property
        {
            "stop_loss": {"type": "static", "pips": 50},
            "unknown_field": "some_value",
        },
        # Both pips and price_offset defined
        {"stop_loss": {"type": "static", "pips": 50, "price_offset": 0.0050}},
    ]

    for config in invalid_configs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=config, schema=rem_schema)
