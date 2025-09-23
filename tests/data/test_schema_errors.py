# Validates: [DH-2.3], [DH-2.6]
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_platform.data.schema import load_and_normalize_data


def test_load_and_normalize_success_path(tmp_path: Path):
    """Tests the ideal path for data loading and normalization."""
    # Arrange: create a perfect CSV file
    f = tmp_path / "perfect.csv"
    f.write_text(
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1,2,0.5,1.5,100\n"
        "2023-01-01 01:00:00,1.5,2.5,1.0,2.0,200"
    )

    # Act
    df, flags = load_and_normalize_data(f)

    # Assert: df is correct and no flags are raised
    assert len(df) == 2
    assert not flags
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert df.iloc[0]["close"] == 1.5


def test_load_and_normalize_handles_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange: create a dummy file path and force read_csv to raise
    f = tmp_path / "bad.csv"
    f.write_text("garbage")

    def _boom(path):  # type: ignore[no-redef]
        raise RuntimeError("boom")

    monkeypatch.setattr(pd, "read_csv", _boom)

    # Act
    df, flags = load_and_normalize_data(f)

    # Assert: empty df and an unexpected_error flag present
    assert df.empty
    assert any(flag.startswith("unexpected_error:") for flag in flags)


def test_load_and_normalize_handles_missing_timestamp_column(tmp_path: Path):
    # Arrange: create a CSV with a missing 'UTCTime' column
    f = tmp_path / "missing_cols.csv"
    f.write_text("Open,High,Low,Close,Volume\n1,2,0.5,1.5,100")

    # Act
    df, flags = load_and_normalize_data(f)

    # Assert: empty df and a missing_timestamp flag present
    assert df.empty
    assert "missing_timestamp" in flags


def test_load_and_normalize_handles_bad_timestamp_parse(tmp_path: Path):
    # Arrange: create a CSV with a non-parseable timestamp
    f = tmp_path / "bad_ts.csv"
    f.write_text("UTCTime,Open,High,Low,Close,Volume\nnot-a-date,1,2,0.5,1.5,100")

    # Act
    df, flags = load_and_normalize_data(f)

    # Assert: empty df and an unexpected_error flag present
    assert df.empty
    assert any(flag.startswith("unexpected_error:") for flag in flags)
