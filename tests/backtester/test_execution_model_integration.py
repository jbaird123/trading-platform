"""Integration tests for execution model functionality.

Tests the complete next_bar_open execution flow to ensure that:
1. Entries are deferred to the next bar's open price
2. Exits are deferred to the next bar's open price
3. Prices match exactly as expected
4. Multiple trades execute correctly with the deferred model
"""

from datetime import datetime

import pandas as pd
import pytest
from trading_platform.backtester.core import _run_backtest_simulation
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager

# Test instrument
TEST_INSTRUMENT = {
    "symbol": "EUR_USD",  # Use registered instrument name
}


class DummyStrategy:
    """Minimal strategy for testing."""

    def generate_signals(self, df):
        pass

    def get_context(self, bar_index):
        return {"ctx_atr": 0.0, "ctx_rsi": None, "ctx_ema_slow": None}


def test_next_bar_open_execution_model_complete_flow():
    """
    Integration test for next_bar_open execution model.

    Tests the complete flow with multiple entries and exits to ensure:
    - Long entry signal at bar 1 → executes at bar 2 open
    - Long exit signal at bar 4 → executes at bar 5 open
    - Short entry signal at bar 6 → executes at bar 7 open
    - Short exit signal at bar 9 → executes at bar 10 open (if exists)

    This verifies that the entire next_bar_open execution pipeline works
    correctly for realistic trading scenarios.
    """
    # Create 11 bars (0-10) with distinct prices for each bar
    idx = [datetime(2024, 1, 1, h) for h in range(11)]
    df = pd.DataFrame(
        {
            "open": [
                1.0000,
                1.0010,
                1.0020,
                1.0030,
                1.0040,
                1.0050,
                1.0060,
                1.0070,
                1.0080,
                1.0090,
                1.0100,
            ],
            "high": [
                1.0005,
                1.0015,
                1.0025,
                1.0035,
                1.0045,
                1.0055,
                1.0065,
                1.0075,
                1.0085,
                1.0095,
                1.0105,
            ],
            "low": [
                0.9995,
                1.0005,
                1.0015,
                1.0025,
                1.0035,
                1.0045,
                1.0055,
                1.0065,
                1.0075,
                1.0085,
                1.0095,
            ],
            "close": [
                1.0002,
                1.0012,
                1.0022,
                1.0032,
                1.0042,
                1.0052,
                1.0062,
                1.0072,
                1.0082,
                1.0092,
                1.0102,
            ],
            "volume": [100] * 11,
        },
        index=idx,
    )

    # Create strategy
    strategy = DummyStrategy()

    # Signals: bar 1 enter_long, bar 4 exit_long, bar 6 enter_short, bar 9 exit_short
    signals = pd.Series(
        [
            None,  # Bar 0
            "enter_long",  # Bar 1: signal to enter long
            None,  # Bar 2
            None,  # Bar 3
            "exit_long",  # Bar 4: signal to exit long
            None,  # Bar 5
            "enter_short",  # Bar 6: signal to enter short
            None,  # Bar 7
            None,  # Bar 8
            "exit_short",  # Bar 9: signal to exit short
            None,  # Bar 10
        ],
        index=df.index,
    )

    # Create config with next_bar_open execution model
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        instrument=TEST_INSTRUMENT,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        entry_window_bars=0,  # Immediate execution on entry window open
        warmup_bars=0,
        min_hold_bars=0,
        allow_flip_on_bar=False,
    )

    # Create minimal REM
    rem = RiskExitManager(config=None, instrument=TEST_INSTRUMENT)

    # Run backtest
    result = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,  # type: ignore[arg-type]
        config=config,
        rem=rem,
        rmm_context=None,
        return_exposure=False,
        return_skips=False,
    )
    trades_list = result if isinstance(result, list) else result[0]

    # Should have 2 trades
    assert len(trades_list) == 2, f"Expected 2 trades, got {len(trades_list)}"

    # Trade 1 (long): Signal at bar 1, entry at bar 2, signal at bar 4, exit at bar 5
    trade1 = trades_list[0]
    assert trade1.side == "long"
    assert (
        trade1.entry_time == idx[2]
    ), f"Expected entry at bar 2, got {trade1.entry_time}"
    assert trade1.entry_price == pytest.approx(
        1.0020
    ), f"Expected entry price 1.0020 (bar 2 open), got {trade1.entry_price}"
    assert trade1.exit_time == idx[5], f"Expected exit at bar 5, got {trade1.exit_time}"
    assert trade1.exit_price == pytest.approx(
        1.0050
    ), f"Expected exit price 1.0050 (bar 5 open), got {trade1.exit_price}"
    assert trade1.exit_reason == "signal"

    # Trade 2 (short): Signal at bar 6, entry at bar 7, signal at bar 9, exit at bar 10
    trade2 = trades_list[1]
    assert trade2.side == "short"
    assert (
        trade2.entry_time == idx[7]
    ), f"Expected entry at bar 7, got {trade2.entry_time}"
    assert trade2.entry_price == pytest.approx(
        1.0070
    ), f"Expected entry price 1.0070 (bar 7 open), got {trade2.entry_price}"
    assert (
        trade2.exit_time == idx[10]
    ), f"Expected exit at bar 10, got {trade2.exit_time}"
    assert trade2.exit_price == pytest.approx(
        1.0100
    ), f"Expected exit price 1.0100 (bar 10 open), got {trade2.exit_price}"
    assert trade2.exit_reason == "signal"

    # Verify PnL calculations
    # Long trade: entry at 1.0020, exit at 1.0050 → +0.0030 pips
    assert trade1.pnl == pytest.approx(
        0.0030, abs=1e-6
    ), f"Expected long PnL ~0.0030, got {trade1.pnl}"

    # Short trade: entry at 1.0070, exit at 1.0100 → -0.0030 pips (loss)
    assert trade2.pnl == pytest.approx(
        -0.0030, abs=1e-6
    ), f"Expected short PnL ~-0.0030, got {trade2.pnl}"


