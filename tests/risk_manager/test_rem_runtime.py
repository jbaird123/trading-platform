"""Runtime-focused tests for RiskExitManager behaviour."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
import trading_platform.risk_manager.rem_indicators as rem_indicators
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager


@pytest.fixture(autouse=True)
def _reset_registry(monkeypatch):
    """Reset REM indicator registry per test to avoid cross-test pollution."""
    monkeypatch.setattr(
        rem_indicators,
        "REM_INDICATORS_REGISTRY",
        {
            "atr": rem_indicators.REMIndicatorSpec(
                name="atr",
                description="Average True Range",
                required_params={"multiplier": float},
                optional_params={"length": (int, 14)},
                stop_calculator=_atr_stop_calculator,
            )
        },
    )


def _atr_stop_calculator(
    entry_price: float,
    side: str,
    current_bar: pd.Series,
    params: dict,
) -> float:
    multiplier = params["multiplier"]
    atr_value = float(current_bar.get("atr", 0.0))
    distance = atr_value * multiplier
    if side == "long":
        return entry_price - distance
    return entry_price + distance


def _long_position() -> Position:
    return Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.2000,
        entry_mid_price=1.2000,
        side="long",
        size=100000.0,
        mfe_currency=400.0,
    )


def _short_position() -> Position:
    return Position(
        symbol="EURUSD",
        entry_time=datetime.now(),
        entry_price=1.2000,
        entry_mid_price=1.2000,
        side="short",
        size=100000.0,
        mfe_currency=400.0,
    )


def test_fixed_pips_requires_instrument_metadata():
    rem = RiskExitManager(
        config={"stop_loss": {"type": "fixed_pips", "pips": 20.0}},
        instrument=None,
    )

    position = _long_position()
    bar = pd.Series({"high": 1.2050, "low": 1.1950})

    with pytest.raises(ValueError, match="pip_location missing"):
        rem.check_exits(position, bar)


def test_indicator_rule_uses_registry_values():
    rem = RiskExitManager(
        config={
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.0},
            }
        }
    )

    position = _long_position()
    bar = pd.Series({"high": 1.2050, "low": 1.1950, "atr": 0.0015})

    exit_info = rem.check_exits(position, bar)
    assert exit_info is not None
    assert exit_info["reason"] == "stop-loss"
    assert abs(exit_info["exit_price"] - 1.1970) < 1e-9


def test_reference_rule_without_offset_uses_context():
    rem = RiskExitManager(
        config={
            "stop_loss": {
                "type": "reference",
                "reference_point": "context.support_level",
            }
        }
    )

    position = _long_position()
    bar = pd.Series({"high": 1.2050, "low": 1.1950})
    result = rem.check_exits(
        position,
        bar,
        signal=None,
    )
    assert result is None

    position.context_at_entry = {"support_level": 1.1975}
    result = rem.check_exits(position, bar)
    assert result is not None
    assert result["exit_price"] == 1.1975


def test_reference_rule_with_offset_resolves_price():
    rem = RiskExitManager(
        config={
            "stop_loss": {
                "type": "reference",
                "reference_point": "context.support_level",
                "offset": {"type": "offset", "price_offset": 0.0010},
            }
        }
    )
    position = _long_position()
    position.context_at_entry = {"support_level": 1.1980}
    bar = pd.Series({"high": 1.2050, "low": 1.1950})

    result = rem.check_exits(position, bar)
    assert result is not None
    assert abs(result["exit_price"] - 1.1970) < 1e-9


def test_trailing_stop_updates_long_position():
    rem = RiskExitManager(
        config={
            "stop_loss": {"type": "fixed_pips", "pips": 20.0},
            "trailing_stop": {
                "distance": {"type": "fixed_pips", "pips": 10.0},
            },
        },
        instrument={"pip_location": 0.0001},
    )
    position = _long_position()
    bar = pd.Series({"high": 1.2050, "low": 1.1985})

    assert rem.check_exits(position, bar) is None


def test_trailing_stop_updates_short_position():
    rem = RiskExitManager(
        config={
            "stop_loss": {"type": "fixed_pips", "pips": 20.0},
            "trailing_stop": {
                "distance": {"type": "fixed_pips", "pips": 10.0},
            },
        },
        instrument={"pip_location": 0.0001},
    )
    position = _short_position()
    bar = pd.Series({"high": 1.2015, "low": 1.1945})

    assert rem.check_exits(position, bar) is None


def test_take_profit_exit_hits_first():
    rem = RiskExitManager(
        config={
            "stop_loss": {"type": "offset", "price_offset": 0.0020},
            "take_profit": {"type": "offset", "price_offset": 0.0030},
        }
    )
    position = _long_position()
    bar = pd.Series({"high": 1.2055, "low": 1.1980})

    exit_info = rem.check_exits(position, bar)
    assert exit_info is not None
    assert exit_info["reason"] == "take-profit"
