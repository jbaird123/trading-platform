from __future__ import annotations

INDICATORS: dict[str, dict] = {
    # Moving Averages
    "SMA": {
        "display": "Simple Moving Average",
        "category": "trend",
        "description": "Average of prices over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
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
        "ta": {
            "module": "pandas_ta.overlap",
            "function": "ema",
        },
    },
    "WMA": {
        "display": "Weighted Moving Average",
        "category": "trend",
        "description": "Linearly weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
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
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "atr",
        },
    },
    "KC": {
        "display": "Keltner Channels Width",
        "category": "volatility",
        "description": "Normalized width of Keltner Channels.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "mult", "type": "float", "default": 2.0},
        ],
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
        "ta": {
            "module": "pandas_ta.volume",
            "function": "cmf",
        },
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
        "ta": {
            "module": "pandas_ta.trend",
            "function": "ichimoku",
        },
    },
    "SUPERTREND": {
        "display": "SuperTrend",
        "category": "trend",
        "description": "Popular trend-following indicator used for trend direction and stops.",
        "params": [
            {"name": "length", "type": "int", "default": 7},
            {"name": "multiplier", "type": "float", "default": 3.0},
        ],
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
        "ta": {"module": "", "class": ""},  # custom implementation TBD
    },
    "HHV": {
        "display": "Highest High Value",
        "category": "levels",
        "description": "Rolling maximum over a window (e.g., 20-day high).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "ta": {"module": "", "class": ""},
    },
    "LLV": {
        "display": "Lowest Low Value",
        "category": "levels",
        "description": "Rolling minimum over a window (e.g., 20-day low).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "ta": {"module": "", "class": ""},
    },
    "DC": {
        "display": "Donchian Channels",
        "category": "levels",
        "description": (
            "Upper/lower bands from rolling high/low; exposes name_upper/name_lower"
        ),
        "params": [{"name": "length", "type": "int", "default": 20}],
        "ta": {"module": "", "class": ""},
    },
}
