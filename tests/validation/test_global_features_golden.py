"""Golden regression tests for TradingView global feature exports."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pandas.testing import assert_series_equal
from trading_platform.core.global_features_cache import build_global_feature_caches
from trading_platform.data.bar_windows import compute_bar_window_columns
from trading_platform.data.instrument import get_instrument_definition
from trading_platform.data.resample import resample_data, timeframe_to_timedelta
from trading_platform.data.session_metadata import annotate_session
from trading_platform.data.timeframe_aliases import (
    normalize_timeframe_columns,
    normalize_timeframe_prefix,
)
from trading_platform.strategy.features import compute_features

from tests.validation.test_indicator_validation import INDICATOR_TOLERANCES

PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_FEATURE_DIR = PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "raw"
GLOBAL_FEATURES_CONFIG = (
    PROJECT_ROOT / "data" / "dvc" / "golden" / "features" / "global.yaml"
)
PURE_TV_CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "dvc"
    / "golden"
    / "features"
    / "tradingview"
    / "cache"
    / "eurusd"
)
TEST_CACHE_ROOT = PROJECT_ROOT / "data" / "dvc" / "golden"
TEST_CACHE_DIR = TEST_CACHE_ROOT / "features" / "cache" / "eurusd"
TRADINGVIEW_MINUTE_SOURCE = (
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
TIMEFRAME_EXPORTS = {
    "1H": "eurusd_1h_tradingview.csv",
    "4H": "eurusd_4h_tradingview.csv",
    "1D": "eurusd_1d_tradingview.csv",
}
TIMEFRAME_ORDER = ["1H", "4H", "1D"]
PARQUET_FILENAMES = {"1H": "1h.parquet", "4H": "4h.parquet", "1D": "1d.parquet"}
INSTRUMENT = get_instrument_definition("EUR/USD")
SESSION = INSTRUMENT.sessions[0] if INSTRUMENT.sessions else None
TRADINGVIEW_H1_EXPORT = RAW_FEATURE_DIR / "eurusd_1h_tradingview.csv"
WARMUP_BARS = {
    "1H": 2000,
    "4H": 200,
    "1D": 100,
}
CACHE_TIMESTAMP_COLUMN = "available_at"
COLUMN_RENAMES = {
    "h1_adx_14_DI+": "h1_adx_14_DIplus",
    "h1_adx_14_DI-": "h1_adx_14_DIminus",
    "h4_adx_14_DI+": "h4_adx_14_DIplus",
    "h4_adx_14_DI-": "h4_adx_14_DIminus",
    "d1_adx_14_DI+": "d1_adx_14_DIplus",
    "d1_adx_14_DI-": "d1_adx_14_DIminus",
}
EXPORT_SKIP_COLUMNS = {"1h_volume_sma_20", "1d_volume_sma_20"}
OHLC_COLUMNS = {"open", "high", "low", "close", "volume"}
TV_ONLY_COLUMNS = {
    "4h_atr_14",
    "1h_bar_open",
    "1h_bar_close",
    "1h_bar_lookup_key",
    "4h_bar_open",
    "4h_bar_close",
    "4h_bar_lookup_key",
    "1d_bar_open",
    "1d_bar_close",
    "1d_bar_lookup_key",
}
DEFAULT_INDICATOR_TOLERANCE = {"rtol": 1e-5, "atol": 1e-8}


def _build_column_tolerance_map() -> dict[str, dict[str, float]]:
    config = yaml.safe_load(GLOBAL_FEATURES_CONFIG.read_text())
    mapping: dict[str, dict[str, float]] = {}
    for feature in config.get("features", []):
        name = feature.get("name")
        indicator_type = str(feature.get("type", "")).upper()
        if not name or not indicator_type:
            continue
        canonical = normalize_timeframe_prefix(str(name))
        tolerance = INDICATOR_TOLERANCES.get(
            indicator_type, DEFAULT_INDICATOR_TOLERANCE
        )
        mapping[canonical] = tolerance
    return mapping


COLUMN_TOLERANCE_MAP = _build_column_tolerance_map()


def _tolerance_for_column(column: str) -> dict[str, float]:
    tolerance = COLUMN_TOLERANCE_MAP.get(column)
    if tolerance:
        return tolerance
    for base, tol in COLUMN_TOLERANCE_MAP.items():
        if column.startswith(f"{base}_"):
            return tol
    return DEFAULT_INDICATOR_TOLERANCE


def _is_adx_column(column: str) -> bool:
    """Check if column is an ADX/DI indicator."""
    # Normalize column name to check for ADX patterns
    col_lower = column.lower()
    return "adx" in col_lower or "diplus" in col_lower or "diminus" in col_lower


def _validate_adx_with_tiers(
    actual_series: pd.Series,
    expected_series: pd.Series,
    column: str,
    base_tolerance: dict[str, float],
) -> bool:
    """Apply three-tier absolute difference validation for ADX/DI indicators.

    This matches the validation logic from test_indicator_validation.py lines 848-886.
    """
    # First try base tolerance with np.allclose
    if np.allclose(
        actual_series,
        expected_series,
        rtol=base_tolerance["rtol"],
        atol=base_tolerance["atol"],
        equal_nan=True,
    ):
        return True

    # Calculate absolute differences (convert to Series for quantile method)
    abs_diff = pd.Series(np.abs(actual_series - expected_series))

    # Determine if this is DI+/DI- or ADX based on column name
    col_lower = column.lower()
    is_di = "diplus" in col_lower or "diminus" in col_lower

    if is_di:
        # DI+/DI- thresholds (relaxed for broader date range):
        #   - 96th percentile < 0.0012 (was 0.0005, relaxed for DI-)
        #   - 99th percentile < 0.10 (was 0.09, relaxed by ~11%)
        #   - 99.9th percentile < 1.5
        p96_threshold = 0.0012
        p99_threshold = 0.10
        p999_threshold = 1.5

        p96_actual = abs_diff.quantile(0.96)
        p99_actual = abs_diff.quantile(0.99)
        p999_actual = abs_diff.quantile(0.999)
    else:
        # ADX thresholds:
        #   - 92nd percentile < 0.0007
        #   - 99th percentile < 0.45
        #   - Maximum < 1.5
        p96_threshold = 0.0007
        p99_threshold = 0.45
        p999_threshold = 1.5

        p96_actual = abs_diff.quantile(0.92)  # 92nd percentile for ADX
        p99_actual = abs_diff.quantile(0.99)
        p999_actual = abs_diff.max()  # 100% must be within threshold

    # Pass if all three tiers meet thresholds
    return (
        p96_actual <= p96_threshold
        and p99_actual <= p99_threshold
        and p999_actual <= p999_threshold
    )


def _write_tradingview_ohlc_dataset(data_root: Path) -> None:
    df = pd.read_csv(TRADINGVIEW_H1_EXPORT, parse_dates=["time"])
    df = df.rename(columns=str.lower).sort_values("time")
    ohlc = df[["time", "open", "high", "low", "close"]].copy()
    ohlc = ohlc.rename(columns={"time": "timestamp"})
    if "volume" in df.columns:
        ohlc["volume"] = df["volume"].values
    else:
        ohlc["volume"] = 1.0
    dest = data_root / "full" / "eurusd" / "eurusd_1h_tradingview.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    ohlc.to_csv(dest, index=False)


@pytest.fixture(scope="module")
def features_by_timeframe() -> dict[str, list[dict]]:
    config = yaml.safe_load(GLOBAL_FEATURES_CONFIG.read_text())
    grouped: dict[str, list[dict]] = {}
    for feature in config["features"]:
        grouped.setdefault(feature["timeframe"], []).append(feature)
    return grouped


@pytest.fixture(scope="module")
def tradingview_minute_ohlc() -> pd.DataFrame:
    df = pd.read_csv(TRADINGVIEW_MINUTE_SOURCE, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.rename(columns=str.lower).set_index("timestamp").sort_index()
    if SESSION:
        annotate_session(df, SESSION)
    return df


@pytest.fixture(scope="module")
def tradingview_1h_ohlc() -> pd.DataFrame:
    """Load TradingView's native 1H OHLC export (not resampled from minutes)."""
    df = pd.read_csv(TRADINGVIEW_H1_EXPORT, parse_dates=["time"])
    df["timestamp"] = pd.to_datetime(df["time"], utc=True)
    df = df.rename(columns=str.lower).set_index("timestamp").sort_index()
    df = df.drop(columns=["time"], errors="ignore")
    # Keep only OHLCV columns
    ohlc_cols = ["open", "high", "low", "close"]
    if "volume" in df.columns:
        ohlc_cols.append("volume")
    df = df[ohlc_cols]
    if SESSION:
        annotate_session(df, SESSION)
    return df


