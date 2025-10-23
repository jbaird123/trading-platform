# Validates: [SE-3.3]
import pytest
import yaml
from pydantic import ValidationError
from trading_platform.strategy.models import StrategyConfig

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


def test_strategy_with_risk_block_fails_validation():
    """
    Tests that a strategy definition with a 'risk' block fails validation
    against the StrategyConfig Pydantic model, enforcing SE-3.3.
    """
    invalid_strategy_config = yaml.safe_load(INVALID_STRATEGY_YAML)

    with pytest.raises(ValidationError) as excinfo:
        StrategyConfig.model_validate(invalid_strategy_config)

    # Check that the error is about the unexpected 'risk' property
    message = str(excinfo.value)
    assert "risk" in message
    assert "Extra inputs are not permitted" in message
