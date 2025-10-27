"""Warmup calculator for indicator initialization.

This module calculates the minimum data required before a backtest start date
to ensure all indicators (strategy and global features) are fully initialized
with no NaN values.

The algorithm is instrument-agnostic and works by counting actual bars in the data,
not calendar time. This handles Forex (weekend gaps), Crypto (24/7), and Stock
(trading hours) markets correctly.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from trading_platform.data.resample import resample_data


def calculate_indicator_bars_needed(indicator_type: str, params: dict[str, Any]) -> int:
    """Calculate how many bars an indicator needs to initialize.

    Args:
        indicator_type: Type of indicator (e.g., "EMA", "ATR", "MACD")
        params: Indicator parameters

    Returns:
        Number of bars needed for the indicator to be fully initialized
    """
    # Most indicators need their length/period parameter
    length = params.get("length", params.get("period", 14))

    # Special cases that need more bars
    if indicator_type.upper() == "ADX":
        # ADX needs length for DI calculation, then length again for ADX smoothing
        return int(length * 2)
    elif indicator_type.upper() == "MACD":
        # MACD needs slow period + signal period
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        return int(slow + signal)
    elif indicator_type.upper() in ["BB", "BBANDS"]:
        # Bollinger Bands need length for SMA calculation
        return int(params.get("length", 20))
    elif indicator_type.upper() == "STOCH":
        # Stochastic needs k period + d period (SMA of k)
        k_period = params.get("k_period", params.get("length", 14))
        d_period = params.get("d_period", params.get("smooth", 3))
        return int(k_period + d_period)

    # Default: use the length parameter
    return int(length)


def calculate_warmup_start_date(
    strategy_features: list[dict[str, Any]],
    global_features: list[dict[str, Any]],
    execution_timeframe: str,
    market_data: pd.DataFrame,
    backtest_start_date: pd.Timestamp | str,
    safety_days: int = 10,
) -> tuple[date, dict[str, Any]]:
    """Calculate the start date for loading data with warmup period.

    Algorithm:
    1. For each indicator (strategy + global), calculate bars needed
    2. Count backwards that many bars in the actual data (resampled if needed)
    3. Find the earliest timestamp across all indicators
    4. Convert to date and subtract safety buffer

    This is instrument-agnostic because it counts actual bars in the data,
    not calendar time. Works for Forex, Crypto, Stocks automatically.

    Args:
        strategy_features: List of strategy feature definitions
        global_features: List of global feature definitions
        execution_timeframe: Execution timeframe (e.g., "1H", "15min")
        market_data: The market data to analyze (must include warmup period)
        backtest_start_date: When the backtest should start
        safety_days: Extra days to add as safety buffer (default 10)

    Returns:
        Tuple of (warmup_start_date, info_dict) where info_dict contains:
            - required_bars: dict mapping feature names to bars needed
            - earliest_feature: name of the feature requiring most warmup
            - earliest_timestamp: the earliest timestamp found
            - safety_buffer_days: the safety buffer applied

    Raises:
        ValueError: If insufficient data available for warmup
    """
    backtest_start = pd.Timestamp(backtest_start_date)

    if backtest_start not in market_data.index:
        # Find nearest bar
        idx = market_data.index.get_indexer([backtest_start], method="ffill")[0]
        if idx == -1:
            raise ValueError(
                f"Backtest start date {backtest_start} is before available data"
            )
        backtest_start = market_data.index[idx]

    start_idx_raw = market_data.index.get_loc(backtest_start)
    # get_loc can return int, slice, or bool array - we need int
    if not isinstance(start_idx_raw, int):
        raise ValueError(
            f"Backtest start {backtest_start} maps to multiple locations in data"
        )
    start_idx: int = start_idx_raw

    # Track all warmup requirements
    warmup_timestamps: dict[str, pd.Timestamp] = {}
    bars_needed: dict[str, int] = {}

    # Process strategy features (on execution timeframe)
    for feature in strategy_features:
        feature_name = feature.get("name", "unknown")
        feature_type = feature.get("type", "")
        feature_params = feature.get("params", {})

        bars = calculate_indicator_bars_needed(feature_type, feature_params)
        bars_needed[f"strategy_{feature_name}"] = bars

        # Count backwards in execution timeframe data
        warmup_idx = start_idx - bars
        if warmup_idx < 0:
            raise ValueError(
                f"Insufficient data for strategy feature '{feature_name}' "
                f"({feature_type}). Need {bars} bars before {backtest_start}, "
                f"but only {start_idx} available."
            )

        warmup_timestamps[f"strategy_{feature_name}"] = pd.Timestamp(
            market_data.index[warmup_idx]
        )

    # Process global features (may be on different timeframes)
    for feature in global_features:
        feature_name = feature.get("name", "unknown")
        feature_type = feature.get("type", "")
        feature_params = feature.get("params", {})
        feature_timeframe = feature.get("timeframe")

        bars = calculate_indicator_bars_needed(feature_type, feature_params)
        bars_needed[f"global_{feature_name}"] = bars

        # If feature timeframe matches execution, use market_data directly
        if not feature_timeframe or feature_timeframe == execution_timeframe:
            warmup_idx = start_idx - bars
            if warmup_idx < 0:
                raise ValueError(
                    f"Insufficient data for global feature '{feature_name}' "
                    f"({feature_type}). Need {bars} bars before "
                    f"{backtest_start}, but only {start_idx} available."
                )
            warmup_timestamps[f"global_{feature_name}"] = pd.Timestamp(
                market_data.index[warmup_idx]
            )
        else:
            # Feature is on a different timeframe - resample and count
            resampled = resample_data(market_data, feature_timeframe)

            # Find backtest start in resampled data
            start_idx_resampled = resampled.index.get_indexer(
                [backtest_start], method="ffill"
            )[0]
            if start_idx_resampled == -1:
                raise ValueError(
                    f"Backtest start {backtest_start} not found in "
                    f"{feature_timeframe} data"
                )

            warmup_idx_resampled = start_idx_resampled - bars
            if warmup_idx_resampled < 0:
                raise ValueError(
                    f"Insufficient data for global feature '{feature_name}' "
                    f"({feature_type} on {feature_timeframe}). Need {bars} "
                    f"bars before {backtest_start}, but only "
                    f"{start_idx_resampled} available."
                )

            warmup_timestamps[f"global_{feature_name}"] = pd.Timestamp(
                resampled.index[warmup_idx_resampled]
            )

    # Find earliest timestamp
    if not warmup_timestamps:
        # No indicators - no warmup needed
        return backtest_start.date(), {
            "required_bars": {},
            "earliest_feature": None,
            "earliest_timestamp": backtest_start,
            "safety_buffer_days": 0,
        }

    earliest_feature = min(warmup_timestamps, key=warmup_timestamps.get)  # type: ignore
    earliest_timestamp = warmup_timestamps[earliest_feature]

    # Convert to date (strip time component)
    earliest_date = earliest_timestamp.date()

    # Apply safety buffer
    warmup_start_date = earliest_date - timedelta(days=safety_days)

    return warmup_start_date, {
        "required_bars": bars_needed,
        "earliest_feature": earliest_feature,
        "earliest_timestamp": earliest_timestamp,
        "safety_buffer_days": safety_days,
    }
