"""
Tests for look-ahead bias detection in indicators.

This test suite validates that all custom indicators are free
from look-ahead bias by comparing vectorized vs bar-by-bar computation.
"""

import numpy as np
import pandas as pd
import pytest
from trading_platform.strategy.features import (
    adx,
    atr,
    ema,
    ema_slope,
    rsi,
)
from trading_platform.strategy.indicator_helpers import find_swing_points
from trading_platform.strategy.safe_indicators import (
    donchian_channels,
    hhv,
    llv,
    safe_rolling_max,
    safe_rolling_mean,
    safe_rolling_min,
)

from tests.utils.bias_detection import (
    BiasTestResult,
    detect_lookahead_bias,
    detect_lookahead_bias_multicolumn,
)


@pytest.fixture
def test_ohlcv_data() -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    n = 500

    # Generate price data with realistic properties
    base_price = 100.0
    returns = np.random.normal(0, 0.02, n)
    close = base_price * np.exp(np.cumsum(returns))

    # Generate OHLC with realistic relationships
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n)))
    open_ = close * (1 + np.random.normal(0, 0.005, n))

    # Volume
    volume = np.random.uniform(1000, 10000, n)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h"),
    )

    return df


# ============================================================
# Safe Indicator Helpers Tests
# ============================================================


def test_safe_rolling_max_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """safe_rolling_max should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return safe_rolling_max(df["close"], window=20)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_safe_rolling_min_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """safe_rolling_min should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return safe_rolling_min(df["close"], window=20)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_safe_rolling_mean_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """safe_rolling_mean should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return safe_rolling_mean(df["close"], window=20)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_hhv_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """HHV (highest high value) should have no bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return hhv(df["high"], length=50)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_llv_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """LLV (lowest low value) should have no bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return llv(df["low"], length=50)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_donchian_channels_no_bias(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """Donchian Channels should have no bias."""

    def indicator_upper(df: pd.DataFrame) -> pd.Series:
        dc = donchian_channels(df["high"], df["low"], length=20)
        return dc["upper"]

    def indicator_lower(df: pd.DataFrame) -> pd.Series:
        dc = donchian_channels(df["high"], df["low"], length=20)
        return dc["lower"]

    result_upper = detect_lookahead_bias(indicator_upper, test_ohlcv_data)
    result_lower = detect_lookahead_bias(indicator_lower, test_ohlcv_data)

    assert not result_upper.has_bias, f"Upper band: {result_upper}"
    assert not result_lower.has_bias, f"Lower band: {result_lower}"


# ============================================================
# Core Indicator Tests (from features.py)
# ============================================================


def test_ema_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """EMA should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return ema(df["close"], length=20)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_ema_slope_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """EMA slope should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return ema_slope(df["close"], length=20, slope_period=1)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_rsi_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """RSI should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return rsi(df["close"], length=14)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_atr_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """ATR should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return atr(df, length=14)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


def test_adx_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """ADX should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        adx_df = adx(df, length=14)
        return adx_df["ADX"]  # Return just the ADX column

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)


# ============================================================
# Custom Indicators Tests
# ============================================================


def test_swing_high_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """
    Swing high detection should have no look-ahead bias.

    This test validates the fix for the swing point indicator.
    Previously used center=True which caused +1,446% bias.
    After fix, should show no bias.
    """

    def indicator(df: pd.DataFrame) -> pd.DataFrame:
        return find_swing_points(df, left_bars=10, right_bars=10)

    result = detect_lookahead_bias_multicolumn(indicator, test_ohlcv_data, "swing_high")

    assert not result.has_bias, str(result)


def test_swing_low_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """
    Swing low detection should have no look-ahead bias.

    Validates the same fix as swing_high.
    """

    def indicator(df: pd.DataFrame) -> pd.DataFrame:
        return find_swing_points(df, left_bars=10, right_bars=10)

    result = detect_lookahead_bias_multicolumn(indicator, test_ohlcv_data, "swing_low")

    assert not result.has_bias, str(result)


