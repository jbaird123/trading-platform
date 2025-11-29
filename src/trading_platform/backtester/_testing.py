"""Internal testing utilities for backtester.

This module provides entry points for unit tests that require synthetic data.
Do not use these functions in production code.

For production use, use `run_backtest()` from `trading_platform.backtester`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from trading_platform.backtester.engine import BacktestResult, run_event_loop_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def run_backtest_with_synthetic_data(
    *,
    config: RunConfig,
    market_data: pd.DataFrame,
    strategy_config: dict[str, Any] | None = None,
    compiled_strategy: CompiledStrategy | None = None,
    precomputed_signals: Any | None = None,
    strategy_feature_df: pd.DataFrame | None = None,
    data_handler: Any | None = None,
    global_feature_df: pd.DataFrame | None = None,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    rem_instance: RiskExitManager | None = None,
) -> BacktestResult:
    """Run backtest with synthetic/fabricated market data.

    FOR UNIT TESTS ONLY. Do not use in production code.

    This function is a thin wrapper around the backtest engine that allows
    tests to pass synthetic market data directly. Production code should use
    `run_backtest()` which handles data loading and warmup automatically.

    Args:
        config: Run configuration
        market_data: Synthetic OHLCV DataFrame for testing
        strategy_config: Strategy configuration dict
        compiled_strategy: Pre-compiled strategy (alternative to strategy_config)
        precomputed_signals: Optional pre-computed signals
        strategy_feature_df: Optional pre-computed strategy features
        data_handler: Optional data handler for intra-bar zoom
        global_feature_df: Optional pre-computed global features
        rmm_context: Optional RMM context per bar
        rem_instance: Optional RiskExitManager instance

    Returns:
        BacktestResult with trades, equity curve, and metadata

    Raises:
        ValueError: If market_data is missing required columns or has NaN values
    """
    # Validate market data
    required_cols = {"open", "high", "low", "close", "volume"}
    missing_cols = required_cols - set(market_data.columns)
    if missing_cols:
        raise ValueError(f"missing required columns: {sorted(missing_cols)}")
    if pd.isna(market_data["close"]).any():
        raise ValueError("close has NaNs")

    # Validate precomputed signals if provided
    if precomputed_signals is not None:
        if len(precomputed_signals) != len(market_data):
            raise ValueError(
                f"signals length mismatch: got {len(precomputed_signals)} signals "
                f"but {len(market_data)} bars"
            )

        def _is_blank(val: Any) -> bool:
            if val is None:
                return True
            try:
                if pd.isna(val):
                    return True
            except Exception:
                pass
            try:
                import math

                if isinstance(val, float) and math.isnan(val):
                    return True
            except Exception:
                pass
            return False

        bad = [
            v
            for v in list(precomputed_signals)
            if not (
                _is_blank(v)
                or (
                    isinstance(v, str)
                    and v in {"enter_long", "enter_short", "exit_long", "exit_short"}
                )
                or hasattr(v, "command")  # Signal-like
            )
        ]
        if bad:
            raise ValueError("invalid command values")

    return run_event_loop_backtest(
        config=config,
        market_data=market_data,
        strategy_config=strategy_config,
        compiled_strategy=compiled_strategy,
        precomputed_signals=precomputed_signals,
        strategy_feature_df=strategy_feature_df,
        data_handler=data_handler,
        global_feature_df=global_feature_df,
        rmm_context=rmm_context,
        rem_instance=rem_instance,
        profiler=None,
    )
