"""
Tests for Trade creation and PnL calculation waterfall.

This module validates the clear, auditable waterfall from ideal PnL
(mid-to-mid price movement) to net PnL after all costs.
"""

from datetime import UTC, datetime

import pandas as pd

from trading_platform.core.costs import CostModel
from trading_platform.portfolio.portfolio import PortfolioManager


def test_pnl_calculation_waterfall():
    """
    Test that PnL calculation follows a clear waterfall:
    1. pnl_movement = exit_mid - entry_mid (pure price movement)
    2. costs = spread + commission + slippage
    3. pnl = pnl_movement - costs
    """
    # Setup: EUR/USD with 2-pip spread, 10k position
    cost_model_config = {
        "spread_per_unit": 0.0002,  # 2 pips
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
        initial_cash=100000.0,
        instrument=instrument,
        cost_model=cost_model_config,
    )

    # Entry at mid-price 1.2010
    entry_mid = 1.2010
    size = 10000.0
    entry_time = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)

    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=entry_mid,
        size=size,
        entry_time=entry_time,
        instrument=instrument,
    )

    # Exit at mid-price 1.2020 (10 pip gain)
    exit_mid = 1.2020
    exit_time = datetime(2023, 1, 1, 13, 0, tzinfo=UTC)

    pm.close_position(
        exit_price=exit_mid,
        exit_time=exit_time,
        exit_reason="test",
    )

    # Verify waterfall
    assert len(pm.trades) == 1
    trade = pm.trades[0]

    # Step 1: Calculate expected pnl_movement (mid-to-mid)
    expected_movement = (exit_mid - entry_mid) * size * 1.0  # point_value=1.0
    assert trade.pnl_movement == expected_movement  # $10.00

    # Step 2: Verify spread cost (2 pips on 10k units)
    expected_spread = 0.0002 * size  # $2.00
    assert trade.cost_breakdown["spread"] == expected_spread

    # Step 3: Verify total costs
    expected_total_cost = expected_spread  # No commission/slippage
    assert trade.cost_currency == expected_total_cost

    # Step 4: Verify final PnL = movement - costs
    expected_pnl = expected_movement - expected_total_cost  # $10 - $2 = $8
    assert trade.pnl == expected_pnl


def test_pnl_waterfall_with_loss():
    """Test PnL waterfall for a losing trade."""
    cost_model_config = {
        "spread_per_unit": 0.0002,  # 2 pips
        "slippage_per_unit": 0.0001,  # 1 pip slippage per side
        "commission": {"type": "per_unit", "value": 0.5},  # $0.50 per unit
    }
    instrument = {
        "symbol": "EURUSD",
        "asset_class": "Forex",
        "point_value": 1.0,
        "pip_location": 0.0001,
    }

    pm = PortfolioManager(
        initial_cash=100000.0,
        instrument=instrument,
        cost_model=cost_model_config,
    )

    # Entry at 1.2010, exit at 1.2000 (10 pip loss)
    entry_mid = 1.2010
    exit_mid = 1.2000
    size = 10000.0

    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=entry_mid,
        size=size,
        entry_time=datetime(2023, 1, 1, 12, 0, tzinfo=UTC),
        instrument=instrument,
    )

    pm.close_position(
        exit_price=exit_mid,
        exit_time=datetime(2023, 1, 1, 13, 0, tzinfo=UTC),
        exit_reason="stop-loss",
    )

    trade = pm.trades[0]

    # Movement: -10 pips = -$10.00
    expected_movement = (exit_mid - entry_mid) * size * 1.0
    assert trade.pnl_movement == expected_movement  # -$10.00

    # Costs breakdown
    spread_cost = 0.0002 * size  # $2.00
    slippage_cost = 0.0001 * size * 2  # $1.00 entry + $1.00 exit = $2.00
    commission_cost = 0.5 * size * 2  # $5000 entry + $5000 exit = $10000
    total_cost = spread_cost + slippage_cost + commission_cost  # $10,004.00

    assert trade.cost_breakdown["spread"] == spread_cost
    assert trade.cost_breakdown["slippage"] == slippage_cost
    assert trade.cost_breakdown["commission"] == commission_cost
    assert trade.cost_currency == total_cost

    # Final PnL = -$10.00 - $10,004.00 = -$10,014.00
    expected_pnl = expected_movement - total_cost
    assert trade.pnl == expected_pnl
