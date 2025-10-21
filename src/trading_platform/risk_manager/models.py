"""Pydantic models for strict REM configuration validation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

import trading_platform.risk_manager.rem_indicators as rem_indicators


class _StrictModel(BaseModel):
    """Mixin enforcing `extra = forbid` on all REM models."""

    model_config = {"extra": "forbid"}


class AbsoluteLevelRule(_StrictModel):
    """Exit at an explicit price level."""

    type: Literal["absolute"]
    price: Annotated[float, Field(description="Absolute price level for exit")]


class PriceOffsetRule(_StrictModel):
    """Exit at entry_price ± price_offset (canonical units)."""

    type: Literal["offset"]
    price_offset: Annotated[
        float,
        Field(
            gt=0,
            description="Positive distance in canonical price units from entry price",
        ),
    ]


class FixedPipsRule(_StrictModel):
    """Exit at entry_price ± pips × instrument pip size."""

    type: Literal["fixed_pips"]
    pips: Annotated[
        float, Field(gt=0, description="Positive distance expressed in pips")
    ]


class IndicatorRule(_StrictModel):
    """Exit distance calculated using a registered indicator."""

    type: Literal["indicator"]
    indicator: str
    params: dict[str, Any]

    @field_validator("params")
    @classmethod
    def _ensure_params_dict(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value is None:
            raise ValueError("Indicator params cannot be null")
        if not isinstance(value, dict):
            raise ValueError("Indicator params must be an object")
        return value

    @model_validator(mode="after")
    def _validate_against_registry(self) -> IndicatorRule:
        spec = rem_indicators.REM_INDICATORS_REGISTRY.get(self.indicator)
        if spec is None:
            raise ValueError(f"Unknown REM indicator '{self.indicator}'")

        params = dict(self.params)

        # Required parameters
        for key, expected_type in spec.required_params.items():
            if key not in params:
                raise ValueError(f"Missing required parameter '{key}'")
            if not isinstance(params[key], expected_type):
                raise TypeError(
                    f"Parameter '{key}' must be of type {expected_type.__name__}"
                )

        # Optional parameters (apply defaults)
        for key, (expected_type, default) in spec.optional_params.items():
            if key not in params:
                params[key] = default
                continue
            if not isinstance(params[key], expected_type):
                raise TypeError(
                    f"Parameter '{key}' must be of type {expected_type.__name__}"
                )

        allowed = set(spec.required_params) | set(spec.optional_params)
        unknown = set(params) - allowed
        if unknown:
            unknown_list = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown parameter(s): {unknown_list}")

        self.params = params
        return self


DistanceRule = Annotated[PriceOffsetRule | FixedPipsRule, Field(discriminator="type")]


class ReferenceRule(_StrictModel):
    """Exit derived from a contextual reference point plus optional offset."""

    type: Literal["reference"]
    reference_point: Annotated[
        str,
        Field(
            min_length=1,
            description="Dot-notation path into signal context (e.g. context.atr)",
        ),
    ]
    offset: DistanceRule | None = None


StopRule = Annotated[
    AbsoluteLevelRule | PriceOffsetRule | FixedPipsRule | IndicatorRule | ReferenceRule,
    Field(discriminator="type"),
]


class TrailingStopRule(_StrictModel):
    """Trailing stop definition leveraging the distance union."""

    distance: DistanceRule
    step: Annotated[
        float | None,
        Field(
            default=None,
            ge=0,
            description="Minimum improvement required before tightening",
        ),
    ]
    update: Literal["bar", "tick"] | None = Field(
        default=None, description="Cadence for stop updates"
    )


class REMConfig(_StrictModel):
    """Top-level configuration for the Risk Exit Manager."""

    name: str | None = None
    version: str | None = None
    stop_loss: StopRule
    take_profit: StopRule | None = None
    trailing_stop: TrailingStopRule | None = None


__all__ = [
    "REMConfig",
    "AbsoluteLevelRule",
    "PriceOffsetRule",
    "FixedPipsRule",
    "IndicatorRule",
    "ReferenceRule",
    "DistanceRule",
    "TrailingStopRule",
]
