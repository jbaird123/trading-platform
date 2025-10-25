"""Tests for campaign review workflow."""

import json

import pytest
import yaml
from trading_platform.ai.campaigns.review import (
    approve_candidate,
    generate_review_report,
    get_approved_candidates,
    get_needs_rework_candidates,
    mark_needs_rework,
    reject_candidate,
)


@pytest.fixture
def sample_candidates():
    """Sample candidates with metrics."""
    return [
        {
            "run_id": f"run_{i:03d}",
            "total_pnl": 1000 + i * 100,
            "sharpe_ratio": 1.0 + i * 0.1,
            "win_rate": 0.5 + i * 0.01,
            "total_trades": 50 + i,
        }
        for i in range(5)
    ]


def test_generate_review_report_creates_markdown(tmp_path, sample_candidates):
    """Test that review report generates markdown."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Create index.json
    with open(candidates_dir / "index.json", "w") as f:
        json.dump(sample_candidates, f)

    # Generate report
    report_path = generate_review_report("test_campaign", data_root=tmp_path)

    # Verify
    assert report_path.exists()
    content = report_path.read_text()
    assert "Top Performers" in content
    assert "run_004" in content  # Highest sharpe


def test_approve_candidate_updates_campaign_decision_yaml(tmp_path):
    """Test approving a candidate."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Approve
    approve_candidate(
        campaign_id="test_campaign",
        run_id="run_001",
        notes="Good metrics",
        reviewer="tester",
        data_root=tmp_path,
    )

    # Load decision.yaml
    decision_path = candidates_dir / "decision.yaml"
    assert decision_path.exists()

    with open(decision_path) as f:
        decision = yaml.safe_load(f)

    assert decision["campaign_id"] == "test_campaign"
    assert decision["reviewed_by"] == "tester"
    assert "reviewed_at" in decision
    assert len(decision["decisions"]) == 1
    assert decision["decisions"][0]["run_id"] == "run_001"
    assert decision["decisions"][0]["status"] == "approved"
    assert decision["decisions"][0]["notes"] == "Good metrics"


def test_reject_candidate_appends_to_campaign_decision_yaml(tmp_path):
    """Test rejecting a candidate."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # First approve one
    approve_candidate(
        campaign_id="test_campaign",
        run_id="run_001",
        notes="Good",
        data_root=tmp_path,
    )

    # Then reject another
    reject_candidate(
        campaign_id="test_campaign",
        run_id="run_002",
        reason="High drawdown",
        data_root=tmp_path,
    )

    # Load decision.yaml
    with open(candidates_dir / "decision.yaml") as f:
        decision = yaml.safe_load(f)

    assert len(decision["decisions"]) == 2
    rejected = [d for d in decision["decisions"] if d["status"] == "rejected"][0]
    assert rejected["run_id"] == "run_002"
    assert rejected["reason"] == "High drawdown"


def test_needs_rework_candidate_appends_to_campaign_decision_yaml(tmp_path):
    """Test marking candidate as needs-rework."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Mark needs rework
    mark_needs_rework(
        campaign_id="test_campaign",
        run_id="run_003",
        reason="Adjust parameters",
        suggestions="Increase stop loss",
        data_root=tmp_path,
    )

    # Load decision.yaml
    with open(candidates_dir / "decision.yaml") as f:
        decision = yaml.safe_load(f)

    needs_rework = decision["decisions"][0]
    assert needs_rework["run_id"] == "run_003"
    assert needs_rework["status"] == "needs-rework"
    assert needs_rework["reason"] == "Adjust parameters"
    assert needs_rework["suggestions"] == "Increase stop loss"


def test_get_approved_candidates_filters_correctly(tmp_path):
    """Test getting approved candidates."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Create mixed decisions
    approve_candidate("test_campaign", "run_001", "Good", data_root=tmp_path)
    approve_candidate("test_campaign", "run_002", "Good", data_root=tmp_path)
    reject_candidate("test_campaign", "run_003", "Bad", data_root=tmp_path)

    # Get approved
    approved = get_approved_candidates("test_campaign", data_root=tmp_path)

    assert len(approved) == 2
    assert "run_001" in approved
    assert "run_002" in approved
    assert "run_003" not in approved


def test_get_needs_rework_candidates_filters_correctly(tmp_path):
    """Test getting needs-rework candidates."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Create mixed decisions
    approve_candidate("test_campaign", "run_001", "Good", data_root=tmp_path)
    mark_needs_rework(
        "test_campaign", "run_002", "Adjust", "Fix params", data_root=tmp_path
    )
    mark_needs_rework(
        "test_campaign", "run_003", "Review", "Check trades", data_root=tmp_path
    )

    # Get needs-rework
    needs_rework = get_needs_rework_candidates("test_campaign", data_root=tmp_path)

    assert len(needs_rework) == 2
    assert "run_002" in needs_rework
    assert "run_003" in needs_rework
    assert "run_001" not in needs_rework


def test_generate_review_report_handles_missing_index(tmp_path):
    """Test handling of missing index.json."""
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    # Should handle gracefully
    report_path = generate_review_report("test_campaign", data_root=tmp_path)
    assert report_path.exists()
    content = report_path.read_text()
    assert "No candidates" in content or "0 candidates" in content.lower()


def test_get_approved_candidates_handles_missing_decision(tmp_path):
    """Test getting approved when no decision.yaml exists."""
    approved = get_approved_candidates("test_campaign", data_root=tmp_path)
    assert approved == []


def test_generate_review_report_uses_cwd_default(
    tmp_path, sample_candidates, monkeypatch
):
    """Test that data_root defaults to cwd."""
    monkeypatch.chdir(tmp_path)

    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    with open(candidates_dir / "index.json", "w") as f:
        json.dump(sample_candidates, f)

    # Don't pass data_root
    report_path = generate_review_report("test_campaign")
    assert report_path.exists()


def test_approve_candidate_uses_cwd_default(tmp_path, monkeypatch):
    """Test that approve uses cwd as default."""
    monkeypatch.chdir(tmp_path)

    # Don't pass data_root
    approve_candidate("test_campaign", "run_001", "Good")

    decision_path = tmp_path / "data" / "candidates" / "test_campaign" / "decision.yaml"
    assert decision_path.exists()


def test_get_approved_candidates_uses_cwd_default(tmp_path, monkeypatch):
    """Test that get_approved uses cwd as default."""
    monkeypatch.chdir(tmp_path)

    approve_candidate("test_campaign", "run_001", "Good")
    approved = get_approved_candidates("test_campaign")
    assert "run_001" in approved