def test_next_bar_open_vs_current_bar_close_comparison():
    """
    Compare next_bar_open vs current_bar_close execution models.

    This test verifies that the two execution models produce different
    entry/exit times and prices as expected.
    """
    # Create 5 bars with distinct prices
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.0000, 1.0010, 1.0020, 1.0030, 1.0040],
            "high": [1.0005, 1.0015, 1.0025, 1.0035, 1.0045],
            "low": [0.9995, 1.0005, 1.0015, 1.0025, 1.0035],
            "close": [1.0002, 1.0012, 1.0022, 1.0032, 1.0042],
            "volume": [100] * 5,
        },
        index=idx,
    )

    strategy = DummyStrategy()

    # Signals: bar 0 enter_long, bar 2 exit_long
    signals = pd.Series(["enter_long", None, "exit_long", None, None], index=df.index)

    rem = RiskExitManager(config=None, instrument=TEST_INSTRUMENT)

    # Test current_bar_close (legacy)
    config_legacy = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        instrument=TEST_INSTRUMENT,
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
        entry_window_bars=0,
        warmup_bars=0,
        min_hold_bars=0,
        allow_flip_on_bar=False,
    )

    result_legacy = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,  # type: ignore[arg-type]
        config=config_legacy,
        rem=rem,
    )
    trades_legacy = (
        result_legacy if isinstance(result_legacy, list) else result_legacy[0]
    )

    # Test next_bar_open (realistic)
    config_realistic = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        instrument=TEST_INSTRUMENT,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        entry_window_bars=0,
        warmup_bars=0,
        min_hold_bars=0,
        allow_flip_on_bar=False,
    )

    result_realistic = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,  # type: ignore[arg-type]
        config=config_realistic,
        rem=rem,
    )
    trades_realistic = (
        result_realistic if isinstance(result_realistic, list) else result_realistic[0]
    )

    # Both should have 1 trade
    assert len(trades_legacy) == 1
    assert len(trades_realistic) == 1

    trade_legacy = trades_legacy[0]
    trade_realistic = trades_realistic[0]

    # Legacy: Entry at bar 0, exit at bar 2
    assert trade_legacy.entry_time == idx[0]
    assert trade_legacy.entry_price == pytest.approx(
        1.0002
    )  # Bar 0 close (signal bar close)
    assert trade_legacy.exit_time == idx[2]
    assert trade_legacy.exit_price == pytest.approx(
        1.0022
    )  # Bar 2 close (signal bar close)

    # Realistic: Entry at bar 1, exit at bar 3
    assert trade_realistic.entry_time == idx[1]
    assert trade_realistic.entry_price == pytest.approx(
        1.0010
    )  # Bar 1 open (next bar open)
    assert trade_realistic.exit_time == idx[3]
    assert trade_realistic.exit_price == pytest.approx(
        1.0030
    )  # Bar 3 open (next bar open)

    # Verify they differ as expected
    assert trade_legacy.entry_time != trade_realistic.entry_time
    assert trade_legacy.entry_price != trade_realistic.entry_price
    assert trade_legacy.exit_time != trade_realistic.exit_time
    assert trade_legacy.exit_price != trade_realistic.exit_price
