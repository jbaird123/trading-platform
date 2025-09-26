"""Consolidated tests for trading_platform.data.schema.load_and_normalize_data."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from trading_platform.data.schema import load_and_normalize_data


# --- Happy-path and error handling ------------------------------------------------


def test_load_and_normalize_success_path(tmp_path: Path) -> None:
    csv_file = tmp_path / "perfect.csv"
    csv_file.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1,2,0.5,1.5,100\n"
        "2023-01-01 01:00:00,1.5,2.5,1.0,2.0,200\n"
    )

    df, flags = load_and_normalize_data(csv_file)

    assert len(df) == 2
    assert not flags
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"


def test_load_and_normalize_handles_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_file = tmp_path / "boom.csv"
    csv_file.write_text("garbage")

    def _explode(*args, **kwargs):  # pragma: no cover - executed via monkeypatch
        raise RuntimeError("boom")

    monkeypatch.setattr(pd, "read_csv", _explode)

    df, flags = load_and_normalize_data(csv_file)

    assert df.empty
    assert any(flag.startswith("unexpected_error:") for flag in flags)


def test_load_and_normalize_handles_missing_timestamp_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "missing_ts.csv"
    csv_file.write_text("Open,High,Low,Close,Volume\n1,2,0.5,1.5,100\n")

    df, flags = load_and_normalize_data(csv_file)

    assert df.empty
    assert "missing_timestamp" in flags


def test_load_and_normalize_handles_bad_timestamp_parse(tmp_path: Path) -> None:
    csv_file = tmp_path / "bad_ts.csv"
    csv_file.write_text("UTCTime,Open,High,Low,Close,Volume\nnot-a-date,1,2,0.5,1.5,100\n")

    df, flags = load_and_normalize_data(csv_file)

    assert df.empty
    assert any(flag.startswith("unexpected_error:") for flag in flags)


# --- Coverage-focused scenarios ---------------------------------------------------


def _write_temp_csv(content: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as handle:
        handle.write(content)
        name = handle.name
    return Path(name)


def test_schema_missing_or_unknown_columns() -> None:
    path_missing = _write_temp_csv("UTCTime,Open\n2023-01-01 00:00:00,1.0\n")
    try:
        result, flags = load_and_normalize_data(path_missing)
        assert result.empty
        assert "unexpected_columns" in flags[0]
        assert "missing=" in flags[0]
    finally:
        path_missing.unlink(missing_ok=True)

    path_unknown = _write_temp_csv(
        "UTCTime,Open,High,Low,Close,Volume,UnknownCol\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000,test\n"
    )
    try:
        result, flags = load_and_normalize_data(path_unknown)
        assert result.empty
        assert "unexpected_columns" in flags[0]
        assert "unknown=" in flags[0]
    finally:
        path_unknown.unlink(missing_ok=True)

    path_both = _write_temp_csv(
        "UTCTime,Open,UnknownCol\n2023-01-01 00:00:00,1.0,test\n"
    )
    try:
        result, flags = load_and_normalize_data(path_both)
        assert result.empty
        assert "unexpected_columns" in flags[0]
        assert "missing=" in flags[0] and "unknown=" in flags[0]
    finally:
        path_both.unlink(missing_ok=True)


def test_schema_normalized_column_validation() -> None:
    path_missing = _write_temp_csv(
        "timestamp,open\n2023-01-01 00:00:00,1.0\n"
    )
    try:
        result, flags = load_and_normalize_data(path_missing)
        assert result.empty
        assert "unexpected_columns" in flags[0]
        assert "missing=" in flags[0]
    finally:
        path_missing.unlink(missing_ok=True)

    path_unknown = _write_temp_csv(
        "timestamp,open,high,low,close,volume,unknown_col\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000,test\n"
    )
    try:
        result, flags = load_and_normalize_data(path_unknown)
        assert result.empty
        assert "unexpected_columns" in flags[0]
        assert "unknown=" in flags[0]
    finally:
        path_unknown.unlink(missing_ok=True)


def test_schema_successful_normalization_again() -> None:
    path = _write_temp_csv(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
    )
    try:
        result, flags = load_and_normalize_data(path)
        assert not result.empty
        assert flags == []
        assert result.index.name == "timestamp"
        assert set(["open", "high", "low", "close", "volume"]).issubset(result.columns)
    finally:
        path.unlink(missing_ok=True)

