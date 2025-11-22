from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from trading_platform.backtester.models import DecisionSnapshot
from trading_platform.core.global_features import GLOBAL_FEATURE_PREFIX


def normalize_global_feature_key(name: str) -> str:
    """Strip canonical prefix to keep downstream joins consistent."""
    if name.startswith(GLOBAL_FEATURE_PREFIX):
        return name[len(GLOBAL_FEATURE_PREFIX) :]
    return name


def extract_context_extras(context: dict[str, Any]) -> dict[str, Any]:
    """Return non-feature fields (risk, gating) from an existing snapshot."""
    protected = {"strategy_features", "global_features", "regime"}
    return {k: v for k, v in (context or {}).items() if k not in protected}


def lookup_global_features_for_timestamp(
    *,
    timestamp: datetime,
    global_feature_df: pd.DataFrame | None,
    global_feature_normalized_keys: list[str],
    global_feature_timeframes: dict[str, int],
    execution_tf_minutes: int | None,
) -> dict[str, Any]:
    """Fetch cached global features for a specific timestamp."""
    if global_feature_df is None:
        return {}
    if timestamp not in global_feature_df.index:
        raise ValueError(
            f"Timestamp {timestamp} not found in global features cache. "
            "This indicates misaligned data or missing cache rows."
        )
    feature_row = global_feature_df.loc[timestamp]
    features: dict[str, Any] = {}
    columns = list(global_feature_df.columns)
    for idx, column in enumerate(columns):
        val = feature_row[column]
        feature_minutes = global_feature_timeframes.get(column)
        if pd.isna(val):
            if (
                execution_tf_minutes is not None
                and feature_minutes is not None
                and feature_minutes >= execution_tf_minutes
            ):
                raise ValueError(
                    "Global feature "
                    f"{column!r} is NaN at {timestamp}. "
                    "Features at or above the execution timeframe must "
                    "be fully populated."
                )
            # Sub-execution timeframe features are allowed to be NaN; skip them.
            continue
        normalized_val = val
        if idx < len(global_feature_normalized_keys):
            key = global_feature_normalized_keys[idx]
        else:
            key = column
        features[key] = normalized_val
    return features


def build_context_snapshot(
    *,
    timestamp: datetime,
    strategy_context: dict[str, Any],
    rmm_context: dict[datetime, dict[str, Any]] | None,
    regime_builder: Callable[[dict[str, Any] | None], dict[str, Any] | None] | None,
    global_feature_df: pd.DataFrame | None,
    global_feature_normalized_keys: list[str],
    global_feature_timeframes: dict[str, int],
    execution_tf_minutes: int | None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a full context blob aligned to a specific timestamp."""
    global_features = lookup_global_features_for_timestamp(
        timestamp=timestamp,
        global_feature_df=global_feature_df,
        global_feature_normalized_keys=global_feature_normalized_keys,
        global_feature_timeframes=global_feature_timeframes,
        execution_tf_minutes=execution_tf_minutes,
    )
    context: dict[str, Any] = {
        "strategy_features": strategy_context,
        "global_features": global_features,
        "decision_time": timestamp.isoformat(),
    }
    if rmm_context is not None and regime_builder is not None:
        regime_source = rmm_context.get(timestamp)
        if regime_source is None and execution_tf_minutes:
            lookback = pd.to_timedelta(f"{execution_tf_minutes}min")
            regime_source = rmm_context.get(timestamp - lookback)
        if regime_source is not None:
            regime_data = regime_builder(regime_source)
            if regime_data is not None:
                context["regime"] = regime_data
    if extra_fields:
        context.update(extra_fields)
    return context


def realign_context_snapshot(
    *,
    base_context: dict[str, Any] | None,
    timestamp: datetime,
    rmm_context: dict[datetime, dict[str, Any]] | None,
    regime_builder: Callable[[dict[str, Any] | None], dict[str, Any] | None] | None,
    global_feature_df: pd.DataFrame | None,
    global_feature_normalized_keys: list[str],
    global_feature_timeframes: dict[str, int],
    execution_tf_minutes: int | None,
) -> dict[str, Any]:
    """Rebuild an existing context so its globals/regime align to timestamp."""
    strategy_context: dict[str, Any] = {}
    extras: dict[str, Any] = {}
    if base_context:
        strategy_context = base_context.get("strategy_features") or {}
        extras = extract_context_extras(base_context)
    return build_context_snapshot(
        timestamp=timestamp,
        strategy_context=strategy_context,
        rmm_context=rmm_context,
        regime_builder=regime_builder,
        global_feature_df=global_feature_df,
        global_feature_normalized_keys=global_feature_normalized_keys,
        global_feature_timeframes=global_feature_timeframes,
        execution_tf_minutes=execution_tf_minutes,
        extra_fields=extras,
    )


@dataclass
class DecisionSnapshotFactory:
    """Helper that builds DecisionSnapshots with fully-aligned context."""

    rmm_context: dict[datetime, dict[str, Any]] | None
    regime_builder: Callable[[dict[str, Any] | None], dict[str, Any] | None] | None
    global_feature_df: pd.DataFrame | None
    global_feature_keys: list[str]
    global_feature_timeframes: dict[str, int]
    execution_tf_minutes: int | None

    def create(
        self,
        *,
        timestamp: datetime,
        price: float,
        side: str,
        size: float,
        bar_index: int | None,
        strategy_context: dict[str, Any],
        extra_fields: dict[str, Any] | None = None,
    ) -> DecisionSnapshot:
        context = build_context_snapshot(
            timestamp=timestamp,
            strategy_context=strategy_context,
            rmm_context=self.rmm_context,
            regime_builder=self.regime_builder,
            global_feature_df=self.global_feature_df,
            global_feature_normalized_keys=self.global_feature_keys,
            global_feature_timeframes=self.global_feature_timeframes,
            execution_tf_minutes=self.execution_tf_minutes,
            extra_fields=extra_fields,
        )
        return DecisionSnapshot(
            timestamp=timestamp,
            price=price,
            side=side,  # type: ignore[arg-type]
            size=size,
            bar_index=bar_index,
            strategy_features=deepcopy(context["strategy_features"]),
            global_features=deepcopy(context["global_features"]),
            regime=deepcopy(context.get("regime")),
            risk=deepcopy(context.get("risk", {})),
            gating=deepcopy(context.get("gating")),
            context=deepcopy(context),
        )
