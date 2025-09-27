from pathlib import Path

import pandas as pd
import pytest
from trading_platform.data.loader import load_instrument_data


def test_load_instrument_data_success():
    """
    Verify data is loaded from a conventional directory structure,
    combining 'full' and 'incremental' files.
    """
    test_data_root = Path("tests/fixtures/data")
    df, _ = load_instrument_data("EURUSD", test_data_root)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.index[0].isoformat() == "2023-01-01T00:00:00+00:00"
    assert df.index[1].isoformat() == "2023-01-02T00:00:00+00:00"
    assert df.iloc[1]["open"] == 1.2


def test_load_instrument_data_not_found():
    """
    Verify a FileNotFoundError is raised for a symbol with no data.
    """
    test_data_root = Path("tests/fixtures/data")
    with pytest.raises(FileNotFoundError, match="No data files found for symbol"):
        load_instrument_data("NOSUCHSYMBOL", test_data_root)
