"""High-level orchestration functions for running backtests.

This module provides the SINGLE ENTRY POINT for all backtests.
All code paths (CLI, tests, sweeps, programmatic use) MUST go through
run_backtest() to ensure consistent behavior.
"""

# ruff: noqa: TRY301

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from trading_platform.backtester.core import (
    SimulationReturn,
    _execute_backtest_loop,
)
from trading_platform.backtester.warmup import calculate_warmup_start_date
from trading_platform.core.config import RunConfig
from trading_platform.core.feature_resolver import resolve_global_features
from trading_platform.portfolio.trade import Trade
from trading_platform.regime_market_manager.gating import ProfitabilityGatingEngine
from trading_platform.regime_market_manager.models import RMMGatingProfile
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.features import _resolve_parameter
from trading_platform.strategy.yaml_strategy import CompiledStrategy, compile_strategy

logger = logging.getLogger(__name__)

SignalInput = pd.Series | list[Any] | tuple[Any, ...]


def _infer_execution_timeframe(config: RunConfig, market_data: pd.DataFrame) -> str:
    instrument_cfg = getattr(config, "instrument", None) or {}
    if isinstance(instrument_cfg, dict):
        instrument_tf = instrument_cfg.get("timeframe")
    else:
        instrument_tf = getattr(instrument_cfg, "timeframe", None)
    if instrument_tf:
        return str(instrument_tf)
    data_req_cfg = getattr(config, "data_request", None) or {}
    if isinstance(data_req_cfg, dict):
        data_req_tf = data_req_cfg.get("timeframe")
    else:
        data_req_tf = getattr(data_req_cfg, "timeframe", None)
    if data_req_tf:
        return str(data_req_tf)
    if market_data is not None and not market_data.empty:
        try:
            return _detect_timeframe_from_index(market_data.index)
        except Exception:
            return "1H"
    raise ValueError(
        "Execution timeframe is required. Provide instrument.timeframe or "
        "data_request.timeframe in the run config."
    )


def _detect_timeframe_from_index(index: pd.Index) -> str:
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("Cannot detect timeframe without DatetimeIndex data.")
    if len(index) < 2:
        raise ValueError("Need at least two bars to detect timeframe.")
    diffs = index[1:] - index[:-1]
    most_common = diffs.value_counts().idxmax()
    minutes = int(pd.Timedelta(most_common).total_seconds() / 60)
    mapping = {
        1: "1min",
        5: "5min",
        15: "15min",
        60: "1H",
        240: "4H",
        1440: "1D",
        10080: "1W",
    }
    timeframe = mapping.get(minutes)
    if not timeframe:
        raise ValueError(f"Detected unsupported timeframe cadence: {minutes} minutes.")
    return timeframe


def _resolve_global_feature_defs(
    execution_timeframe: str, config_path: Path | str | None
) -> list[dict[str, Any]]:
    if not config_path:
        return []
    path = Path(config_path)
    resolved = resolve_global_features(execution_timeframe, config_path=path)
    feature_defs: list[dict[str, Any]] = []
    for feature in resolved:
        feature_defs.append(
            {
                "name": feature.name,
                "type": feature.type,
                "params": feature.params,
                "source": feature.source,
                "timeframe": feature.timeframe,
            }
        )
    return feature_defs


def _parse_data_request_bounds(
    data_request: dict[str, Any] | None, market_data: pd.DataFrame
) -> tuple[pd.Timestamp, pd.Timestamp, bool]:
    if data_request is None:
        data_request = {}

    target_start = cast(pd.Timestamp, market_data.index.min())
    target_end = cast(pd.Timestamp, market_data.index.max())
    start_explicit = False

    start_val = data_request.get("start")
    if start_val is not None:
        try:
            target_start = pd.to_datetime(start_val, utc=True)
            start_explicit = True
        except Exception:
            pass

    end_val = data_request.get("end")
    if end_val is not None:
        try:
            end_ts = pd.to_datetime(end_val, utc=True)
            if isinstance(end_val, str) and len(end_val) == 10:
                end_ts = end_ts + timedelta(days=1) - timedelta(seconds=1)
            target_end = end_ts
        except Exception:
            pass

    return target_start, target_end, start_explicit


