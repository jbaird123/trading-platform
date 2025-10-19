"""
Tests for DynamicREM (Dynamic Risk & Exit Manager).

Tasks 12-21: Epic 2, Features 2.1-2.2
Validates dynamic position management with breakeven, partial exits,
and volatility-aware trailing stops.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.dynamic_rem import DynamicREM

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]


def test_breakeven_trigger():
    """Task 12: Test breakeven trigger when trade reaches +0.75R.

    Validates: Epic 2.1, Feature 2.1, Task 12
    When a position reaches 0.75R profit, the stop-loss should move to
    breakeven (entry price).
    """
    # Create DynamicREM with breakeven threshold
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "breakeven_threshold": 0.75,  # Move to breakeven at +0.75R
    }

    rem = DynamicREM(config)

    # Create a long position
    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,  # Risk of $150
        bars_held=5,
    )

    # Current price at +0.75R
    # If risk is $150 for 1.5 ATR, 1R = $100
    # +0.75R = $75 profit
    # entry=1.1000, need to move up $75 on 10k units = 0.0075 pips
    # Actual R calculation: risk_amount / size = distance
    # distance = 150 / 10000 = 0.015
    # 1R = 0.015, so 0.75R = 0.01125
    current_price = 1.1000 + 0.01125
    atr = 0.010  # ATR value
    initial_stop = 1.1000 - (1.5 * 0.010)  # Original stop at -1.5 ATR

    # Manage position with current price
    updated_stop, updated_tp = rem.manage_position(
        position, current_price=current_price, atr=atr, initial_stop=initial_stop
    )

    # Stop should now be at breakeven (entry price)
    assert updated_stop is not None
    assert abs(updated_stop - 1.1000) < 0.0001  # Breakeven = entry price


def test_partial_profit_trigger():
    """Task 14: Test partial profit-taking when target is reached.

    Validates: Epic 2.1, Feature 2.1, Task 14
    When a position reaches a profit target, the REM should generate
    an order to close a fraction of the position.
    """
    # Create DynamicREM with partial exit configuration
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "partial_exits": [
            {"r_multiple": 1.0, "fraction": 0.5},  # Close 50% at 1R
            {"r_multiple": 2.0, "fraction": 0.5},  # Close 50% more at 2R
        ],
    }

    rem = DynamicREM(config)

    # Create a long position
    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,
        bars_held=5,
    )

    # Current price at +1.0R (first partial exit target)
    # 1R = $150, so price move = 150 / 10000 = 0.015
    current_price = 1.1000 + 0.015

    # Manage position - should trigger partial exit
    orders = rem.check_partial_exits(position, current_price)

    # Should generate an order to close 50% of the position
    assert orders is not None
    assert len(orders) > 0
    order = orders[0]
    assert order["action"] == "close_partial"
    assert order["fraction"] == 0.5
    assert order["r_multiple"] == 1.0


def test_atr_trailing_stop_after_partial_exit():
    """Task 16: Test ATR trailing stop activation after partial exit.

    Validates: Epic 2.1, Feature 2.1, Task 16
    After a partial exit, the stop-loss should trail using ATR multiple.
    """
    # Create DynamicREM with partial exit and trailing stop
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "partial_exits": [{"r_multiple": 1.0, "fraction": 0.5}],
        "trailing_stop": {
            "atr_multiple": 1.0,  # Trail at 1 ATR
            "activate_after_partial": True,
        },
    }

    rem = DynamicREM(config)

    # Create a long position
    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,
        bars_held=5,
    )

    # Current price at +1.5R (after partial exit at 1R)
    current_price = 1.1000 + 0.0225  # 1.5R = 1.5 * 150 / 10000
    atr = 0.010
    initial_stop = 1.1000 - (1.5 * 0.010)

    # Simulate that partial exit has occurred
    context = {"partial_exits_triggered": [1.0]}  # Already exited at 1R

    # Manage position with trailing stop
    updated_stop, updated_tp = rem.manage_position(
        position,
        current_price=current_price,
        atr=atr,
        initial_stop=initial_stop,
        context=context,
    )

    # Stop should now trail at current_price - (1.0 * ATR)
    expected_stop = current_price - (1.0 * atr)
    assert updated_stop is not None
    assert abs(updated_stop - expected_stop) < 0.0001


def test_stop_tightens_on_falling_adx():
    """Task 20: Test stop tightens when ADX falls below threshold.

    Validates: Epic 2.2, Feature 2.2, Task 20
    When ADX falls below volatility threshold, trailing stop should tighten.
    """
    # Create DynamicREM with volatility-aware trailing
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "trailing_stop": {"atr_multiple": 1.5},  # Normal trailing distance
        "volatility_threshold": 20.0,  # ADX threshold
        "low_volatility_multiplier": 0.75,  # Tighten to 0.75x when ADX < 20
    }

    rem = DynamicREM(config)

    # Create a long position in profit
    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,
        bars_held=10,
    )

    # Current price at +1.5R
    current_price = 1.1000 + 0.0225
    atr = 0.010
    initial_stop = 1.1000 - (1.5 * 0.010)

    # Context with low ADX (falling volatility)
    context = {"adx": 15.0}  # Below threshold of 20

    # Manage position
    updated_stop, updated_tp = rem.manage_position(
        position,
        current_price=current_price,
        atr=atr,
        initial_stop=initial_stop,
        context=context,
    )

    # Stop should tighten: current_price - (1.5 * 0.75 * ATR)
    expected_stop = current_price - (1.5 * 0.75 * atr)
    assert updated_stop is not None
    assert abs(updated_stop - expected_stop) < 0.0001


def test_partial_exit_fires_only_once():
    """Test that each partial exit target fires only once per position.

    Code Review Fix: Ensures partial exits don't retrigger on subsequent calls
    when the R-multiple stays above the threshold.
    """
    # Create DynamicREM with multiple partial exit targets
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "partial_exits": [
            {"r_multiple": 1.0, "fraction": 0.5},  # Close 50% at 1R
            {"r_multiple": 2.0, "fraction": 0.3},  # Close 30% at 2R
        ],
    }

    rem = DynamicREM(config)

    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,
        bars_held=5,
    )

    # First call at 1.0R - should trigger first partial
    current_price_1r = 1.1000 + 0.015
    orders1 = rem.check_partial_exits(position, current_price_1r)
    assert len(orders1) == 1
    assert orders1[0]["r_multiple"] == 1.0
    assert rem.stats["partial_exits_triggered"] == 1

    # Second call at same price - should NOT retrigger
    orders2 = rem.check_partial_exits(position, current_price_1r)
    assert len(orders2) == 0
    assert rem.stats["partial_exits_triggered"] == 1  # Count unchanged

    # Third call at 2.0R - should trigger second partial only
    current_price_2r = 1.1000 + 0.030
    orders3 = rem.check_partial_exits(position, current_price_2r)
    assert len(orders3) == 1
    assert orders3[0]["r_multiple"] == 2.0
    assert rem.stats["partial_exits_triggered"] == 2

    # Fourth call at same price - should NOT retrigger
    orders4 = rem.check_partial_exits(position, current_price_2r)
    assert len(orders4) == 0
    assert rem.stats["partial_exits_triggered"] == 2  # Count unchanged


def test_stop_tightens_when_adx_is_zero():
    """Test that volatility tightening works when ADX is exactly zero.

    Code Review Fix: Ensures explicit 'is not None' check allows ADX=0
    to trigger stop tightening in flat/low-volatility markets.
    """
    config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "trailing_stop": {"atr_multiple": 1.5},
        "volatility_threshold": 20.0,
        "low_volatility_multiplier": 0.75,
    }

    rem = DynamicREM(config)

    position = Position(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=1.1000,
        entry_mid_price=1.1000,
        side="long",
        size=10000,
        initial_risk_ccy=150.0,
        bars_held=10,
    )

    current_price = 1.1000 + 0.0225  # At +1.5R
    atr = 0.010
    initial_stop = 1.1000 - (1.5 * 0.010)

    # Context with ADX = 0 (very flat market)
    context = {"adx": 0.0}

    # Manage position - stop should tighten even with ADX=0
    updated_stop, _ = rem.manage_position(
        position,
        current_price=current_price,
        atr=atr,
        initial_stop=initial_stop,
        context=context,
    )

    # Stop should tighten: current_price - (1.5 * 0.75 * ATR)
    expected_stop = current_price - (1.5 * 0.75 * atr)
    assert updated_stop is not None
    assert abs(updated_stop - expected_stop) < 0.0001

    # Verify tightening was tracked
    assert rem.stats["volatility_tightenings"] == 1


def test_dynamic_rem_schema_validation():
    """Task 18: Test DynamicREM configuration against schema.

    Validates: Epic 2.1, Feature 2.1, Task 18
    Ensures DynamicREM config validates against rem_dynamic.schema.json
    """
    if jsonschema is None:
        return  # Skip if jsonschema not installed

    # Load schema
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "schemas"
        / "rem_dynamic.schema.json"
    )
    schema = json.loads(schema_path.read_text())

    # Valid configuration
    valid_config = {
        "name": "DynamicREM_Test",
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "breakeven_threshold": 0.75,
        "partial_exits": [
            {"r_multiple": 1.0, "fraction": 0.5},
            {"r_multiple": 2.0, "fraction": 0.5},
        ],
        "trailing_stop": {
            "atr_multiple": 1.0,
            "activate_after_partial": True,
        },
        "volatility_threshold": 20.0,
        "low_volatility_multiplier": 0.75,
    }

    # Should validate without error
    jsonschema.validate(valid_config, schema)

    # Invalid config (missing required field)
    invalid_config = {"name": "Invalid"}

    try:
        jsonschema.validate(invalid_config, schema)
        assert False, "Should have raised validation error"
    except jsonschema.ValidationError:
        pass  # Expected


def test_create_rem_factory():
    """Task 19: Test REM factory creates DynamicREM with validation.

    Validates: Epic 2.1, Feature 2.1, Task 19
    Ensures create_rem factory validates config and instantiates DynamicREM
    """
    from trading_platform.risk_manager import create_rem

    # Valid configuration
    valid_config = {
        "stop_loss": {"atr_multiple": 1.5},
        "take_profit": {"atr_multiple": 3.0},
        "breakeven_threshold": 0.75,
        "partial_exits": [{"r_multiple": 1.0, "fraction": 0.5}],
    }

    # Should create DynamicREM without error
    rem = create_rem(valid_config)
    assert isinstance(rem, DynamicREM)
    assert rem.breakeven_threshold == 0.75

    # Invalid config type
    try:
        create_rem("invalid_string")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be a dictionary" in str(e)

    # Schema validation failure (if jsonschema available)
    if jsonschema is not None:
        invalid_config = {"name": "Invalid"}  # Missing required fields
        try:
            create_rem(invalid_config)
            assert False, "Should have raised ValueError for schema validation"
        except ValueError as e:
            assert "schema validation failed" in str(e)
