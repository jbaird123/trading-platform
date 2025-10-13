from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import RiskExitManager
from .dynamic_rem import DynamicREM

__all__ = ["RiskExitManager", "DynamicREM", "create_rem"]

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]


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

    # Validate against DynamicREM schema if jsonschema available
    if jsonschema is not None:
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "schemas"
            / "rem_dynamic.schema.json"
        )
        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(
                f"DynamicREM config schema validation failed: {e.message}"
            ) from e

    return DynamicREM(config)
