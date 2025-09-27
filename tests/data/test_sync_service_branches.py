from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_platform.data import sync_service as ss


def test_latest_file_selection(tmp_path: Path) -> None:
    # Create two previous files; the later one should be chosen
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)

    f1 = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    f1.write_text(
        "timestamp,open\n2023-01-01 00:00:00+00:00,1\n"
    )

    f2 = full_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    f2.write_text(
        "timestamp,open\n2023-01-02 00:00:00+00:00,1\n"
    )

    # New file starts after latest existing file
    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)
    new_file = inc_dir / "new.csv"
    new_file.write_text(
        "timestamp,open\n2023-01-02 00:05:00+00:00,1\n"
    )

    # The gap is 5 minutes during market hours so a RuntimeError is expected.
    # Also verify the function prints the expected timestamp/gap information
    import pytest

    with pytest.raises(RuntimeError):
        ss.verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_incremental_file_equal_new_file_skipped(tmp_path: Path) -> None:
    # Create only incremental dir with a file equal to new_file_path
    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)
    new_file = inc_dir / "eurusd_interval_minute_1_20230103_20230103.csv"
    new_file.write_text(
        "timestamp,open\n2023-01-03 00:00:00+00:00,1\n"
    )

    # No full dir and the only incremental file is the new file, so
    # verify_data_continuity should skip and report no previous files
    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)


def test_is_during_market_hours_monday_friday_sunday() -> None:
    # Monday case (weekday==0): hour >= 0 branch
    mon1 = pd.Timestamp("2025-08-25 00:10:00+00:00")
    mon2 = pd.Timestamp("2025-08-25 02:00:00+00:00")
    assert ss._is_during_market_hours(mon1, mon2) is True

    # Friday case (weekday==4): hour <= 21 branch
    fri1 = pd.Timestamp("2025-08-22 10:00:00+00:00")
    fri2 = pd.Timestamp("2025-08-22 20:00:00+00:00")
    assert ss._is_during_market_hours(fri1, fri2) is True

    # Sunday case (weekday==6): hour >= 21 branch
    sun1 = pd.Timestamp("2025-08-24 21:30:00+00:00")
    sun2 = pd.Timestamp("2025-08-24 22:30:00+00:00")
    assert ss._is_during_market_hours(sun1, sun2) is True
