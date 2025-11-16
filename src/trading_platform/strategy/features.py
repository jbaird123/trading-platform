"""
Feature computation module for trading strategies.

Provides the compute_features() function plus helper wrappers used by legacy code.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.tseries.frequencies import to_offset

from trading_platform.data.timeframe_aliases import canonicalize_timeframe
from trading_platform.strategy import indicator_implementations as _impl
from trading_platform.strategy.indicator_implementations import (
    _price_series,
    adx,
    atr,
    ema,
    hhv,
    llv,
    rsi,
)

__all__ = [
    "compute_features",
    "_price_series",
    "_resolve_parameter",
    "adx",
    "atr",
    "bb_width",
    "donchian_channels",
    "ema",
    "ema_slope",
    "hhv",
    "llv",
    "rsi",
]


def ema_slope(series: pd.Series, length: int, slope_period: int = 1) -> pd.Series:
    """EMA Slope - wrapper for backwards compatibility."""
    df = pd.DataFrame({"close": series})
    result: pd.Series = _impl.compute_ema_slope(
        df, {"length": length, "slope_period": slope_period}, "close", None
    )
    return result


def bb_width(series: pd.Series, length: int, ndev: float) -> pd.Series:
    """BB Width - wrapper for backwards compatibility."""
    df = pd.DataFrame({"close": series})
    result: pd.Series = _impl.compute_bb_width(
        df, {"length": length, "ndev": ndev}, "close", None
    )
    return result


def donchian_channels(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    """Donchian Channels - wrapper for backwards compatibility."""
    from trading_platform.strategy.indicator_implementations import compute_dc

    result = compute_dc(df, {"length": length}, "close", None)
    return result["upper"], result["lower"]


def _resolve_parameter(param_value: Any, strategy_parameters: dict) -> Any:
    """Resolve parameter placeholders like ${param_name}."""
    if not isinstance(param_value, str):
        return param_value
    if param_value.startswith("${") and param_value.endswith("}"):
        param_name = param_value[2:-1]
        if param_name in strategy_parameters:
            return strategy_parameters[param_name]
        raise ValueError(f"Parameter '{param_name}' not found in strategy parameters.")
    return param_value


def compute_features(
    df: pd.DataFrame,
    specs: list[dict],
    strategy_parameters: dict | None = None,
) -> pd.DataFrame:
    """Compute features via the canonical global feature pipeline."""
    if strategy_parameters is None:
        strategy_parameters = {}

    execution_timeframe = _infer_execution_timeframe(df.index)

    from trading_platform.core.global_feature_pipeline import build_global_feature_frame

    features_df, _ = build_global_feature_frame(
        market_data=df,
        feature_defs=specs,
        execution_timeframe=execution_timeframe,
        strategy_parameters=strategy_parameters,
    )

    return df.join(features_df, how="left")


_MINUTE_TO_TIMEFRAME = {
    1: "1min",
    5: "5min",
    15: "15min",
    30: "30min",
    60: "1h",
    120: "2h",
    240: "4h",
    1440: "1d",
    10080: "1w",
}


def _infer_execution_timeframe(index: pd.Index) -> str:
    """Infer a canonical timeframe label from a datetime index."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return "1min"

    try:
        freq = pd.infer_freq(index)
    except (ValueError, TypeError):
        freq = None

    if freq:
        try:
            offset = to_offset(freq)
            nanos = getattr(offset, "nanos", None)
            delta_attr = getattr(offset, "delta", None)
            if nanos is not None and nanos != 0:
                delta = pd.to_timedelta(nanos, unit="ns")
            elif delta_attr is not None:
                delta = pd.to_timedelta(delta_attr)
            else:
                delta = pd.to_timedelta(freq)
            minutes = int(delta.total_seconds() // 60)
            tf = _MINUTE_TO_TIMEFRAME.get(minutes)
            if tf:
                return tf
        except (ValueError, TypeError):
            pass

    try:
        delta = index[1] - index[0]
        minutes = int(delta.total_seconds() // 60)
        tf = _MINUTE_TO_TIMEFRAME.get(minutes)
        if tf:
            return tf
    except (TypeError, AttributeError):
        pass

    return canonicalize_timeframe("1min") or "1min"
