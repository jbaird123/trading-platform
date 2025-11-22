from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.backtester.new_engine import run_event_loop_backtest
from trading_platform.core.config import RunConfig
from trading_platform.strategy.yaml_strategy import validate_strategy_config

__all__ = ["run_backtest", "run_event_loop_backtest"]


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
    rmm_context: dict[Any, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    compiled_strategy: Any | None = None,
    precomputed_signals: Any | None = None,
    feature_enriched_df: pd.DataFrame | None = None,
    rem_instance: Any | None = None,
    cache_root: Path | str | None = None,
) -> (
    dict[str, Any]
    | tuple[list[Any], list[tuple[Any, float]]]
    | tuple[list[Any], list[tuple[Any, float]], list[dict[str, Any]]]
):
    """Compatibility wrapper around the event-loop backtester."""
    # Legacy-only params ignored: precomputed_signals, feature_enriched_df,
    # rem_instance, cache_root, global_features_config_path, global_feature_defs.
    required_cols = {"open", "high", "low", "close", "volume"}
    missing_cols = required_cols - set(market_data.columns)
    if missing_cols:
        raise ValueError(f"missing required columns: {sorted(missing_cols)}")
    if pd.isna(market_data["close"]).any():
        raise ValueError("close has NaNs")
    if precomputed_signals is not None and len(precomputed_signals) != len(market_data):
        raise ValueError("signals length mismatch")
    if precomputed_signals is not None:

        def _is_blank(val: Any) -> bool:
            pd_local: Any
            try:
                import pandas as pd_local
            except ImportError:  # pragma: no cover
                pd_local = None
            if val is None:
                return True
            if pd_local is not None:
                try:
                    if pd_local.isna(val):
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

    if strategy_params:
        base_params = strategy_cfg.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update(strategy_params)
            strategy_cfg["parameters"] = base_params

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

    global_feature_df = None
    if global_features_config_path is not None:
        from trading_platform.core.feature_resolver import resolve_global_features
        from trading_platform.strategy.features import compute_features

        tf = None
        if config.instrument and isinstance(config.instrument, dict):
            tf = config.instrument.get("timeframe")
        tf_str = str(tf) if tf is not None else ""
        resolved = resolve_global_features(
            execution_timeframe=tf_str, config_path=Path(global_features_config_path)
        )
        if not resolved:
            global_feature_df = None
        else:
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
                market_data, specs, strategy_cfg.get("parameters")
            )
            base_cols = set(market_data.columns)
            global_feature_df = global_feature_df.loc[
                :, [c for c in global_feature_df.columns if c not in base_cols]
            ]
            if global_feature_df.empty:
                global_feature_df = None
            if global_feature_df is not None:
                for col in global_feature_df.columns:
                    series = global_feature_df[col]
                    first_valid = series.first_valid_index()
                    if first_valid is None:
                        raise ValueError(f"Global feature '{col}' is NaN")
                    first_valid_idx = cast(Any, first_valid)
                    if pd.isna(series.loc[first_valid_idx:]).any():
                        raise ValueError(f"Global feature '{col}' is NaN")
                global_feature_df = global_feature_df.ffill().bfill()

    result = run_event_loop_backtest(
        config=config,
        market_data=market_data,
        strategy_config=strategy_cfg,
        data_handler=data_handler,
        compiled_strategy=compiled_strategy,
        precomputed_signals=precomputed_signals,
        strategy_feature_df=feature_enriched_df,
        global_feature_df=global_feature_df,
        rmm_context=rmm_context,
        rem_instance=rem_instance,
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
        "feature_enriched_df": feature_enriched_df,
    }
    if skipped:
        payload["skipped"] = skipped
    return payload
