from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import pandas_ta as ta

from trading_platform.strategy.custom_indicators import find_swing_points


def _price_series(df: pd.DataFrame, source: str) -> pd.Series:
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


def ema(series: pd.Series, length: int) -> pd.Series:
    n = len(series)
    length = max(1, min(int(length), n))
    result = ta.ema(close=series, length=length)
    if result is None:
        return pd.Series([np.nan] * n, index=series.index, dtype="float64")
    return cast(pd.Series, result)


def ema_slope(series: pd.Series, length: int, slope_period: int = 1) -> pd.Series:
    """Calculate the slope (rate of change) of an EMA.

    Args:
        series: Input price series
        length: EMA period
        slope_period: Lookback period for calculating slope (default=1)

    Returns:
        Series containing the EMA slope values
    """
    ema_values = ema(series, length)
    # Calculate slope as difference over slope_period
    slope = ema_values.diff(periods=slope_period)
    return slope


def rsi(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    result = ta.rsi(close=series, length=length)
    if result is None:
        return pd.Series([np.nan] * len(series), index=series.index, dtype="float64")
    return cast(pd.Series, result)


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    n = len(df)
    length = max(1, min(int(length), n))
    try:
        result = ta.atr(
            high=df["high"], low=df["low"], close=df["close"], length=length
        )
        if result is None:
            return pd.Series([np.nan] * n, index=df.index, dtype="float64")
        return cast(pd.Series, result)
    except (IndexError, ValueError, TypeError):
        # TypeError can occur in pandas_ta with Python 3.13 (isnan bug)
        return pd.Series([np.nan] * n, index=df.index, dtype="float64")


def adx(df: pd.DataFrame, length: int) -> pd.Series:
    n = len(df)
    if n < 3:
        return pd.Series([np.nan] * n, index=df.index, dtype="float64")
    length = max(3, min(int(length), n))

    try:
        result = ta.adx(
            high=df["high"], low=df["low"], close=df["close"], length=length
        )
        if result is None:
            return pd.Series([np.nan] * n, index=df.index, dtype="float64")
        # pandas_ta returns DataFrame with ADX, DMP, DMN columns
        # We want the ADX column (first one)
        if isinstance(result, pd.DataFrame):
            return cast(pd.Series, result.iloc[:, 0])
        return cast(pd.Series, result)
    except (IndexError, ValueError, TypeError):
        # TypeError can occur in pandas_ta with Python 3.13 (isnan bug)
        return pd.Series([np.nan] * n, index=df.index, dtype="float64")


def bb_width(series: pd.Series, length: int, ndev: float) -> pd.Series:
    length = max(1, int(length))
    ndev = float(ndev)
    bb = ta.bbands(close=series, length=length, std=ndev)  # type: ignore
    if bb is None or bb.empty:
        return pd.Series([np.nan] * len(series), index=series.index, dtype="float64")
    # pandas_ta returns DataFrame with columns: BBL_length_std, BBM_, BBU_
    hband = bb.iloc[:, 2]  # Upper band
    lband = bb.iloc[:, 0]  # Lower band
    mavg = bb.iloc[:, 1].replace(0, 1.0)  # Middle band
    return cast(pd.Series, (hband - lband) / mavg)


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


def donchian_channels(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    length = max(1, int(length))
    upper = pd.Series(df["high"]).rolling(length, min_periods=1).max()
    lower = pd.Series(df["low"]).rolling(length, min_periods=1).min()
    return upper, lower


def atr_percentile(df: pd.DataFrame, atr_length: int, lookback: int) -> pd.Series:
    """Calculate ATR percentile rank over a lookback period.

    Args:
        df: DataFrame with OHLC data
        atr_length: ATR calculation period
        lookback: Lookback period for percentile calculation

    Returns:
        Series with ATR percentile values (0-100)
    """
    atr_values = atr(df, atr_length)
    # Calculate percentile rank using rolling window
    # Count how many values in window are less than current value
    percentile = atr_values.rolling(window=lookback, min_periods=1).apply(
        lambda x: (x.iloc[-1] > x).sum() / (len(x) - 1) * 100 if len(x) > 1 else 50.0,
        raw=False,
    )
    return percentile


def realized_volatility(series: pd.Series, length: int) -> pd.Series:
    """Calculate realized volatility as the standard deviation of returns.

    Args:
        series: Price series (typically close)
        length: Lookback period for volatility calculation

    Returns:
        Series with realized volatility values
    """
    # Calculate log returns
    log_ret = pd.Series(np.log(series / series.shift(1)), index=series.index)
    # Calculate rolling standard deviation of returns
    vol = log_ret.rolling(window=length, min_periods=1).std()
    return cast(pd.Series, vol)


def volume_zscore(series: pd.Series, length: int) -> pd.Series:
    """Calculate volume z-score relative to rolling mean and std.

    Args:
        series: Volume series
        length: Lookback period for mean/std calculation

    Returns:
        Series with volume z-score values
    """
    rolling_mean = series.rolling(window=length, min_periods=1).mean()
    rolling_std = series.rolling(window=length, min_periods=1).std()
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, 1)
    z_score = (series - rolling_mean) / rolling_std
    return z_score


def _resolve_parameter(param_value: Any, strategy_parameters: dict) -> Any:
    """Resolves parameter, substituting placeholders like ${param_name}."""
    if not isinstance(param_value, str):
        return param_value
    if param_value.startswith("${") and param_value.endswith("}"):
        param_name = param_value[2:-1]
        if param_name in strategy_parameters:
            return strategy_parameters[param_name]
        else:
            raise ValueError(
                f"Parameter '{param_name}' not found in strategy " f"parameters."
            )
    return param_value


def _resample_to_higher_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample OHLCV data to a higher timeframe.

    Args:
        df: DataFrame with OHLCV data
        timeframe: Target timeframe (e.g., '1h', '4h', '1D')

    Returns:
        Resampled DataFrame
    """
    # Use pandas resample with OHLC aggregation
    resampled = df.resample(timeframe).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return resampled


def compute_features(
    df: pd.DataFrame, specs: list[dict], strategy_parameters: dict = {}
) -> pd.DataFrame:
    """Compute features as configured in specs.

    Each spec: {name, type, params, source}
    Returns DataFrame with original df plus new feature columns by name.

    Note: Returns NaN values naturally where indicators need warm-up period.
    The backtester will skip bars with NaN in required features.
    The AI pipeline should call .dropna() explicitly if needed.
    """
    if strategy_parameters is None:
        strategy_parameters = {}

    out = df.copy()
    for spec in specs or []:
        name = str(spec.get("name"))
        typ = str(spec.get("type"))
        params = spec.get("params") or {}
        source = str(spec.get("source", "close"))
        timeframe = spec.get("timeframe")  # Optional higher timeframe
        source_ref = None
        _src_ref_val = spec.get("source_ref")
        if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
            ref_val = _src_ref_val.get("ref")
            source_ref = str(ref_val) if ref_val is not None else None
        if not name:
            continue

        # Handle higher-timeframe features (Task 11)
        if timeframe:
            # Resample data to higher timeframe
            df_resampled = _resample_to_higher_timeframe(df, timeframe)
            # Compute feature on resampled data (create temp spec without timeframe)
            temp_spec = {
                "name": name,
                "type": typ,
                "params": params,
                "source": source,
            }
            if source_ref:
                temp_spec["source_ref"] = {"ref": source_ref}
            # Recursively compute on resampled data
            df_htf = compute_features(df_resampled, [temp_spec], strategy_parameters)
            # Forward-fill back to original timeframe
            htf_series = df_htf[name].reindex(df.index, method="ffill")
            out[name] = htf_series
            continue

        # Resolve parameters for the current feature
        resolved_params = {
            k: _resolve_parameter(v, strategy_parameters) for k, v in params.items()
        }

        if typ == "EMA":
            length = int(resolved_params.get("length", 14))
            out[name] = ema(_price_series(df, source), length)
        elif typ == "EMASlope":
            length = int(resolved_params.get("length", 14))
            slope_period = int(resolved_params.get("slope_period", 1))
            out[name] = ema_slope(_price_series(df, source), length, slope_period)
        elif typ == "SMA":
            length = int(resolved_params.get("length", 14))
            result = ta.sma(close=_price_series(df, source), length=length)
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "WMA":
            length = int(resolved_params.get("length", 14))
            result = ta.wma(close=_price_series(df, source), length=length)
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "RSI":
            length = int(resolved_params.get("length", 14))
            out[name] = rsi(_price_series(df, source), length)
        elif typ == "ATR":
            length = int(resolved_params.get("length", 14))
            out[name] = atr(df, length)
        elif typ == "ADX":
            out[name] = adx(df, int(resolved_params.get("length", 14)))
        elif typ == "BB":
            length = int(resolved_params.get("length", 20))
            ndev = float(resolved_params.get("ndev", 2.0))
            bb = ta.bbands(
                close=_price_series(df, source),
                length=length,
                std=ndev,  # type: ignore[arg-type]
            )
            if bb is not None and not bb.empty:
                out[f"{name}_upper"] = bb.iloc[:, 2]
                out[f"{name}_lower"] = bb.iloc[:, 0]
                out[f"{name}_middle"] = bb.iloc[:, 1]
            else:
                out[f"{name}_upper"] = np.nan
                out[f"{name}_lower"] = np.nan
                out[f"{name}_middle"] = np.nan
        elif typ == "BBWidth":
            out[name] = bb_width(
                _price_series(df, source),
                int(resolved_params.get("length", 20)),
                float(resolved_params.get("ndev", 2.0)),
            )
        elif typ == "MACD":
            slow = int(resolved_params.get("slow", 26))
            fast = int(resolved_params.get("fast", 12))
            signal = int(resolved_params.get("signal", 9))
            macd = ta.macd(
                close=_price_series(df, source),
                fast=fast,
                slow=slow,
                signal=signal,
            )
            if macd is not None and not macd.empty:
                # pandas_ta returns: MACD_f_s, MACDh_f_s, MACDs_f_s
                out[f"{name}_macd"] = macd.iloc[:, 0]
                out[f"{name}_signal"] = macd.iloc[:, 2]
                out[f"{name}_diff"] = macd.iloc[:, 1]
            else:
                out[f"{name}_macd"] = np.nan
                out[f"{name}_signal"] = np.nan
                out[f"{name}_diff"] = np.nan
        elif typ == "PSAR":
            step = float(resolved_params.get("step", 0.02))
            max_step = float(resolved_params.get("max", 0.2))
            psar = ta.psar(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                af0=step,
                af=step,
                max_af=max_step,
            )
            if psar is not None and not psar.empty:
                # pandas_ta returns multiple columns
                out[f"{name}"] = psar.iloc[:, 3]  # PSARl/s
                out[f"{name}_up"] = psar.iloc[:, 0]  # PSARl
                out[f"{name}_down"] = psar.iloc[:, 1]  # PSARs
            else:
                out[f"{name}"] = np.nan
                out[f"{name}_up"] = np.nan
                out[f"{name}_down"] = np.nan
        elif typ == "STOCH":
            length = int(resolved_params.get("length", 14))
            k = int(resolved_params.get("k", 3))
            d = int(resolved_params.get("d", 3))
            stoch = ta.stoch(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                k=length,
                d=d,
                smooth_k=k,
            )
            if stoch is not None and not stoch.empty:
                out[f"{name}"] = stoch.iloc[:, 0]  # STOCHk
                out[f"{name}_signal"] = stoch.iloc[:, 1]  # STOCHd
            else:
                out[f"{name}"] = np.nan
                out[f"{name}_signal"] = np.nan
        elif typ == "CCI":
            length = int(resolved_params.get("length", 20))
            result = ta.cci(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=length,
            )
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "ROC":
            length = int(resolved_params.get("length", 12))
            result = ta.roc(close=_price_series(df, source), length=length)
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "HHV":
            series_in = (
                pd.Series(df[source_ref], dtype="float64")
                if source_ref
                else _price_series(df, source or "high")
            )
            out[name] = hhv(series_in, int(resolved_params.get("length", 20)))
        elif typ == "LLV":
            series_in = (
                pd.Series(df[source_ref], dtype="float64")
                if source_ref
                else _price_series(df, source or "low")
            )
            out[name] = llv(series_in, int(resolved_params.get("length", 20)))
        elif typ in ("SWING_HIGH", "SWING_LOW"):
            left_bars = int(resolved_params.get("left_bars", 10))
            right_bars = int(resolved_params.get("right_bars", 10))
            swings = find_swing_points(
                df,
                left_bars=left_bars,
                right_bars=right_bars,
            )
            if typ == "SWING_HIGH":
                out[name] = swings["swing_high"]
            else:
                out[name] = swings["swing_low"]
        elif typ == "DC":
            up, lo = donchian_channels(df, int(resolved_params.get("length", 20)))
            out[f"{name}_upper"] = up
            out[f"{name}_lower"] = lo
        elif typ == "KC":
            length = int(resolved_params.get("length", 20))
            mult = float(resolved_params.get("mult", 2.0))
            kc = ta.kc(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=length,
                scalar=mult,
            )
            if kc is not None and not kc.empty:
                out[f"{name}_upper"] = kc.iloc[:, 2]
                out[f"{name}_lower"] = kc.iloc[:, 0]
                out[f"{name}_middle"] = kc.iloc[:, 1]
            else:
                out[f"{name}_upper"] = np.nan
                out[f"{name}_lower"] = np.nan
                out[f"{name}_middle"] = np.nan
        elif typ == "OBV":
            result = ta.obv(close=_price_series(df, source), volume=df["volume"])
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "CMF":
            length = int(resolved_params.get("length", 20))
            result = ta.cmf(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                volume=df["volume"],
                length=length,
            )
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "VWAP":
            result = ta.vwap(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                volume=df["volume"],
            )
            out[name] = (
                cast(pd.Series, result)
                if result is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "CHOP":
            chop = ta.chop(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=int(resolved_params.get("length", 14)),
                atr_length=int(resolved_params.get("atr_length", 1)),
                scalar=float(resolved_params.get("scalar", 100.0)),
            )
            out[name] = (
                cast(pd.Series, chop)
                if chop is not None
                else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
            )
        elif typ == "ICHIMOKU":
            ichimoku_df, _ = ta.ichimoku(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                tenkan=int(resolved_params.get("tenkan", 9)),
                kijun=int(resolved_params.get("kijun", 26)),
                senkou=int(resolved_params.get("senkou", 52)),
            )
            if ichimoku_df is not None and not ichimoku_df.empty:
                out[f"{name}_tenkan"] = ichimoku_df.iloc[:, 0]
                out[f"{name}_kijun"] = ichimoku_df.iloc[:, 1]
                out[f"{name}_senkou_a"] = ichimoku_df.iloc[:, 2]
                out[f"{name}_senkou_b"] = ichimoku_df.iloc[:, 3]
                out[f"{name}_chikou"] = ichimoku_df.iloc[:, 4]
            else:
                out[f"{name}_tenkan"] = np.nan
                out[f"{name}_kijun"] = np.nan
                out[f"{name}_senkou_a"] = np.nan
                out[f"{name}_senkou_b"] = np.nan
                out[f"{name}_chikou"] = np.nan
        elif typ == "SUPERTREND":
            st = ta.supertrend(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=int(resolved_params.get("length", 7)),
                multiplier=float(resolved_params.get("multiplier", 3.0)),
            )
            if st is not None and not st.empty:
                out[f"{name}"] = st.iloc[:, 0]
                out[f"{name}_direction"] = st.iloc[:, 1]
                out[f"{name}_long"] = st.iloc[:, 2]
                out[f"{name}_short"] = st.iloc[:, 3]
            else:
                out[name] = np.nan
                out[f"{name}_direction"] = np.nan
                out[f"{name}_long"] = np.nan
                out[f"{name}_short"] = np.nan
        elif typ.startswith("CDL_"):
            # Candlestick patterns
            pattern_name = typ[4:].lower()  # Remove CDL_ prefix
            if hasattr(ta, f"cdl_{pattern_name}"):
                pattern_func = getattr(ta, f"cdl_{pattern_name}")
                result = pattern_func(
                    open_=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                )
                out[name] = (
                    cast(pd.Series, result)
                    if result is not None
                    else pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
                )
            else:
                out[name] = np.nan
        elif typ == "ATRPercentile":
            atr_len = int(resolved_params.get("atr_length", 14))
            lookback = int(resolved_params.get("lookback", 20))
            out[name] = atr_percentile(df, atr_len, lookback)
        elif typ == "RealizedVolatility":
            length = int(resolved_params.get("length", 20))
            out[name] = realized_volatility(_price_series(df, source), length)
        elif typ == "VolumeZScore":
            length = int(resolved_params.get("length", 20))
            out[name] = volume_zscore(pd.Series(df["volume"]), length)
        else:
            out[name] = np.nan

    # Return with natural NaN values - consuming code handles them
    return out
