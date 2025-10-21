"""Unit tests for RiskExitManager core functionality.

# Validates: [REM-6.x]
"""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError
from trading_platform.core.signal import Signal
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager


def test_contextual_stop_loss_rule():
    """Test REM with reference_price rule using signal context.

    Task 2.1: Validates contextual stop-loss calculation.
    """
    # Create REM config with reference rule type
    config = {
        "name": "Contextual Risk Test",
        "stop_loss": {
            "type": "reference",
            "reference_point": "context.order_block_low",
            "offset": {"type": "fixed_pips", "pips": 5.0},
        },
    }

    # EUR/USD instrument with pip_location = 0.0001
    instrument = {"pip_location": 0.0001}

    rem = RiskExitManager(config=config, instrument=instrument)

    # Create a mock Signal with context
    signal = Signal(command="enter_long", context={"order_block_low": 1.2000})

    # Create a mock position
    position = Position(
        symbol="EURUSD",
        side="long",
        size=10000,
        entry_price=1.2050,
        entry_mid_price=1.2050,
        entry_time=pd.Timestamp("2024-01-01"),
    )

    # Create current bar where price hits the stop
    # Stop should be at 1.2000 - 5 pips = 1.2000 - 0.0005 = 1.1995
    current_bar = pd.Series({"high": 1.2040, "low": 1.1990, "close": 1.2000})

    # Check exits with signal context
    exit_details = rem.check_exits(position, current_bar, signal=signal)

    # Assert stop-loss was triggered at the calculated price
    assert exit_details is not None
    assert exit_details["reason"] == "stop-loss"
    assert exit_details["exit_price"] == 1.1995


def test_risk_exit_manager_rejects_unknown_indicator():
    """Ensure REM refuses configs referencing unregistered indicators."""
    config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "bollinger",
            "params": {"multiplier": 2.0},
        }
    }

    with pytest.raises(ValidationError, match="Unknown REM indicator"):
        RiskExitManager(config=config)


def test_risk_exit_manager_rejects_negative_trailing_distance():
    """Trailing stop distances must be positive."""
    config = {
        "stop_loss": {"type": "fixed_pips", "pips": 20.0},
        "trailing_stop": {
            "distance": {"type": "offset", "price_offset": -0.001},
        },
    }

    with pytest.raises(ValidationError, match="greater than 0"):
        RiskExitManager(config=config)


def test_risk_exit_manager_raises_on_missing_type_field():
    """Legacy payloads without a type discriminator are rejected."""
    config = {"stop_loss": {"type": "offset", "price_offset": 0.001}}

    with pytest.raises(ValidationError, match="type"):
        RiskExitManager(config=config)
