import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from trading_platform.ai.evaluation.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_statistical_significance,
    get_classification_metrics,
)


# Fixtures for PnL series
@pytest.fixture
def positive_pnl_series():
    return pd.Series([0.01, 0.02, 0.015, 0.005])


@pytest.fixture
def negative_pnl_series():
    return pd.Series([-0.01, -0.02, -0.015, -0.005])


@pytest.fixture
def mixed_pnl_series():
    return pd.Series([0.01, -0.005, 0.02, -0.01, 0.015])


@pytest.fixture
def zero_std_pnl_series():
    return pd.Series([0.01, 0.01, 0.01, 0.01])


@pytest.fixture
def zero_downside_std_pnl_series():
    return pd.Series([0.01, 0.02, 0.03, 0.04])


# Fixtures for classification metrics
@pytest.fixture
def y_true_binary():
    return pd.Series([0, 1, 0, 1, 0, 1])


@pytest.fixture
def y_pred_binary():
    return pd.Series([0, 1, 1, 1, 0, 0])


@pytest.fixture
def y_prob_binary():
    return pd.Series([0.1, 0.9, 0.6, 0.8, 0.2, 0.3])


# Fixtures for statistical significance
@pytest.fixture
def scores_a_significant():
    return [0.8, 0.85, 0.79, 0.82, 0.83]


@pytest.fixture
def scores_b_significant():
    return [0.7, 0.72, 0.68, 0.71, 0.73]


@pytest.fixture
def scores_no_significant_difference():
    return [0.8, 0.81, 0.79, 0.82, 0.8]


class TestFinancialMetrics:
    def test_calculate_sharpe_ratio_positive_pnl(self, positive_pnl_series):
        sharpe = calculate_sharpe_ratio(positive_pnl_series)
        # Expected value calculated manually or with a known library
        expected_sharpe = (
            positive_pnl_series.mean() / positive_pnl_series.std()
        ) * np.sqrt(252)
        assert pytest.approx(sharpe) == expected_sharpe

    def test_calculate_sharpe_ratio_negative_pnl(self, negative_pnl_series):
        sharpe = calculate_sharpe_ratio(negative_pnl_series)
        expected_sharpe = (
            negative_pnl_series.mean() / negative_pnl_series.std()
        ) * np.sqrt(252)
        assert pytest.approx(sharpe) == expected_sharpe

    def test_calculate_sharpe_ratio_mixed_pnl(self, mixed_pnl_series):
        sharpe = calculate_sharpe_ratio(mixed_pnl_series)
        expected_sharpe = (mixed_pnl_series.mean() / mixed_pnl_series.std()) * np.sqrt(
            252
        )
        assert pytest.approx(sharpe) == expected_sharpe

    def test_calculate_sharpe_ratio_zero_std(self, zero_std_pnl_series):
        sharpe = calculate_sharpe_ratio(zero_std_pnl_series)
        assert sharpe == 0.0

    def test_calculate_sharpe_ratio_custom_periods(self, positive_pnl_series):
        sharpe = calculate_sharpe_ratio(positive_pnl_series, periods_per_year=12)
        expected_sharpe = (
            positive_pnl_series.mean() / positive_pnl_series.std()
        ) * np.sqrt(12)
        assert pytest.approx(sharpe) == expected_sharpe

    def test_calculate_sortino_ratio_positive_pnl(self, positive_pnl_series):
        sortino = calculate_sortino_ratio(positive_pnl_series)
        # For positive PnL, downside_returns.std() will be 0, so Sortino should be 0.0
        assert sortino == 0.0

    def test_calculate_sortino_ratio_negative_pnl(self, negative_pnl_series):
        sortino = calculate_sortino_ratio(negative_pnl_series)
        downside_returns = negative_pnl_series[negative_pnl_series < 0]
        expected_sortino = (
            negative_pnl_series.mean() / downside_returns.std()
        ) * np.sqrt(252)
        assert pytest.approx(sortino) == expected_sortino

    def test_calculate_sortino_ratio_mixed_pnl(self, mixed_pnl_series):
        sortino = calculate_sortino_ratio(mixed_pnl_series)
        downside_returns = mixed_pnl_series[mixed_pnl_series < 0]
        expected_sortino = (mixed_pnl_series.mean() / downside_returns.std()) * np.sqrt(
            252
        )
        assert pytest.approx(sortino) == expected_sortino

    def test_calculate_sortino_ratio_zero_downside_std(
        self, zero_downside_std_pnl_series
    ):
        sortino = calculate_sortino_ratio(zero_downside_std_pnl_series)
        assert sortino == 0.0

    def test_calculate_sortino_ratio_custom_periods(self, mixed_pnl_series):
        sortino = calculate_sortino_ratio(mixed_pnl_series, periods_per_year=12)
        downside_returns = mixed_pnl_series[mixed_pnl_series < 0]
        expected_sortino = (mixed_pnl_series.mean() / downside_returns.std()) * np.sqrt(
            12
        )
        assert pytest.approx(sortino) == expected_sortino


