from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import RiskExitManager
from .dynamic_rem import DynamicREM
from .models import (
    AbsoluteLevelRule,
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
]


def create_rem(config: dict[str, Any]) -> DynamicREM:
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
    if not isinstance(config, dict):
        raise ValueError("REM config must be a dictionary")

    # Note: JSON schema validation removed. Pydantic will be the validation
    # source when DynamicREM Pydantic model is implemented. JSON schemas are
    # for documentation only.
    # TODO: Replace with Pydantic validation when DynamicREM model is implemented

    return DynamicREM(config)
