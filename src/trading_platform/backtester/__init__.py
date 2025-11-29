from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.backtester.engine import run_event_loop_backtest
from trading_platform.backtester.warmup_helpers import (
    ensure_market_data_with_warmup,
    infer_execution_timeframe,
    resolve_global_feature_defs,
    resolve_strategy_features_for_warmup,
)
from trading_platform.core.config import RunConfig
from trading_platform.strategy.yaml_strategy import validate_strategy_config

__all__ = ["run_backtest"]


def run_backtest(
    config: RunConfig,
    strategy_config: dict[str, Any] | None = None,
    strategy_path: str | Path | None = None,
    strategy_params: dict[str, Any] | None = None,
    strategy_overrides: dict[str, Any] | None = None,
    global_features_config_path: Path | str | None = None,
    rmm_context: dict[Any, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    compiled_strategy: Any | None = None,
    profiler: Any | None = None,
) -> (
    dict[str, Any]
    | tuple[list[Any], list[tuple[Any, float]]]
    | tuple[list[Any], list[tuple[Any, float]], list[dict[str, Any]]]
):
    """Run a backtest with automatic data loading and warmup.

    This is the primary entry point for running backtests. It handles:
    - Loading market data from disk based on config.data_request
    - Applying warmup from the earliest available data
    - Computing global features
    - Running the backtest engine

    Args:
        config: Run configuration containing data_request with symbol, timeframe,
            start (trading window start), and end parameters
        strategy_config: Strategy configuration dict
        strategy_path: Path to strategy YAML/JSON file (alternative to strategy_config)
        strategy_params: Parameter overrides for the strategy
        strategy_overrides: Feature-level overrides for the strategy
        global_features_config_path: Path to global features config
        rmm_context: Optional RMM context per bar
        return_exposure: If True, return (trades, equity) tuple instead of dict
        return_skips: If True and return_exposure=True, return (trades, equity, skips)
        compiled_strategy: Pre-compiled strategy (alternative to strategy_config)
        profiler: Optional performance profiler

    Returns:
        Either a dict with trades/equity_curve/metadata, or tuple(s) if
        return_exposure=True

    Raises:
        ValueError: If config.data_request is missing or incomplete
    """
    from trading_platform.core import paths
    from trading_platform.data.handler import DataHandler
    from trading_platform.data.instrument import get_instrument_definition

    # Extract data request from config
    data_request = getattr(config, "data_request", None)
    if not isinstance(data_request, dict):
        raise ValueError(
            "config.data_request is required. "
            "It must contain at least 'symbol' and 'timeframe'."
        )

    symbol = data_request.get("symbol")
    timeframe = data_request.get("timeframe")
    end = data_request.get("end")

    if not symbol:
        raise ValueError("config.data_request must contain 'symbol'")
    if not timeframe:
        raise ValueError("config.data_request must contain 'timeframe'")

    # Create DataHandler and load data
    # Note: We do NOT pass 'start' to get_data - we load ALL available data for warmup
    instrument_def = get_instrument_definition(symbol)
    data_handler = DataHandler(
        symbol=symbol,
        data_root=paths.RAW_DATA_DIR,
        instrument=instrument_def,
    )

    # Load full data (no start filter - warmup uses all available data)
    # Only apply end filter if specified
    market_data = data_handler.get_data(timeframe=timeframe, end=end)

    # Validate market data
    required_cols = {"open", "high", "low", "close", "volume"}
    missing_cols = required_cols - set(market_data.columns)
    if missing_cols:
        raise ValueError(f"missing required columns: {sorted(missing_cols)}")
    if pd.isna(market_data["close"]).any():
        raise ValueError("close has NaNs")

    # Resolve strategy config
    strategy_cfg = strategy_config
    if strategy_cfg is None and strategy_path:
        path = Path(strategy_path)
        with open(path) as f:
            if path.suffix in [".yaml", ".yml"]:
                import yaml

                strategy_cfg = yaml.safe_load(f)
            else:
                import json

                strategy_cfg = json.load(f)
    if strategy_cfg is None and config.strategy:
        strategy_cfg = config.strategy
    if strategy_cfg is None and compiled_strategy is not None:
        strategy_cfg = getattr(compiled_strategy, "original_config", None)
        if strategy_cfg is None:
            raise ValueError(
                "compiled_strategy is missing original_config. "
                "Use compile_strategy or provide strategy_config/strategy_path."
            )
    if strategy_cfg is None:
        raise ValueError(
            "No strategy configuration provided. "
            "Provide strategy_config, strategy_path, or config.strategy."
        )

    # Enforce strict validation
    validate_strategy_config(strategy_cfg)

    # Apply strategy params
    if strategy_params:
        base_params = strategy_cfg.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update(strategy_params)
            strategy_cfg["parameters"] = base_params

    # Apply strategy overrides
    if strategy_overrides:
        feat_over = strategy_overrides.get("features") or {}
        if feat_over and isinstance(strategy_cfg.get("features"), list):
            for f in strategy_cfg["features"]:
                name = str(f.get("name", ""))
                if name and name in feat_over and isinstance(feat_over[name], dict):
                    params = f.get("params") or {}
                    if isinstance(params, dict):
                        params.update(feat_over[name])
                        f["params"] = params

    # Enforce warmup: always include earliest available data
    execution_timeframe = infer_execution_timeframe(config, market_data)

    # Resolve strategy/global feature defs for warmup
    if compiled_strategy is not None:
        strategy_features = resolve_strategy_features_for_warmup(compiled_strategy)
    else:
        strategy_features = (
            strategy_cfg.get("features", []) if isinstance(strategy_cfg, dict) else []
        )
    try:
        global_feature_defs = resolve_global_feature_defs(
            execution_timeframe, global_features_config_path
        )
    except FileNotFoundError:
        global_feature_defs = []

    # Apply warmup - uses earliest available bar
    market_data = ensure_market_data_with_warmup(
        market_data=market_data,
        execution_timeframe=execution_timeframe,
        strategy_features=strategy_features,
        global_features=global_feature_defs,
        data_request=data_request,
        data_handler=data_handler,
    )

    # Compute global features (not using cache for now - future change)
    global_feature_df = None
    instrument_tf = None
    if config.instrument and isinstance(config.instrument, dict):
        instrument_tf = config.instrument.get("timeframe")
    if (
        global_features_config_path is not None
        and profiler is not None
        and profiler.enabled
    ):
        with profiler.stage(
            "compute_global_features",
            metadata={
                "config_path": str(global_features_config_path),
            },
        ):
            global_feature_df = _compute_global_features(
                market_data=market_data,
                global_features_config_path=global_features_config_path,
                execution_timeframe=execution_timeframe,
                instrument_tf=instrument_tf,
                strategy_params=strategy_cfg.get("parameters"),
            )
    elif global_features_config_path is not None:
        global_feature_df = _compute_global_features(
            market_data=market_data,
            global_features_config_path=global_features_config_path,
            execution_timeframe=execution_timeframe,
            instrument_tf=instrument_tf,
            strategy_params=strategy_cfg.get("parameters"),
        )

    # Run the backtest engine
    result = run_event_loop_backtest(
        config=config,
        market_data=market_data,
        strategy_config=strategy_cfg,
        data_handler=data_handler,
        compiled_strategy=compiled_strategy,
        precomputed_signals=None,
        strategy_feature_df=None,
        global_feature_df=global_feature_df,
        rmm_context=rmm_context,
        rem_instance=None,
        profiler=profiler,
    )

    trades = result.trades
    equity = result.equity_curve
    skipped = result.skipped

    if return_exposure:
        if return_skips:
            return trades, equity, skipped
        return trades, equity

    payload: dict[str, Any] = {
        "trades": trades,
        "equity_curve": equity,
        "strategy_name": (strategy_cfg or {}).get("strategy_name")
        or (strategy_cfg or {}).get("name")
        or getattr(compiled_strategy, "name", None),
        "compiled_strategy": compiled_strategy,
        "feature_enriched_df": None,
        "profiler": result.profiler,
        # Include market data and data handler for callers that need them
        # (e.g., CLI for RMM, parameter sweep, walk-forward analysis)
        "market_data": market_data,
        "data_handler": data_handler,
    }
    if skipped:
        payload["skipped"] = skipped
    return payload


def _compute_global_features(
    market_data: pd.DataFrame,
    global_features_config_path: Path | str,
    execution_timeframe: str | None,
    instrument_tf: str | None,
    strategy_params: dict[str, Any] | None,
) -> pd.DataFrame | None:
    """Compute global features from config path.

    Args:
        market_data: OHLCV DataFrame
        global_features_config_path: Path to global features config
        execution_timeframe: Inferred execution timeframe
        instrument_tf: Instrument timeframe from config
        strategy_params: Strategy parameters for feature computation

    Returns:
        DataFrame with global features, or None if no features resolved
    """
    from trading_platform.core.feature_resolver import resolve_global_features
    from trading_platform.strategy.features import compute_features

    tf = instrument_tf or execution_timeframe
    tf_str = str(tf) if tf else ""
    resolved = resolve_global_features(
        execution_timeframe=tf_str,
        config_path=Path(global_features_config_path),
    )
    if not resolved:
        return None

    specs = [
        {
            "name": f.name,
            "type": f.type,
            "params": f.params,
            "source": f.source,
            **(
                {}
                if f.timeframe == tf
                else {"timeframe": f.timeframe}
                if f.timeframe
                else {}
            ),
        }
        for f in resolved
    ]
    global_feature_df = compute_features(
        market_data,
        specs,
        strategy_params,
    )
    base_cols = set(market_data.columns)
    global_feature_df = global_feature_df.loc[
        :, [c for c in global_feature_df.columns if c not in base_cols]
    ]
    if global_feature_df.empty:
        return None

    # Validate no NaNs in valid range
    for col in global_feature_df.columns:
        series = global_feature_df[col]
        first_valid = series.first_valid_index()
        if first_valid is None:
            raise ValueError(f"Global feature '{col}' is NaN")
        first_valid_idx = cast(Any, first_valid)
        if pd.isna(series.loc[first_valid_idx:]).any():
            raise ValueError(f"Global feature '{col}' is NaN")

    return global_feature_df.ffill().bfill()
