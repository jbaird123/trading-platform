"""
Consolidated tests for Regime Market Manager engine logic.

Tasks 22-29: Epic 3 - RMM Features
"""

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
from trading_platform.regime_market_manager.models import RMMConfig

# --- Helper utilities -----------------------------------------------------------


def _make_config(config_dict: dict) -> RMMConfig:
    """Helper to convert dict to RMMConfig for testing.

    Automatically adds a dummy regime if regimes list is empty, since
    RMMConfig requires at least one regime.
    """
    if "regimes" not in config_dict or not config_dict["regimes"]:
        config_dict = config_dict.copy()
        config_dict["regimes"] = [
            {
                "label": "dummy",
                "confidence": 0.5,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 0.0,
                        }
                    ]
                },
            }
        ]
    return RMMConfig(**config_dict)


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

    result = _eval_pred(
        df,
        {
            "condition": "is_above",
            "left": {"ref": "price"},
            "right": {"ref": "threshold"},
        },
    )
    pd.testing.assert_series_equal(
        result, pd.Series([False, True, True, True], index=df.index)
    )

    result = _eval_pred(
        df,
        {
            "condition": "is_below",
            "left": {"ref": "price"},
            "right": {"ref": "threshold"},
        },
    )
    pd.testing.assert_series_equal(
        result, pd.Series([True, False, False, False], index=df.index)
    )

    result = _eval_pred(
        df,
        {
            "condition": "cross_above",
            "left": {"ref": "price"},
            "right": {"ref": "threshold"},
        },
    )
    pd.testing.assert_series_equal(
        result, pd.Series([False, True, False, False], index=df.index)
    )

    result = _eval_pred(
        df,
        {
            "condition": "cross_below",
            "left": {"ref": "price"},
            "right": {"ref": "threshold"},
        },
    )
    pd.testing.assert_series_equal(
        result, pd.Series([False, False, False, False], index=df.index)
    )


def test_eval_pred_unknown_condition_defaults_false() -> None:
    df = pd.DataFrame(
        {"price": [1.0, 1.5], "threshold": [1.2, 1.2]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    pred = {
        "condition": "unknown_condition",
        "left": {"ref": "price"},
        "right": {"ref": "threshold"},
    }
    # Implementation raises ValueError for safety (fail loudly)
    with pytest.raises(ValueError, match="Unrecognized RMM condition"):
        _eval_pred(df, pred)
    # Missing condition key also raises
    with pytest.raises(ValueError, match="Unrecognized RMM condition"):
        _eval_pred(df, {"left": {"ref": "price"}, "right": {"ref": "threshold"}})


def test_eval_block_any_of() -> None:
    df = pd.DataFrame(
        {"indicator1": [1.0, 0.5], "indicator2": [0.8, 1.2], "threshold": [0.9, 0.9]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    block = {
        "any_of": [
            {
                "condition": "is_above",
                "left": {"ref": "indicator1"},
                "right": {"ref": "threshold"},
            },
            {
                "condition": "is_above",
                "left": {"ref": "indicator2"},
                "right": {"ref": "threshold"},
            },
        ]
    }
    result = _eval_block(df, block)
    pd.testing.assert_series_equal(result, pd.Series([True, True], index=df.index))


def test_eval_block_empty_conditions() -> None:
    df = pd.DataFrame(
        {"value": [1.0, 2.0]}, index=pd.date_range("2024-01-01", periods=2)
    )
    pd.testing.assert_series_equal(
        _eval_block(df, {"other_field": []}),
        pd.Series([False, False], index=df.index),
    )


# --- Engine-level behaviour -----------------------------------------------------


def _engine_config() -> RMMConfig:
    return RMMConfig(
        features=[
            {"name": "EMA(20)", "type": "EMA", "params": {"length": 20}},  # type: ignore[list-item]
            {"name": "ADX(14)", "type": "ADX", "params": {"length": 14}},  # type: ignore[list-item]
        ],
        regimes=[
            {  # type: ignore[list-item]
                "label": "trend_up",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "ADX(14)"},
                            "right": 25.0,
                        }
                    ]
                },
            },
            {  # type: ignore[list-item]
                "label": "range",
                "confidence": 0.6,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"ref": "ADX(14)"},
                            "right": 15.0,
                        }
                    ]
                },
            },
        ],
    )


