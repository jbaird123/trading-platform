"""Tests for campaign batch execution engine."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from trading_platform.ai.campaigns.models import (
    CampaignPlan,
    Provenance,
    SingleRun,
)
from trading_platform.ai.campaigns.runner import execute_campaign_runs


@pytest.fixture
def sample_provenance():
    """Sample provenance metadata."""
    return Provenance(
        git_commit="abc123",
        poetry_lock_sha256="deadbeef" + "0" * 56,
        python_version="3.13.8",
        platform="Darwin-25.0.0",
        dvc_version="3.63.0",
        data_snapshot_id="snapshot123",
        captured_at="2025-10-24T12:00:00Z",
    )


@pytest.fixture
def single_run_plan(sample_provenance, tmp_path):
    """Campaign plan with a single run."""
    # Create the strategy file that the runner will load
    strategy_path = tmp_path / "strategy.yaml"
    strategy_data = {
        "strategy_name": "TestStrategy",
        "parameters": {"param1": 10},
        "features": [],
        "long_entry_rules": [],
        "long_exit_rules": [],
    }
    with open(strategy_path, "w") as f:
        yaml.dump(strategy_data, f)

    return CampaignPlan(
        campaign_id="test_campaign_001",
        strategy_path=strategy_path,
        execution_timeframe="1h",
        strategy_archetype="trend_following",
        runs=[
            SingleRun(
                run_id="test_campaign_001_0000_EURUSD",
                instrument="EURUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                param_overrides=None,
                output_path=Path("test_campaign_001/test_campaign_001_0000_EURUSD"),
            )
        ],
        contextual_features=[],
        provenance=sample_provenance,
    )


@pytest.fixture
def multi_run_plan(sample_provenance, tmp_path):
    """Campaign plan with three runs."""
    # Create the strategy file that the runner will load
    strategy_path = tmp_path / "strategy.yaml"
    strategy_data = {
        "strategy_name": "TestStrategy",
        "parameters": {"param1": 10},
        "features": [],
        "long_entry_rules": [],
        "long_exit_rules": [],
    }
    with open(strategy_path, "w") as f:
        yaml.dump(strategy_data, f)

    return CampaignPlan(
        campaign_id="test_campaign_002",
        strategy_path=strategy_path,
        execution_timeframe="1h",
        strategy_archetype="trend_following",
        runs=[
            SingleRun(
                run_id=f"test_campaign_002_{i:04d}_EURUSD",
                instrument="EURUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                param_overrides=None,
                output_path=Path(f"test_campaign_002/test_campaign_002_{i:04d}_EURUSD"),
            )
            for i in range(3)
        ],
        contextual_features=[],
        provenance=sample_provenance,
    )


def test_execute_campaign_single_run(single_run_plan, tmp_path):
    """Test executing campaign with single run."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        # Mock successful execution
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Success", stderr="", args=[]
        )

        results = execute_campaign_runs(
            single_run_plan, runs_dir=runs_dir, campaign_dir=campaign_dir
        )

        assert results.total_runs == 1
        assert results.successful == 1
        assert results.failed == 0
        assert results.campaign_id == "test_campaign_001"


def test_execute_campaign_multiple_runs(multi_run_plan, tmp_path):
    """Test executing campaign with multiple runs sequentially."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        # Mock successful execution for all runs
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Success", stderr="", args=[]
        )

        results = execute_campaign_runs(
            multi_run_plan, runs_dir=runs_dir, campaign_dir=campaign_dir
        )

        assert results.successful == 3
        assert results.failed == 0
        assert mock_run.call_count == 3


def test_execute_campaign_fails_fast_on_error(multi_run_plan, tmp_path):
    """Test execution stops on first failure with fail_fast=True."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        with patch("platform.platform", return_value="Darwin-25.0.0"):
            # First run succeeds, second fails
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
                MagicMock(returncode=1, stdout="", stderr="Error occurred", args=[]),
            ]

            results = execute_campaign_runs(
                multi_run_plan,
                runs_dir=runs_dir,
                campaign_dir=campaign_dir,
                fail_fast=True,
            )

            # Should stop after 2 runs (1 success, 1 failure)
            assert results.successful == 1
            assert results.failed == 1
            assert mock_run.call_count == 2


