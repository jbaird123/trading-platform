"""Tests for campaign enrichment stage."""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from trading_platform.ai.campaigns.enrichment import enrich_campaign_dataset


@pytest.fixture
def approved_candidates(tmp_path):
    """Create approved candidates with decision.yaml."""
    campaign_id = "test_campaign"
    candidates_dir = tmp_path / "data" / "candidates" / campaign_id
    candidates_dir.mkdir(parents=True)

    # Create decision.yaml with 2 approved, 1 rejected
    decision_data = {
        "campaign_id": campaign_id,
        "reviewed_by": "test_user",
        "reviewed_at": "2025-01-01T00:00:00Z",
        "decisions": [
            {"run_id": "run_001", "status": "approved", "notes": "Good"},
            {"run_id": "run_002", "status": "approved", "notes": "Good"},
            {"run_id": "run_003", "status": "rejected", "reason": "Bad"},
        ],
    }

    import yaml

    with open(candidates_dir / "decision.yaml", "w") as f:
        yaml.dump(decision_data, f)

    # Create candidate directories with brief.json
    for run_id in ["run_001", "run_002", "run_003"]:
        run_dir = candidates_dir / run_id
        run_dir.mkdir()

        brief = {
            "meta": {
                "run_id": run_id,
                "strategy_archetype": "trend_following",
                "execution_timeframe": "15m",
            },
            "trades": [
                {"trade_id": f"{run_id}_t1", "pnl": 100.0},
                {"trade_id": f"{run_id}_t2", "pnl": -50.0},
            ],
            "backtest_metrics": {"total_pnl": 50.0},
        }

        with open(run_dir / "brief.json", "w") as f:
            json.dump(brief, f)

    return tmp_path


