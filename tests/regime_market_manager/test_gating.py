from typing import cast

import pandas as pd
import pytest
from trading_platform.ai.models.registry import ModelRegistry
from trading_platform.regime_market_manager.gating import (
    GatingDecision,
    ProfitabilityGatingEngine,
)
from trading_platform.regime_market_manager.models import RMMGatingProfile


class DummyClassifier:
    def __init__(self, probability: float) -> None:
        self._probability = probability

    def predict_proba(self, df: pd.DataFrame):
        import numpy as np

        proba = np.array([[1.0 - self._probability, self._probability]])
        return proba


class DummyRegistry:
    def __init__(self, models):
        self._models = models

    def load(self):
        return None

    def get_model(self, family: str, key: str):
        return self._models.get(key)


def _build_profile():
    return RMMGatingProfile.model_validate(
        {
            "profile": {"name": "test"},
            "contexts": [
                {
                    "timeframe": "5min",
                    "archetype": "trend_following",
                    "classifier_model": "gb_weighted",
                    "probability_threshold": 0.5,
                    "gating_expression": "alignment_full",
                }
            ],
        }
    )


def test_gating_engine_allows_when_probability_and_alignment_pass():
    profile = _build_profile()
    registry = DummyRegistry({"5min_trend_following": DummyClassifier(0.8)})
    engine = ProfitabilityGatingEngine(profile, registry=cast(ModelRegistry, registry))
    context = {
        "strategy_features": {},
        "global_features": {
            "m15_trend_alignment_full_alignment": 1.0,
        },
    }
    decision = engine.should_allow(
        timeframe="5min",
        archetype="trend_following",
        side="long",
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
        context=context,
    )
    assert isinstance(decision, GatingDecision)
    assert decision.allowed is True
    assert decision.probability == 0.8


def test_gating_engine_blocks_when_probability_below_threshold():
    profile = _build_profile()
    registry = DummyRegistry({"5min_trend_following": DummyClassifier(0.2)})
    engine = ProfitabilityGatingEngine(profile, registry=cast(ModelRegistry, registry))
    context = {
        "strategy_features": {},
        "global_features": {
            "m15_trend_alignment_full_alignment": 1.0,
        },
    }
    decision = engine.should_allow(
        timeframe="5min",
        archetype="trend_following",
        side="long",
        symbol="EUR_USD",
        entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
        context=context,
    )
    assert decision.allowed is False
    assert decision.reason == "probability_below_threshold"


def test_gating_engine_raises_when_classifier_missing():
    profile = _build_profile()
    registry = DummyRegistry({})
    engine = ProfitabilityGatingEngine(profile, registry=cast(ModelRegistry, registry))
    with pytest.raises(RuntimeError):
        engine.should_allow(
            timeframe="5min",
            archetype="trend_following",
            side="long",
            symbol="EUR_USD",
            entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
            context={},
        )
