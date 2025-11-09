"""
Feature computation module for trading strategies.

This module provides the compute_features() function which uses the unified
indicator registry to calculate technical indicators on OHLCV data.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from trading_platform.data.resample import resample_data, timeframe_to_timedelta

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
    """Resample OHLCV data to a higher timeframe using canonical rules."""
    return resample_data(df, timeframe)


def _to_series(value: Any, index: pd.Index) -> pd.Series:
    """Ensure a value is a Series aligned to the provided index."""
    if isinstance(value, pd.Series):
        return cast(pd.Series, value.reindex(index))
    if isinstance(value, pd.DataFrame):
        if value.shape[1] != 1:
            raise ValueError(
                "Indicator output DataFrame must have exactly one column "
                "when assigning to a single feature."
            )
        return cast(pd.Series, value.iloc[:, 0].reindex(index))
    if hasattr(value, "__len__") and len(value) == len(index):
        return cast(pd.Series, pd.Series(value, index=index))
    repeated = pd.Series([value] * len(index), index=index)
    return cast(pd.Series, repeated)


def _append_columns(
    base: pd.DataFrame,
    columns: dict[str, Any],
    assign_state: dict[str, int],
    added_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Assign columns in-place, consolidating periodically to avoid fragmentation."""
    if not columns:
        return base
    for name, value in columns.items():
        series = _to_series(value, base.index)
        base[name] = series
        if added_columns is not None:
            added_columns.append(name)
    assign_state["pending"] = assign_state.get("pending", 0) + len(columns)
    if assign_state["pending"] >= 32:
        consolidate = getattr(base, "_consolidate_inplace", None)
        if callable(consolidate):
            consolidate()
        assign_state["pending"] = 0
    return base


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
    resampled_assign_states: dict[str, dict[str, int]] = {}

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
    assign_state: dict[str, int] = {"pending": 0}

    for spec in base_specs:
        out, _ = _process_single_feature(
            spec,
            out,
            strategy_parameters,
            assign_state=assign_state,
        )

    # Process higher timeframe features grouped by timeframe
    for timeframe, group_specs in timeframe_groups.items():
        # Resample once per timeframe (cached)
        if timeframe not in resampled_frames:
            resampled_frames[timeframe] = resample_data(df, rule=timeframe)

        df_resampled = resampled_frames[timeframe]
        shift_needed = not df_resampled.index.equals(df.index)
        timeframe_delta = (
            timeframe_to_timedelta(timeframe) if shift_needed else pd.Timedelta(0)
        )

        assign_state_htf = resampled_assign_states.setdefault(timeframe, {"pending": 0})

        # Compute all features for this timeframe on the resampled data
        for spec in group_specs:
            name = str(spec.get("name"))
            typ = str(spec.get("type"))
            params = spec.get("params") or {}
            # Handle PriceSource enum and None properly
            source_val = spec.get("source", "close")
            if hasattr(source_val, "value"):  # PriceSource enum
                source = source_val.value
            elif source_val is None:
                source = "close"
            else:
                source = str(source_val)
            source_ref = None

            # Extract source_ref if present
            _src_ref_val = spec.get("source_ref")
            if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
                ref_val = _src_ref_val.get("ref")
                source_ref = str(ref_val) if ref_val is not None else None

            if not name:
                continue

            temp_spec: dict[str, Any] = {
                "name": name,
                "type": typ,
                "params": params,
                "source": source,
            }
            if source_ref:
                temp_spec["source_ref"] = {"ref": source_ref}

            df_resampled, new_column_names = _process_single_feature(
                temp_spec,
                df_resampled,
                strategy_parameters,
                assign_state=assign_state_htf,
            )
            resampled_frames[timeframe] = df_resampled
            if not new_column_names:
                continue

            htf_values = df_resampled[new_column_names].copy()
            if shift_needed:
                htf_values.index = htf_values.index + timeframe_delta
            htf_values = htf_values.reindex(df.index, method="ffill")

            new_cols: dict[str, pd.Series] = {
                col: htf_values[col] for col in new_column_names
            }
            out = _append_columns(out, new_cols, assign_state)

    # Return with natural NaN values - consuming code handles them
    return out


def _process_single_feature(
    spec: dict,
    data: pd.DataFrame,
    strategy_parameters: dict,
    *,
    assign_state: dict[str, int],
) -> tuple[pd.DataFrame, list[str]]:
    """Process a single feature specification and append new columns.

    Args:
        spec: Feature specification dict
        df: Input OHLCV DataFrame
        out: Output DataFrame to add feature to (modified in place)
        strategy_parameters: Parameters for substitution
    """
    name = str(spec.get("name"))
    typ = str(spec.get("type"))
    params = spec.get("params") or {}
    # Handle PriceSource enum and None properly
    source_val = spec.get("source", "close")
    if hasattr(source_val, "value"):  # PriceSource enum
        source = source_val.value
    elif source_val is None:
        source = "close"
    else:
        source = str(source_val)
    source_ref = None

    # Extract source_ref if present
    _src_ref_val = spec.get("source_ref")
    if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
        ref_val = _src_ref_val.get("ref")
        source_ref = str(ref_val) if ref_val is not None else None

    if not name:
        return data, []

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

        fallback_columns = {name: pd.Series(np.nan, index=data.index)}
        added: list[str] = []
        data = _append_columns(
            data,
            fallback_columns,
            assign_state,
            added_columns=added,
        )
        return data, added

    # Call implementation with standard interface
    impl_fn = indicator["implementation"]
    result = impl_fn(data, resolved_params, source, source_ref)

    # Handle output based on return type
    new_columns: dict[str, pd.Series] = {}
    if isinstance(result, dict):
        # Multi-column output (BB, MACD, ADX, etc.)
        for col_name, col_data in result.items():
            if col_name == "":
                # Empty string means no suffix (e.g., PSAR, STOCH main value)
                new_columns[name] = col_data
            else:
                new_columns[f"{name}_{col_name}"] = col_data
    else:
        # Single-column output (EMA, RSI, ATR, etc.)
        new_columns[name] = result

    added_columns: list[str] = []
    data = _append_columns(
        data,
        new_columns,
        assign_state,
        added_columns=added_columns,
    )
    return data, added_columns
