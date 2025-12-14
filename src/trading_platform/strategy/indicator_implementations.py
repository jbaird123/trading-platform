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

import weakref
from typing import Any, Callable, cast

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
)

from trading_platform.data.resample import resample_data, timeframe_to_timedelta
from trading_platform.strategy.indicator_helpers import find_swing_points

_PRICE_SERIES_CACHE: dict[int, dict[str, pd.Series]] = {}
_PRICE_CACHE_FINALIZERS: dict[int, weakref.finalize] = {}
_INDICATOR_SERIES_CACHE: dict[int, dict[str, pd.Series]] = {}
_INDICATOR_CACHE_FINALIZERS: dict[int, weakref.finalize] = {}


def _get_price_cache(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Return (or create) the per-DataFrame cache for price-derived series."""
    key = id(df)
    cache = _PRICE_SERIES_CACHE.get(key)
    if cache is None:
        cache = {}
        _PRICE_SERIES_CACHE[key] = cache

        def _cleanup(ref_key: int = key) -> None:
            _PRICE_SERIES_CACHE.pop(ref_key, None)
            _PRICE_CACHE_FINALIZERS.pop(ref_key, None)

        _PRICE_CACHE_FINALIZERS[key] = weakref.finalize(df, _cleanup)
    return cache


def _price_series(df: pd.DataFrame, source: str) -> pd.Series:
    """Convert source string to price series.

    Strict validation - raises ValueError for unrecognized sources.
    """
    cache = _get_price_cache(df)
    if source in cache:
        return cache[source]

    if source in ("open", "high", "low", "close"):
        series = pd.Series(df[source], dtype="float64")
    elif source == "volume":
        series = pd.Series(df["volume"])
        if not pd.api.types.is_numeric_dtype(series):
            series = series.astype("float64")
    elif source == "hl2":
        series = (
            pd.Series(df["high"], dtype="float64")
            + pd.Series(df["low"], dtype="float64")
        ) / 2.0
    elif source == "ohlc4":
        series = (
            pd.Series(df["open"], dtype="float64")
            + pd.Series(df["high"], dtype="float64")
            + pd.Series(df["low"], dtype="float64")
            + pd.Series(df["close"], dtype="float64")
        ) / 4.0
    else:
        raise ValueError(
            f"Unrecognized source: {source}. "
            f"Valid sources: open, high, low, close, hl2, ohlc4, volume"
        )

    cache[source] = series
    return series


def _get_indicator_cache(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Return per-DataFrame cache for expensive derived indicator series."""
    key = id(df)
    cache = _INDICATOR_SERIES_CACHE.get(key)
    if cache is None:
        cache = {}
        _INDICATOR_SERIES_CACHE[key] = cache

        def _cleanup(ref_key: int = key) -> None:
            _INDICATOR_SERIES_CACHE.pop(ref_key, None)
            _INDICATOR_CACHE_FINALIZERS.pop(ref_key, None)

        _INDICATOR_CACHE_FINALIZERS[key] = weakref.finalize(df, _cleanup)
    return cache


def _cache_indicator_series(
    df: pd.DataFrame,
    cache_key: str,
    builder: Callable[[], pd.Series],
) -> pd.Series:
    """Return cached indicator series or build/store it on demand."""
    cache = _get_indicator_cache(df)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = builder()
    cache[cache_key] = result
    return result


def _volume_series(df: pd.DataFrame) -> pd.Series:
    return _price_series(df, "volume")


def _price_array(df: pd.DataFrame, source: str) -> np.ndarray:
    return _price_series(df, source).to_numpy(dtype="float64")


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
            high=_price_series(df, "high"),
            low=_price_series(df, "low"),
            close=_price_series(df, "close"),
            window=length,
            fillna=False,
        )
        result = indicator.average_true_range()
        # Replace 0.0 values with NaN where insufficient data
        # ATR needs at least 'length' bars to be valid
        result = result.replace(0.0, np.nan)
        return result  # type: ignore[no-any-return]
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
            high=_price_series(df, "high"),
            low=_price_series(df, "low"),
            close=_price_series(df, "close"),
            window=length,
            fillna=False,
        )
        # Replace 0.0 values with NaN where insufficient data
        # ADX indicators need warm-up period
        adx_series = indicator.adx().replace(0.0, np.nan)
        di_plus = indicator.adx_pos().replace(0.0, np.nan)
        di_minus = indicator.adx_neg().replace(0.0, np.nan)

        renamed = pd.DataFrame(
            {
                "ADX": adx_series,
                "DI+": di_plus,
                "DI-": di_minus,
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
    """Compute Simple Moving Average using TA-Lib."""
    length = int(params.get("length", 14))
    series = _price_series(df, source)
    try:
        result = talib.SMA(series.to_numpy(dtype="float64"), timeperiod=length)
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_wma(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Weighted Moving Average using TA-Lib."""
    length = int(params.get("length", 14))
    series = _price_series(df, source)
    try:
        result = talib.WMA(series.to_numpy(dtype="float64"), timeperiod=length)
        return pd.Series(result, index=df.index, dtype="float64")
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


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
    """Compute Highest High Value.

    Note: Always uses 'high' column, ignoring source parameter.
    """
    series_in = (
        pd.Series(df[source_ref], dtype="float64")
        if source_ref
        else _price_series(df, "high")  # Always use high, ignore source param
    )
    return hhv(series_in, int(params.get("length", 20)))


def compute_llv(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "low",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Lowest Low Value.

    Note: Always uses 'low' column, ignoring source parameter.
    """
    series_in = (
        pd.Series(df[source_ref], dtype="float64")
        if source_ref
        else _price_series(df, "low")  # Always use low, ignore source param
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


def compute_ema_slope_pct(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute EMA slope as a percentage of the EMA value."""
    length = int(params.get("length", 14))
    slope_period = int(params.get("slope_period", 1))
    price_series = _price_series(df, source)
    ema_values = ema(price_series, length)
    slope = ema_values.diff(periods=slope_period)
    denominator = ema_values.replace(0.0, np.nan)
    pct = slope / denominator
    pct = pct.replace([np.inf, -np.inf], np.nan)
    return pct


def compute_rsi_bias(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute RSI bias normalised to [-1, 1]."""
    length = int(params.get("length", 14))
    rsi_vals = rsi(_price_series(df, source), length)
    bias = (rsi_vals - 50.0) / 50.0
    bias = bias.clip(lower=-1.0, upper=1.0)
    return bias


def compute_adx_strength(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute ADX strength scaled to [0, 1]."""
    length = int(params.get("length", 14))
    adx_df = adx(df, length)
    adx_vals = adx_df["ADX"]
    strength = (adx_vals / 50.0).clip(lower=0.0, upper=1.0)
    return strength


def compute_atr_percent(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute ATR as a percent of price."""
    length = int(params.get("length", 14))
    atr_vals = atr(df, length)
    price_series = _price_series(df, source).replace(0.0, np.nan)
    atr_pct = (atr_vals / price_series).replace([np.inf, -np.inf], np.nan)
    return atr_pct


def compute_atr_slope_pct(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute ATR slope normalised by ATR value."""
    length = int(params.get("length", 14))
    slope_period = int(params.get("slope_period", 1))
    atr_vals = atr(df, length)
    slope = atr_vals.diff(slope_period)
    with np.errstate(divide="ignore", invalid="ignore"):
        slope_pct = slope / atr_vals
    slope_pct = slope_pct.replace([np.inf, -np.inf], np.nan)
    return slope_pct


def compute_ema_trend_alignment(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compute multi-timeframe EMA slope alignment metrics."""
    timeframes_param = params.get("timeframes") or []
    if isinstance(timeframes_param, str):
        tf_list = [timeframes_param]
    else:
        tf_list = list(timeframes_param)

    tf_list = [str(tf) for tf in tf_list if str(tf)]
    if not tf_list:
        empty = pd.Series(np.nan, index=df.index, dtype="float64")
        return {
            "stack_score": empty,
            "full_alignment": empty,
            "nonzero_fraction": empty,
        }

    length = int(params.get("length", 50))
    slope_period = int(params.get("slope_period", 1))

    slope_pct_values: dict[str, pd.Series] = {}

    for tf in tf_list:
        try:
            resampled = resample_data(df, rule=tf)
        except Exception:
            slope_pct_values[tf] = pd.Series(np.nan, index=df.index, dtype="float64")
            continue

        shift_needed = not resampled.index.equals(df.index)
        timeframe_delta = (
            timeframe_to_timedelta(tf) if shift_needed else pd.Timedelta(0)
        )

        pct = compute_ema_slope_pct(
            resampled,
            {"length": length, "slope_period": slope_period},
            source,
            source_ref,
        )
        pct = pct.copy()
        if shift_needed:
            pct.index = pct.index + timeframe_delta
        pct = pct.reindex(df.index, method="ffill")
        slope_pct_values[tf] = pct

    slope_pct_df = pd.DataFrame(slope_pct_values, index=df.index)
    sign_df = slope_pct_df.apply(np.sign)
    sign_df = sign_df.where(~slope_pct_df.isna(), np.nan)

    positive_count = (sign_df > 0).sum(axis=1)
    negative_count = (sign_df < 0).sum(axis=1)
    nonzero_count = (sign_df != 0).sum(axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        stack_score = (positive_count - negative_count) / nonzero_count

    stack_score = stack_score.replace([np.inf, -np.inf], np.nan)

    full_alignment = (
        (nonzero_count > 0)
        & ((positive_count == nonzero_count) | (negative_count == nonzero_count))
    ).astype(float)

    nonzero_fraction = (nonzero_count / len(tf_list)).astype(float)

    stack_score = stack_score.astype(float)
    return {
        "stack_score": stack_score,
        "full_alignment": full_alignment,
        "nonzero_fraction": nonzero_fraction,
    }


def compute_ema_slope_confluence(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """Compare EMA slope between a base timeframe and higher timeframes."""

    length = int(params.get("length", 50))
    slope_period = int(params.get("slope_period", 1))

    base_timeframe = str(params.get("base_timeframe", "current") or "current")
    compare_param = params.get("compare_timeframes")
    if compare_param is None:
        compare_param = params.get("compare_timeframe")

    if isinstance(compare_param, str):
        compare_timeframes = [compare_param]
    else:
        compare_timeframes = list(compare_param or [])

    if not compare_timeframes:
        empty = pd.Series(np.nan, index=df.index, dtype="float64")
        return {
            "spread": empty,
            "ratio": empty,
            "alignment": empty,
        }

    def slope_for_timeframe(timeframe: str) -> pd.Series:
        if timeframe.lower() in {"", "current", "none"}:
            slope_source = df
            needs_align = False
        else:
            try:
                slope_source = resample_data(df, rule=str(timeframe))
            except Exception:
                return pd.Series(np.nan, index=df.index, dtype="float64")
            needs_align = True

        delta = (
            timeframe_to_timedelta(str(timeframe))
            if needs_align and not slope_source.index.equals(df.index)
            else pd.Timedelta(0)
        )
        shift_needed = delta != pd.Timedelta(0)

        slope_values = compute_ema_slope_pct(
            slope_source,
            {"length": length, "slope_period": slope_period},
            source,
            source_ref,
        )
        if needs_align and shift_needed:
            slope_values = slope_values.copy()
            slope_values.index = slope_values.index + delta
            slope_values = slope_values.reindex(df.index, method="ffill")
        return slope_values

    base_slope = slope_for_timeframe(base_timeframe)
    outputs: dict[str, pd.Series] = {}

    for compare_tf in compare_timeframes:
        compare_slope = slope_for_timeframe(str(compare_tf))
        spread = base_slope - compare_slope

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = base_slope / compare_slope
        ratio = ratio.replace([np.inf, -np.inf], np.nan)

        alignment = np.sign(base_slope) * np.sign(compare_slope)
        alignment = alignment.where(
            ~(base_slope.isna() | compare_slope.isna()),
            np.nan,
        )

        outputs[f"spread_{compare_tf}"] = spread
        outputs[f"ratio_{compare_tf}"] = ratio
        outputs[f"alignment_{compare_tf}"] = alignment

    return outputs


def compute_ema_distance_pct(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute percent distance between price and EMA."""
    length = int(params.get("length", 14))
    price = _price_series(df, source)
    ema_values = ema(price, length)
    denominator = price.replace(0.0, np.nan)
    distance = (price - ema_values) / denominator
    distance = distance.replace([np.inf, -np.inf], np.nan)
    return distance


def compute_rsi_slope(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute slope of RSI."""
    length = int(params.get("length", 14))
    slope_period = int(params.get("slope_period", 1))
    rsi_values = rsi(_price_series(df, source), length)
    return rsi_values.diff(slope_period)


def _rolling_percentile(series: pd.Series, lookback: int) -> pd.Series:
    """Return rolling percentile (0-1) of current value within lookback."""

    window = max(1, int(lookback))

    def _percentile(values: np.ndarray) -> float:
        if values.size == 0:
            return float("nan")
        current = values[-1]
        if np.isnan(current):
            return float("nan")
        valid = values[~np.isnan(values)]
        if valid.size == 0:
            return float("nan")
        count = np.count_nonzero(valid <= current)
        return float(count) / float(valid.size)

    return series.rolling(window=window, min_periods=1).apply(_percentile, raw=True)


def compute_bb_width_percentile(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute percentile rank of Bollinger Band width."""
    length = int(params.get("length", 20))
    ndev = float(params.get("ndev", 2.0))
    lookback = int(params.get("lookback", 100))
    cache_key = f"bb_width_pct::{length}:{ndev}:{lookback}:{source}:{source_ref or ''}"
    return _cache_indicator_series(
        df,
        cache_key,
        lambda: _rolling_percentile(
            compute_bb_width(
                df,
                {"length": length, "ndev": ndev},
                source,
                source_ref,
            ),
            lookback,
        ),
    )


def compute_range_atr_ratio(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute high-low range divided by ATR."""
    length = int(params.get("length", 14))
    atr_vals = atr(df, length)
    range_values = _price_series(df, "high") - _price_series(df, "low")
    denominator = atr_vals.replace(0.0, np.nan)
    ratio = range_values / denominator
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    return ratio


def _true_range(df: pd.DataFrame) -> pd.Series:
    high = _price_series(df, "high")
    low = _price_series(df, "low")
    prev_close = _price_series(df, "close").shift(1)
    high_low = high - low
    high_close = (high - prev_close).abs()
    low_close = (low - prev_close).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


def compute_true_range_zscore(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute z-score of true range over rolling window."""
    window = int(params.get("window", 50))
    tr = _true_range(df)
    mean = tr.rolling(window=window, min_periods=1).mean()
    std = tr.rolling(window=window, min_periods=1).std(ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        zscore = (tr - mean) / std
    zscore = zscore.replace([np.inf, -np.inf], np.nan)
    return zscore


def _distance_pct(series: pd.Series, reference: pd.Series) -> pd.Series:
    denominator = reference.replace(0.0, np.nan)
    distance = (series - reference) / denominator
    return distance.replace([np.inf, -np.inf], np.nan)


def compute_close_to_hhv_pct(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute distance of price to rolling highest high."""
    length = int(params.get("length", 20))
    price = _price_series(df, source)
    hhv_series = hhv(_price_series(df, "high"), length)
    return _distance_pct(price, hhv_series)


def compute_close_to_llv_pct(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute distance of price to rolling lowest low."""
    length = int(params.get("length", 20))
    price = _price_series(df, source)
    llv_series = llv(_price_series(df, "low"), length)
    return _distance_pct(price, llv_series)


def compute_hhv_slope(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "high",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute slope of rolling highest high."""
    length = int(params.get("length", 20))
    slope_period = int(params.get("slope_period", 1))
    hhv_series = hhv(_price_series(df, source), length)
    return hhv_series.diff(slope_period)


def compute_llv_slope(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "low",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute slope of rolling lowest low."""
    length = int(params.get("length", 20))
    slope_period = int(params.get("slope_period", 1))
    llv_series = llv(_price_series(df, source), length)
    return llv_series.diff(slope_period)


def compute_volume_sma_ratio(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "volume",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute ratio of volume to its SMA."""
    length = int(params.get("length", 20))
    volume = _price_series(df, source)
    sma_values = compute_sma(df, {"length": length}, source, source_ref)
    denominator = sma_values.replace(0.0, np.nan)
    ratio = volume / denominator
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    return ratio


def compute_prior_return(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute price return over previous N bars."""
    window = int(params.get("window", 1))
    price = _price_series(df, source)
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = price.pct_change(periods=window)
    return returns.replace([np.inf, -np.inf], np.nan)


def compute_day_of_week_onehot(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> dict[str, pd.Series]:
    """One-hot encode day of week."""
    index = df.index
    if not isinstance(index, pd.DatetimeIndex):
        empty = _empty_series(df)
        return {f"dow_{day}": empty for day in range(7)}

    day = index.dayofweek
    columns: dict[str, pd.Series] = {}
    for dow in range(7):
        columns[f"dow_{dow}"] = pd.Series((day == dow).astype(float), index=index)
    return columns


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
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        indicator = DonchianChannel(
            high=high,
            low=low,
            close=close,
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
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        indicator = PSARIndicator(
            high=high,
            low=low,
            close=close,
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
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        indicator = StochasticOscillator(
            high=high,
            low=low,
            close=close,
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
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        indicator = KeltnerChannel(
            high=high,
            low=low,
            close=close,
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
            close=_price_series(df, source),
            volume=_volume_series(df),
            fillna=False,
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
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        indicator = ChaikinMoneyFlowIndicator(
            high=high,
            low=low,
            close=close,
            volume=_volume_series(df),
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
    """Compute Volume Weighted Average Price (session-anchored).

    Implements industry-standard session-anchored VWAP that resets at the
    start of each trading session (daily). Uses Typical Price (H+L+C)/3 as
    the price source.

    VWAP = Cumulative(Typical Price × Volume) / Cumulative(Volume)

    Note: This differs from the ta library's VolumeWeightedAveragePrice which
    uses a rolling window approach. Session-anchored VWAP is the standard used
    by most trading platforms including TradingView.
    """
    try:
        # Calculate Typical Price (industry standard for VWAP)
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        typical_price = (high + low + close) / 3
        volume = _volume_series(df)

        # Identify session boundaries (new day in UTC)
        # Assumes index is DatetimeIndex with timezone info
        session: pd.Series | pd.DatetimeIndex
        if isinstance(df.index, pd.DatetimeIndex):
            # Create session identifier (date only)
            session = df.index.normalize()
        else:
            # Fallback: treat entire dataset as one session
            session = pd.Series(0, index=df.index)

        # Calculate VWAP for each session
        # Group by session and calculate cumulative sums within each session
        pv = typical_price * volume

        # Use groupby with cumsum to reset at session boundaries
        cum_pv = pv.groupby(session).cumsum()
        cum_vol = volume.groupby(session).cumsum()

        # VWAP = cumulative(price × volume) / cumulative(volume)
        vwap = cum_pv / cum_vol

        return pd.Series(vwap, name="vwap", index=df.index)
    except (IndexError, ValueError, TypeError, KeyError):
        return _empty_series(df)


def compute_chop(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Choppiness Index.

    Formula: 100 * LOG10(SUM(ATR(1), n) / (MaxHi(n) - MinLo(n))) / LOG10(n)

    Values: 0-100 scale
    - Close to 0: Strong trending market
    - Close to 100: Choppy/sideways market
    - Common thresholds: <38.2 trending, 38.2-61.8 neutral, >61.8 choppy
    """
    length = int(params.get("length", 14))
    n = len(df)

    if n < length:
        return _empty_series(df)

    try:
        # Calculate True Range for period of 1
        high = _price_series(df, "high")
        low = _price_series(df, "low")
        close = _price_series(df, "close")
        prev_close = close.shift(1)

        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)

        # Sum of TR over n periods
        sum_tr = tr.rolling(window=length, min_periods=length).sum()

        # Highest high and lowest low over n periods
        max_high = high.rolling(window=length, min_periods=length).max()
        min_low = low.rolling(window=length, min_periods=length).min()

        # Calculate CHOP
        range_hl = max_high - min_low
        # Avoid division by zero
        range_hl = range_hl.replace(0, np.nan)

        chop = 100 * np.log10(sum_tr / range_hl) / np.log10(length)

        return cast(pd.Series, chop)
    except (IndexError, ValueError, TypeError, KeyError):
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
            high=_price_series(df, "high"),
            low=_price_series(df, "low"),
            close=_price_series(df, "close"),
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
            high=_price_series(df, "high"),
            low=_price_series(df, "low"),
            window1=tenkan,
            window2=kijun,
            window3=senkou,
            visual=False,  # No displacement - TV exports already include displacement
            fillna=False,
        )
        # Note: TradingView exports Ichimoku values WITHOUT displacement applied
        # FOR SENKOU SPANS ONLY. Chikou span IS shifted in the export.
        # - Senkou A/B: Raw calculated values (no shift)
        # - Chikou: close.shift(+26) - shows past price at current position
        #   (positive shift moves values forward, so past values appear at current bar)
        return {
            "tenkan": indicator.ichimoku_conversion_line(),
            "kijun": indicator.ichimoku_base_line(),
            "senkou_a": indicator.ichimoku_a(),
            "senkou_b": indicator.ichimoku_b(),
            "chikou": _price_series(df, "close").shift(kijun),
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
    """Compute SuperTrend indicator.

    Algorithm by Olivier Seban. Combines ATR and price to identify trend direction.

    Returns dict with keys:
    - "": Main SuperTrend value (alternates between upper/lower band based on trend)
    - "direction": 1 for uptrend, -1 for downtrend
    - "long": Lower band (support in uptrend)
    - "short": Upper band (resistance in downtrend)

    Default params: length=7, multiplier=3.0
    """
    length = int(params.get("length", 7))
    multiplier = float(params.get("multiplier", 3.0))
    n = len(df)

    if n < length:
        empty = _empty_series(df)
        return {"": empty, "direction": empty, "long": empty, "short": empty}

    try:
        atr_values = atr(df, length)
        first_valid_ts = atr_values.first_valid_index()
        if first_valid_ts is None:
            empty = _empty_series(df)
            return {"": empty, "direction": empty, "long": empty, "short": empty}

        start_pos = atr_values.index.get_loc(first_valid_ts)

        hl2 = (_price_series(df, "high") + _price_series(df, "low")) / 2
        basic_upper = hl2 + (multiplier * atr_values)
        basic_lower = hl2 - (multiplier * atr_values)

        final_upper = pd.Series(np.nan, index=df.index, dtype="float64")
        final_lower = pd.Series(np.nan, index=df.index, dtype="float64")
        supertrend = pd.Series(np.nan, index=df.index, dtype="float64")
        direction = pd.Series(np.nan, index=df.index, dtype="float64")

        close = _price_series(df, "close")

        for i in range(start_pos, n):
            if i == start_pos:
                final_upper.iloc[i] = basic_upper.iloc[i]
                final_lower.iloc[i] = basic_lower.iloc[i]
                continue

            if (
                basic_upper.iloc[i] < final_upper.iloc[i - 1]
                or close.iloc[i - 1] > final_upper.iloc[i - 1]
            ):
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

            if (
                basic_lower.iloc[i] > final_lower.iloc[i - 1]
                or close.iloc[i - 1] < final_lower.iloc[i - 1]
            ):
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]

        for i in range(start_pos, n):
            if i == start_pos:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
                continue

            if close.iloc[i] > final_upper.iloc[i - 1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < final_lower.iloc[i - 1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                supertrend.iloc[i] = final_upper.iloc[i]

        return {
            "": supertrend,  # Main value
            "direction": direction,  # 1=up, -1=down
            "long": final_lower,  # Support line
            "short": final_upper,  # Resistance line
        }
    except (IndexError, ValueError, TypeError, KeyError):
        empty = _empty_series(df)
        return {"": empty, "direction": empty, "long": empty, "short": empty}


def compute_swing_high(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Swing High points.

    Returns the high price value at swing high points (matching TradingView),
    NaN elsewhere.
    """
    left_bars = int(params.get("left_bars", 10))
    right_bars = int(params.get("right_bars", 10))
    swings = find_swing_points(
        df,
        left_bars=left_bars,
        right_bars=right_bars,
        return_prices=True,  # Return actual price values, not 1.0/0.0 flags
    )
    result: pd.Series = swings["swing_high"]
    return result


def compute_swing_low(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series:
    """Compute Swing Low points.

    Returns the low price value at swing low points (matching TradingView),
    NaN elsewhere.
    """
    left_bars = int(params.get("left_bars", 10))
    right_bars = int(params.get("right_bars", 10))
    swings = find_swing_points(
        df,
        left_bars=left_bars,
        right_bars=right_bars,
        return_prices=True,  # Return actual price values, not 1.0/0.0 flags
    )
    result: pd.Series = swings["swing_low"]
    return result


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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
            _price_array(df, "open"),
            _price_array(df, "high"),
            _price_array(df, "low"),
            _price_array(df, "close"),
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
    """Calculate ATR percentile rank over a lookback period.

    Matches TradingView's ta.percentrank() calculation, which rounds to 5% zones
    for readability (0, 5, 10, ..., 100).
    """
    atr_len = int(params.get("atr_length", 14))
    lookback = int(params.get("lookback", 20))
    cache_key = f"atr_pct::{atr_len}:{lookback}"

    def _build_series() -> pd.Series:
        atr_values = atr(df, atr_len)
        window = max(2, lookback + 1)
        return atr_values.rolling(
            window=window,
            min_periods=2,
        ).apply(_percentrank_tv, raw=True)

    return _cache_indicator_series(df, cache_key, _build_series)


def _percentrank_tv(values: np.ndarray) -> float:
    """TradingView-style percentile rank rounded to nearest 5%."""
    if values.size <= 1:
        return 0.0
    current = values[-1]
    if np.isnan(current):
        return float("nan")
    previous = values[:-1]
    previous = previous[~np.isnan(previous)]
    if previous.size == 0:
        return float("nan")
    count_below = np.count_nonzero(previous < current)
    precise = count_below / float(previous.size) * 100.0
    return round(precise / 5.0) * 5.0


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
    series = _volume_series(df)
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
) -> dict[str, pd.Series]:
    """Compute Fibonacci Retracement Levels.

    Calculates Fibonacci retracement levels between swing high and swing low.
    Uses find_swing_points() to identify swing points.

    Returns dict with standard Fibonacci ratios:
    - "0.000": Swing low (0% retracement)
    - "0.236": 23.6% retracement
    - "0.382": 38.2% retracement
    - "0.500": 50% retracement
    - "0.618": 61.8% retracement (golden ratio)
    - "0.786": 78.6% retracement
    - "1.000": Swing high (100% retracement)

    Default params: left_bars=5, right_bars=5 (for swing point detection)
    """
    left_bars = int(params.get("left_bars", 5))
    right_bars = int(params.get("right_bars", 5))

    # Standard Fibonacci ratios
    fib_ratios = [0.000, 0.236, 0.382, 0.500, 0.618, 0.786, 1.000]

    try:
        # Find swing points
        swings = find_swing_points(df, left_bars=left_bars, right_bars=right_bars)

        swing_high_series = swings["swing_high"]
        swing_low_series = swings["swing_low"]

        # Forward fill to get the most recent swing high/low at each point
        recent_swing_high = swing_high_series.ffill()
        recent_swing_low = swing_low_series.ffill()

        # Calculate range
        fib_range = recent_swing_high - recent_swing_low

        # Calculate Fibonacci levels
        # For uptrend: start from swing low and add ratios of range
        # For downtrend: start from swing high and subtract ratios of range
        # We'll calculate both and use the most recent swing direction
        result = {}

        for ratio in fib_ratios:
            # Calculate level from swing low (uptrend perspective)
            level = recent_swing_low + (fib_range * ratio)
            result[f"{ratio:.3f}"] = level

        return result

    except (IndexError, ValueError, TypeError, KeyError):
        empty = _empty_series(df)
        return {f"{ratio:.3f}": empty for ratio in fib_ratios}
