"""Exercise RMM classification branches that lacked coverage."""

from trading_platform.regime_market_manager.classification import classify_regime
from trading_platform.regime_market_manager.config import RegimeManagerConfig


def test_classify_regime_trend_down_high_confidence():
    """Test classify_regime for strong downward trend. Covers line 31."""
    config = RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )

    # High ADX with strong negative slope (downward trend)
    indicators = {
        "ADX(14)": 30.0,  # Above trend_threshold_high
        "EMA_Slope(50)": -0.8,  # Below -slope_threshold
    }

    result = classify_regime(indicators, config)

    assert result["regime"] == "trend_down"
    assert result["confidence"] == "high"


def test_classify_regime_low_adx_ranging():
    """Test classify_regime for low ADX ranging market. Covers line 38."""
    config = RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )

    # Low ADX indicating ranging market
    indicators = {
        "ADX(14)": 10.0,  # Below trend_threshold_low
        "EMA_Slope(50)": 0.2,  # Moderate slope
    }

    result = classify_regime(indicators, config)

    assert result["regime"] == "range"
    assert result["confidence"] == "medium"


def test_classify_regime_missing_indicators():
    """Test classify_regime with missing indicators (defaults to 0.0)."""
    config = RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )

    # Empty indicators dictionary - should use default values (0.0)
    indicators: dict[str, float] = {}

    result = classify_regime(indicators, config)

    # With ADX=0.0 (< trend_threshold_low), should classify as ranging
    assert result["regime"] == "range"
    assert result["confidence"] == "medium"


def test_classify_regime_trend_up_high_confidence():
    """Test classify_regime for strong upward trend."""
    config = RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )

    # High ADX with strong positive slope (upward trend)
    indicators = {
        "ADX(14)": 35.0,  # Above trend_threshold_high
        "EMA_Slope(50)": 0.8,  # Above slope_threshold
    }

    result = classify_regime(indicators, config)

    assert result["regime"] == "trend_up"
    assert result["confidence"] == "high"


def test_classify_regime_default_uncertain():
    """Test classify_regime for uncertain/default case."""
    config = RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )

    # Moderate ADX (between thresholds) with minimal slope
    indicators = {
        "ADX(14)": 20.0,  # Between trend_threshold_low and trend_threshold_high
        "EMA_Slope(50)": 0.2,  # Below slope_threshold
    }

    result = classify_regime(indicators, config)

    # Should fall through to default case
    assert result["regime"] == "range"
    assert result["confidence"] == "low"
