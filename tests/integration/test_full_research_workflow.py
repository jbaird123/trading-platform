from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_phase0_data_validation_workflow(tmp_path: Path) -> None:
    """Test Phase 0: Data validation workflow."""
    from trading_platform.data.integrity_validator import validate_all_data

    # Create test data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create sample data files
    for instrument in ["EURUSD", "GBPUSD"]:
        file_path = data_dir / f"{instrument}_1H.parquet"
        dates = pd.date_range("2020-01-01", periods=1000, freq="h")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [1.1] * len(dates),
                "high": [1.2] * len(dates),
                "low": [1.0] * len(dates),
                "close": [1.15] * len(dates),
                "volume": [1000] * len(dates),
            }
        )
        df.to_parquet(file_path)

    # Phase 0: Validate data
    results = validate_all_data(data_dir, ["EURUSD", "GBPUSD"])

    # Assert validation succeeds
    assert results["total_files"] == 2
    assert results["total_issues"] == 0


def test_phase1_meta_campaign_generation_workflow(tmp_path: Path) -> None:
    """Test Phase 1: Meta-campaign generation workflow."""
    from trading_platform.core.meta_campaign_config import MetaCampaignConfig
    from trading_platform.core.meta_campaign_generator import (
        calculate_cartesian_product,
    )

    # Create minimal meta-campaign config
    config_file = tmp_path / "meta_campaign.yaml"
    config_yaml = """
meta_campaign_id: test_campaign
description: Test campaign

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 1H

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategies/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast: 10, slow: 20 }
"""
    config_file.write_text(config_yaml)

    # Load config
    config = MetaCampaignConfig.from_yaml(config_file)

    # Generate campaigns
    campaigns = calculate_cartesian_product(config)

    # Should generate 1 campaign (1 date × 1 instrument × 1 timeframe × 1 param set)
    assert len(campaigns) == 1
    assert campaigns[0]["instrument"] == "EURUSD"
    assert campaigns[0]["execution_timeframe"] == "1H"


def test_walk_forward_validation_workflow(tmp_path: Path) -> None:
    """Test Phase 5: Walk-forward validation workflow."""
    from trading_platform.validation.walk_forward import (
        check_performance_consistency,
        split_into_periods,
        walk_forward_validate,
    )

    # Create test data for 3 years
    dates = pd.date_range("2019-01-01", "2021-12-31", freq="D")
    data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [1.1] * len(dates),
            "close": [1.15] * len(dates),
        }
    )

    # Split into periods
    periods = split_into_periods(data, period="year")
    assert len(periods) == 3

    # Mock functions
    def mock_train(training_data: pd.DataFrame) -> dict:
        return {"model": "trained"}

    def mock_backtest(config: dict, test_data: pd.DataFrame) -> dict:
        return {"sharpe_ratio": 1.5, "max_drawdown": -0.15}

    # Run walk-forward validation
    results = walk_forward_validate(
        data=data,
        strategy_config={"strategy": "test"},
        periods=periods,
        train_model_fn=mock_train,
        run_backtest_fn=mock_backtest,
    )

    # Should have 2 test periods
    assert len(results) == 2

    # Check consistency
    assert check_performance_consistency(results, metric="sharpe_ratio")


def test_pre_deployment_checklist_workflow(tmp_path: Path) -> None:
    """Test pre-deployment checklist workflow."""
    from trading_platform.validation.pre_deployment import run_pre_deployment_checklist

    # Create mock artifacts
    model_metrics = {
        "profitability_r2": 0.3,
        "diagnostic_f1": 0.7,
    }

    walk_forward_results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": 1.6, "max_drawdown": -0.12},
    }

    phase4_results = {
        "without_filter": {"sharpe_ratio": 1.2},
        "with_filter_0.5": {"sharpe_ratio": 1.8},
    }

    strategy_config = {
        "metadata": {"git_commit": "abc123"},
    }

    # Run checklist
    checklist = run_pre_deployment_checklist(
        model_metrics=model_metrics,
        walk_forward_results=walk_forward_results,
        phase4_results=phase4_results,
        strategy_config=strategy_config,
    )

    # All items should pass
    assert all(item["passed"] for item in checklist.values())
