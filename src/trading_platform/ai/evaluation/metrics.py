"""
This module defines evaluation metrics for the AI Lab's models.
It includes standard ML metrics as well as custom trading-specific metrics.
"""

from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
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
    if downside_returns.empty:
        return 0.0  # No downside returns, so Sortino is 0.0
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


def calculate_statistical_significance(
    scores_a: List[float], scores_b: List[float]
) -> Dict[str, float]:
    """
    Performs an independent t-test to compare two sets of performance scores.

    Args:
        scores_a: A list of performance scores from model A (e.g., from CV folds).
        scores_b: A list of performance scores from model B.

    Returns:
        A dictionary containing the t-statistic and the p-value.
    """
    t_stat, p_value = ttest_ind(scores_a, scores_b, equal_var=False)
    return {"t_statistic": t_stat, "p_value": p_value}


# Placeholder for other custom metrics
# For example, metrics related to trade duration, MFE/MAE of predicted trades, etc.
