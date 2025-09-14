from __future__ import annotations

from pydantic import BaseModel, Field


class RegimeManagerConfig(BaseModel):
    """
    Configuration for the rule-based Regime Market Manager.
    """

    trend_indicator: str = Field(
        default="ADX(14)", description="Indicator used to measure trend strength."
    )
    trend_threshold_high: float = Field(
        default=25.0,
        description="ADX value above which a strong trend is considered.",
    )
    trend_threshold_low: float = Field(
        default=20.0,
        description="ADX value below which a ranging market is considered.",
    )
    slope_indicator: str = Field(
        default="EMA(200)_slope", description="Indicator for trend direction."
    )
    slope_threshold: float = Field(
        default=0.1,
        description="Absolute slope value to confirm trend direction.",
    )
