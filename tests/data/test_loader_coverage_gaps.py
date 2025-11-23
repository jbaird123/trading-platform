"""Additional tests to achieve 100% coverage for data/loader.py."""

import pytest
from trading_platform.data.loader import load_instrument_data


def test_load_instrument_data_empty_base_file(tmp_path):
    """Test that empty base file raises ValueError."""

    # Create directory structure
    symbol_dir = tmp_path / "full" / "eurusd"
    symbol_dir.mkdir(parents=True)

    # Create empty base file
    empty_file = symbol_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    empty_file.write_text("timestamp,open,high,low,close,volume\n")  # Header only

    # Should raise ValueError for empty data
    with pytest.raises(ValueError, match="Base data file is empty"):
        load_instrument_data("EURUSD", tmp_path)


def test_load_instrument_data_with_incremental_files(tmp_path):
    """Test loading with incremental files."""

    # Create directory structure
    full_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create base file
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    base_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,100\n"
        "2023-01-01 01:00:00+00:00,1.05,1.15,0.95,1.10,110\n"
    )

    # Create incremental file
    inc_file = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    inc_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-02 00:00:00+00:00,1.10,1.20,1.00,1.15,120\n"
    )

    df, flags = load_instrument_data("EURUSD", tmp_path)

    # Should have combined data
    assert len(df) == 3  # 2 base + 1 incremental
    assert len(flags) == 0


def test_load_instrument_data_skip_empty_incremental_files(tmp_path):
    """Test that empty incremental files are skipped."""

    # Create directory structure
    full_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create base file
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    base_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,100\n"
    )

    # Create empty incremental file
    empty_inc = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    empty_inc.write_text("timestamp,open,high,low,close,volume\n")  # Header only

    df, flags = load_instrument_data("EURUSD", tmp_path)

    # Should only have base data (empty incremental skipped)
    assert len(df) == 1
    assert len(flags) == 0


def test_load_instrument_data_skip_corrupt_incremental_files(tmp_path):
    """Test that corrupt incremental files are skipped."""

    # Create directory structure
    full_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create base file
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    base_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,100\n"
    )

    # Create corrupt incremental file
    corrupt_inc = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    corrupt_inc.write_text("corrupted,data,file\n")

    df, flags = load_instrument_data("EURUSD", tmp_path)

    # Should only have base data (corrupt incremental skipped)
    assert len(df) == 1
    assert len(flags) == 0


def test_load_instrument_data_multiple_dataframes_concat(tmp_path):
    """Test concatenation when multiple dataframes are loaded."""

    # Create directory structure
    full_dir = tmp_path / "full" / "eurusd"
    inc_dir = tmp_path / "incremental" / "eurusd"
    full_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)

    # Create base file
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    base_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,100\n"
    )

    # Create multiple incremental files
    inc_file1 = inc_dir / "eurusd_interval_minute_1_20230102_20230102.csv"
    inc_file1.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-02 00:00:00+00:00,1.10,1.20,1.00,1.15,120\n"
    )

    inc_file2 = inc_dir / "eurusd_interval_minute_1_20230103_20230103.csv"
    inc_file2.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-03 00:00:00+00:00,1.15,1.25,1.05,1.20,130\n"
    )

    df, flags = load_instrument_data("EURUSD", tmp_path)

    # Should have all data concatenated and sorted
    assert len(df) == 3  # 1 base + 2 incremental
    assert df.index.is_monotonic_increasing  # Should be sorted
    assert len(flags) == 0
