# Validates: [DH-F.1]
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from trading_platform.data.sync import main


def test_main_sync_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Integration test for main sync logic."""
    # Create a dummy file in the test directory with new structure
    full_symbol_dir = tmp_path / "full" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    dummy_file = full_symbol_dir / "eurusd_interval_min_1_20250901_20250920.csv"
    dummy_file.write_text("timestamp,open,high,low,close,volume\n")

    # Mock the download_and_save_data function
    download_calls: list[dict] = []

    def mock_download_and_save_data(
        symbol: str, start_date: date, end_date: date, data_root: Path
    ):
        download_calls.append(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "data_root": data_root,
            }
        )

    monkeypatch.setattr(
        "trading_platform.data.sync.download_and_save_data", mock_download_and_save_data
    )  # Test single symbol sync
    main(["--symbol", "EUR/USD", "--data-root", str(tmp_path)])

    # Assert download_and_save_data was called with correct parameters
    assert len(download_calls) == 1
    call = download_calls[0]
    assert call["symbol"] == "EUR/USD"
    assert call["start_date"] == date(2025, 9, 21)  # Day after last file date

    # Calculate expected end_date (yesterday)
    yesterday = date.today() - timedelta(days=1)
    assert call["end_date"] == yesterday
    assert call["data_root"] == tmp_path

    # Reset for next test
    download_calls.clear()

    # Test --all option
    main(["--all", "--data-root", str(tmp_path)])

    # Assert download_and_save_data is called for symbols with existing data
    # In this test, only EURUSD has existing data files, so only 1 call expected
    assert len(download_calls) == 1
    call = download_calls[0]
    assert call["symbol"] == "EURUSD"  # Normalized from existing data
    assert call["start_date"] == date(2025, 9, 21)
    assert call["end_date"] == yesterday
    assert call["data_root"] == tmp_path


def test_main_requires_symbol_or_all(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--data-root", str(tmp_path)])


def test_process_symbol_skips_without_existing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trading_platform.data.sync import process_symbol

    def fake_last_sync(files):
        assert files == []
        return None

    def fail_download(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("download should not be called")

    monkeypatch.setattr("trading_platform.data.sync.get_last_sync_date", fake_last_sync)
    monkeypatch.setattr(
        "trading_platform.data.sync.download_and_save_data", fail_download
    )

    process_symbol("EUR/USD", tmp_path)


def test_process_symbol_uses_incremental_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trading_platform.data.sync import process_symbol

    incremental_dir = tmp_path / "incremental" / "eurusd"
    incremental_dir.mkdir(parents=True)
    inc_file = incremental_dir / "eurusd_interval_min_1_20240101_20240131.csv"
    inc_file.write_text("timestamp,open,high,low,close,volume\n")

    captured_files: list[list[Path]] = []

    def fake_last_sync(files):
        captured_files.append(files)
        return date(2024, 1, 31)

    download_calls: list[dict] = []

    def fake_download(symbol, start_date, end_date, data_root):
        download_calls.append(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "data_root": data_root,
            }
        )

    monkeypatch.setattr("trading_platform.data.sync.get_last_sync_date", fake_last_sync)
    monkeypatch.setattr(
        "trading_platform.data.sync.download_and_save_data", fake_download
    )

    process_symbol("EUR/USD", tmp_path)

    assert captured_files and captured_files[0][0] == inc_file
    assert download_calls
    call = download_calls[0]
    assert call["symbol"] == "EUR/USD"
    assert call["start_date"] == date(2024, 2, 1)


def test_process_symbol_skips_when_up_to_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trading_platform.data.sync import process_symbol

    full_symbol_dir = tmp_path / "full" / "eurusd"
    full_symbol_dir.mkdir(parents=True)
    latest = date.today() - timedelta(days=1)
    filename = f"eurusd_interval_min_1_{latest:%Y%m%d}_{latest:%Y%m%d}.csv"
    (full_symbol_dir / filename).write_text("timestamp,open,high,low,close,volume\n")

    def fake_last_sync(files):
        assert files
        return latest

    def fail_download(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("download should not be called")

    monkeypatch.setattr("trading_platform.data.sync.get_last_sync_date", fake_last_sync)
    monkeypatch.setattr(
        "trading_platform.data.sync.download_and_save_data", fail_download
    )

    process_symbol("EUR/USD", tmp_path)
