"""Tests for exit simulation logic."""

from datetime import datetime, timezone

import pandas as pd
import pytest
from trading_platform.backtester.analysis.exit_simulation import (
    run_single_trade_simulation,
)
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.models.exit_analysis import SimulatedHold


@pytest.fixture
def long_trade():
    """Create a sample long trade for testing."""
    return Trade(
        symbol="USDJPY",
        entry_time=datetime(2025, 8, 12, 15, 0, tzinfo=timezone.utc),
        exit_time=datetime(2025, 8, 13, 3, 0, tzinfo=timezone.utc),
        entry_price=147.80,
        exit_price=148.08,
        side="long",
        size=10000.0,
        pnl=15.0,
        exit_reason="opposite_signal",
        stop_loss=147.30,  # 50 pips below entry
        take_profit=148.30,  # 50 pips above entry
        pnl_movement=17.0,
        cost_currency=2.0,
        bars_held=23,
    )


@pytest.fixture
def short_trade():
    """Create a sample short trade for testing."""
    return Trade(
        symbol="USDJPY",
        entry_time=datetime(2025, 8, 15, 3, 0, tzinfo=timezone.utc),
        exit_time=datetime(2025, 8, 15, 18, 0, tzinfo=timezone.utc),
        entry_price=147.28,
        exit_price=147.24,
        side="short",
        size=10000.0,
        pnl=2.5,
        exit_reason="opposite_signal",
        stop_loss=147.78,  # 50 pips above entry
        take_profit=146.78,  # 50 pips below entry
        pnl_movement=3.5,
        cost_currency=1.0,
        bars_held=29,
    )


@pytest.fixture
def price_data_hits_stop_loss():
    """
    Price data where a long trade hits stop-loss on bar 3.

    Trade exit at 148.08, stop-loss at 147.30.
    Bar 3 has low=147.20, which triggers the stop.
    """
    data = pd.DataFrame(
        {
            "open": [148.10, 148.05, 147.90, 147.25, 147.40],
            "high": [148.15, 148.10, 148.00, 147.30, 147.50],
            "low": [148.00, 147.90, 147.80, 147.20, 147.35],
            "close": [148.08, 147.95, 147.85, 147.28, 147.45],
        },
        index=pd.date_range(
            "2025-08-13 03:30:00",
            periods=5,
            freq="30min",
            tz=timezone.utc,
        ),
    )
    return data


@pytest.fixture
def price_data_hits_take_profit():
    """
    Price data where a long trade hits take-profit on bar 2.

    Trade exit at 148.08, take-profit at 148.30.
    Bar 2 has high=148.35, which triggers the TP.
    """
    data = pd.DataFrame(
        {
            "open": [148.10, 148.20, 148.32, 148.25, 148.20],
            "high": [148.15, 148.25, 148.35, 148.30, 148.25],
            "low": [148.05, 148.15, 148.25, 148.20, 148.15],
            "close": [148.12, 148.22, 148.30, 148.23, 148.18],
        },
        index=pd.date_range(
            "2025-08-13 03:30:00",
            periods=5,
            freq="30min",
            tz=timezone.utc,
        ),
    )
    return data


@pytest.fixture
def price_data_no_trigger():
    """
    Price data where trade runs full period without hitting stops.

    Trade exit at 148.08, SL at 147.30, TP at 148.30.
    All bars stay within 147.30-148.30 range.
    """
    data = pd.DataFrame(
        {
            "open": [148.10, 148.05, 148.00, 147.95, 147.90],
            "high": [148.15, 148.10, 148.05, 148.00, 147.95],
            "low": [148.00, 147.95, 147.90, 147.85, 147.80],
            "close": [148.08, 148.02, 147.98, 147.92, 147.88],
        },
        index=pd.date_range(
            "2025-08-13 03:30:00",
            periods=5,
            freq="30min",
            tz=timezone.utc,
        ),
    )
    return data


