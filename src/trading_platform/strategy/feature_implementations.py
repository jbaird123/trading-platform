"""
Indicator implementation functions for the unified registry.

All functions follow the standard interface:
    compute_X(df, params, source, source_ref) -> Series | dict[str, Series]

Args:
    df: OHLCV DataFrame with columns: open, high, low, close, volume
    params: Resolved parameters dict (already substituted ${vars})
    source: Price source (open/high/low/close/hl2/ohlc4)
    source_ref: Optional reference to another column in df

Returns:
    - Single pd.Series for single-output indicators (EMA, RSI, ATR)
    - Dict[str, pd.Series] for multi-output indicators (BB, MACD, ADX)
      Keys are column suffixes: {"upper": series, "lower": series}
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

# Import TA-Lib for candlestick patterns
import talib

# Import from ta library (stable, production-ready)
from ta.momentum import ROCIndicator, RSIIndicator, StochasticOscillator
from ta.trend import (
    MACD as MACDIndicator,
)
from ta.trend import (
    ADXIndicator,
    CCIIndicator,
    EMAIndicator,
    IchimokuIndicator,
    PSARIndicator,
)
from ta.volatility import (
    AverageTrueRange,
    BollingerBands,
    DonchianChannel,
    KeltnerChannel,
)
from ta.volume import (
    ChaikinMoneyFlowIndicator,
    OnBalanceVolumeIndicator,
    VolumeWeightedAveragePrice,
)

from trading_platform.strategy.custom_indicators import find_swing_points


def _price_series(df: pd.DataFrame, source: str) -> pd.Series:
    """Convert source string to price series."""
    if source in ("open", "high", "low", "close"):
        return pd.Series(df[source], dtype="float64")
    if source == "hl2":
        return (pd.Series(df["high"]) + pd.Series(df["low"])) / 2.0
    if source == "ohlc4":
        return (
            pd.Series(df["open"])
            + pd.Series(df["high"])
            + pd.Series(df["low"])
            + pd.Series(df["close"])
        ) / 4.0
    return pd.Series(df["close"], dtype="float64")


def _empty_series(df: pd.DataFrame) -> pd.Series:
    """Create empty NaN series with same index as df."""
    return pd.Series([np.nan] * len(df), index=df.index, dtype="float64")


# ==============================================================================
# Helper Functions (reused by implementations)
# ==============================================================================


def ema(series: pd.Series, length: int) -> pd.Series:
    """Calculate EMA using ta library."""
    n = len(series)
    length = max(1, min(int(length), n))
    try:
        indicator = EMAIndicator(close=series, window=length, fillna=False)
        return indicator.ema_indicator()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return pd.Series([np.nan] * n, index=series.index, dtype="float64")


def rsi(series: pd.Series, length: int) -> pd.Series:
    """Calculate RSI using ta library."""
    length = max(1, int(length))
    try:
        indicator = RSIIndicator(close=series, window=length, fillna=False)
        return indicator.rsi()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return pd.Series([np.nan] * len(series), index=series.index, dtype="float64")


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    """Calculate ATR using ta library."""
    n = len(df)
    length = max(1, min(int(length), n))
    try:
        indicator = AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=False,
        )
        return indicator.average_true_range()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return pd.Series([np.nan] * n, index=df.index, dtype="float64")


def adx(df: pd.DataFrame, length: int) -> pd.DataFrame:
    """Calculate ADX using ta library, return DataFrame with ADX, DI+, DI- columns."""
    n = len(df)
    if n < 3:
        empty_df = pd.DataFrame(
            {"ADX": [np.nan] * n, "DI+": [np.nan] * n, "DI-": [np.nan] * n},
            index=df.index,
        )
        return empty_df
    length = max(3, min(int(length), n))
    try:
        indicator = ADXIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=False,
        )
        renamed = pd.DataFrame(
            {
                "ADX": indicator.adx(),
                "DI+": indicator.adx_pos(),
                "DI-": indicator.adx_neg(),
            },
            index=df.index,
        )
        return renamed
    except (IndexError, ValueError, TypeError):
        empty_df = pd.DataFrame(
            {"ADX": [np.nan] * n, "DI+": [np.nan] * n, "DI-": [np.nan] * n},
            index=df.index,
        )
        return empty_df


def hhv(series: pd.Series, length: int) -> pd.Series:
    """Highest High Value over length periods."""
    if length <= 0:
        raise ValueError(f"Length must be positive, got {length}")
    length = int(length)
    return series.rolling(window=length, min_periods=1).max()


def llv(series: pd.Series, length: int) -> pd.Series:
    """Lowest Low Value over length periods."""
    if length <= 0:
        raise ValueError(f"Length must be positive, got {length}")
    length = int(length)
    return series.rolling(window=length, min_periods=1).min()


# ==============================================================================
# Batch 1: Simple Single-Output Indicators
# ==============================================================================


def compute_ema(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Exponential Moving Average."""
    length = int(params.get("length", 14))
    return ema(_price_series(df, source), length)


