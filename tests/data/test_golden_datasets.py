"""Golden dataset validation tests.

# Validates: [DH-2.13]

Note: Indicator validation tests (EMA, RSI, ADX, ATR, BB) were removed as they
are redundant with tests/validation/test_indicator_validation.py which provides
superior coverage with proper bar-close alignment handling.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from trading_platform.data.schema import resample_ohlc

SAMPLE_1H_FILE = (
    Path(__file__).parent.parent.parent
    / "data/samples/tradingview_oanda_eurusd_1h_sample.csv"
)
SAMPLE_1MIN_FILE = (
    Path(__file__).parent.parent.parent
    / "data/samples/tradingview_oanda_eurusd_1min_sample.csv"
)


def _load_and_prep_dataframe(file_path: Path) -> pd.DataFrame:
    """Loads and prepares a dataframe from a TradingView CSV."""
    df = pd.read_csv(file_path)
    df = df.rename(columns={"time": "timestamp", "Volume": "volume"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    return df


def test_resampling_1min_to_1h_matches_golden_data():
    # Validates: [DH-2.5]
    """
    Ensures that resampling 1-minute data to a 1-hour timeframe produces
    OHLCV data that is identical to the golden 1-hour dataset.
    """
    # Load the golden 1H data
    golden_data_1h = _load_and_prep_dataframe(SAMPLE_1H_FILE)

    # Load the 1-minute data that will be resampled
    df_1min = _load_and_prep_dataframe(SAMPLE_1MIN_FILE)

    # Resample the 1-minute data to 1-hour
    resampled_df = resample_ohlc(df_1min, "1H")

    # Select only the core OHLCV columns from the golden 1H data for comparison
    golden_ohlcv_1h = golden_data_1h[["open", "high", "low", "close", "volume"]]

    # Align the two dataframes to ensure we only compare matching timestamps
    aligned_resampled, aligned_golden = resampled_df.align(
        golden_ohlcv_1h, join="inner", axis=0
    )

    # Check that we have data to compare after alignment
    assert not aligned_resampled.empty, "Resampled data is empty after alignment."
    assert not aligned_golden.empty, "Golden 1H data is empty after alignment."

    # 1. Test OHLC data for exact equality
    assert_frame_equal(
        aligned_resampled[["open", "high", "low", "close"]],
        aligned_golden[["open", "high", "low", "close"]],
    )

    # 2. Test volume separately with a tolerance, as it can have minor noise
    assert np.allclose(
        aligned_resampled["volume"],
        aligned_golden["volume"],
        rtol=1e-2,  # Allow for 1% difference in volume
    ), "Resampled volume does not match golden data within tolerance."