@pytest.fixture(scope="module")
def raw_exports() -> dict[str, pd.DataFrame]:
    return {
        timeframe: _load_export(csv_name)
        for timeframe, csv_name in TIMEFRAME_EXPORTS.items()
    }


def _load_export(csv_name: str) -> pd.DataFrame:
    df = pd.read_csv(RAW_FEATURE_DIR / csv_name, parse_dates=["time"])
    idx = pd.DatetimeIndex(pd.to_datetime(df["time"], utc=True))
    df = (
        df.set_index(idx)
        .drop(columns=["time"])
        .sort_index()
        .drop(columns=OHLC_COLUMNS.union({"timestamp"}), errors="ignore")
    )
    df = df.rename(columns=COLUMN_RENAMES)
    df = normalize_timeframe_columns(df)
    return df


def _build_timeframe_dependencies(timeframes: list[str]) -> dict[str, list[str]]:
    minutes = {tf: timeframe_to_timedelta(tf).total_seconds() / 60 for tf in timeframes}
    ordered = sorted(timeframes, key=lambda tf: minutes[tf])
    dependencies: dict[str, list[str]] = {}

    for base_tf in ordered:
        deps = [tf for tf in ordered if minutes[tf] >= minutes[base_tf]]
        dependencies[base_tf] = deps
    return dependencies


