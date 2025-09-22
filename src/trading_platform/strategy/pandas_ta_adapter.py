from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def sma(close: pd.Series, length: int) -> pd.Series:
    """Calculate Simple Moving Average (SMA)"""
    result = ta.sma(close=close, length=length)
    return result.rename(f"SMA_{length}")


def ema(close: pd.Series, length: int) -> pd.Series:
    """Calculate Exponential Moving Average (EMA)"""
    result = ta.ema(close=close, length=length)
    return result.rename(f"EMA_{length}")


def wma(close: pd.Series, length: int) -> pd.Series:
    """Calculate Weighted Moving Average (WMA)"""
    result = ta.wma(close=close, length=length)
    return result.rename(f"WMA_{length}")


def macd(close: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """Calculate Moving Average Convergence Divergence (MACD)"""
    result = ta.macd(close=close, fast=fast, slow=slow, signal=signal)
    result = result.rename(
        columns={
            f"MACD_{fast}_{slow}_{signal}": "macd",
            f"MACDh_{fast}_{slow}_{signal}": "macd_diff",
            f"MACDs_{fast}_{slow}_{signal}": "macd_signal",
        }
    )
    return result


def psar(high: pd.Series, low: pd.Series, step: float, max_step: float) -> pd.DataFrame:
    """Calculate Parabolic SAR (PSAR)"""
    result = ta.psar(high=high, low=low, af0=step, af=max_step)
    # pandas-ta psar returns a dataframe with PSARl (long), PSARs (short), PSARaf, PSARr
    # The old 'ta' library returns a single series.
    # We need to figure out how to combine these into a single series.
    # For now, we will return the dataframe as is and let the caller handle it.
    return result


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.DataFrame:
    """Calculate Average Directional Index (ADX)"""
    result = ta.adx(high=high, low=low, close=close, length=length)
    result = result.rename(
        columns={
            f"ADX_{length}": "adx",
            f"DMP_{length}": "adx_pos",
            f"DMN_{length}": "adx_neg",
        }
    )
    return result


def rsi(close: pd.Series, length: int) -> pd.Series:
    """Calculate Relative Strength Index (RSI)"""
    result = ta.rsi(close=close, length=length)
    return result.rename(f"RSI_{length}")


def stoch(
    high: pd.Series, low: pd.Series, close: pd.Series, k: int, d: int
) -> pd.DataFrame:
    """Calculate Stochastic Oscillator"""
    result = ta.stoch(high=high, low=low, close=close, k=k, d=d)
    result = result.rename(
        columns={
            f"STOCHk_{k}_{d}_3": "stoch_k",
            f"STOCHd_{k}_{d}_3": "stoch_d",
        }
    )
    return result


def cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Calculate Commodity Channel Index (CCI)"""
    result = ta.cci(high=high, low=low, close=close, length=length)
    return result.rename(f"CCI_{length}")


def roc(close: pd.Series, length: int) -> pd.Series:
    """Calculate Rate of Change (ROC)"""
    result = ta.roc(close=close, length=length)
    return result.rename(f"ROC_{length}")


def bbands(close: pd.Series, length: int, std: float) -> pd.DataFrame:
    """Calculate Bollinger Bands (BB)"""
    result = ta.bbands(close=close, length=length, std=std)
    result = result.rename(
        columns={
            f"BBL_{length}_{std}_{std}": "bb_lower",
            f"BBM_{length}_{std}_{std}": "bb_middle",
            f"BBU_{length}_{std}_{std}": "bb_upper",
            f"BBB_{length}_{std}_{std}": "bb_width",
            f"BBP_{length}_{std}_{std}": "bb_percent",
        }
    )
    return result


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Calculate Average True Range (ATR)"""
    result = ta.atr(high=high, low=low, close=close, length=length)
    return result.rename(f"ATR_{length}")


def kc(
    high: pd.Series, low: pd.Series, close: pd.Series, length: int, mult: float
) -> pd.DataFrame:
    """Calculate Keltner Channels (KC)"""
    result = ta.kc(high=high, low=low, close=close, length=length, scalar=mult)
    result = result.rename(
        columns={
            f"KCL_{length}_{mult}": "kc_lower",
            f"KCM_{length}_{mult}": "kc_middle",
            f"KCU_{length}_{mult}": "kc_upper",
        }
    )
    return result


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (OBV)"""
    result = ta.obv(close=close, volume=volume)
    return result.rename("OBV")


def cmf(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int
) -> pd.Series:
    """Calculate Chaikin Money Flow (CMF)"""
    result = ta.cmf(high=high, low=low, close=close, volume=volume, length=length)
    return result.rename(f"CMF_{length}")


def vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int
) -> pd.Series:
    """Calculate Volume Weighted Average Price (VWAP)"""
    result = ta.vwap(high=high, low=low, close=close, volume=volume, length=length)
    return result.rename(f"VWAP_{length}")
