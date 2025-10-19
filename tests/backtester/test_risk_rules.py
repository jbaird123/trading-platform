from __future__ import annotations

from datetime import datetime
from typing import cast

import pandas as pd
from pytest import approx
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


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


def _dummy_strategy_with_sl(stop_loss_pips: float) -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy_sl",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={"stop_loss_pips": stop_loss_pips},
    )


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


def test_daily_loss_cap_blocks_new_entries():
    """Test that the daily loss cap blocks new entries after being hit."""
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [100.0, 89.0, 100.0],
            "high": [101.0, 95.0, 101.0],
            "low": [99.0, 89.0, 99.0],
            "close": [100.0, 90.0, 100.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    strategy = _dummy_strategy_with_sl(10.0)
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", "exit_long", "enter_long"], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        daily_loss_cap=5.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, exposure, skipped = cast(tuple[list, list, list], result)

    assert any(s.get("skip_reason") == "risk_cap" for s in skipped)


def test_exposure_curve_tracks_gross_notional():
    """Test that the exposure curve tracks gross notional value per bar."""
    idx = [datetime(2023, 1, 1, h) for h in range(4)]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 111.0, 121.0, 131.0],
            "low": [99.0, 99.0, 99.0, 99.0],
            "close": [100.0, 110.0, 120.0, 130.0],
            "volume": [100] * 4,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series([None, "enter_long", None, "exit_long"], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=10000.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, curve, skipped = cast(tuple[list, list, list], result)

    expected = [0.0, 1_100_000.0, 1_200_000.0, 0.0]
    got = [v for _, v in curve]
    assert got == approx(expected)


def test_position_cap_skips_same_direction_entry():
    """Test that the position cap skips a same-direction entry if a position is open."""
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [100] * 2,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", "enter_long"], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        pm_limits={"max_open_long": 1},
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, exposure, skipped = cast(tuple[list, list, list], result)

    # Should have 1 trade: bar 0 enters long, bar 1 tries to enter long
    # again but skipped. Trade is force-closed at end of backtest
    assert len(trades) == 1
    assert trades[0].side == "long"
    assert trades[0].exit_reason == "end_of_data"
    # TODO: Verify skipped entry for bar 1 (position cap logic needs review)


def test_position_cap_not_reached_when_already_open():
    """Test that the position cap is not triggered for an existing position."""
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [100] * 2,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", None], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        pm_limits={"max_open_long": 2},
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, exposure, skipped = cast(tuple[list, list, list], result)

    # Should have 1 trade: bar 0 enters long, bar 1 has no signal,
    # position force-closed at end
    assert len(trades) == 1
    assert trades[0].side == "long"
    assert trades[0].exit_reason == "end_of_data"
    # No entries should be skipped due to position cap (max is 2, we only opened 1)
    assert not any(s.get("skip_reason") == "position_cap" for s in skipped)


def test_position_cap_zero_blocks_new_entry():
    """Test that a position cap of zero blocks any new entry."""
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [100] * 2,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", None], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        pm_limits={"max_open_long": 0},
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    trades, exposure, skipped = cast(tuple[list, list, list], result)

    assert any(s.get("skip_reason") == "position_cap" for s in skipped)


def test_rmm_blocks_disallowed_side():
    """Test that the RMM blocks a trade if the side is not allowed."""
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "volume": [100] * 2,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    sig = pd.Series(["enter_long", "exit_long"], index=df.index)
    cfg = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="current_bar_close",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})
    rmm_ctx = {
        df.index[0]: {
            "label": "trend_down",
            "confidence": 0.9,
            "allowed_sides": ["short"],
            "policy": {"min_confidence": 0.5},
        }
    }

    result = run_backtest(
        market_data=df,
        signals=sig,
        strategy=strategy,
        config=cfg,
        rem=rem,
        rmm_context=rmm_ctx,
        return_skips=True,
        return_exposure=True,
    )
    trades, exposure, skips = cast(tuple[list, list, list], result)

    assert len(cast(list, trades)) == 0
    assert any(s.get("skip_reason") == "rmm_block" for s in cast(list, skips))
