# Validates: [DH-F.1]
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from trading_platform.data.sync import main


def test_main_sync_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Integration test for main sync logic."""
    # Create a dummy file in the test directory
    full_dir = tmp_path / "full"
    full_dir.mkdir()
    dummy_file = full_dir / "eurusd_interval_min_1_20250901_20250920.csv"
    dummy_file.write_text("timestamp,open,high,low,close,volume\n")

    # Mock the download_and_save_data function
    download_calls: list[dict] = []

    def mock_download_and_save_data(
            symbol: str, start_date: date, end_date: date, data_root: Path
        ):
            download_calls.append({
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'data_root': data_root
        })

    monkeypatch.setattr(
        'trading_platform.data.sync.download_and_save_data',
        mock_download_and_save_data
    )    # Test single symbol sync
    main(['--symbol', 'EUR/USD', '--data-root', str(tmp_path)])

    # Assert download_and_save_data was called with correct parameters
    assert len(download_calls) == 1
    call = download_calls[0]
    assert call['symbol'] == 'EUR/USD'
    assert call['start_date'] == date(2025, 9, 21)  # Day after last file date

    # Calculate expected end_date (yesterday)
    yesterday = date.today() - timedelta(days=1)
    assert call['end_date'] == yesterday
    assert call['data_root'] == tmp_path

    # Reset for next test
    download_calls.clear()

    # Test --all option
    main(['--all', '--data-root', str(tmp_path)])

    # Assert download_and_save_data is called for symbols with existing data
    # In this test, only EURUSD has existing data files, so only 1 call expected
    assert len(download_calls) == 1
    call = download_calls[0]
    assert call['symbol'] == 'EURUSD'  # Normalized from existing data
    assert call['start_date'] == date(2025, 9, 21)
    assert call['end_date'] == yesterday
