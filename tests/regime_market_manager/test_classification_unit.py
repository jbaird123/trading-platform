# Validates: [RMM-4.1], [RMM-4.3]
from __future__ import annotations

from trading_platform.regime_market_manager.classification import classify_regime
from trading_platform.regime_market_manager.config import RegimeManagerConfig


def test_trend_down_when_adx_high_and_slope_negative():
    cfg = RegimeManagerConfig()
    indicators = {
        cfg.trend_indicator: cfg.trend_threshold_high + 1.0,
        cfg.slope_indicator: -cfg.slope_threshold - 0.01,
    }
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "trend_down" and out["confidence"] == "high"


def test_default_uncertain_when_adx_between_thresholds():
    cfg = RegimeManagerConfig()
    # ADX between low and high; slope near zero → default/uncertain case
    indicators = {
        cfg.trend_indicator: (cfg.trend_threshold_low + cfg.trend_threshold_high) / 2.0,
        cfg.slope_indicator: 0.0,
    }
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "range" and out["confidence"] == "low"


def test_high_adx_neutral_slope_falls_through_to_default_low():
    cfg = RegimeManagerConfig()
    indicators = {
        cfg.trend_indicator: cfg.trend_threshold_high + 5.0,
        cfg.slope_indicator: 0.0,
    }
    out = classify_regime(indicators, cfg)
    assert out["regime"] == "range" and out["confidence"] == "low"
