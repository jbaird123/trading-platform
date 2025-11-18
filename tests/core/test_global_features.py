import logging
from pathlib import Path

import pytest
from sklearn.ensemble import GradientBoostingClassifier
from trading_platform.ai.models.profitability_classifier import (
    ProfitabilityClassifierModel,
)
from trading_platform.core.feature_resolver import ResolvedFeature
from trading_platform.core.global_features import (
    resolve_global_feature_manifest,
    select_minimal_global_features,
)
from trading_platform.regime_market_manager.models import (
    RMMGatingContext,
    RMMGatingProfile,
)


def test_resolve_manifest_defaults_to_project_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    path, features = resolve_global_feature_manifest("5min", None)
    assert path.name == "global.yaml"
    assert features, "Expected default manifest to return features"
    assert any("defaulting" in message for message in caplog.text.splitlines())


def test_select_minimal_global_features_uses_classifier_metadata(
    tmp_path: Path,
) -> None:
    feature_a = ResolvedFeature(
        name="1h_atr_14",
        type="ATR",
        params={"length": 14},
        timeframe="1H",
        source="close",
    )
    feature_b = ResolvedFeature(
        name="1h_rsi_14",
        type="RSI",
        params={"length": 14},
        timeframe="1H",
        source="close",
    )
    features = [feature_a, feature_b]

    registry_dir = tmp_path / "models"
    clf_dir = registry_dir / "profitability_classifier"
    clf_dir.mkdir(parents=True, exist_ok=True)
    model = ProfitabilityClassifierModel(timeframe="5min", archetype="trend_following")
    model.model = GradientBoostingClassifier()
    model.feature_names_ = [
        "context_at_entry_global_features_1h_atr_14",
        "context_at_entry_global_features_1h_atr_14_slope",
    ]
    model.save(clf_dir / "5min_trend_following.pkl")

    profile = RMMGatingProfile(
        contexts=[
            RMMGatingContext(
                timeframe="5min",
                archetype="trend_following",
                classifier_model="gb",
                probability_threshold=0.6,
            )
        ]
    )

    subset = select_minimal_global_features(
        features,
        mode="minimal",
        gating_profile=profile,
        model_dir=registry_dir,
    )

    assert [feature.name for feature in subset] == ["1h_atr_14"]