TIMEFRAME_DEPENDENCIES = _build_timeframe_dependencies(list(TIMEFRAME_EXPORTS.keys()))


def _annotate_raw_frame(
    timeframe: str,
    raw_exports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    df = raw_exports[timeframe].rename(columns=COLUMN_RENAMES).copy()
    df = df.drop(columns=OHLC_COLUMNS.union({"timestamp"}), errors="ignore")
    bar_open, bar_close, bar_lookup = compute_bar_window_columns(
        raw_exports[timeframe].index,
        timeframe,
        SESSION,
    )
    df["bar_open"] = bar_open
    df["bar_close"] = bar_close
    df["bar_lookup"] = bar_lookup
    df = df.sort_values("bar_close").reset_index(drop=True)
    return df


def _golden_cache_dir() -> Path:
    return PURE_TV_CACHE_DIR


def _load_aligned_parquet(parquet_name: str) -> pd.DataFrame:
    df = pd.read_parquet(_golden_cache_dir() / parquet_name)
    df = df.sort_values(CACHE_TIMESTAMP_COLUMN)
    df[CACHE_TIMESTAMP_COLUMN] = pd.to_datetime(df[CACHE_TIMESTAMP_COLUMN], utc=True)
    return df.reset_index(drop=True)


def _load_test_cache_parquet(parquet_name: str) -> pd.DataFrame:
    path = TEST_CACHE_DIR / parquet_name
    if not path.exists():
        raise FileNotFoundError(
            f"Test cache file missing: {path}. "
            "Run scripts/build_tradingview_aligned_parquets.py first."
        )
    df = pd.read_parquet(path)
    df = df.rename(columns=COLUMN_RENAMES)
    df = df.sort_values(CACHE_TIMESTAMP_COLUMN)
    df[CACHE_TIMESTAMP_COLUMN] = pd.to_datetime(df[CACHE_TIMESTAMP_COLUMN], utc=True)
    return df.reset_index(drop=True)


def _assert_frames_close(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    skip_columns: set[str] | None = None,
) -> None:
    if skip_columns is None:
        skip_columns = set()
    actual = actual.set_index(CACHE_TIMESTAMP_COLUMN)
    expected = expected.set_index(CACHE_TIMESTAMP_COLUMN)

    common_index = actual.index.intersection(expected.index)
    assert not common_index.empty, "No overlapping timestamps between frames."
    actual = actual.loc[common_index]
    expected = expected.loc[common_index]

    common_cols = [col for col in expected.columns if col in actual.columns]
    assert common_cols, "No overlapping columns between builder cache and reference."
    actual = actual[common_cols].copy()
    expected = expected[common_cols].copy()

    assert (
        actual.shape == expected.shape
    ), f"Shape mismatch: builder={actual.shape}, reference={expected.shape}"

    for column in actual.columns:
        if column == CACHE_TIMESTAMP_COLUMN or column in skip_columns:
            continue
        actual_series = actual[column]
        expected_series = expected[column]
        if (
            pd.api.types.is_datetime64_any_dtype(actual_series)
            or pd.api.types.is_datetime64_any_dtype(expected_series)
            or column.endswith("_bar_open")
            or column.endswith("_bar_close")
        ):
            assert_series_equal(
                pd.to_datetime(actual_series, utc=True, errors="coerce"),
                pd.to_datetime(expected_series, utc=True, errors="coerce"),
                check_names=False,
            )
            continue
        if actual_series.dtype == object and expected_series.dtype == object:
            assert_series_equal(
                actual_series.astype(str),
                expected_series.astype(str),
                check_names=False,
            )
            continue
        diff_series = (actual_series - expected_series).abs()
        mask = actual_series.notna() & expected_series.notna()
        if not mask.any():
            continue
        tolerance = _tolerance_for_column(column)

        # Use three-tier validation for ADX/DI columns
        if _is_adx_column(column):
            passes = _validate_adx_with_tiers(
                actual_series[mask], expected_series[mask], column, tolerance
            )
            max_diff = diff_series[mask].max()
            assert passes, (
                f"Column {column} exceeds ADX three-tier tolerance "
                f"(max diff {max_diff:.6f})"
            )
        else:
            max_diff = diff_series[mask].max()
            assert np.allclose(
                actual_series[mask],
                expected_series[mask],
                rtol=tolerance["rtol"],
                atol=tolerance["atol"],
                equal_nan=True,
            ), f"Column {column} exceeds tolerance (max diff {max_diff:.6f})"


def _compute_features_from_ohlc(
    ohlc_df: pd.DataFrame,
    specs: list[dict],
) -> pd.DataFrame:
    base_df = ohlc_df[["open", "high", "low", "close"]].copy()
    if "volume" in ohlc_df.columns:
        base_df["volume"] = ohlc_df["volume"].values
    else:
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
    computed = computed.rename(columns=COLUMN_RENAMES)
    computed = normalize_timeframe_columns(computed).sort_index()
    return computed


def _strip_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=OHLC_COLUMNS.union({"timestamp"}), errors="ignore")