def test_execute_campaign_continues_on_error(multi_run_plan, tmp_path):
    """Test execution continues on failure with continue_on_error=True."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        with patch("platform.platform", return_value="Darwin-25.0.0"):
            # First succeeds, second fails, third succeeds
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
                MagicMock(returncode=1, stdout="", stderr="Error", args=[]),
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
            ]

            results = execute_campaign_runs(
                multi_run_plan,
                runs_dir=runs_dir,
                campaign_dir=campaign_dir,
                continue_on_error=True,
            )

            # All 3 runs attempted
            assert results.successful == 2
            assert results.failed == 1
            assert mock_run.call_count == 3


def test_execute_campaign_writes_execution_log(single_run_plan, tmp_path):
    """Test that execution log file is created."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Success", stderr="", args=[]
        )

        execute_campaign_runs(
            single_run_plan, runs_dir=runs_dir, campaign_dir=campaign_dir
        )

        log_file = campaign_dir / "execution.log"
        assert log_file.exists()

        # Log should contain run_id
        log_content = log_file.read_text()
        assert "test_campaign_001_0000_EURUSD" in log_content


def test_execute_campaign_creates_failure_reports(single_run_plan, tmp_path):
    """Test that failure reports are created for failed runs."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        with patch("platform.platform", return_value="Darwin-25.0.0"):
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="Partial output",
                stderr="Traceback: Error occurred",
                args=[],
            )

            results = execute_campaign_runs(
                single_run_plan,
                runs_dir=runs_dir,
                campaign_dir=campaign_dir,
                continue_on_error=True,
            )

            assert results.failed == 1

            # Check failure report exists
            failure_report = (
                campaign_dir
                / "failures"
                / "test_campaign_001_0000_EURUSD_failure_report.json"
            )
            assert failure_report.exists()

            # Verify report contents
            with open(failure_report) as f:
                report = json.load(f)

            assert report["run_id"] == "test_campaign_001_0000_EURUSD"
            assert report["exit_code"] == 1
            assert "Traceback" in report["stderr"]
            assert "failed_at" in report
            assert "config_snapshot" in report
            assert "environment" in report


def test_execute_campaign_raises_on_error_without_flags(multi_run_plan, tmp_path):
    """Test that execution raises RuntimeError when both flags are False."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        with patch("platform.platform", return_value="Darwin-25.0.0"):
            # First succeeds, second fails
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
                MagicMock(returncode=1, stdout="", stderr="Error", args=[]),
            ]

            with pytest.raises(RuntimeError, match="failed with exit code"):
                execute_campaign_runs(
                    multi_run_plan,
                    runs_dir=runs_dir,
                    campaign_dir=campaign_dir,
                    fail_fast=False,
                    continue_on_error=False,
                )


def test_execute_campaign_creates_completion_summary(multi_run_plan, tmp_path):
    """Test that campaign completion summary is created."""
    runs_dir = tmp_path / "runs"
    campaign_dir = tmp_path / "campaign"

    with patch("subprocess.run") as mock_run:
        with patch("platform.platform", return_value="Darwin-25.0.0"):
            # Mix of success and failure
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
                MagicMock(returncode=1, stdout="", stderr="Error", args=[]),
                MagicMock(returncode=0, stdout="Success", stderr="", args=[]),
            ]

            execute_campaign_runs(
                multi_run_plan,
                runs_dir=runs_dir,
                campaign_dir=campaign_dir,
                continue_on_error=True,
            )

            # Check completion summary exists
            summary_file = campaign_dir / "campaign_complete.yaml"
            assert summary_file.exists()

            # Verify summary contents
            with open(summary_file) as f:
                summary = yaml.safe_load(f)

            assert summary["campaign_id"] == "test_campaign_002"
            assert summary["total_runs"] == 3
            assert summary["successful"] == 2
            assert summary["failed"] == 1
            assert "total_runtime_seconds" in summary
            assert "completed_at" in summary