class TestClassificationMetrics:
    def test_get_classification_metrics_basic(
        self, y_true_binary, y_pred_binary, y_prob_binary
    ):
        metrics = get_classification_metrics(
            y_true_binary, y_pred_binary, y_prob_binary
        )

        assert pytest.approx(metrics["accuracy"]) == accuracy_score(
            y_true_binary, y_pred_binary
        )
        assert pytest.approx(metrics["precision"]) == precision_score(
            y_true_binary, y_pred_binary
        )
        assert pytest.approx(metrics["recall"]) == recall_score(
            y_true_binary, y_pred_binary
        )
        assert pytest.approx(metrics["f1_score"]) == f1_score(
            y_true_binary, y_pred_binary
        )
        assert pytest.approx(metrics["roc_auc"]) == roc_auc_score(
            y_true_binary, y_prob_binary
        )

    def test_get_classification_metrics_perfect_prediction(self, y_true_binary):
        y_pred_perfect = y_true_binary
        y_prob_perfect = pd.Series([0.1 if x == 0 else 0.9 for x in y_true_binary])
        metrics = get_classification_metrics(
            y_true_binary, y_pred_perfect, y_prob_perfect
        )

        assert metrics["accuracy"] == 1.0
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1_score"] == 1.0
        assert metrics["roc_auc"] == 1.0

    def test_get_classification_metrics_worst_prediction(self, y_true_binary):
        y_pred_worst = 1 - y_true_binary  # Invert predictions
        y_prob_worst = pd.Series([0.9 if x == 0 else 0.1 for x in y_true_binary])
        metrics = get_classification_metrics(y_true_binary, y_pred_worst, y_prob_worst)

        assert metrics["accuracy"] == 0.0
        assert metrics["precision"] == 0.0  # No true positives
        assert metrics["recall"] == 0.0  # No true positives
        assert metrics["f1_score"] == 0.0  # No true positives
        assert metrics["roc_auc"] == 0.0


class TestStatisticalSignificance:
    def test_calculate_statistical_significance_significant(
        self, scores_a_significant, scores_b_significant
    ):
        result = calculate_statistical_significance(
            scores_a_significant, scores_b_significant
        )
        # Check if p-value is below a common significance level (e.g., 0.05)
        assert result["p_value"] < 0.05
        assert isinstance(result["t_statistic"], float)
        assert isinstance(result["p_value"], float)

    def test_calculate_statistical_significance_no_significant_difference(
        self, scores_a_significant, scores_no_significant_difference
    ):
        result = calculate_statistical_significance(
            scores_a_significant, scores_no_significant_difference
        )
        assert result["p_value"] > 0.05  # Should not be significant

    def test_calculate_statistical_significance_identical_scores(
        self, scores_a_significant
    ):
        result = calculate_statistical_significance(
            scores_a_significant, scores_a_significant
        )
        assert pytest.approx(result["t_statistic"]) == 0.0
        assert result["p_value"] == 1.0  # Identical means no difference
