from pathlib import Path

from trading_platform.data.loader import load_instrument_data


def test_load_instrument_data_alternate_test_dir(tmp_path: Path) -> None:
    """Loader should accept the legacy '<symbol>_test' layout.

    This exercises the compatibility branch that looks for a directory
    named '<sanitized_symbol>_test' when the standard 'full/<symbol>'
    path is not present.
    """
    # Create the alternative test dir structure: eurusd_test/full/... 
    test_root = tmp_path
    symbol = "EUR/USD"
    sanitized = "eurusd"

    alt_dir = test_root / f"{sanitized}_test"
    full_dir = alt_dir / "full"
    full_dir.mkdir(parents=True)

    # Write a minimal CSV base file under the alternate path
    base_file = full_dir / "eurusd_interval_minute_1_20230101_20230101.csv"
    base_file.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2023-01-01 00:00:00+00:00,1.0,1.1,0.9,1.05,100\n"
    )

    # Call loader using the normal data_root (which lacks full/eurusd)
    df, flags = load_instrument_data(symbol, test_root)

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert flags == []
