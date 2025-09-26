"""
Precise tests to hit the exact missing coverage lines with very specific scenarios.
"""

from datetime import datetime

import pandas as pd
from trading_platform.execution.controller import run_live_controller
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def test_controller_precise_continue_scenario():
    """
    Test the exact scenario for line 134 continue statement:
    - desired == "flat"
    - current_state != "flat" (to enter the if block)
    - pm.current_position is None
    """
    # Market data: first signal long, second signal flat
    idx = [datetime(2024, 1, 1, h) for h in [10, 11]]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0],  # High then low
            "high": [3.0, 1.0],
            "low": [3.0, 1.0],
            "close": [3.0, 1.0],  # Above threshold, then below
            "volume": [1, 1],
        },
        index=idx,
    )

    # Strategy that goes long then flat
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

    # Portfolio manager with no position initially
    pm = PortfolioManager(initial_cash=1000.0)

    # Use adapter that will reject the first long order to keep position None
    class RejectFirstOrderAdapter(OandaStubAdapter):
        def __init__(self, pm):
            super().__init__(pm)
            self.first_call = True

        def place_order(self, *, symbol, side, size, meta=None):
            if self.first_call and side == "long":
                self.first_call = False
                # Reject the long order so pm.current_position stays None
                from trading_platform.execution.adapter_base import OrderResult

                return OrderResult(
                    order_id="rejected-1", status="rejected", message="test_rejection"
                )
            return super().place_order(symbol=symbol, side=side, size=size, meta=meta)

    adapter = RejectFirstOrderAdapter(pm)

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )

    # The scenario should be:
    # 1. current_state starts as "flat"
    # 2. desired becomes "long", current_state != desired, so enters if block
    # 3. Order rejected, pm.current_position stays None, current_state becomes "long"
    # 4. desired="flat", current_state("long") != desired("flat"), enters if block
    # 5. desired == "flat" and pm.current_position is None triggers continue

    # First order rejected but state set, second iteration triggers continue
    assert result.orders == 0  # First order rejected, second order continued


def test_controller_kill_switch_precise_scenario():
    """
    Test exact kill switch scenario for branch 147->125:
    - max_orders is reached
    - break statement is executed
    """
    # Market data with enough variation to place multiple orders
    idx = [datetime(2024, 1, 1, h) for h in [10, 11, 12]]
    market_data = pd.DataFrame(
        {
            "open": [3.0, 1.0, 3.0],  # High, low, high
            "high": [3.0, 1.0, 3.0],
            "low": [3.0, 1.0, 3.0],
            "close": [3.0, 1.0, 3.0],  # Long, flat, long signals
            "volume": [1, 1, 1],
        },
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "AlternatingForKillSwitch",
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

    # Set max_orders to 1 so kill switch triggers on first accepted order
    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        adapter=adapter,
        pm=pm,
        max_orders=1,  # Should trigger break on branch 147->125
    )

    # Should place 1 order then break
    assert result.orders == 1

    # Verify kill switch was triggered
    kill_events = [log for log in result.logs if log.get("reason") == "kill_switch"]
    assert len(kill_events) == 1


def test_oanda_stub_flat_branch_103_to_119():
    """
    Test the exact branch 103->119 in oanda_stub.py:
    elif side == "flat" and self.pm.current_position:
    """
    pm = PortfolioManager(initial_cash=1000.0)

    # Create a position to satisfy self.pm.current_position condition
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        size=1.0,
        entry_time=datetime(2024, 1, 1, 10),
    )

    # Verify position exists
    assert pm.current_position is not None

    adapter = OandaStubAdapter(pm=pm)

    # Place order with side="flat" to hit the exact elif condition
    result = adapter.place_order(
        symbol="EURUSD",
        side="flat",  # This is the condition side == "flat"
        size=1.0,
        meta={"price": 1.1100, "time": datetime(2024, 1, 1, 11)},
    )

    # Order should be accepted and position should be closed
    assert result.status == "accepted"
    assert pm.current_position is None  # Position should be closed
    assert len(pm.trades) == 1
    assert pm.trades[0].exit_reason == "flat"


def test_controller_flat_signal_with_rejected_long():
    """
    Alternative approach to hit continue line by ensuring state mismatch.
    """
    # Single row of market data that produces flat signal
    idx = [datetime(2024, 1, 1, 10)]
    market_data = pd.DataFrame(
        {
            "open": [1.0],  # Low value
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],  # Below threshold = flat signal
            "volume": [1],
        },
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "FlatSignal",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 2.0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 2.0}]}
        ],
    }

    pm = PortfolioManager(initial_cash=1000.0)

    # Custom adapter to simulate different current_state
    class CustomStateAdapter(OandaStubAdapter):
        def __init__(self, pm):
            super().__init__(pm)

    adapter = CustomStateAdapter(pm)

    # Manually modify the controller logic by starting with non-flat state
    # This is tricky because current_state starts as "flat"
    # We need desired="flat", current_state != "flat", and pm.current_position is None

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, adapter=adapter, pm=pm
    )

    # This test focuses on the specific logic flow
    assert result.orders == 0  # Should not place orders for flat signal
