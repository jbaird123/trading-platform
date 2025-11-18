"""Tests for campaign configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from trading_platform.ai.campaigns.models import (
    CampaignConfig,
    Provenance,
    RunMatrixEntry,
)


def test_campaign_config_validates_required_fields():
    """Test that CampaignConfig validates with all required fields."""
    campaign_dict = {
        "campaign_id": "test_campaign",
        "strategy_path": "config/strategy/example.yaml",
        "execution_timeframe": "15m",
        "run_matrix": [],
        "strategy_archetype": "trend_following",
    }

    config = CampaignConfig.model_validate(campaign_dict)

    assert config.campaign_id == "test_campaign"
    assert config.strategy_path == Path("config/strategy/example.yaml")
    assert config.execution_timeframe == "15m"
    assert config.run_matrix == []
    assert config.strategy_archetype == "trend_following"


def test_campaign_config_rejects_missing_fields():
    """Test that CampaignConfig rejects missing required fields."""
    campaign_dict = {
        "campaign_id": "test_campaign",
        "strategy_path": "config/strategy/example.yaml",
        "execution_timeframe": "15m",
        "run_matrix": [],
        # Missing strategy_archetype
    }

    with pytest.raises(ValidationError) as exc_info:
        CampaignConfig.model_validate(campaign_dict)

    assert "strategy_archetype" in str(exc_info.value)
    assert "required" in str(exc_info.value).lower()


def test_run_matrix_entry_validates_dates():
    """Test that RunMatrixEntry validates with correct fields."""
    entry_dict = {
        "instrument": "EURUSD",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }

    entry = RunMatrixEntry.model_validate(entry_dict)

    assert entry.instrument == "EURUSD"
    assert entry.start_date == "2023-01-01"
    assert entry.end_date == "2023-12-31"
    assert entry.param_overrides is None


def test_run_matrix_entry_accepts_param_overrides():
    """Test that RunMatrixEntry accepts parameter overrides."""
    entry_dict = {
        "instrument": "EURUSD",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "param_overrides": {"fast_length": 10, "slow_length": 20},
    }

    entry = RunMatrixEntry.model_validate(entry_dict)

    assert entry.param_overrides == {"fast_length": 10, "slow_length": 20}


def test_campaign_config_accepts_contextual_features():
    """Test that CampaignConfig accepts contextual features."""
    campaign_dict = {
        "campaign_id": "test_campaign",
        "strategy_path": "config/strategy/example.yaml",
        "execution_timeframe": "15m",
        "strategy_archetype": "trend_following",
        "run_matrix": [],
        "contextual_features": [
            {
                "name": "1h_rsi",
                "type": "RSI",
                "params": {"length": 14},
                "timeframe": "1h",
            }
        ],
    }

    config = CampaignConfig.model_validate(campaign_dict)

    assert len(config.contextual_features) == 1
    assert config.contextual_features[0].name == "1h_rsi"
    assert config.contextual_features[0].timeframe == "1h"


def test_provenance_captures_all_metadata():
    """Test that Provenance model captures all required metadata."""
    prov_dict = {
        "git_commit": "abc1234",
        "poetry_lock_sha256": "deadbeef" + "0" * 56,  # 64 chars
        "python_version": "3.12.0",
        "platform": "darwin",
        "dvc_version": "3.63.0",
        "data_snapshot_id": "a1b2c3d4e5f6",
        "captured_at": "2025-10-24T12:00:00Z",
    }

    prov = Provenance.model_validate(prov_dict)

    assert prov.git_commit == "abc1234"
    assert len(prov.poetry_lock_sha256) == 64
    assert prov.python_version == "3.12.0"
    assert prov.platform == "darwin"
    assert prov.dvc_version == "3.63.0"
    assert prov.data_snapshot_id == "a1b2c3d4e5f6"
    assert prov.captured_at == "2025-10-24T12:00:00Z"
