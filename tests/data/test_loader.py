"""Consolidated tests for trading_platform.data.loader.load_from_catalog."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml
from trading_platform.data.instrument import InstrumentDefinition
from trading_platform.data.loader import load_from_catalog


def _write_sample_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "UTCTime,Open,High,Low,Close,Volume",
                "2023-01-01 00:00:00,1,2,0.5,1.5,10",
                "2023-01-01 01:00:00,1,2,0.5,1.6,10",
                "2023-01-01 02:00:00,1,2,0.5,1.7,10",
            ]
        )
    )


def _write_catalog(path: Path, content: dict) -> None:
    path.write_text(yaml.dump(content))


# --- Happy-path loader behaviour -------------------------------------------------


def test_load_from_catalog_filters_and_resamples(tmp_path: Path) -> None:
    csv_path = tmp_path / "eurusd.csv"
    _write_sample_csv(csv_path)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_path)}})

    request = {
        "symbol": "EUR_USD",
        "timeframe": "2H",
        "start": "2023-01-01 00:30:00",
        "end": "2023-01-01 02:00:00",
    }

    df, flags, instrument = load_from_catalog(request, catalog_path=catalog_path)

    assert flags == []
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert len(df) <= 1  # resampled into 2H buckets after filtering


# --- Validation error coverage ---------------------------------------------------


def test_loader_invalid_data_request() -> None:
    with pytest.raises(ValueError, match="data_request must be a dict"):
        load_from_catalog("not a dict")  # type: ignore[arg-type]


def test_loader_missing_symbol_variants() -> None:
    for payload in ({}, {"symbol": ""}, {"symbol": None}):
        with pytest.raises(ValueError, match="data_request.symbol is required"):
            load_from_catalog(payload)


def test_loader_catalog_not_found() -> None:
    with pytest.raises(FileNotFoundError, match="data catalog not found"):
        load_from_catalog(
            {"symbol": "EUR_USD"}, catalog_path=Path("/non/existent/catalog.yaml")
        )


def test_loader_symbol_not_in_catalog(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"OTHER": {"csv_path": "/path/other.csv"}})

    with pytest.raises(ValueError, match="symbol not in catalog: FAKE"):
        load_from_catalog({"symbol": "FAKE"}, catalog_path=catalog_path)

    _write_catalog(catalog_path, {})
    with pytest.raises(ValueError, match="symbol not in catalog: FAKE"):
        load_from_catalog({"symbol": "FAKE"}, catalog_path=catalog_path)

    _write_catalog(catalog_path, {"FAKE": {"description": "missing csv"}})
    with pytest.raises(ValueError, match="symbol not in catalog: FAKE"):
        load_from_catalog({"symbol": "FAKE"}, catalog_path=catalog_path)


def test_loader_empty_data_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    with pytest.raises(ValueError, match="Loaded data is empty"):
        load_from_catalog({"symbol": "EUR_USD"}, catalog_path=catalog_path)


# --- Additional behavioural branches --------------------------------------------


def test_loader_with_timeframe_resampling(tmp_path: Path) -> None:
    csv_file = tmp_path / "eurusd.csv"
    csv_file.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
        "2023-01-01 00:01:00,1.05,1.15,0.95,1.10,1100\n"
    )
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    df, flags, instrument = load_from_catalog(
        {"symbol": "EUR_USD", "timeframe": "1min"}, catalog_path=catalog_path
    )

    assert not flags
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_loader_without_timeframe_leaves_rows_intact(tmp_path: Path) -> None:
    csv_file = tmp_path / "eurusd.csv"
    _write_sample_csv(csv_file)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    df, flags, instrument = load_from_catalog(
        {"symbol": "EUR_USD"}, catalog_path=catalog_path
    )

    assert not flags
    assert len(df) == 3  # no resampling, original rows retained
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_load_from_catalog_returns_instrument_definition(tmp_path: Path) -> None:
    """Test that load_from_catalog returns InstrumentDefinition as third element."""
    csv_file = tmp_path / "eurusd.csv"
    _write_sample_csv(csv_file)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    # Mock get_instrument_definition to avoid dependency on actual definitions
    from unittest.mock import patch

    mock_instrument = InstrumentDefinition(
        asset_class="Forex",
        point_value=1.0,
        tick_size=0.00001,
        commission_model={"type": "spread"},
        sessions=[],
        symbol="EUR_USD",
    )

    with patch(
        "trading_platform.data.loader.get_instrument_definition",
        return_value=mock_instrument,
    ):
        result = load_from_catalog({"symbol": "EUR_USD"}, catalog_path=catalog_path)

        # Assert that the function returns a tuple with exactly three elements
        assert isinstance(result, tuple)
        assert len(result) == 3

        df, flags, instrument = result

        # Assert that the third element is an instance of InstrumentDefinition
        assert isinstance(instrument, InstrumentDefinition)
        assert instrument.symbol == "EUR_USD"


def test_load_from_catalog_with_symbol_normalization(tmp_path: Path) -> None:
    """Test that load_from_catalog works with symbol normalization."""
    csv_file = tmp_path / "eurusd.csv"
    _write_sample_csv(csv_file)
    catalog_path = tmp_path / "catalog.yaml"

    # Use canonical format in catalog
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    # Test that EUR_USD (non-canonical) finds EURUSD in catalog
    df, flags, instrument = load_from_catalog(
        {"symbol": "EUR_USD"}, catalog_path=catalog_path
    )

    assert not flags
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert instrument.symbol == "EURUSD"  # Should be normalized to canonical format

    # Test that EUR/USD (another non-canonical format) also works
    df2, flags2, instrument2 = load_from_catalog(
        {"symbol": "EUR/USD"}, catalog_path=catalog_path
    )

    assert not flags2
    assert not df2.empty
    assert instrument2.symbol == "EURUSD"  # Should be normalized to canonical format

    # Verify both return the same data
    pd.testing.assert_frame_equal(df, df2)
    assert instrument.symbol == instrument2.symbol


def test_load_from_catalog_loads_incremental_data(tmp_path: Path) -> None:
    """Test that load_from_catalog can load and combine incremental data files."""
    # Create base file
    base_file = tmp_path / "eurusd_base.csv"
    base_file.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
        "2023-01-01 01:00:00,1.05,1.15,0.95,1.10,1100\n"
    )

    # Create incremental directory and files
    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)

    inc_file1 = incremental_dir / "eurusd_interval_min_1_20230102_20230102.csv"
    inc_file1.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-02 00:00:00,1.10,1.20,1.00,1.15,1200\n"
    )

    inc_file2 = incremental_dir / "eurusd_interval_min_1_20230103_20230103.csv"
    inc_file2.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-03 00:00:00,1.15,1.25,1.05,1.20,1300\n"
    )

    # Create catalog pointing to base file
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(base_file)}})

    # Test loading - should combine all files
    df, flags, instrument = load_from_catalog(
        {"symbol": "EURUSD"}, catalog_path=catalog_path
    )

    # Assert that the returned DataFrame contains data from all files
    assert not flags
    assert len(df) == 4  # 2 base + 1 + 1 incremental

    # Assert that the index is sorted and unique
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique

    # Verify data spans from base file to incremental files
    assert df.index[0].strftime("%Y-%m-%d") == "2023-01-01"
    assert df.index[-1].strftime("%Y-%m-%d") == "2023-01-03"


def test_loader_skips_empty_incremental_files(tmp_path: Path) -> None:
    """Empty incremental CSV files must not be appended to the dataset."""
    base_file = tmp_path / "eurusd_base.csv"
    _write_sample_csv(base_file)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(base_file)}})

    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)
    empty_file = incremental_dir / "eurusd_interval_min_1_20240101_20240101.csv"
    empty_file.write_text("timestamp,open,high,low,close,volume\n")

    df, flags, _ = load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)

    assert len(df) == 3
    assert flags == []


def test_loader_ignores_failed_incremental_files(tmp_path: Path) -> None:
    """Incremental loader failures are ignored while base data is returned."""
    base_file = tmp_path / "eurusd_base.csv"
    _write_sample_csv(base_file)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(base_file)}})

    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)
    bad_file = incremental_dir / "eurusd_interval_min_1_bad_bad.csv"
    bad_file.write_text("garbage\n")

    from unittest.mock import patch

    from trading_platform.data import loader as loader_module

    real_load = loader_module.load_and_normalize_data

    def side_effect(path: Path):
        if Path(path) == base_file:
            return real_load(Path(path))
        raise RuntimeError("failed incremental load")

    with patch(
        "trading_platform.data.loader.load_and_normalize_data",
        side_effect=side_effect,
    ):
        df, flags, _ = load_from_catalog(
            {"symbol": "EURUSD"}, catalog_path=catalog_path
        )

    assert len(df) == 3
    assert flags == []
