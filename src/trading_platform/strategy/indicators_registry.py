from __future__ import annotations

# Safety levels: safe, validated, requires_test
# See strategy/indicator_safety.py for details

INDICATORS: dict[str, dict] = {
    # Moving Averages
    "SMA": {
        "display": "Simple Moving Average",
        "category": "trend",
        "description": "Average of prices over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.overlap",
            "function": "sma",
        },
    },
    "EMA": {
        "display": "Exponential Moving Average",
        "category": "trend",
        "description": "Exponentially weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.overlap",
            "function": "ema",
        },
    },
    "EMASlope": {
        "display": "EMA Slope",
        "category": "trend",
        "description": "Rate of change (slope) of the EMA.",
        "params": [
            {"name": "length", "type": "int", "default": 14},
            {"name": "slope_period", "type": "int", "default": 1},
        ],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "WMA": {
        "display": "Weighted Moving Average",
        "category": "trend",
        "description": "Linearly weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.overlap",
            "function": "wma",
        },
    },
    # Oscillators
    "MACD": {
        "display": "MACD",
        "category": "momentum",
        "description": "Difference of fast/slow EMAs with signal.",
        "params": [
            {"name": "fast", "type": "int", "default": 12},
            {"name": "slow", "type": "int", "default": 26},
            {"name": "signal", "type": "int", "default": 9},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "macd",
        },
    },
    "PSAR": {
        "display": "Parabolic SAR",
        "category": "trend",
        "description": "Stops and reversals indicator.",
        "params": [
            {"name": "step", "type": "float", "default": 0.02},
            {"name": "max_step", "type": "float", "default": 0.2},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.trend",
            "function": "psar",
        },
    },
    "ADX": {
        "display": "Average Directional Index",
        "category": "trend",
        "description": "Strength of a trend.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.trend",
            "function": "adx",
        },
    },
    "RSI": {
        "display": "Relative Strength Index",
        "category": "momentum",
        "description": "Momentum oscillator 0–100.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "rsi",
        },
    },
    "STOCH": {
        "display": "Stochastic Oscillator",
        "category": "momentum",
        "description": "%K oscillator.",
        "params": [
            {"name": "k", "type": "int", "default": 14},
            {"name": "d", "type": "int", "default": 3},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "stoch",
        },
    },
    "CCI": {
        "display": "Commodity Channel Index",
        "category": "momentum",
        "description": "Deviation from typical price.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "cci",
        },
    },
    "ROC": {
        "display": "Rate of Change",
        "category": "momentum",
        "description": "Percentage change over a period.",
        "params": [{"name": "length", "type": "int", "default": 12}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "roc",
        },
    },
    "CHOP": {
        "display": "Chop Index",
        "category": "momentum",
        "description": "Determines if the market is choppy (sideways) or trending.",
        "params": [
            {"name": "length", "type": "int", "default": 14},
            {"name": "atr_length", "type": "int", "default": 1},
            {"name": "scalar", "type": "float", "default": 100},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "chop",
        },
    },
    # Volatility / bands & channels
    "BB": {
        "display": "Bollinger Bands",
        "category": "volatility",
        "description": "Upper/lower/middle bands computed from price.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "std", "type": "float", "default": 2.0},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "bbands",
        },
    },
    "BBWidth": {
        "display": "Bollinger Bands Width",
        "category": "volatility",
        "description": "Normalized width of Bollinger Bands.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "std", "type": "float", "default": 2.0},
        ],
        "safety": "validated",
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "bbands",
        },
    },
    "ATR": {
        "display": "Average True Range",
        "category": "volatility",
        "description": "Average of true ranges over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "atr",
        },
    },
    "ATRPercentile": {
        "display": "ATR Percentile",
        "category": "volatility",
        "description": "Percentile rank of ATR over lookback period.",
        "params": [
            {"name": "atr_length", "type": "int", "default": 14},
            {"name": "lookback", "type": "int", "default": 20},
        ],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "KC": {
        "display": "Keltner Channels Width",
        "category": "volatility",
        "description": "Normalized width of Keltner Channels.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "mult", "type": "float", "default": 2.0},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "kc",
        },
    },
    # Volume/flow
    "OBV": {
        "display": "On-Balance Volume",
        "category": "volume",
        "description": "Cumulative volume adjusted by price direction.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volume",
            "function": "obv",
        },
    },
    "CMF": {
        "display": "Chaikin Money Flow",
        "category": "volume",
        "description": "Money flow over a window.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volume",
            "function": "cmf",
        },
    },
    "RealizedVolatility": {
        "display": "Realized Volatility",
        "category": "volatility",
        "description": "Standard deviation of log returns.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "VolumeZScore": {
        "display": "Volume Z-Score",
        "category": "volume",
        "description": "Z-score of volume relative to rolling mean.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "ICHIMOKU": {
        "display": "Ichimoku Cloud",
        "category": "trend",
        "description": "All-in-one trend indicator with support/resistance levels.",
        "params": [
            {"name": "tenkan", "type": "int", "default": 9},
            {"name": "kijun", "type": "int", "default": 26},
            {"name": "senkou", "type": "int", "default": 52},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.trend",
            "function": "ichimoku",
        },
    },
    "SUPERTREND": {
        "display": "SuperTrend",
        "category": "trend",
        "description": (
            "Popular trend-following indicator used for " "trend direction and stops."
        ),
        "params": [
            {"name": "length", "type": "int", "default": 7},
            {"name": "multiplier", "type": "float", "default": 3.0},
        ],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.trend",
            "function": "supertrend",
        },
    },
    "VWAP": {
        "display": "Volume Weighted Average Price",
        "category": "price",
        "description": "Intraday average price weighted by volume.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.volume",
            "function": "vwap",
        },
    },
    # Derived / composite
    "FIB": {
        "display": "Fibonacci Retracement Levels",
        "category": "levels",
        "description": "Key retracement levels between swing high/low.",
        "params": [{"name": "window", "type": "int", "default": 100}],
        "safety": "requires_test",
        "ta": {"module": "", "class": ""},  # custom implementation TBD
    },
    "HHV": {
        "display": "Highest High Value",
        "category": "levels",
        "description": "Rolling maximum over a window (e.g., 20-day high).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "ta": {"module": "", "class": ""},
    },
    "LLV": {
        "display": "Lowest Low Value",
        "category": "levels",
        "description": "Rolling minimum over a window (e.g., 20-day low).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "ta": {"module": "", "class": ""},
    },
    "SWING_HIGH": {
        "display": "Swing High",
        "category": "levels",
        "description": "Detects a swing high point (a local maximum).",
        "params": [
            {"name": "left_bars", "type": "int", "default": 10},
            {"name": "right_bars", "type": "int", "default": 10},
        ],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "SWING_LOW": {
        "display": "Swing Low",
        "category": "levels",
        "description": "Detects a swing low point (a local minimum).",
        "params": [
            {"name": "left_bars", "type": "int", "default": 10},
            {"name": "right_bars", "type": "int", "default": 10},
        ],
        "safety": "validated",
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "DC": {
        "display": "Donchian Channels",
        "category": "levels",
        "description": (
            "Upper/lower bands from rolling high/low; exposes name_upper/name_lower"
        ),
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "ta": {"module": "", "class": ""},
    },
    # Candlestick Patterns
    "CDL_DOJI": {
        "display": "Doji",
        "category": "pattern",
        "description": "Detects a Doji candlestick pattern (indecision).",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_doji",
        },
    },
    "CDL_HAMMER": {
        "display": "Hammer / Hanging Man",
        "category": "pattern",
        "description": "Detects Hammer (bullish) or Hanging Man (bearish) patterns.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_hammer",
        },
    },
    "CDL_ENGULFING": {
        "display": "Engulfing",
        "category": "pattern",
        "description": "Detects Bullish or Bearish Engulfing patterns.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_engulfing",
        },
    },
    "CDL_MORNINGSTAR": {
        "display": "Morning Star",
        "category": "pattern",
        "description": "Detects the Morning Star (bullish) reversal pattern.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_morningstar",
        },
    },
    "CDL_EVENINGSTAR": {
        "display": "Evening Star",
        "category": "pattern",
        "description": "Detects the Evening Star (bearish) reversal pattern.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_eveningstar",
        },
    },
    "CDL_HARAMI": {
        "display": "Harami",
        "category": "pattern",
        "description": "Detects Harami (inside bar) reversal patterns.",
        "params": [],
        "safety": "safe",
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_harami",
        },
    },
}
