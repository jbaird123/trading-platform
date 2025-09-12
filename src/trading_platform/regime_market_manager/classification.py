from __future__ import annotations

from typing import Any

from trading_platform.regime_market_manager.config import RegimeManagerConfig


def classify_regime(
    indicators: dict[str, Any], config: RegimeManagerConfig
) -> dict[str, Any]:
    """
    Classifies the market regime based on a dictionary of indicator values.

    This is a baseline rule-based implementation.

    Args:
        indicators: A dictionary where keys are indicator names (e.g., "ADX(14)")
                    and values are their current numerical values.
        config: The configuration object with thresholds and indicator names.

    Returns:
        A dictionary containing the 'regime' label and 'confidence'.
    """
    # A simple rule-based classifier. The order of rules matters.
    adx = indicators.get(config.trend_indicator, 0.0)
    ema_slope = indicators.get(config.slope_indicator, 0.0)

    # Rule for strong trending regime (high ADX)
    if adx > config.trend_threshold_high:
        if ema_slope > config.slope_threshold:  # Threshold for a clear upward slope
            return {"regime": "trend_up", "confidence": "high"}
        if ema_slope < -config.slope_threshold:  # Threshold for a clear downward slope
            return {"regime": "trend_down", "confidence": "high"}

    # Rule for ranging regime (low ADX)
    if adx < config.trend_threshold_low:
        # We could add more checks here (e.g., on BB_width) for more confidence
        return {"regime": "range", "confidence": "medium"}

    # Default/uncertain case
    return {"regime": "range", "confidence": "low"}
