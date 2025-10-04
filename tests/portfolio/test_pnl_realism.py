"""
Test unrealized PnL calculation for open positions.

This ensures that unrealized PnL correctly reflects the full spread
cost, mimicking live broker behavior.
"""

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.portfolio.portfolio import PortfolioManager


def test_unrealized_pnl_reflects_full_spread():
    """
    Verify that unrealized PnL on an open position accounts for the
    full spread cost.

    When a position is opened and then updated with new bar data,
    the unrealized_pnl should be calculated using the exit price
    (which includes spread), not the mid-price.
    """
    # Create a cost model with a known spread (2 pips = 0.0002)
    cost_model_config = {
        "spread_per_unit": 0.0001,  # 1 pip spread per unit
        "slippage_per_unit": 0.0,
        "commission": {"type": "per_unit", "value": 0.0},
    }
    instrument = {
        "symbol": "EURUSD",
        "asset_class": "Forex",
        "point_value": 1.0,
        "pip_location": 0.0001,
    }

    # Create portfolio manager
    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=10000.0,
        cost_model=cost_model_config,
        instrument=instrument,
    )

    # Open a long position at mid-price 1.1005
    entry_time = datetime(2025, 1, 1, 10, 0)
    # Entry price for long = 1.1005 + spread/2 = 1.10055
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1005,
        size=10000,
        entry_time=entry_time,
        instrument=instrument,
    )

    assert pm.current_position is not None
    assert pm.current_position.entry_mid_price == 1.1005
    # Entry price is ask price for long
    assert pm.current_position.entry_price == pytest.approx(1.10055, abs=1e-6)

    # Update with a new bar where mid-price moves to 1.1015
    update_time = datetime(2025, 1, 1, 10, 5)
    update_bar = pd.Series(
        {
            "open": 1.1010,
            "high": 1.1020,
            "low": 1.1005,
            "close": 1.1015,
            "volume": 1000,
        },
        name=update_time,
    )

    # Update position metrics
    pm._update_position_metrics(update_bar)

    # Calculate expected unrealized PnL
    # Exit price for long = bid price = 1.1015 - spread/2 = 1.10145
    # Unrealized = (1.10145 - 1.10055) * 10000 = 9.0
    expected_unrealized_pnl = (1.10145 - 1.10055) * 10000

    assert pm.current_position.unrealized_pnl == pytest.approx(
        expected_unrealized_pnl, abs=1e-2
    )

    # Verify it's positive (profit) but less than pure mid-to-mid
    mid_to_mid_pnl = (1.1015 - 1.1005) * 10000  # 100.0
    assert pm.current_position.unrealized_pnl < mid_to_mid_pnl
    assert pm.current_position.unrealized_pnl > 0


def test_unrealized_pnl_for_short_position():
    """
    Verify unrealized PnL calculation for short positions.
    """
    cost_model_config = {
        "spread_per_unit": 0.0001,
        "slippage_per_unit": 0.0,
        "commission": {"type": "per_unit", "value": 0.0},
    }
    instrument = {
        "symbol": "EURUSD",
        "asset_class": "Forex",
        "point_value": 1.0,
        "pip_location": 0.0001,
    }

    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=10000.0,
        cost_model=cost_model_config,
        instrument=instrument,
    )

    # Open a short position at mid-price 1.1005
    entry_time = datetime(2025, 1, 1, 10, 0)
    # Entry price for short = 1.1005 - spread/2 = 1.10045
    pm.create_new_position(
        symbol="EURUSD",
        side="short",
        entry_price=1.1005,
        size=10000,
        entry_time=entry_time,
        instrument=instrument,
    )

    assert pm.current_position is not None
    assert pm.current_position.entry_mid_price == 1.1005
    assert pm.current_position.entry_price == pytest.approx(1.10045, abs=1e-6)

    # Update with a new bar where mid-price moves to 1.0995 (down)
    update_time = datetime(2025, 1, 1, 10, 5)
    update_bar = pd.Series(
        {
            "open": 1.1000,
            "high": 1.1005,
            "low": 1.0990,
            "close": 1.0995,
            "volume": 1000,
        },
        name=update_time,
    )

    pm._update_position_metrics(update_bar)

    # Calculate expected unrealized PnL
    # Exit price for short = ask price = 1.0995 + spread/2 = 1.09955
    # Unrealized = (1.10045 - 1.09955) * 10000 = 9.0
    expected_unrealized_pnl = (1.10045 - 1.09955) * 10000

    assert pm.current_position.unrealized_pnl == pytest.approx(
        expected_unrealized_pnl, abs=1e-2
    )

    # Verify it's positive (profit) but less than pure mid-to-mid
    mid_to_mid_pnl = (1.1005 - 1.0995) * 10000  # 100.0
    assert pm.current_position.unrealized_pnl < mid_to_mid_pnl
    assert pm.current_position.unrealized_pnl > 0


def test_unrealized_pnl_negative_when_losing():
    """
    Verify unrealized PnL is negative when position is losing.
    """
    cost_model_config = {
        "spread_per_unit": 0.0001,
        "slippage_per_unit": 0.0,
        "commission": {"type": "per_unit", "value": 0.0},
    }
    instrument = {
        "symbol": "EURUSD",
        "asset_class": "Forex",
        "point_value": 1.0,
        "pip_location": 0.0001,
    }

    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=10000.0,
        cost_model=cost_model_config,
        instrument=instrument,
    )

    # Open a long position
    entry_time = datetime(2025, 1, 1, 10, 0)
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1005,
        size=10000,
        entry_time=entry_time,
        instrument=instrument,
    )

    # Update with a new bar where mid-price moves down to 1.0995
    update_time = datetime(2025, 1, 1, 10, 5)
    update_bar = pd.Series(
        {
            "open": 1.1000,
            "high": 1.1005,
            "low": 1.0990,
            "close": 1.0995,
            "volume": 1000,
        },
        name=update_time,
    )

    pm._update_position_metrics(update_bar)

    # Should be negative since price moved down
    assert pm.current_position is not None
    assert pm.current_position.unrealized_pnl < 0