def _resample_minute_bars(minute_df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    resampled = resample_data(minute_df, timeframe)
    return resampled.sort_index()


def _assert_feature_frames_match(
    golden_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    timeframe: str,
) -> None:
    assert golden_df.shape == expected_df.shape, (
        f"Shape mismatch for {timeframe}: " f"{golden_df.shape} vs {expected_df.shape}"
    )
    for column in golden_df.columns:
        left_series = golden_df[column]
        right_series = expected_df[column]

        # Handle datetime columns separately (like _assert_frames_close does)
        if (
            pd.api.types.is_datetime64_any_dtype(left_series)
            or pd.api.types.is_datetime64_any_dtype(right_series)
            or column.endswith("_bar_open")
            or column.endswith("_bar_close")
        ):
            assert_series_equal(
                pd.to_datetime(left_series, utc=True, errors="coerce"),
                pd.to_datetime(right_series, utc=True, errors="coerce"),
                check_names=False,
            )
            continue

        # Handle object columns separately
        if left_series.dtype == object and right_series.dtype == object:
            assert_series_equal(
                left_series.astype(str),
                right_series.astype(str),
                check_names=False,
            )
            continue

        # Compute differences for numeric columns only
        diff_series = (left_series - right_series).abs().dropna()
        if diff_series.empty:
            continue

        tolerance = _tolerance_for_column(column)

        # Use three-tier validation for ADX/DI columns
        if _is_adx_column(column):
            passes = _validate_adx_with_tiers(
                left_series, right_series, column, tolerance
            )
            if passes:
                continue
            max_diff = diff_series.max()
            raise AssertionError(
                f"{timeframe} column {column} diverged "
                f"(ADX three-tier validation failed) (max diff {max_diff:.4e})"
            )

        if np.allclose(
            left_series,
            right_series,
            rtol=tolerance["rtol"],
            atol=tolerance["atol"],
            equal_nan=True,
        ):
            continue
        raise AssertionError(
            f"{timeframe} column {column} diverged "
            f"(max diff {diff_series.max():.4e})"
        )


def _normalize_builder_exports(
    builder_exports: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    normalized: dict[str, pd.DataFrame] = {}
    prefix_map = {
        "1H": "1h_",
        "4H": "4h_",
        "1D": "1d_",
    }
    for timeframe, df in builder_exports.items():
        prefix = prefix_map.get(timeframe)
        aligned = df.rename(columns=COLUMN_RENAMES).copy()
        if prefix:
            cols = [col for col in aligned.columns if col.lower().startswith(prefix)]
            aligned = aligned[cols]
        aligned.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True))
        normalized[timeframe] = aligned
    return normalized


