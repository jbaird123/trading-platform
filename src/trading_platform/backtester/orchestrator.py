"""High-level orchestration functions for running backtests.

This module provides the SINGLE ENTRY POINT for all backtests.
All code paths (CLI, tests, sweeps, programmatic use) MUST go through
run_backtest() to ensure consistent behavior.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from trading_platform.backtester.core import (
    SimulationReturn,
    _run_backtest_simulation,
)
from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy


def run_backtest(
    config: RunConfig,
    market_data: pd.DataFrame,
    strategy_config: dict[str, Any] | None = None,
    strategy_path: str | Path | None = None,
    strategy_params: dict[str, Any] | None = None,
    strategy_overrides: dict[str, Any] | None = None,
    data_handler: Any = None,
    global_features_config_path: Path | str | None = None,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
) -> (
    dict[str, Any]
    | tuple[list[Trade], list[tuple[datetime, float]]]
    | tuple[list[Trade], list[tuple[datetime, float]], list[dict[str, Any]]]
):
    """Run a backtest. This is the ONLY public entry point for all backtests.

    All backtest entry points (CLI, tests, sweeps, programmatic use) MUST go through
    this function to ensure consistent behavior and maintain live/backtest parity.

    Args:
        config: RunConfig containing all backtest configuration
        market_data: Pre-loaded market data (REQUIRED)
        strategy_config: Optional strategy configuration dict. If not provided,
            will be loaded from strategy_path or config.strategy
        strategy_path: Optional path to strategy YAML/JSON file
        strategy_params: Optional parameter overrides for strategy (used in sweeps)
        strategy_overrides: Optional per-run overrides for strategy tunables
        data_handler: Optional DataHandler for 1-minute resolution access
        global_features_config_path: Optional path to global features config
        rmm_context: Optional RMM context for risk mode management
        return_exposure: If True, return exposure curve as second element of tuple
        return_skips: If True, return skip records as third element of tuple

    Returns:
        If return_exposure=False and return_skips=False:
            Dictionary with keys: trades, equity_curve, strategy_name, initial_capital,
            compiled_strategy, feature_enriched_df
        If return_exposure=True:
            Tuple of (trades_list, exposure_curve) or
            (trades_list, exposure_curve, skips)

    Raises:
        ValueError: If warmup validation fails or strategy config is missing
    """
    df = market_data

    # Load strategy configuration
    if strategy_config is None:
        if strategy_path:
            # Load strategy from YAML/JSON file
            path = Path(strategy_path)
            with open(path) as f:
                if path.suffix in [".yaml", ".yml"]:
                    strategy_config = yaml.safe_load(f)
                else:  # .json
                    import json

                    strategy_config = json.load(f)
        elif config.strategy:
            strategy_config = config.strategy
        else:
            raise ValueError(
                "No strategy configuration provided. "
                "Provide strategy_config, strategy_path, or config.strategy"
            )

    # Apply strategy_params from config (used for parameter sweeps)
    # This allows the config to override strategy defaults
    if strategy_params:
        base_params = strategy_config.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update(strategy_params)
            strategy_config["parameters"] = base_params

    # Apply optional per-run overrides for strategy tunables
    if strategy_overrides:
        # 1) Parameter-level overrides
        param_over = strategy_overrides.get("parameters") or {}
        if param_over:
            base_params = strategy_config.get("parameters") or {}
            if isinstance(base_params, dict):
                base_params.update(param_over)
                strategy_config["parameters"] = base_params
        # 2) Feature-level overrides
        feat_over = strategy_overrides.get("features") or {}
        if feat_over and isinstance(strategy_config.get("features"), list):
            for f in strategy_config["features"]:
                name = str(f.get("name", ""))
                if name and name in feat_over and isinstance(feat_over[name], dict):
                    params = f.get("params") or {}
                    if isinstance(params, dict):
                        params.update(feat_over[name])
                        f["params"] = params

    # Compile strategy and generate signals
    strat = compile_strategy(strategy_config)
    signals = strat.generate_signals(df)

    # Note: Warmup validation is handled in _run_backtest_simulation()
    # which validates ALL features (strategy + global) in one place

    # Get feature-enriched dataframe for REM (includes ATR, etc.)
    feature_enriched_df = strat._feature_df if strat._feature_df is not None else df
    if feature_enriched_df is not None:
        # Defensive checks: feature_df must match input df's length and index type
        if len(feature_enriched_df) != len(df) or not isinstance(
            feature_enriched_df.index, type(df.index)
        ):
            # Fall back to raw df if mismatched (can happen in tests with mocks)
            feature_enriched_df = df

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
    rem = RiskExitManager(
        config=rem_cfg if rem_cfg else None,
        instrument=instrument_dict,
        exit_tie_break=exit_tie_break,
    )

    # Run backtest simulation
    res: SimulationReturn = _run_backtest_simulation(
        market_data=feature_enriched_df,
        signals=signals,
        strategy=strat,
        config=config,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=return_exposure,
        return_skips=return_skips,
        data_handler=data_handler,
        global_features_config_path=global_features_config_path,
    )

    # Handle return value based on return_exposure and return_skips flags
    # CLI uses tuple format (return_exposure=True), tests/programmatic use dict format
    if return_exposure:
        # Return tuple format for CLI use (includes exposure curve)
        if isinstance(res, list):  # pragma: no cover - defensive guard
            raise AssertionError(
                "Simulation returned list when exposure output was requested."
            )
        return res

    # Otherwise return dict format for programmatic/test use
    # Even if return_skips=True, we return dict (skips are in the tuple
    # but we extract trades)
    skipped_records: list[dict[str, Any]] = []
    if isinstance(res, tuple):
        trades_list = cast(list[Trade], res[0])
        exposure = cast(list[tuple[Any, float]], res[1]) if len(res) > 1 else []
        if len(res) > 2:
            skipped_records = cast(list[dict[str, Any]], res[2])
    else:
        trades_list = cast(list[Trade], res)
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
        "compiled_strategy": strat,
        "feature_enriched_df": feature_enriched_df,
        "skipped": skipped_records,
    }
