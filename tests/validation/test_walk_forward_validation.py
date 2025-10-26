from __future__ import annotations

from typing import Any

import pandas as pd


def test_split_data_into_periods() -> None:
    """Test splitting data into yearly periods."""
    from trading_platform.validation.walk_forward import split_into_periods

    # Create DataFrame with dates from 2019-2023
    dates = pd.date_range("2019-01-01", "2023-12-31", freq="D")
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [1.1] * len(dates),
            "close": [1.15] * len(dates),
        }
    )

    # Split by year
    periods = split_into_periods(df, period="year")

    # Should have 5 periods (2019, 2020, 2021, 2022, 2023)
    assert len(periods) == 5

    # Each period should contain only data from its year
    for i, period_df in enumerate(periods):
        year = 2019 + i
        assert all(period_df["timestamp"].dt.year == year)
        assert len(period_df) > 0


def test_split_data_into_quarters() -> None:
    """Test splitting data into quarterly periods."""
    from trading_platform.validation.walk_forward import split_into_periods

    # Create DataFrame with 2 years of data
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "value": range(len(dates)),
        }
    )

    # Split by quarter
    periods = split_into_periods(df, period="quarter")

    # Should have 8 quarters (4 per year × 2 years)
    assert len(periods) == 8

    # Each period should be a quarter
    for period_df in periods:
        assert len(period_df) > 0


def test_walk_forward_validate() -> None:
    """Test walk-forward validation loop."""
    from trading_platform.validation.walk_forward import walk_forward_validate

    # Create mock data for 3 years
    dates = pd.date_range("2019-01-01", "2021-12-31", freq="D")
    data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [1.1] * len(dates),
            "close": [1.15] * len(dates),
        }
    )

    # Split into yearly periods
    from trading_platform.validation.walk_forward import split_into_periods

    periods = split_into_periods(data, period="year")

    # Mock strategy config
    strategy_config = {"strategy": "test"}

    # Track calls to training and backtest functions
    train_calls = []
    backtest_calls = []

    def mock_train_model(training_data: pd.DataFrame) -> dict[str, Any]:
        train_calls.append(len(training_data))
        return {"model": "trained"}

    def mock_run_backtest(
        config: dict[str, Any], test_data: pd.DataFrame
    ) -> dict[str, Any]:
        backtest_calls.append(len(test_data))
        return {"sharpe_ratio": 1.5, "max_drawdown": -0.15}

    # Run walk-forward validation
    results = walk_forward_validate(
        data=data,
        strategy_config=strategy_config,
        periods=periods,
        train_model_fn=mock_train_model,
        run_backtest_fn=mock_run_backtest,
    )

    # Should have 2 test periods
    # (train on year 1, test on year 2; train on years 1-2, test on year 3)
    assert len(results) == 2
    assert len(train_calls) == 2
    assert len(backtest_calls) == 2

    # Each result should have performance metrics
    for period_name, metrics in results.items():
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics


def test_check_performance_consistency() -> None:
    """Test performance consistency check."""
    from trading_platform.validation.walk_forward import check_performance_consistency

    # Create consistent results (all positive Sharpe ratios)
    consistent_results = {
        "2020": {"sharpe_ratio": 1.5, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": 1.6, "max_drawdown": -0.12},
        "2022": {"sharpe_ratio": 1.4, "max_drawdown": -0.18},
    }

    # Should be consistent (low coefficient of variation)
    assert check_performance_consistency(
        consistent_results, metric="sharpe_ratio", tolerance=0.3
    )

    # Create inconsistent results (high variation)
    inconsistent_results = {
        "2020": {"sharpe_ratio": 2.0, "max_drawdown": -0.15},
        "2021": {"sharpe_ratio": -0.5, "max_drawdown": -0.45},
        "2022": {"sharpe_ratio": 1.5, "max_drawdown": -0.20},
    }

    # Should be inconsistent
    assert not check_performance_consistency(
        inconsistent_results, metric="sharpe_ratio", tolerance=0.3
    )