def test_rmm_engine_validate_config_without_jsonschema() -> None:
    """Test that RMM engine validation now uses Pydantic models.

    Validation happens automatically when creating an RMMConfig Pydantic model.
    Invalid configs will raise pydantic ValidationError.
    """
    # Valid config should create successfully
    valid_config: RMMConfig = RMMConfig(
        regimes=[
            {  # type: ignore[list-item]
                "label": "test",
                "confidence": 0.5,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 1.0,
                        }
                    ]
                },
            }
        ]
    )
    engine = RMMEngine(config=valid_config)
    assert engine.config is not None

    # Invalid config should raise ValidationError
    with pytest.raises(Exception):  # Will be pydantic ValidationError
        RMMConfig(regimes=[])


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

    with patch(
        "trading_platform.regime_market_manager.engine.resample_ohlc"
    ) as mock_resample, patch(
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
    """Test RMM engine classification.

    TODO: This test needs investigation. After Pydantic migration, the RMM
    engine is returning 'trend_up' instead of 'unknown' when ADX is between
    thresholds. This may indicate an issue with how mocking works or a
    change in the classification logic that needs review.
    For now, updated to match current behavior.
    """
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

    with patch(
        "trading_platform.regime_market_manager.engine.resample_ohlc"
    ) as mock_resample, patch(
        "trading_platform.regime_market_manager.engine.compute_features"
    ) as mock_features:
        daily = hourly_data.copy()
        daily.index = pd.date_range("2024-01-01", periods=1, freq="D")
        mock_resample.return_value = daily
        features = daily.copy()
        features["ADX(14)"] = 20.0  # Between configured thresholds
        mock_features.return_value = features

        result = engine.classify_daily(hourly_data)
        assert len(result) == 1
        # ADX is 20, which is between trend_up (>25) and range (<15) thresholds
        # So it should return 'unknown' with confidence 0.0
        assert result.iloc[0]["label"] == "unknown"
        assert result.iloc[0]["confidence"] == 0.0


def test_rmm_engine_allowed_sides_for() -> None:
    assert RMMEngine.allowed_sides_for("trend_up", 0.3, {"min_confidence": 0.5}) == []
    assert (
        RMMEngine.allowed_sides_for("trend_up", 0.8, {"allow_labels": ["trend_down"]})
        == []
    )
    assert (
        RMMEngine.allowed_sides_for("trend_up", 0.8, {"block_labels": ["trend_up"]})
        == []
    )
    assert RMMEngine.allowed_sides_for("trend_up", 0.8, {}) == ["long"]
    assert RMMEngine.allowed_sides_for("trend_down", 0.8, {}) == ["short"]
    # Bug #1 fix: range now returns ["long", "short"] instead of []
    assert RMMEngine.allowed_sides_for("range", 0.8, {}) == ["long", "short"]


def test_rmm_engine_project_to_index_empty_daily() -> None:
    # Need a minimal valid config with at least one regime
    minimal_config = _make_config(
        {
            "regimes": [
                {
                    "label": "test",
                    "confidence": 0.5,
                    "conditions": {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": "close",
                                "right": 1.0,
                            }
                        ]
                    },
                }
            ]
        }
    )
    engine = RMMEngine(config=minimal_config)
    target_index = pd.date_range("2024-01-01", periods=3, freq="h")
    empty_daily = pd.DataFrame(columns=["label", "confidence"])

    result = engine.project_to_index(empty_daily, target_index, policy={})
    expected = pd.DataFrame(
        {
            "label": ["unknown"] * 3,
            "confidence": [0.0] * 3,
            "raw_label": ["unknown"] * 3,
            "raw_confidence": [0.0] * 3,
            "bars_in_state": [0] * 3,
            "cooldown_remaining": [0] * 3,
            "allowed_sides": [[] for _ in range(3)],
        },
        index=target_index,
    )
    expected["allowed_sides"] = expected["allowed_sides"].astype("object")
    expected = expected[result.columns]
    pd.testing.assert_frame_equal(result, expected)


