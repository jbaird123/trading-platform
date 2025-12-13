"""Shared engineered feature groups and helpers for profitability models."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

ENGINEERED_GROUP_PATTERNS: dict[str, list[str]] = {
    "alignment": [
        "trend_alignment",
        "ema_50_slope_pct",
        "ema_50_distance_pct",
        "slope_confluence",
    ],
    "volatility": [
        "atr_percentile",
        "atr_slope_pct",
        "bb_width_percentile",
        "range_atr_ratio",
        "true_range_zscore",
    ],
    "structure": [
        "close_to_hhv",
        "close_to_llv",
        "hhv_20_slope",
        "llv_20_slope",
    ],
    "momentum": [
        "rsi_bias",
        "rsi_slope",
        "roc_",
        "prior_return",
    ],
    "volume": [
        "volume_sma_ratio",
    ],
    "calendar": [
        "calendar",
        "day_of_week",
    ],
}

RISK_FEATURE_COLUMNS = [
    "risk_distance_abs",
    "risk_distance_pct_entry",
    "risk_distance_atr_ratio",
]


def collect_group_patterns(group_names: Iterable[str]) -> list[str]:
    """Expand group names into their substring patterns."""

    patterns: list[str] = []
    for name in group_names:
        patterns.extend(ENGINEERED_GROUP_PATTERNS[name])
    return patterns


def add_normalized_risk_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append normalized risk features derived from stop distance."""

    if "initial_stop_loss_price" not in df.columns or "entry_price" not in df.columns:
        for column in RISK_FEATURE_COLUMNS:
            df[column] = np.nan
        return df

    risk_distance = (df["entry_price"] - df["initial_stop_loss_price"]).abs()
    df["risk_distance_abs"] = risk_distance

    entry_abs = df["entry_price"].abs().replace(0, np.nan)
    df["risk_distance_pct_entry"] = np.divide(risk_distance, entry_abs)

    # Try to find ATR from global features based on execution timeframe
    atr_col = None
    if "execution_timeframe" in df.columns:
        # Map execution_timeframe to global feature timeframe format
        tf_map = {"5min": "5min", "15min": "15min", "1H": "1h", "4H": "4h", "1D": "1d"}
        # Get the first non-null execution_timeframe to determine ATR column
        first_tf = (
            df["execution_timeframe"].dropna().iloc[0]
            if not df["execution_timeframe"].dropna().empty
            else None
        )
        if first_tf and first_tf in tf_map:
            candidate = f"context_at_entry_global_features_{tf_map[first_tf]}_atr_14"
            if candidate in df.columns:
                atr_col = candidate

    if atr_col is not None:
        atr = df[atr_col].replace(0, np.nan)
        df["risk_distance_atr_ratio"] = np.divide(risk_distance, atr)
    else:
        df["risk_distance_atr_ratio"] = np.nan

    return df
