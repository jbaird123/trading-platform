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
            "indicator": "donchian",
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
    config = {"stop_loss": {"price_offset": 0.001}}

    with pytest.raises(ValidationError, match="type"):
        RiskExitManager(config=config)


def _bar(data: dict[str, float], timestamp: str) -> pd.Series:
    """Helper to build a pandas Series with a timestamp index name."""
    series = pd.Series(data)
    series.name = pd.Timestamp(timestamp)
    return series


def test_indicator_stop_uses_prior_bar() -> None:
    """Indicator-based stops must be derived from the prior completed bar."""
    config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "atr",
            "params": {"length": 14, "multiplier": 2.0},
        }
    }
    rem = RiskExitManager(config=config)

    position = Position(
        symbol="EURUSD",
        entry_time=pd.Timestamp("2024-02-01 12:00:00+00:00"),
        entry_price=1.1050,
        entry_mid_price=1.1050,
        side="long",
        size=10000,
    )

    prior_bar = _bar(
        {"close": 1.1050, "atr_14": 0.0012},
        "2024-02-01 13:00:00+00:00",
    )
    current_bar = _bar(
        {"open": 1.1055, "high": 1.1060, "low": 1.1023, "close": 1.1040},
        "2024-02-01 14:00:00+00:00",
    )

    exit_details = rem.check_exits(
        position,
        current_bar,
        prior_bar=prior_bar,
    )
    assert exit_details is not None
    expected_stop = prior_bar["close"] - prior_bar["atr_14"] * 2.0
    assert exit_details["exit_price"] == pytest.approx(expected_stop, rel=0, abs=1e-9)

    intrabar_details = rem.check_exits_intrabar(
        position,
        current_bar,
        prior_bar=prior_bar,
    )
    assert intrabar_details is not None
    assert intrabar_details["exit_price"] == pytest.approx(
        expected_stop, rel=0, abs=1e-9
    )


def test_indicator_stop_without_prior_bar_raises() -> None:
    """Fail fast when indicator stop lacks the prior bar input."""
    config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "atr",
            "params": {"length": 14, "multiplier": 2.0},
        }
    }
    rem = RiskExitManager(config=config)

    position = Position(
        symbol="EURUSD",
        entry_time=pd.Timestamp("2024-02-01 12:00:00+00:00"),
        entry_price=1.1050,
        entry_mid_price=1.1050,
        side="long",
        size=10000,
    )

    current_bar = _bar(
        {"open": 1.1055, "high": 1.1060, "low": 1.1023, "close": 1.1040},
        "2024-02-01 14:00:00+00:00",
    )

    with pytest.raises(ValueError, match="requires prior bar data"):
        rem.check_exits(position, current_bar)


def test_bollinger_indicator_stop_uses_band_value() -> None:
    """Bollinger-based indicator stops should pull the correct band."""
    config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "bollinger",
            "params": {"band": "lower"},
        }
    }
    rem = RiskExitManager(config=config)

    position = Position(
        symbol="EURUSD",
        entry_time=pd.Timestamp("2024-03-01 12:00:00+00:00"),
        entry_price=1.2050,
        entry_mid_price=1.2050,
        side="long",
        size=10000,
    )

    prior_bar = _bar(
        {"close": 1.2050, "bb_lower": 1.1980, "bb_upper": 1.2120},
        "2024-03-01 13:00:00+00:00",
    )
    current_bar = _bar(
        {"open": 1.2055, "high": 1.2060, "low": 1.1975, "close": 1.2030},
        "2024-03-01 14:00:00+00:00",
    )

    exit_details = rem.check_exits(position, current_bar, prior_bar=prior_bar)
    assert exit_details is not None
    assert exit_details["exit_price"] == pytest.approx(1.1980, abs=1e-9)


def test_indicator_stop_reads_strategy_and_global_context() -> None:
    """Indicator stops may source values from strategy/global feature context."""
    config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "chandelier",
            "params": {"multiplier": 3.0, "length": 22, "atr_length": 14},
        }
    }
    rem = RiskExitManager(config=config)

    position = Position(
        symbol="EURUSD",
        entry_time=pd.Timestamp("2024-04-01 12:00:00+00:00"),
        entry_price=1.2060,
        entry_mid_price=1.2060,
        side="long",
        size=10000,
        context_at_entry={
            "strategy_features": {"hhv_22": 1.2100},
            "global_features": {"atr_14": 0.0025},
        },
    )

    prior_bar = _bar({"close": 1.2060}, "2024-04-01 13:00:00+00:00")
    current_bar = _bar(
        {"open": 1.2060, "high": 1.2070, "low": 1.2010, "close": 1.2020},
        "2024-04-01 14:00:00+00:00",
    )

    exit_details = rem.check_exits(position, current_bar, prior_bar=prior_bar)
    assert exit_details is not None
    expected_stop = 1.2100 - (0.0025 * 3.0)
    assert exit_details["exit_price"] == pytest.approx(expected_stop, abs=1e-9)
