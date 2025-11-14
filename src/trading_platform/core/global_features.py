"""Utilities for loading and filtering global feature manifests."""

from __future__ import annotations

import logging
from os import fspath
from pathlib import Path
from typing import Iterable, Sequence

from trading_platform.ai.models import ModelRegistry
from trading_platform.core import paths
from trading_platform.core.feature_resolver import (
    ResolvedFeature,
    resolve_global_features,
)
from trading_platform.regime_market_manager.gating import ALIGNMENT_COLUMN_MAP
from trading_platform.regime_market_manager.models import RMMGatingProfile

logger = logging.getLogger(__name__)

GLOBAL_FEATURE_PREFIX = "context_at_entry_global_features_"
DEFAULT_GLOBAL_FEATURES_PATH = (
    paths.PROJECT_ROOT / "config" / "features" / "global.yaml"
)


def resolve_global_feature_manifest(
    execution_timeframe: str,
    config_path: Path | str | None,
    *,
    warn_on_default: bool = True,
) -> tuple[Path, list[ResolvedFeature]]:
    """Resolve the global feature list for a run.

    Returns the resolved config path and the filtered ResolvedFeature list.
    """

    if config_path is None:
        if not DEFAULT_GLOBAL_FEATURES_PATH.exists():
            raise FileNotFoundError(
                "Global features config not provided and default path "
                f"{DEFAULT_GLOBAL_FEATURES_PATH} does not exist."
            )
        if warn_on_default:
            logger.warning(
                "No global_features_config_path provided; defaulting to %s",
                DEFAULT_GLOBAL_FEATURES_PATH,
            )
        resolved_path = DEFAULT_GLOBAL_FEATURES_PATH
    else:
        try:
            resolved_path = Path(fspath(config_path))
        except TypeError:
            resolved_path = Path(str(config_path))

    features = resolve_global_features(execution_timeframe, config_path=resolved_path)
    return resolved_path, features


def feature_to_dict(feature: ResolvedFeature) -> dict[str, object]:
    """Convert a ResolvedFeature to the dict format expected downstream."""

    return {
        "name": feature.name,
        "type": feature.type,
        "params": feature.params,
        "source": feature.source,
        "timeframe": feature.timeframe,
    }


def select_minimal_global_features(
    features: Sequence[ResolvedFeature],
    *,
    mode: str,
    include: Iterable[str] | None = None,
    gating_profile: RMMGatingProfile | None = None,
    model_dir: Path | None = None,
) -> list[ResolvedFeature]:
    """Apply minimal-mode filtering to the global feature manifest."""

    if mode != "minimal":
        return list(features)

    required: set[str] = set(include or [])
    required.update(_features_from_gating_profile(gating_profile, model_dir))

    if not required:
        logger.warning(
            "global_features_mode='minimal' but no required features detected; "
            "falling back to full feature set."
        )
        return list(features)

    available_names = {feature.name for feature in features}
    effective_required = {name for name in required if name in available_names}
    missing = required - available_names

    if not effective_required:
        logger.warning(
            "Minimal global features requested but none of the required"
            " names are present in the manifest; falling back to full set.",
        )
        return list(features)

    selected = [feature for feature in features if feature.name in effective_required]
    if missing:
        logger.warning(
            "Minimal global features: requested features not found in manifest %s.",
            sorted(missing),
        )

    return selected


def _features_from_gating_profile(
    profile: RMMGatingProfile | None,
    model_dir: Path | None,
) -> set[str]:
    if profile is None:
        return set()

    required: set[str] = set()
    registry = ModelRegistry(
        model_dir=model_dir or paths.PROJECT_ROOT / "data" / "dvc" / "ml" / "models"
    )
    registry.load()

    for context in profile.contexts:
        key = f"{context.timeframe}_{context.archetype}"
        classifier = registry.get_model("profitability_classifier", key)
        if classifier is None or not getattr(classifier, "feature_names_", None):
            logger.warning(
                "Minimal global features: classifier %s missing or untrained; "
                "falling back to full feature set for this context.",
                key,
            )
            return set()

        for feature_name in classifier.feature_names_:
            if feature_name.startswith(GLOBAL_FEATURE_PREFIX):
                required.add(feature_name[len(GLOBAL_FEATURE_PREFIX) :])
        alignment_col = ALIGNMENT_COLUMN_MAP.get(context.timeframe.lower())
        if alignment_col and alignment_col.startswith(GLOBAL_FEATURE_PREFIX):
            required.add(alignment_col[len(GLOBAL_FEATURE_PREFIX) :])

    return required
