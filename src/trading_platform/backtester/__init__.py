from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from trading_platform.backtester.new_engine import run_event_loop_backtest
from trading_platform.core.config import RunConfig

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
    if strategy_config is None:
        if strategy_path:
            path = Path(strategy_path)
            with open(path) as f:
                if path.suffix in [".yaml", ".yml"]:
                    import yaml

                    strategy_config = yaml.safe_load(f)
                else:
                    import json

                    strategy_config = json.load(f)
        elif compiled_strategy is not None:
            strategy_config = getattr(compiled_strategy, "original_config", None)
            if strategy_config is None:
                raise ValueError(
                    "compiled_strategy provided without strategy_config or "
                    "original_config"
                )
        elif config.strategy:
            strategy_config = config.strategy
        else:
            raise ValueError(
                "No strategy configuration provided. "
                "Provide strategy_config, strategy_path, or config.strategy"
            )

    if strategy_params:
        base_params = strategy_config.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update(strategy_params)
            strategy_config["parameters"] = base_params

    if strategy_overrides:
        feat_over = strategy_overrides.get("features") or {}
        if feat_over and isinstance(strategy_config.get("features"), list):
            for f in strategy_config["features"]:
                name = str(f.get("name", ""))
                if name and name in feat_over and isinstance(feat_over[name], dict):
                    params = f.get("params") or {}
                    if isinstance(params, dict):
                        params.update(feat_over[name])
                        f["params"] = params

    result = run_event_loop_backtest(
        config=config,
        market_data=market_data,
        strategy_config=strategy_config,
        data_handler=data_handler,
        global_feature_df=None,
        rmm_context=rmm_context,
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
        "strategy_name": strategy_config.get("strategy_name")
        or strategy_config.get("name")
        or getattr(compiled_strategy, "name", None),
        "compiled_strategy": compiled_strategy,
    }
    if skipped:
        payload["skipped"] = skipped
    return payload
