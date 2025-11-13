from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_series_equal
from trading_platform.core.global_features_cache import (
    build_global_feature_caches,
    cache_covers_features,
)


def _write_sample_csv(path: Path) -> None:
    idx = pd.date_range("2023-01-01", periods=720, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 100.0,
        }
    )
    df.to_csv(path, index=False)


def _write_sample_global_yaml(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "features:",
                '  - name: "m5_test_ema"',
                '    type: "EMA"',
                '    params: {"length": 3}',
                '    timeframe: "5min"',
                '  - name: "m15_test_rsi"',
                '    type: "RSI"',
                '    params: {"length": 5}',
                '    timeframe: "15min"',
            ]
        )
    )


def test_build_global_feature_caches_creates_outputs(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_sample_global_yaml(global_yaml)

    descriptor = build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min", "15min"],
        overwrite=True,
    )

    metadata = descriptor.metadata_path().read_text()
    assert "5min" in metadata
    assert "15min" in metadata

    five_min_df = pd.read_parquet(descriptor.timeframe_path("5min"))
    fifteen_min_df = pd.read_parquet(descriptor.timeframe_path("15min"))

    assert "5min_test_ema" in five_min_df.columns
    assert "15min_test_rsi" in fifteen_min_df.columns


def test_build_global_feature_caches_is_idempotent(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_sample_global_yaml(global_yaml)

    descriptor = build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min"],
        overwrite=True,
    )
    first_metadata = descriptor.metadata_path().stat().st_mtime

    descriptor_repeat = build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min"],
        overwrite=False,
    )
    second_metadata = descriptor_repeat.metadata_path().stat().st_mtime

    assert descriptor.base_dir() == descriptor_repeat.base_dir()
    assert first_metadata == second_metadata


def test_available_at_matches_bar_close(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_sample_global_yaml(global_yaml)

    descriptor = build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min"],
        overwrite=True,
    )

    cache_df = pd.read_parquet(descriptor.timeframe_path("5min"))
    assert "available_at" in cache_df.columns

    available = pd.to_datetime(cache_df["available_at"], utc=True)
    assert available.is_monotonic_increasing
    diffs = available.diff().dropna()
    assert not diffs.empty
    assert (diffs == pd.Timedelta(minutes=5)).all()


def test_build_global_feature_caches_includes_bar_windows(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_sample_global_yaml(global_yaml)

    descriptor = build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min"],
        overwrite=True,
        include_bar_windows=True,
    )

    five_min_df = pd.read_parquet(descriptor.timeframe_path("5min"))
    assert "5min_bar_open" in five_min_df.columns
    assert "5min_bar_close" in five_min_df.columns
    assert "5min_bar_lookup_key" in five_min_df.columns
    available = pd.to_datetime(five_min_df["available_at"], utc=True)
    bar_open = pd.to_datetime(five_min_df["5min_bar_open"], utc=True)
    bar_close = pd.to_datetime(five_min_df["5min_bar_close"], utc=True)
    valid_mask = bar_open.notna() & bar_close.notna()
    assert valid_mask.any()
    bar_open_valid = bar_open[valid_mask]
    bar_close_valid = bar_close[valid_mask]
    delta = pd.Timedelta(minutes=5)
    assert_series_equal(
        bar_open_valid + delta,
        bar_close_valid,
        check_names=False,
    )
    assert (bar_open_valid < bar_close_valid).all()
    assert (bar_close_valid <= available[valid_mask]).all()
    lookup = pd.to_datetime(five_min_df["5min_bar_lookup_key"], utc=True)
    lookup_valid = lookup.notna()
    if lookup_valid.any():
        assert (lookup[lookup_valid] <= available[lookup_valid]).all()


def test_cache_covers_features_detects_available_columns(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_sample_global_yaml(global_yaml)

    build_global_feature_caches(
        symbol="EUR_USD",
        data_root=data_root,
        config_path=global_yaml,
        timeframes=["5min"],
        overwrite=True,
    )

    assert cache_covers_features(
        symbol="EUR_USD",
        cache_root=data_root,
        config_path=global_yaml,
        timeframe="5min",
        feature_names=["m5_test_ema"],
    )
    assert not cache_covers_features(
        symbol="EUR_USD",
        cache_root=data_root,
        config_path=global_yaml,
        timeframe="5min",
        feature_names=["missing_feature"],
    )
