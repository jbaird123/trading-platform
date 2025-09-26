"""
Final attempt to hit the exact missing coverage lines with precise state management.
"""

from datetime import datetime

import pandas as pd
from trading_platform.execution.controller import run_live_controller
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_continue_line_134_exact_scenario():
    """
    Hit line 134 continue statement exactly:
    1. First signal: long (current_state becomes "long", but order fails)
    2. Second signal: flat (desired="flat", pm.current_position=None -> continue)
    """
    # Market data: first high (long signal), then low (flat signal)
    idx = [datetime(2024, 1, 1, h) for h in [10, 11]]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0],
            "high": [3.0, 1.0],
            "low": [3.0, 1.0],
            "close": [3.0, 1.0],  # Above threshold, then below
            "volume": [1, 1],
        },
        index=idx,
    )

    # Strategy: long above 2.0, flat below 2.0
    strategy_cfg = {
        "strategy_name": "LongThenFlat",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }

    pm = PortfolioManager(initial_cash=1000.0)

    # Custom adapter that rejects long orders but allows state change
    class RejectLongAdapter(OandaStubAdapter):
        def place_order(self, *, symbol, side, size, meta=None):
            if side == "long":
                # Reject the long order so pm.current_position stays None
                from trading_platform.execution.adapter_base import OrderResult

                return OrderResult(
                    order_id="rejected", status="rejected", message="test_rejection"
                )
            return super().place_order(symbol=symbol, side=side, size=size, meta=meta)

    adapter = RejectLongAdapter(pm)

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )

    # Expected flow:
    # 1. desired="long", current_state="flat" -> order rejected, state="long"
    # 2. desired="flat", current_state="long" -> hits continue at line 134
    assert result.orders == 0
    assert pm.current_position is None


def test_kill_switch_branch_147_to_125_exact():
    """
    Hit the exact break statement for kill switch (branch 147->125).
    Need to place exactly max_orders, then trigger break.
    """
    # Single data point to trigger one order attempt
    idx = [datetime(2024, 1, 1, 10)]
    market_data = pd.DataFrame(
        {
            "open": [3.0],
            "high": [3.0],
            "low": [3.0],
            "close": [3.0],  # Above threshold = long signal
            "volume": [1],
        },
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "LongSignal",
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

    # Set max_orders to 1 and provide data that would place 1 order
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        adapter=adapter,
        pm=pm,
        max_orders=1,
    )

    # Should place 1 order, then break due to kill switch
    assert result.orders == 1
    kill_logs = [log for log in result.logs if log.get("reason") == "kill_switch"]
    assert len(kill_logs) == 1


def test_oanda_stub_branch_103_to_119_exact():
    """
    Hit exact elif branch 103->119 in oanda_stub.py:
    elif side == "flat" and self.pm.current_position:
    """
    pm = PortfolioManager(initial_cash=1000.0)

    # Create position first
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        size=1.0,
        entry_time=datetime(2024, 1, 1, 10),
    )

    assert pm.current_position is not None

    adapter = OandaStubAdapter(pm=pm)

    # Place flat order to hit elif side == "flat" and self.pm.current_position
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    assert result.status == "accepted"
    assert pm.current_position is None  # Position should be closed
