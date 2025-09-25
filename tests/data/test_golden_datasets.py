from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from trading_platform.data.schema import resample_ohlc
from trading_platform.strategy.features import compute_features

# Define the indicators to test based on the columns in the sample CSV
# Format: (our_name, tradingview_name, type, params)
INDICATOR_TEST_CASES = [
    ("EMA_50", "EMA_50", "EMA", {"length": 50}),
    ("EMA_20", "EMA_20", "EMA", {"length": 20}),
    ("RSI_14", "RSI_14", "RSI", {"length": 14}),
    ("ADX_14", "ADX_14_14", "ADX", {"length": 14}),
    ("ATR_14", "ATR_14_RMA", "ATR", {"length": 14}),
    ("BB_MIDDLE", "BB_Basis", "BB", {"length": 20, "ndev": 2.0}),
    ("BB_UPPER", "BB_Upper", "BB", {"length": 20, "ndev": 2.0}),
    ("BB_LOWER", "BB_Lower", "BB", {"length": 20, "ndev": 2.0}),
]

SAMPLE_1H_FILE = (
    Path(__file__).parent.parent.parent
    / "data/samples/tradingview_oanda_eurusd_1h_sample.csv"
)
SAMPLE_1MIN_FILE = (
    Path(__file__).parent.parent.parent
    / "data/samples/tradingview_oanda_eurusd_1min_sample.csv"
)


# Most indicators have a "warm-up" period where their values can differ
# between libraries. We'll skip this many initial bars before comparing.
WARMUP_PERIOD = 100

# Certain indicators (like RSI, ADX) use different smoothing methods (EMA vs. RMA)
# between libraries, so we allow a slightly higher tolerance for them.
TOLERANCES = {
    "RSI_14": {"rtol": 1e-3},
    "ADX_14": {"rtol": 1e-2},  # ADX has a more complex calculation
    "ATR_14": {"rtol": 1e-3},
}


def _load_and_prep_dataframe(file_path: Path) -> pd.DataFrame:
    """Loads and prepares a dataframe from a TradingView CSV."""
    df = pd.read_csv(file_path)
    df = df.rename(columns={"time": "timestamp", "Volume": "volume"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    return df


@pytest.fixture(scope="module")
def golden_data_1h():
    """Loads and prepares the 1-hour golden dataset."""
    return _load_and_prep_dataframe(SAMPLE_1H_FILE)


@pytest.fixture(scope="module")
def calculated_data(golden_data_1h):
    """Calculates indicators using our platform's code on the 1h data."""
    feature_specs = [
        {"name": our_name, "type": type, "params": params}
        for our_name, _, type, params in INDICATOR_TEST_CASES
        if type != "BB"  # Handle BB separately
    ]
    feature_specs.append(
        {"name": "BB", "type": "BB", "params": {"length": 20, "ndev": 2.0}}
    )
    calculated_df = compute_features(golden_data_1h, feature_specs).rename(
        columns={
            "BB_middle": "BB_MIDDLE",
            "BB_upper": "BB_UPPER",
            "BB_lower": "BB_LOWER",
        }
    )
    return calculated_df


@pytest.mark.parametrize("our_name, tradingview_name, _, __", INDICATOR_TEST_CASES)
def test_indicator_matches_tradingview(
    golden_data_1h,
    calculated_data,
    our_name,
    tradingview_name,
    _,
    __,
):
    # Validates: [DH-2.11], [SE-3.6]
    """
    Compares indicator values calculated by our platform against the golden
    dataset from TradingView to ensure they are numerically consistent.
    """
    golden_series = golden_data_1h[tradingview_name].dropna()
    calculated_series = calculated_data[our_name].dropna()
    aligned_golden, aligned_calculated = golden_series.align(
        calculated_series, join="inner"
    )
    aligned_golden = aligned_golden.iloc[WARMUP_PERIOD:]
    aligned_calculated = aligned_calculated.iloc[WARMUP_PERIOD:]

    assert not aligned_golden.empty, f"No overlapping data for {our_name}"
    assert not aligned_calculated.empty, f"No overlapping data for {our_name}"

    tolerance = TOLERANCES.get(our_name, {"rtol": 1e-5, "atol": 1e-8})
    assert np.allclose(
        aligned_golden, aligned_calculated, **tolerance
    ), f"Indicator '{our_name}' failed validation against TradingView data."


def test_resampling_1min_to_1h_matches_golden_data(golden_data_1h):
    # Validates: [DH-2.5]
    """
    Ensures that resampling 1-minute data to a 1-hour timeframe produces
    OHLCV data that is identical to the golden 1-hour dataset.
    """
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
        rtol=1e-2  # Allow for 1% difference in volume
    ), "Resampled volume does not match golden data within tolerance."
