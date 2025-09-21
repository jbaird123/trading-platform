from __future__ import annotations

from typing import cast

import pandas as pd

try:
    from ta.momentum import (  # type: ignore[import-untyped]
        ROCIndicator,
        RSIIndicator,
        StochasticOscillator,
    )
    from ta.trend import (  # type: ignore[import-untyped]
        MACD,
        ADXIndicator,
        CCIIndicator,
        EMAIndicator,
        PSARIndicator,
        SMAIndicator,
        WMAIndicator,
    )
    from ta.volatility import (  # type: ignore[import-untyped]
        AverageTrueRange,
        BollingerBands,
        KeltnerChannel,
    )
    from ta.volume import (  # type: ignore[import-untyped]
        ChaikinMoneyFlowIndicator,
        OnBalanceVolumeIndicator,
        VolumeWeightedAveragePrice,
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
    n = len(series)
    length = max(1, min(int(length), n))
    return cast(
        pd.Series,
        EMAIndicator(close=series, window=length, fillna=True).ema_indicator(),
    )


def rsi(series: pd.Series, length: int) -> pd.Series:
    length = max(1, int(length))
    return cast(pd.Series, RSIIndicator(close=series, window=length, fillna=True).rsi())


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    n = len(df)
    length = max(1, min(int(length), n))
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
    n = len(df)
    # ADX needs at least 3 bars; for very short windows, return zeros safely
    if n < 3:
        return pd.Series([0.0] * n, index=df.index, dtype="float64")
    # Clamp window to available length to avoid internal indexing errors
    length = max(3, min(int(length), n))
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


def _resolve_parameter(param_value: Any, strategy_parameters: dict) -> Any:
    """Resolves a parameter value, substituting placeholders like ${param_name}."""
    if isinstance(param_value, str) and param_value.startswith("${") and param_value.endswith("}"):
        param_name = param_value[2:-1]
        if param_name in strategy_parameters:
            return strategy_parameters[param_name]
        else:
            raise ValueError(f"Parameter '{param_name}' not found in strategy parameters.")
    return param_value


def compute_features(
    df: pd.DataFrame, specs: list[dict], strategy_parameters: dict = None
) -> pd.DataFrame:
    """Compute features as configured in specs.

    Each spec: {name, type, params, source}
    Returns a DataFrame including original df plus new feature columns by name.
    """
    if strategy_parameters is None:
        strategy_parameters = {}

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

        # Resolve parameters for the current feature
        resolved_params = {
            k: _resolve_parameter(v, strategy_parameters) for k, v in params.items()
        }

        if typ == "EMA":
            length = int(resolved_params.get("length", 14))
            out[name] = ema(_price_series(df, source), length)
        elif typ == "SMA":
            length = int(resolved_params.get("length", 14))
            out[name] = cast(
                pd.Series,
                SMAIndicator(
                    close=_price_series(df, source), window=length, fillna=True
                ).sma_indicator(),
            )
        elif typ == "WMA":
            length = int(resolved_params.get("length", 14))
            out[name] = cast(
                pd.Series,
                WMAIndicator(
                    close=_price_series(df, source), window=length, fillna=True
                ).wma(),
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
            bb = BollingerBands(
                close=_price_series(df, source),
                window=int(resolved_params.get("length", 20)),
                window_dev=float(resolved_params.get("ndev", 2.0)),
                fillna=True,
            )
            out[f"{name}_upper"] = cast(pd.Series, bb.bollinger_hband())
            out[f"{name}_lower"] = cast(pd.Series, bb.bollinger_lband())
            out[f"{name}_middle"] = cast(pd.Series, bb.bollinger_mavg())
        elif typ == "BBWidth":
            out[name] = bb_width(
                _price_series(df, source),
                int(resolved_params.get("length", 20)),
                float(resolved_params.get("ndev", 2.0)),
            )
        elif typ == "MACD":
            macd = MACD(
                close=_price_series(df, source),
                window_slow=int(resolved_params.get("slow", 26)),
                window_fast=int(resolved_params.get("fast", 12)),
                window_sign=int(resolved_params.get("signal", 9)),
                fillna=True,
            )
            out[f"{name}_macd"] = cast(pd.Series, macd.macd())
            out[f"{name}_signal"] = cast(pd.Series, macd.macd_signal())
            out[f"{name}_diff"] = cast(pd.Series, macd.macd_diff())
        elif typ == "PSAR":
            psar = PSARIndicator(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                step=float(resolved_params.get("step", 0.02)),
                max_step=float(resolved_params.get("max", 0.2)),
                fillna=True,
            )
            out[f"{name}"] = cast(pd.Series, psar.psar())
            out[f"{name}_up"] = cast(pd.Series, psar.psar_up())
            out[f"{name}_down"] = cast(pd.Series, psar.psar_down())
        elif typ == "STOCH":
            st = StochasticOscillator(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                window=int(resolved_params.get("length", 14)),
                fillna=True,
            )
            out[f"{name}"] = cast(pd.Series, st.stoch())
            out[f"{name}_signal"] = cast(pd.Series, st.stoch_signal())
        elif typ == "CCI":
            out[name] = cast(
                pd.Series,
                CCIIndicator(
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    window=int(resolved_params.get("length", 20)),
                    fillna=True,
                ).cci(),
            )
        elif typ == "ROC":
            out[name] = cast(
                pd.Series,
                ROCIndicator(
                    close=_price_series(df, source),
                    window=int(resolved_params.get("length", 12)),
                    fillna=True,
                ).roc(),
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
        elif typ == "DC":
            up, lo = donchian_channels(df, int(resolved_params.get("length", 20)))
            out[f"{name}_upper"] = up
            out[f"{name}_lower"] = lo
        elif typ == "KC":
            kc = KeltnerChannel(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                window=int(resolved_params.get("length", 20)),
                window_atr=int(resolved_params.get("length", 20)),
                original_version=False,
                fillna=True,
            )
            out[f"{name}_upper"] = cast(pd.Series, kc.keltner_channel_hband())
            out[f"{name}_lower"] = cast(pd.Series, kc.keltner_channel_lband())
            out[f"{name}_middle"] = cast(pd.Series, kc.keltner_channel_mband())
        elif typ == "OBV":
            out[name] = cast(
                pd.Series,
                OnBalanceVolumeIndicator(
                    close=_price_series(df, source), volume=df["volume"], fillna=True
                ).on_balance_volume(),
            )
        elif typ == "CMF":
            out[name] = cast(
                pd.Series,
                ChaikinMoneyFlowIndicator(
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    volume=df["volume"],
                    window=int(resolved_params.get("length", 20)),
                    fillna=True,
                ).chaikin_money_flow(),
            )
        elif typ == "VWAP":
            out[name] = cast(
                pd.Series,
                VolumeWeightedAveragePrice(
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    volume=df["volume"],
                    fillna=True,
                ).vwap,
            )
        else:
            out[name] = pd.NA
    return out
