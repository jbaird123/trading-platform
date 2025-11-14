"""Tests for global feature resolver utility."""

import tempfile
from pathlib import Path

import pytest
import yaml
from trading_platform.core.feature_resolver import (
    ResolvedFeature,
    resolve_global_features,
)


def test_resolve_global_features_returns_resolved_features(tmp_path: Path) -> None:
    """Test that resolve_global_features returns ResolvedFeature objects."""
    global_yaml = tmp_path / "config" / "features" / "global.yaml"
    global_yaml.parent.mkdir(parents=True)

    global_yaml.write_text(
        yaml.dump(
            {
                "features": [
                    {
                        "name": "1h_rsi_14",
                        "type": "RSI",
                        "params": {"length": 14},
                        "timeframe": "1H",
                    },
                ]
            }
        )
    )

    # Temporarily change the working directory for this test
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        features = resolve_global_features("1min")
        assert len(features) == 1
        assert isinstance(features[0], ResolvedFeature)
        assert features[0].name == "1h_rsi_14"
    finally:
        os.chdir(original_cwd)


def test_resolve_global_features_missing_file() -> None:
    """Test that resolve_global_features raises FileNotFoundError if
    global.yaml missing.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            with pytest.raises(FileNotFoundError) as exc_info:
                resolve_global_features("1H")

            error_msg = str(exc_info.value).lower()
            assert "global feature configuration not found" in error_msg
        finally:
            os.chdir(original_cwd)


def test_resolve_global_features_includes_gte_timeframe(tmp_path: Path) -> None:
    """Test that features with timeframe >= execution_timeframe are included."""
    global_yaml = tmp_path / "config" / "features" / "global.yaml"
    global_yaml.parent.mkdir(parents=True)

    global_yaml.write_text(
        yaml.dump(
            {
                "features": [
                    {
                        "name": "15min_rsi",
                        "type": "RSI",
                        "params": {"length": 14},
                        "timeframe": "15min",
                    },
                    {
                        "name": "1h_ema",
                        "type": "EMA",
                        "params": {"length": 50},
                        "timeframe": "1H",
                    },
                    {
                        "name": "1d_atr",
                        "type": "ATR",
                        "params": {"length": 14},
                        "timeframe": "1D",
                    },
                ]
            }
        )
    )

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Execution timeframe is 1min - should include all higher timeframes
        features = resolve_global_features("1min")
        assert len(features) == 3
        names = [f.name for f in features]
        assert "15min_rsi" in names
        assert "1h_ema" in names
        assert "1d_atr" in names
    finally:
        os.chdir(original_cwd)


def test_resolve_global_features_filters_lt_timeframe(tmp_path: Path) -> None:
    """Test that features with timeframe < execution_timeframe are excluded."""
    global_yaml = tmp_path / "config" / "features" / "global.yaml"
    global_yaml.parent.mkdir(parents=True)

    global_yaml.write_text(
        yaml.dump(
            {
                "features": [
                    {
                        "name": "5min_rsi",
                        "type": "RSI",
                        "params": {"length": 14},
                        "timeframe": "5min",
                    },
                    {
                        "name": "15min_ema",
                        "type": "EMA",
                        "params": {"length": 50},
                        "timeframe": "15min",
                    },
                    {
                        "name": "1h_atr",
                        "type": "ATR",
                        "params": {"length": 14},
                        "timeframe": "1H",
                    },
                ]
            }
        )
    )

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Execution timeframe is 1H - should exclude m5 and m15
        features = resolve_global_features("1H")
        assert len(features) == 1
        assert features[0].name == "1h_atr"
    finally:
        os.chdir(original_cwd)


def test_resolve_global_features_includes_no_timeframe(tmp_path: Path) -> None:
    """Test that features without timeframe are included."""
    global_yaml = tmp_path / "config" / "features" / "global.yaml"
    global_yaml.parent.mkdir(parents=True)

    global_yaml.write_text(
        yaml.dump(
            {
                "features": [
                    {
                        "name": "1h_rsi",
                        "type": "RSI",
                        "params": {"length": 14},
                    },  # No timeframe
                    {
                        "name": "1d_ema",
                        "type": "EMA",
                        "params": {"length": 50},
                        "timeframe": "1D",
                    },
                ]
            }
        )
    )

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        features = resolve_global_features("1H")
        assert len(features) == 2
        names = [f.name for f in features]
        assert "1h_rsi" in names
        assert "1d_ema" in names
    finally:
        os.chdir(original_cwd)
