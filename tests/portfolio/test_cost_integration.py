# Validates: [PM-5.6], [BT-7.4]
from __future__ import annotations

from datetime import datetime

from pytest import approx
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.reporting.brief import compute_costs_aggregate


def test_portfolio_cost_breakdown_and_aggregate_with_lot_scaling():
    # Instrument with lot_size so per-unit costs scale by effective units
    instrument = {"symbol": "FX", "lot_size": 100_000}
    cost_model = {
        "spread_per_unit": 0.5,  # per side
        "slippage_per_unit": 0.2,  # per side
        "commission": {"type": "per_unit", "value": 2.0},  # per side
    }
    pm = PortfolioManager(
        initial_cash=0.0, instrument=instrument, cost_model=cost_model
    )

    # Open position: size 10k units with lot 100k => 0.1 units
    entry_time = datetime(2024, 1, 1, 0, 0)
    exit_time = datetime(2024, 1, 1, 1, 0)
    pm.create_new_position(
        symbol="FX",
        side="long",
        entry_price=1.0,
        size=10_000.0,
        entry_time=entry_time,
        instrument=instrument,
    )

    # Close position;
    # Mid-price pnl_gross = (1.05 - 1.0) * 10_000 = 500
    # We only check costs here, not pnl_gross
    pm.close_position(
        exit_price=1.05, exit_time=exit_time, exit_reason="signal", context_at_exit=None
    )

    assert len(pm.trades) == 1
    t = pm.trades[0]
    # Per side costs: slippage=0.02, commission=0.2
    # Spread cost (round trip) = 0.05
    # Total cost = spread + 2*slippage + 2*commission = 0.05 + 0.04 + 0.4 = 0.49
    assert t.cost_breakdown is not None
    assert t.cost_breakdown["spread"] == approx(0.05)
    assert t.cost_breakdown["slippage"] == approx(0.04)  # Both sides
    assert t.cost_breakdown["commission"] == approx(0.4)  # Both sides
    assert t.cost_currency == approx(0.49)

    agg = compute_costs_aggregate(pm.trades)
    assert agg is not None
    assert agg["total_costs"] == approx(0.49)
    assert agg["avg_cost_per_trade"] == approx(0.49)
    assert agg["breakdown"] == {
        "spread": approx(0.05),
        "commission": approx(0.4),
        "slippage": approx(0.04),
    }


def test_spread_impacts_pnl_via_fill_price():
    """Verify that spread correctly impacts PnL via adjusted fill prices."""
    instrument = {"symbol": "EURUSD", "point_value": 1.0}
    cost_model = {
        "spread_per_unit": 0.0002,
        "slippage_per_unit": 0.0,
        "commission": {"type": "per_unit", "value": 0.0},
    }
    pm = PortfolioManager(
        initial_cash=100_000.0, instrument=instrument, cost_model=cost_model
    )

    # 1. Create Position
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,  # Mid-price
        size=10_000.0,
        entry_time=datetime(2024, 1, 1, 0, 0),
        instrument=instrument,
    )

    # Entry fill price should be higher due to spread
    assert pm.current_position is not None
    assert pm.current_position.entry_price == approx(1.1001)  # 1.1000 + 0.0002/2

    # 2. Close Position
    pm.close_position(
        exit_price=1.1010,  # Mid-price
        exit_time=datetime(2024, 1, 1, 1, 0),
        exit_reason="signal",
    )

    assert len(pm.trades) == 1
    trade = pm.trades[0]

    # Exit fill price should be lower due to spread
    assert trade.exit_price == approx(1.1009)  # 1.1010 - 0.0002/2

    # 3. Verify PnL
    # Gross PnL is based on actual fill prices
    # (1.1009 - 1.1001) * 10_000 = 0.0008 * 10_000 = 8.0
    assert trade.pnl_gross == approx(8.0)

    # Net PnL (no other costs in this test)
    assert trade.pnl == approx(8.0)

    # 4. Verify Cost Reporting
    # The cost breakdown should still report the impact of the spread
    assert trade.cost_breakdown is not None
    assert trade.cost_breakdown["spread"] == approx(2.0)  # 0.0002 * 10_000
    assert trade.cost_breakdown["commission"] == approx(0.0)
    assert trade.cost_breakdown["slippage"] == approx(0.0)
    assert trade.cost_currency == approx(2.0)

    # 5. Verify Final Cash
    # initial_cash + net_pnl
    assert pm.cash == approx(100_000.0 + 8.0)
