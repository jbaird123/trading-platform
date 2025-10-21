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
    indicator: str = Field(
        description="Name of the registered indicator providing the dynamic distance."
    )
    params: dict[str, Any] = Field(
        description="Indicator-specific parameters validated against the registry."
    )

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
            description=(
                "Dot-notation path into signal context (for example,"
                " `context.order_block_low`)."
            ),
        ),
    ]
    offset: DistanceRule | None = Field(
        default=None,
        description=(
            "Optional distance rule applied relative to the reference point"
            " (positive moves price away for take-profit, negative toward"
            " for stop-loss)."
        ),
    )


StopRule = Annotated[
    AbsoluteLevelRule | PriceOffsetRule | FixedPipsRule | IndicatorRule | ReferenceRule,
    Field(discriminator="type"),
]


class TrailingStopRule(_StrictModel):
    """Trailing stop definition leveraging the distance union."""

    distance: DistanceRule = Field(
        description=(
            "Distance rule describing how far the trailing stop should remain"
            " from the favorable extreme (e.g., fixed pips)."
        )
    )
    step: Annotated[
        float | None,
        Field(
            default=None,
            ge=0,
            description=(
                "Minimum improvement required (in price units) before the"
                " trailing stop tightens again."
            ),
        ),
    ]
    update: Literal["bar", "tick"] | None = Field(
        default=None,
        description="Cadence for trailing stop updates (bar-by-bar or tick).",
    )


class REMConfig(_StrictModel):
    """Top-level configuration for the Risk Exit Manager."""

    name: str | None = Field(
        default=None,
        description="Optional human-readable name for this REM configuration.",
    )
    description: str | None = Field(
        default=None,
        description="Free-form description clarifying how the configuration is used.",
    )
    version: str | None = Field(
        default=None,
        description="Optional semantic version for the configuration document.",
    )
    stop_loss: StopRule = Field(
        description="Primary stop-loss rule applied to every open position."
    )
    take_profit: StopRule | None = Field(
        default=None,
        description="Optional take-profit rule applied alongside the stop-loss.",
    )
    trailing_stop: TrailingStopRule | None = Field(
        default=None,
        description="Optional trailing-stop definition used to ratchet protective stops.",
    )


class ATRDistanceRule(_StrictModel):
    """ATR-multiple distance expressed via multiplier."""

    type: Literal["atr"]
    multiplier: Annotated[
        float,
        Field(
            gt=0,
            description="ATR multiplier used to derive stop distance",
        ),
    ]


DynamicDistanceRule = Annotated[
    PriceOffsetRule | ATRDistanceRule, Field(discriminator="type")
]


class PartialExitRule(_StrictModel):
    """Definition for partial exit targets."""

    r_multiple: Annotated[
        float, Field(ge=0, description="R-multiple threshold to trigger exit")
    ]
    fraction: Annotated[
        float,
        Field(
            gt=0,
            le=1,
            description="Fraction of position to close (0.0 < fraction ≤ 1.0)",
        ),
    ]


class DynamicTrailingStopRule(_StrictModel):
    """Trailing stop configuration for DynamicREM."""

    distance: DynamicDistanceRule = Field(
        description="Distance rule (ATR-based or fixed offset) applied when trailing."
    )
    activate_after_partial: bool = Field(
        default=False,
        description="Delay trailing activation until a partial exit occurs",
    )


class DynamicREMConfig(_StrictModel):
    """Configuration model for Dynamic Risk & Exit Manager."""

    name: str | None = Field(
        default=None,
        description="Optional human-readable name for the DynamicREM configuration.",
    )
    description: str | None = Field(
        default=None,
        description="Narrative description covering the risk approach this config encodes.",
    )
    version: str | None = Field(
        default=None,
        description="Optional semantic version for auditing DynamicREM configs.",
    )
    stop_loss: StopRule = Field(
        description="Base stop-loss rule evaluated before dynamic adjustments."
    )
    take_profit: StopRule | None = Field(
        default=None,
        description="Optional take-profit rule evaluated alongside dynamic exits.",
    )
    breakeven_threshold: Annotated[
        float | None,
        Field(
            default=None,
            ge=0,
            description="R-multiple at which the stop-loss is lifted to the entry price.",
        ),
    ] = None
    partial_exits: list[PartialExitRule] = Field(
        default_factory=list,
        description="Sequence of partial exit targets evaluated in order of appearance.",
    )
    trailing_stop: DynamicTrailingStopRule | None = Field(
        default=None,
        description="Optional trailing-stop configuration activated by DynamicREM.",
    )
    volatility_threshold: Annotated[
        float | None,
        Field(
            default=None,
            ge=0,
            description=(
                "ADX threshold below which the trailing stop distance should be"
                " tightened."
            ),
        ),
    ] = None
    low_volatility_multiplier: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Factor applied to the trailing distance whenever volatility is"
                " below the threshold (0 < multiplier ≤ 1)."
            ),
        ),
    ] = 1.0


__all__ = [
    "REMConfig",
    "AbsoluteLevelRule",
    "PriceOffsetRule",
    "FixedPipsRule",
    "IndicatorRule",
    "ReferenceRule",
    "DistanceRule",
    "TrailingStopRule",
    "ATRDistanceRule",
    "DynamicDistanceRule",
    "PartialExitRule",
    "DynamicTrailingStopRule",
    "DynamicREMConfig",
]