def _resolve_strategy_features_for_warmup(
    strat: Any,
) -> list[dict[str, Any]]:
    resolved_features: list[dict[str, Any]] = []
    params = getattr(strat, "parameters", None) or {}
    features = getattr(strat, "features", None) or []
    for feature in features:
        feature_copy = feature.copy()
        feat_params = feature_copy.get("params")
        if isinstance(feat_params, dict):
            feature_copy["params"] = {
                key: _resolve_parameter(value, params)
                for key, value in feat_params.items()
            }
        resolved_features.append(feature_copy)
    return resolved_features


def ensure_market_data_with_warmup(
    *,
    market_data: pd.DataFrame,
    execution_timeframe: str,
    strategy_features: list[dict[str, Any]],
    global_features: list[dict[str, Any]],
    data_request: dict[str, Any] | None,
    data_handler: Any | None,
) -> pd.DataFrame:
    """Ensure market data includes enough history for indicator warmup."""
    if market_data.empty:
        return market_data

    target_start, target_end, start_explicit = _parse_data_request_bounds(
        data_request, market_data
    )

    if not isinstance(market_data.index, pd.DatetimeIndex):
        logger.warning("Market data index is not datetime; skipping warmup extension.")
        return cast(pd.DataFrame, market_data.loc[target_start:target_end].copy())

    if not strategy_features and not global_features:
        return market_data.loc[target_start:target_end].copy()

    working_data = market_data

    def _calculate(start_data: pd.DataFrame) -> tuple[pd.Timestamp, dict[str, Any]]:
        warmup_start_date, info = calculate_warmup_start_date(
            strategy_features=strategy_features,
            global_features=global_features,
            execution_timeframe=execution_timeframe,
            market_data=start_data,
            backtest_start_date=target_start,
        )
        warmup_ts = pd.Timestamp(info.get("earliest_timestamp") or warmup_start_date)
        if warmup_ts.tzinfo is None:
            warmup_ts = warmup_ts.tz_localize("UTC")
        else:
            warmup_ts = warmup_ts.tz_convert("UTC")
        return warmup_ts, info

    def _fallback(reason: str) -> pd.DataFrame:
        logger.debug(
            "Warmup calculation could not extend data (%s); "
            "falling back to requested window.",
            reason,
        )
        return cast(pd.DataFrame, market_data.loc[target_start:target_end].copy())

    try:
        warmup_ts, _ = _calculate(working_data)
    except ValueError as exc:
        if not start_explicit or data_handler is None:
            return _fallback(str(exc))
        logger.debug(
            "Warmup calculation failed (%s); requesting additional history.",
            exc,
        )
        working_data = cast(
            pd.DataFrame,
            data_handler.get_data(
                timeframe=execution_timeframe,
                start=None,
                end=None,
            ),
        )
        try:
            warmup_ts, _ = _calculate(working_data)
        except ValueError as inner_exc:
            return _fallback(str(inner_exc))
    try:
        idx = working_data.index.get_indexer([warmup_ts], method="bfill")[0]
        if idx == -1:
            raise KeyError
        warmup_ts = cast(pd.Timestamp, working_data.index[idx])
    except Exception:
        warmup_ts = cast(pd.Timestamp, working_data.index.min())

    if warmup_ts < working_data.index.min():
        raise ValueError(
            "Insufficient historical data to satisfy indicator warmup. "
            f"Warmup requires data before {warmup_ts}, but market data "
            f"starts at {working_data.index.min()}."
        )

    trimmed = working_data.loc[warmup_ts:target_end].copy()
    if trimmed.empty:
        raise ValueError(
            "Warmup trimming removed all market data. "
            "Verify data_request bounds and feature lookbacks."
        )
    return trimmed


