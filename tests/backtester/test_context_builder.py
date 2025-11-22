from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from trading_platform.backtester.context import (
    DecisionSnapshotFactory,
    build_context_snapshot,
    realign_context_snapshot,
)
from trading_platform.core.global_features import GLOBAL_FEATURE_PREFIX


def _make_feature_frame(timestamp: datetime) -> pd.DataFrame:
    columns = [
        f"{GLOBAL_FEATURE_PREFIX}ema_fast",
        f"{GLOBAL_FEATURE_PREFIX}atr",
    ]
    data = {
        columns[0]: [1.23, 1.24],
        columns[1]: [0.5, 0.55],
    }
    index = [timestamp, timestamp + timedelta(minutes=5)]
    return pd.DataFrame(data, index=index)


def test_build_context_snapshot_merges_strategy_and_global_features() -> None:
    """Ensure strategy/global features plus decision_time are captured."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    frame = _make_feature_frame(start)
    context = build_context_snapshot(
        timestamp=start,
        strategy_context={"momentum": 3.0},
        rmm_context=None,
        regime_builder=None,
        global_feature_df=frame,
        global_feature_normalized_keys=["ema_fast", "atr"],
        global_feature_timeframes={
            f"{GLOBAL_FEATURE_PREFIX}ema_fast": 5,
            f"{GLOBAL_FEATURE_PREFIX}atr": 60,
        },
        execution_tf_minutes=5,
        extra_fields={"risk": {"entry_price": 1.0}},
    )
    assert context["strategy_features"]["momentum"] == 3.0
    assert context["global_features"]["ema_fast"] == pytest.approx(1.23)
    assert context["decision_time"] == start.isoformat()
    assert context["risk"]["entry_price"] == 1.0


def test_realign_context_snapshot_updates_globals_and_preserves_extras() -> None:
    """realign_context_snapshot should refresh globals but keep custom fields."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    frame = _make_feature_frame(start)
    base_context = {
        "strategy_features": {"momentum": 1.0},
        "global_features": {"ema": 0.0},
        "risk": {"entry_price": 1.0},
        "gating": {"allowed": True},
    }
    updated = realign_context_snapshot(
        base_context=base_context,
        timestamp=start + timedelta(minutes=5),
        rmm_context=None,
        regime_builder=None,
        global_feature_df=frame,
        global_feature_normalized_keys=["ema_fast", "atr"],
        global_feature_timeframes={
            f"{GLOBAL_FEATURE_PREFIX}ema_fast": 5,
            f"{GLOBAL_FEATURE_PREFIX}atr": 60,
        },
        execution_tf_minutes=5,
    )
    assert updated["global_features"]["ema_fast"] == pytest.approx(1.24)
    assert updated["risk"]["entry_price"] == 1.0
    assert updated["gating"]["allowed"] is True


def test_decision_snapshot_factory_returns_deepcopy() -> None:
    """Decision snapshots should not retain references to mutable context."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    frame = _make_feature_frame(start)
    factory = DecisionSnapshotFactory(
        rmm_context=None,
        regime_builder=None,
        global_feature_df=frame,
        global_feature_keys=["ema_fast", "atr"],
        global_feature_timeframes={
            f"{GLOBAL_FEATURE_PREFIX}ema_fast": 5,
            f"{GLOBAL_FEATURE_PREFIX}atr": 60,
        },
        execution_tf_minutes=5,
    )
    snapshot = factory.create(
        timestamp=start,
        price=1.0,
        side="long",
        size=1.0,
        bar_index=10,
        strategy_context={"momentum": 2.0},
        extra_fields={"risk": {"entry_price": 1.0}},
    )
    # Mutate source data to confirm snapshot is isolated.
    frame.iloc[0, 0] = 99.0
    assert snapshot.context["global_features"]["ema_fast"] == pytest.approx(1.23)
    assert snapshot.risk["entry_price"] == 1.0
