"""Tests for CampaignPlanner."""

from pathlib import Path
from unittest.mock import patch

import pytest
from trading_platform.ai.campaigns.models import CampaignConfig, RunMatrixEntry
from trading_platform.ai.campaigns.planner import CampaignPlanner
from trading_platform.core.config import FeatureConfig


@pytest.fixture
def sample_campaign_config():
    """Sample campaign configuration."""
    return CampaignConfig(
        campaign_id="test_campaign_001",
        strategy_path=Path("config/strategy/example.yaml"),
        execution_timeframe="1h",
        strategy_archetype="trend_following",
        run_matrix=[
            RunMatrixEntry(
                instrument="EURUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                param_overrides={"stop_pips": 20, "tp_pips": 40},
            ),
            RunMatrixEntry(
                instrument="GBPUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                param_overrides=None,
            ),
        ],
        contextual_features=[
            FeatureConfig(
                name="atr_daily",
                type="ATR",
                timeframe="1d",
                params={"period": 14},
            )
        ],
    )


@pytest.fixture
def mock_provenance():
    """Mock provenance object."""
    from trading_platform.ai.campaigns.models import Provenance

    return Provenance(
        git_commit="abc123",
        poetry_lock_sha256="deadbeef" + "0" * 56,
        python_version="3.13.8",
        platform="Darwin-25.0.0",
        dvc_version="3.63.0",
        data_snapshot_id="snapshot123",
        captured_at="2025-10-24T12:00:00Z",
    )


def test_generate_plan_returns_campaign_plan(sample_campaign_config, mock_provenance):
    """Test that generate_plan() returns CampaignPlan object."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        assert plan.campaign_id == "test_campaign_001"
        assert plan.provenance == mock_provenance
        assert len(plan.runs) == 2  # Two entries in run matrix


def test_generate_plan_expands_run_matrix(sample_campaign_config, mock_provenance):
    """Test that generate_plan() expands run matrix into SingleRun objects."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        # First run
        run1 = plan.runs[0]
        assert run1.run_id.startswith("test_campaign_001_")
        assert run1.instrument == "EURUSD"
        assert run1.start_date == "2024-01-01"
        assert run1.end_date == "2024-12-31"
        assert run1.param_overrides == {"stop_pips": 20, "tp_pips": 40}

        # Second run
        run2 = plan.runs[1]
        assert run2.run_id.startswith("test_campaign_001_")
        assert run2.instrument == "GBPUSD"
        assert run2.start_date == "2024-01-01"
        assert run2.end_date == "2024-12-31"
        assert run2.param_overrides is None


def test_generate_plan_creates_unique_run_ids(sample_campaign_config, mock_provenance):
    """Test that each run gets a unique run_id."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        run_ids = [run.run_id for run in plan.runs]
        assert len(run_ids) == len(set(run_ids))  # All unique


def test_generate_plan_includes_strategy_config(
    sample_campaign_config, mock_provenance
):
    """Test that generate_plan() includes strategy configuration."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        assert plan.strategy_path == Path("config/strategy/example.yaml")
        assert plan.execution_timeframe == "1h"
        assert plan.strategy_archetype == "trend_following"


def test_generate_plan_includes_contextual_features(
    sample_campaign_config, mock_provenance
):
    """Test that generate_plan() includes contextual features."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        assert len(plan.contextual_features) == 1
        assert plan.contextual_features[0].name == "atr_daily"
        assert plan.contextual_features[0].timeframe == "1d"


def test_generate_plan_creates_output_paths(sample_campaign_config, mock_provenance):
    """Test that generate_plan() creates output paths for each run."""
    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(sample_campaign_config)

        for run in plan.runs:
            # Each run should have output_path defined
            assert run.output_path is not None
            # Should be under campaign_id directory
            assert str(run.output_path).startswith("test_campaign_001/")


def test_generate_plan_handles_empty_run_matrix(mock_provenance):
    """Test that generate_plan() handles empty run matrix."""
    config = CampaignConfig(
        campaign_id="empty_campaign",
        strategy_path=Path("config/strategy/example.yaml"),
        execution_timeframe="1h",
        strategy_archetype="trend_following",
        run_matrix=[],  # Empty
    )

    with patch(
        "trading_platform.ai.campaigns.planner.ProvenanceCollector"
    ) as mock_collector:
        mock_collector.return_value.capture.return_value = mock_provenance

        planner = CampaignPlanner()
        plan = planner.generate_plan(config)

        assert plan.campaign_id == "empty_campaign"
        assert len(plan.runs) == 0
