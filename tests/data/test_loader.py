"""Consolidated tests for trading_platform.data.loader.load_from_catalog."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

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
    _write_catalog(catalog_path, {"EUR_USD": {"csv_path": str(csv_path)}})

    request = {
        "symbol": "EUR_USD",
        "timeframe": "2H",
        "start": "2023-01-01 00:30:00",
        "end": "2023-01-01 02:00:00",
    }

    df, flags = load_from_catalog(request, catalog_path=catalog_path)

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
            {"symbol": "EURUSD"}, catalog_path=Path("/non/existent/catalog.yaml")
        )


def test_loader_symbol_not_in_catalog(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"OTHER": {"csv_path": "/path/other.csv"}})

    with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
        load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)

    _write_catalog(catalog_path, {})
    with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
        load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)

    _write_catalog(catalog_path, {"EURUSD": {"description": "missing csv"}})
    with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
        load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)


def test_loader_empty_data_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EURUSD": {"csv_path": str(csv_file)}})

    with pytest.raises(ValueError, match="Loaded data is empty"):
        load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)


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

    df, flags = load_from_catalog(
        {"symbol": "EURUSD", "timeframe": "1min"}, catalog_path=catalog_path
    )

    assert not flags
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_loader_without_timeframe_leaves_rows_intact(tmp_path: Path) -> None:
    csv_file = tmp_path / "eurusd.csv"
    _write_sample_csv(csv_file)
    catalog_path = tmp_path / "catalog.yaml"
    _write_catalog(catalog_path, {"EUR_USD": {"csv_path": str(csv_file)}})

    df, flags = load_from_catalog({"symbol": "EUR_USD"}, catalog_path=catalog_path)

    assert not flags
    assert len(df) == 3  # no resampling, original rows retained
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
