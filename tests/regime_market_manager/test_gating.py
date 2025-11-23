from typing import Sequence, cast

import pandas as pd
import pytest
from trading_platform.ai.models.registry import ModelRegistry
from trading_platform.regime_market_manager.gating import (
    GatingDecision,
    ProfitabilityGatingEngine,
)
from trading_platform.regime_market_manager.models import RMMGatingProfile


class DummyClassifier:
    def __init__(
        self, probability: float, required_features: Sequence[str] | None = None
    ) -> None:
        self._probability = probability
        self.required_features = list(required_features or [])

    def predict_proba(self, df: pd.DataFrame):
        import numpy as np

        missing = [
            feature for feature in self.required_features if feature not in df.columns
        ]
        if missing:
            raise AssertionError(f"Missing features: {missing}")
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
            "15min_trend_alignment_full_alignment": 1.0,
        },
    }
    decision = engine.should_allow(
        timeframe="5min",
        archetype="trend_following",
        side="long",
        symbol="EURUSD",
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
            "15min_trend_alignment_full_alignment": 1.0,
        },
    }
    decision = engine.should_allow(
        timeframe="5min",
        archetype="trend_following",
        side="long",
        symbol="EURUSD",
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
            symbol="EURUSD",
            entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
            context={},
        )


def test_gating_engine_builds_prefixed_feature_row():
    required = [
        "context_at_entry_strategy_features_ema_fast",
        "context_at_entry_strategy_features_atr_14",
        "context_at_entry_global_features_15min_day_of_week_dow_3",
        "context_at_entry_global_features_15min_trend_alignment_full_alignment",
        "risk_distance_abs",
        "risk_distance_pct_entry",
        "risk_distance_atr_ratio",
        "side",
        "symbol",
        "hour_of_day",
        "day_of_week",
    ]
    profile = _build_profile()
    registry = DummyRegistry(
        {"5min_trend_following": DummyClassifier(0.7, required_features=required)}
    )
    engine = ProfitabilityGatingEngine(profile, registry=cast(ModelRegistry, registry))
    context = {
        "strategy_features": {
            "ema_fast": 1.0,
            "atr_14": 0.5,
        },
        "global_features": {
            "15min_day_of_week_dow_3": 1.0,
            "15min_trend_alignment_full_alignment": 1.0,
        },
        "risk": {
            "entry_price": 1.2345,
            "initial_stop_loss_price": 1.2305,
        },
    }
    decision = engine.should_allow(
        timeframe="5min",
        archetype="trend_following",
        side="long",
        symbol="EURUSD",
        entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
        context=context,
    )
    assert decision.allowed is True
