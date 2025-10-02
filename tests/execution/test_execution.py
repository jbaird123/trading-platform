"""Tests for execution layer.

# Validates: [EX-8.1], [EX-8.2]
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pandas as pd
from trading_platform.execution.controller import reconcile, run_live_controller
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_reconcile_function_side_mismatch():
    """Test reconcile function side mismatch."""
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))
    adapter = Mock()
    adapter.account_snapshot.return_value = {"open_side": "short", "size": 1.0}
    diffs = reconcile(pm, adapter)
    assert "side_mismatch" in diffs


def test_reconcile_function_size_mismatch():
    """Test reconcile function size mismatch."""
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))
    adapter = Mock()
    adapter.account_snapshot.return_value = {"open_side": "long", "size": 2.0}
    diffs = reconcile(pm, adapter)
    assert "size_mismatch" in diffs


def test_reconcile_function_no_mismatches():
    """Test reconcile function when everything matches."""
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))
    adapter = Mock()
    adapter.account_snapshot.return_value = {"open_side": "long", "size": 1.0}
    diffs = reconcile(pm, adapter)
    assert diffs == []


def test_reconcile_function_both_mismatches():
    """Test reconcile function with both side and size mismatches."""
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))
    adapter = Mock()
    adapter.account_snapshot.return_value = {"open_side": "short", "size": 2.0}
    diffs = reconcile(pm, adapter)
    assert "side_mismatch" in diffs
    assert "size_mismatch" in diffs


def test_reconcile_function_no_position_vs_adapter_position():
    """Test reconcile when portfolio is flat but adapter has a position."""
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = Mock()
    adapter.account_snapshot.return_value = {"open_side": "long", "size": 1.0}
    diffs = reconcile(pm, adapter)
    assert "side_mismatch" in diffs
    assert "size_mismatch" in diffs


def test_live_controller_flat_continue():
    """Test run_live_controller continues when desired='flat' and no position."""
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    market_data = pd.DataFrame(
        {
            "open": [1] * 3,
            "high": [1] * 3,
            "low": [1] * 3,
            "close": [1] * 3,
            "volume": [100] * 3,
        },
        index=idx,
    )
    strategy_cfg = {
        "strategy_name": "FlatAlways",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )
    assert result.orders == 0


def test_live_controller_kill_switch():
    """Test run_live_controller kill switch break."""
    idx = [datetime(2024, 1, 1, 10)]
    market_data = pd.DataFrame(
        {
            "open": [3.0],
            "high": [3.0],
            "low": [3.0],
            "close": [3.0],
            "volume": [100],
        },
        index=idx,
    )
    strategy_cfg = {
        "strategy_name": "LongSignal",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        pm=pm,
        adapter=adapter,
        max_orders=1,
    )
    assert result.orders == 1
    assert any(log.get("reason") == "kill_switch" for log in result.logs)


def test_oanda_stub_flat_with_position():
    """Test OandaStubAdapter flat order with an existing position."""
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 10))
    adapter = OandaStubAdapter(pm)
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )
    assert result.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 1


def test_oanda_stub_flat_without_position():
    """Test OandaStubAdapter flat order without an existing position."""
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm)
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )
    assert result.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 0


def test_controller_precise_continue_with_rejected_order():
    """Test continue statement with a rejected order scenario."""
    idx = [datetime(2024, 1, 1, h) for h in [10, 11]]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0],
            "high": [3.0, 1.0],
            "low": [3.0, 1.0],
            "close": [3.0, 1.0],
            "volume": [100, 100],
        },
        index=idx,
    )
    strategy_cfg = {
        "strategy_name": "LongThenFlat",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }
    pm = PortfolioManager(initial_cash=1000.0)

    class RejectLongAdapter(OandaStubAdapter):
        def place_order(self, *, symbol, side, size, meta=None):
            if side == "enter_long":
                from trading_platform.execution.adapter_base import OrderResult

                return OrderResult(
                    order_id="rejected", status="rejected", message="test"
                )
            return super().place_order(symbol=symbol, side=side, size=size, meta=meta)

    adapter = RejectLongAdapter(pm)
    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )
    assert result.orders == 0
    assert pm.current_position is None
