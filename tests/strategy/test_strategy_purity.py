# Validates: [SE-3.3]
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError, validate

# A strategy that violates SE-3.3 by including a risk management block.
INVALID_STRATEGY_YAML = """
strategy_name: "Violates SE-3.3"
description: "This strategy incorrectly includes a risk block."
features:
  - name: ema_fast
    type: EMA
    params:
      length: 10
  - name: ema_slow
    type: EMA
    params:
      length: 20
long_entry_rules:
  - all_of:
      - condition: is_above
        left: { ref: ema_fast }
        right: { ref: ema_slow }
long_exit_rules:
  - all_of:
      - condition: is_below
        left: { ref: ema_fast }
        right: { ref: ema_slow }
risk:
  stop:
    type: fixed
    value: 100
"""


def get_strategy_schema():
    """Loads the strategy JSON schema."""
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "schemas"
        / "strategy.schema.json"
    )
    return json.loads(schema_path.read_text())


def test_strategy_with_risk_block_fails_validation():
    """
    Tests that a strategy definition with a 'risk' block fails validation
    against the strategy schema, enforcing SE-3.3.
    """
    strategy_schema = get_strategy_schema()
    invalid_strategy_config = yaml.safe_load(INVALID_STRATEGY_YAML)

    with pytest.raises(ValidationError) as excinfo:
        validate(instance=invalid_strategy_config, schema=strategy_schema)

    # Check that the error is about the unexpected 'risk' property
    assert "Additional properties are not allowed ('risk' was unexpected)" in str(
        excinfo.value
    )
