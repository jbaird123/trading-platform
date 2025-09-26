"""Consolidated tests for RMM classification logic."""
from __future__ import annotations

from trading_platform.regime_market_manager.classification import classify_regime
from trading_platform.regime_market_manager.config import RegimeManagerConfig

# --- Unit behaviour coverage -----------------------------------------------------

def test_trend_down_when_adx_high_and_slope_negative() -> None:
    cfg = RegimeManagerConfig()
    indicators = {
        cfg.trend_indicator: cfg.trend_threshold_high + 1.0,
        cfg.slope_indicator: -cfg.slope_threshold - 0.01,
    }
    result = classify_regime(indicators, cfg)
    assert result["regime"] == "trend_down"
    assert result["confidence"] == "high"


def test_default_uncertain_when_adx_between_thresholds() -> None:
    cfg = RegimeManagerConfig()
    indicators = {
        cfg.trend_indicator: (cfg.trend_threshold_low + cfg.trend_threshold_high) / 2.0,
        cfg.slope_indicator: 0.0,
    }
    result = classify_regime(indicators, cfg)
    assert result["regime"] == "range"
    assert result["confidence"] == "low"


def test_high_adx_neutral_slope_falls_through_to_range() -> None:
    cfg = RegimeManagerConfig()
    indicators = {
        cfg.trend_indicator: cfg.trend_threshold_high + 5.0,
        cfg.slope_indicator: 0.0,
    }
    result = classify_regime(indicators, cfg)
    assert result["regime"] == "range"
    assert result["confidence"] == "low"


# --- Additional branch coverage --------------------------------------------------

def _base_config() -> RegimeManagerConfig:
    return RegimeManagerConfig(
        trend_indicator="ADX(14)",
        slope_indicator="EMA_Slope(50)",
        trend_threshold_high=25.0,
        trend_threshold_low=15.0,
        slope_threshold=0.5,
    )


def test_strong_downtrend_high_confidence() -> None:
    cfg = _base_config()
    indicators = {"ADX(14)": 30.0, "EMA_Slope(50)": -0.8}
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "trend_down"
    assert out["confidence"] == "high"


def test_low_adx_range_medium_confidence() -> None:
    cfg = _base_config()
    indicators = {"ADX(14)": 10.0, "EMA_Slope(50)": 0.2}
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "range"
    assert out["confidence"] == "medium"


def test_missing_indicators_default_to_range() -> None:
    cfg = _base_config()
    out = classify_regime({}, cfg)
    assert out["regime"] == "range"
    assert out["confidence"] == "medium"


def test_strong_uptrend_high_confidence() -> None:
    cfg = _base_config()
    indicators = {"ADX(14)": 35.0, "EMA_Slope(50)": 0.8}
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "trend_up"
    assert out["confidence"] == "high"


def test_range_low_confidence_between_thresholds() -> None:
    cfg = _base_config()
    indicators = {"ADX(14)": 20.0, "EMA_Slope(50)": 0.2}
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "range"
    assert out["confidence"] == "low"

