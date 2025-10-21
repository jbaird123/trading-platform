from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import RiskExitManager
from .dynamic_rem import DynamicREM
from .models import (
    AbsoluteLevelRule,
    ATRDistanceRule,
    DynamicREMConfig,
    DynamicTrailingStopRule,
    FixedPipsRule,
    IndicatorRule,
    PriceOffsetRule,
    ReferenceRule,
    REMConfig,
    TrailingStopRule,
)

__all__ = [
    "RiskExitManager",
    "DynamicREM",
    "create_rem",
    "REMConfig",
    "AbsoluteLevelRule",
    "PriceOffsetRule",
    "FixedPipsRule",
    "IndicatorRule",
    "ReferenceRule",
    "TrailingStopRule",
    "ATRDistanceRule",
    "DynamicTrailingStopRule",
    "DynamicREMConfig",
]


def create_rem(config: DynamicREMConfig | dict[str, Any]) -> DynamicREM:
    """Factory function to create DynamicREM with schema validation.

    Task 19: Wire DynamicREM into factory with schema validation.
    This ensures misconfigurations fail fast during instantiation.

    Args:
        config: DynamicREM configuration dictionary

    Returns:
        DynamicREM instance

    Raises:
        ValueError: If config is invalid or fails schema validation
    """
    if isinstance(config, DynamicREMConfig):
        model = config
    elif isinstance(config, dict):
        model = DynamicREMConfig(**config)
    else:
        raise ValueError("REM config must be a dictionary")

    return DynamicREM(model)
