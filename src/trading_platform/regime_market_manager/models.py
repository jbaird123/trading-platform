"""Pydantic models for RMM configuration validation."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from trading_platform.core.config import PriceSource
from trading_platform.strategy.indicators_registry import INDICATORS


class RMMFeatureConfig(BaseModel):
    """Configuration for a single technical indicator/feature for RMM."""

    model_config = {"extra": "forbid"}

    name: str = Field(
        description="Local identifier used by conditions (e.g., ema_slope)."
    )
    type: str = Field(
        description=(
            "Indicator type to compute for regime logic "
            "(validated against registry)."
        )
    )
    params: dict[str, Any] | None = Field(
        default=None, description="Indicator-specific parameters (e.g., length)."
    )
    source: PriceSource | None = Field(
        default=None, description="Input price series used by the indicator."
    )
    source_ref: dict[str, Any] | None = Field(
        default=None,
        description="Reference another computed feature as the input series.",
    )
    timeframe: str | None = Field(
        default=None,
        description=(
            "Optional pandas offset alias if feature should be computed on a "
            "different timeframe than the RMM classification timeframe."
        ),
        pattern=r"^\d*(?:[DHMS]|[mM][iI][nN]|[tT]|[wW])$",
    )

    @field_validator("type")
    @classmethod
    def validate_indicator_type(cls, value: str) -> str:
        if value not in INDICATORS:
            allowed = ", ".join(sorted(INDICATORS))
            raise ValueError(
                f"Unknown indicator type '{value}'. Must be one of: {allowed}."
            )
        return value


class RMMIndicatorRef(BaseModel):
    """Reference to a feature defined in the features list."""

    model_config = {"extra": "forbid"}
    ref: str = Field(description="Name of a feature defined in the features list.")


RMMOperand = Union[RMMIndicatorRef, float, Literal["open", "high", "low", "close"]]


class RMMPredicate(BaseModel):
    """A single condition to be evaluated."""

    model_config = {"extra": "forbid"}

    condition: Literal[
        "is_above",
        "is_below",
        "hour_is_in",
        "hour_is_not_in",
        "day_of_week_is_in",
        "day_of_week_is_not_in",
        "percentile_is_above",
        "volatility_is_between",
    ]
    lower: float | None = Field(
        default=None, description="Lower bound for volatility_is_between predicate."
    )
    upper: float | None = Field(
        default=None, description="Upper bound for volatility_is_between predicate."
    )
    left: RMMOperand | None = None
    right: RMMOperand | None = None
    values: list[str | int] | None = None


class RMMRuleBlock(BaseModel):
    """A block of conditions (all_of or any_of)."""

    model_config = {"extra": "forbid"}

    all_of: list[RMMPredicate] | None = Field(
        default=None, description="A list of predicate conditions that must ALL be met."
    )
    any_of: list[RMMPredicate] | None = Field(
        default=None,
        description="A list of predicate conditions where AT LEAST ONE must be met.",
    )

    @model_validator(mode="before")
    @classmethod
    def check_one_of(cls, data: Any) -> Any:
        if isinstance(data, dict):
            all_of_present = "all_of" in data and data.get("all_of") is not None
            any_of_present = "any_of" in data and data.get("any_of") is not None

            if all_of_present and any_of_present:
                raise ValueError(
                    "RMMRuleBlock must have exactly one of all_of or "
                    "any_of, but both were found."
                )
            if not all_of_present and not any_of_present:
                raise ValueError(
                    "RMMRuleBlock must have exactly one of all_of or "
                    "any_of, but neither was found."
                )
        return data


class RMMRegime(BaseModel):
    """Definition of a single market regime."""

    model_config = {"extra": "forbid"}

    label: str = Field(description="Regime name (e.g., trend_up, range, volatile).")
    conditions: RMMRuleBlock
    confidence: Annotated[
        float,
        Field(
            ge=0.0, le=1.0, description="Confidence assigned when conditions are met."
        ),
    ]


class RMMHysteresis(BaseModel):
    """Hysteresis settings to prevent rapid regime switching."""

    model_config = {"extra": "forbid"}

    min_bars: int = Field(
        0, ge=0, description="Bars a label must persist before switching."
    )
    cooldown_bars: int = Field(
        0, ge=0, description="Bars to wait after a switch before switching again."
    )


class RMMPolicy(BaseModel):
    """Policy to filter trades based on regime."""

    model_config = {"extra": "forbid"}

    min_confidence: Annotated[
        float,
        Field(
            ge=0.0, le=1.0, description="Lowest confidence required to accept a regime."
        ),
    ] = 0.0
    allow_labels: list[str] | None = Field(
        default=None, description="Whitelist of labels permitted for trading."
    )
    block_labels: list[str] | None = Field(
        default=None, description="Blacklist of labels to block from trading."
    )


class RMMConfig(BaseModel):
    """Top-level configuration for the Regime Market Manager."""

    model_config = {"extra": "forbid"}

    name: str | None = Field(
        default=None, description="Human-friendly name for this RMM configuration."
    )
    version: str | None = Field(
        default=None, description="Optional version tag for this RMM config."
    )
    timeframe: str | None = Field(
        default=None,
        description=(
            "Timeframe for regime classification (e.g., '1D', '4H', '1H', "
            "'15min', '5T'). Must be a valid pandas resample frequency."
        ),
        pattern=r"^\d*(?:[DHMS]|[mM][iI][nN]|[tT])$",
    )
    features: list[RMMFeatureConfig] | None = Field(
        default=None, description="Indicators/features used to classify regimes."
    )
    hysteresis: RMMHysteresis | None = None
    policy: RMMPolicy | None = None
    regimes: list[RMMRegime] = Field(
        description="List of regime definitions and their conditions.", min_length=1
    )


__all__ = [
    "RMMConfig",
    "RMMFeatureConfig",
    "RMMHysteresis",
    "RMMPolicy",
    "RMMRegime",
    "RMMRuleBlock",
    "RMMPredicate",
    "RMMOperand",
    "RMMIndicatorRef",
    "RMMGatingProfile",
    "RMMGatingContext",
    "parse_rmm_resource",
]


class RMMGatingContext(BaseModel):
    """Context-specific profitability gating configuration."""

    model_config = {"extra": "forbid"}

    timeframe: str = Field(description="Execution timeframe (e.g., '5min').")
    archetype: str = Field(
        description="Strategy archetype (e.g., 'trend_following', 'mean_reversion')."
    )
    classifier_model: str = Field(
        description="Classifier alias (e.g., gb_weighted, logistic)."
    )
    feature_group: str | None = Field(
        default=None,
        description="Feature group used during analysis (for documentation only).",
    )
    probability_threshold: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description="Probability threshold required to enable trades.",
        ),
    ]
    gating_expression: str = Field(
        default="true",
        description="Boolean expression that must evaluate to True for gating.",
    )
    expected_coverage: float | None = Field(
        default=None, description="Documented coverage fraction from analysis."
    )
    expected_mean_r: float | None = Field(
        default=None, description="Documented mean R from analysis."
    )
    expected_sum_r: float | None = Field(
        default=None, description="Documented sum R from analysis."
    )
    commentary: str | None = Field(
        default=None, description="Free-form notes about this gating context."
    )


class RMMGatingProfileMeta(BaseModel):
    """Metadata describing a profitability gating profile."""

    model_config = {"extra": "allow"}  # allow future metadata fields

    name: str = Field(description="Human-friendly profile name.")
    description: str | None = Field(default=None, description="Profile summary.")
    source_analysis: dict[str, Any] | None = Field(
        default=None, description="Pointers to analysis artifacts."
    )
    notes: str | None = Field(default=None, description="Additional notes.")


class RMMGatingProfile(BaseModel):
    """Top-level profitability gating profile."""

    model_config = {"extra": "forbid"}

    profile: RMMGatingProfileMeta | None = Field(
        default=None, description="Profile metadata."
    )
    contexts: list[RMMGatingContext] = Field(
        description="List of gating contexts (timeframe/archetype pairs).",
        min_length=1,
    )

    def context_map(self) -> dict[tuple[str, str], RMMGatingContext]:
        """Return mapping keyed by (timeframe_lower, archetype)."""
        return {(ctx.timeframe.lower(), ctx.archetype): ctx for ctx in self.contexts}


def parse_rmm_resource(
    config_dict: dict[str, Any],
) -> tuple[dict[str, Any] | None, RMMGatingProfile | None]:
    """Determine whether a YAML blob is a classic RMMConfig or gating profile.

    Returns:
        Tuple of (legacy_rmm_dict, gating_profile). Only one element will be non-null.
    """
    if "regimes" in config_dict:
        # Legacy rule-based RMM config
        return config_dict, None

    if "contexts" in config_dict:
        profile = RMMGatingProfile.model_validate(config_dict)
        return None, profile

    return config_dict, None