class TestExitSimulation:
    """Test run_single_trade_simulation function."""

    def test_simulation_hits_stop_loss(self, long_trade, price_data_hits_stop_loss):
        """Test simulation where position hits stop-loss."""
        result = run_single_trade_simulation(
            trade=long_trade,
            price_data=price_data_hits_stop_loss,
            hold_bars=10,
        )

        assert isinstance(result, SimulatedHold)
        assert result.hold_bars == 10
        assert result.simulated_exit_reason == "stop_loss"
        # Stop hit at bar 3 (0-indexed)
        assert result.simulated_exit_bar_offset == 3
        # Should have negative PnL from stop-loss
        assert result.simulated_pnl < long_trade.pnl
        assert result.pnl_change_vs_actual < 0
        # MFE should be tracked
        assert result.mfe_during_hold >= 0
        # MAE should be negative (went against position)
        assert result.mae_during_hold < 0

    def test_simulation_hits_take_profit(self, long_trade, price_data_hits_take_profit):
        """Test simulation where position hits take-profit."""
        result = run_single_trade_simulation(
            trade=long_trade,
            price_data=price_data_hits_take_profit,
            hold_bars=10,
        )

        assert isinstance(result, SimulatedHold)
        assert result.hold_bars == 10
        assert result.simulated_exit_reason == "take_profit"
        # TP hit at bar 2 (0-indexed)
        assert result.simulated_exit_bar_offset == 2
        # Should have positive PnL from take-profit
        assert result.simulated_pnl > long_trade.pnl
        assert result.pnl_change_vs_actual > 0
        # MFE should be positive
        assert result.mfe_during_hold > 0

    def test_simulation_held_full_period(self, long_trade, price_data_no_trigger):
        """Test simulation where position is held for full period."""
        result = run_single_trade_simulation(
            trade=long_trade,
            price_data=price_data_no_trigger,
            hold_bars=5,
        )

        assert isinstance(result, SimulatedHold)
        assert result.hold_bars == 5
        assert result.simulated_exit_reason == "held_full_period"
        # Exit at the last bar (bar 4 for 5 bars, 0-indexed)
        assert result.simulated_exit_bar_offset == 4
        # PnL based on final close price
        # Entry at 148.08 (exit price of original trade)
        # Final close at 147.88
        # For long: (147.88 - 148.08) * 10000 = -2000 pips = -$20
        # Original PnL was +15, so change = -35
        assert result.pnl_change_vs_actual < 0
        # MFE/MAE offsets should be within 0-4 range
        assert 0 <= result.mfe_bar_offset <= 4
        assert 0 <= result.mae_bar_offset <= 4

    def test_simulation_short_trade_hits_stop(
        self, short_trade, price_data_hits_take_profit
    ):
        """
        Test short trade hitting stop-loss.

        Reusing price_data_hits_take_profit but for a short.
        Short SL at 147.78, price goes to 148.35 -> triggers SL.
        """
        result = run_single_trade_simulation(
            trade=short_trade,
            price_data=price_data_hits_take_profit,
            hold_bars=10,
        )

        assert isinstance(result, SimulatedHold)
        assert result.simulated_exit_reason == "stop_loss"
        # Short position loses money when price rises
        assert result.simulated_pnl < short_trade.pnl

    def test_simulation_insufficient_data(self, long_trade):
        """Test simulation when there's not enough data."""
        # Only 2 bars of data but asking for 10-bar simulation
        limited_data = pd.DataFrame(
            {
                "open": [148.10, 148.05],
                "high": [148.15, 148.10],
                "low": [148.00, 147.95],
                "close": [148.08, 148.02],
            },
            index=pd.date_range(
                "2025-08-13 03:30:00",
                periods=2,
                freq="30min",
                tz=timezone.utc,
            ),
        )

        result = run_single_trade_simulation(
            trade=long_trade, price_data=limited_data, hold_bars=10
        )

        # Should use available data (2 bars)
        assert result.hold_bars == 10
        assert result.simulated_exit_reason == "held_full_period"
        # Exit at last available bar (bar 1, 0-indexed)
        assert result.simulated_exit_bar_offset == 1

    def test_mfe_mae_tracking(self, long_trade, price_data_no_trigger):
        """Test that MFE/MAE are correctly tracked during simulation."""
        result = run_single_trade_simulation(
            trade=long_trade,
            price_data=price_data_no_trigger,
            hold_bars=5,
        )

        # For long trade with entry at 148.08:
        # Bar 0: high=148.15, low=148.00
        # Bar 1: high=148.10, low=147.95
        # ...
        # MFE should be max(high - 148.08) across all bars
        # MAE should be min(low - 148.08) across all bars

        assert result.mfe_during_hold > 0  # Some bars went above entry
        assert result.mae_during_hold < 0  # Some bars went below entry
        assert 0 <= result.mfe_bar_offset <= 4
        assert 0 <= result.mae_bar_offset <= 4