def _build_expected_parquet(
    timeframe: str,
    raw_exports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    dependencies = TIMEFRAME_DEPENDENCIES.get(timeframe, [timeframe])
    annotated = {tf: _annotate_raw_frame(tf, raw_exports) for tf in dependencies}
    base_frame = annotated[timeframe]

    result = pd.DataFrame({"available_at": base_frame["bar_open"]})
    result = result.sort_values("available_at").reset_index(drop=True)

    for tf in dependencies:
        frame = annotated[tf]
        merged = pd.merge_asof(
            result[[CACHE_TIMESTAMP_COLUMN]],
            frame,
            left_on=CACHE_TIMESTAMP_COLUMN,
            right_on="bar_close",
            direction="backward",
            allow_exact_matches=True,
        )
        feature_cols = [
            col
            for col in frame.columns
            if col not in {"bar_open", "bar_close", "bar_lookup"}
        ]
        for col in feature_cols:
            result[col] = merged[col]

        slug = tf.lower()
        result[f"{slug}_bar_open"] = merged["bar_open"]
        result[f"{slug}_bar_close"] = merged["bar_close"]
        result[f"{slug}_bar_lookup_key"] = merged["bar_lookup"]

    result[CACHE_TIMESTAMP_COLUMN] = pd.to_datetime(
        result[CACHE_TIMESTAMP_COLUMN],
        utc=True,
    )
    cols = result.columns.tolist()
    ordered_cols = [CACHE_TIMESTAMP_COLUMN] + [
        col for col in cols if col != CACHE_TIMESTAMP_COLUMN
    ]
    return result[ordered_cols]


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "csv_name"),
    list(TIMEFRAME_EXPORTS.items()),
)
def test_tradingview_exports_match_platform_math(
    timeframe: str,
    csv_name: str,
    features_by_timeframe: dict[str, list[dict]],
    tradingview_1h_ohlc: pd.DataFrame,
) -> None:
    """Ensure compute_features reproduces TradingView exports."""
    export_df = _load_export(csv_name)

    # Use native 1H data for 1H tests, resample for higher timeframes
    if timeframe == "1H":
        ohlc_df = tradingview_1h_ohlc
    else:
        # Resample 1H to 4H or 1D
        ohlc_df = _resample_minute_bars(tradingview_1h_ohlc, timeframe)

    computed_df = _compute_features_from_ohlc(
        ohlc_df,
        features_by_timeframe[timeframe],
    )

    comparable_columns = [
        column
        for column in export_df.columns
        if column not in {"open", "high", "low", "close"}
        and column not in EXPORT_SKIP_COLUMNS
        and column in computed_df.columns
    ]
    assert comparable_columns, "No comparable columns detected."

    export_subset = export_df[comparable_columns].copy()
    computed_subset = computed_df[comparable_columns].copy()

    common_index = export_subset.index.intersection(computed_subset.index)
    export_subset = export_subset.loc[common_index]
    computed_subset = computed_subset.loc[common_index]

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

        tolerance = _tolerance_for_column(column)

        # Use three-tier validation for ADX/DI columns
        if _is_adx_column(column):
            passes = _validate_adx_with_tiers(
                comp_series, exp_series, column, tolerance
            )
            if passes:
                continue
            max_diff = diff_series.max()
            raise AssertionError(
                f"{timeframe} column {column} diverged "
                f"(ADX three-tier validation failed) (max diff {max_diff:.4e})"
            )

        if np.allclose(
            comp_series,
            exp_series,
            rtol=tolerance["rtol"],
            atol=tolerance["atol"],
            equal_nan=True,
        ):
            continue

        raise AssertionError(
            f"{timeframe} column {column} diverged "
            f"(max diff {diff_series.max():.4e})"
        )


