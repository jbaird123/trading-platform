"""
Feature computation module for trading strategies.

Provides the compute_features() function plus helper wrappers used by legacy code.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.tseries.frequencies import to_offset

from trading_platform.data.bar_windows import compute_bar_close_index
from trading_platform.data.session_metadata import (
    ALIGNED_TO_CLOSE_ATTR,
    SESSION_ATTR,
)
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
    df_aligned = _align_index_to_bar_close(df, execution_timeframe)

    from trading_platform.core.global_feature_pipeline import build_global_feature_frame

    features_df, _ = build_global_feature_frame(
        market_data=df_aligned,
        feature_defs=specs,
        execution_timeframe=execution_timeframe,
        strategy_parameters=strategy_parameters,
    )

    return df_aligned.join(features_df, how="left")


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
            try:
                delta = pd.Timedelta(offset.freqstr)
            except (ValueError, TypeError):
                delta = pd.to_timedelta(freq)
            minutes = int(delta.total_seconds() // 60)
            tf = _MINUTE_TO_TIMEFRAME.get(minutes)
            if tf:
                return tf
        except (ValueError, TypeError):
            pass

    # Fall back to the most common delta between consecutive bars
    if isinstance(index, pd.DatetimeIndex) and len(index) > 1:
        deltas = pd.Series(index[1:] - index[:-1])
        deltas = deltas[deltas > pd.Timedelta(0)]
        if not deltas.empty:
            mode_delta = deltas.value_counts().index[0]
            minutes = int(mode_delta.total_seconds() // 60)
            tf = _MINUTE_TO_TIMEFRAME.get(minutes)
            if tf:
                return tf

    try:
        delta = index[1] - index[0]
        minutes = int(delta.total_seconds() // 60)
        tf = _MINUTE_TO_TIMEFRAME.get(minutes)
        if tf:
            return tf
    except (TypeError, AttributeError):
        pass

    return canonicalize_timeframe("1min") or "1min"


def _align_index_to_bar_close(
    df: pd.DataFrame,
    execution_timeframe: str,
) -> pd.DataFrame:
    """
    Shift the index to bar close timestamps so feature availability matches cache.
    """
    if df.attrs.get(ALIGNED_TO_CLOSE_ATTR):
        return df

    if not isinstance(df.index, pd.DatetimeIndex) or df.empty:
        return df

    session = df.attrs.get(SESSION_ATTR)
    try:
        close_index = compute_bar_close_index(df.index, execution_timeframe, session)
    except Exception:
        return df

    aligned = df.copy()
    aligned.index = close_index
    if session is not None:
        aligned.attrs[SESSION_ATTR] = session
    aligned.attrs[ALIGNED_TO_CLOSE_ATTR] = True
    return aligned
