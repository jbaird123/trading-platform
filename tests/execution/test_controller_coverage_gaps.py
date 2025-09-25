# Coverage gaps for execution/controller.py
# Missing lines: 95, 99, 134, 147->125
from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pandas as pd
from trading_platform.execution.controller import reconcile_report, run_live_controller
from trading_platform.portfolio.portfolio import PortfolioManager


def test_controller_reconcile_report_side_mismatch():
    """Test reconcile_report when adapter and portfolio have different sides (line 95)."""
    # Create portfolio manager with a long position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return different side (short)
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "short",  # Different from portfolio (long) - triggers line 95
        "size": 1.0,
    }

    # Call reconcile_report
    diffs = reconcile_report(pm, adapter)

    # Should detect side mismatch
    assert "side_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"
    adapter.account_snapshot.assert_called_once()


def test_controller_reconcile_report_size_mismatch():
    """Test reconcile_report when adapter and portfolio have different sizes (line 99)."""
    # Create portfolio manager with a position of size 1.0
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return different size (2.0)
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",  # Same side
        "size": 2.0,  # Different size from portfolio (1.0) - triggers line 99
    }

    # Call reconcile_report
    diffs = reconcile_report(pm, adapter)

    # Should detect size mismatch
    assert "size_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"
    adapter.account_snapshot.assert_called_once()


def test_controller_reconcile_report_size_none_handling():
    """Test reconcile_report when adapter returns None for size (line 98)."""
    # Create portfolio manager with a position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return None for size
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",
        "size": None,  # This should be converted to 0.0 - tests line 98
    }

    # Call reconcile_report
    diffs = reconcile_report(pm, adapter)

    # Should detect size mismatch (1.0 vs 0.0)
    assert "size_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"


def test_live_controller_flat_with_no_position():
    """Test run_live_controller when desired is flat but no position exists (line 134)."""
    # Create market data
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    vals = [1.0, 1.1, 1.2]
    market_data = pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 3},
        index=idx,
    )

    # Strategy config that has entry rules but should result in flat signals
    strategy_cfg = {
        "strategy_name": "FlatTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 10.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 10.0}]}
        ],
    }

    # Portfolio manager with no position
    pm = PortfolioManager(initial_cash=1000.0)

    # Mock adapter
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.place_order.return_value = Mock(status="accepted")
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    # Run controller
    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )

    # Should continue without placing order when desired is flat and no position - line 134
    adapter.place_order.assert_not_called()

    # Should still have reconcile report at end
    assert any(log.get("event") == "reconcile" for log in result.logs)


def test_live_controller_max_orders_kill_switch():
    """Test run_live_controller kill switch when max_orders reached (branch 147->125)."""
    # Create market data with alternating values to trigger entry/exit/entry
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    vals = [1.0, 0.05, 1.2, 0.05, 1.4]  # high -> low -> high -> low -> high
    market_data = pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 5},
        index=idx,
    )

    # Strategy config that alternates between long and flat
    strategy_cfg = {
        "strategy_name": "AlternatingTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.1}]}
        ],
    }

    # Portfolio manager with initial long position so flat orders can be processed
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    # Mock adapter that accepts orders
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.place_order.return_value = Mock(status="accepted")
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    # Run controller with max_orders=2 to trigger kill switch
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        pm=pm,
        adapter=adapter,
        max_orders=2,  # This should trigger kill switch after 2 orders
    )

    # Should place exactly 2 orders then break due to kill switch
    assert adapter.place_order.call_count == 2

    # Should have kill switch event - tests branch 147->125
    kill_switch_events = [
        log
        for log in result.logs
        if log.get("event") == "shutdown" and log.get("reason") == "kill_switch"
    ]
    assert len(kill_switch_events) == 1


def test_live_controller_empty_market_data():
    """Test run_live_controller with empty market data for mark price calculation."""
    # Empty market data
    market_data = pd.DataFrame()

    strategy_cfg = {
        "strategy_name": "EmptyTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 10.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 10.0}]}
        ],
    }

    pm = PortfolioManager(initial_cash=1000.0)
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    # Run controller
    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )

    # Should handle empty data and still generate reconcile report
    assert any(log.get("event") == "reconcile" for log in result.logs)
