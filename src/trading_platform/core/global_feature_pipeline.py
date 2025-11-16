"""Shared global feature pipeline for unified indicator computation.

This module provides build_global_feature_frame(), the canonical implementation
for computing technical indicators across multiple timeframes. It is used by both
the strategy feature computation and the global feature cache builder to ensure
identical outputs.

The pipeline handles:
- Timeframe validation and canonicalization
- Grouping features by timeframe for efficient resampling
- Higher-timeframe data resampling with correct OHLC aggregation
- Indicator computation via the unified registry
- NaN guard tracking (first valid timestamp per feature)
- Parameter substitution (${param_name} placeholders)
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import pandas as pd
from trading_platform.data.resample import resample_data, timeframe_to_timedelta
from trading_platform.data.session_metadata import ALIGNED_TO_CLOSE_ATTR, SESSION_ATTR
from trading_platform.data.timeframe_aliases import canonicalize_timeframe
from trading_platform.strategy.indicators_registry import INDICATORS


def build_global_feature_frame(
    market_data: pd.DataFrame,
    feature_defs: list[dict[str, Any]],
    *,
    execution_timeframe: str,
    data_handler: Any | None = None,  # DataHandler | None for future use
    warmup_start: pd.Timestamp | None = None,  # Reserved for future use
    resample_strategy: str = "forward_fill",  # Reserved for future use
    strategy_parameters: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a DataFrame of technical indicators from feature definitions.

    This is the canonical implementation used by both compute_features() and
    the global feature cache builder. It ensures identical outputs across all
    contexts, preventing subtle discrepancies.

    Args:
        market_data: OHLCV DataFrame with index as timestamp
        feature_defs: List of feature specification dicts, each containing:
            - name: Column name for the feature
            - type: Indicator type (must exist in INDICATORS registry)
            - params: Parameters dict for the indicator
            - source: Price source (open/high/low/close/hl2/ohlc4)
            - timeframe: Optional timeframe for higher-TF features
            - source_ref: Optional reference to another column
        execution_timeframe: The base timeframe for execution (e.g., "5min")
        data_handler: Reserved for future use
        warmup_start: Reserved for future use
        resample_strategy: Reserved for future use
        strategy_parameters: Parameters for ${param} substitution

    Returns:
        Tuple of:
        - DataFrame with computed feature columns (indexed like market_data)
        - Metadata dict with structure: {"valid_start": {column: timestamp}}

    Raises:
        ValueError: If execution_timeframe is invalid or unsupported
        ValueError: If a feature timeframe cannot be resampled
        KeyError: If an indicator type is not found in the registry

    Example:
        >>> features, meta = build_global_feature_frame(
        ...     df,
        ...     [{"name": "ema_20", "type": "EMA", "params": {"length": 20}}],
        ...     execution_timeframe="5min"
        ... )
        >>> meta["valid_start"]["ema_20"]
        Timestamp('2023-01-01 00:20:00+0000', tz='UTC')
    """
    if strategy_parameters is None:
        strategy_parameters = {}

    # 1. Validate and canonicalize execution_timeframe
    canonical_execution_tf = canonicalize_timeframe(execution_timeframe)
    if (
        not canonical_execution_tf
        or canonical_execution_tf not in _SUPPORTED_TIMEFRAMES
    ):
        raise ValueError(f"Unsupported timeframe: {execution_timeframe}")

    # 2. Initialize output structures
    feature_columns: list[pd.Series] = []
    valid_starts: dict[str, Any] = {}

    # 3. Group feature_defs by timeframe (default to execution_timeframe)
    timeframe_groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for spec in feature_defs:
        tf = spec.get("timeframe")
        if tf:
            canonical_tf = canonicalize_timeframe(tf)
            if not canonical_tf or canonical_tf not in _SUPPORTED_TIMEFRAMES:
                raise ValueError(f"Unsupported timeframe: {tf}")
            if canonical_tf not in timeframe_groups:
                timeframe_groups[canonical_tf] = []
            timeframe_groups[canonical_tf].append(spec)
        else:
            # No timeframe means use execution timeframe
            if canonical_execution_tf not in timeframe_groups:
                timeframe_groups[canonical_execution_tf] = []
            timeframe_groups[canonical_execution_tf].append(spec)

    # 4. Process each timeframe group
    for timeframe, group_specs in timeframe_groups.items():
        # Resample if needed
        if timeframe == canonical_execution_tf:
            df_for_group = market_data
            shift_needed = False
            timeframe_delta = pd.Timedelta(0)
        else:
            # Higher timeframe - must resample
            try:
                session = market_data.attrs.get(SESSION_ATTR)
                df_for_group = resample_data(
                    market_data, rule=timeframe, session=session
                )
            except Exception as e:
                raise ValueError(
                    f"Cannot resample to timeframe '{timeframe}': {e}"
                ) from e

            # Determine if we need to shift the index for alignment
            shift_needed = not df_for_group.index.equals(market_data.index)
            aligned_to_close = df_for_group.attrs.get(ALIGNED_TO_CLOSE_ATTR, False)
            timeframe_delta = (
                timeframe_to_timedelta(timeframe)
                if shift_needed and not aligned_to_close
                else pd.Timedelta(0)
            )

        # 5. Compute each feature in this timeframe group
        for spec in group_specs:
            name = spec.get("name")
            typ = spec.get("type")
            params = spec.get("params", {})
            source_val = spec.get("source", "close")
            source_ref = None

            if not name or not typ:
                continue

            # Handle PriceSource enum if present
            if hasattr(source_val, "value"):
                source = source_val.value
            elif source_val is None:
                source = "close"
            else:
                source = str(source_val)

            # Extract source_ref if present
            _src_ref_val = spec.get("source_ref")
            if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
                ref_val = _src_ref_val.get("ref")
                source_ref = str(ref_val) if ref_val is not None else None

            # Resolve ${param} substitutions
            resolved_params = _resolve_parameters(params, strategy_parameters)

            # Look up indicator from registry
            indicator = INDICATORS.get(typ)
            if not indicator:
                raise KeyError(
                    f"Indicator type '{typ}' not found in registry. "
                    f"Available types: {', '.join(sorted(INDICATORS.keys()))}"
                )

            # Call the implementation
            impl_fn = indicator["implementation"]
            result = impl_fn(df_for_group, resolved_params, source, source_ref)

            # Handle single vs multi-column output
            if isinstance(result, dict):
                # Multi-column (BB, MACD, ADX, etc.)
                for col_suffix, col_data in result.items():
                    if col_suffix == "":
                        column_name = name
                    else:
                        column_name = f"{name}_{col_suffix}"

                    series = _to_series_aligned(
                        col_data, market_data.index, shift_needed, timeframe_delta
                    )
                    feature_columns.append(series.rename(column_name))

                    # Track first valid index
                    first_valid = series.first_valid_index()
                    if first_valid is not None and isinstance(
                        first_valid, pd.Timestamp
                    ):
                        valid_starts[column_name] = first_valid
            else:
                # Single-column (EMA, RSI, ATR, etc.)
                series = _to_series_aligned(
                    result, market_data.index, shift_needed, timeframe_delta
                )
                feature_columns.append(series.rename(name))

                # Track first valid index
                first_valid = series.first_valid_index()
                if first_valid is not None and isinstance(first_valid, pd.Timestamp):
                    valid_starts[name] = first_valid

    # 6. Concatenate all feature columns
    if not feature_columns:
        # No features - return empty frame with correct index
        concatenated = pd.DataFrame(index=market_data.index)
    else:
        concatenated = pd.concat(feature_columns, axis=1)
        # Ensure alignment to market_data index
        concatenated = concatenated.reindex(market_data.index)

    # 7. Return frame and metadata
    return concatenated, {"valid_start": valid_starts}