def test_rmm_engine_project_to_index_with_daily_data() -> None:
    # Need a minimal valid config with at least one regime
    minimal_config = _make_config(
        {
            "regimes": [
                {
                    "label": "test",
                    "confidence": 0.5,
                    "conditions": {
                        "all_of": [
                            {
                                "condition": "is_above",
                                "left": "close",
                                "right": 1.0,
                            }
                        ]
                    },
                }
            ]
        }
    )
    engine = RMMEngine(config=minimal_config)
    # Target index on 2024-01-02 (second day)
    target_index = pd.date_range("2024-01-02 00:00", periods=6, freq="h")
    # Daily data for 2024-01-01 and 2024-01-02
    # project_to_index shifts by 1 to prevent lookahead bias
    daily = pd.DataFrame(
        {"label": ["trend_up", "trend_up"], "confidence": [0.8, 0.8]},
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )
    result = engine.project_to_index(
        daily, target_index, policy={"min_confidence": 0.5}
    )
    assert len(result) == 6
    # After shift(1), day 2024-01-02 uses label from 2024-01-01
    assert all(result["label"] == "trend_up")
    assert all(result["confidence"] == 0.8)
    assert all(result["raw_label"] == "unknown")
    assert all(result["raw_confidence"] == 0.0)
    assert all(result["bars_in_state"] == 0)
    assert all(result["cooldown_remaining"] == 0)
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

    engine = RMMEngine(config=_make_config(config))

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
    # classify_daily returns label, confidence, and intermediate calculations
    assert "label" in daily.columns
    assert "confidence" in daily.columns
    assert not daily.empty
    assert (daily["confidence"] >= 0).all() and (daily["confidence"] <= 1).all()


def test_classify_regime_with_already_resampled_data() -> None:
    """Test classify_regime when data is already resampled."""
    # Validates: [REQ-RMM-001] Handle pre-resampled data
    import pandas as pd
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [],
        "regimes": [
            {
                "label": "default",
                "confidence": 0.5,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 0.0,
                        }
                    ]
                },
            }
        ],
        "timeframe": "1D",
    }

    engine = RMMEngine(config=_make_config(config))

    # Already resampled daily data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.05, 1.15],
            "low": [0.95, 1.05],
            "close": [1.02, 1.12],
            "volume": [1000, 1100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    assert "label" in result.columns
    assert "confidence" in result.columns
    assert len(result) == 2


def test_classify_regime_without_explicit_timeframe() -> None:
    """Test classify_regime uses config timeframe when not provided."""
    # Validates: [REQ-RMM-002] Use config timeframe as default
    import pandas as pd
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [],
        "regimes": [
            {
                "label": "default",
                "confidence": 0.5,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": "close",
                            "right": 0.0,
                        }
                    ]
                },
            }
        ],
        "timeframe": "1H",
    }

    engine = RMMEngine(config=_make_config(config))

    df = pd.DataFrame(
        {
            "open": [1.0] * 60,
            "high": [1.05] * 60,
            "low": [0.95] * 60,
            "close": [1.02] * 60,
            "volume": [1000] * 60,
        },
        index=pd.date_range("2024-01-01", periods=60, freq="min", tz="UTC"),
    )

    result = engine.classify_regime(df, timeframe=None)  # Should use "1H" from config

    assert "label" in result.columns


# --- Task 22: New RMM Features ---------------------------------------------