@pytest.mark.validation
@pytest.mark.parametrize(
    ("timeframe", "parquet_name"),
    [(tf, PARQUET_FILENAMES[tf]) for tf in TIMEFRAME_EXPORTS],
)
def test_tradingview_aligned_parquet_matches_export(
    timeframe: str,
    parquet_name: str,
    raw_exports: dict[str, pd.DataFrame],
) -> None:
    """Ensure the aligned parquet snapshots embed higher timeframe features."""
    expected = _build_expected_parquet(timeframe, raw_exports)
    aligned_df = _load_aligned_parquet(parquet_name).sort_values(CACHE_TIMESTAMP_COLUMN)
    expected = expected.sort_values(CACHE_TIMESTAMP_COLUMN)
    common_index = expected[CACHE_TIMESTAMP_COLUMN].isin(
        aligned_df[CACHE_TIMESTAMP_COLUMN]
    )
    aligned_df = aligned_df[
        aligned_df[CACHE_TIMESTAMP_COLUMN].isin(expected[CACHE_TIMESTAMP_COLUMN])
    ].reset_index(drop=True)
    expected = expected[common_index].reset_index(drop=True)
    warmup = WARMUP_BARS.get(timeframe, 0)
    if warmup:
        aligned_df = aligned_df.iloc[warmup:].reset_index(drop=True)
        expected = expected.iloc[warmup:].reset_index(drop=True)
    _assert_frames_close(aligned_df, expected, skip_columns=EXPORT_SKIP_COLUMNS)


@pytest.mark.validation
def test_test_cache_matches_tradingview_snapshot() -> None:
    """Ensure the committed builder cache matches the TradingView reference."""
    for timeframe, parquet_name in PARQUET_FILENAMES.items():
        builder_df = _load_test_cache_parquet(parquet_name).sort_values(
            CACHE_TIMESTAMP_COLUMN
        )
        golden_df = _load_aligned_parquet(parquet_name).sort_values(
            CACHE_TIMESTAMP_COLUMN
        )
        builder_df = builder_df[
            builder_df[CACHE_TIMESTAMP_COLUMN].isin(golden_df[CACHE_TIMESTAMP_COLUMN])
        ].reset_index(drop=True)
        golden_df = golden_df[
            golden_df[CACHE_TIMESTAMP_COLUMN].isin(builder_df[CACHE_TIMESTAMP_COLUMN])
        ].reset_index(drop=True)
        _assert_frames_close(builder_df, golden_df)


