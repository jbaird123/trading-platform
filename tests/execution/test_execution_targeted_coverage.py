"""
Additional execution tests to target remaining coverage gaps with precise scenarios.
"""

from datetime import datetime

import pandas as pd

from trading_platform.execution.controller import run_live_controller
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_controller_continue_with_mixed_signals():
    """Test controller continue statement with mixed flat/long signals."""
    # Market data that creates scenario where flat signal comes with no position
    idx = [datetime(2024, 1, 1, h) for h in range(4)]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0, 3.0, 1.0],  # High, low, high, low
            "high": [3.0, 1.0, 3.0, 1.0],
            "low": [3.0, 1.0, 3.0, 1.0],
            "close": [3.0, 1.0, 3.0, 1.0],  # Above/below threshold
            "volume": [1, 1, 1, 1],
        },
        index=idx,
    )

    # Strategy that alternates long/flat based on close > 2.0
    strategy_cfg = {
        "strategy_name": "AlternatingStrategy",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }

    # Start with no position to trigger continue when flat is desired
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )

    # Should place orders for long signals, but continue for flat when no position
    assert result.orders >= 1


def test_controller_kill_switch_with_position_flipping():
    """Test kill switch with position creation and flipping."""
    # Market data that alternates to create state changes
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0, 3.0, 1.0, 3.0],  # High, low, high, low, high
            "high": [3.0, 1.0, 3.0, 1.0, 3.0],
            "low": [3.0, 1.0, 3.0, 1.0, 3.0],
            "close": [3.0, 1.0, 3.0, 1.0, 3.0],  # Alternating signals
            "volume": [1, 1, 1, 1, 1],
        },
        index=idx,
    )

    # Strategy that alternates long/flat based on threshold
    strategy_cfg = {
        "strategy_name": "AlternatingStrategy",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }

    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)

    # Set max_orders to 2 to trigger kill switch after 2 state changes
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        adapter=adapter,
        pm=pm,
        max_orders=2,
    )

    # Should hit max orders and trigger kill switch
    assert result.orders == 2
    kill_switch_logs = [
        log
        for log in result.logs
        if log.get("event") == "shutdown" and log.get("reason") == "kill_switch"
    ]
    assert len(kill_switch_logs) == 1


def test_oanda_stub_explicit_flat_close():
    """Test explicit flat order closing position."""
    pm = PortfolioManager(initial_cash=1000.0)

    # Create position first
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        size=1.0,
        entry_time=datetime(2024, 1, 1, 10),
    )

    adapter = OandaStubAdapter(pm=pm)

    # Verify position exists before flat order
    assert pm.current_position is not None
    assert pm.current_position.side == "long"

    # Place explicit flat order
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Verify order accepted and position closed
    assert result.status == "accepted"
    assert pm.current_position is None
    assert len(pm.trades) == 1
    assert pm.trades[0].exit_reason == "flat"


def test_controller_flat_then_long_sequence():
    """Test sequence where flat signal comes first (no position), then long."""
    idx = [datetime(2024, 1, 1, h) for h in [10, 11]]
    market_data = pd.DataFrame(
        {
            "open": [1.0, 3.0],  # First low (flat), then high (long)
            "high": [1.0, 3.0],
            "low": [1.0, 3.0],
            "close": [1.0, 3.0],  # Below threshold, then above
            "volume": [1, 1],
        },
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "FlatThenLong",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }

    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )

    # Should place 1 order (for long signal), flat signal continues due to no position
    assert result.orders == 1