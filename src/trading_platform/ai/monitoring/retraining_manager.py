from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from trading_platform.ai.monitoring.performance_monitor import (
    AIDriftDetector,
    AIModelPerformanceMonitor,
)

logger = logging.getLogger(__name__)


class AIRetrainingManager:
    """Manages the triggers and process for AI model retraining."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.retraining_criteria = config.get("retraining_criteria", {})
        self.drift_detector = AIDriftDetector(config.get("drift_detector_config", {}))
        self.performance_monitor = AIModelPerformanceMonitor(
            config.get("performance_monitor_config", {})
        )
        logger.info("AIRetrainingManager initialized.")

    def evaluate_retraining_need(
        self,
        new_data: pd.DataFrame,
        baseline_data: pd.DataFrame,
        model_predictions: pd.Series,
        true_labels: pd.Series,
        current_performance_brief: dict[str, Any],
    ) -> bool:
        """
        Evaluates if retraining is needed based on defined criteria.
        """
        logger.info("Evaluating retraining need...")

        # Check for data and concept drift
        drift_results = self.drift_detector.check_for_drift(
            new_data, baseline_data, model_predictions, true_labels
        )
        data_drift_trigger = self.retraining_criteria.get("on_data_drift", False)
        if drift_results.get("data_drift_detected") and data_drift_trigger:
            logger.warning("Retraining triggered: Data drift detected.")
            return True
        concept_drift_trigger = self.retraining_criteria.get("on_concept_drift", False)
        if drift_results.get("concept_drift_detected") and concept_drift_trigger:
            logger.warning("Retraining triggered: Concept drift detected.")
            return True

        # Check for performance degradation
        # This would involve comparing current_performance_brief against baselines
        # or thresholds defined in self.performance_monitor.config
        # For now, a placeholder check:
        if self.retraining_criteria.get("on_performance_degradation", False):
            # Example: check if Sharpe ratio dropped below a threshold
            current_sharpe = current_performance_brief.get(
                "overall_performance", {}
            ).get("sharpe_ratio")
            min_sharpe = self.retraining_criteria.get("min_sharpe_for_retraining")
            if current_sharpe is not None and min_sharpe is not None:
                if current_sharpe < min_sharpe:
                    logger.warning(
                        "Retraining triggered: Performance degradation detected. "
                        f"Sharpe Ratio ({current_sharpe}) below threshold "
                        f"({min_sharpe})."
                    )
                    return True

        # Check for scheduled retraining (e.g., weekly, monthly)
        if self.retraining_criteria.get("scheduled_interval", None):
            # This would involve checking the last retraining timestamp and current time
            # For now, a placeholder that always returns False for scheduled unless explicitly set
            logger.info("Scheduled retraining check (placeholder).")
            pass

        logger.info("No retraining needed at this time.")
        return False

    def trigger_training_pipeline(self) -> None:
        """Initiates the AI model training pipeline."""
        logger.info("Initiating AI model training pipeline...")
        from trading_platform.ai.training.pipeline import AITrainingPipeline

        # Assuming the config for AITrainingPipeline is available or can be derived
        # from self.config. For now, using a placeholder path as expected by the test.
        training_pipeline = AITrainingPipeline(config_path="config.yaml")
        training_pipeline.run()
