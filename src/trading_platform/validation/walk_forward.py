from __future__ import annotations

from typing import Any, Callable

import pandas as pd


def split_into_periods(df: pd.DataFrame, period: str = "year") -> list[pd.DataFrame]:
    """
    Split DataFrame into periods (year, quarter, or month).

    Args:
        df: DataFrame with 'timestamp' column
        period: Period granularity ('year', 'quarter', or 'month')

    Returns:
        List of DataFrames, one per period
    """
    if "timestamp" not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if period == "year":
        df["period"] = df["timestamp"].dt.year
    elif period == "quarter":
        df["period"] = df["timestamp"].dt.to_period("Q").astype(str)
    elif period == "month":
        df["period"] = df["timestamp"].dt.to_period("M").astype(str)
    else:
        raise ValueError(
            f"Invalid period: {period}. Must be 'year', 'quarter', or 'month'"
        )

    # Group by period and create list of DataFrames
    periods = []
    for _, group in df.groupby("period", sort=True):
        period_df = group.drop(columns=["period"]).reset_index(drop=True)
        periods.append(period_df)

    return periods


def walk_forward_validate(
    data: pd.DataFrame,
    strategy_config: dict[str, Any],
    periods: list[pd.DataFrame],
    train_model_fn: Callable[[pd.DataFrame], dict[str, Any]],
    run_backtest_fn: Callable[[dict[str, Any], pd.DataFrame], dict[str, Any]],
) -> dict[str, Any]:
    """
    Perform walk-forward validation.

    For each period N:
    - Training data: all periods up to N
    - Test data: period N+1
    - Train model on training data
    - Run backtest on test data
    - Store results for period N+1

    Args:
        data: Full dataset
        strategy_config: Strategy configuration
        periods: List of period DataFrames
        train_model_fn: Function to train model, returns model dict
        run_backtest_fn: Function to run backtest, returns metrics dict

    Returns:
        Dict mapping period names to performance metrics
    """
    results = {}

    # Walk forward through periods
    for i in range(len(periods) - 1):
        # Training data: concatenate all periods up to i
        training_data = pd.concat(periods[: i + 1], ignore_index=True)

        # Test data: period i+1
        test_data = periods[i + 1]

        # Train model
        _ = train_model_fn(training_data)  # Model returned but not used here

        # Run backtest on test period
        performance = run_backtest_fn(strategy_config, test_data)

        # Store results with period name
        period_name = f"period_{i + 1}"
        if "timestamp" in test_data.columns:
            min_date = test_data["timestamp"].min()
            max_date = test_data["timestamp"].max()
            period_name = (
                f"{min_date.year}-{min_date.month:02d} to "
                f"{max_date.year}-{max_date.month:02d}"
            )

        results[period_name] = performance

    return results


def check_performance_consistency(
    results: dict[str, Any], metric: str = "sharpe_ratio", tolerance: float = 0.3
) -> bool:
    """
    Check if performance is consistent across periods.

    Uses coefficient of variation (std/mean) to measure consistency.

    Args:
        results: Dict of period results with performance metrics
        metric: Metric to check for consistency
        tolerance: Maximum coefficient of variation to consider consistent

    Returns:
        True if consistent, False otherwise
    """
    if not results:
        return False

    # Extract metric values
    values = []
    for period_metrics in results.values():
        if metric in period_metrics:
            values.append(period_metrics[metric])

    if not values or len(values) < 2:
        return False

    # Calculate coefficient of variation
    mean_val = sum(values) / len(values)
    if mean_val == 0:
        return False

    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    std_val = variance**0.5
    coefficient_of_variation = std_val / abs(mean_val)

    return bool(coefficient_of_variation <= tolerance)
