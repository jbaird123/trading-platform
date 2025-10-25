"""Tests for campaign candidate validation."""

import json

import pytest
from trading_platform.ai.campaigns.validator import validate_campaign_candidates


@pytest.fixture
def valid_brief():
    """Valid brief.json data."""
    return {
        "meta": {
            "strategy_archetype": "trend_following",
            "execution_timeframe": "15m",
        },
        "backtest_metrics": {
            "total_pnl": 1000.0,
            "sharpe_ratio": 1.5,
            "win_rate": 0.6,
            "max_drawdown": -0.2,  # 20% drawdown
        },
        "trades": [
            {"trade_id": "t1", "pnl": 100, "r_multiple": 2.0},
            {"trade_id": "t2", "pnl": -50, "r_multiple": -1.0},
            {"trade_id": "t3", "pnl": 150, "r_multiple": 3.0},
            {"trade_id": "t4", "pnl": 200, "r_multiple": 4.0},
            {"trade_id": "t5", "pnl": -100, "r_multiple": -2.0},
        ],
        "data_quality": {"has_nans": False, "duplicate_bars_count": 0},
    }


def test_validate_candidates_checks_schema(tmp_path, valid_brief):
    """Test that schema validation passes for valid brief."""
    # Create candidate directory
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(valid_brief, f)

    # Validate
    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.total_candidates == 1
    assert report.passed == 1
    assert report.failed == 0
    assert "schema_validation" in report.results[0].checks
    assert report.results[0].checks["schema_validation"].status == "passed"


def test_validate_candidates_detects_invalid_schema(tmp_path):
    """Test that invalid schema is detected."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Missing trades array
    invalid_brief = {
        "meta": {"strategy_archetype": "trend_following"},
        "backtest_metrics": {"total_pnl": 1000.0},
    }

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(invalid_brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.failed == 1
    assert report.results[0].checks["schema_validation"].status == "failed"
    msg = report.results[0].checks["schema_validation"].message
    assert msg is not None and "trades" in msg.lower()


def test_validate_candidates_checks_data_quality(tmp_path, valid_brief):
    """Test data quality validation."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Set has_nans flag
    brief = valid_brief.copy()
    brief["data_quality"] = {"has_nans": True, "duplicate_bars_count": 0}

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert "data_quality" in report.results[0].checks
    assert report.results[0].checks["data_quality"].status == "warning"
    msg = report.results[0].checks["data_quality"].message
    assert msg is not None and "nan" in msg.lower()


def test_validate_candidates_checks_min_trades(tmp_path, valid_brief):
    """Test minimum trades validation."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Only 2 trades
    brief = valid_brief.copy()
    brief["trades"] = [
        {"trade_id": "t1", "pnl": 100},
        {"trade_id": "t2", "pnl": -50},
    ]

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.results[0].checks["min_trades"].status == "failed"
    msg = report.results[0].checks["min_trades"].message
    assert msg is not None and "insufficient" in msg.lower()


def test_validate_candidates_detects_duplicate_trade_ids(tmp_path, valid_brief):
    """Test duplicate trade ID detection."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Duplicate trade IDs
    brief = valid_brief.copy()
    brief["trades"] = [
        {"trade_id": "t1", "pnl": 100},
        {"trade_id": "t1", "pnl": -50},  # Duplicate
        {"trade_id": "t2", "pnl": 150},
        {"trade_id": "t3", "pnl": 200},
        {"trade_id": "t4", "pnl": -100},
    ]

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.results[0].checks["duplicate_detection"].status == "failed"
    msg = report.results[0].checks["duplicate_detection"].message
    assert msg is not None and "duplicate" in msg.lower()


def test_validate_candidates_saves_report(tmp_path, valid_brief):
    """Test that validation report is saved."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(valid_brief, f)

    validate_campaign_candidates("test_campaign", data_root=tmp_path)

    report_path = (
        tmp_path / "data" / "candidates" / "test_campaign" / "validation_report.json"
    )
    assert report_path.exists()

    # Load and verify structure
    with open(report_path) as f:
        report_data = json.load(f)

    assert "campaign_id" in report_data
    assert "validated_at" in report_data
    assert "results" in report_data


def test_validate_candidates_handles_missing_brief(tmp_path, caplog):
    """Test handling of missing brief.json."""
    # Create candidate directory without brief
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.total_candidates == 0
    assert "no candidates found" in caplog.text.lower() or report.total_candidates == 0


def test_validate_candidates_checks_max_drawdown(tmp_path, valid_brief):
    """Test max drawdown validation."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Excessive drawdown
    brief = valid_brief.copy()
    brief["backtest_metrics"]["max_drawdown"] = -0.6  # 60% drawdown

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.results[0].checks["max_drawdown"].status == "failed"
    msg = report.results[0].checks["max_drawdown"].message
    assert msg is not None and "excessive" in msg.lower()


def test_validate_candidates_handles_missing_candidates_dir(tmp_path):
    """Test handling of missing candidates directory."""
    # Don't create the directory at all
    report = validate_campaign_candidates("nonexistent", data_root=tmp_path)

    assert report.total_candidates == 0
    assert report.passed == 0
    assert report.failed == 0


