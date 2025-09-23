# ORPHANED_TEST: This test does not seem to correspond to a requirement.
from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_platform.data.loader import load_from_catalog


def _write_sample_csv(p: Path) -> None:
    p.write_text(
        "\n".join(
            [
                "UTCTime,Open,High,Low,Close,Volume",
                "2023-01-01 00:00:00,1,2,0.5,1.5,10",
                "2023-01-01 01:00:00,1,2,0.5,1.6,10",
                "2023-01-01 02:00:00,1,2,0.5,1.7,10",
            ]
        )
    )


def test_load_from_catalog_filters_and_resamples(tmp_path: Path) -> None:
    csvp = tmp_path / "eurusd.csv"
    _write_sample_csv(csvp)
    catp = tmp_path / "catalog.yaml"
    catp.write_text(f"EUR_USD:\n  csv_path: '{csvp}'\n")

    req = {
        "symbol": "EUR_USD",
        "timeframe": "2H",
        "start": "2023-01-01 00:30:00",
        "end": "2023-01-01 02:00:00",
    }

    df, flags = load_from_catalog(req, catalog_path=catp)
    assert flags == []
    # Normalized columns and UTC index
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    # Start filter removes the 00:00 row; resample to 2H yields at most 1 row
    assert len(df) <= 1


def test_load_from_catalog_missing_symbol(tmp_path: Path) -> None:
    catp = tmp_path / "catalog.yaml"
    catp.write_text("{}\n")
    req = {"symbol": "MISSING"}
    try:
        load_from_catalog(req, catalog_path=catp)
        assert False, "expected ValueError for missing symbol"
    except ValueError as e:  # noqa: PT011
        assert "symbol not in catalog" in str(e)
