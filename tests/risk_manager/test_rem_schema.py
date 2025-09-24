import json
from pathlib import Path

import jsonschema
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
        # Pips-based stop only
        {"stop_loss": {"pips": 50}},
        # Price-offset-based stop and take-profit
        {
            "stop_loss": {"price_offset": 0.0050},
            "take_profit": {"price_offset": 0.0100},
        },
        # ATR-based stop and take-profit
        {
            "stop_loss": {"atr_multiple": 2.5, "atr_length": 14},
            "take_profit": {"atr_multiple": 5.0},
        },
        # Absolute stop
        {"stop_loss": {"absolute_price": 1.0950}},
        # With trailing stop
        {
            "stop_loss": {"price_offset": 0.0020},
            "take_profit": {"price_offset": 0.0040},
            "trailing_stop": {"price_offset": 0.0015, "update": "bar"},
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
        # Empty stop_loss
        {"stop_loss": {}},
        # Too many fields in stop_loss
        {"stop_loss": {"pips": 10, "price_offset": 0.0010}},
        # Unknown top-level field
        {"stop_loss": {"pips": 10}, "unknown_field": "x"},
        # Trailing without any distance
        {"stop_loss": {"price_offset": 0.0010}, "trailing_stop": {"update": "bar"}},
    ]

    for config in invalid_configs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=config, schema=rem_schema)
