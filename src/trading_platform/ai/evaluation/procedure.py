"""
This module defines the standardized evaluation procedure for AI models.
"""

from typing import Any, Dict, List

import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from trading_platform.ai.evaluation.metrics import get_classification_metrics


class AIEvaluationProcedure:
    """
    Orchestrates a standardized evaluation process for a trained model.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the evaluation procedure with a given configuration.
        """
        self.config = config

    def run_cross_validation(
        self, model: Any, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, Any]:
        """
        Performs time-series cross-validation and returns aggregated metrics.
        """
        print("Performing time-series cross-validation...")
        cv_config = self.config.get("cross_validation", {})
        n_splits = cv_config.get("n_splits", 5)

        tscv = TimeSeriesSplit(n_splits=n_splits)

        all_scores: List[Dict[str, float]] = []
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"  - Fold {fold+1}/{n_splits}")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test) # type: ignore
            y_prob_raw = model.predict_proba(X_test) # type: ignore
            # For binary classification, predict_proba can return (n_samples,) or (n_samples, 2)
            # If (n_samples, 2), we take the probability of the positive class (index 1)
            # If (n_samples,), it's already the probability of the positive class
            y_prob = y_prob_raw[:, 1] if y_prob_raw.ndim == 2 else y_prob_raw

            # Placeholder for calculating metrics for the fold
            fold_scores = get_classification_metrics(y_test, y_pred, y_prob)
            all_scores.append(fold_scores)

        # Aggregate scores across all folds
        df_scores = pd.DataFrame(all_scores)
        mean_scores = df_scores.mean().to_dict()
        std_scores = df_scores.std().to_dict()

        # Format the final report
        aggregated_scores = {f"mean_{key}": value for key, value in mean_scores.items()}
        aggregated_scores.update(
            {f"std_{key}": value for key, value in std_scores.items()}
        )

        print("Cross-validation complete.")
        return aggregated_scores

    def run_stress_testing(self, model: Any, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Placeholder for performing stress tests on the model.
        This would involve evaluating the model on curated slices of data
        representing specific market conditions (e.g., high volatility).
        """
        print("Performing stress testing (placeholder)...")
        # Example: Test on a high volatility slice of data
        # high_vol_data = data[data['volatility'] > 0.8]
        # ... evaluate model on high_vol_data ...
        stress_test_results = {"performance_in_high_vol": "degraded"}
        print("Stress testing complete.")
        return stress_test_results

    def run_bias_detection(self, model: Any, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Placeholder for bias detection procedures.
        This could involve checking for performance disparities across
        different regimes or other data segments.
        """
        print("Performing bias detection (placeholder)...")
        bias_detection_results = {"bias_found": "none"}
        print("Bias detection complete.")
        return bias_detection_results

    def run(self, model: Any, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """
        Executes the full evaluation procedure.
        """
        print("--- Starting AI Evaluation Procedure ---")

        results = {}

        if self.config.get("run_cross_validation", False):
            results["cross_validation"] = self.run_cross_validation(model, X, y)

        if self.config.get("run_stress_testing", False):
            # Note: Stress testing might require the full dataset with features
            results["stress_testing"] = self.run_stress_testing(model, X)

        if self.config.get("run_bias_detection", False):
            results["bias_detection"] = self.run_bias_detection(model, X)

        print("--- AI Evaluation Procedure finished successfully. ---")
        return results
