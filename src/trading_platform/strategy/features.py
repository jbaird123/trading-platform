from __future__ import annotations

from typing import cast

import pandas as pd

try:
    from ta.momentum import RSIIndicator  # type: ignore[import-untyped]
    from ta.trend import ADXIndicator, EMAIndicator  # type: ignore[import-untyped]
    from ta.volatility import (  # type: ignore[import-untyped]
        AverageTrueRange,
        BollingerBands,
    )
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "The 'ta' library is required for indicator computations. Please "
        "install it (poetry add ta) and re-run."
    ) from exc


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
    length = max(1, int(length))
    return cast(
        pd.Series,
        EMAIndicator(close=series, window=length, fillna=True).ema_indicator(),
    )


def rsi(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    return cast(pd.Series, RSIIndicator(close=series, window=length, fillna=True).rsi())


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    length = max(1, int(length))
    return cast(
        pd.Series,
        AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=True,
        ).average_true_range(),
    )


def adx(df: pd.DataFrame, length: int) -> pd.Series:
    length = max(1, int(length))
    return cast(
        pd.Series,
        ADXIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=length,
            fillna=True,
        ).adx(),
    )


def bb_width(series: pd.Series, length: int, ndev: float) -> pd.Series:
    length = max(1, int(length))
    ndev = float(ndev)
    bb = BollingerBands(close=series, window=length, window_dev=ndev, fillna=True)
    hband = cast(pd.Series, bb.bollinger_hband())
    lband = cast(pd.Series, bb.bollinger_lband())
    mavg = cast(pd.Series, bb.bollinger_mavg()).replace(0, 1.0)
    return cast(pd.Series, (hband - lband) / mavg)


def hhv(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    return series.rolling(window=length, min_periods=1).max()


def llv(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    return series.rolling(window=length, min_periods=1).min()


def donchian_channels(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    length = max(1, int(length))
    upper = pd.Series(df["high"]).rolling(length, min_periods=1).max()
    lower = pd.Series(df["low"]).rolling(length, min_periods=1).min()
    return upper, lower


def compute_features(df: pd.DataFrame, specs: list[dict]) -> pd.DataFrame:
    """Compute features as configured in specs.

    Each spec: {name, type, params, source}
    Returns a DataFrame including original df plus new feature columns by name.
    """
    out = df.copy()
    for spec in specs or []:
        name = str(spec.get("name"))
        typ = str(spec.get("type"))
        params = spec.get("params") or {}
        source = str(spec.get("source", "close"))
        source_ref = None
        _src_ref_val = spec.get("source_ref")
        if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
            ref_val = _src_ref_val.get("ref")
            source_ref = str(ref_val) if ref_val is not None else None
        if not name:
            continue
        if typ == "EMA":
            length = int(params.get("length", 14))
            out[name] = ema(_price_series(df, source), length)
        elif typ == "RSI":
            length = int(params.get("length", 14))
            out[name] = rsi(_price_series(df, source), length)
        elif typ == "ATR":
            length = int(params.get("length", 14))
            out[name] = atr(df, length)
        elif typ == "ADX":
            out[name] = adx(df, int(params.get("length", 14)))
        elif typ == "BB":
            bb = BollingerBands(
                close=_price_series(df, source),
                window=int(params.get("length", 20)),
                window_dev=float(params.get("ndev", 2.0)),
                fillna=True,
            )
            out[f"{name}_upper"] = cast(pd.Series, bb.bollinger_hband())
            out[f"{name}_lower"] = cast(pd.Series, bb.bollinger_lband())
            out[f"{name}_middle"] = cast(pd.Series, bb.bollinger_mavg())
        elif typ == "BBWidth":
            out[name] = bb_width(
                _price_series(df, source),
                int(params.get("length", 20)),
                float(params.get("ndev", 2.0)),
            )
        elif typ == "HHV":
            series_in = (
                pd.Series(df[source_ref], dtype="float64")
                if source_ref
                else _price_series(df, source or "high")
            )
            out[name] = hhv(series_in, int(params.get("length", 20)))
        elif typ == "LLV":
            series_in = (
                pd.Series(df[source_ref], dtype="float64")
                if source_ref
                else _price_series(df, source or "low")
            )
            out[name] = llv(series_in, int(params.get("length", 20)))
        elif typ == "DC":
            up, lo = donchian_channels(df, int(params.get("length", 20)))
            out[f"{name}_upper"] = up
            out[f"{name}_lower"] = lo
        else:
            out[name] = pd.NA
    return out