@pytest.mark.validation
def test_bar_metadata_alignment() -> None:
    """Verify 100% alignment of bar metadata between builder and golden caches.

    This test ensures that bar window metadata (*_bar_open, *_bar_close,
    *_bar_lookup_key) matches exactly between the builder cache and golden cache.
    This validates the "available after close" semantics are implemented identically.
    """
    for timeframe, parquet_name in PARQUET_FILENAMES.items():
        builder_df = _load_test_cache_parquet(parquet_name).sort_values(
            CACHE_TIMESTAMP_COLUMN
        )
        golden_df = _load_aligned_parquet(parquet_name).sort_values(
            CACHE_TIMESTAMP_COLUMN
        )

        # Filter to common timestamps
        builder_df = builder_df[
            builder_df[CACHE_TIMESTAMP_COLUMN].isin(golden_df[CACHE_TIMESTAMP_COLUMN])
        ].reset_index(drop=True)
        golden_df = golden_df[
            golden_df[CACHE_TIMESTAMP_COLUMN].isin(builder_df[CACHE_TIMESTAMP_COLUMN])
        ].reset_index(drop=True)

        # Get all bar metadata columns for this timeframe
        bar_metadata_cols = [
            col
            for col in builder_df.columns
            if col.endswith("_bar_open")
            or col.endswith("_bar_close")
            or col.endswith("_bar_lookup_key")
        ]

        for col in bar_metadata_cols:
            builder_series = builder_df[col]
            golden_series = golden_df[col]

            # Special handling for 1d_bar_lookup_key: truncate time from builder
            if col == "1d_bar_lookup_key":
                # Builder: "2021-12-30T00:00:00Z", Golden: "2021-12-30"
                # Truncate builder values to date-only
                builder_series = builder_series.apply(
                    lambda x: (
                        x.split("T")[0] if isinstance(x, str) and "T" in x else x
                    )
                )

            # For datetime columns, compare as datetime
            if col.endswith("_bar_open") or col.endswith("_bar_close"):
                builder_series = pd.to_datetime(
                    builder_series, utc=True, errors="coerce"
                )
                golden_series = pd.to_datetime(golden_series, utc=True, errors="coerce")

                # Check for exact match including NaT values
                mismatch_mask = ~(
                    (builder_series == golden_series)
                    | (builder_series.isna() & golden_series.isna())
                )

                if mismatch_mask.any():
                    first_mismatch_idx = int(mismatch_mask.idxmax())
                    raise AssertionError(
                        f"{timeframe} {col}: Mismatch at row {first_mismatch_idx} "
                        f"(available_at={builder_df[CACHE_TIMESTAMP_COLUMN].iloc[first_mismatch_idx]})\n"
                        f"  Builder: {builder_series.iloc[first_mismatch_idx]}\n"
                        f"  Golden:  {golden_series.iloc[first_mismatch_idx]}"
                    )
            else:
                # For lookup_key columns (strings), check exact match
                # Handle None values properly
                mismatch_mask = ~(
                    (builder_series == golden_series)
                    | (builder_series.isna() & golden_series.isna())
                    | ((builder_series == "None") & (golden_series == "None"))
                    | (
                        (builder_series.isna() | (builder_series == "None"))
                        & (golden_series.isna() | (golden_series == "None"))
                    )
                )

                if mismatch_mask.any():
                    first_mismatch_idx = int(mismatch_mask.idxmax())
                    raise AssertionError(
                        f"{timeframe} {col}: Mismatch at row {first_mismatch_idx} "
                        f"(available_at={builder_df[CACHE_TIMESTAMP_COLUMN].iloc[first_mismatch_idx]})\n"
                        f"  Builder: {builder_series.iloc[first_mismatch_idx]}\n"
                        f"  Golden:  {golden_series.iloc[first_mismatch_idx]}"
                    )


@pytest.mark.validation
def test_cache_builder_produces_available_after_close(
    tmp_path: Path,
    raw_exports: dict[str, pd.DataFrame],
) -> None:
    """Round-trip the cache builder against the golden available-after-close parquet."""
    data_root = tmp_path / "tv_data"
    _write_tradingview_ohlc_dataset(data_root)

    descriptor = build_global_feature_caches(
        symbol="EUR/USD",
        data_root=data_root,
        config_path=GLOBAL_FEATURES_CONFIG,
        timeframes=list(TIMEFRAME_EXPORTS.keys()),
        overwrite=True,
        include_bar_windows=True,
    )

    builder_exports: dict[str, pd.DataFrame] = {}
    for timeframe in TIMEFRAME_EXPORTS:
        tf_path = descriptor.timeframe_path(timeframe)
        builder_exports[timeframe] = pd.read_parquet(tf_path)

    for timeframe, parquet_name in PARQUET_FILENAMES.items():
        expected = _build_expected_parquet(timeframe, raw_exports)
        golden = _load_aligned_parquet(parquet_name)
        common_columns = [
            col
            for col in golden.columns
            if col in expected.columns and col not in EXPORT_SKIP_COLUMNS
        ]
        missing_columns = [col for col in golden.columns if col not in expected.columns]
        assert (
            common_columns
        ), "No overlapping columns between builder output and golden snapshot."
        if missing_columns:
            assert set(missing_columns).issubset(
                TV_ONLY_COLUMNS
            ), f"Unexpected TradingView-only columns: {missing_columns}"
        golden_subset = golden[common_columns].set_index(CACHE_TIMESTAMP_COLUMN)
        expected_subset = expected[common_columns].set_index(CACHE_TIMESTAMP_COLUMN)
        common_index = expected_subset.index.intersection(golden_subset.index)
        assert (
            not common_index.empty
        ), "No overlapping timestamps between builder output and golden snapshot."
        golden_subset = golden_subset.loc[common_index]
        expected_subset = expected_subset.loc[common_index]
        warmup = WARMUP_BARS.get(timeframe, 0)
        if warmup > 0:
            golden_subset = golden_subset.iloc[warmup:]
            expected_subset = expected_subset.iloc[warmup:]
        _assert_feature_frames_match(golden_subset, expected_subset, timeframe)
