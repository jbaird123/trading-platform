"""Backtester core tests.

# Validates: [BT-7.1], [BT-7.2], [BT-7.3], [BT-7.5], [BT-7.9]
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from trading_platform.backtester.core import (
    _simulate_counterfactual_exact,
    _simulate_counterfactual_fast,
    run_backtest,
)
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

BacktestTriple = tuple[
    list[Any],
    list[tuple[datetime, float]],
    list[dict[str, Any]],
]

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "EURUSD",
    "asset_class": "Forex",
    "point_value": 1.0,
    "tick_size": 0.00001,
    "pip_location": 0.0001,
}


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


def test_rmm_blocks_signal_not_in_allowed_sides():
    """Test RMM blocking when command not in allowed sides."""
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
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    # First bar has enter_long command, rest are None
    signals = pd.Series(["enter_long"] + [None] * 4, index=df.index)
    rmm_context = {
        timestamp: {
            "allowed_sides": ["short"],
            "label": "bearish_regime",
            "confidence": 0.8,
            "policy": {"min_confidence": 0.5},
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
    )
    rem = RiskExitManager(config={})

    trades_list, _, skipped_list = cast(
        BacktestTriple,
        run_backtest(
            market_data=df,
            signals=signals,
            strategy=strategy,
            config=config,
            rem=rem,
            rmm_context=rmm_context,
            return_exposure=False,
            return_skips=True,
        ),
    )

    assert not trades_list
    # With event-based entries, only the first signal transition triggers
    # an entry attempt
    assert len(skipped_list) == 1
    assert skipped_list[0]["skip_reason"] == "rmm_block"


def test_rmm_allows_signal_opens_position() -> None:
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
            "volume": [100] * 3,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long", "exit_long", None], index=df.index)
    rmm_context = {
        df.index[0]: {
            "allowed_sides": ["long"],
            "label": "bull",
            "confidence": 0.7,
            "policy": {"min_confidence": 0.5},
        }
    }
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        initial_cash=1_000.0,
        instrument=_instrument(),
        position_size=1.0,
    )
    rem = RiskExitManager(config={})

    trades = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
    )

    assert len(trades) == 1
    assert trades[0].side == "long"


def test_return_skips_only():
    """Test return combination with skips only (no exposure)."""
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [1.005] * 3,
            "high": [1.005] * 3,
            "low": [1.005] * 3,
            "close": [1.005] * 3,
            "volume": [100] * 3,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long", None, "exit_long"], index=df.index)
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        initial_cash=10000.0,
        instrument=_instrument(),
        position_size=100.0,
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=False,
        return_skips=True,
    )

    _, exposure_curve, _ = cast(BacktestTriple, result)
    assert exposure_curve == []


def test_counterfactual_fast_invalid_start_index():
    """Test counterfactual fast with invalid start index."""
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

    result = _simulate_counterfactual_fast(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        start_index=-1,
        side="long",
        entry_price=1.0,
        size=100,
        instrument={"symbol": "EURUSD", "lot_size": 100_000},
        cost_model=None,
    )
    assert result == {}


def test_counterfactual_fast_short_side():
    """Test counterfactual fast simulation with short side."""
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 5,
            "high": [1.03] * 5,
            "low": [0.97] * 5,
            "close": [1.0] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )

    result = _simulate_counterfactual_fast(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        start_index=0,
        side="short",
        entry_price=1.00,
        size=100,
        instrument={"symbol": "EURUSD", "lot_size": 100_000},
        cost_model=None,
    )
    assert isinstance(result, dict)
    assert len(result) > 0


def test_counterfactual_exact_invalid_start_index():
    """Test counterfactual exact with invalid start index."""
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
    mock_rem = Mock()

    result = _simulate_counterfactual_exact(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        rem=mock_rem,
        start_index=-1,
        side="long",
        entry_price=1.0,
        size=100,
        instrument={"symbol": "EURUSD", "lot_size": 100_000},
        cost_model=None,
        symbol="EURUSD",
    )
    assert result == {}


def test_counterfactual_exact_rem_exit_breaks_loop() -> None:
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [100] * 3,
        },
        index=idx,
    )

    class StubREM:
        def check_exits(self, position: Any, current_bar: pd.Series) -> dict | None:
            return {
                "exit_price": float(current_bar["close"]),
                "reason": "stub_exit",
            }

    result = _simulate_counterfactual_exact(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        start_index=0,
        side="long",
        entry_price=100.0,
        size=1.0,
        instrument=TEST_INSTRUMENT,
        cost_model={},
        rem=StubREM(),  # type: ignore[arg-type]
        symbol="EURUSD",
    )

    assert result["cf_exit_kind"] == "rem"
    assert result["cf_mode"] == "exact"
    assert result["cf_exit_price"] == 100.5


def test_counterfactual_exact_returns_empty_when_position_not_created(
    monkeypatch: Any,
) -> None:
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "volume": [100, 100],
        },
        index=idx,
    )

    monkeypatch.setattr(
        "trading_platform.backtester.core.PortfolioManager.create_new_position",
        lambda *args, **kwargs: None,
    )

    class NoExitREM:
        def check_exits(self, position: Any, current_bar: pd.Series) -> None:
            return None

    result = _simulate_counterfactual_exact(
        market_data=df,
        strategy=_dummy_strategy_cfg(),
        start_index=0,
        side="long",
        entry_price=100.0,
        size=1.0,
        instrument=TEST_INSTRUMENT,
        cost_model={},
        rem=NoExitREM(),  # type: ignore[arg-type]
        symbol="EURUSD",
    )

    assert result == {}


def test_backtester_with_rem_pips_stop_loss():
    """Tests that the Backtester correctly handles a 'pips'-based stop-loss."""
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        allow_flip_on_bar=False,
        initial_cash=10000.0,
        position_size=1.0,
        rem_config={"stop_loss": {"pips": 50}},
        instrument={"symbol": "EURUSD", "pip_location": 0.0001},
    )
    rem = RiskExitManager(config=config.rem_config or {}, instrument=config.instrument)
    entry_price = 1.20000
    stop_price = entry_price - (50 * 0.0001)
    market_data = pd.DataFrame(
        [
            {
                "open": 1.1900,
                "high": 1.1950,
                "low": 1.1850,
                "close": entry_price,
                "volume": 100,
            },
            {
                "open": 1.2010,
                "high": 1.2020,
                "low": stop_price,
                "close": 1.1960,
                "volume": 100,
            },
        ],
        index=pd.to_datetime(["2023-01-01 10:00", "2023-01-01 11:00"]).tz_localize(
            "UTC"
        ),
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(market_data)  # Populate _feature_df for context lookups
    signals = pd.Series(["enter_long", None], index=market_data.index)

    trades = run_backtest(
        market_data=market_data,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
    )

    assert len(trades) == 1
    assert trades[0].exit_reason == "stop-loss"
    assert trades[0].exit_price == stop_price


class TestBacktesterCoreCoverage:
    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        close_prices = [1.02 + i * 0.1 for i in range(10)]
        return pd.DataFrame(
            {
                "open": close_prices,
                "high": close_prices,
                "low": close_prices,
                "close": close_prices,
                "volume": [100] * 10,
            },
            index=dates,
        )

    @pytest.fixture
    def sample_signals(self):
        return pd.Series(
            [None, "enter_long", "exit_long", "enter_short"] * 2 + [None] * 2
        )

    @pytest.fixture
    def mock_config(self):
        return RunConfig(
            user_id="test_user",
            run_seed=42,
            log_level="INFO",
            allow_flip_on_bar=False,
            initial_cash=10000.0,
            position_size=1.0,
            instrument={"symbol": "EURUSD", "multiplier": 1.0, "min_size": 0.01},
            cost_model={"type": "percentage", "rate": 0.001},
        )

    @pytest.fixture
    def mock_strategy(self):
        strategy = MagicMock(spec=CompiledStrategy)
        strategy.get_context.return_value = {"test": "context"}
        return strategy

    @pytest.fixture
    def mock_rem(self):
        rem = MagicMock(spec=RiskExitManager)
        rem.check_exits.return_value = None
        return rem

    def test_rmm_context_with_missing_datetime(
        self, sample_data, sample_signals, mock_config, mock_strategy, mock_rem
    ):
        """Test RMM context where a specific datetime is missing."""
        rmm_context = {
            sample_data.index[2]: {
                "allowed_sides": ["long"],
                "label": "trending_up",
                "confidence": 0.8,
                "policy": {"min_confidence": 0.7},
            }
        }
        result = run_backtest(
            market_data=sample_data,
            signals=sample_signals,
            strategy=mock_strategy,
            config=mock_config,
            rem=mock_rem,
            rmm_context=rmm_context,
        )
        assert isinstance(result, list)

    def test_counterfactual_exact_mode(
        self, sample_data, sample_signals, mock_config, mock_strategy, mock_rem
    ):
        """Test exact counterfactual mode."""
        mock_config.counterfactual_mode = "exact"
        mock_config.daily_loss_cap = 0.01

        with patch(
            "trading_platform.portfolio.portfolio.PortfolioManager.hit_daily_loss_cap",
            return_value=True,
        ):
            _, _, skipped = cast(
                BacktestTriple,
                run_backtest(
                    market_data=sample_data,
                    signals=sample_signals,
                    strategy=mock_strategy,
                    config=mock_config,
                    rem=mock_rem,
                    return_exposure=False,
                    return_skips=True,
                ),
            )
        if skipped:
            assert any(s.get("cf_mode") == "exact" for s in skipped)

    def test_simulate_counterfactual_exact_with_rem_exit(
        self, sample_data, mock_strategy, mock_rem
    ):
        """Test _simulate_counterfactual_exact with a REM-triggered exit."""

        def mock_check_exits(position, current_bar):
            if current_bar.name == sample_data.index[2]:
                return {"exit_price": 1.25, "reason": "stop_loss"}
            return None

        mock_rem.check_exits.side_effect = mock_check_exits

        result = _simulate_counterfactual_exact(
            market_data=sample_data,
            strategy=mock_strategy,
            start_index=1,
            side="long",
            entry_price=1.12,
            size=1.0,
            instrument=TEST_INSTRUMENT,
            cost_model={"type": "percentage", "rate": 0.001},
            rem=mock_rem,
            symbol="EURUSD",
        )
        assert result["cf_exit_kind"] == "rem"


def test_rmm_context_enrichment_in_trades_and_skips():
    """
    Test that RMM context (regime_label) is properly enriched in both executed trades
    and skipped trades when running a backtest with RMM enabled.

    This test is expected to fail until the implementation is complete.
    """
    # Create test data with enough bars for meaningful regime detection
    idx = [datetime(2024, 1, 1, h) for h in range(10)]
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.3, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9],
            "high": [1.1, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0],
            "low": [0.9, 1.0, 1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8],
            "close": [1.0, 1.1, 1.2, 1.3, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9],
            "volume": [100] * 10,
        },
        index=idx,
    )

    # Generate mixed command signals
    signals = pd.Series(
        [
            "enter_long",
            None,
            "enter_short",
            "exit_short",
            "enter_long",
            "enter_short",
            "exit_short",
            "enter_long",
            "enter_short",
            "exit_short",
        ],
        index=df.index,
    )

    # Create RMM context that will:
    # 1. Allow some trades (when regime matches signal direction)
    # 2. Block some trades (when regime doesn't match signal direction)
    rmm_context = {}
    for i, timestamp in enumerate(df.index):
        if i < 3:  # First 3 bars: trend_up regime, allows long only
            rmm_context[timestamp] = {
                "allowed_sides": ["long"],
                "label": "trend_up",
                "confidence": 0.8,
                "policy": {"min_confidence": 0.6},
            }
        elif i < 7:  # Next 4 bars: trend_down regime, allows short only
            rmm_context[timestamp] = {
                "allowed_sides": ["short"],
                "label": "trend_down",
                "confidence": 0.9,
                "policy": {"min_confidence": 0.6},
            }
        else:  # Last 3 bars: range regime, allows both
            rmm_context[timestamp] = {
                "allowed_sides": ["long", "short"],
                "label": "range",
                "confidence": 0.7,
                "policy": {"min_confidence": 0.6},
            }

    # Use simple dummy strategy since we're passing signals directly
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)  # Populate _feature_df for context lookups

    config = RunConfig(
        user_id="test_context_enrichment",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        instrument=_instrument(),
        allow_flip_on_bar=True,  # Allow position flips to get more trades
    )

    rem = RiskExitManager(config={})

    # Run backtest with RMM context - signals are passed directly to run_backtest
    trades_list, _, skipped_list = cast(
        BacktestTriple,
        run_backtest(
            market_data=df,
            signals=signals,
            strategy=strategy,
            config=config,
            rem=rem,
            rmm_context=rmm_context,
            return_exposure=False,
            return_skips=True,
        ),
    )

    # Expected results based on our RMM setup:
    # Bar 0: long signal, trend_up regime (allows long) -> should execute
    # Bar 1: long signal, trend_up regime (allows long) -> should execute
    # Bar 2: short signal, trend_up regime (allows long) -> should skip
    # Bar 3: flat signal -> no trade attempt
    # Bar 4: long signal, trend_down regime (allows short) -> should skip
    # Bar 5: short signal, trend_down regime (allows short) -> should execute
    # Bar 6: flat signal -> no trade attempt
    # Bar 7: long signal, range regime (allows both) -> should execute
    # Bar 8: short signal, range regime (allows both) -> should execute
    # Bar 9: flat signal -> no trade attempt

    # Acceptance Criteria 1: At least one trade was skipped due to RMM policy
    rmm_skipped = [s for s in skipped_list if s.get("skip_reason") == "rmm_block"]
    assert (
        len(rmm_skipped) >= 1
    ), f"Expected at least 1 RMM-blocked trade, got {len(rmm_skipped)}"

    # Acceptance Criteria 2: Skipped trades contain regime context
    for skip in rmm_skipped:
        # Check that the skipped trade has regime information in its context
        # This may be in different places depending on implementation
        regime_found = False

        # Check if regime info is directly in the skip dict
        if "regime" in skip and "label" in skip["regime"]:
            regime_label = skip["regime"]["label"]
            regime_found = True

        # Check if there's a context field with regime info
        elif (
            "context" in skip and skip["context"] and "regime_label" in skip["context"]
        ):
            regime_label = skip["context"]["regime_label"]
            regime_found = True

        # Check if there's a context field with nested regime info
        elif "context" in skip and skip["context"] and "regime" in skip["context"]:
            regime_info = skip["context"]["regime"]
            if isinstance(regime_info, dict) and "label" in regime_info:
                regime_label = regime_info["label"]
                regime_found = True

        assert regime_found, f"Skipped trade missing regime context: {skip}"
        assert regime_label in [
            "trend_up",
            "trend_down",
            "range",
        ], f"Invalid regime label: {regime_label}"

    # Acceptance Criteria 3: Executed trades contain regime context in context_at_entry
    assert (
        len(trades_list) >= 1
    ), f"Expected at least 1 executed trade, got {len(trades_list)}"

    for trade in trades_list:
        context_at_entry = getattr(trade, "context_at_entry", None)
        assert context_at_entry is not None, f"Trade missing context_at_entry: {trade}"
        assert isinstance(
            context_at_entry, dict
        ), f"context_at_entry should be dict, got {type(context_at_entry)}"

        # Check for regime_label in context_at_entry
        regime_found = False
        if "regime_label" in context_at_entry:
            regime_label = context_at_entry["regime_label"]
            regime_found = True
        elif "regime" in context_at_entry and isinstance(
            context_at_entry["regime"], dict
        ):
            if "label" in context_at_entry["regime"]:
                regime_label = context_at_entry["regime"]["label"]
                regime_found = True

        assert (
            regime_found
        ), f"Trade context_at_entry missing regime info: {context_at_entry}"
        assert regime_label in [
            "trend_up",
            "trend_down",
            "range",
        ], f"Invalid regime label in trade: {regime_label}"


def test_entry_window_allows_delayed_entry():
    """Test that entry window allows entry when RMM unblocks within window."""
    # Bar 0: signal="long", RMM blocks
    # Bar 1: signal="long", RMM blocks
    # Bar 2: signal="long", RMM allows → should enter (within 3-bar window)
    # Bar 3: signal="flat" → exits
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 5,
            "high": [1.0] * 5,
            "low": [1.0] * 5,
            "close": [1.0] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)
    # Signal exits at bar 3
    signals = pd.Series(["enter_long", None, None, "exit_long", None], index=df.index)

    # Block for first 2 bars, then allow
    rmm_context = {
        idx[0]: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[1]: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[2]: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[3]: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[4]: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.8,
            "policy": {},
        },
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        entry_window_bars=3,  # Allow 3 bars for entry after signal transition
    )
    rem = RiskExitManager(config={})

    trades_list, _, skipped_list = cast(
        BacktestTriple,
        run_backtest(
            market_data=df,
            signals=signals,
            strategy=strategy,
            config=config,
            rem=rem,
            rmm_context=rmm_context,
            return_exposure=False,
            return_skips=True,
        ),
    )

    # Should have 1 trade that entered on bar 2
    assert len(trades_list) == 1
    assert trades_list[0].entry_time == idx[2]
    assert trades_list[0].side == "long"

    # Should have 2 skipped trades (bars 0 and 1)
    assert len(skipped_list) == 2
    assert skipped_list[0]["skip_reason"] == "rmm_block"
    assert skipped_list[1]["skip_reason"] == "rmm_block"


def test_entry_window_expires():
    """Test that entry window expires after configured bars."""
    # Bar 0: signal="long", RMM blocks
    # Bar 1: signal="long", RMM blocks
    # Bar 2: signal="long", RMM blocks (window=1, expires after bar 1)
    # Bar 3: signal="long", RMM allows → should NOT enter (window expired)
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 5,
            "high": [1.0] * 5,
            "low": [1.0] * 5,
            "close": [1.0] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)
    signals = pd.Series(["enter_long"] + [None] * 4, index=df.index)

    # Block for first 3 bars, then allow
    rmm_context = {
        idx[0]: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[1]: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[2]: {
            "allowed_sides": ["short"],
            "label": "bearish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[3]: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.8,
            "policy": {},
        },
        idx[4]: {
            "allowed_sides": ["long"],
            "label": "bullish",
            "confidence": 0.8,
            "policy": {},
        },
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        entry_window_bars=1,  # Only allow 1 bar after transition (bars 0-1)
    )
    rem = RiskExitManager(config={})

    trades_list, _, skipped_list = cast(
        BacktestTriple,
        run_backtest(
            market_data=df,
            signals=signals,
            strategy=strategy,
            config=config,
            rem=rem,
            rmm_context=rmm_context,
            return_exposure=False,
            return_skips=True,
        ),
    )

    # Should have no trades (window expired before RMM allowed)
    assert len(trades_list) == 0

    # Should have 2 skipped trades (bars 0 and 1, within window)
    assert len(skipped_list) == 2


def test_entry_window_prevents_reentry_after_rem_exit():
    """Test that we only enter once per signal transition
    (no re-entry on same signal)."""
    # Bar 0: signal transitions to "long", enter
    # Bar 1: signal still "long", position still open
    # Bar 2: signal transitions to "flat", exit
    # Bar 3: signal transitions back to "long", should enter again (new transition)
    # Bar 4: signal still "long", should NOT re-enter
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    df = pd.DataFrame(
        {
            "open": [1.0] * 5,
            "high": [1.0] * 5,
            "low": [1.0] * 5,
            "close": [1.0] * 5,
            "volume": [100] * 5,
        },
        index=idx,
    )
    strategy = _dummy_strategy_cfg()
    strategy.generate_signals(df)
    # Signal: enter_long -> None -> exit_long -> enter_long -> exit_long
    signals = pd.Series(
        ["enter_long", None, "exit_long", "enter_long", "exit_long"], index=df.index
    )

    # Allow all bars
    rmm_context = {
        ts: {
            "allowed_sides": ["long", "short"],
            "label": "neutral",
            "confidence": 0.8,
            "policy": {},
        }
        for ts in idx
    }

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=100.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        entry_window_bars=5,  # Large window
    )
    rem = RiskExitManager(config={})

    result = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=False,
        return_skips=False,
    )
    trades_list = result if isinstance(result, list) else result[0]

    # Should have 2 trades (bar 0-2 and bar 3-4)
    assert len(trades_list) == 2
    assert trades_list[0].entry_time == idx[0]
    assert trades_list[0].exit_time == idx[2]
    assert trades_list[1].entry_time == idx[3]
    assert trades_list[1].exit_time == idx[4]
