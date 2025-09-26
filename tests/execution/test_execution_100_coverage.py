"""
Comprehensive test coverage for execution/controller.py and execution/oanda_stub.py.

This file targets the specific missing lines and branches identified in coverage:

Controller.py:
- Line 95: diffs.append("side_mismatch") in reconcile function (not reconcile_report)
- Line 99: diffs.append("size_mismatch") in reconcile function (not reconcile_report)
- Line 134: continue statement when desired == "flat" and no position
- Branch 147->125: kill switch break when max_orders reached

Oanda_stub.py:
- Branch 103->119: elif side == "flat" and self.pm.current_position condition
"""

from datetime import datetime
from unittest.mock import Mock

import pandas as pd
from trading_platform.execution.controller import reconcile, run_live_controller
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_reconcile_function_side_mismatch_line_95():
    """Test reconcile function (not reconcile_report) side mismatch to hit line 95."""
    # Create portfolio manager with a long position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return different side (short)
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "short",  # Different from portfolio (long) - triggers line 95
        "size": 1.0,
    }

    # Call reconcile function (not reconcile_report)
    diffs = reconcile(pm, adapter)

    # Should detect side mismatch - line 95: diffs.append("side_mismatch")
    assert "side_mismatch" in diffs
    adapter.account_snapshot.assert_called_once()


def test_reconcile_function_size_mismatch_line_99():
    """Test reconcile function (not reconcile_report) size mismatch to hit line 99."""
    # Create portfolio manager with a position of size 1.0
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return same side but different size
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",  # Same side
        "size": 2.0,  # Different size from portfolio (1.0) - triggers line 99
    }

    # Call reconcile function (not reconcile_report)
    diffs = reconcile(pm, adapter)

    # Should detect size mismatch - line 99: diffs.append("size_mismatch")
    assert "size_mismatch" in diffs
    adapter.account_snapshot.assert_called_once()


def test_reconcile_function_no_mismatches():
    """Test reconcile function when everything matches."""
    # Create portfolio manager with a position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter to return matching values
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",  # Same side
        "size": 1.0,  # Same size
    }

    # Call reconcile function
    diffs = reconcile(pm, adapter)

    # Should have no mismatches
    assert diffs == []
    adapter.account_snapshot.assert_called_once()


def test_live_controller_flat_continue_line_134():
    """Test run_live_controller continue when desired='flat' and no position."""
    # Use same setup as test_controller_flat_continue.py
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    market_data = pd.DataFrame(
        {
            "open": [1, 1, 1],
            "high": [1, 1, 1],
            "low": [1, 1, 1],
            "close": [1, 1, 1],
            "volume": [1, 1, 1],
        },
        index=idx,
    )

    # Strategy config that produces flat signals (close=1 is not > 2.0)
    strategy_cfg = {
        "strategy_name": "FlatAlways",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }

    # Portfolio manager with no position
    pm = PortfolioManager(initial_cash=1000.0)
    assert pm.current_position is None  # Ensure no position

    # Use real OandaStubAdapter (not mock) to match working test
    adapter = OandaStubAdapter(pm=pm)

    # Run controller
    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )

    # Should not place any orders due to continue statement (line 134)
    # When desired="flat" and pm.current_position is None, continue is executed
    assert result.orders == 0


def test_live_controller_kill_switch_branch_147_to_125():
    """Test run_live_controller kill switch break to hit branch 147->125."""
    # Create market data that will trigger long signals
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    vals = [3.0, 3.0, 3.0]  # High values to trigger long signals
    market_data = pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 3},
        index=idx,
    )

    # Strategy config that produces long signals (close=3.0 > 2.0)
    strategy_cfg = {
        "strategy_name": "LongSignals",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }

    # Portfolio manager starts flat
    pm = PortfolioManager(initial_cash=1000.0)

    # Use real OandaStubAdapter that accepts orders
    adapter = OandaStubAdapter(pm=pm)

    # Run controller with max_orders=1 to trigger kill switch after first order
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        pm=pm,
        adapter=adapter,
        max_orders=1,  # This will trigger break after 1 order (branch 147->125)
    )

    # Should place exactly 1 order then break
    assert result.orders == 1

    # Should have kill switch event in logs
    kill_switch_logs = [
        log
        for log in result.logs
        if log.get("event") == "shutdown" and log.get("reason") == "kill_switch"
    ]
    assert len(kill_switch_logs) == 1


def test_oanda_stub_flat_with_position_branch_103_to_119():
    """Test OandaStubAdapter flat order with existing position."""
    # Create portfolio manager with an existing long position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 10))

    # Verify position exists
    assert pm.current_position is not None
    assert pm.current_position.side == "long"
    assert len(pm.trades) == 0  # No completed trades yet

    # Create OandaStubAdapter
    adapter = OandaStubAdapter(pm)

    # Place order with side="flat" to hit branch 103->119
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",  # This triggers: elif side == "flat" and self.pm.current_position
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted
    assert result.status == "accepted"
    assert result.message == "stub"

    # Position should be closed (branch 103->119)
    assert pm.current_position is None

    # Should have one completed trade
    assert len(pm.trades) == 1
    assert pm.trades[0].exit_reason == "flat"
    assert pm.trades[0].exit_price == 1.1100


def test_oanda_stub_flat_without_position():
    """Test OandaStubAdapter flat order without position."""
    # Create portfolio manager without position
    pm = PortfolioManager(initial_cash=1000.0)

    # Verify no position exists
    assert pm.current_position is None

    # Create OandaStubAdapter
    adapter = OandaStubAdapter(pm)

    # Place order with side="flat" - should not trigger branch 103->119
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted but no position operations
    assert result.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 0


def test_reconcile_function_both_mismatches():
    """Test reconcile function with both side and size mismatches."""
    # Create portfolio manager with a position
    pm = PortfolioManager(initial_cash=1000.0)
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    # Mock adapter with both side and size mismatches
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "short",  # Side mismatch
        "size": 2.0,  # Size mismatch
    }

    # Call reconcile function
    diffs = reconcile(pm, adapter)

    # Should detect both mismatches (lines 95 and 99)
    assert "side_mismatch" in diffs
    assert "size_mismatch" in diffs
    assert len(diffs) == 2


def test_reconcile_function_no_position_vs_adapter_position():
    """Test reconcile function when portfolio has no position but adapter does."""
    # Create portfolio manager with no position
    pm = PortfolioManager(initial_cash=1000.0)
    assert pm.current_position is None

    # Mock adapter with a position
    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",  # Portfolio has None (no position)
        "size": 1.0,
    }

    # Call reconcile function
    diffs = reconcile(pm, adapter)

    # Should detect side mismatch (None vs "long") and size mismatch (0.0 vs 1.0)
    assert "side_mismatch" in diffs
    assert "size_mismatch" in diffs