def test_calculates_atr_percentile() -> None:
    """Task 22: Test atr_percentile feature calculation."""
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 14, "lookback": 20},
            }
        ],
        "regimes": [],
    }

    engine = RMMEngine(config=_make_config(config))

    # Create test data with known ATR pattern
    df = pd.DataFrame(
        {
            "open": [100.0] * 50,
            "high": [101.0 + i * 0.1 for i in range(50)],
            "low": [99.0 - i * 0.1 for i in range(50)],
            "close": [100.5] * 50,
            "volume": [1000] * 50,
        },
        index=pd.date_range("2024-01-01", periods=50, freq="D"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    # Feature should exist and be a percentile (0-100)
    assert "atr_pct" in result.columns
    assert (result["atr_pct"].dropna() >= 0).all()
    assert (result["atr_pct"].dropna() <= 100).all()


def test_calculates_realized_volatility() -> None:
    """Task 22: Test realized_volatility feature calculation."""
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [
            {
                "name": "rvol",
                "type": "RealizedVolatility",
                "params": {"length": 20},
            }
        ],
        "regimes": [],
    }

    engine = RMMEngine(config=_make_config(config))

    # Create test data with varying returns
    close_prices = [100.0]
    for i in range(1, 50):
        # Alternating small changes
        close_prices.append(close_prices[-1] * (1 + 0.01 * ((-1) ** i)))

    df = pd.DataFrame(
        {
            "open": close_prices,
            "high": [c * 1.01 for c in close_prices],
            "low": [c * 0.99 for c in close_prices],
            "close": close_prices,
            "volume": [1000] * 50,
        },
        index=pd.date_range("2024-01-01", periods=50, freq="D"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    # Feature should exist and be positive (volatility >= 0)
    assert "rvol" in result.columns
    assert (result["rvol"].dropna() >= 0).all()


def test_calculates_volume_zscore() -> None:
    """Task 22: Test volume_zscore feature calculation."""
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [
            {"name": "vol_z", "type": "VolumeZScore", "params": {"length": 20}}
        ],
        "regimes": [],
    }

    engine = RMMEngine(config=_make_config(config))

    # Create test data with spike in volume at the end
    volumes = [1000.0] * 40 + [3000.0] * 10  # Volume spike in last 10 bars

    df = pd.DataFrame(
        {
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.0] * 50,
            "volume": volumes,
        },
        index=pd.date_range("2024-01-01", periods=50, freq="D"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    # Feature should exist
    assert "vol_z" in result.columns
    # Last bar (with volume spike) should have positive z-score
    assert result["vol_z"].iloc[-1] > 0


# --- Task 26: New RMM Predicates ------------------------------------------


def test_predicate_percentile_is_above() -> None:
    """Task 26: Test percentile_is_above predicate."""
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 5, "lookback": 20},
            }
        ],
        "regimes": [
            {
                "label": "high_vol",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "percentile_is_above",
                            "left": {"ref": "atr_pct"},
                            "right": 90,
                        }
                    ]
                },
            }
        ],
    }

    engine = RMMEngine(config=_make_config(config))

    # Create test data with dramatically increasing volatility at end
    highs = [101.0] * 30 + [101.0 + (i - 30) * 0.5 for i in range(30, 50)]
    lows = [99.0] * 30 + [99.0 - (i - 30) * 0.5 for i in range(30, 50)]

    df = pd.DataFrame(
        {
            "open": [100.0] * 50,
            "high": highs,
            "low": lows,
            "close": [100.5] * 50,
            "volume": [1000] * 50,
        },
        index=pd.date_range("2024-01-01", periods=50, freq="D"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    # Last bars should trigger high_vol regime (ATR percentile > 90)
    # Due to percentile calculation, the very last bar will be at 100th percentile
    assert result["label"].iloc[-1] == "high_vol"
    assert result["confidence"].iloc[-1] == 0.8


def test_predicate_volatility_is_between() -> None:
    """Task 26: Test volatility_is_between predicate."""
    from trading_platform.regime_market_manager.engine import RMMEngine

    config = {
        "features": [
            {
                "name": "rvol",
                "type": "RealizedVolatility",
                "params": {"length": 10},
            }
        ],
        "regimes": [
            {
                "label": "moderate_vol",
                "confidence": 0.7,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "volatility_is_between",
                            "left": {"ref": "rvol"},
                            "lower": 0.005,
                            "upper": 0.015,
                        }
                    ]
                },
            }
        ],
    }

    engine = RMMEngine(config=_make_config(config))

    # Create test data with moderate volatility
    close_prices = [100.0]
    for i in range(1, 50):
        # Small consistent moves (moderate volatility)
        close_prices.append(close_prices[-1] * (1 + 0.008 * ((-1) ** i)))

    df = pd.DataFrame(
        {
            "open": close_prices,
            "high": [c * 1.005 for c in close_prices],
            "low": [c * 0.995 for c in close_prices],
            "close": close_prices,
            "volume": [1000] * 50,
        },
        index=pd.date_range("2024-01-01", periods=50, freq="D"),
    )

    result = engine.classify_regime(df, timeframe="1D", already_resampled=True)

    # Should classify as moderate_vol in later bars
    assert result["label"].iloc[-1] == "moderate_vol"
    assert result["confidence"].iloc[-1] == 0.7
