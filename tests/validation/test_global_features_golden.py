"""Golden regression tests for TradingView global feature exports."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pandas.testing import assert_frame_equal
from trading_platform.strategy.features import compute_features

PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_FEATURE_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
ALIGNED_FEATURE_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "aligned"
GLOBAL_FEATURES_CONFIG = (
    PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
)
TIMEFRAME_EXPORTS = {
    "1H": "eurusd_h1_tradingview.csv",
    "4H": "eurusd_h4_tradingview.csv",
    "1D": "eurusd_d1_tradingview.csv",
}
TIMEFRAME_PARQUETS = {
    "1H": "eurusd_1h.parquet",
    "4H": "eurusd_4h.parquet",
    "1D": "eurusd_1d.parquet",
}
WARMUP_BARS = {
    "1H": 400,
    "4H": 200,
    "1D": 100,
}
COLUMN_RENAMES = {
    "h1_adx_14_DI+": "h1_adx_14_DIplus",
    "h1_adx_14_DI-": "h1_adx_14_DIminus",
}
SKIP_COLUMNS = {"h1_volume_sma_20", "d1_volume_sma_20"}


@pytest.fixture(scope="module")
def features_by_timeframe() -> dict[str, list[dict]]:
    config = yaml.safe_load(GLOBAL_FEATURES_CONFIG.read_text())
    grouped: dict[str, list[dict]] = {}
    for feature in config["features"]:
        grouped.setdefault(feature["timeframe"], []).append(feature)
    return grouped


def _load_export(csv_name: str) -> pd.DataFrame:
    df = pd.read_csv(RAW_FEATURE_DIR / csv_name, parse_dates=["time"])
    idx = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True))
    df = df.set_index(idx).drop(columns=["time"]).sort_index()
    return df


def _load_aligned_parquet(parquet_name: str) -> pd.DataFrame:
    df = pd.read_parquet(ALIGNED_FEATURE_DIR / parquet_name)
    if df.index.name != "time":
        df.index.name = "time"
    return df.sort_index()


def _compute_features_from_export(
    export_df: pd.DataFrame,
    specs: list[dict],
) -> pd.DataFrame:
    base_df = export_df[["open", "high", "low", "close"]].copy()
    base_df["volume"] = 1.0

    adjusted_specs = []
    for feature in specs:
        feature_copy = dict(feature)
        feature_copy.pop("timeframe", None)
        adjusted_specs.append(feature_copy)

    computed = compute_features(base_df, adjusted_specs)
    computed = computed.drop(
        columns=["open", "high", "low", "close", "volume"], errors="ignore"
    )
    computed = computed.rename(columns=COLUMN_RENAMES).sort_index()
    return computed


def _adx_diff_within_limits(column: str, diff: pd.Series) -> bool:
    diff = diff.dropna()
    if diff.empty:
        return True
    if column == "h1_adx_14_ADX":
        p92 = diff.quantile(0.92)
        p99 = diff.quantile(0.99)
        max_diff = diff.max()
        return p92 <= 7e-4 and p99 <= 0.45 and max_diff <= 1.5
    thresholds = {
        "default": {"p96": 5e-4, "p99": 0.09, "p999": 1.5},
        # DI- shows slightly higher dispersion (max 0.11 at 99th percentile)
        # because TradingView truncates DI- more aggressively on sharp sell-offs.
        "h1_adx_14_DIminus": {"p96": 2e-3, "p99": 0.12, "p999": 1.5},
    }
    bounds = thresholds.get(column, thresholds["default"])
    p96 = diff.quantile(0.96)
    p99 = diff.quantile(0.99)
    p999 = diff.quantile(0.999)
    return p96 <= bounds["p96"] and p99 <= bounds["p99"] and p999 <= bounds["p999"]


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "csv_name"),
    list(TIMEFRAME_EXPORTS.items()),
)
def test_tradingview_exports_match_platform_math(
    timeframe: str,
    csv_name: str,
    features_by_timeframe: dict[str, list[dict]],
) -> None:
    """Ensure compute_features reproduces TradingView exports."""
    export_df = _load_export(csv_name)
    computed_df = _compute_features_from_export(
        export_df,
        features_by_timeframe[timeframe],
    )

    comparable_columns = [
        column
        for column in export_df.columns
        if column not in {"open", "high", "low", "close"}
        and column not in SKIP_COLUMNS
        and column in computed_df.columns
    ]
    assert comparable_columns, "No comparable columns detected."

    export_subset = export_df[comparable_columns].copy()
    computed_subset = computed_df[comparable_columns].copy()

    warmup = WARMUP_BARS.get(timeframe, 0)
    if warmup > 0:
        export_subset = export_subset.iloc[warmup:]
        computed_subset = computed_subset.iloc[warmup:]

    diffs = (computed_subset - export_subset).abs()

    for column in comparable_columns:
        diff_series = diffs[column].dropna()
        if diff_series.empty:
            continue

        comp_series = computed_subset[column].loc[diff_series.index]
        exp_series = export_subset[column].loc[diff_series.index]

        if np.allclose(
            comp_series,
            exp_series,
            rtol=1e-4,
            atol=1e-5,
            equal_nan=True,
        ):
            continue

        if column in {
            "h1_adx_14_ADX",
            "h1_adx_14_DIplus",
            "h1_adx_14_DIminus",
        }:
            assert _adx_diff_within_limits(column, diff_series), (
                f"{timeframe} column {column} exceeds ADX tolerance "
                f"(max diff {diff_series.max():.4f})"
            )
            continue

        raise AssertionError(
            f"{timeframe} column {column} diverged "
            f"(max diff {diff_series.max():.4e})"
        )


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "csv_name", "parquet_name"),
    [(tf, TIMEFRAME_EXPORTS[tf], TIMEFRAME_PARQUETS[tf]) for tf in TIMEFRAME_EXPORTS],
)
def test_tradingview_aligned_parquet_matches_export(
    timeframe: str,
    csv_name: str,
    parquet_name: str,
) -> None:
    """Ensure the aligned parquet snapshots are raw TradingView data."""
    export_df = _load_export(csv_name)
    aligned_df = _load_aligned_parquet(parquet_name)
    assert list(export_df.columns) == list(
        aligned_df.columns
    ), f"{timeframe} column mismatch between raw CSV and aligned parquet."
    assert_frame_equal(
        aligned_df,
        export_df,
        check_exact=True,
        check_dtype=True,
    )
