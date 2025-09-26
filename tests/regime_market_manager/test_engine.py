"""Consolidated tests for Regime Market Manager engine logic."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from trading_platform.regime_market_manager.engine import (
    RMMEngine,
    _eval_block,
    _eval_pred,
    _op_series,
)


# --- Helper utilities -----------------------------------------------------------

def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [1.0, 1.1, 1.2], "volume": [100, 200, 300]},
        index=pd.date_range("2024-01-01", periods=3),
    )


# --- Base operand/predicate helpers --------------------------------------------

def test_op_series_edge_cases() -> None:
    df = _sample_df()
    result = _op_series(df, 5)
    pd.testing.assert_series_equal(result, pd.Series([5.0, 5.0, 5.0], index=df.index))

    result = _op_series(df, "invalid_column")
    pd.testing.assert_series_equal(result, pd.Series([0.0, 0.0, 0.0], index=df.index))

    result = _op_series(df, {"ref": "close"})
    pd.testing.assert_series_equal(result, df["close"].astype(float))


def test_eval_pred_known_conditions() -> None:
    df = pd.DataFrame(
        {"price": [1.0, 1.5, 1.2, 1.8], "threshold": [1.1, 1.1, 1.1, 1.1]},
        index=pd.date_range("2024-01-01", periods=4),
    )

    result = _eval_pred(df, {"condition": "is_above", "left": "price", "right": "threshold"})
    pd.testing.assert_series_equal(result, pd.Series([False, True, True, True], index=df.index))

    result = _eval_pred(df, {"condition": "is_below", "left": "price", "right": "threshold"})
    pd.testing.assert_series_equal(result, pd.Series([True, False, False, False], index=df.index))

    result = _eval_pred(df, {"condition": "cross_above", "left": "price", "right": "threshold"})
    pd.testing.assert_series_equal(result, pd.Series([False, True, False, False], index=df.index))

    result = _eval_pred(df, {"condition": "cross_below", "left": "price", "right": "threshold"})
    pd.testing.assert_series_equal(result, pd.Series([False, False, False, False], index=df.index))


def test_eval_pred_unknown_condition_defaults_false() -> None:
    df = pd.DataFrame(
        {"price": [1.0, 1.5], "threshold": [1.2, 1.2]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    pred = {"condition": "unknown_condition", "left": "price", "right": "threshold"}
    pd.testing.assert_series_equal(
        _eval_pred(df, pred), pd.Series([False, False], index=df.index)
    )
    pd.testing.assert_series_equal(
        _eval_pred(df, {"left": "price", "right": "threshold"}),
        pd.Series([False, False], index=df.index),
    )


def test_eval_block_any_of() -> None:
    df = pd.DataFrame(
        {"indicator1": [1.0, 0.5], "indicator2": [0.8, 1.2], "threshold": [0.9, 0.9]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    block = {
        "any_of": [
            {"condition": "is_above", "left": "indicator1", "right": "threshold"},
            {"condition": "is_above", "left": "indicator2", "right": "threshold"},
        ]
    }
    result = _eval_block(df, block)
    pd.testing.assert_series_equal(result, pd.Series([True, True], index=df.index))


def test_eval_block_empty_conditions() -> None:
    df = pd.DataFrame({"value": [1.0, 2.0]}, index=pd.date_range("2024-01-01", periods=2))
    pd.testing.assert_series_equal(
        _eval_block(df, {"other_field": []}),
        pd.Series([False, False], index=df.index),
    )


# --- Engine-level behaviour -----------------------------------------------------

def _engine_config() -> dict:
    return {
        "features": ["EMA(20)", "ADX(14)"],
        "regimes": [
            {
                "label": "trend_up",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {"condition": "is_above", "left": "ADX(14)", "right": 25.0}
                    ]
                },
            },
            {
                "label": "range",
                "confidence": 0.6,
                "conditions": {
                    "all_of": [
                        {"condition": "is_below", "left": "ADX(14)", "right": 15.0}
                    ]
                },
            },
        ],
    }


def test_rmm_engine_validate_config_requires_jsonschema() -> None:
    with patch("trading_platform.regime_market_manager.engine.jsonschema", None):
        with pytest.raises(ValueError, match="jsonschema is required for RMM"):
            RMMEngine.validate_config({"regimes": []})


def test_rmm_engine_classify_daily_matches_regime() -> None:
    engine = RMMEngine(config=_engine_config())
    hourly_data = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.3] * 6,
            "high": [1.05, 1.15, 1.25, 1.35] * 6,
            "low": [0.95, 1.05, 1.15, 1.25] * 6,
            "close": [1.02, 1.12, 1.22, 1.32] * 6,
            "volume": [100, 200, 300, 400] * 6,
        },
        index=pd.date_range("2024-01-01", periods=24, freq="h"),
    )

    with patch("trading_platform.regime_market_manager.engine.resample_ohlc") as mock_resample, patch(
        "trading_platform.regime_market_manager.engine.compute_features"
    ) as mock_features:
        daily = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.35],
                "low": [0.95],
                "close": [1.32],
                "volume": [2400],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="D"),
        )
        mock_resample.return_value = daily
        features = daily.copy()
        features["ADX(14)"] = 30.0
        mock_features.return_value = features

        result = engine.classify_daily(hourly_data)
        assert len(result) == 1
        assert result.iloc[0]["label"] == "trend_up"
        assert result.iloc[0]["confidence"] == 0.8


def test_rmm_engine_classify_daily_unknown_regime() -> None:
    engine = RMMEngine(config=_engine_config())
    hourly_data = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.05],
            "low": [0.95],
            "close": [1.02],
            "volume": [100],
        },
        index=pd.date_range("2024-01-01", periods=1, freq="h"),
    )

    with patch("trading_platform.regime_market_manager.engine.resample_ohlc") as mock_resample, patch(
        "trading_platform.regime_market_manager.engine.compute_features"
    ) as mock_features:
        daily = hourly_data.copy()
        daily.index = pd.date_range("2024-01-01", periods=1, freq="D")
        mock_resample.return_value = daily
        features = daily.copy()
        features["ADX(14)"] = 20.0  # Between configured thresholds -> no match
        mock_features.return_value = features

        result = engine.classify_daily(hourly_data)
        assert len(result) == 1
        assert result.iloc[0]["label"] == "unknown"
        assert result.iloc[0]["confidence"] == 0.0


def test_rmm_engine_allowed_sides_for() -> None:
    assert RMMEngine.allowed_sides_for("trend_up", 0.3, {"min_confidence": 0.5}) == []
    assert RMMEngine.allowed_sides_for("trend_up", 0.8, {"allow_labels": ["trend_down"]}) == []
    assert RMMEngine.allowed_sides_for("trend_up", 0.8, {"block_labels": ["trend_up"]}) == []
    assert RMMEngine.allowed_sides_for("trend_up", 0.8, {}) == ["long"]
    assert RMMEngine.allowed_sides_for("trend_down", 0.8, {}) == ["short"]
    assert RMMEngine.allowed_sides_for("range", 0.8, {}) == []


def test_rmm_engine_project_to_index_empty_daily() -> None:
    engine = RMMEngine(config={})
    target_index = pd.date_range("2024-01-01", periods=3, freq="h")
    empty_daily = pd.DataFrame(columns=["label", "confidence"])

    result = engine.project_to_index(empty_daily, target_index, policy={})
    expected = pd.DataFrame(
        {
            "label": ["unknown"] * 3,
            "confidence": [0.0] * 3,
            "allowed_sides": [[] for _ in range(3)],
        },
        index=target_index,
    )
    expected["allowed_sides"] = expected["allowed_sides"].astype("object")
    pd.testing.assert_frame_equal(result, expected)


def test_rmm_engine_project_to_index_with_daily_data() -> None:
    engine = RMMEngine(config={})
    target_index = pd.date_range("2024-01-01 00:00", periods=6, freq="h")
    daily = pd.DataFrame(
        {"label": ["trend_up"], "confidence": [0.8]},
        index=pd.date_range("2024-01-01", periods=1, freq="D"),
    )
    result = engine.project_to_index(daily, target_index, policy={"min_confidence": 0.5})
    assert len(result) == 6
    assert all(result["label"] == "trend_up")
    assert all(result["confidence"] == 0.8)
    assert all(sides == ["long"] for sides in result["allowed_sides"])


def test_rmm_engine_classify_daily_end_to_end() -> None:
    config = {
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": 3},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": 5},
                "source": "close",
            },
            {"name": "adx", "type": "ADX", "params": {"length": 5}},
        ],
        "regimes": [
            {
                "label": "trend_up",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"},
                        }
                    ]
                },
            },
            {
                "label": "trend_down",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"ref": "ema_fast"},
                            "right": {"ref": "ema_slow"},
                        }
                    ]
                },
            },
        ],
    }

    engine = RMMEngine(config=config)
    RMMEngine.validate_config(config)

    start = pd.Timestamp("2023-01-01")
    idx = [start + pd.Timedelta(hours=i) for i in range(48)]
    close = [100 + i * 0.1 for i in range(48)]
    hourly = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1] * len(close),
        },
        index=idx,
    )

    daily = engine.classify_daily(hourly)
    assert set(daily.columns) == {"label", "confidence"}
    assert not daily.empty
    assert (daily["confidence"] >= 0).all() and (daily["confidence"] <= 1).all()
