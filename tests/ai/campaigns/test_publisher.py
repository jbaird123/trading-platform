"""Tests for campaign dataset publishing."""

import hashlib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from trading_platform.ai.campaigns.publisher import publish_campaign_dataset


@pytest.fixture
def enriched_dataset(tmp_path):
    """Create enriched dataset for testing."""
    enriched_dir = tmp_path / "data" / "enriched" / "test_campaign"
    enriched_dir.mkdir(parents=True)
    enriched_path = enriched_dir / "rich_trades.parquet"

    # Create enriched data
    df = pd.DataFrame(
        {
            "trade_id": [f"t{i}" for i in range(5)],
            "pnl": [100.0, -50.0, 75.0, -25.0, 150.0],
            "campaign_id": ["test_campaign"] * 5,
            "run_id": ["run_001"] * 5,
        }
    )
    df.to_parquet(enriched_path)

    return tmp_path


def test_publish_reads_from_enriched(enriched_dataset, monkeypatch):
    """Test that publisher reads from enriched folder."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = publish_campaign_dataset("test_campaign")

            # Verify it read from enriched folder
            assert result.campaign_id == "test_campaign"
            assert result.total_trades_published == 5


def test_publish_appends_to_master_log(enriched_dataset, monkeypatch):
    """Test that publishing appends to existing master trade log."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Create existing master log
        master_dir = enriched_dataset / "data" / "dvc" / "processed" / "training_sets"
        master_dir.mkdir(parents=True)
        master_log_path = master_dir / "master_trade_log.parquet"

        existing_df = pd.DataFrame(
            {
                "trade_id": [f"old_{i}" for i in range(10)],
                "pnl": [50.0] * 10,
                "campaign_id": ["old_campaign"] * 10,
                "run_id": ["old_run"] * 10,
            }
        )
        existing_df.to_parquet(master_log_path)

        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = publish_campaign_dataset("test_campaign")

            # Verify append
            assert result.master_log_updated
            final_df = pd.read_parquet(master_log_path)
            assert len(final_df) == 15  # 10 + 5


def test_publish_generates_checksum(enriched_dataset, monkeypatch):
    """Test that publishing generates valid SHA256 checksum."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = publish_campaign_dataset("test_campaign")

            # Verify checksum
            assert hasattr(result, "sha256_checksum")
            assert len(result.sha256_checksum) == 64
            assert all(c in "0123456789abcdef" for c in result.sha256_checksum)

            # Recalculate and verify
            master_path = (
                enriched_dataset
                / "data"
                / "dvc"
                / "processed"
                / "training_sets"
                / "master_trade_log.parquet"
            )
            with open(master_path, "rb") as f:
                actual_checksum = hashlib.sha256(f.read()).hexdigest()
            assert result.sha256_checksum == actual_checksum


def test_publish_updates_curation_history(enriched_dataset, monkeypatch):
    """Test that publishing updates curation history."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Create history file
            history_dir = enriched_dataset / "docs" / "ai"
            history_dir.mkdir(parents=True)
            history_file = history_dir / "data_curation_history.md"
            history_file.write_text("# Data Curation History\n\n")

            result = publish_campaign_dataset("test_campaign")

            # Verify history updated
            history_content = history_file.read_text()
            assert "test_campaign" in history_content
            assert result.sha256_checksum in history_content
            assert "campaign-runner" in history_content


def test_publish_updates_audit_log(enriched_dataset, monkeypatch):
    """Test that publishing updates audit log."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Create audit log file
            audit_dir = enriched_dataset / "docs" / "ai" / "logs"
            audit_dir.mkdir(parents=True)
            audit_file = audit_dir / "campaign_audit.md"
            audit_file.write_text("# Campaign Audit Log\n\n")

            publish_campaign_dataset("test_campaign")

            # Verify audit log updated
            audit_content = audit_file.read_text()
            assert "test_campaign" in audit_content
            assert "publish" in audit_content.lower()


def test_publish_executes_dvc_tracking(enriched_dataset, monkeypatch):
    """Test that publishing executes DVC tracking commands."""
    monkeypatch.chdir(enriched_dataset)

    # Mock paths.PROJECT_ROOT
    with patch(
        "trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT",
        enriched_dataset,
    ):
        # Mock subprocess for DVC commands
        with patch(
            "trading_platform.ai.campaigns.publisher.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = publish_campaign_dataset("test_campaign")

            # Verify DVC commands called
            assert mock_run.call_count >= 2
            calls = [call[0][0] for call in mock_run.call_args_list]

            # Check for dvc add
            dvc_add_call = None
            dvc_push_call = None
            for call in calls:
                if "dvc" in call and "add" in call:
                    dvc_add_call = call
                if "dvc" in call and "push" in call:
                    dvc_push_call = call

            assert dvc_add_call is not None
            assert dvc_push_call is not None
            assert result.dvc_tracking_updated


def test_publish_raises_error_for_missing_enriched(tmp_path):
    """Test that publishing raises error if enriched dataset doesn't exist."""
    # Mock paths.PROJECT_ROOT
    with patch("trading_platform.ai.campaigns.publisher.paths.PROJECT_ROOT", tmp_path):
        # Try to publish without creating enriched dataset
        with pytest.raises(FileNotFoundError, match="Enriched dataset not found"):
            publish_campaign_dataset("nonexistent_campaign")
