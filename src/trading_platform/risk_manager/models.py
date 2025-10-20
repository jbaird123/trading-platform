"""Pydantic models for REM configuration validation.

This module provides strict validation for Risk and Exit Manager (REM)
configurations using Pydantic with `extra="forbid"` to prevent silent failures
from typos or unimplemented features.

All REM configurations must be validated through these models to ensure:
1. Only implemented indicators are allowed
2. Required parameters are present
3. Parameter types are correct
4. No extra/unknown fields are present
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class FixedPipStop(BaseModel):
    """Fixed pip-based stop or take-profit rule.

    This rule defines an exit at a fixed pip distance from entry price.
    The platform will convert pips to price units based on the instrument's pip size.

    Example:
        {
            "type": "fixed_pips",
            "pips": 20
        }
    """

    model_config = {"extra": "forbid"}

    type: Literal["fixed_pips"]
    pips: Annotated[float, Field(gt=0, description="Distance in pips from entry price")]


class ATRStopParams(BaseModel):
    """Parameters for ATR-based stops.

    ATR (Average True Range) is a volatility indicator. The stop distance is
    calculated as: distance = ATR(length) * multiplier

    Example:
        {
            "length": 14,
            "multiplier": 2.0
        }
    """

    model_config = {"extra": "forbid"}

    length: Annotated[int, Field(ge=1, description="ATR lookback period in bars")] = 14
    multiplier: Annotated[
        float, Field(gt=0, description="Multiplier applied to ATR value")
    ]


class IndicatorStop(BaseModel):
    """Indicator-based stop or take-profit rule.

    Uses a whitelisted indicator to calculate stop distance dynamically based on
    market conditions (e.g., volatility).

    Only indicators explicitly registered in REM_INDICATORS_REGISTRY are allowed.

    Example:
        {
            "type": "indicator",
            "indicator": "atr",
            "params": {
                "length": 14,
                "multiplier": 2.0
            }
        }
    """

    model_config = {"extra": "forbid"}

    type: Literal["indicator"]
    indicator: Literal["atr", "bollinger", "keltner"]
    # Future: Union[ATRStopParams, BollingerStopParams, KeltnerStopParams]
    params: ATRStopParams


class REMConfig(BaseModel):
    """Risk and Exit Manager configuration.

    Defines stop-loss and optional take-profit rules for position management.

    At minimum, a stop_loss rule must be provided. Take-profit is optional.

    Example (fixed pips):
        {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            }
        }

    Example (ATR-based):
        {
            "name": "Conservative ATR",
            "version": "1.0",
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {
                    "length": 14,
                    "multiplier": 2.0
                }
            },
            "take_profit": {
                "type": "fixed_pips",
                "pips": 40
            }
        }
    """

    model_config = {"extra": "forbid"}

    name: str | None = None
    version: str | None = None
    stop_loss: FixedPipStop | IndicatorStop = Field(..., discriminator="type")
    take_profit: FixedPipStop | IndicatorStop | None = Field(
        default=None, discriminator="type"
    )


__all__ = [
    "REMConfig",
    "FixedPipStop",
    "IndicatorStop",
    "ATRStopParams",
]
