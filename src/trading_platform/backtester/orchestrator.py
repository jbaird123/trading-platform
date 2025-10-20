"""High-level orchestration functions for running backtests.

This module provides a simplified API for running complete backtests
from a RunConfig, primarily for testing and programmatic use.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy


def run_backtest_from_config(
    config: RunConfig,
    market_data: pd.DataFrame,
    strategy_config: dict[str, Any] | None = None,
    strategy_path: str | None = None,
    data_handler: Any = None,
) -> dict[str, Any]:
    """Run a complete backtest from a RunConfig.

    This is a simplified orchestration function that:
    1. Uses provided market_data
    2. Loads and compiles the strategy
    3. Generates signals
    4. Creates REM (Risk Exit Manager)
    5. Runs the backtest
    6. Returns results as a dict

    Args:
        config: RunConfig containing all backtest configuration
        market_data: Market data DataFrame
        strategy_config: Optional strategy configuration dict
        strategy_path: Optional path to strategy YAML file. If provided,
            will load strategy from this file
        data_handler: Optional DataHandler for 1-minute resolution zoom.
            If provided, enables intra-bar ambiguity resolution.

    Returns:
        Dictionary with keys:
            - trades: List of Trade objects
            - equity_curve: List of (datetime, equity) tuples
            - strategy_name: Name of the strategy
            - initial_capital: Starting capital

    Raises:
        ValueError: If no strategy configuration is available
    """
    # Get market data
    df = market_data

    # Get strategy config
    if strategy_config is None:
        if strategy_path:
            # Load strategy from file
            from pathlib import Path

            import yaml

            with open(Path(strategy_path)) as f:
                strategy_config = yaml.safe_load(f)
        elif config.strategy:
            strategy_config = config.strategy
        else:
            raise ValueError(
                "No strategy configuration provided. "
                "Provide strategy_config or strategy_path argument, or config.strategy"
            )

    # Compile strategy and generate signals
    strat = compile_strategy(strategy_config)
    signals = strat.generate_signals(df)

    # Get feature-enriched dataframe for REM
    feature_enriched_df = strat._feature_df if strat._feature_df is not None else df

    # Create REM (Risk Exit Manager)
    if config.instrument:
        # Convert dict to InstrumentDefinition if needed
        if isinstance(config.instrument, dict):
            instrument_dict = config.instrument
        else:
            instrument_dict = config.instrument.model_dump()
    else:
        instrument_dict = None

    rem_cfg = config.rem_config or {}
    exit_tie_break = getattr(config, "exit_tie_break", "stop_then_tp")
    # Pass dict directly - RiskExitManager will validate new-format configs
    # and allow legacy configs to bypass validation
    rem = RiskExitManager(
        config=rem_cfg if rem_cfg else None, instrument=instrument_dict, exit_tie_break=exit_tie_break
    )

    # Run backtest
    trades = run_backtest(
        market_data=feature_enriched_df,
        signals=signals,
        strategy=strat,
        config=config,
        rem=rem,
        rmm_context=None,  # Simplified - no RMM for basic tests
        return_exposure=True,
        return_skips=False,
        data_handler=data_handler,
    )

    # Handle return value (can be tuple or list)
    if isinstance(trades, tuple):
        trades_list = cast(list[Trade], trades[0])
        exposure = cast(list[tuple[Any, float]], trades[1])
    else:
        trades_list = cast(list[Trade], trades)
        exposure = []

    # Build equity curve from trades
    equity_curve = []
    current_equity = float(config.initial_cash)
    for trade in trades_list:
        current_equity += trade.pnl
        if trade.exit_time:
            equity_curve.append((trade.exit_time, current_equity))

    return {
        "trades": trades_list,
        "equity_curve": equity_curve or exposure,
        "strategy_name": strat.name,
        "initial_capital": float(config.initial_cash),
    }
