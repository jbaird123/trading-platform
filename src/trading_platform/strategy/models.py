"""Pydantic models for strategy configuration.

This module defines the strategy configuration schema using Pydantic as the
single source of truth. JSON schemas are auto-generated from these models.

VALIDATION PHILOSOPHY:
- Fail loudly and early for invalid configurations
- No silent failures or default fallbacks
- All enums and constraints from JSON schema are enforced
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from trading_platform.core.config import FeatureConfig


class StrategyCondition(str, Enum):
    """Valid condition operators for strategy predicates.

    These match the conditions supported by the strategy engine.
    Any condition not in this enum will be rejected at validation time.
    """

    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    IS_ABOVE = "is_above"
    IS_BELOW = "is_below"
    SLOPE_IS_ABOVE = "slope_is_above"
    ROC_IS_ABOVE = "roc_is_above"


class OHLCField(str, Enum):
    """Valid OHLC price field references."""

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


class Operand(BaseModel):
    """Operand in a predicate (can be a feature reference, constant, or field).

    STRICT VALIDATION: Exactly one of ref, value, or field must be provided.
    This prevents silent failures where invalid operands become zeros.
    """

    model_config = {"extra": "forbid"}

    ref: str | None = Field(default=None, description="Reference to a feature by name")
    value: float | None = Field(default=None, description="Constant numeric value")
    field: OHLCField | None = Field(
        default=None, description="Reference to OHLCV field"
    )

    @model_validator(mode="after")
    def validate_exactly_one_operand_type(self) -> Operand:
        """Ensure exactly one of ref, value, or field is provided.

        Raises:
            ValueError: If zero or multiple operand types are provided.
        """
        provided = sum(
            [
                self.ref is not None,
                self.value is not None,
                self.field is not None,
            ]
        )

        if provided == 0:
            raise ValueError(
                "Operand must have exactly one of: ref, value, or field. " "Got none."
            )
        if provided > 1:
            raise ValueError(
                f"Operand must have exactly one of: ref, value, or field. "
                f"Got multiple: ref={self.ref}, value={self.value}, field={self.field}"
            )

        return self


class Predicate(BaseModel):
    """A single condition in a rule (e.g., ema_fast > ema_slow).

    STRICT VALIDATION: condition must be from StrategyCondition enum.
    Typos or invalid conditions will be rejected immediately.

    Operands must be in proper dict format:
    - {field: "close"} for OHLC field references
    - {value: 1.5} for numeric constants
    - {ref: "ema_fast"} for feature references
    """

    model_config = {"extra": "forbid"}

    condition: StrategyCondition = Field(
        description="Comparison operator from valid strategy conditions"
    )
    left: Operand = Field(
        description="Left operand (feature ref, constant, or OHLC field)"
    )
    right: Operand = Field(
        description="Right operand (feature ref, constant, or OHLC field)"
    )


class RuleBlock(BaseModel):
    """A rule block containing predicates combined with all_of or any_of logic.

    STRICT VALIDATION:
    - Exactly one of all_of or any_of must be provided (not both, not neither)
    - Predicate lists must have at least 1 item (empty lists rejected)
    """

    model_config = {"extra": "forbid"}

    all_of: list[Predicate] | None = Field(
        default=None,
        description="All predicates must be true (AND logic)",
        min_length=1,
    )
    any_of: list[Predicate] | None = Field(
        default=None,
        description="At least one predicate must be true (OR logic)",
        min_length=1,
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional context mapping for contextual REM rules "
            "(e.g., order_block_low)"
        ),
    )

    @model_validator(mode="after")
    def validate_exactly_one_logic_type(self) -> RuleBlock:
        """Ensure exactly one of all_of or any_of is provided.

        Raises:
            ValueError: If zero or both logic types are provided.
        """
        provided = sum(
            [
                self.all_of is not None,
                self.any_of is not None,
            ]
        )

        if provided == 0:
            raise ValueError(
                "RuleBlock must have exactly one of: all_of or any_of. " "Got neither."
            )
        if provided > 1:
            raise ValueError(
                "RuleBlock must have exactly one of: all_of or any_of. " "Got both."
            )

        return self


class StrategyConfig(BaseModel):
    """Strategy configuration defining entry/exit rules and features.

    A strategy consists of:
    - Features: Technical indicators to compute
    - Entry/Exit Rules: Conditions for opening and closing positions
    - Parameters: Configurable values that can be overridden

    Example:
        {
            "strategy_name": "EMA Crossover",
            "description": "Simple moving average crossover strategy",
            "version": "1.0",
            "parameters": {"ema_fast_length": 20, "ema_slow_length": 50},
            "features": [
                {
                    "name": "ema_fast",
                    "type": "EMA",
                    "params": {"length": 20},
                    "source": "close"
                },
                {
                    "name": "ema_slow",
                    "type": "EMA",
                    "params": {"length": 50},
                    "source": "close"
                }
            ],
            "overlays": ["ema_fast", "ema_slow"],
            "long_entry_rules": [
                {
                    "all_of": [
                        {
                            "condition": "cross_above",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"}
                        }
                    ]
                }
            ],
            "long_exit_rules": [
                {
                    "any_of": [
                        {
                            "condition": "cross_below",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"}
                        }
                    ]
                }
            ]
        }
    """

    model_config = {"extra": "forbid"}

    strategy_name: str = Field(description="Human-readable name for the strategy")
    description: str | None = Field(
        default=None, description="Optional description of the strategy"
    )
    version: str | None = Field(default=None, description="Strategy version string")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional metadata (e.g., strategy_archetype) passed through to "
            "run config and downstream artifacts."
        ),
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Strategy parameters that can be overridden " "(e.g., indicator lengths)"
        ),
    )

    features: list[FeatureConfig] = Field(
        default_factory=list,
        description="List of technical indicators/features to compute",
    )

    overlays: list[str] = Field(
        default_factory=list,
        description=(
            "List of feature names to overlay on price chart " "for visualization"
        ),
    )

    long_entry_rules: list[RuleBlock] | None = Field(
        default=None, description="Rules for entering long positions"
    )
    long_exit_rules: list[RuleBlock] | None = Field(
        default=None, description="Rules for exiting long positions"
    )

    short_entry_rules: list[RuleBlock] | None = Field(
        default=None, description="Rules for entering short positions"
    )
    short_exit_rules: list[RuleBlock] | None = Field(
        default=None, description="Rules for exiting short positions"
    )

    @model_validator(mode="after")
    def validate_has_entry_rules(self) -> StrategyConfig:
        """Ensure strategy has at least one entry rule (long or short).

        A strategy without any entry rules cannot generate trades.
        This matches the JSON schema requirement:
        anyOf[long_entry_rules, short_entry_rules].

        Raises:
            ValueError: If neither long_entry_rules nor short_entry_rules are provided.
        """
        has_long_entry = (
            self.long_entry_rules is not None and len(self.long_entry_rules) > 0
        )
        has_short_entry = (
            self.short_entry_rules is not None and len(self.short_entry_rules) > 0
        )

        if not has_long_entry and not has_short_entry:
            raise ValueError(
                "Strategy must have at least one entry rule. "
                "Provide either long_entry_rules or short_entry_rules (or both). "
                "A strategy without entry rules cannot generate trades."
            )

        return self

    @model_validator(mode="after")
    def validate_feature_names_no_timeframe_prefix(self) -> StrategyConfig:
        """Ensure strategy features do NOT have timeframe prefixes.

        Strategy features must not have timeframe prefixes
        (1min_, 5min_, 15min_, 1h_, 4h_, 1d_).
        Only global features should have timeframe prefixes.

        Raises:
            ValueError: If any feature has a timeframe prefix.
        """
        timeframe_prefix_pattern = r"^(m1|m5|m15|h1|h4|d1)_"

        for feature in self.features:
            if re.match(timeframe_prefix_pattern, feature.name):
                raise ValueError(
                    f"Strategy features must NOT have timeframe prefix. "
                    f"Found: {feature.name}"
                )

        return self
