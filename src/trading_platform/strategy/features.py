"""
Feature computation module for trading strategies.

This module provides the compute_features() function which uses the unified
indicator registry to calculate technical indicators on OHLCV data.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from trading_platform.data.resample import resample_data

# ema_slope is now compute_ema_slope, create wrapper
from trading_platform.strategy import indicator_implementations as _impl

# Import helper functions for backwards compatibility with existing tests
# These are exported from indicator_implementations for test usage
from trading_platform.strategy.indicator_implementations import (
    _price_series,
    adx,
    atr,
    ema,
    hhv,
    llv,
    rsi,
)
from trading_platform.strategy.indicators_registry import INDICATORS


def ema_slope(series: pd.Series, length: int, slope_period: int = 1) -> pd.Series:
    """EMA Slope - wrapper for backwards compatibility."""
    # Create a minimal DataFrame for the implementation
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


# Also export the donchian_channels function name
def donchian_channels(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    """Donchian Channels - wrapper for backwards compatibility."""
    from trading_platform.strategy.indicator_implementations import compute_dc

    result = compute_dc(df, {"length": length}, "close", None)
    return result["upper"], result["lower"]


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


def _resolve_parameter(param_value: Any, strategy_parameters: dict) -> Any:
    """Resolves parameter, substituting placeholders like ${param_name}."""
    if not isinstance(param_value, str):
        return param_value
    if param_value.startswith("${") and param_value.endswith("}"):
        param_name = param_value[2:-1]
        if param_name in strategy_parameters:
            return strategy_parameters[param_name]
        else:
            raise ValueError(
                f"Parameter '{param_name}' not found in strategy " f"parameters."
            )
    return param_value


def _resample_to_higher_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe.

    Args:
        df: DataFrame with OHLCV data
        timeframe: Target timeframe (e.g., '1h', '4h', '1D')

    Returns:
        Resampled DataFrame
    """
    # Use pandas resample with OHLC aggregation
    resampled = df.resample(timeframe).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return resampled


def compute_features(
    df: pd.DataFrame, specs: list[dict], strategy_parameters: dict | None = None
) -> pd.DataFrame:
    """Compute features as configured in specs using the unified registry.

    Each spec: {name, type, params, source, source_ref (optional), timeframe (optional)}
    Returns DataFrame with original df plus new feature columns by name.

    Note: Returns NaN values naturally where indicators need warm-up period.
    The backtester will skip bars with NaN in required features.
    The AI pipeline should call .dropna() explicitly if needed.

    Args:
        df: OHLCV DataFrame with columns: open, high, low, close, volume
        specs: List of feature specifications
        strategy_parameters: Optional strategy parameters for ${var} substitution

    Returns:
        DataFrame with computed features added as new columns
    """
    if strategy_parameters is None:
        strategy_parameters = {}

    out = df.copy()

    # Cache for resampled DataFrames - scoped to this single call
    resampled_frames: dict[str, pd.DataFrame] = {}

    # Group specs by timeframe for efficient resampling
    base_specs = []
    timeframe_groups: dict[str, list[dict]] = {}

    for spec in specs or []:
        timeframe = spec.get("timeframe")
        if timeframe:
            if timeframe not in timeframe_groups:
                timeframe_groups[timeframe] = []
            timeframe_groups[timeframe].append(spec)
        else:
            base_specs.append(spec)

    # Process base timeframe features first
    for spec in base_specs:
        _process_single_feature(spec, df, out, strategy_parameters)

    # Process higher timeframe features grouped by timeframe
    for timeframe, group_specs in timeframe_groups.items():
        # Resample once per timeframe (cached)
        if timeframe not in resampled_frames:
            resampled_frames[timeframe] = resample_data(df, rule=timeframe)

        df_resampled = resampled_frames[timeframe]

        # Compute all features for this timeframe on the resampled data
        for spec in group_specs:
            # Build temp spec without timeframe to avoid recursion
            name = str(spec.get("name"))
            typ = str(spec.get("type"))
            params = spec.get("params") or {}
            source = str(spec.get("source", "close"))
            source_ref = None

            # Extract source_ref if present
            _src_ref_val = spec.get("source_ref")
            if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
                ref_val = _src_ref_val.get("ref")
                source_ref = str(ref_val) if ref_val is not None else None

            if not name:
                continue

            temp_spec = {
                "name": name,
                "type": typ,
                "params": params,
                "source": source,
            }
            if source_ref:
                temp_spec["source_ref"] = {"ref": source_ref}

            # Compute feature on resampled data
            df_htf = compute_features(df_resampled, [temp_spec], strategy_parameters)

            # Handle multi-output indicators (e.g., ADX returns name_ADX,
            # name_DI+, name_DI-). Find columns that start with feature name.
            htf_cols = [
                col
                for col in df_htf.columns
                if col == name or col.startswith(f"{name}_")
            ]

            if not htf_cols:
                # Fallback: try the exact name (shouldn't happen but be safe)
                htf_cols = [name]

            # Reindex and forward-fill all columns for this feature
            for col in htf_cols:
                if col in df_htf.columns:
                    htf_series = df_htf[col].reindex(df.index, method="ffill")
                    out[col] = htf_series

    # Return with natural NaN values - consuming code handles them
    return out


def _process_single_feature(
    spec: dict,
    df: pd.DataFrame,
    out: pd.DataFrame,
    strategy_parameters: dict,
) -> None:
    """Process a single feature specification and add to output DataFrame.

    Args:
        spec: Feature specification dict
        df: Input OHLCV DataFrame
        out: Output DataFrame to add feature to (modified in place)
        strategy_parameters: Parameters for substitution
    """
    name = str(spec.get("name"))
    typ = str(spec.get("type"))
    params = spec.get("params") or {}
    source = str(spec.get("source", "close"))
    source_ref = None

    # Extract source_ref if present
    _src_ref_val = spec.get("source_ref")
    if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
        ref_val = _src_ref_val.get("ref")
        source_ref = str(ref_val) if ref_val is not None else None

    if not name:
        return

    # Resolve parameter substitutions (${param_name})
    resolved_params = {
        k: _resolve_parameter(v, strategy_parameters) for k, v in params.items()
    }

    # Get indicator from registry
    indicator = INDICATORS.get(typ)
    if not indicator:
        # For backwards compatibility, unknown indicators return NaN
        # instead of raising an error
        import numpy as np

        out[name] = np.nan
        return

    # Call implementation with standard interface
    impl_fn = indicator["implementation"]
    result = impl_fn(df, resolved_params, source, source_ref)

    # Handle output based on return type
    if isinstance(result, dict):
        # Multi-column output (BB, MACD, ADX, etc.)
        for col_name, col_data in result.items():
            if col_name == "":
                # Empty string means no suffix (e.g., PSAR, STOCH main value)
                out[name] = col_data
            else:
                out[f"{name}_{col_name}"] = col_data
    else:
        # Single-column output (EMA, RSI, ATR, etc.)
        out[name] = result
