"""
This module defines evaluation metrics for the AI Lab's models.
It includes standard ML metrics as well as custom trading-specific metrics.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def calculate_sharpe_ratio(pnl_series: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculates the annualized Sharpe Ratio from a series of PnL values.

    Args:
        pnl_series: A pandas Series of PnL values (e.g., daily returns).
        periods_per_year: The number of periods in a year for annualization.

    Returns:
        The annualized Sharpe Ratio. Returns 0 if standard deviation is zero.
    """
    if pnl_series.std() == 0:
        return 0.0
    return float((pnl_series.mean() / pnl_series.std()) * np.sqrt(periods_per_year))


def calculate_sortino_ratio(
    pnl_series: pd.Series, periods_per_year: int = 252
) -> float:
    """
    Calculates the annualized Sortino Ratio from a series of PnL values.

    Args:
        pnl_series: A pandas Series of PnL values.
        periods_per_year: The number of periods in a year for annualization.

    Returns:
        The annualized Sortino Ratio. Returns 0 if downside deviation is zero.
    """
    downside_returns = pnl_series[pnl_series < 0]
    downside_std = downside_returns.std()
    if downside_std == 0:
        return 0.0
    return float((pnl_series.mean() / downside_std) * np.sqrt(periods_per_year))


def get_classification_metrics(
    y_true: pd.Series, y_pred: pd.Series, y_prob: pd.Series
) -> dict:
    """
    Calculates and returns a dictionary of standard classification metrics.
    """
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred),
        "f1_score": f1_score(y_true, y_pred),
        "roc_auc": roc_auc_score(y_true, y_prob),
    }
    return metrics


# Placeholder for other custom metrics
# For example, metrics related to trade duration, MFE/MAE of predicted trades, etc.
