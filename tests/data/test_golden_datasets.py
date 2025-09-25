from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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

SAMPLE_FILE = (
    Path(__file__).parent.parent.parent
    / "data/samples/tradingview_oanda_eurusd_1h_sample.csv"
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


@pytest.fixture(scope="module")
def golden_data():
    """Loads and prepares the golden dataset from TradingView."""
    df = pd.read_csv(SAMPLE_FILE)
    # The loader is strict; we manually normalize for this test case.
    df = df.rename(columns={"time": "timestamp", "Volume": "volume"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    return df


@pytest.fixture(scope="module")
def calculated_data(golden_data):
    """Calculates indicators using our platform's code."""
    feature_specs = [
        {"name": our_name, "type": type, "params": params}
        for our_name, _, type, params in INDICATOR_TEST_CASES
        if type != "BB"  # Handle BB separately
    ]
    # Add a single spec for Bollinger Bands
    feature_specs.append(
        {"name": "BB", "type": "BB", "params": {"length": 20, "ndev": 2.0}}
    )

    # Rename BB columns to match our test cases
    calculated_df = compute_features(golden_data, feature_specs).rename(
        columns={
            "BB_middle": "BB_MIDDLE",
            "BB_upper": "BB_UPPER",
            "BB_lower": "BB_LOWER",
        }
    )
    return calculated_df


@pytest.mark.parametrize("our_name, tradingview_name, _, __", INDICATOR_TEST_CASES)
def test_indicator_matches_tradingview(
    golden_data,
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
    # Extract the series to compare, dropping initial NaNs from both
    golden_series = golden_data[tradingview_name].dropna()
    calculated_series = calculated_data[our_name].dropna()

    # Align the series by index, taking the intersection of dates
    aligned_golden, aligned_calculated = golden_series.align(
        calculated_series, join="inner"
    )

    # Skip the warm-up period where calculations might differ
    aligned_golden = aligned_golden.iloc[WARMUP_PERIOD:]
    aligned_calculated = aligned_calculated.iloc[WARMUP_PERIOD:]

    # Check that we have data to compare
    assert not aligned_golden.empty, f"No overlapping data for {our_name}"
    assert not aligned_calculated.empty, f"No overlapping data for {our_name}"

    # Get indicator-specific tolerance or use a strict default
    tolerance = TOLERANCES.get(our_name, {"rtol": 1e-5, "atol": 1e-8})

    # Compare the values, allowing for a small tolerance
    assert np.allclose(
        aligned_golden, aligned_calculated, **tolerance
    ), f"Indicator '{our_name}' failed validation against TradingView data."
