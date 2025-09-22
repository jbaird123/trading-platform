from __future__ import annotations

import pandas as pd
from trading_platform.strategy.pandas_ta_adapter import bbands, ema, macd, rsi, sma


def test_sma():
    """Test the SMA adapter function."""
    close = pd.Series([1, 2, 3, 4, 5])
    result = sma(close=close, length=3)
    expected = pd.Series([None, None, 2.0, 3.0, 4.0])
    pd.testing.assert_series_equal(result, expected, check_names=False)


def test_ema():
    """Test the EMA adapter function."""
    close = pd.Series([1, 2, 3, 4, 5])
    result = ema(close=close, length=3)
    expected = pd.Series([None, None, 2.0, 3.0, 4.0])
    pd.testing.assert_series_equal(result, expected, check_names=False)


def test_macd():
    """Test the MACD adapter function."""
    close = pd.Series([i for i in range(1, 41)])
    result = macd(close=close, fast=12, slow=26, signal=9)
    assert isinstance(result, pd.DataFrame)
    assert "macd" in result.columns
    assert "macd_diff" in result.columns
    assert "macd_signal" in result.columns


def test_rsi():
    """Test the RSI adapter function."""
    close = pd.Series([i for i in range(1, 21)])
    result = rsi(close=close, length=14)
    assert isinstance(result, pd.Series)


def test_bbands():
    """Test the Bollinger Bands adapter function."""
    close = pd.Series([i for i in range(1, 21)])
    result = bbands(close=close, length=5, std=2.0)
    print(result.columns)
    assert isinstance(result, pd.DataFrame)
    assert "bb_lower" in result.columns
    assert "bb_middle" in result.columns
    assert "bb_upper" in result.columns
