"""Tests for campaign enrichment stage."""

import json
from unittest.mock import patch

import pandas as pd
import pytest
from trading_platform.ai.campaigns.enrichment import enrich_campaign_dataset


@pytest.fixture
def approved_candidates(tmp_path):
    """Create approved candidates with decision.yaml and plan.json."""
    campaign_id = "test_campaign"

    # Create campaign plan with metadata
    campaign_dir = tmp_path / "data" / "campaigns" / campaign_id
    campaign_dir.mkdir(parents=True)

    plan_data = {
        "campaign_id": campaign_id,
        "strategy_path": "config/strategy/test.yaml",
        "strategy_archetype": "trend_following",
        "execution_timeframe": "15min",
        "runs": [],
        "contextual_features": [],
        "provenance": {
            "git_commit": "abc123",
            "poetry_lock_sha256": "deadbeef" + "0" * 56,
            "python_version": "3.13.8",
            "platform": "Darwin-25.0.0",
            "dvc_version": "3.63.0",
            "data_snapshot_id": "snapshot123",
            "captured_at": "2025-10-24T12:00:00Z",
        },
    }

    with open(campaign_dir / "plan.json", "w") as f:
        json.dump(plan_data, f)

    # Create candidates directory
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

    # Create candidate directories with brief.json (with trades)
    for run_id in ["run_001", "run_002", "run_003"]:
        run_dir = candidates_dir / run_id
        run_dir.mkdir()

        brief = {
            "meta": {
                "run_id": run_id,
            },
            "trades": [
                {
                    "symbol": "EURUSD",
                    "side": "long",
                    "entry_time": "2023-01-01T00:00:00Z",
                    "exit_time": "2023-01-01T01:00:00Z",
                    "pnl": 100.0,
                    "context_at_entry": {"rsi": 30.0},
                },
                {
                    "symbol": "EURUSD",
                    "side": "short",
                    "entry_time": "2023-01-01T02:00:00Z",
                    "exit_time": "2023-01-01T03:00:00Z",
                    "pnl": -50.0,
                    "context_at_entry": {"rsi": 70.0},
                },
            ],
            "overall_performance": {"total_pnl": 50.0},
        }

        with open(run_dir / "brief.json", "w") as f:
            json.dump(brief, f)

    return tmp_path


def test_enrich_approved_candidates_only(approved_candidates, monkeypatch):
    """Test that enrichment only processes approved candidates."""
    monkeypatch.chdir(approved_candidates)

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        result = enrich_campaign_dataset("test_campaign")

        # Verify only approved candidates processed (2 approved, not the 1 rejected)
        assert result.approved_candidates == 2
        # Each approved candidate has 2 trades = 4 total
        assert result.total_trades_enriched == 4


def test_enrichment_extracts_trades_directly(approved_candidates, monkeypatch):
    """Test that enrichment extracts trades directly without subprocess."""
    monkeypatch.chdir(approved_candidates)

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        result = enrich_campaign_dataset("test_campaign")

        # Load the created parquet file
        output_path = result.output_path
        df = pd.read_parquet(output_path)

        # Verify trades were extracted
        assert len(df) == 4  # 2 approved * 2 trades each
        assert "symbol" in df.columns
        assert "pnl" in df.columns
        assert "context_at_entry_rsi" in df.columns  # Flattened


def test_enrichment_adds_campaign_metadata(approved_candidates, monkeypatch):
    """Test that enrichment adds campaign metadata columns."""
    monkeypatch.chdir(approved_candidates)

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        result = enrich_campaign_dataset("test_campaign")

        # Load and verify metadata
        df = pd.read_parquet(result.output_path)

        # Verify metadata columns added
        assert "campaign_id" in df.columns
        assert "strategy_archetype" in df.columns
        assert "execution_timeframe" in df.columns
        assert "run_id" in df.columns

        # Verify metadata values
        assert all(df["campaign_id"] == "test_campaign")
        assert all(df["strategy_archetype"] == "trend_following")
        assert all(df["execution_timeframe"] == "15min")
        assert set(df["run_id"].unique()) == {"run_001", "run_002"}


def test_enrichment_returns_summary(approved_candidates, monkeypatch):
    """Test that enrichment returns EnrichmentResult summary."""
    monkeypatch.chdir(approved_candidates)

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
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

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        result = enrich_campaign_dataset("test_campaign")

        # Should still process run_001 even though run_002 brief missing
        assert result.approved_candidates == 2  # Still 2 approved
        assert result.total_trades_enriched == 2  # Only run_001's 2 trades


def test_enrichment_removes_redundant_columns(approved_candidates, monkeypatch):
    """Test that enrichment removes flattened redundant columns."""
    monkeypatch.chdir(approved_candidates)

    with patch(
        "trading_platform.ai.campaigns.enrichment.paths.PROJECT_ROOT",
        approved_candidates,
    ):
        result = enrich_campaign_dataset("test_campaign")

        df = pd.read_parquet(result.output_path)

        # Verify redundant columns removed
        assert "context_at_exit" not in df.columns
        assert "post_exit_analysis" not in df.columns

        # But flattened versions should exist (if present in data)
        # In this test, context_at_entry is flattened
        assert "context_at_entry_rsi" in df.columns