def compute_sma(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Simple Moving Average."""
    length = int(params.get("length", 14))
    series = _price_series(df, source)
    return series.rolling(window=length, min_periods=1).mean()


def compute_wma(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Weighted Moving Average."""
    length = int(params.get("length", 14))
    series = _price_series(df, source)
    weights = np.arange(1, length + 1)
    return series.rolling(window=length, min_periods=1).apply(
        lambda x: np.average(x, weights=weights[: len(x)]) if len(x) > 0 else np.nan,
        raw=True,
    )


def compute_rsi(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Relative Strength Index."""
    length = int(params.get("length", 14))
    return rsi(_price_series(df, source), length)


def compute_atr(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Average True Range."""
    length = int(params.get("length", 14))
    return atr(df, length)


def compute_roc(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Rate of Change."""
    length = int(params.get("length", 12))
    try:
        indicator = ROCIndicator(
            close=_price_series(df, source), window=length, fillna=False
        )
        return indicator.roc()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


# ==============================================================================
# Batch 2: Rolling Window Indicators
# ==============================================================================


def compute_hhv(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "high",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Highest High Value."""
    series_in = (
        pd.Series(df[source_ref], dtype="float64")
        if source_ref
        else _price_series(df, source)
    )
    return hhv(series_in, int(params.get("length", 20)))


def compute_llv(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "low",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Lowest Low Value."""
    series_in = (
        pd.Series(df[source_ref], dtype="float64")
        if source_ref
        else _price_series(df, source)
    )
    return llv(series_in, int(params.get("length", 20)))


def compute_ema_slope(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute EMA Slope (rate of change)."""
    length = int(params.get("length", 14))
    slope_period = int(params.get("slope_period", 1))
    ema_values = ema(_price_series(df, source), length)
    slope = ema_values.diff(periods=slope_period)
    return slope


def compute_bb_width(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Bollinger Bands Width."""
    length = int(params.get("length", 20))
    ndev = float(params.get("ndev", 2.0))
    try:
        indicator = BollingerBands(
            close=_price_series(df, source),
            window=length,
            window_dev=ndev,
            fillna=False,
        )
        hband = indicator.bollinger_hband()
        lband = indicator.bollinger_lband()
        mavg = indicator.bollinger_mavg().replace(0, 1.0)
        return cast(pd.Series, (hband - lband) / mavg)
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


# ==============================================================================
# Batch 3: Multi-Output Indicators
# ==============================================================================


def compute_bb(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Bollinger Bands (upper, lower, middle)."""
    length = int(params.get("length", 20))
    ndev = float(params.get("ndev", 2.0))
    try:
        indicator = BollingerBands(
            close=_price_series(df, source),
            window=length,
            window_dev=ndev,
            fillna=False,
        )
        return {
            "upper": indicator.bollinger_hband(),
            "lower": indicator.bollinger_lband(),
            "middle": indicator.bollinger_mavg(),
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"upper": empty, "lower": empty, "middle": empty}


def compute_macd(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute MACD (macd, signal, diff)."""
    slow = int(params.get("slow", 26))
    fast = int(params.get("fast", 12))
    signal = int(params.get("signal", 9))
    try:
        indicator = MACDIndicator(
            close=_price_series(df, source),
            window_slow=slow,
            window_fast=fast,
            window_sign=signal,
            fillna=False,
        )
        return {
            "macd": indicator.macd(),
            "signal": indicator.macd_signal(),
            "diff": indicator.macd_diff(),
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"macd": empty, "signal": empty, "diff": empty}


def compute_dc(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Donchian Channels (upper, lower)."""
    length = int(params.get("length", 20))
    try:
        indicator = DonchianChannel(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=False,
        )
        return {
            "upper": indicator.donchian_channel_hband(),
            "lower": indicator.donchian_channel_lband(),
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"upper": empty, "lower": empty}


# ==============================================================================
# Batch 4: Complex Indicators
# ==============================================================================


def compute_adx(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute ADX (ADX, DI+, DI-)."""
    adx_df = adx(df, int(params.get("length", 14)))
    return {
        "ADX": adx_df["ADX"],
        "DI+": adx_df["DI+"],
        "DI-": adx_df["DI-"],
    }


def compute_psar(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Parabolic SAR."""
    step = float(params.get("step", 0.02))
    max_step = float(params.get("max", 0.2))
    try:
        indicator = PSARIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            step=step,
            max_step=max_step,
            fillna=False,
        )
        psar_val = indicator.psar()
        psar_up = indicator.psar_up()
        psar_down = indicator.psar_down()
        return {
            "": psar_val,  # Main value, no suffix
            "up": psar_up,
            "down": psar_down,
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"": empty, "up": empty, "down": empty}


def compute_stoch(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Stochastic Oscillator."""
    k_period = int(params.get("k", 14))
    d_period = int(params.get("d", 3))
    # Note: smooth_k is not used by ta library's StochasticOscillator
    # but kept in params for backwards compatibility
    try:
        indicator = StochasticOscillator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=k_period,
            smooth_window=d_period,
            fillna=False,
        )
        return {
            "": indicator.stoch(),  # %K (main value, no suffix)
            "signal": indicator.stoch_signal(),  # %D
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"": empty, "signal": empty}


def compute_kc(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Keltner Channels."""
    length = int(params.get("length", 20))
    # Note: mult parameter not used by ta library's KeltnerChannel
    # but kept in params for backwards compatibility
    try:
        indicator = KeltnerChannel(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            window_atr=length,
            fillna=False,
            original_version=False,
        )
        return {
            "upper": indicator.keltner_channel_hband(),
            "lower": indicator.keltner_channel_lband(),
            "middle": indicator.keltner_channel_mband(),
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {"upper": empty, "lower": empty, "middle": empty}


# ==============================================================================
# Batch 5: Volume/Advanced
# ==============================================================================


def compute_obv(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute On-Balance Volume."""
    try:
        indicator = OnBalanceVolumeIndicator(
            close=_price_series(df, source), volume=df["volume"], fillna=False
        )
        return indicator.on_balance_volume()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


def compute_cmf(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Chaikin Money Flow."""
    length = int(params.get("length", 20))
    try:
        indicator = ChaikinMoneyFlowIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df["volume"],
            window=length,
            fillna=False,
        )
        return indicator.chaikin_money_flow()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


def compute_vwap(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Volume Weighted Average Price."""
    try:
        indicator = VolumeWeightedAveragePrice(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df["volume"],
            fillna=False,
        )
        return indicator.volume_weighted_average_price()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


def compute_chop(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Choppiness Index.

    TODO: CHOP is not available in the stable ta library.
    Need custom implementation or TA-Lib alternative.
    Currently returns empty series to prevent import errors.
    """
    # Temporary placeholder - CHOP not in stable ta library
    return _empty_series(df)


def compute_cci(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Commodity Channel Index."""
    length = int(params.get("length", 20))
    try:
        indicator = CCIIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=False,
        )
        return indicator.cci()  # type: ignore[no-any-return]
    except (IndexError, ValueError, TypeError):
        return _empty_series(df)


# ==============================================================================
# Batch 6: Very Complex
# ==============================================================================


def compute_ichimoku(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute Ichimoku Cloud."""
    tenkan = int(params.get("tenkan", 9))
    kijun = int(params.get("kijun", 26))
    senkou = int(params.get("senkou", 52))
    try:
        indicator = IchimokuIndicator(
            high=df["high"],
            low=df["low"],
            window1=tenkan,
            window2=kijun,
            window3=senkou,
            fillna=False,
        )
        return {
            "tenkan": indicator.ichimoku_conversion_line(),
            "kijun": indicator.ichimoku_base_line(),
            "senkou_a": indicator.ichimoku_a(),
            "senkou_b": indicator.ichimoku_b(),
            "chikou": df["close"].shift(-kijun),  # Lagging span
        }
    except (IndexError, ValueError, TypeError):
        empty = _empty_series(df)
        return {
            "tenkan": empty,
            "kijun": empty,
            "senkou_a": empty,
            "senkou_b": empty,
            "chikou": empty,
        }


def compute_supertrend(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute SuperTrend.

    TODO: SUPERTREND is not available in the stable ta library.
    Need custom implementation or TA-Lib alternative.
    Currently returns empty series to prevent import errors.
    """
    # Temporary placeholder - SUPERTREND not in stable ta library
    empty = _empty_series(df)
    return {"": empty, "direction": empty, "long": empty, "short": empty}


def compute_swing_high(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Swing High points."""
    left_bars = int(params.get("left_bars", 10))
    right_bars = int(params.get("right_bars", 10))
    swings = find_swing_points(
        df,
        left_bars=left_bars,
        right_bars=right_bars,
    )
    return swings["swing_high"]


def compute_swing_low(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Swing Low points."""
    left_bars = int(params.get("left_bars", 10))
    right_bars = int(params.get("right_bars", 10))
    swings = find_swing_points(
        df,
        left_bars=left_bars,
        right_bars=right_bars,
    )
    return swings["swing_low"]


# ==============================================================================
# Batch 7: Candlestick Patterns
# ==============================================================================


def compute_cdl_doji(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Doji candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLDOJI(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_cdl_hammer(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Hammer candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLHAMMER(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_cdl_engulfing(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Engulfing candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLENGULFING(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_cdl_morningstar(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Morning Star candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLMORNINGSTAR(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_cdl_eveningstar(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Evening Star candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLEVENINGSTAR(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_cdl_harami(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Harami candlestick pattern using TA-Lib.

    Returns integer values: 0 (no pattern), 100 (bullish), -100 (bearish).
    """
    try:
        result = talib.CDLHARAMI(
            df["open"].values,
            df["high"].values,
            df["low"].values,
            df["close"].values,
        )
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


# ==============================================================================
# Batch 8: Custom/RMM
# ==============================================================================


def compute_atr_percentile(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Calculate ATR percentile rank over a lookback period."""
    atr_len = int(params.get("atr_length", 14))
    lookback = int(params.get("lookback", 20))
    atr_values = atr(df, atr_len)
    # Calculate percentile rank using rolling window
    # Count how many values in window are less than current value
    percentile = atr_values.rolling(window=lookback, min_periods=1).apply(
        lambda x: (x.iloc[-1] > x).sum() / (len(x) - 1) * 100 if len(x) > 1 else 50.0,
        raw=False,
    )
    return percentile


def compute_realized_volatility(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Calculate realized volatility as the standard deviation of returns."""
    length = int(params.get("length", 20))
    series = _price_series(df, source)
    # Calculate log returns
    log_ret = pd.Series(np.log(series / series.shift(1)), index=series.index)
    # Calculate rolling standard deviation of returns
    vol = log_ret.rolling(window=length, min_periods=1).std()
    return cast(pd.Series, vol)


def compute_volume_zscore(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Calculate volume z-score relative to rolling mean and std."""
    length = int(params.get("length", 20))
    series = pd.Series(df["volume"])
    rolling_mean = series.rolling(window=length, min_periods=1).mean()
    rolling_std = series.rolling(window=length, min_periods=1).std()
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, 1)
    z_score = (series - rolling_mean) / rolling_std
    return z_score


def compute_fib(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Fibonacci Retracement Levels (TBD - placeholder)."""
    # TODO: Implement fibonacci retracement levels
    # This is a placeholder that returns NaN
    return _empty_series(df)