def test_swing_points_with_different_params_no_bias(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """Test swing points with various parameter combinations."""
    param_combinations = [
        (5, 5),
        (10, 10),
        (15, 15),
        (10, 5),  # Asymmetric
        (5, 10),  # Asymmetric
    ]

    for left, right in param_combinations:

        def indicator(df: pd.DataFrame) -> pd.DataFrame:
            return find_swing_points(df, left_bars=left, right_bars=right)

        result_high = detect_lookahead_bias_multicolumn(
            indicator, test_ohlcv_data, "swing_high"
        )
        result_low = detect_lookahead_bias_multicolumn(
            indicator, test_ohlcv_data, "swing_low"
        )

        assert (
            not result_high.has_bias
        ), f"Swing high (left={left}, right={right}): {result_high}"
        assert (
            not result_low.has_bias
        ), f"Swing low (left={left}, right={right}): {result_low}"


# ============================================================
# Intentional Bias Detection Tests (Negative Tests)
# ============================================================


def test_detects_bias_in_centered_rolling_max(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """
    Verify that bias detection catches center=True rolling windows.

    This is a negative test - we expect bias to be detected.
    """

    def biased_indicator(df: pd.DataFrame) -> pd.Series:
        # INTENTIONALLY BIASED - uses center=True
        return df["close"].rolling(window=20, center=True).max()

    result = detect_lookahead_bias(biased_indicator, test_ohlcv_data)

    # This SHOULD detect bias
    assert result.has_bias, "Bias detection failed! Should detect center=True bias."
    assert result.max_difference > 0.0


def test_detects_bias_in_negative_shift(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """
    Verify that bias detection catches negative shifts (look ahead).

    Negative shift looks into the future.
    """

    def biased_indicator(df: pd.DataFrame) -> pd.Series:
        # INTENTIONALLY BIASED - shift(-1) looks ahead 1 bar
        return df["close"].shift(-1)

    result = detect_lookahead_bias(biased_indicator, test_ohlcv_data)

    # This SHOULD detect bias
    assert result.has_bias, "Bias detection failed! Should detect negative shift."


# ============================================================
# Edge Cases
# ============================================================


def test_bias_detection_with_short_data() -> None:
    """Test behavior with data shorter than min_warmup."""
    short_data = pd.DataFrame(
        {"close": [1, 2, 3, 4, 5]},
        index=pd.date_range("2020-01-01", periods=5, freq="1h"),
    )

    def simple_indicator(df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(3).mean()

    # Should raise error due to insufficient data
    with pytest.raises(ValueError, match="Test data too short"):
        detect_lookahead_bias(simple_indicator, short_data, min_warmup=50)


def test_bias_detection_with_all_nan_indicator(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """Test behavior when indicator returns all NaN."""

    def all_nan_indicator(df: pd.DataFrame) -> pd.Series:
        return pd.Series([np.nan] * len(df), index=df.index)

    result = detect_lookahead_bias(all_nan_indicator, test_ohlcv_data)

    # Should not detect bias (no valid bars to compare)
    assert not result.has_bias
    assert result.bars_tested == 0


def test_bias_result_string_representation() -> None:
    """Test BiasTestResult string formatting."""
    # No bias case
    result_clean = BiasTestResult(
        has_bias=False,
        max_difference=0.0,
        biased_bars=[],
        total_bars=100,
        bars_tested=80,
    )
    assert "✓ No bias detected" in str(result_clean)
    assert "80/100" in str(result_clean)

    # Bias detected case
    result_biased = BiasTestResult(
        has_bias=True,
        max_difference=0.5,
        biased_bars=[
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-01-02"),
        ],
        total_bars=100,
        bars_tested=80,
    )
    assert "✗ BIAS DETECTED!" in str(result_biased)
    assert "0.5" in str(result_biased)
    assert "2 (" in str(result_biased)  # 2 biased bars


def test_bias_percentage_calculation() -> None:
    """Test bias percentage calculation."""
    result = BiasTestResult(
        has_bias=True,
        max_difference=0.1,
        biased_bars=[pd.Timestamp("2020-01-01")] * 10,  # 10 bars
        total_bars=100,
        bars_tested=50,  # 10/50 = 20%
    )

    assert result.bias_percentage == pytest.approx(20.0)


# ============================================================
# Performance Test
# ============================================================


def test_bias_detection_performance(
    test_ohlcv_data: pd.DataFrame,
) -> None:
    """
    Bias detection should complete in reasonable time.

    Note: This is intentionally slow (bar-by-bar computation).
    Only used during testing/validation, not production.
    """
    import time

    def indicator(df: pd.DataFrame) -> pd.Series:
        return ema(df["close"], length=20)

    start = time.time()
    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    elapsed = time.time() - start

    # Should complete in < 10 seconds for 500 bars
    assert elapsed < 10.0, f"Too slow: {elapsed:.2f}s"
    assert not result.has_bias
