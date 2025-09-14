from __future__ import annotations

import pandas as pd

try:
    from ta.momentum import RSIIndicator
    from ta.trend import ADXIndicator, EMAIndicator
    from ta.volatility import AverageTrueRange, BollingerBands
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
    return EMAIndicator(close=series, window=length, fillna=True).ema_indicator()


def rsi(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    return RSIIndicator(close=series, window=length, fillna=True).rsi()


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    length = max(1, int(length))
    return AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=length, fillna=True
    ).average_true_range()


def adx(df: pd.DataFrame, length: int) -> pd.Series:
    length = max(1, int(length))
    return ADXIndicator(
        high=df["high"], low=df["low"], close=df["close"], window=length, fillna=True
    ).adx()


def bb_width(series: pd.Series, length: int, ndev: float) -> pd.Series:
    length = max(1, int(length))
    ndev = float(ndev)
    bb = BollingerBands(close=series, window=length, window_dev=ndev, fillna=True)
    hband = bb.bollinger_hband()
    lband = bb.bollinger_lband()
    mavg = bb.bollinger_mavg().replace(0, 1.0)
    return (hband - lband) / mavg


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
            out[name] = bb_width(
                _price_series(df, source),
                int(params.get("length", 20)),
                float(params.get("ndev", 2.0)),
            )
        elif typ == "HHV":
            out[name] = hhv(
                _price_series(df, source or "high"), int(params.get("length", 20))
            )
        elif typ == "LLV":
            out[name] = llv(
                _price_series(df, source or "low"), int(params.get("length", 20))
            )
        elif typ == "DC":
            up, lo = donchian_channels(df, int(params.get("length", 20)))
            out[f"{name}_upper"] = up
            out[f"{name}_lower"] = lo
        else:
            out[name] = pd.NA
    return out
