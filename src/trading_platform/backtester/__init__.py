from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from trading_platform.backtester.engine import run_event_loop_backtest
from trading_platform.backtester.warmup_helpers import (
    ensure_market_data_with_warmup,
    infer_execution_timeframe,
    resolve_global_feature_defs,
    resolve_strategy_features_for_warmup,
)
from trading_platform.core import paths
from trading_platform.core.config import RunConfig
from trading_platform.core.currency_converter import CurrencyConverter
from trading_platform.core.global_features_cache import (
    cache_covers_features,
    load_cached_global_features,
)
from trading_platform.strategy.yaml_strategy import validate_strategy_config

__all__ = ["run_backtest"]


# Global feature cache: keyed by (config_path, timeframe, data_range)
# This avoids recomputing identical global features across repeated run_backtest calls
# (e.g., in parameter sweeps, monte carlo, walk-forward optimization)
_GLOBAL_FEATURE_CACHE: dict[tuple[str, str, str], pd.DataFrame] = {}


def _make_global_feature_cache_key(
    config_path: Path | str,
    execution_timeframe: str | None,
    instrument_tf: str | None,
    market_data: pd.DataFrame,
) -> tuple[str, str, str]:
    """Create a cache key for global features.

    Note: Global features are defined in config/features/global.yaml and do NOT
    use strategy parameter references (${param}). Therefore, the cache key does
    not include strategy_params - the same global features are valid across all
    parameter combinations in a sweep.
    """
    # Resolve config path to absolute for consistent keying
    resolved_path = str(Path(config_path).resolve())

    # Timeframe used for feature resolution
    tf = instrument_tf or execution_timeframe or ""

    # Data range - use start/end timestamps and length
    data_range = f"{market_data.index[0]}_{market_data.index[-1]}_{len(market_data)}"

    return (resolved_path, tf, data_range)


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

    # Compute global features with caching
    # Cache avoids recomputing identical features in sweeps/monte carlo/walk-forward
    global_feature_df = None
    instrument_tf = None
    if config.instrument and isinstance(config.instrument, dict):
        instrument_tf = config.instrument.get("timeframe")

    if global_features_config_path is not None:
        # Check in-memory cache first
        cache_key = _make_global_feature_cache_key(
            config_path=global_features_config_path,
            execution_timeframe=execution_timeframe,
            instrument_tf=instrument_tf,
            market_data=market_data,
        )
        cached_df = _GLOBAL_FEATURE_CACHE.get(cache_key)

        if cached_df is not None:
            global_feature_df = cached_df
        else:
            # Try file-based cache before computing
            file_cache_loaded = False
            instrument_dict = config.instrument or {}
            symbol = instrument_dict.get("symbol") or (
                data_request.get("symbol") if data_request else None
            )
            if symbol and execution_timeframe:
                # Get feature names from global feature defs
                feature_names = [
                    f["name"]
                    for f in global_feature_defs
                    if isinstance(f.get("name"), str)
                ]
                config_path_resolved = Path(global_features_config_path)
                if feature_names and cache_covers_features(
                    symbol=symbol,
                    cache_root=paths.GLOBAL_FEATURE_CACHE_DIR,
                    config_path=config_path_resolved,
                    timeframe=execution_timeframe,
                    feature_names=feature_names,
                ):
                    instrument_def = get_instrument_definition(symbol)
                    cache_result = load_cached_global_features(
                        symbol=symbol,
                        cache_root=paths.GLOBAL_FEATURE_CACHE_DIR,
                        config_path=config_path_resolved,
                        timeframe=execution_timeframe,
                        feature_names=feature_names,
                        session_group=instrument_def.session_group,
                    )
                    if cache_result is not None:
                        global_feature_df, _ = cache_result
                        file_cache_loaded = True
                        # Store in in-memory cache for future calls
                        _GLOBAL_FEATURE_CACHE[cache_key] = global_feature_df

            # Compute if not loaded from file cache
            if not file_cache_loaded:
                if profiler is not None and profiler.enabled:
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
                    if global_feature_df is not None:
                        _GLOBAL_FEATURE_CACHE[cache_key] = global_feature_df
                else:
                    global_feature_df = _compute_global_features(
                        market_data=market_data,
                        global_features_config_path=global_features_config_path,
                        execution_timeframe=execution_timeframe,
                        instrument_tf=instrument_tf,
                        strategy_params=strategy_cfg.get("parameters"),
                    )
                    if global_feature_df is not None:
                        _GLOBAL_FEATURE_CACHE[cache_key] = global_feature_df

    # Initialize currency converter for P&L normalization to USD
    reference_currency = getattr(config, "reference_currency", "USD")
    currency_converter = CurrencyConverter(
        reference_currency=reference_currency,
        data_root=paths.RAW_DATA_DIR,
    )
    # Preload conversion data needed for the trading symbol
    # symbol is validated non-None above at line 119-120
    assert symbol is not None
    currency_converter.preload_for_symbol(symbol)

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
        currency_converter=currency_converter,
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

    # Validate no NaNs - all global features must be fully populated
    nan_cols = [
        col for col in global_feature_df.columns if global_feature_df[col].isna().any()
    ]
    if nan_cols:
        raise ValueError(
            f"Global features contain NaNs: {', '.join(sorted(nan_cols))}. "
            "Ensure all features are fully populated."
        )

    return global_feature_df
