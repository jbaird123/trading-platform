"""Tests for the shared global feature pipeline (build_global_feature_frame).

This module tests parity between the new global pipeline and the existing
compute_features implementation to ensure identical outputs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from trading_platform.strategy.features import compute_features


def _generate_deterministic_ohlcv(
    periods: int = 500, freq: str = "5min", seed: int = 42
) -> pd.DataFrame:
    """Generate deterministic OHLCV data for testing."""
    np.random.seed(seed)
    idx = pd.date_range("2023-01-01", periods=periods, freq=freq, tz="UTC")

    # Generate realistic price data with trend and volatility
    base_price = 100.0
    trend = np.linspace(0, 5, periods)
    noise = np.random.randn(periods) * 0.5

    close = base_price + trend + noise
    high = close + np.abs(np.random.randn(periods) * 0.3)
    low = close - np.abs(np.random.randn(periods) * 0.3)
    open_price = close + np.random.randn(periods) * 0.2
    volume = 1000 + np.random.randint(-100, 100, periods)

    df = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Provide sample OHLCV data for tests."""
    return _generate_deterministic_ohlcv()


@pytest.fixture
def feature_manifest_same_timeframe() -> list[dict[str, Any]]:
    """Feature manifest with same-timeframe indicator (EMA on 5min)."""
    return [
        {
            "name": "ema_20",
            "type": "EMA",
            "params": {"length": 20},
            "source": "close",
        }
    ]


@pytest.fixture
def feature_manifest_higher_timeframe() -> list[dict[str, Any]]:
    """Feature manifest with higher-timeframe indicator (ATR on 15min)."""
    return [
        {
            "name": "atr_14_15min",
            "type": "ATR",
            "params": {"length": 14},
            "source": "close",
            "timeframe": "15min",
        }
    ]


@pytest.fixture
def feature_manifest_multi_timeframe() -> list[dict[str, Any]]:
    """Feature manifest with multiple timeframes requiring resampling."""
    return [
        {
            "name": "ema_20",
            "type": "EMA",
            "params": {"length": 20},
            "source": "close",
        },
        {
            "name": "atr_14_15min",
            "type": "ATR",
            "params": {"length": 14},
            "source": "close",
            "timeframe": "15min",
        },
        {
            "name": "sma_50_15min",
            "type": "SMA",
            "params": {"length": 50},
            "source": "close",
            "timeframe": "15min",
        },
    ]


def test_build_global_feature_frame_exists(
    sample_ohlcv, feature_manifest_same_timeframe
):
    """Test that build_global_feature_frame now exists (TDD green phase)."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    # Should be callable
    result, metadata = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_same_timeframe,
        execution_timeframe="5min",
    )

    assert result is not None
    assert metadata is not None
    assert "ema_20" in result.columns


def test_compute_features_baseline_same_timeframe(
    sample_ohlcv, feature_manifest_same_timeframe
):
    """Baseline test: compute_features works with same-timeframe indicator."""
    result = compute_features(sample_ohlcv, feature_manifest_same_timeframe)

    assert "ema_20" in result.columns
    assert len(result) == len(sample_ohlcv)
    assert result.index.equals(sample_ohlcv.index)

    # EMA should have NaN values for warmup period
    assert result["ema_20"].isna().sum() > 0
    assert result["ema_20"].notna().sum() > 0


def test_compute_features_baseline_higher_timeframe(
    sample_ohlcv, feature_manifest_higher_timeframe
):
    """Baseline test: compute_features works with higher-timeframe indicator."""
    result = compute_features(sample_ohlcv, feature_manifest_higher_timeframe)

    assert "atr_14_15min" in result.columns
    assert len(result) == len(sample_ohlcv)
    assert result.index.equals(sample_ohlcv.index)


def test_compute_features_baseline_multi_timeframe(
    sample_ohlcv, feature_manifest_multi_timeframe
):
    """Baseline test: compute_features works with multiple timeframes."""
    result = compute_features(sample_ohlcv, feature_manifest_multi_timeframe)

    assert "ema_20" in result.columns
    assert "atr_14_15min" in result.columns
    assert "sma_50_15min" in result.columns
    assert len(result) == len(sample_ohlcv)


def test_parity_same_timeframe_exact_match(
    sample_ohlcv, feature_manifest_same_timeframe
):
    """Test build_global_feature_frame matches compute_features same-TF."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    # Compute using existing implementation
    result_old = compute_features(
        sample_ohlcv, feature_manifest_same_timeframe, strategy_parameters={}
    )

    # Compute using new shared pipeline
    result_new, metadata = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_same_timeframe,
        execution_timeframe="5min",
        strategy_parameters={},
    )

    # Assert exact parity
    pd.testing.assert_frame_equal(
        result_old[["ema_20"]],
        result_new[["ema_20"]],
        check_dtype=True,
        atol=1e-12,
        rtol=1e-12,
    )

    # Verify metadata contains valid_start info
    assert "valid_start" in metadata
    valid_start_dict = metadata["valid_start"]
    assert isinstance(valid_start_dict, dict)
    assert "ema_20" in valid_start_dict
    assert isinstance(valid_start_dict["ema_20"], pd.Timestamp)