def run_backtest(
    config: RunConfig,
    market_data: pd.DataFrame,
    strategy_config: dict[str, Any] | None = None,
    strategy_path: str | Path | None = None,
    strategy_params: dict[str, Any] | None = None,
    strategy_overrides: dict[str, Any] | None = None,
    data_handler: Any = None,
    global_features_config_path: Path | str | None = None,
    global_feature_defs: list[dict[str, Any]] | None = None,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    compiled_strategy: CompiledStrategy | None = None,
    precomputed_signals: SignalInput | None = None,
    feature_enriched_df: pd.DataFrame | None = None,
    rem_instance: RiskExitManager | None = None,
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
        compiled_strategy: Precompiled strategy instance (skips YAML loading).
        precomputed_signals: Optional Series/sequence of commands to use instead
            of calling `strategy.generate_signals`.
        feature_enriched_df: Optional feature-enriched dataframe to use when
            precomputed signals are supplied.
        rem_instance: Optional RiskExitManager to reuse (primarily for tests).

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
    strategy_metadata: dict[str, Any] = {}
    strategy_archetype = "trend_following"

    if compiled_strategy is None:
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

        strategy_metadata = strategy_config.get("metadata") or {}
        strategy_archetype = str(
            strategy_metadata.get("strategy_archetype", "trend_following")
        )
        strat = compile_strategy(strategy_config)
    else:
        strat = compiled_strategy
        strategy_config = strategy_config or {}
        metadata = getattr(strat, "metadata", None)
        if isinstance(metadata, dict):
            strategy_metadata = metadata
        strategy_archetype = str(
            strategy_metadata.get(
                "strategy_archetype",
                getattr(strat, "name", "trend_following"),
            )
        )

    execution_timeframe = _infer_execution_timeframe(config, df)

    resolved_global_features: list[dict[str, Any]]
    if global_feature_defs is not None:
        resolved_global_features = list(global_feature_defs)
    else:
        resolved_global_features = _resolve_global_feature_defs(
            execution_timeframe, global_features_config_path
        )
    strategy_feature_defs = _resolve_strategy_features_for_warmup(strat)

    df = ensure_market_data_with_warmup(
        market_data=df,
        execution_timeframe=execution_timeframe,
        strategy_features=strategy_feature_defs,
        global_features=resolved_global_features,
        data_request=config.data_request,
        data_handler=data_handler,
    )

    if precomputed_signals is not None:
        if isinstance(precomputed_signals, pd.Series):
            signals = precomputed_signals
        else:
            signals = pd.Series(list(precomputed_signals), index=df.index)
        if len(signals) != len(df):
            raise ValueError(
                "precomputed_signals length must equal market_data length "
                f"({len(signals)} != {len(df)})"
            )
        if isinstance(precomputed_signals, pd.Series) and not signals.index.equals(
            df.index
        ):
            raise ValueError("precomputed_signals index must match market_data index")
        if feature_enriched_df is None:
            cached_features = getattr(strat, "_feature_df", None)
            feature_enriched_df = cached_features if cached_features is not None else df
    else:
        signals = strat.generate_signals(df)
        feature_enriched_df = strat._feature_df if strat._feature_df is not None else df

    # Note: Warmup validation is handled in _execute_backtest_loop(), which
    # validates strategy and global features together.

    # Defensive checks: feature_df must match input df's length and index type
    if len(feature_enriched_df) != len(df) or not isinstance(
        feature_enriched_df.index, type(df.index)
    ):
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
    rem = rem_instance or RiskExitManager(
        config=rem_cfg if rem_cfg else None,
        instrument=instrument_dict,
        exit_tie_break=exit_tie_break,
    )

    gating_engine: ProfitabilityGatingEngine | None = None
    gating_metadata: dict[str, Any] | None = None
    if config.rmm_gating_profile:
        profile = RMMGatingProfile.model_validate(config.rmm_gating_profile)
        gating_engine = ProfitabilityGatingEngine(profile)
        instrument_timeframe = None
        instrument_symbol = None
        if instrument_dict:
            instrument_timeframe = instrument_dict.get("timeframe")
            instrument_symbol = instrument_dict.get("symbol")
        gating_metadata = {
            "strategy_archetype": strategy_archetype,
            "instrument_timeframe": instrument_timeframe,
            "instrument_symbol": instrument_symbol,
        }

    # Run backtest simulation
    res: SimulationReturn = _execute_backtest_loop(
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
        global_feature_defs=resolved_global_features,
        gating_engine=gating_engine,
        gating_metadata=gating_metadata,
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
