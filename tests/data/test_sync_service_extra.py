from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd
import pytest

from trading_platform.data import sync_service as ss


def test_verify_data_continuity_all_prev_unreadable(tmp_path: Path, monkeypatch, capsys) -> None:
    # Create a couple of files that will be considered prev files
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)
    f1 = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    f1.write_text("not,a,real,csv\n")

    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)
    new_file = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    new_file.write_text("timestamp,open,high,low,close,volume\n2023-01-02 00:00:00+00:00,1,2,3,4,5\n")

    # Monkeypatch read_csv to always raise for prev files
    def fake_read_csv(path, *a, **k):
        raise RuntimeError("cannot read")

    monkeypatch.setattr(ss.pd, "read_csv", fake_read_csv)

    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)
    out = capsys.readouterr().out
    assert "Could not determine latest timestamp" in out


def test_verify_data_continuity_new_file_read_error(tmp_path: Path, monkeypatch, capsys) -> None:
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)
    prev = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    prev.write_text("timestamp,open\n2023-01-01 00:00:00+00:00,1\n")

    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)
    new_file = inc_dir / "new.csv"
    new_file.write_text("corrupt")

    # Fake read_csv to return a df for prev, but raise for new_file
    real_read = ss.pd.read_csv

    def fake_read_csv(path, *a, **k):
        if str(path).endswith("new.csv"):
            raise ValueError("bad new file")
        return real_read(path, *a, **k)

    monkeypatch.setattr(ss.pd, "read_csv", fake_read_csv)

    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)
    out = capsys.readouterr().out
    assert "Could not read new file" in out or "Warning: Could not read new file" in out


def test_verify_data_continuity_continuous_gap(tmp_path: Path, capsys) -> None:
    full_dir = tmp_path / "full" / "eurusd"
    full_dir.mkdir(parents=True)
    prev = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    prev.write_text("timestamp,open\n2023-01-01 00:00:00+00:00,1\n")

    inc_dir = tmp_path / "incremental" / "eurusd"
    inc_dir.mkdir(parents=True)
    # New file starts one minute later -> considered continuous
    new_file = inc_dir / "new.csv"
    new_file.write_text("timestamp,open\n2023-01-01 00:01:00+00:00,1\n")

    ss.verify_data_continuity("EUR/USD", tmp_path, new_file)
    out = capsys.readouterr().out
    assert "Data appears continuous" in out


def test_download_and_save_data_start_in_future(tmp_path: Path, capsys) -> None:
    future = date.today() + timedelta(days=2)
    ss.download_and_save_data("EUR/USD", future, future, tmp_path)
    out = capsys.readouterr().out
    assert "Start date" in out and "in the future" in out


def test_download_and_save_data_end_adjusted_and_fetch_raises(monkeypatch, tmp_path: Path, capsys) -> None:
    # Create fake module with fetch that raises
    class FakeDukaErr:
        INTERVAL_MIN_1 = 1
        OFFER_SIDE_BID = 1

        @staticmethod
        def fetch(*a, **k):
            raise RuntimeError("network")

    monkeypatch.setitem(sys.modules, "dukascopy_python", FakeDukaErr)

    start = date.today() - timedelta(days=1)
    end = date.today() + timedelta(days=5)  # in future to trigger adjust
    ss.download_and_save_data("EUR/USD", start, end, tmp_path)
    out = capsys.readouterr().out
    assert "Adjusting end date" in out or "Error fetching data from Dukascopy" in out


def test_weekend_and_market_hours_tz_naive() -> None:
    # Use tz-naive timestamps to force tz_localize code paths
    last_ts = pd.Timestamp("2023-01-06 21:00:00")
    first_ts = pd.Timestamp("2023-01-08 21:30:00")

    assert ss._is_expected_weekend_gap(last_ts, first_ts)
    assert not ss._is_during_market_hours(last_ts, first_ts)


def test_download_and_save_data_import_error(monkeypatch, tmp_path: Path, capsys) -> None:
    # Force ImportError for dukascopy_python by patching __import__
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "dukascopy_python":
            raise ModuleNotFoundError("no module named dukascopy_python")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Import error occurs at function import time and will propagate
    with pytest.raises(ModuleNotFoundError):
        ss.download_and_save_data("EUR/USD", date.today(), date.today(), tmp_path)
