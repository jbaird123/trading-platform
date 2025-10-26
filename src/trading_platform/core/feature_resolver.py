"""Feature resolver utility for loading and filtering global features."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import GlobalFeatureSetConfig
from .timeframes import compare_timeframes


@dataclass
class ResolvedFeature:
    """Type-safe representation of a resolved feature."""

    name: str
    type: str
    params: dict[str, Any]
    timeframe: str | None
    source: str


def resolve_global_features(execution_timeframe: str) -> list[ResolvedFeature]:
    """Resolve global features for the given execution timeframe.

    Loads global.yaml, validates all feature names have timeframe prefixes,
    and filters features to include only those with timeframe >= execution_timeframe.

    Args:
        execution_timeframe: The timeframe at which the strategy executes

    Returns:
        List of ResolvedFeature objects that should be computed

    Raises:
        FileNotFoundError: If config/features/global.yaml does not exist
        ValueError: If any feature name is invalid (missing prefix,
            unrecognized timeframe, etc.)
    """
    global_yaml_path = Path("config/features/global.yaml")

    if not global_yaml_path.exists():
        raise FileNotFoundError(
            f"Global feature configuration not found at {global_yaml_path}"
        )

    # Load and parse YAML
    with open(global_yaml_path) as f:
        yaml_content = yaml.safe_load(f)

    # Parse into GlobalFeatureSetConfig (validates timeframe prefix naming)
    config = GlobalFeatureSetConfig.model_validate(yaml_content)

    # Filter features by timeframe
    resolved = []
    for feature in config.features:
        # Include if no timeframe specified (implicit to execution timeframe)
        if feature.timeframe is None:
            resolved.append(
                ResolvedFeature(
                    name=feature.name,
                    type=feature.type,
                    params=feature.params or {},
                    timeframe=feature.timeframe,
                    source=feature.source.value if feature.source else "close",
                )
            )
            continue

        # Include if feature timeframe >= execution timeframe
        if compare_timeframes(feature.timeframe, execution_timeframe) >= 0:
            resolved.append(
                ResolvedFeature(
                    name=feature.name,
                    type=feature.type,
                    params=feature.params or {},
                    timeframe=feature.timeframe,
                    source=feature.source.value if feature.source else "close",
                )
            )

    return resolved
