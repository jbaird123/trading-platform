"""Golden regression tests for TradingView global feature exports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml
from pandas.testing import assert_frame_equal
from trading_platform.data.resample import resample_data
from trading_platform.strategy.features import compute_features

PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_FEATURE_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
GLOBAL_FEATURES_CONFIG = (
    PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
)
BASE_OHLC_SOURCE = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "ohlcv"
    / "tradingview"
    / "full"
    / "eurusd"
    / "eurusd_1min.csv"
)

TIMEFRAME_FILES = {
    "1H": "eurusd_h1_tradingview.csv",
    "4H": "eurusd_h4_tradingview.csv",
    "1D": "eurusd_d1_tradingview.csv",
}

COLUMN_RENAMES = {
    "h1_adx_14_DI+": "h1_adx_14_DIplus",
    "h1_adx_14_DI-": "h1_adx_14_DIminus",
}


def _load_1min_ohlcv() -> pd.DataFrame:
    df = pd.read_csv(BASE_OHLC_SOURCE, parse_dates=["timestamp"])
    idx = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True))
    df = df[["open", "high", "low", "close", "volume"]]
    df.index = idx
    return df.sort_index()


@pytest.fixture(scope="module")
def one_minute_ohlcv() -> pd.DataFrame:
    return _load_1min_ohlcv()


@pytest.fixture(scope="module")
def features_by_timeframe() -> dict[str, list[dict]]:
    config = yaml.safe_load(GLOBAL_FEATURES_CONFIG.read_text())
    grouped: dict[str, list[dict]] = {}
    for feature in config["features"]:
        grouped.setdefault(feature["timeframe"], []).append(feature)
    return grouped


def _load_tradingview_features(csv_name: str) -> pd.DataFrame:
    path = RAW_FEATURE_DIR / csv_name
    df = pd.read_csv(path, parse_dates=["time"])
    idx = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True))
    df = df.set_index(idx).drop(columns=["time"]).sort_index()
    return df


def _compute_platform_features(
    base_df: pd.DataFrame,
    timeframe: str,
    feature_specs: list[dict],
) -> pd.DataFrame:
    resampled = resample_data(base_df, timeframe)
    computed = compute_features(resampled, feature_specs)
    computed = computed.drop(
        columns=["open", "high", "low", "close", "volume"], errors="ignore"
    )
    computed = computed.rename(columns=COLUMN_RENAMES).sort_index()
    return computed


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "csv_name"),
    list(TIMEFRAME_FILES.items()),
)
def test_tradingview_raw_features_match_platform(
    timeframe: str,
    csv_name: str,
    features_by_timeframe: dict[str, list[dict]],
) -> None:
    """Ensure our compute_features output matches TradingView exports."""
    raw_df = _load_tradingview_features(csv_name)

    base_df = raw_df[["open", "high, "low", "close"]].copy()

    expected_columns = [
        column
        for column in raw_df.columns
        if column not in {"open", "high", "low", "close"}
    ]

    common_index = raw_df.index.intersection(platform_df.index)
    assert len(common_index) > 0, "No overlapping timestamps to compare."

    raw_subset = raw_df.loc[common_index, expected_columns]
    platform_subset = platform_df.loc[common_index, expected_columns]

    assert_frame_equal(
        platform_subset,
        raw_subset,
        check_exact=False,
        rtol=1e-9,
        atol=1e-9,
        check_dtype=False,
    )


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "csv_name", "parquet_name"),
    [(tf, files[0], files[1]) for tf, files in TIMEFRAME_FILES.items()],
)
def test_aligned_parquet_matches_raw_export(
    timeframe: str,
    csv_name: str,
    parquet_name: str,
) -> None:
    """Verify persisted aligned caches mirror the raw TradingView exports."""
    raw_df = _load_tradingview_features(csv_name)
    feature_only = raw_df.drop(
        columns=["open", "high", "low", "close"], errors="ignore"
    )

    parquet_path = ALIGNED_FEATURE_DIR / parquet_name
    aligned_df = pd.read_parquet(parquet_path)

    assert_frame_equal(
        aligned_df,
        feature_only,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
        check_dtype=False,
    )
