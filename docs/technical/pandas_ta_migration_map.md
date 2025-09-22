# `ta` to `pandas-ta` Migration Map

This document provides the mapping from the old `ta` library indicators to the new `pandas-ta` library equivalents. It notes differences in parameters, function calls, and expected output.

- **Parameter Convention**: `ta` commonly uses `window` for the period length, whereas `pandas-ta` consistently uses `length`.
- **Call Style**: `ta` uses indicator-specific classes that must be instantiated (e.g., `SMAIndicator(close, window=14).sma_indicator()`). `pandas-ta` can be called directly on a DataFrame's `ta` accessor (e.g., `df.ta.sma(length=14)`).
- **Output Naming**: `pandas-ta` produces predictable column names (e.g., `SMA_14`), which is an improvement over `ta`.

---

| Indicator | `ta` Class | `pandas-ta` Function | Parameter Differences | Notes |
|:--- |:--- |:--- |:--- |:--- |
| **SMA** | `ta.trend.SMAIndicator` | `pandas_ta.sma` | `window` -> `length` | |
| **EMA** | `ta.trend.EMAIndicator` | `pandas_ta.ema` | `window` -> `length` | `pandas-ta` has an `adjust` parameter that may affect calculations. |
| **WMA** | `ta.trend.WMAIndicator` | `pandas_ta.wma` | `window` -> `length` | |
| **MACD** | `ta.trend.MACD` | `pandas_ta.macd` | `window_slow` -> `fast`, `window_fast` -> `slow`, `window_sign` -> `signal` | `pandas-ta` parameter names are more conventional. |
| **PSAR** | `ta.trend.PSARIndicator` | `pandas_ta.psar` | `step` -> `af0`, `max_step` -> `af` | `pandas-ta` uses different names for acceleration factor parameters. |
| **ADX** | `ta.trend.ADXIndicator` | `pandas_ta.adx` | `window` -> `length` | |
| **RSI** | `ta.momentum.RSIIndicator` | `pandas_ta.rsi` | `window` -> `length` | |
| **STOCH** | `ta.momentum.StochasticOscillator` | `pandas_ta.stoch` | `window` -> `k`, `smooth_window` -> `d` | `pandas-ta` uses `k` and `d` for the two main periods. |
| **CCI** | `ta.trend.CCIIndicator` | `pandas_ta.cci` | `window` -> `length` | |
| **ROC** | `ta.momentum.ROCIndicator` | `pandas_ta.roc` | `window` -> `length` | |
| **BB** | `ta.volatility.BollingerBands` | `pandas_ta.bbands` | `window` -> `length`, `window_dev` -> `std` | `pandas-ta` uses `std` for standard deviation. |
| **BBWidth** | `ta.volatility.BollingerBands` | `pandas_ta.bbands` | `window` -> `length`, `window_dev` -> `std` | Derived from `bbands` output. `pandas-ta` provides `BBB_` column. |
| **ATR** | `ta.volatility.AverageTrueRange` | `pandas_ta.atr` | `window` -> `length` | |
| **KC** | `ta.volatility.KeltnerChannel` | `pandas_ta.kc` | `window` -> `length` | `pandas-ta` implementation is more standard. |
| **OBV** | `ta.volume.OnBalanceVolumeIndicator` | `pandas_ta.obv` | None | |
| **CMF** | `ta.volume.ChaikinMoneyFlowIndicator` | `pandas_ta.cmf` | `window` -> `length` | |
| **VWAP** | `ta.volume.VolumeWeightedAveragePrice` | `pandas_ta.vwap` | `window` -> `length` | `pandas-ta` requires a `length` for anchored VWAP. |