def test_enrich_approved_candidates_only(approved_candidates, monkeypatch):
    """Test that enrichment only processes approved candidates."""
    monkeypatch.chdir(approved_candidates)

    # Mock subprocess.run for ai-curate-data
    with patch("trading_platform.ai.campaigns.enrichment.subprocess.run") as mock_run:
        # Mock successful execution
        mock_run.return_value = MagicMock(returncode=0)

        # Mock the parquet file creation
        output_path = (
            approved_candidates
            / "data"
            / "enriched"
            / "test_campaign"
            / "rich_trades.parquet"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create mock enriched data
        mock_df = pd.DataFrame(
            {
                "trade_id": ["run_001_t1", "run_001_t2", "run_002_t1", "run_002_t2"],
                "pnl": [100.0, -50.0, 100.0, -50.0],
            }
        )

        with patch(
            "trading_platform.ai.campaigns.enrichment.pd.read_parquet",
            return_value=mock_df,
        ):
            with patch.object(pd.DataFrame, "to_parquet"):
                result = enrich_campaign_dataset("test_campaign")

                # Verify only approved candidates processed
                assert result.approved_candidates == 2
                assert result.total_trades_enriched == 4


def test_enrich_uses_ai_curate_data(approved_candidates, monkeypatch):
    """Test that enrichment calls ai-curate-data subprocess."""
    monkeypatch.chdir(approved_candidates)

    with patch("trading_platform.ai.campaigns.enrichment.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        # Mock parquet operations
        mock_df = pd.DataFrame({"trade_id": ["run_001_t1"], "pnl": [100.0]})
        with patch(
            "trading_platform.ai.campaigns.enrichment.pd.read_parquet",
            return_value=mock_df,
        ):
            with patch.object(pd.DataFrame, "to_parquet"):
                enrich_campaign_dataset("test_campaign")

                # Verify subprocess called with correct arguments
                assert mock_run.called
                call_args = mock_run.call_args[0][0]
                assert call_args[0:3] == ["poetry", "run", "tp"]
                assert "ai-curate-data" in call_args
                assert "--source-dir" in call_args
                assert "--output-file" in call_args


def test_enrichment_adds_campaign_metadata(approved_candidates, monkeypatch):
    """Test that enrichment adds campaign metadata columns."""
    monkeypatch.chdir(approved_candidates)

    with patch("trading_platform.ai.campaigns.enrichment.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        # Create mock enriched data
        mock_df = pd.DataFrame(
            {"trade_id": ["run_001_t1", "run_002_t1"], "pnl": [100.0, 100.0]}
        )

        captured_df = None

        def capture_to_parquet(path, **kwargs):
            nonlocal captured_df
            captured_df = mock_df.copy()

        with patch(
            "trading_platform.ai.campaigns.enrichment.pd.read_parquet",
            return_value=mock_df,
        ):
            with patch.object(
                pd.DataFrame, "to_parquet", side_effect=capture_to_parquet
            ):
                enrich_campaign_dataset("test_campaign")

                # Verify metadata columns added
                assert "campaign_id" in mock_df.columns
                assert "strategy_archetype" in mock_df.columns
                assert "execution_timeframe" in mock_df.columns
                assert "run_id" in mock_df.columns


def test_enrichment_returns_summary(approved_candidates, monkeypatch):
    """Test that enrichment returns EnrichmentResult summary."""
    monkeypatch.chdir(approved_candidates)

    with patch("trading_platform.ai.campaigns.enrichment.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        mock_df = pd.DataFrame(
            {
                "trade_id": ["run_001_t1", "run_001_t2", "run_002_t1", "run_002_t2"],
                "pnl": [100.0, -50.0, 100.0, -50.0],
            }
        )

        with patch(
            "trading_platform.ai.campaigns.enrichment.pd.read_parquet",
            return_value=mock_df,
        ):
            with patch.object(pd.DataFrame, "to_parquet"):
                result = enrich_campaign_dataset("test_campaign")

                # Verify summary fields
                assert result.campaign_id == "test_campaign"
                assert result.approved_candidates == 2
                assert result.total_trades_enriched == 4
                assert "rich_trades.parquet" in str(result.output_path)
                assert result.enriched_at  # ISO timestamp


def test_enrichment_handles_missing_briefs(approved_candidates, monkeypatch):
    """Test enrichment handles candidates with missing brief files."""
    monkeypatch.chdir(approved_candidates)

    # Remove one brief to test missing file handling
    import os

    brief_path = (
        approved_candidates
        / "data"
        / "candidates"
        / "test_campaign"
        / "run_002"
        / "brief.json"
    )
    os.remove(brief_path)

    with patch("trading_platform.ai.campaigns.enrichment.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        # Mock data for only run_001 since run_002 brief is missing
        mock_df = pd.DataFrame(
            {"trade_id": ["run_001_t1", "run_001_t2"], "pnl": [100.0, -50.0]}
        )

        with patch(
            "trading_platform.ai.campaigns.enrichment.pd.read_parquet",
            return_value=mock_df,
        ):
            with patch.object(pd.DataFrame, "to_parquet"):
                result = enrich_campaign_dataset("test_campaign")

                # Should still process run_001 even though run_002 brief missing
                assert result.approved_candidates == 2  # Still 2 approved
                assert result.total_trades_enriched == 2


def test_enrichment_file_operations(approved_candidates, monkeypatch):
    """Test actual file operations in enrichment without mocking."""
    monkeypatch.chdir(approved_candidates)

    # Mock paths.PROJECT_ROOT to use temp directory
    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        # Mock only subprocess to prevent actual ai-curate-data execution
        with patch(
            "trading_platform.ai.campaigns.enrichment.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Create a real parquet file for the test
            output_dir = approved_candidates / "data" / "enriched" / "test_campaign"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "rich_trades.parquet"

            # Create real parquet data
            real_df = pd.DataFrame(
                {
                    "trade_id": [
                        "run_001_t1",
                        "run_001_t2",
                        "run_002_t1",
                        "run_002_t2",
                    ],
                    "pnl": [100.0, -50.0, 100.0, -50.0],
                }
            )
            real_df.to_parquet(output_path)

            # Run enrichment - this should execute file operations
            result = enrich_campaign_dataset("test_campaign")

            # Verify result
            assert result.approved_candidates == 2
            assert result.total_trades_enriched == 4

            # Verify metadata columns were added
            final_df = pd.read_parquet(output_path)
            assert "campaign_id" in final_df.columns
            assert "run_id" in final_df.columns
            assert "strategy_archetype" in final_df.columns
            assert "execution_timeframe" in final_df.columns