def test_validate_candidates_handles_empty_candidates_dir(tmp_path):
    """Test handling of empty candidates directory."""
    # Create directory but no subdirectories
    candidates_dir = tmp_path / "data" / "candidates" / "test_campaign"
    candidates_dir.mkdir(parents=True)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert report.total_candidates == 0


def test_validate_candidates_uses_cwd_as_default(tmp_path, valid_brief, monkeypatch):
    """Test that data_root defaults to current directory."""
    monkeypatch.chdir(tmp_path)

    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(valid_brief, f)

    report = validate_campaign_candidates("test_campaign")

    assert report.total_candidates == 1


def test_validate_candidates_checks_indicator_registry(tmp_path, valid_brief):
    """Test indicator registry validation."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Add contextual features with invalid indicator
    brief = valid_brief.copy()
    brief["meta"]["contextual_features"] = [
        {"name": "rsi_14", "type": "RSI", "params": {"length": 14}},
        {"name": "invalid_ind", "type": "INVALID_INDICATOR", "params": {}},
    ]

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert "indicator_registry" in report.results[0].checks
    assert report.results[0].checks["indicator_registry"].status == "failed"
    msg = report.results[0].checks["indicator_registry"].message
    assert msg is not None and "INVALID_INDICATOR" in msg


def test_validate_candidates_passes_valid_indicators(tmp_path, valid_brief):
    """Test that valid indicators pass registry check."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    # Add contextual features with valid indicators only
    brief = valid_brief.copy()
    brief["meta"]["contextual_features"] = [
        {"name": "rsi_14", "type": "RSI", "params": {"length": 14}},
        {"name": "ema_20", "type": "EMA", "params": {"length": 20}},
    ]

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert "indicator_registry" in report.results[0].checks
    assert report.results[0].checks["indicator_registry"].status == "passed"


def test_validate_candidates_computes_drift_stats(tmp_path, valid_brief):
    """Test drift monitoring with KS-statistic."""
    import pandas as pd

    # Create baseline master trade log
    master_log_dir = tmp_path / "data" / "dvc" / "processed" / "training_sets"
    master_log_dir.mkdir(parents=True)
    master_log_path = master_log_dir / "master_trade_log.parquet"

    # Create baseline with r_multiple mean=1.0, std=1.0
    baseline_df = pd.DataFrame(
        {"r_multiple": [i / 10.0 for i in range(-10, 11)]}  # -1.0 to 1.0
    )
    baseline_df.to_parquet(master_log_path)

    # Create candidate with significantly different distribution (mean=5.0)
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    brief = valid_brief.copy()
    brief["trades"] = [
        {"trade_id": f"t{i}", "pnl": 100, "r_multiple": 5.0 + (i / 10.0)}
        for i in range(10)
    ]

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert "drift_monitoring" in report.results[0].checks
    # Should detect drift with KS > 0.15
    assert report.results[0].checks["drift_monitoring"].status == "warning"
    msg = report.results[0].checks["drift_monitoring"].message
    assert msg is not None and "DRIFT DETECTED" in msg
    assert "KS=" in msg


def test_validate_candidates_no_drift_detected(tmp_path, valid_brief):
    """Test that similar distributions pass drift check."""
    import pandas as pd

    # Create baseline master trade log
    master_log_dir = tmp_path / "data" / "dvc" / "processed" / "training_sets"
    master_log_dir.mkdir(parents=True)
    master_log_path = master_log_dir / "master_trade_log.parquet"

    # Create baseline with r_multiple similar to valid_brief
    baseline_df = pd.DataFrame(
        {"r_multiple": [2.0, -1.0, 3.0, 4.0, -2.0] * 10}  # Same pattern repeated
    )
    baseline_df.to_parquet(master_log_path)

    # Create candidate with similar distribution
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(valid_brief, f)

    report = validate_campaign_candidates("test_campaign", data_root=tmp_path)

    assert "drift_monitoring" in report.results[0].checks
    # Should pass with KS < 0.15
    assert report.results[0].checks["drift_monitoring"].status == "passed"
    msg = report.results[0].checks["drift_monitoring"].message
    assert msg is not None and ("No drift" in msg or "KS=" in msg)


def test_validate_candidates_updates_audit_log(tmp_path, valid_brief):
    """Test that audit log is updated."""
    candidate_dir = tmp_path / "data" / "candidates" / "test_campaign" / "run_001"
    candidate_dir.mkdir(parents=True)

    with open(candidate_dir / "brief.json", "w") as f:
        json.dump(valid_brief, f)

    validate_campaign_candidates("test_campaign", data_root=tmp_path)

    audit_log_path = tmp_path / "docs" / "ai" / "logs" / "campaign_audit.md"
    assert audit_log_path.exists()

    # Read and verify audit log content
    with open(audit_log_path) as f:
        content = f.read()

    assert "Campaign Audit Log" in content
    assert "Action" in content
    assert "Validation" in content
    assert "test_campaign" in content
    assert "Total Candidates" in content
    assert "Passed" in content