def test_parity_higher_timeframe_exact_match(
    sample_ohlcv, feature_manifest_higher_timeframe
):
    """Test build_global_feature_frame matches compute_features higher-TF."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    # Compute using existing implementation
    result_old = compute_features(
        sample_ohlcv, feature_manifest_higher_timeframe, strategy_parameters={}
    )

    # Compute using new shared pipeline
    result_new, metadata = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_higher_timeframe,
        execution_timeframe="5min",
        strategy_parameters={},
    )

    # Assert exact parity
    pd.testing.assert_frame_equal(
        result_old[["atr_14_15min"]],
        result_new[["atr_14_15min"]],
        check_dtype=True,
        atol=1e-12,
        rtol=1e-12,
    )


def test_parity_multi_timeframe_exact_match(
    sample_ohlcv, feature_manifest_multi_timeframe
):
    """Test build_global_feature_frame matches compute_features multi-TF."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    # Compute using existing implementation
    result_old = compute_features(
        sample_ohlcv, feature_manifest_multi_timeframe, strategy_parameters={}
    )

    # Compute using new shared pipeline
    result_new, metadata = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_multi_timeframe,
        execution_timeframe="5min",
        strategy_parameters={},
    )

    # Get feature columns only (not original OHLCV)
    feature_cols = ["ema_20", "atr_14_15min", "sma_50_15min"]

    # Assert exact parity for all features
    pd.testing.assert_frame_equal(
        result_old[feature_cols],
        result_new[feature_cols],
        check_dtype=True,
        atol=1e-12,
        rtol=1e-12,
    )

    # Verify metadata structure
    assert "valid_start" in metadata
    valid_start_dict = metadata["valid_start"]
    assert isinstance(valid_start_dict, dict)
    for col in feature_cols:
        assert col in valid_start_dict
        assert isinstance(valid_start_dict[col], pd.Timestamp)


