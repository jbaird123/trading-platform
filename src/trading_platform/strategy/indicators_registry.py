"""
Unified Indicator Registry.

This module provides the single source of truth for all technical indicators,
including their metadata, implementations, and safety classifications.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from trading_platform.strategy import indicator_implementations as impl

if TYPE_CHECKING:
    import pandas as pd


class SafetyLevel(Enum):
    """Safety classification for indicators to prevent look-ahead bias."""

    SAFE = "safe"
    # Proven safe through testing or review.
    # Built-in library indicators with known safe implementations.

    VALIDATED = "validated"
    # Custom indicators that have been manually reviewed
    # and validated to be free from look-ahead bias.

    REQUIRES_TEST = "requires_test"
    # New or untrusted indicators that must pass automated
    # bias detection before being used.


INDICATORS: dict[str, dict] = {
    # Moving Averages
    "SMA": {
        "display": "Simple Moving Average",
        "category": "trend",
        "description": "Average of prices over a window.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "implementation": impl.compute_sma,
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
        "implementation": impl.compute_ema,
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
        "implementation": impl.compute_ema_slope,
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "EMASlopePct": {
        "display": "EMA Slope Percent",
        "category": "trend",
        "description": "EMA slope expressed as percent of EMA value.",
        "params": [
            {"name": "length", "type": "int", "default": 14},
            {"name": "slope_period", "type": "int", "default": 1},
        ],
        "safety": "validated",
        "implementation": impl.compute_ema_slope_pct,
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "WMA": {
        "display": "Weighted Moving Average",
        "category": "trend",
        "description": "Linearly weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "implementation": impl.compute_wma,
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
        "implementation": impl.compute_macd,
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
        "implementation": impl.compute_psar,
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
        "implementation": impl.compute_adx,
        "ta": {
            "module": "pandas_ta.trend",
            "function": "adx",
        },
    },
    "ADXStrength": {
        "display": "ADX Strength",
        "category": "trend",
        "description": "ADX scaled to a 0-1 strength score.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "validated",
        "implementation": impl.compute_adx_strength,
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "RSI": {
        "display": "Relative Strength Index",
        "category": "momentum",
        "description": "Momentum oscillator 0–100.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "safe",
        "implementation": impl.compute_rsi,
        "ta": {
            "module": "pandas_ta.momentum",
            "function": "rsi",
        },
    },
    "RSIBias": {
        "display": "RSI Bias",
        "category": "momentum",
        "description": "RSI normalised to [-1, 1] to show bias.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "validated",
        "implementation": impl.compute_rsi_bias,
        "ta": {"module": "", "class": ""},  # custom implementation
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
        "implementation": impl.compute_stoch,
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
        "implementation": impl.compute_cci,
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
        "implementation": impl.compute_roc,
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
        "safety": "validated",  # Custom implementation - bias tested
        "implementation": impl.compute_chop,
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
        "implementation": impl.compute_bb,
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
        "implementation": impl.compute_bb_width,
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
        "implementation": impl.compute_atr,
        "ta": {
            "module": "pandas_ta.volatility",
            "function": "atr",
        },
    },
    "ATRPercent": {
        "display": "ATR Percent",
        "category": "volatility",
        "description": "ATR expressed as a percentage of price.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "validated",
        "implementation": impl.compute_atr_percent,
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "EMATrendAlignment": {
        "display": "EMA Trend Alignment",
        "category": "trend",
        "description": "Alignment metrics for EMA slopes across timeframes.",
        "params": [
            {"name": "timeframes", "type": "list", "default": []},
            {"name": "length", "type": "int", "default": 50},
            {"name": "slope_period", "type": "int", "default": 1},
        ],
        "safety": "validated",
        "implementation": impl.compute_ema_trend_alignment,
        "ta": {"module": "", "class": ""},  # custom implementation
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
        "implementation": impl.compute_atr_percentile,
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
        "implementation": impl.compute_kc,
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
        "implementation": impl.compute_obv,
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
        "implementation": impl.compute_cmf,
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
        "implementation": impl.compute_realized_volatility,
        "ta": {"module": "", "class": ""},  # custom implementation
    },
    "VolumeZScore": {
        "display": "Volume Z-Score",
        "category": "volume",
        "description": "Z-score of volume relative to rolling mean.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "implementation": impl.compute_volume_zscore,
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
        "implementation": impl.compute_ichimoku,
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
        "safety": "validated",  # Custom implementation - bias tested
        "implementation": impl.compute_supertrend,
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
        "implementation": impl.compute_vwap,
        "ta": {
            "module": "pandas_ta.volume",
            "function": "vwap",
        },
    },
    # Derived / composite
    "FIB": {
        "display": "Fibonacci Retracement Levels",
        "category": "levels",
        "description": (
            "Key retracement levels between swing high/low "
            "(7 levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)."
        ),
        "params": [
            {"name": "left_bars", "type": "int", "default": 5},
            {"name": "right_bars", "type": "int", "default": 5},
        ],
        "safety": "validated",  # Uses validated find_swing_points() - bias tested
        "implementation": impl.compute_fib,
        "ta": {"module": "", "class": ""},  # custom implementation
        "multi_output": True,  # Returns dict of 7 Fibonacci levels
    },
    "HHV": {
        "display": "Highest High Value",
        "category": "levels",
        "description": "Rolling maximum over a window (e.g., 20-day high).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "implementation": impl.compute_hhv,
        "ta": {"module": "", "class": ""},
    },
    "LLV": {
        "display": "Lowest Low Value",
        "category": "levels",
        "description": "Rolling minimum over a window (e.g., 20-day low).",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",
        "implementation": impl.compute_llv,
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
        "implementation": impl.compute_swing_high,
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
        "implementation": impl.compute_swing_low,
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
        "implementation": impl.compute_dc,
        "ta": {"module": "", "class": ""},
    },
    # Candlestick Patterns
    "CDL_DOJI": {
        "display": "Doji",
        "category": "pattern",
        "description": "Detects a Doji candlestick pattern (indecision).",
        "params": [],
        "safety": "safe",
        "implementation": impl.compute_cdl_doji,
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
        "implementation": impl.compute_cdl_hammer,
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
        "implementation": impl.compute_cdl_engulfing,
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
        "implementation": impl.compute_cdl_morningstar,
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
        "implementation": impl.compute_cdl_eveningstar,
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
        "implementation": impl.compute_cdl_harami,
        "ta": {
            "module": "pandas_ta.candles",
            "function": "cdl_harami",
        },
    },
}


# ==============================================================================
# Safety Helper Functions
# ==============================================================================


def get_safety_level(indicator_type: str) -> SafetyLevel:
    """
    Get the safety level for an indicator type.

    Args:
        indicator_type: Indicator type name (e.g., 'EMA', 'SWING_HIGH')

    Returns:
        SafetyLevel for the indicator (REQUIRES_TEST if not in registry)

    Example:
        >>> get_safety_level('EMA')
        SafetyLevel.SAFE
        >>> get_safety_level('SWING_HIGH')
        SafetyLevel.VALIDATED
    """
    indicator = INDICATORS.get(indicator_type)
    if not indicator:
        return SafetyLevel.REQUIRES_TEST
    safety_str = indicator.get("safety", "requires_test")
    return SafetyLevel(safety_str)


def is_indicator_safe(indicator_type: str) -> bool:
    """
    Check if an indicator is safe to use without testing.

    Args:
        indicator_type: Indicator type name

    Returns:
        True if indicator is SAFE or VALIDATED

    Example:
        >>> is_indicator_safe('EMA')
        True
        >>> is_indicator_safe('UNKNOWN_INDICATOR')
        False
    """
    level = get_safety_level(indicator_type)
    return level in (SafetyLevel.SAFE, SafetyLevel.VALIDATED)


def requires_bias_test(indicator_type: str) -> bool:
    """
    Check if indicator requires bias detection testing.

    Args:
        indicator_type: Indicator type name

    Returns:
        True if indicator requires testing before use

    Example:
        >>> requires_bias_test('EMA')
        False
        >>> requires_bias_test('FIB')
        True
    """
    level = get_safety_level(indicator_type)
    return level == SafetyLevel.REQUIRES_TEST


class LookAheadBiasError(Exception):
    """Raised when an indicator fails bias detection."""

    pass


def validate_indicator_safety(
    indicator_type: str,
    test_data: pd.DataFrame | None = None,
) -> None:
    """
    Validate that an indicator is safe to use.

    Args:
        indicator_type: Indicator type name
        test_data: Optional test data for bias detection
                   (required if indicator REQUIRES_TEST)

    Raises:
        LookAheadBiasError: If indicator requires testing but fails

    Example:
        >>> validate_indicator_safety('EMA')  # Safe, no error
        >>> validate_indicator_safety('UNKNOWN', test_data)  # May raise
    """
    level = get_safety_level(indicator_type)

    if level in (SafetyLevel.SAFE, SafetyLevel.VALIDATED):
        # Already verified safe
        return

    if level == SafetyLevel.REQUIRES_TEST:
        # Need to run bias detection
        if test_data is None:
            raise LookAheadBiasError(
                f"Indicator '{indicator_type}' requires bias "
                f"detection testing but no test data provided. "
                f"Either:\n"
                f"1. Add it to INDICATORS registry as SAFE/VALIDATED\n"
                f"2. Provide test_data for automatic validation\n"
                f"3. Run tests in tests/strategy/"
                f"test_indicator_bias_detection.py"
            )

        # This would need the actual indicator function
        # For now, we raise an error indicating manual testing needed
        raise LookAheadBiasError(
            f"Indicator '{indicator_type}' is not classified as safe. "
            f"Please run bias detection tests in "
            f"tests/strategy/test_indicator_bias_detection.py "
            f"and update INDICATORS registry if it passes."
        )


def get_safety_summary() -> dict[str, list[str]]:
    """
    Get a summary of all indicators by safety level.

    Returns:
        Dict mapping safety level names to lists of indicators

    Example:
        >>> summary = get_safety_summary()
        >>> print(f"Safe: {len(summary['safe'])} indicators")
    """
    summary: dict[str, list[str]] = {
        "safe": [],
        "validated": [],
        "requires_test": [],
    }

    for indicator_name, indicator_data in INDICATORS.items():
        safety_str = indicator_data.get("safety", "requires_test")
        summary[safety_str].append(indicator_name)

    return summary
