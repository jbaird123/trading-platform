# Validates: [BT-7.4], [NOTE-14.9]
from __future__ import annotations

from pytest import approx
from trading_platform.core.costs import CostModel


def test_get_entry_and_exit_prices():
    cm = CostModel.from_dict({"spread_per_unit": 0.0002})
    mid_price = 1.1000

    # Long trade
    assert cm.get_entry_price(mid_price, "long") == approx(1.1001)  # mid + spread/2
    assert cm.get_exit_price(mid_price, "long") == approx(1.0999)  # mid - spread/2

    # Short trade
    assert cm.get_entry_price(mid_price, "short") == approx(1.0999)  # mid - spread/2
    assert cm.get_exit_price(mid_price, "short") == approx(1.1001)  # mid + spread/2


def test_compute_spread_cost():
    cm = CostModel.from_dict({"spread_per_unit": 0.01})
    cost = cm.compute_spread_cost(size=100)
    assert cost == 1.0  # 0.01 * 100


def test_commission_per_unit_mode():
    cm = CostModel.from_dict(
        {
            "spread_per_unit": 0.01,
            "slippage_per_unit": 0.02,
            "commission": {"type": "per_unit", "value": 0.05},
        }
    )
    total, bd = cm.compute_entry_cost(size=100, price=10.0)
    assert bd["spread"] == 0.0  # Spread is not in breakdown from compute_*_cost
    assert bd["slippage"] == 2.0  # 0.02 * 100
    assert bd["commission"] == 5.0  # 0.05 * 100
    assert total == 7.0  # Slippage + Commission


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
    # units = 0.1; slippage=0.02, commission=0.2; total=0.22
    # spread is not included in this calculation
    assert bd["spread"] == approx(0.0)
    assert bd["slippage"] == approx(0.02)
    assert bd["commission"] == approx(0.2)
    assert total == approx(0.22)


def test_bps_notional_commission_ignores_lot_size():
    # bps uses price*size; lot_size should not affect commission
    cm = CostModel.from_dict({"commission": {"type": "bps_notional", "value": 10.0}})
    instrument = {"lot_size": 100_000}
    # size=10_000, price=2.0 => notional=20_000; 10 bps => 20_000 * 0.001 = 20
    total, bd = cm.compute_entry_cost(size=10_000, price=2.0, instrument=instrument)
    assert bd["commission"] == 20.0
    assert total == 20.0


def test_from_dict_invalid_values_coerce_to_defaults():
    # Provide invalid strings; _as_float should coerce to defaults without raising
    cm = CostModel.from_dict(
        {
            "spread_per_unit": "oops",
            "slippage_per_unit": "oops",
            "commission": {"type": "per_unit", "value": "oops"},
        }
    )
    total, bd = cm.compute_entry_cost(size=10, price=1.0)
    assert bd == {"spread": 0.0, "commission": 0.0, "slippage": 0.0}
    assert total == 0.0


def test_unknown_commission_type_falls_back_to_zero():
    cm = CostModel.from_dict(
        {
            "spread_per_unit": 0.1,
            "slippage_per_unit": 0.2,
            "commission": {"type": "unknown", "value": 999.0},
        }
    )
    total, bd = cm.compute_entry_cost(size=10, price=1.0)
    # commission should be zero; only slippage contributes
    # spread is not included in this calculation
    assert bd["commission"] == approx(0.0)
    assert bd["spread"] == approx(0.0)
    assert bd["slippage"] == approx(2.0)
    assert total == approx(2.0)


def test_effective_units_bad_lot_size_returns_size():
    from trading_platform.core.costs import effective_units

    size = 1234.0
    units = effective_units(size, {"lot_size": "bad"})
    assert units == size
