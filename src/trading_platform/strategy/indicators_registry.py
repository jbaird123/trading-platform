from __future__ import annotations

INDICATORS: dict[str, dict] = {
    # Moving Averages
    "SMA": {
        "display": "Simple Moving Average",
        "category": "trend",
        "description": "Average of prices over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.trend", "class": "SMAIndicator"},
    },
    "EMA": {
        "display": "Exponential Moving Average",
        "category": "trend",
        "description": "Exponentially weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.trend", "class": "EMAIndicator"},
    },
    "WMA": {
        "display": "Weighted Moving Average",
        "category": "trend",
        "description": "Linearly weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.trend", "class": "WMAIndicator"},
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
        "ta": {"module": "ta.trend", "class": "MACD"},
    },
    "PSAR": {
        "display": "Parabolic SAR",
        "category": "trend",
        "description": "Stops and reversals indicator.",
        "params": [
            {"name": "step", "type": "float", "default": 0.02},
            {"name": "max", "type": "float", "default": 0.2},
        ],
        "ta": {"module": "ta.trend", "class": "PSARIndicator"},
    },
    "ADX": {
        "display": "Average Directional Index",
        "category": "trend",
        "description": "Strength of a trend.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.trend", "class": "ADXIndicator"},
    },
    "RSI": {
        "display": "Relative Strength Index",
        "category": "momentum",
        "description": "Momentum oscillator 0–100.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.momentum", "class": "RSIIndicator"},
    },
    "STOCH": {
        "display": "Stochastic Oscillator",
        "category": "momentum",
        "description": "%K oscillator.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.momentum", "class": "StochasticOscillator"},
    },
    "CCI": {
        "display": "Commodity Channel Index",
        "category": "momentum",
        "description": "Deviation from typical price.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "ta": {"module": "ta.trend", "class": "CCIIndicator"},
    },
    "ROC": {
        "display": "Rate of Change",
        "category": "momentum",
        "description": "Percentage change over a period.",
        "params": [{"name": "length", "type": "int", "default": 12}],
        "ta": {"module": "ta.momentum", "class": "ROCIndicator"},
    },
    # Volatility / bands & channels
    "BB": {
        "display": "Bollinger Bands",
        "category": "volatility",
        "description": "Upper/lower/middle bands computed from price.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "ndev", "type": "float", "default": 2.0},
        ],
        "ta": {"module": "ta.volatility", "class": "BollingerBands"},
    },
    "BBWidth": {
        "display": "Bollinger Bands Width",
        "category": "volatility",
        "description": "Normalized width of Bollinger Bands.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "ndev", "type": "float", "default": 2.0},
        ],
        "ta": {"module": "ta.volatility", "class": "BollingerBands"},
    },
    "ATR": {
        "display": "Average True Range",
        "category": "volatility",
        "description": "Average of true ranges over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "ta": {"module": "ta.volatility", "class": "AverageTrueRange"},
    },
    "KC": {
        "display": "Keltner Channels Width",
        "category": "volatility",
        "description": "Normalized width of Keltner Channels.",
        "params": [
            {"name": "length", "type": "int", "default": 20},
            {"name": "mult", "type": "float", "default": 2.0},
        ],
        "ta": {"module": "ta.volatility", "class": "KeltnerChannel"},
    },
    # Volume/flow
    "OBV": {
        "display": "On-Balance Volume",
        "category": "volume",
        "description": "Cumulative volume adjusted by price direction.",
        "params": [],
        "ta": {"module": "ta.volume", "class": "OnBalanceVolumeIndicator"},
    },
    "CMF": {
        "display": "Chaikin Money Flow",
        "category": "volume",
        "description": "Money flow over a window.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "ta": {"module": "ta.volume", "class": "ChaikinMoneyFlowIndicator"},
    },
    "VWAP": {
        "display": "Volume Weighted Average Price",
        "category": "price",
        "description": "Intraday average price weighted by volume.",
        "params": [],
        "ta": {"module": "ta.volume", "class": "VolumeWeightedAveragePrice"},
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