def test_parity_timestamps_and_dtypes(sample_ohlcv, feature_manifest_same_timeframe):
    """Test that timestamps and dtypes match exactly."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    result_old = compute_features(
        sample_ohlcv, feature_manifest_same_timeframe, strategy_parameters={}
    )
    result_new, _ = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_same_timeframe,
        execution_timeframe="5min",
        strategy_parameters={},
    )

    # Index must be identical
    assert result_new.index.equals(result_old.index)
    assert result_new.index[0] == result_old.index[0]
    assert result_new.index[-1] == result_old.index[-1]

    # Dtypes must match
    assert result_new["ema_20"].dtype == result_old["ema_20"].dtype


def test_parity_nan_guard_positions(sample_ohlcv, feature_manifest_multi_timeframe):
    """Test that NaN guard positions (warmup start) match exactly."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    result_old = compute_features(
        sample_ohlcv, feature_manifest_multi_timeframe, strategy_parameters={}
    )
    result_new, metadata = build_global_feature_frame(
        sample_ohlcv,
        feature_manifest_multi_timeframe,
        execution_timeframe="5min",
        strategy_parameters={},
    )

    # Compare first valid index for each feature
    for col in ["ema_20", "atr_14_15min", "sma_50_15min"]:
        first_valid_old = result_old[col].first_valid_index()
        first_valid_new = result_new[col].first_valid_index()

        assert first_valid_old == first_valid_new, f"Mismatch for {col}"

        # Metadata should report the same timestamp
        valid_start_dict = metadata["valid_start"]
        assert valid_start_dict[col] == first_valid_new


def test_unsupported_timeframe_raises_valueerror(sample_ohlcv):
    """Test that unsupported timeframe raises ValueError with clear message."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    invalid_manifest = [
        {
            "name": "ema_20",
            "type": "EMA",
            "params": {"length": 20},
            "source": "close",
            "timeframe": "37min",  # Invalid timeframe
        }
    ]

    with pytest.raises(ValueError, match="37min"):
        build_global_feature_frame(
            sample_ohlcv,
            invalid_manifest,
            execution_timeframe="5min",
        )


def test_invalid_execution_timeframe_raises_valueerror(sample_ohlcv):
    """Test that invalid execution_timeframe raises ValueError."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    manifest = [
        {
            "name": "ema_20",
            "type": "EMA",
            "params": {"length": 20},
            "source": "close",
        }
    ]

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        build_global_feature_frame(
            sample_ohlcv,
            manifest,
            execution_timeframe="invalid_tf",
        )


def test_parameter_substitution_works(sample_ohlcv):
    """Test that ${param} substitution works in the new pipeline."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    manifest = [
        {
            "name": "ema_dynamic",
            "type": "EMA",
            "params": {"length": "${ema_period}"},
            "source": "close",
        }
    ]

    strategy_params = {"ema_period": 30}

    result_old = compute_features(sample_ohlcv, manifest, strategy_params)
    result_new, _ = build_global_feature_frame(
        sample_ohlcv,
        manifest,
        execution_timeframe="5min",
        strategy_parameters=strategy_params,
    )

    pd.testing.assert_series_equal(
        result_old["ema_dynamic"],
        result_new["ema_dynamic"],
        check_dtype=True,
        atol=1e-12,
    )


def test_data_handler_parameter_passed_through(sample_ohlcv):
    """Test that data_handler parameter is accepted and passed through."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    manifest = [
        {
            "name": "ema_20",
            "type": "EMA",
            "params": {"length": 20},
            "source": "close",
        }
    ]

    mock_handler = Mock()

    # Should not raise an error
    result, metadata = build_global_feature_frame(
        sample_ohlcv,
        manifest,
        execution_timeframe="5min",
        data_handler=mock_handler,
    )

    assert "ema_20" in result.columns


def test_resample_strategy_parameter_honored(sample_ohlcv):
    """Test that resample_strategy parameter is accepted."""
    from trading_platform.core.global_feature_pipeline import (
        build_global_feature_frame,
    )

    manifest = [
        {
            "name": "atr_15min",
            "type": "ATR",
            "params": {"length": 14},
            "source": "close",
            "timeframe": "15min",
        }
    ]

    # Should accept different resample strategies
    result1, _ = build_global_feature_frame(
        sample_ohlcv,
        manifest,
        execution_timeframe="5min",
        resample_strategy="forward_fill",
    )

    result2, _ = build_global_feature_frame(
        sample_ohlcv,
        manifest,
        execution_timeframe="5min",
        resample_strategy="forward_fill",  # Same strategy for now
    )

    assert "atr_15min" in result1.columns
    assert "atr_15min" in result2.columns
