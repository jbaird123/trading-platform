"""Tests for grid feature pattern search utilities."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from trading_platform.ai.models.feature_groups import add_normalized_risk_features
from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    DEFAULT_GROUPS,
    _collect_features,
    collect_patterns,
    evaluate_context,
    generate_group_combinations,
    split_data,
)
from trading_platform.rmm_analysis.train_profitability_selected_groups import (
    DEFAULT_COMBOS,
    _parse_combos,
    _resolve_contexts,
)


def test_generate_group_combinations_respects_max_size() -> None:
    combos = generate_group_combinations(["a", "b", "c"], max_size=2)
    assert combos == [
        ("a",),
        ("b",),
        ("c",),
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
    ]


def test_collect_patterns_concatenates_groups() -> None:
    patterns = collect_patterns(["alignment", "volatility"])
    for group in ("alignment", "volatility"):
        for pattern in DEFAULT_GROUPS[group]:
            assert pattern in patterns


def _build_context_dataframe() -> pd.DataFrame:
    dates = pd.date_range(
        "2018-01-01",
        "2023-12-31",
        freq="7D",
        tz="UTC",
    )
    size = len(dates)
    frame = pd.DataFrame(
        {
            "entry_time": dates,
            "r_multiple": np.sin(np.linspace(-3.0, 3.0, size)),
            "initial_stop_loss_price": np.linspace(1.0, 2.0, size),
            "entry_price": np.linspace(1.05, 2.05, size),
            "side": np.where(np.arange(size) % 2 == 0, "long", "short"),
            "symbol": "EURUSD",
            "execution_timeframe": "15min",
            "strategy_archetype": "trend_following",
        }
    )
    frame["context_at_entry_strategy_features_atr_14"] = np.linspace(
        0.5,
        1.5,
        size,
    )
    for pattern in collect_patterns(["alignment"]):
        column = f"context_at_entry_global_features_{pattern}"
        frame[column] = np.linspace(0.1, 0.9, size)
    return add_normalized_risk_features(frame)


def test_evaluate_context_produces_metrics() -> None:
    df = _build_context_dataframe()
    train_df, test_df = split_data(df)
    patterns = collect_patterns(["alignment"])
    result = evaluate_context(
        train_df,
        test_df,
        patterns,
        random_state=7,
        n_estimators=8,
    )
    assert result is not None
    metrics, importance_df = result
    rf_sign = cast(float, metrics["rf_sign_accuracy"])
    assert rf_sign >= 0.4
    auc_value = cast(float, metrics["logistic_sign_auc"])
    assert auc_value >= 0.4 or np.isnan(auc_value)
    assert importance_df is not None
    assert not importance_df.empty


def test_collect_features_adds_normalized_risk_features() -> None:
    df = _build_context_dataframe()
    patterns = collect_patterns(["alignment"])
    features = _collect_features(df, patterns)
    assert "risk_distance_abs" in features.columns
    assert "risk_distance_pct_entry" in features.columns
    assert "risk_distance_atr_ratio" in features.columns
    assert "initial_stop_loss_price" not in features.columns


def test_parse_combos_allows_defaults_and_custom() -> None:
    assert _parse_combos(None) == [tuple(combo.split("+")) for combo in DEFAULT_COMBOS]
    combos = _parse_combos(["alignment+structure", "calendar"])
    assert combos == [("alignment", "structure"), ("calendar",)]


def test_resolve_contexts_from_dataframe() -> None:
    df = _build_context_dataframe()
    contexts = _resolve_contexts(df, None)
    assert contexts == [("15min", "trend_following")]
    contexts = _resolve_contexts(df, ["15min_trend_following"])
    assert contexts == [("15min", "trend_following")]


def test_resolve_contexts_validates_format() -> None:
    df = _build_context_dataframe()
    try:
        _ = _resolve_contexts(df, ["invalid"])
    except ValueError as exc:
        assert "must be formatted" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for malformed context")
