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
        # Fixed pips-based stop only (new format)
        {"stop_loss": {"type": "fixed_pips", "pips": 50}},
        # Fixed pips stop and take-profit (new format)
        {
            "stop_loss": {"type": "fixed_pips", "pips": 20},
            "take_profit": {"type": "fixed_pips", "pips": 40},
        },
        # ATR indicator-based stop and take-profit (new format)
        {
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.5, "length": 14},
            },
            "take_profit": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 5.0},
            },
        },
        # ATR with default length
        {
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.0},
            }
        },
        # With name and version metadata
        {
            "name": "Conservative ATR",
            "version": "1.0",
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.0, "length": 14},
            },
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
        # Missing type field (old format no longer valid)
        {"stop_loss": {"type": "fixed_pips", "pips": 50}},
        # Missing required pips field
        {"stop_loss": {"type": "fixed_pips"}},
        # Zero pips (must be > 0)
        {"stop_loss": {"type": "fixed_pips", "pips": 0}},
        # Negative pips
        {"stop_loss": {"type": "fixed_pips", "pips": -10}},
        # Unknown top-level field (additionalProperties: false)
        {"stop_loss": {"type": "fixed_pips", "pips": 10}, "unknown_field": "x"},
        # Unknown indicator (not in whitelist)
        {
            "stop_loss": {
                "type": "indicator",
                "indicator": "rsi",  # Not whitelisted!
                "params": {"length": 14},
            }
        },
        # ATR without required multiplier
        {
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"length": 14},  # Missing multiplier!
            }
        },
        # Extra field in ATR params
        {
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.0, "unknown_param": 123},
            }
        },
    ]

    for config in invalid_configs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=config, schema=rem_schema)
