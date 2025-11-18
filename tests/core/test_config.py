import logging

import pytest
from pydantic import ValidationError
from trading_platform.core import paths
from trading_platform.core.config import (
    FeatureConfig,
    GlobalFeatureSetConfig,
    RunConfig,
)


def test_run_config_auto_populate_instrument_from_data_request() -> None:
    """Test instrument auto-populated from data_request."""
    # Validates: [REQ-CONFIG-001] Auto-populate instrument
    from trading_platform.core.config import RunConfig

    config = RunConfig.model_validate(
        {
            "run_id": "test",
            "data_request": {"symbol": "EUR_USD", "timeframe": "1H"},
        }
    )

    assert config.instrument is not None
    assert config.instrument["symbol"] == "EURUSD"
    assert config.instrument["timeframe"] == "1H"


def test_run_config_enforces_workspace_runs_dir(caplog) -> None:
    """Test that RunConfig overrides a user-provided runs_dir."""
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_override",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": "./some_other_dir",
            }
        )

    assert config.runs_dir.resolve() == paths.RUNS_DIR.resolve()
    assert "Ignoring configured `runs_dir`" in caplog.text
    assert "outside the project workspace" in caplog.text
    assert "some_other_dir" in caplog.text


def test_run_config_allows_custom_workspace_runs_dir(caplog) -> None:
    """Test RunConfig allows custom paths within workspace."""
    # Validates: Task 1 - Relaxed path validator

    # Test Case 1: Allow custom path within workspace
    custom_dir = paths.WORKSPACE_DIR / "custom_runs"
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_custom",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": str(custom_dir),
            }
        )

    # Should accept the custom directory within workspace
    assert config.runs_dir.resolve() == custom_dir.resolve()
    # Should not log a warning for valid workspace path
    assert "Ignoring configured `runs_dir`" not in caplog.text

    # Test Case 2: Reject path outside workspace
    caplog.clear()
    outside_dir = "/tmp/some_dir"
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_outside",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": outside_dir,
            }
        )

    # Should reject and fall back to default
    assert config.runs_dir.resolve() == paths.RUNS_DIR.resolve()
    # Should log a warning for path outside workspace
    assert "Ignoring configured `runs_dir`" in caplog.text
    assert "outside the project workspace" in caplog.text
    assert outside_dir in caplog.text


def test_feature_config_rejects_invalid_source() -> None:
    """Test that FeatureConfig rejects invalid source values."""
    with pytest.raises(ValidationError) as exc_info:
        FeatureConfig(
            name="test_feature",
            type="RSI",
            params={"length": 14},
            source="invalid_source",  # type: ignore[arg-type]
        )

    assert "source" in str(exc_info.value)


def test_feature_config_global_requires_timeframe_prefix() -> None:
    """Test that global FeatureConfig requires timeframe prefix in name."""
    with pytest.raises(ValidationError) as exc_info:
        FeatureConfig.model_validate(
            {
                "name": "rsi_14",  # Missing timeframe prefix
                "type": "RSI",
                "params": {"length": 14},
            },
            context={"is_global": True},
        )

    error_msg = str(exc_info.value)
    assert "timeframe prefix" in error_msg.lower()
    assert "rsi_14" in error_msg


def test_feature_config_global_accepts_valid_prefix() -> None:
    """Test that global FeatureConfig accepts valid timeframe-prefixed names."""
    valid_names = ["1min_rsi", "5min_ema", "15min_atr", "1h_rsi", "4h_ema", "1d_sma"]

    for name in valid_names:
        # Should not raise ValidationError
        config = FeatureConfig.model_validate(
            {
                "name": name,
                "type": "RSI",
                "params": {"length": 14},
            },
            context={"is_global": True},
        )
        assert config.name == name


def test_run_config_has_no_contextual_features_field() -> None:
    """Test that RunConfig does not have a contextual_features field."""
    with pytest.raises(ValidationError) as exc_info:
        RunConfig.model_validate(
            {
                "run_id": "test",
                "instrument": {"symbol": "EURUSD"},
                "contextual_features": [],
            }
        )

    error_msg = str(exc_info.value).lower()
    assert "extra" in error_msg and (
        "not permitted" in error_msg or "forbidden" in error_msg
    )


def test_global_feature_set_config_validates_names() -> None:
    """Test that GlobalFeatureSetConfig validates feature names."""
    # Valid: all features have timeframe prefix
    config = GlobalFeatureSetConfig.model_validate(
        {
            "features": [
                {"name": "1h_rsi_14", "type": "RSI", "params": {"length": 14}},
                {"name": "15min_ema_9", "type": "EMA", "params": {"length": 9}},
            ]
        }
    )
    assert len(config.features) == 2

    # Invalid: missing timeframe prefix
    with pytest.raises(ValidationError) as exc_info:
        GlobalFeatureSetConfig.model_validate(
            {
                "features": [
                    {"name": "rsi_14", "type": "RSI", "params": {"length": 14}},
                ]
            }
        )

    error_msg = str(exc_info.value)
    assert "timeframe prefix" in error_msg.lower()
