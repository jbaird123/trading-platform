from __future__ import annotations

from trading_platform.core.costs import CostModel


def test_commission_per_unit_mode():
    cm = CostModel.from_dict(
        {
            "spread_per_unit": 0.01,
            "slippage_per_unit": 0.02,
            "commission": {"type": "per_unit", "value": 0.05},
        }
    )
    total, bd = cm.compute_entry_cost(size=100, price=10.0)
    assert bd["spread"] == 1.0  # 0.01 * 100
    assert bd["slippage"] == 2.0  # 0.02 * 100
    assert bd["commission"] == 5.0  # 0.05 * 100
    assert total == 8.0


def test_commission_per_trade_flat_mode():
    cm = CostModel.from_dict({"commission": {"type": "per_trade_flat", "value": 1.25}})
    total, bd = cm.compute_entry_cost(size=10, price=50.0)
    assert bd["commission"] == 1.25
    assert bd["spread"] == 0.0 and bd["slippage"] == 0.0
    assert total == 1.25


def test_commission_bps_notional_mode():
    cm = CostModel.from_dict({"commission": {"type": "bps_notional", "value": 10.0}})
    # notional = 50 * 100 = 5000; 10 bps => 5000 * 0.001 = 5.0
    total, bd = cm.compute_entry_cost(size=100, price=50.0)
    assert bd["commission"] == 5.0
    assert total == 5.0


def test_rejects_legacy_commission_per_unit_key():
    try:
        CostModel.from_dict({"commission_per_unit": 0.01})
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Unsupported key 'commission_per_unit'" in str(e)


def test_per_unit_costs_scale_by_lot_size():
    # lot_size scales units: size 10_000 with lot 100_000 => 0.1 units
    cm = CostModel.from_dict(
        {
            "spread_per_unit": 0.5,
            "slippage_per_unit": 0.2,
            "commission": {"type": "per_unit", "value": 2.0},
        }
    )
    instrument = {"lot_size": 100_000}
    total, bd = cm.compute_entry_cost(size=10_000, price=1.2345, instrument=instrument)
    # units = 0.1; spread=0.05, slippage=0.02, commission=0.2; total=0.27
    from pytest import approx

    assert bd["spread"] == approx(0.05)
    assert bd["slippage"] == approx(0.02)
    assert bd["commission"] == approx(0.2)
    assert total == approx(0.27)


def test_bps_notional_commission_ignores_lot_size():
    # bps uses price*size; lot_size should not affect commission
    cm = CostModel.from_dict({"commission": {"type": "bps_notional", "value": 10.0}})
    instrument = {"lot_size": 100_000}
    # size=10_000, price=2.0 => notional=20_000; 10 bps => 20_000 * 0.001 = 20
    total, bd = cm.compute_entry_cost(size=10_000, price=2.0, instrument=instrument)
    assert bd["commission"] == 20.0
    assert total == 20.0
