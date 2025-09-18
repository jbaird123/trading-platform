import json
from pathlib import Path

import jsonschema  # type: ignore
import pytest

# Validates: [SYS-1.7.3]

SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "docs/schemas/run_config.schema.json"
)


@pytest.fixture(scope="module")
def run_config_schema():
    """Loads the RunConfig JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_schema_is_valid_json(run_config_schema):
    """Ensure the schema itself is a valid JSON document."""
    assert isinstance(run_config_schema, dict)


def test_valid_run_configs(run_config_schema):
    """Test that valid RunConfig configurations validate successfully."""
    valid_configs = [
        # Minimal required config
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Config with all optional components
        {
            "run_id": "my_test_run_123",
            "strategy": "config/strategy/ema_crossover.yaml",
            "rem": "config/rem/basic_price_exits.yaml",
            "rmm": "config/rmm/daily_trend.yaml",
            "instrument": {"symbol": "GBP_JPY", "timeframe": "D1"},
            "data": {
                "source": "oanda",
                "start_date": "2020-01-01",
                "end_date": "2024-01-01",
            },
        },
    ]

    for config in valid_configs:
        try:
            jsonschema.validate(instance=config, schema=run_config_schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"Valid config failed validation: {config}\n{e}")


def test_invalid_run_configs(run_config_schema):
    """Test that invalid RunConfig configurations fail validation."""
    invalid_configs = [
        # Missing required 'instrument'
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Missing required 'strategy'
        {
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        },
        # Extra unknown property
        {
            "strategy": "config/strategy/ema_crossover.yaml",
            "instrument": {"symbol": "EUR_USD", "timeframe": "H1"},
            "data": {
                "source": "dukascopy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
            "unknown_field": True,
        },
    ]

    for config in invalid_configs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=config, schema=run_config_schema)
