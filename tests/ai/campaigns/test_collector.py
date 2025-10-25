"""Tests for campaign artifact collection."""

import json
from pathlib import Path

import pytest
from trading_platform.ai.campaigns.collector import collect_campaign_artifacts


@pytest.fixture
def sample_brief():
    """Sample brief.json data."""
    return {
        "meta": {
            "strategy_archetype": "trend_following",
            "execution_timeframe": "15m",
        },
        "backtest_metrics": {
            "total_pnl": 1000.0,
            "sharpe_ratio": 1.5,
            "win_rate": 0.6,
            "max_drawdown": -200.0,
        },
        "trades": [
            {"entry_time": "2024-01-01", "exit_time": "2024-01-02", "pnl": 100},
            {"entry_time": "2024-01-03", "exit_time": "2024-01-04", "pnl": -50},
        ],
    }


def test_collect_artifacts_uses_prescribed_structure(tmp_path, sample_brief):
    """Test that artifacts are collected to data/candidates/<campaign_id>/."""
    # Create fake run directory
    run_dir = tmp_path / "runs" / "campaigns" / "test_campaign" / "run_001"
    run_dir.mkdir(parents=True)

    # Write brief.json
    brief_path = run_dir / "brief.json"
    with open(brief_path, "w") as f:
        json.dump(sample_brief, f)

    # Collect artifacts
    summary = collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Check prescribed structure
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    assert candidates_dir.exists()
    assert (candidates_dir / "run_001" / "brief.json").exists()
    assert summary.total_candidates == 1
    assert summary.candidates_dir == Path("data/candidates/test_campaign")


def test_collect_artifacts_multiple_runs(tmp_path, sample_brief):
    """Test collecting artifacts from multiple runs."""
    # Create 3 run directories
    for i in range(3):
        run_dir = tmp_path / "runs" / "campaigns" / "test_campaign" / f"run_00{i}"
        run_dir.mkdir(parents=True)

        brief_path = run_dir / "brief.json"
        with open(brief_path, "w") as f:
            json.dump(sample_brief, f)

    # Collect artifacts
    summary = collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Verify all collected
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    assert summary.total_candidates == 3
    assert (candidates_dir / "run_000" / "brief.json").exists()
    assert (candidates_dir / "run_001" / "brief.json").exists()
    assert (candidates_dir / "run_002" / "brief.json").exists()


def test_collect_artifacts_extracts_metadata(tmp_path, sample_brief):
    """Test that metadata is extracted from brief and saved."""
    run_dir = tmp_path / "runs" / "campaigns" / "test_campaign" / "run_001"
    run_dir.mkdir(parents=True)

    brief_path = run_dir / "brief.json"
    with open(brief_path, "w") as f:
        json.dump(sample_brief, f)

    # Collect artifacts
    collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Check metadata.json exists
    metadata_path = (
        tmp_path / "data" / "candidates" / "test_campaign" / "run_001" / "metadata.json"
    )
    assert metadata_path.exists()

    # Load and verify metadata
    with open(metadata_path) as f:
        metadata = json.load(f)

    assert metadata["run_id"] == "run_001"
    assert metadata["strategy_archetype"] == "trend_following"
    assert metadata["execution_timeframe"] == "15m"
    assert metadata["total_pnl"] == 1000.0
    assert metadata["sharpe_ratio"] == 1.5
    assert metadata["win_rate"] == 0.6
    assert metadata["total_trades"] == 2
    assert metadata["max_drawdown"] == -200.0


def test_collect_artifacts_creates_index(tmp_path, sample_brief):
    """Test that index.json is created with all candidates."""
    # Create 2 runs with different metrics
    for i, pnl in enumerate([1000.0, 1500.0]):
        run_dir = tmp_path / "runs" / "campaigns" / "test_campaign" / f"run_00{i}"
        run_dir.mkdir(parents=True)

        brief = sample_brief.copy()
        brief["backtest_metrics"] = brief["backtest_metrics"].copy()
        brief["backtest_metrics"]["total_pnl"] = pnl

        with open(run_dir / "brief.json", "w") as f:
            json.dump(brief, f)

    # Collect artifacts
    collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Check index.json
    index_path = tmp_path / "data" / "candidates" / "test_campaign" / "index.json"
    assert index_path.exists()

    with open(index_path) as f:
        index = json.load(f)

    assert len(index) == 2
    assert index[0]["run_id"] == "run_000"
    assert index[0]["total_pnl"] == 1000.0
    assert index[1]["run_id"] == "run_001"
    assert index[1]["total_pnl"] == 1500.0


def test_collect_artifacts_skips_missing_brief(tmp_path, caplog, sample_brief):
    """Test that runs without brief.json are skipped with warning."""
    # Create one run with brief, one without
    run_dir_1 = tmp_path / "runs" / "campaigns" / "test_campaign" / "run_001"
    run_dir_1.mkdir(parents=True)
    with open(run_dir_1 / "brief.json", "w") as f:
        json.dump(sample_brief, f)

    # Run without brief
    run_dir_2 = tmp_path / "runs" / "campaigns" / "test_campaign" / "run_002"
    run_dir_2.mkdir(parents=True)

    # Collect artifacts
    summary = collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Should only collect 1
    assert summary.total_candidates == 1

    # Should have logged warning
    assert "run_002" in caplog.text
    assert "brief.json not found" in caplog.text.lower()


def test_collect_artifacts_handles_missing_campaign_dir(tmp_path, caplog):
    """Test handling of missing campaign runs directory."""
    # Don't create campaign directory at all
    summary = collect_campaign_artifacts(
        "nonexistent_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Should return empty summary
    assert summary.total_candidates == 0
    assert summary.campaign_id == "nonexistent_campaign"
    assert len(summary.candidates) == 0

    # Should have logged warning
    assert "not found" in caplog.text.lower()


def test_collect_artifacts_uses_cwd_as_default_data_root(
    tmp_path, sample_brief, monkeypatch
):
    """Test that data_root defaults to current directory."""
    # Change to tmp_path
    monkeypatch.chdir(tmp_path)

    # Create run directory
    run_dir = tmp_path / "runs" / "campaigns" / "test_campaign" / "run_001"
    run_dir.mkdir(parents=True)
    with open(run_dir / "brief.json", "w") as f:
        json.dump(sample_brief, f)

    # Collect without specifying data_root
    summary = collect_campaign_artifacts("test_campaign", runs_dir=tmp_path / "runs")

    # Should use current directory
    assert summary.total_candidates == 1
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    assert candidates_dir.exists()


def test_collect_artifacts_skips_non_directory_files(tmp_path, sample_brief):
    """Test that non-directory files in campaign dir are skipped."""
    campaign_dir = tmp_path / "runs" / "campaigns" / "test_campaign"
    campaign_dir.mkdir(parents=True)

    # Create a regular file (not a directory)
    (campaign_dir / "some_file.txt").write_text("not a run directory")

    # Create a proper run directory
    run_dir = campaign_dir / "run_001"
    run_dir.mkdir()
    with open(run_dir / "brief.json", "w") as f:
        json.dump(sample_brief, f)

    # Collect artifacts
    summary = collect_campaign_artifacts(
        "test_campaign", runs_dir=tmp_path / "runs", data_root=tmp_path
    )

    # Should only collect from actual directory
    assert summary.total_candidates == 1