def _resolve_parameters(
    params: dict[str, Any], strategy_parameters: dict[str, Any]
) -> dict[str, Any]:
    """Resolve ${param_name} placeholders in parameter values."""
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            param_name = value[2:-1]
            if param_name not in strategy_parameters:
                raise ValueError(
                    f"Parameter '{param_name}' not found in strategy parameters."
                )
            resolved[key] = strategy_parameters[param_name]
        else:
            resolved[key] = value
    return resolved


def _to_series_aligned(
    value: Any,
    target_index: pd.Index,
    shift_needed: bool,
    timeframe_delta: pd.Timedelta,
) -> pd.Series:
    """Convert indicator output to Series aligned with target_index.

    Implements the same logic as compute_features for higher-timeframe alignment:
    - If shift_needed, shift index by timeframe_delta then ffill to target
    - Otherwise, reindex directly to target
    """
    if isinstance(value, pd.Series):
        series = value
    elif isinstance(value, pd.DataFrame):
        if value.shape[1] != 1:
            raise ValueError(
                "Indicator returned DataFrame with multiple columns "
                "but should return Series or dict[str, Series]"
            )
        series = value.iloc[:, 0]
    else:
        # Scalar or array-like
        if hasattr(value, "__len__") and len(value) == len(target_index):
            series = pd.Series(value, index=target_index)
        else:
            # Scalar - broadcast
            series = pd.Series([value] * len(target_index), index=target_index)

    # Apply the same alignment logic as compute_features
    if shift_needed:
        # Shift index by delta then forward-fill to target
        series = series.copy()
        series.index = series.index + timeframe_delta
        series = series.reindex(target_index, method="ffill")
    elif not series.index.equals(target_index):
        # No shift needed but indices don't match - just reindex
        series = series.reindex(target_index)

    return series


# Supported timeframes - must match canonicalized pandas-style labels
_SUPPORTED_TIMEFRAMES = {
    "1min",
    "5min",
    "15min",
    "30min",
    "1h",
    "2h",
    "4h",
    "1d",
    "1w",
}


__all__ = ["build_global_feature_frame"]
