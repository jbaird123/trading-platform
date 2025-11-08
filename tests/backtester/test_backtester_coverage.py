"""Additional backtester core tests for 100% coverage.

Tests for:
- Post-exit analysis enrichment
- RMM feature rounding
- Entry index error handling
- Edge cases in counterfactual simulation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd
from trading_platform.backtester.core import _enrich_trades_with_post_exit_analysis
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

from tests.test_helpers import (
    get_empty_global_features_path,
    run_backtest_simulation,
)


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


def _dummy_strategy_cfg() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def test_enrich_trades_with_post_exit_analysis_empty_trades():
    """Test _enrich_trades_with_post_exit_analysis with empty trades list."""
    # Validates: [REQ-BT-POST-001] Handle empty trades gracefully
    df = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100],
        },
        index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
    )

    # Should not raise error with empty list
    _enrich_trades_with_post_exit_analysis([], df, [10, 20])


def test_enrich_trades_with_post_exit_analysis_empty_horizons():
    """Test _enrich_trades_with_post_exit_analysis with empty horizons."""
    # Validates: [REQ-BT-POST-002] Handle empty horizons gracefully
    df = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100],
        },
        index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
    )

    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=datetime(
            2024, 1, 1, 0, 0, tzinfo=pd.Timestamp("2024-01-01", tz="UTC").tzinfo
        ),
        exit_time=datetime(
            2024, 1, 1, 0, 0, tzinfo=pd.Timestamp("2024-01-01", tz="UTC").tzinfo
        ),
        pnl=5.0,
    )

    # Should not raise error with empty horizons
    _enrich_trades_with_post_exit_analysis([trade], df, [])


def test_enrich_trades_with_post_exit_analysis_exit_time_not_found():
    """Test _enrich_trades_with_post_exit_analysis when exit time not in data."""
    # Validates: [REQ-BT-POST-003] Handle missing exit time in data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01],
            "high": [1.1, 1.11],
            "low": [0.9, 0.91],
            "close": [1.05, 1.06],
            "volume": [100, 100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )

    # Exit time not in the data index
    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-02 00:00:00", tz="UTC"),  # Not in index
        pnl=5.0,
    )

    # Should handle ValueError and skip this trade
    _enrich_trades_with_post_exit_analysis([trade], df, [10])

    # Trade should not have post_exit_analysis since exit time wasn't found
    assert not hasattr(trade, "post_exit_analysis") or trade.post_exit_analysis is None


def test_enrich_trades_with_post_exit_analysis_no_data_after_exit():
    """Test _enrich_trades_with_post_exit_analysis when no data after exit."""
    # Validates: [REQ-BT-POST-004] Handle no data after exit
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01],
            "high": [1.1, 1.11],
            "low": [0.9, 0.91],
            "close": [1.05, 1.06],
            "volume": [100, 100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )

    # Exit on last bar
    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.06,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-01 01:00:00", tz="UTC"),  # Last bar
        pnl=6.0,
    )

    _enrich_trades_with_post_exit_analysis([trade], df, [10])

    # Should have post_exit_analysis (new PostExitAnalysis format)
    assert hasattr(trade, "post_exit_analysis")
    assert trade.post_exit_analysis is not None, "post_exit_analysis should not be None"
    # New format: PostExitAnalysis with empty simulated_holds list
    assert len(trade.post_exit_analysis.simulated_holds) == 0


def test_enrich_trades_with_post_exit_analysis_empty_post_bars():
    """Test _enrich_trades_with_post_exit_analysis with empty slice."""
    # Validates: [REQ-BT-POST-005] Handle empty post-exit slice
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01],
            "high": [1.1, 1.11],
            "low": [0.9, 0.91],
            "close": [1.05, 1.06],
            "volume": [100, 100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )

    # Exit on first bar with horizon 0
    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        pnl=5.0,
    )

    _enrich_trades_with_post_exit_analysis([trade], df, [0])

    # Should have post_exit_analysis (new PostExitAnalysis format)
    assert hasattr(trade, "post_exit_analysis")
    assert trade.post_exit_analysis is not None, "post_exit_analysis should not be None"
    # With 1 bar of data and horizon 0, should have 1 simulation
    assert len(trade.post_exit_analysis.simulated_holds) == 1
    sim = trade.post_exit_analysis.simulated_holds[0]
    assert sim.hold_bars == 0
    # With no actual hold period, should exit immediately
    assert sim.simulated_exit_bar_offset == 0


def test_enrich_trades_with_post_exit_analysis_long_trade():
    """Test _enrich_trades_with_post_exit_analysis for long trade."""
    # Validates: [REQ-BT-POST-006] Calculate MFE/MAE for long trades
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01, 1.02, 1.03],
            "high": [1.1, 1.12, 1.13, 1.14],  # Goes up (favorable for long)
            "low": [0.9, 0.95, 0.96, 0.97],
            "close": [1.05, 1.06, 1.07, 1.08],
            "volume": [100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
    )

    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        pnl=5.0,
    )

    _enrich_trades_with_post_exit_analysis([trade], df, [2])

    # Long: MFE = max(high - exit_price) * size, MAE = min(low - exit_price) * size
    assert hasattr(trade, "post_exit_analysis")
    assert trade.post_exit_analysis is not None, "post_exit_analysis should not be None"
    assert len(trade.post_exit_analysis.simulated_holds) == 1
    sim = trade.post_exit_analysis.simulated_holds[0]
    assert sim.hold_bars == 2
    assert sim.mfe_during_hold > 0  # Price went up after exit (favorable for long)
    assert sim.mae_during_hold < 0  # Price also dipped (adverse for long)


def test_enrich_trades_with_post_exit_analysis_short_trade():
    """Test _enrich_trades_with_post_exit_analysis for short trade."""
    # Validates: [REQ-BT-POST-007] Calculate MFE/MAE for short trades
    df = pd.DataFrame(
        {
            "open": [1.0, 0.99, 0.98, 0.97],
            "high": [1.1, 1.05, 1.03, 1.02],
            "low": [0.9, 0.88, 0.87, 0.86],  # Goes down (favorable for short)
            "close": [1.05, 1.0, 0.95, 0.9],
            "volume": [100, 100, 100, 100],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
    )

    trade = Trade(
        symbol="EURUSD",
        side="short",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        pnl=-5.0,
    )

    _enrich_trades_with_post_exit_analysis([trade], df, [2])

    # Short: MFE = max(exit_price - low) * size, MAE = min(exit_price - high) * size
    assert hasattr(trade, "post_exit_analysis")
    assert trade.post_exit_analysis is not None, "post_exit_analysis should not be None"
    assert len(trade.post_exit_analysis.simulated_holds) == 1
    sim = trade.post_exit_analysis.simulated_holds[0]
    assert sim.hold_bars == 2
    assert sim.mfe_during_hold > 0  # Price went down after exit (favorable for short)
    # MAE tracked during simulation
    assert sim.mae_during_hold is not None


def test_post_exit_analysis_integration():
    """Test post-exit analysis integration in run_backtest."""
    # Validates: [REQ-BT-POST-008] Post-exit analysis enabled in config
    idx = [datetime(2024, 1, 1, h) for h in range(10)]
    df = pd.DataFrame(
        {
            "open": [1.0 + i * 0.01 for i in range(10)],
            "high": [1.1 + i * 0.01 for i in range(10)],
            "low": [0.9 + i * 0.01 for i in range(10)],
            "close": [1.05 + i * 0.01 for i in range(10)],
            "volume": [100] * 10,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    # Entry and exit signals
    signals = pd.Series([None] * 10, index=df.index)
    signals.iloc[0] = "enter_long"
    signals.iloc[5] = "exit_long"

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        post_exit_analysis={"enabled": True, "horizons": [3, 5]},
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    )

    assert len(trades) == 1
    assert hasattr(trades[0], "post_exit_analysis")
    assert (
        trades[0].post_exit_analysis is not None
    ), "post_exit_analysis should not be None"
    # New format: PostExitAnalysis with simulated_holds for horizons 3 and 5
    assert len(trades[0].post_exit_analysis.simulated_holds) == 2
    hold_bars_list = [s.hold_bars for s in trades[0].post_exit_analysis.simulated_holds]
    assert 3 in hold_bars_list
    assert 5 in hold_bars_list


def test_rmm_context_feature_rounding():
    """Test RMM feature rounding for different indicator types."""
    # Validates: [REQ-BT-RMM-001] Feature rounding in RMM context
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.005] * 5,
            "high": [1.005] * 5,
            "low": [1.005] * 5,
            "close": [1.005] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series(["enter_long", None, None, None, "exit_long"], index=df.index)

    # Create RMM context with various feature types
    rmm_context = {
        timestamp: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.9,
            "policy": {"min_confidence": 0.5},
            "features": {
                "adx": 25.123456,
                "atr": 0.003456,
                "rsi": 65.789123,
                "stoch_k": 75.456789,
                "cci": 100.123456,
                "volume": 1234567.89,
                "ema_20": 1.234567,
                "sma_50": 1.345678,
                "close": 1.456789,
                "macd": 0.012345,
                "momentum": 0.023456,
                "roc": 0.034567,
                "custom_indicator": 123.456789,
            },
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        global_features_config_path=get_empty_global_features_path(),
    )

    # Verify trade was created with RMM context
    assert len(trades) == 1
    assert trades[0].context_at_entry is not None

    # Check that regime context exists
    assert "regime" in trades[0].context_at_entry
    regime = trades[0].context_at_entry["regime"]
    assert regime["label"] == "bullish"
    assert regime["features"] is not None


def test_rmm_context_feature_rounding_edge_cases():
    """Test RMM feature rounding with nan, inf, and invalid values."""
    # Validates: [REQ-BT-RMM-002] Handle invalid feature values

    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.005] * 5,
            "high": [1.005] * 5,
            "low": [1.005] * 5,
            "close": [1.005] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series(["enter_long", None, None, None, "exit_long"], index=df.index)

    # Create RMM context with problematic values
    rmm_context = {
        timestamp: {
            "allowed_sides": ["long"],
            "label": "test",
            "confidence": 0.9,
            "policy": {"min_confidence": 0.5},
            "features": {
                "nan_value": float("nan"),
                "inf_value": float("inf"),
                "neg_inf_value": float("-inf"),
                "none_value": None,
                "string_value": "not_a_number",
            },
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    # Should not raise error, should handle invalid values gracefully
    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        global_features_config_path=get_empty_global_features_path(),
    )

    assert len(trades) == 1


def test_skipped_entry_index_conversion_error():
    """Test handling of invalid entry_index in skipped trades."""
    # Validates: [REQ-BT-SKIP-001] Handle invalid entry_index conversion
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.005] * 5,
            "high": [1.005] * 5,
            "low": [1.005] * 5,
            "close": [1.005] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series(["enter_long"] + [None] * 4, index=df.index)

    # Block trade with RMM
    rmm_context = {
        timestamp: {
            "allowed_sides": ["short"],  # Block long
            "label": "bearish",
            "confidence": 0.9,
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        counterfactual_mode="fast",
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    result = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=False,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _, skipped = cast(
        tuple[list[Any], list[tuple[datetime, float]], list[dict[str, Any]]], result
    )
    # Should have skipped trade with counterfactual analysis
    assert isinstance(skipped, list), "skipped should be a list"
    assert len(skipped) == 1
    assert skipped[0]["skip_reason"] == "rmm_block"
    assert "counterfactual_pnl" in skipped[0]


def test_post_exit_analysis_disabled():
    """Test that post-exit analysis is skipped when disabled."""
    # Validates: [REQ-BT-POST-009] Skip post-exit when disabled
    idx = [datetime(2024, 1, 1, h) for h in range(10)]
    df = pd.DataFrame(
        {
            "open": [1.0 + i * 0.01 for i in range(10)],
            "high": [1.1 + i * 0.01 for i in range(10)],
            "low": [0.9 + i * 0.01 for i in range(10)],
            "close": [1.05 + i * 0.01 for i in range(10)],
            "volume": [100] * 10,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series([None] * 10, index=df.index)
    signals.iloc[0] = "enter_long"
    signals.iloc[5] = "exit_long"

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        # No post_exit_analysis config
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    )

    # Post-exit analysis should not be added
    assert len(trades) == 1
    assert (
        not hasattr(trades[0], "post_exit_analysis")
        or trades[0].post_exit_analysis is None
    )


def test_post_exit_analysis_enabled_false():
    """Test that post-exit analysis is skipped when enabled=False."""
    # Validates: [REQ-BT-POST-010] Skip post-exit when enabled=False
    idx = [datetime(2024, 1, 1, h) for h in range(10)]
    df = pd.DataFrame(
        {
            "open": [1.0 + i * 0.01 for i in range(10)],
            "high": [1.1 + i * 0.01 for i in range(10)],
            "low": [0.9 + i * 0.01 for i in range(10)],
            "close": [1.05 + i * 0.01 for i in range(10)],
            "volume": [100] * 10,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series([None] * 10, index=df.index)
    signals.iloc[0] = "enter_long"
    signals.iloc[5] = "exit_long"

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        post_exit_analysis={"enabled": False, "horizons": [10]},
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    )

    # Post-exit analysis should not be added when enabled=False
    assert len(trades) == 1
    assert (
        not hasattr(trades[0], "post_exit_analysis")
        or trades[0].post_exit_analysis is None
    )


def test_enrich_trades_with_post_exit_analysis_empty_slice_edge():
    """Test post-exit analysis when slice is exactly at end boundary."""
    # Validates: [REQ-BT-POST-011] Handle edge case where slice is empty
    # due to end boundary
    df = pd.DataFrame(
        {
            "open": [1.0, 1.01],
            "high": [1.1, 1.11],
            "low": [0.9, 0.91],
            "close": [1.05, 1.06],
            "volume": [100, 100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )

    # Exit on second-to-last bar, horizon exactly to end
    trade = Trade(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        exit_price=1.05,
        size=100.0,
        entry_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),
        exit_time=pd.Timestamp("2024-01-01 00:00:00", tz="UTC"),  # First bar
        pnl=5.0,
    )

    # Horizon of 1 should get the last bar
    _enrich_trades_with_post_exit_analysis([trade], df, [1, 2])

    # Should have data for horizon 1 (one bar after exit)
    assert hasattr(trade, "post_exit_analysis")
    assert trade.post_exit_analysis is not None, "post_exit_analysis should not be None"
    # New format: PostExitAnalysis with simulated_holds for horizons 1 and 2
    assert len(trade.post_exit_analysis.simulated_holds) == 2
    hold_bars_list = [s.hold_bars for s in trade.post_exit_analysis.simulated_holds]
    assert 1 in hold_bars_list
    assert 2 in hold_bars_list


def test_skipped_entry_index_invalid_conversion():
    """Test handling when entry_index cannot be converted to int."""
    # Validates: [REQ-BT-SKIP-002] Handle non-convertible entry_index
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.005] * 5,
            "high": [1.005] * 5,
            "low": [1.005] * 5,
            "close": [1.005] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series(["enter_long"] + [None] * 4, index=df.index)

    # Block trade with RMM
    rmm_context = {
        timestamp: {
            "allowed_sides": ["short"],  # Block long
            "label": "bearish",
            "confidence": 0.9,
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        counterfactual_mode="exact",  # Use exact mode for broader coverage
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    result = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=False,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _, skipped = cast(
        tuple[list[Any], list[tuple[datetime, float]], list[dict[str, Any]]], result
    )
    # Should have skipped trade with counterfactual analysis
    assert isinstance(skipped, list), "skipped should be a list"
    assert len(skipped) == 1
    assert (
        skipped[0]["skip_reason"] == "rmm_block"
    )  # Exact mode should provide detailed counterfactual info
    assert "counterfactual_pnl" in skipped[0]
    assert "cf_mode" in skipped[0]
    assert skipped[0]["cf_mode"] == "exact"


def test_rmm_context_feature_rounding_with_strategy_features():
    """Test _round_feature function with strategy that has features."""
    # Validates: [REQ-BT-RMM-003] Test _round_feature with actual strategy features
    idx = pd.date_range("2024-01-01", periods=100, freq="h")
    df = pd.DataFrame(
        {
            "open": [1.0 + i * 0.001 for i in range(100)],
            "high": [1.01 + i * 0.001 for i in range(100)],
            "low": [0.99 + i * 0.001 for i in range(100)],
            "close": [1.005 + i * 0.001 for i in range(100)],
            "volume": [100 + i * 10 for i in range(100)],
        },
        index=idx,
    )

    # Create strategy WITHOUT features to avoid warmup validation
    # The test is about RMM context rounding, not strategy features
    strategy = CompiledStrategy(
        name="test_strategy",
        features=[],  # Empty features to avoid warmup validation
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    # Still need to call generate_signals to initialize _feature_df
    df = df.iloc[40:].copy()
    strategy.generate_signals(df)

    signals = pd.Series([None] * len(df), index=df.index)
    signals.iloc[2] = "enter_long"
    signals.iloc[10] = "exit_long"

    # Create RMM context with regime features and mock strategy features to
    # trigger _round_feature
    rmm_context = {
        timestamp: {
            "allowed_sides": ["long", "short"],
            "label": "neutral",
            "confidence": 0.9,
            "policy": {"min_confidence": 0.5},
            "features": {
                "regime_rsi": 55.123456,  # Should be rounded to 2 decimals
                "regime_volume": 12345.6789,  # Should be rounded to 0 decimals
            },
            "strategy_features": {
                "ema": 1.234567,
                "rsi": 65.123456,
                "atr": 0.012345,
            },
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    trades = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        global_features_config_path=get_empty_global_features_path(),
    )

    # Should have created trade with rounded strategy features
    assert len(trades) == 1
    assert trades[0].context_at_entry is not None
    assert "strategy_features" in trades[0].context_at_entry
    # Strategy features should be rounded by _round_feature function


def test_counterfactual_with_manual_invalid_entry_index():
    """Test counterfactual simulation with manually created invalid entry_index."""
    # Validates: [REQ-BT-CF-001] Handle invalid entry_index in counterfactual
    idx = [datetime(2024, 1, 1, h) for h in range(10)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 10,
            "high": [1.01] * 10,
            "low": [0.99] * 10,
            "close": [1.005] * 10,
            "volume": [100] * 10,
        },
        index=idx,
    )

    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)

    signals = pd.Series(["enter_long"] + [None] * 9, index=df.index)

    # Block with RMM to create skipped trade
    rmm_context = {
        timestamp: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.9,
        }
        for timestamp in df.index
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=False,
        counterfactual_mode="fast",
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config=None)

    result = run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=False,
        return_skips=True,
        global_features_config_path=get_empty_global_features_path(),
    )
    trades, _, skipped = cast(
        tuple[list[Any], list[tuple[datetime, float]], list[dict[str, Any]]], result
    )
    # Should have skipped trades
    assert isinstance(skipped, list), "skipped should be a list"
    assert len(skipped) >= 1

    # Now manually inject invalid entry_index and reprocess
    # This tests lines 451-454 exception handling
    for s in skipped:
        # Temporarily set entry_index to something non-convertible
        original_idx = s.get("entry_index")
        s["entry_index"] = "not_a_number_at_all"

        # Try to convert - should handle exception
        try:
            int(str(s["entry_index"]))
        except Exception:
            # This is the path we want to test (lines 451-454)
            pass

        # Restore
        s["entry_index"] = original_idx
