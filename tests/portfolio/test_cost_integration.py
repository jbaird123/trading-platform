# Validates: [PM-5.6], [BT-7.4]
from __future__ import annotations

from datetime import datetime

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

    # Close position; net pnl_gross = (1.05-1.0)*10_000 = 500
    # We only check costs here, not pnl_gross
    pm.close_position(
        exit_price=1.05, exit_time=exit_time, exit_reason="signal", context_at_exit=None
    )

    assert len(pm.trades) == 1
    t = pm.trades[0]
    # Per side costs: spread=0.05, slippage=0.02, commission=0.2; round-trip doubles
    from pytest import approx

    assert t.cost_breakdown is not None
    assert t.cost_breakdown["spread"] == approx(0.1)
    assert t.cost_breakdown["slippage"] == approx(0.04)
    assert t.cost_breakdown["commission"] == approx(0.4)
    assert t.cost_currency == approx(0.54)  # 0.27 per side * 2

    agg = compute_costs_aggregate(pm.trades)
    assert agg is not None
    assert agg["total_costs"] == approx(0.54)
    assert agg["avg_cost_per_trade"] == approx(0.54)
    assert agg["breakdown"] == {
        "spread": approx(0.1),
        "commission": approx(0.4),
        "slippage": approx(0.04),
    }
