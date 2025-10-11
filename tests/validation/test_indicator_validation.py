"""Comprehensive indicator validation against TradingView batch exports.

This test suite validates all 32 indicators from the 9-batch TradingView export
against our platform's indicator calculations.

Run with: pytest -m validation tests/validation/test_indicator_validation.py -v
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from trading_platform.strategy.features import compute_features

# Test data location (DVC-tracked)
BATCH_DATA_DIR = (
    Path(__file__).parent.parent.parent / "data/dvc/golden/indicators/comprehensive"
)


# Define all 32 indicators with their batch source and TradingView column names
# Format: (our_name, tradingview_column, batch_file, feature_type, params)
# Note: TradingView column names are normalized to lowercase when loading CSVs
COMPREHENSIVE_INDICATOR_TEST_CASES = [
    # Batch 1: Moving Averages (6 indicators)
    # Headers: time,open,high,low,close,SMA 20,EMA 20,WMA 20,RSI 14,ATR 14,PSAR
    # Platform generates: SMA, EMA, WMA, RSI, ATR, PSAR (no suffix)
    ("SMA", "sma 20", "batch1", "SMA", {"length": 20}),
    ("EMA", "ema 20", "batch1", "EMA", {"length": 20}),
    ("WMA", "wma 20", "batch1", "WMA", {"length": 20}),
    ("RSI", "rsi 14", "batch1", "RSI", {"length": 14}),
    ("ATR", "atr 14", "batch1", "ATR", {"length": 14}),
    ("PSAR", "psar", "batch1", "PSAR", {"af0": 0.02, "af": 0.02, "max_af": 0.2}),
    # Batch 2: Oscillators (8 indicators)
    # Headers: time,open,high,low,close,MACD,Signal,Histogram,Stoch K,Stoch D,CCI 20,ROC 12,Choppiness
    # Platform generates: MACD_macd, MACD_signal, MACD_diff, Stoch, Stoch_signal, CCI, ROC, Choppiness
    ("MACD_macd", "macd", "batch2", "MACD", {"fast": 12, "slow": 26, "signal": 9}),
    ("MACD_signal", "signal", "batch2", "MACD", {"fast": 12, "slow": 26, "signal": 9}),
    (
        "MACD_diff",
        "histogram",
        "batch2",
        "MACD",
        {"fast": 12, "slow": 26, "signal": 9},
    ),
    ("Stoch", "stoch k", "batch2", "STOCH", {"k": 14, "d": 3, "smooth_k": 3}),
    ("Stoch_signal", "stoch d", "batch2", "STOCH", {"k": 14, "d": 3, "smooth_k": 3}),
    ("CCI", "cci 20", "batch2", "CCI", {"length": 20}),
    ("ROC", "roc 12", "batch2", "ROC", {"length": 12}),
    ("Choppiness", "choppiness", "batch2", "CHOP", {"length": 14}),
    # Batch 3: Volume (2 indicators)
    # Headers: time,open,high,low,close,OBV,VWAP
    ("OBV", "obv", "batch3", "OBV", {}),
    ("VWAP", "vwap", "batch3", "VWAP", {}),
    # Batch 4: ADX/DMI (3 indicators)
    # Headers: time,open,high,low,close,DI+,DI-,ADX 14
    # Platform generates: DI (single column with DI+ info), need to check DI- mapping
    ("DI", "di+", "batch4", "ADX", {"length": 14}),
    ("DI", "di-", "batch4", "ADX", {"length": 14}),
    ("ADX", "adx 14", "batch4", "ADX", {"length": 14}),
    # Batch 5: Bollinger Bands (3 indicators)
    # Headers: time,open,high,low,close,BB Upper,BB Middle,BB Lower
    ("BB_upper", "bb upper", "batch5", "BB", {"length": 20, "ndev": 2.0}),
    ("BB_middle", "bb middle", "batch5", "BB", {"length": 20, "ndev": 2.0}),
    ("BB_lower", "bb lower", "batch5", "BB", {"length": 20, "ndev": 2.0}),
    # Batch 6: SuperTrend (2 indicators)
    # Headers: time,open,high,low,close,SuperTrend,ST Direction
    (
        "SuperTrend",
        "supertrend",
        "batch6",
        "SUPERTREND",
        {"length": 7, "multiplier": 3.0},
    ),
    (
        "SuperTrend_direction",
        "st direction",
        "batch6",
        "SUPERTREND",
        {"length": 7, "multiplier": 3.0},
    ),
    # Batch 7: Keltner Channels (3 indicators)
    # Headers: time,open,high,low,close,KC Upper,KC Middle,KC Lower
    (
        "KC_upper",
        "kc upper",
        "batch7",
        "KC",
        {"length": 20, "atr_length": 20, "multiplier": 2.0},
    ),
    (
        "KC_middle",
        "kc middle",
        "batch7",
        "KC",
        {"length": 20, "atr_length": 20, "multiplier": 2.0},
    ),
    (
        "KC_lower",
        "kc lower",
        "batch7",
        "KC",
        {"length": 20, "atr_length": 20, "multiplier": 2.0},
    ),
    # Batch 8: Ichimoku (5 indicators)
    # Headers: time,open,high,low,close,Ich Conversion,Ich Base,Ich Span A,Ich Span B,Ich Lagging
    # Platform generates: Ichimoku_tenkan, Ichimoku_kijun, Ichimoku_senkou_a, Ichimoku_senkou_b, Ichimoku_chikou
    (
        "Ichimoku_tenkan",
        "ich conversion",
        "batch8",
        "ICHIMOKU",
        {"tenkan": 9, "kijun": 26, "senkou": 52},
    ),
    (
        "Ichimoku_kijun",
        "ich base",
        "batch8",
        "ICHIMOKU",
        {"tenkan": 9, "kijun": 26, "senkou": 52},
    ),
    (
        "Ichimoku_senkou_a",
        "ich span a",
        "batch8",
        "ICHIMOKU",
        {"tenkan": 9, "kijun": 26, "senkou": 52},
    ),
    (
        "Ichimoku_senkou_b",
        "ich span b",
        "batch8",
        "ICHIMOKU",
        {"tenkan": 9, "kijun": 26, "senkou": 52},
    ),
    (
        "Ichimoku_chikou",
        "ich lagging",
        "batch8",
        "ICHIMOKU",
        {"tenkan": 9, "kijun": 26, "senkou": 52},
    ),
    # Batch 9: CMF (1 indicator)
    # Headers: time,open,high,low,close,CMF 20
    ("CMF", "cmf 20", "batch9", "CMF", {"length": 20}),
]


# Warmup period - skip initial bars where indicators haven't stabilized
WARMUP_PERIOD = 100


# Tolerances for different indicator types
# Some indicators have different calculation methods between pandas-ta and TradingView
INDICATOR_TOLERANCES = {
    # Moving averages - very stable
    "SMA": {"rtol": 1e-6, "atol": 1e-8},
    "EMA": {"rtol": 1e-5, "atol": 1e-8},
    "WMA": {"rtol": 1e-5, "atol": 1e-8},
    # Oscillators - moderate differences due to smoothing
    "RSI": {"rtol": 1e-3, "atol": 1e-8},
    "MACD": {"rtol": 1e-4, "atol": 1e-8},
    "STOCH": {"rtol": 1e-3, "atol": 1e-8},
    "CCI": {"rtol": 1e-3, "atol": 1e-8},
    "ROC": {"rtol": 1e-4, "atol": 1e-8},
    # Trend indicators - can have larger differences
    "ADX": {"rtol": 1e-2, "atol": 1e-6},  # Complex multi-step calculation
    "ATR": {"rtol": 1e-3, "atol": 1e-8},
    "PSAR": {"rtol": 1.5e-2, "atol": 1e-8},  # 1.5% tolerance for SAR algorithm differences
    "SUPERTREND": {"rtol": 1e-3, "atol": 1e-8},
    # Bands/Channels - small differences in std calculation
    "BB": {"rtol": 2e-4, "atol": 1e-8},
    "KC": {"rtol": 5e-4, "atol": 1e-8},
    # Volume indicators
    "OBV": {"rtol": 1e-5, "atol": 1.0},  # Can accumulate rounding
    "CMF": {"rtol": 1e-3, "atol": 1e-8},
    "VWAP": {"rtol": 1e-5, "atol": 1e-8},
    # Complex indicators
    "ICHIMOKU": {"rtol": 1e-3, "atol": 1e-8},
    "CHOP": {"rtol": 1e-2, "atol": 1e-6},
}


def _get_tolerance_for_indicator(feature_type: str) -> dict[str, float]:
    """Get tolerance settings for an indicator type."""
    return INDICATOR_TOLERANCES.get(feature_type, {"rtol": 1e-5, "atol": 1e-8})


@pytest.fixture(scope="module")
def batch_metadata():
    """Load metadata for all batches."""
    metadata_path = BATCH_DATA_DIR / "metadata.json"
    if not metadata_path.exists():
        pytest.skip(
            f"Batch metadata not found at {metadata_path}. Run 'dvc pull' to fetch golden data."
        )

    with open(metadata_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def batch_data_cache(batch_metadata):
    """Load all batch CSV files into memory once for the test session.

    Returns a dict mapping batch_number -> DataFrame with OHLCV + indicators.
    """
    cache = {}

    for batch_info in batch_metadata["batches"]:
        batch_num = batch_info["batch_number"]
        filename = batch_info["filename"]
        filepath = BATCH_DATA_DIR / f"{filename}.dvc"

        # Check if DVC pointer exists (actual data file is managed by DVC)
        if not filepath.exists():
            pytest.skip(
                f"DVC pointer for {filename} not found. Run 'dvc pull' to fetch golden data."
            )

        # Load the actual CSV file (DVC pulls it to same location without .dvc)
        csv_path = BATCH_DATA_DIR / filename
        if not csv_path.exists():
            pytest.skip(
                f"Batch data file {filename} not found. Run 'dvc pull' to fetch golden data."
            )

        # Load and prepare the dataframe
        df = pd.read_csv(csv_path)
        df = df.rename(columns={"time": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

        # Normalize column names (TradingView uses different casing)
        df.columns = df.columns.str.lower()

        cache[f"batch{batch_num}"] = df

    return cache


@pytest.fixture(scope="module")
def platform_calculated_features(batch_data_cache):
    """Calculate all indicators using our platform on the batch1 OHLCV data.

    We use batch1 OHLCV since all batches share the same market data.
    Returns a DataFrame with all calculated indicators.
    """
    # Get OHLCV from batch10 (which includes volume column)
    # All other batches (1-9) have same OHLC but don't include volume
    ohlcv_df = batch_data_cache["batch10"][
        ["open", "high", "low", "close", "volume"]
    ].copy()

    # Build feature specs for all 32 indicators
    # Group by unique feature type + params to avoid recalculating
    feature_specs: list[dict[str, str | dict[str, float]]] = []
    added_features: set[tuple[str, frozenset[tuple[str, float]]]] = set()

    for our_name, _, _, feature_type, params in COMPREHENSIVE_INDICATOR_TEST_CASES:
        # Create a unique key for this feature configuration
        params_typed: dict[str, float] = params  # type: ignore[assignment]
        feature_key = (feature_type, frozenset(params_typed.items()))

        if feature_key not in added_features:
            # For multi-column indicators (BB, MACD, etc), use base name
            base_name = our_name.split("_")[0] if "_" in our_name else our_name

            feature_specs.append(
                {"name": base_name, "type": feature_type, "params": params}
            )
            added_features.add(feature_key)

    # Calculate all features
    calculated_df = compute_features(ohlcv_df, feature_specs)

    return calculated_df


@pytest.mark.validation
@pytest.mark.parametrize(
    "our_name,tradingview_column,batch_file,feature_type,params",
    COMPREHENSIVE_INDICATOR_TEST_CASES,
    ids=[case[0] for case in COMPREHENSIVE_INDICATOR_TEST_CASES],
)
def test_indicator_matches_tradingview_comprehensive(
    batch_data_cache,
    platform_calculated_features,
    our_name,
    tradingview_column,
    batch_file,
    feature_type,
    params,
):
    """Validate that our platform's indicator calculation matches TradingView.

    This test compares each of the 32 indicators against the corresponding
    TradingView export from the batch files.
    """
    # Get TradingView data from the appropriate batch
    batch_df = batch_data_cache[batch_file]

    # Check if TradingView column exists in batch
    if tradingview_column.lower() not in batch_df.columns:
        pytest.fail(
            f"TradingView column '{tradingview_column}' not found in {batch_file}. "
            f"Available columns: {list(batch_df.columns)}"
        )

    tradingview_series = batch_df[tradingview_column.lower()].dropna()

    # Get our calculated data
    # Special handling for PSAR: merge PSAR_up and PSAR_down into single series
    if our_name == "PSAR":
        if "PSAR_up" in platform_calculated_features.columns and "PSAR_down" in platform_calculated_features.columns:
            # Combine PSAR_up and PSAR_down (one will be NaN at any given time)
            calculated_series = (
                platform_calculated_features["PSAR_up"]
                .fillna(platform_calculated_features["PSAR_down"])
                .dropna()
            )
        else:
            pytest.fail(
                f"PSAR requires PSAR_up and PSAR_down columns. "
                f"Available columns: {list(platform_calculated_features.columns)}"
            )
    else:
        if our_name not in platform_calculated_features.columns:
            pytest.fail(
                f"Calculated column '{our_name}' not found in platform data. "
                f"Available columns: {list(platform_calculated_features.columns)}"
            )
        calculated_series = platform_calculated_features[our_name].dropna()

    # Align the two series on timestamp
    aligned_tv, aligned_calc = tradingview_series.align(calculated_series, join="inner")

    # Skip warmup period
    aligned_tv = aligned_tv.iloc[WARMUP_PERIOD:]
    aligned_calc = aligned_calc.iloc[WARMUP_PERIOD:]

    # Ensure we have data to compare
    assert not aligned_tv.empty, f"No TradingView data for {our_name} after warmup"
    assert not aligned_calc.empty, f"No calculated data for {our_name} after warmup"

    # Get tolerance for this indicator type
    tolerance = _get_tolerance_for_indicator(feature_type)
    rtol = tolerance["rtol"]
    atol = tolerance["atol"]

    # Compare values
    close_match = np.allclose(
        aligned_tv, aligned_calc, rtol=rtol, atol=atol, equal_nan=True
    )

    if not close_match:
        # Calculate statistics for debugging
        diff = aligned_calc - aligned_tv
        abs_diff = np.abs(diff)
        rel_diff = abs_diff / np.abs(aligned_tv).replace(0, np.nan)

        max_abs_diff = abs_diff.max()
        max_rel_diff = rel_diff.max()
        mean_abs_diff = abs_diff.mean()

        pytest.fail(
            f"Indicator '{our_name}' validation failed:\n"
            f"  Feature Type: {feature_type}\n"
            f"  Tolerance: rtol={rtol}, atol={atol}\n"
            f"  Max absolute difference: {max_abs_diff:.6e}\n"
            f"  Max relative difference: {max_rel_diff:.6e}\n"
            f"  Mean absolute difference: {mean_abs_diff:.6e}\n"
            f"  Data points compared: {len(aligned_tv)}\n"
            f"  Consider adjusting tolerance if difference is due to library implementation."
        )


@pytest.mark.validation
def test_all_batches_have_same_ohlcv(batch_data_cache):
    """Verify that all 9 batches have identical OHLCV data.

    This is a sanity check to ensure the batch exports are consistent.
    """
    batch_keys = [f"batch{i}" for i in range(1, 10)]

    # Get OHLCV from batch1 as reference
    reference_ohlcv = batch_data_cache["batch1"][
        ["open", "high", "low", "close", "volume"]
    ]

    for batch_key in batch_keys[1:]:  # Skip batch1 since it's the reference
        batch_ohlcv = batch_data_cache[batch_key][
            ["open", "high", "low", "close", "volume"]
        ]

        # Align on timestamp
        aligned_ref, aligned_batch = reference_ohlcv.align(batch_ohlcv, join="inner")

        # Check OHLC are exactly equal
        assert aligned_ref[["open", "high", "low", "close"]].equals(
            aligned_batch[["open", "high", "low", "close"]]
        ), f"OHLC data in {batch_key} doesn't match batch1"

        # Check volume with small tolerance
        assert np.allclose(
            aligned_ref["volume"], aligned_batch["volume"], rtol=1e-6
        ), f"Volume data in {batch_key} doesn't match batch1"


@pytest.mark.validation
def test_metadata_describes_all_test_cases(batch_metadata):
    """Verify that metadata.json has proper structure and documents indicators."""

    # Verify metadata has expected structure
    assert "batches" in batch_metadata
    assert "total_indicators" in batch_metadata
    assert "batches_exported" in batch_metadata

    # Get all indicators from metadata
    metadata_indicators = set()
    for batch in batch_metadata["batches"]:
        for indicator in batch["indicators"]:
            metadata_indicators.add(indicator["name"])

    # Get all test cases
    test_case_indicators = set()
    for our_name, _, _, feature_type, params in COMPREHENSIVE_INDICATOR_TEST_CASES:
        test_case_indicators.add(our_name)

    # Log statistics for awareness
    print("\nIndicator validation coverage:")
    print(f"  Test cases: {len(COMPREHENSIVE_INDICATOR_TEST_CASES)} indicators")
    print(f"  Metadata entries: {len(metadata_indicators)} indicators")
    print(
        f"  Metadata total_indicators field: {batch_metadata.get('total_indicators', 'N/A')}"
    )
    print(f"  Batches exported: {batch_metadata.get('batches_exported', 'N/A')}")

    # Verify we have a reasonable number of indicators
    assert len(metadata_indicators) >= 30, "Expected at least 30 indicators in metadata"
    assert (
        len(COMPREHENSIVE_INDICATOR_TEST_CASES) == 33
    ), "Expected exactly 33 test cases"
