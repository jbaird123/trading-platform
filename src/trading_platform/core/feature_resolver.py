"""Feature resolver utility for loading and filtering global features."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from trading_platform.data.timeframe_aliases import canonicalize_timeframe

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


def resolve_global_features(
    execution_timeframe: str, config_path: Path | str | None = None
) -> list[ResolvedFeature]:
    """Resolve global features for the given execution timeframe.

    Loads global.yaml, validates all feature names have timeframe prefixes,
    and filters features to include only those with timeframe >= execution_timeframe.

    Args:
        execution_timeframe: The timeframe at which the strategy executes
        config_path: Optional path to global features YAML file.
                     Defaults to config/features/global.yaml.
                     Used by golden validation tests to specify a stable
                     fixture file independent of production config changes.

    Returns:
        List of ResolvedFeature objects that should be computed

    Raises:
        FileNotFoundError: If the config file does not exist
        ValueError: If any feature name is invalid (missing prefix,
            unrecognized timeframe, etc.)
    """
    if config_path is None:
        global_yaml_path = Path("config/features/global.yaml")
    else:
        global_yaml_path = Path(config_path)

    if not global_yaml_path.exists():
        raise FileNotFoundError(
            f"Global feature configuration not found at {global_yaml_path}"
        )

    # Load and parse YAML
    with open(global_yaml_path) as f:
        yaml_content = yaml.safe_load(f)

    # Parse into GlobalFeatureSetConfig (validates timeframe prefix naming)
    config = GlobalFeatureSetConfig.model_validate(yaml_content)

    execution_timeframe = (
        canonicalize_timeframe(execution_timeframe) or execution_timeframe
    )
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
                    timeframe=(
                        canonicalize_timeframe(execution_timeframe)
                        or execution_timeframe
                    ),
                    source=feature.source.value if feature.source else "close",
                )
            )
            continue

        # Include if feature timeframe >= execution timeframe
        feature_timeframe = canonicalize_timeframe(feature.timeframe)
        if feature_timeframe is None:
            continue
        if compare_timeframes(feature_timeframe, execution_timeframe) >= 0:
            resolved.append(
                ResolvedFeature(
                    name=feature.name,
                    type=feature.type,
                    params=feature.params or {},
                    timeframe=feature_timeframe,
                    source=feature.source.value if feature.source else "close",
                )
            )

    return resolved
